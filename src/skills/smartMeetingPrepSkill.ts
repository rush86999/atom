import { findCalendarEventByFuzzyReference, CalendarEventSummary, DateHints } from './calendarSkills';

// Define the expected structure of the skill's input
export interface SmartMeetingPrepSkillInput {
  userId: string;
  meeting_reference: string; // e.g., "my meeting tomorrow morning", "the project sync-up"
  // Potentially other context like preferred language for summaries, etc.
}

import { searchEmailsForPrep } from '../../atomic-docker/project/functions/atom-agent/skills/gmailSkills';
// Assuming types.ts is correctly located relative to gmailSkills.ts for these:
import { GmailSearchParameters, GmailMessageSnippet, NotionPageSummary } from '../../atomic-docker/project/functions/atom-agent/types';
import { searchNotionNotes, getNotionPageSummaryById } from '../../atomic-docker/project/functions/atom-agent/skills/notionAndResearchSkills';
import { logger } from '../../../atomic-docker/project/functions/_utils/logger'; // Assuming logger path
import { NOTION_NOTES_DATABASE_ID } from '../../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { storeEmailSnippetInLanceDb, storeNotionPageSummaryInLanceDb } from './lanceDbStorageSkills'; // Added LanceDB storage

const COMMON_STOP_WORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'for', 'if', 'in', 'into', 'is', 'it', 'its',
  'of', 'on', 'or', 'our', 'so', 'such', 'that', 'the', 'their', 'theirs', 'them', 'then', 'there', 'these',
  'they', 'this', 'to', 'was', 'will', 'with', 'about', 'above', 'after', 'again', 'all', 'am', 'any',
  'because', 'been', 'before', 'being', 'below', 'between', 'both', 'can', 'did', 'do', 'does', 'doing',
  'down', 'during', 'each', 'few', 'from', 'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here',
  'hers', 'herself', 'him', 'himself', 'his', 'how', 'i', 'just', 'me', 'my', 'myself', 'no', 'nor', 'not',
  'now', 'only', 'other', 'ought', 'out', 'over', 'own', 'same', 'she', 'should', 'some', 'still', 'than',
  'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which', 'while',
  'who', 'whom', 'why', 'would', 'you', 'your', 'yours', 'yourself', 'yourselves',
  // Common meeting/calendar terms that might not be good search keywords
  'meeting', 'call', 'sync', 'update', 'discuss', 'review', 'agenda', 'minutes', 'notes', 'event', 'schedule',
  'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
  'am', 'pm', 'morning', 'afternoon', 'evening', 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
]);


// Define the expected structure of the skill's output
export interface SmartMeetingPrepSkillOutput {
  resolvedEvent?: CalendarEventSummary;
  preparationNotes?: string;
  relatedDocuments?: any[]; // Using any for mock documents for now
  relatedEmails?: GmailMessageSnippet[];
  relatedNotionPages?: NotionPageSummary[];
  semanticallyRelatedItems?: UniversalSearchResultItem[]; // Added for semantic search results
  // other output fields
}

export class SmartMeetingPrepSkill {
  constructor() {
    // Initialization logic for the skill, if any (e.g., API clients, settings)
  }

  private _extractKeywords(text: string, minLength = 3, maxKeywords = 10): string[] {
    if (!text) return [];
    const words = text.toLowerCase().split(/[^a-z0-9'-]+/); // Split by non-alphanumeric, keep hyphens/apostrophes
    const keywords = words.filter(word => {
      if (word.length < minLength) return false;
      if (COMMON_STOP_WORDS.has(word)) return false;
      if (/^\d+$/.test(word)) return false; // Exclude numbers-only strings
      return true;
    });
    // Simple frequency analysis to get most relevant terms if too many keywords
    if (keywords.length > maxKeywords * 2) { // Heuristic: only do frequency if significantly more keywords
        const freqMap = new Map<string, number>();
        keywords.forEach(kw => freqMap.set(kw, (freqMap.get(kw) || 0) + 1));
        return Array.from(freqMap.entries())
            .sort((a, b) => b[1] - a[1]) // Sort by frequency desc
            .slice(0, maxKeywords)
            .map(entry => entry[0]);
    }
    return Array.from(new Set(keywords)).slice(0, maxKeywords); // Return unique keywords up to maxKeywords
  }

  private _getAttendeeEmails(attendees?: string[]): string[] {
    if (!attendees || attendees.length === 0) return [];
    const emailRegex = /<([^>]+)>/;
    const emails: string[] = [];
    attendees.forEach(attendeeString => {
      const match = attendeeString.match(emailRegex);
      if (match && match[1]) {
        emails.push(match[1].toLowerCase().trim());
      } else if (attendeeString.includes('@') && !attendeeString.includes('<') && !attendeeString.includes('>')) {
        const potentialEmail = attendeeString.split(/\s+/).find(part => part.includes('@'));
        if (potentialEmail) {
            emails.push(potentialEmail.toLowerCase().trim());
        }
      }
    });
    return [...new Set(emails)]; // Unique emails
  }

  private _scoreEmailRelevance(
    email: GmailMessageSnippet,
    titleKeywords: string[],
    descriptionKeywords: string[],
    attendeeEmails: string[],
    meetingStartDate: Date
  ): number {
    let score = 0;
    const emailSubjectLower = (email.subject || '').toLowerCase();
    const emailSnippetLower = (email.snippet || '').toLowerCase();
    const emailFromLower = (email.from || '').toLowerCase();

    // Keyword matching
    titleKeywords.forEach(kw => {
      if (emailSubjectLower.includes(kw)) score += 3;
      if (emailSnippetLower.includes(kw)) score += 2; // Snippet match slightly less weight
    });
    descriptionKeywords.forEach(kw => {
      if (emailSubjectLower.includes(kw)) score += 2;
      if (emailSnippetLower.includes(kw)) score += 1;
    });

    // Attendee involvement (checking 'from' field)
    if (attendeeEmails.some(attEmail => emailFromLower.includes(attEmail))) {
      score += 4;
    }
    // TODO: If 'to'/'cc' fields were available, check them too.

    // Recency
    if (email.date) {
      try {
        const emailDate = new Date(email.date);
        const diffDays = (meetingStartDate.getTime() - emailDate.getTime()) / (1000 * 3600 * 24);
        if (diffDays >= 0 && diffDays <= 2) score += 3; // Within 2 days before meeting
        else if (diffDays > 2 && diffDays <= 7) score += 2; // Within 3-7 days
        else if (diffDays > 7 && diffDays <= 30) score += 1; // Within fetched window (assuming it's not too large)
      } catch (e) {
        logger.warn(`Could not parse email date for scoring: ${email.date}`);
      }
    }
    return score;
  }

  private _scoreNotionPageRelevance(
    page: NotionPageSummary,
    titleKeywords: string[],
    descriptionKeywords: string[],
    meetingStartDate: Date, // For recency of edit
    isExplicitLink: boolean
  ): number {
    let score = 0;
    const pageTitleLower = (page.title || '').toLowerCase();
    const pagePreviewLower = (page.preview_text || '').toLowerCase();

    if (isExplicitLink) {
      score += 10; // High score for explicitly linked pages
    }

    // Keyword matching
    titleKeywords.forEach(kw => {
      if (pageTitleLower.includes(kw)) score += 3;
      if (pagePreviewLower.includes(kw)) score += 2;
    });
    descriptionKeywords.forEach(kw => {
      if (pageTitleLower.includes(kw)) score += 2;
      if (pagePreviewLower.includes(kw)) score += 1;
    });

    // Recency of edit
    if (page.last_edited_time) {
      try {
        const editedDate = new Date(page.last_edited_time);
        const diffDays = (meetingStartDate.getTime() - editedDate.getTime()) / (1000 * 3600 * 24);
        if (diffDays >= -7 && diffDays <= 7) score += 3; // Edited within a week around meeting prep time (allows for future edits too)
        else if (diffDays > 7 && diffDays <= 30) score += 2; // Edited within 1 month
        else if (diffDays > 30 && diffDays <= 90) score +=1;
      } catch (e) {
        logger.warn(`Could not parse Notion page last_edited_time for scoring: ${page.last_edited_time}`);
      }
    }
    return score;
  }

  private _getContextualSnippet(text: string | undefined | null, keywords: string[], maxLength: number = 150, contextWindow: number = 70): string {
    if (!text || text.trim() === "") return "";

    const lowerText = text.toLowerCase();
    let foundKeywordInfo: { index: number, length: number } | null = null;

    for (const kw of keywords) {
      if (!kw || kw.trim() === "") continue;
      const kwLower = kw.toLowerCase();
      const index = lowerText.indexOf(kwLower);
      if (index !== -1) {
        foundKeywordInfo = { index, length: kwLower.length };
        break;
      }
    }

    if (foundKeywordInfo) {
      const keywordStartIndex = foundKeywordInfo.index;
      const keywordEndIndex = keywordStartIndex + foundKeywordInfo.length;

      let start = Math.max(0, keywordStartIndex - contextWindow);
      let end = Math.min(text.length, keywordEndIndex + contextWindow);

      let prefix = start > 0 ? "... " : "";
      let suffix = end < text.length ? " ..." : "";

      let snippet = text.substring(start, end);

      // Adjust if snippet is too long with prefix/suffix
      if ((prefix + snippet + suffix).length > maxLength) {
        const remainingLength = maxLength - prefix.length - suffix.length;
        // Try to keep keyword somewhat centered if possible
        const keywordVisibleStart = Math.max(0, keywordStartIndex - start); // keyword start relative to snippet start
        const idealCutStart = Math.max(0, keywordVisibleStart - Math.floor(remainingLength / 2));
        const idealCutEnd = idealCutStart + remainingLength;

        snippet = snippet.substring(idealCutStart, idealCutEnd);
      }
       // Ensure snippet itself is not over maxLength if prefix/suffix are empty
      if (snippet.length > maxLength) {
        snippet = snippet.substring(0, maxLength -3) + "...";
      }


      return prefix + snippet + suffix;
    } else {
      // No keyword found, return beginning of text
      if (text.length <= maxLength) return text;
      return text.substring(0, maxLength - 3) + "...";
    }
  }

  /**
   * Executes the smart meeting preparation skill.
   *
   * @param input - The input parameters for the skill.
   * @returns A promise that resolves to the skill's output, including the resolved event
   *          and any generated preparation materials (though initially just the event).
   */
  public async execute(input: SmartMeetingPrepSkillInput): Promise<SmartMeetingPrepSkillOutput> {
    console.log(`SmartMeetingPrepSkill: Received request for userId: ${input.userId}, meeting_reference: "${input.meeting_reference}"`);

    // Step 1: Resolve the calendar event
    // For now, date_hints is undefined. This could be derived or passed in input in the future.
    const date_hints: DateHints | undefined = undefined;

    const resolvedEvent = await findCalendarEventByFuzzyReference(
      input.userId,
      input.meeting_reference,
      date_hints
    );

    let preparationNotes: string | undefined = undefined;
    let relatedDocuments: any[] = [];
    let relatedEmails: GmailMessageSnippet[] = [];
    let relatedNotionPages: NotionPageSummary[] = [];
    const dataFetchingErrors: string[] = [];

    if (resolvedEvent) {
      console.log(`SmartMeetingPrepSkill: Resolved event - Title: ${resolvedEvent.title}, StartTime: ${resolvedEvent.startTime}`);

      // Step 2: Find related documents (mocked)
      relatedDocuments = await this._findRelatedDocuments(resolvedEvent);

      // Step 3: Find related emails
      const gmailSearchParams: GmailSearchParameters = {
        // Initially, let's use a generic date query and rely on meetingContext for date refinement.
        // Specific keywords can be added later if needed, or derived from event title/description.
        date_query: "recent", // `searchEmailsForPrep` will use meeting context to refine this
        // body_keywords: resolvedEvent.title, // Optionally add title to body_keywords
      };

      try {
        console.log(`SmartMeetingPrepSkill: Searching emails for event "${resolvedEvent.title}"`);
        const emailSearchResponse = await searchEmailsForPrep(
          input.userId,
          gmailSearchParams,
          resolvedEvent, // Pass the whole event as meetingContext
          5 // Limit to 5 emails for now
        );

        if (emailSearchResponse.ok && emailSearchResponse.data?.results) {
          relatedEmails = emailSearchResponse.data.results;
          console.log(`SmartMeetingPrepSkill: Found ${relatedEmails.length} related emails.`);
        } else {
          const errorMsg = `Email search failed or returned no results. Error: ${emailSearchResponse.error?.message || 'Unknown email search error'}`;
          logger.warn(`SmartMeetingPrepSkill: ${errorMsg}`);
          dataFetchingErrors.push(errorMsg);
        }
      } catch (error: any) {
        const errorMsg = `Error calling searchEmailsForPrep: ${error.message}`;
        logger.error(`SmartMeetingPrepSkill: ${errorMsg}`, error);
        dataFetchingErrors.push(errorMsg);
      }

      // Step 4: Find related Notion pages
      const notionPageMap = new Map<string, NotionPageSummary>(); // To store unique pages by ID

      // 4a. Extract Notion links from description
      if (resolvedEvent.description) {
        const notionUrlRegex = /https:\/\/www\.notion\.so\/([\w.-]+?\/)?([\w-]+)(?:\?pvs=[\w-]+)?(?:#[\w-]+)?/g;
        let match;
        const pageIdsFromLinks: string[] = [];
        while ((match = notionUrlRegex.exec(resolvedEvent.description)) !== null) {
          // The last part of the path before any query params is usually the page ID, sometimes prefixed by title-slug
          // match[2] should be the page_id part (e.g., workspaceName/pageTitle-pageID -> pageID, or pageTitleAndID -> ID part)
          // Notion page IDs are typically 32 hex characters, but can also be part of a slug.
          // A common pattern is title-and-slug-RandomPageID, where RandomPageID is what we want.
          // Or for DB items, just the ID.
          const potentialId = match[2].split('-').pop(); // Get the last part after splitting by hyphen
          if (potentialId && potentialId.length >= 32) { // Heuristic for typical Notion ID length
             // Remove any non-hex characters just in case, though Notion IDs are usually clean hex
            pageIdsFromLinks.push(potentialId.replace(/[^a-f0-9]/gi, ''));
          } else if (potentialId) {
            // If it's shorter, it might be a custom slug or an older ID format.
            // For simplicity, we'll try it if it doesn't look like a common word.
            // A more robust solution would involve checking Notion API if a slug is a page.
            // For now, we'll assume the long ID is the primary target.
            // console.log(`Potential shorter ID or slug found: ${potentialId} from URL ${match[0]}. Skipping for now unless logic is enhanced.`);
          }
        }

        const uniquePageIds = [...new Set(pageIdsFromLinks)];
        console.log(`SmartMeetingPrepSkill: Found ${uniquePageIds.length} unique Notion page IDs from description: ${uniquePageIds.join(', ')}`);

        for (const pageId of uniquePageIds) {
          try {
            // Using the mocked getNotionPageSummaryById for now
            const pageSummaryResponse = await getNotionPageSummaryById(input.userId, pageId);
            if (pageSummaryResponse.ok && pageSummaryResponse.data) {
              notionPageMap.set(pageSummaryResponse.data.id, pageSummaryResponse.data);
              logger.info(`SmartMeetingPrepSkill: Fetched Notion page "${pageSummaryResponse.data.title}" by ID ${pageId} from link.`);
            } else {
              const errorMsg = `Could not fetch Notion page by ID ${pageId} from link. Error: ${pageSummaryResponse.error?.message || 'Unknown error'}`;
              logger.warn(`SmartMeetingPrepSkill: ${errorMsg}`);
              dataFetchingErrors.push(errorMsg);
            }
          } catch (error: any) {
            const errorMsg = `Error calling getNotionPageSummaryById for ${pageId}: ${error.message}`;
            logger.error(`SmartMeetingPrepSkill: ${errorMsg}`, error);
            dataFetchingErrors.push(errorMsg);
          }
        }
      }

      // 4b. Keyword search if not enough found or to supplement
      const titleKeywords = this._extractKeywords(resolvedEvent.title, 3, 5);
      const descriptionKeywords = resolvedEvent.description ? this._extractKeywords(resolvedEvent.description, 3, 7) : [];

      let attendeeKeywords: string[] = [];
      if (resolvedEvent.attendees) {
        const attendeeNames = resolvedEvent.attendees.map(att => {
          const namePart = att.split('<')[0].trim();
          // Further split namePart if it's multiple words, take first 1-2 significant words
          return namePart.split(/\s+/).slice(0,2).join(' '); // e.g. "John Doe" -> "John Doe", "Dr. Jane Smith" -> "Dr. Jane"
        }).join(' ');
        attendeeKeywords = this._extractKeywords(attendeeNames, 3, 5);
      }

      const combinedKeywords = new Set([...titleKeywords, ...descriptionKeywords, ...attendeeKeywords]);
      const keywordQueryText = Array.from(combinedKeywords).join(' ');

      // Use logger instead of console.log for skill internals
      logger.info(`SmartMeetingPrepSkill: Notion keyword query: "${keywordQueryText}" (TitleKWs: [${titleKeywords.join(', ')}], DescKWs: [${descriptionKeywords.join(', ')}], AttKWs: [${attendeeKeywords.join(', ')}])`);

      // Keep track of page IDs that were explicitly linked
      const explicitLinkPageIds = new Set<string>();
      if (resolvedEvent.description) {
          const notionUrlRegex = /https:\/\/www\.notion\.so\/([\w.-]+?\/)?([\w-]+)(?:\?pvs=[\w-]+)?(?:#[\w-]+)?/g;
          let match;
          while ((match = notionUrlRegex.exec(resolvedEvent.description)) !== null) {
              const potentialId = match[2].split('-').pop();
              if (potentialId && potentialId.length >= 32) {
                  explicitLinkPageIds.add(potentialId.replace(/[^a-f0-9]/gi, ''));
              }
          }
      }

      if (keywordQueryText.trim().length > 0) {
        try {
          const searchLimit = Math.max(0, 5 - notionPageMap.size); // Ensure limit is not negative
          if (searchLimit > 0) {
            const keywordSearchResponse = await searchNotionNotes(
              input.userId,
              keywordQueryText,
              NOTION_NOTES_DATABASE_ID || undefined, // Use configured default, pass undefined if not set
              searchLimit
            );
            logger.info(`SmartMeetingPrepSkill: Notion keyword search using DB ID: ${NOTION_NOTES_DATABASE_ID || 'None (backend default)'}`);

            if (keywordSearchResponse.ok && keywordSearchResponse.data) {
              logger.info(`SmartMeetingPrepSkill: Found ${keywordSearchResponse.data.length} Notion pages from keyword search.`);
              keywordSearchResponse.data.forEach(page => {
                if (!notionPageMap.has(page.id)) { // Avoid duplicates
                  notionPageMap.set(page.id, page);
                }
              });
            } else {
              const errorMsg = `Notion keyword search failed or returned no results. Error: ${keywordSearchResponse.error?.message || 'Unknown Notion keyword search error'}`;
              logger.warn(`SmartMeetingPrepSkill: ${errorMsg}`);
              dataFetchingErrors.push(errorMsg);
            }
          } else {
            logger.info("SmartMeetingPrepSkill: Skipping keyword search for Notion as enough pages found from links or limit is zero.");
          }
        } catch (error: any) {
          const errorMsg = `Error calling searchNotionNotes: ${error.message}`;
          logger.error(`SmartMeetingPrepSkill: ${errorMsg}`, error);
          dataFetchingErrors.push(errorMsg);
        }
      } else {
        logger.info("SmartMeetingPrepSkill: No valid keywords generated for Notion search. Skipping keyword search.");
      }
      relatedNotionPages = Array.from(notionPageMap.values());

      // Step 4c: Score and select top items
      const meetingStartDate = new Date(resolvedEvent.startTime); // For recency scoring
      const eventTitleKeywords = this._extractKeywords(resolvedEvent.title, 2, 5);
      const eventDescKeywords = resolvedEvent.description ? this._extractKeywords(resolvedEvent.description, 3, 5) : [];
      const eventAttendeeEmails = this._getAttendeeEmails(resolvedEvent.attendees);

      const scoredEmails = relatedEmails.map(email => ({
        item: email,
        score: this._scoreEmailRelevance(email, eventTitleKeywords, eventDescKeywords, eventAttendeeEmails, meetingStartDate)
      })).sort((a, b) => b.score - a.score);

      const scoredNotionPages = relatedNotionPages.map(page => ({
        item: page,
        score: this._scoreNotionPageRelevance(page, eventTitleKeywords, eventDescKeywords, meetingStartDate, explicitLinkPageIds.has(page.id))
      })).sort((a, b) => b.score - a.score);

      const topEmails = scoredEmails.slice(0, 3); // Select top 3 emails
      const topNotionPages = scoredNotionPages.slice(0, 2); // Select top 2 Notion pages

      logger.info(`SmartMeetingPrepSkill: Top ${topEmails.length} emails selected (scores: ${topEmails.map(e => e.score.toFixed(1)).join(', ')})`);
      topEmails.forEach((se, idx) => logger.info(`TopEmail[${idx}] (Score: ${se.score.toFixed(1)}): ${se.item.subject?.substring(0,50)}... (From: ${se.item.from})`));

      logger.info(`SmartMeetingPrepSkill: Top ${topNotionPages.length} Notion pages selected (scores: ${topNotionPages.map(p => p.score.toFixed(1)).join(', ')})`);
      topNotionPages.forEach((sp, idx) => logger.info(`TopNotion[${idx}] (Score: ${sp.score.toFixed(1)}): ${sp.item.title?.substring(0,50)}... (ExplicitLink: ${explicitLinkPageIds.has(sp.item.id)})`));

      // For now, we still pass all emails/pages to _generatePreparationNotes.
      // The next step will be to use these topEmails/topNotionPages to create a "Highlights" section.
      // Or, _generatePreparationNotes could be modified to only show details for these top items.

      // Step 5: Generate preparation notes
      preparationNotes = await this._generatePreparationNotes(
        resolvedEvent,
        relatedDocuments,
        relatedEmails, // Pass all for now
        relatedNotionPages, // Pass all for now
        dataFetchingErrors,
        topEmails.map(e => e.item),
        topNotionPages.map(p => p.item),
        eventTitleKeywords,
        eventDescKeywords,
        uniqueSemanticallyRelatedItems // Pass de-duplicated semantic results
      );

      // Use logger for this type of info as well
      logger.info(`SmartMeetingPrepSkill: Successfully generated preparation materials for "${resolvedEvent.title}".`);


      // Step 4d: Perform Semantic Search for additional context
      let semanticallyRelatedItems: UniversalSearchResultItem[] = [];
      const semanticQueryText = resolvedEvent.title + (eventDescKeywords.length > 0 ? " " + eventDescKeywords.join(" ") : "");

      if (semanticQueryText.trim()) {
        const searchFilters: SemanticSearchFilters = {
          source_types: ["document_chunk", "email_snippet", "notion_summary"],
          // Optional: Add date filters if desired, e.g., based on meeting date
          // date_before: meetingStartDate.toISOString(),
          // date_after: new Date(meetingStartDate.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        };

        logger.info(`SmartMeetingPrepSkill: Performing semantic search with query: "${semanticQueryText.substring(0, 100)}..."`);
        try {
          const semanticSearchResponse = await semanticSearchLanceDb(
            input.userId,
            semanticQueryText,
            searchFilters,
            5 // Limit to 5 semantic results for now
          );

          if (semanticSearchResponse.ok && semanticSearchResponse.data) {
            semanticallyRelatedItems = semanticSearchResponse.data;
            logger.info(`SmartMeetingPrepSkill: Semantic search returned ${semanticallyRelatedItems.length} items.`);
          } else {
            const semSearchErrorMsg = `Semantic search failed: ${semanticSearchResponse.error?.message || 'Unknown error'}`;
            logger.warn(`SmartMeetingPrepSkill: ${semSearchErrorMsg}`);
            dataFetchingErrors.push(semSearchErrorMsg);
          }
        } catch (semSearchCatchError: any) {
            const semSearchErrorMsg = `Semantic search execution error: ${semSearchCatchError.message}`;
            logger.error(`SmartMeetingPrepSkill: ${semSearchErrorMsg}`, semSearchCatchError);
            dataFetchingErrors.push(semSearchErrorMsg);
        }
      } else {
        logger.info("SmartMeetingPrepSkill: Skipping semantic search due to empty query text.");
      }

      // De-duplicate semanticallyRelatedItems against already fetched emails and Notion pages
      const existingItemIds = new Set<string>();
      relatedEmails.forEach(email => existingItemIds.add(email.id));
      relatedNotionPages.forEach(page => existingItemIds.add(page.id));

      const uniqueSemanticallyRelatedItems = semanticallyRelatedItems.filter(item => {
        // For document_chunks, they are always new in this context as we don't fetch full docs otherwise
        if (item.source_type === "document_chunk") return true;
        // For emails and notion summaries, check if their ID is already in our direct-fetched lists
        return !existingItemIds.has(item.id);
      });

      if (semanticallyRelatedItems.length !== uniqueSemanticallyRelatedItems.length) {
        logger.info(`SmartMeetingPrepSkill: De-duplicated semantic search results. Original: ${semanticallyRelatedItems.length}, Unique: ${uniqueSemanticallyRelatedItems.length}`);
      }
      // Use uniqueSemanticallyRelatedItems going forward for output and notes
      // This variable will be added to skill output in the next step.


      // Asynchronously store fetched items in LanceDB - "fire and forget" style for now
      const storagePromises = [];
      if (relatedEmails.length > 0) {
        logger.info(`SmartMeetingPrepSkill: Attempting to store ${relatedEmails.length} email snippets in LanceDB.`);
        for (const email of relatedEmails) {
          storagePromises.push(
            storeEmailSnippetInLanceDb(input.userId, email)
              .then(res => {
                if (!res.ok) logger.warn(`Failed to store email ${email.id} in LanceDB: ${res.error?.message}`);
                // else logger.debug(`Stored email ${email.id} in LanceDB.`);
              })
              .catch(err => logger.error(`Error during storeEmailSnippetInLanceDb for ${email.id}: ${err.message}`))
          );
        }
      }
      if (relatedNotionPages.length > 0) {
        logger.info(`SmartMeetingPrepSkill: Attempting to store ${relatedNotionPages.length} Notion page summaries in LanceDB.`);
        for (const page of relatedNotionPages) {
          storagePromises.push(
            storeNotionPageSummaryInLanceDb(input.userId, page)
              .then(res => {
                if (!res.ok) logger.warn(`Failed to store Notion page ${page.id} in LanceDB: ${res.error?.message}`);
                // else logger.debug(`Stored Notion page ${page.id} in LanceDB.`);
              })
              .catch(err => logger.error(`Error during storeNotionPageSummaryInLanceDb for ${page.id}: ${err.message}`))
          );
        }
      }
      // We don't await Promise.allSettled(storagePromises) here to avoid blocking response to user.
      // These are background tasks. Proper background job queue would be better for production.
      if (storagePromises.length > 0) {
          Promise.allSettled(storagePromises).then(() => {
              logger.info("LanceDB storage attempts completed (background).");
          });
      }


    } else {
      logger.warn(`SmartMeetingPrepSkill: Could not resolve a specific calendar event for "${input.meeting_reference}". No preparation materials will be generated.`);
      preparationNotes = `Could not resolve a specific calendar event for reference: "${input.meeting_reference}". Please try a more specific query or check your calendar.`;
    }

    const output: SmartMeetingPrepSkillOutput = {
      resolvedEvent: resolvedEvent,
      relatedDocuments: relatedDocuments, // Still mock documents
      relatedEmails: relatedEmails,
      relatedNotionPages: relatedNotionPages,
      semanticallyRelatedItems: uniqueSemanticallyRelatedItems, // Added here
      preparationNotes: preparationNotes,
      // Optionally, include dataFetchingErrors in the output if the caller needs them structured
    };

    logger.info("[SmartMeetingPrepSkill.execute] Final output:", JSON.stringify(output, null, 2));
    return output;
  }

  private async _findRelatedDocuments(event: CalendarEventSummary): Promise<any[]> {
    console.log(`[SmartMeetingPrepSkill._findRelatedDocuments] Dynamically finding mock documents for event: "${event.title}" (ID: ${event.id})`);
    const mockDocs: any[] = [];
    const titleLower = event.title.toLowerCase();
    const descriptionLower = event.description?.toLowerCase() || "";

    // Title-based document mocking
    if (titleLower.includes("budget") || descriptionLower.includes("budget")) {
      mockDocs.push({ name: `Budget Overview for ${event.title}.xlsx`, url: `internal://finance/budget-${event.id}.xlsx`, type: "spreadsheet" });
    }
    if (titleLower.includes("phoenix") || descriptionLower.includes("phoenix")) {
      mockDocs.push({ name: `Project Phoenix Status - ${event.id}.pptx`, url: `internal://projects/phoenix/status-${event.id}.pptx`, type: "presentation" });
    }
    if (titleLower.includes("marketing") || titleLower.includes("strategy") || descriptionLower.includes("marketing") || descriptionLower.includes("strategy")) {
      mockDocs.push({ name: `Marketing Strategy Brief - ${event.id}.pdf`, url: `internal://marketing/strategy-${event.id}.pdf`, type: "pdf" });
    }

    // Attendee-based document mocking
    if (event.attendees) {
      for (const attendeeString of event.attendees) {
        // Using a simplified name extraction here, assuming _extractNameFromAttendeeString is in calendarSkills.ts
        // For direct use here, we'd either import it or use a simpler inline version.
        // Let's use a very simple inline version for this mock:
        const namePart = attendeeString.split('<')[0].trim().toLowerCase();
        const simpleName = namePart.split(' ')[0]; // first word of the name part

        if (simpleName === "alice") {
          mockDocs.push({ name: `Alice's Action Items from previous sessions.txt`, url: `internal://users/alice/actions-${event.id}.txt`, type: "text" });
        }
        if (simpleName === "mark") {
          mockDocs.push({ name: `Mark's Proposal Draft for ${event.title}.docx`, url: `internal://users/mark/drafts/prop-${event.id}.docx`, type: "document" });
        }
         if (simpleName === "sarah" && titleLower.includes("1:1")) {
          mockDocs.push({ name: `Performance Review Notes - Sarah Miller.pdf`, url: `internal://hr/reviews/sarahm-${event.id}.pdf`, type: "confidential" });
        }
      }
    }

    // Generic documents
    mockDocs.push({ name: `Minutes from last general meeting on '${event.title}'.pdf`, url: `internal://meetings/minutes/prev-${event.id}.pdf`, type: "minutes" });

    if (mockDocs.length === 0) {
      mockDocs.push({ name: `Standard Agenda Template.docx`, url: "internal://templates/agenda.docx", type: "template" });
    }

    // Deduplicate (simple check based on name)
    const uniqueDocs = Array.from(new Set(mockDocs.map(doc => doc.name)))
        .map(name => mockDocs.find(doc => doc.name === name));

    console.log(`[SmartMeetingPrepSkill._findRelatedDocuments] Found ${uniqueDocs.length} mock documents dynamically.`);
    return uniqueDocs.slice(0, 4); // Cap at 4 documents for brevity
  }

  private async _generatePreparationNotes(
    event: CalendarEventSummary,
    documents: any[], // Mock documents
    emails: GmailMessageSnippet[], // All fetched emails
    notionPages: NotionPageSummary[], // All fetched Notion pages
    errors: string[],
    topEmails: GmailMessageSnippet[], // Top scored emails
    topNotionPages: NotionPageSummary[], // Top scored Notion pages
    eventTitleKeywords: string[], // Keywords from meeting title
    eventDescKeywords: string[],   // Keywords from meeting description
    semanticallyRelatedItems?: UniversalSearchResultItem[] // Added for semantic search results
  ): Promise<string> {
    logger.info(`[SmartMeetingPrepSkill._generatePreparationNotes] Generating notes for event: "${event.title}", with ${emails.length} total emails (${topEmails.length} top), ${notionPages.length} total Notion pages (${topNotionPages.length} top), ${semanticallyRelatedItems?.length || 0} semantic items, and ${errors.length} errors.`);
    const titleLower = event.title.toLowerCase();
    const descriptionLower = event.description?.toLowerCase() || "";

    let notes = `## Meeting Preparation Notes: ${event.title}\n\n`;

    // Add Key Highlights Section
    if (topEmails.length > 0 || topNotionPages.length > 0) {
      notes += "✨ **Key Highlights**\n\n";
      if (topEmails.length > 0) {
        notes += "**Potentially Relevant Emails:**\n";
        topEmails.forEach(email => {
          const emailDate = email.date ? new Date(email.date).toLocaleDateString() : "N/A";
          const combinedKeywords = [...eventTitleKeywords, ...eventDescKeywords];
          const contextualSnippet = this._getContextualSnippet(email.snippet, combinedKeywords);

          notes += `- **Subject:** "${email.subject || '(No Subject)'}" (From: ${email.from || 'N/A'}, Date: ${emailDate})\n`;
          if (contextualSnippet) {
            notes += `  *Contextual Snippet:* ${contextualSnippet}\n`;
          } else if (email.snippet) { // Fallback to original snippet if contextual one is empty
            notes += `  *Snippet:* ${email.snippet.substring(0,150)}...\n`;
          }
          if (email.link) {
            notes += `  *Link:* ${email.link}\n`;
          }
        });
        notes += "\n";
      }
      if (topNotionPages.length > 0) {
        notes += "**Potentially Relevant Notion Pages:**\n";
        topNotionPages.forEach(page => {
          const combinedKeywords = [...eventTitleKeywords, ...eventDescKeywords];
          const contextualPreview = this._getContextualSnippet(page.preview_text, combinedKeywords);

          notes += `- **Title:** "${page.title || 'Untitled Page'}"`;
          if (page.last_edited_time) {
            notes += ` (Last edited: ${new Date(page.last_edited_time).toLocaleDateString()})`;
          }
          notes += "\n";
          if (contextualPreview) {
            notes += `  *Contextual Preview:* ${contextualPreview}\n`;
          } else if (page.preview_text) { // Fallback to original preview
            notes += `  *Preview:* ${page.preview_text.substring(0,150)}...\n`;
          }
          if (page.url) {
            notes += `  *Link:* ${page.url}\n`;
          }
        });
        notes += "\n";
      }
      notes += "---\n\n"; // Separator after highlights
    }


    notes += `**Scheduled:** ${event.startTime.toLocaleString()} - ${event.endTime.toLocaleString()}\n`;
    notes += `**Location:** ${event.location || "Not specified"}\n`;
    notes += `**Organizer:** ${event.organizer || "N/A"}\n`;

    const attendeeList = event.attendees && event.attendees.length > 0
      ? event.attendees.map(a => a.split('<')[0].trim()).join(", ") // Show cleaner names
      : "No attendees listed";
    notes += `**Attendees:** ${attendeeList}\n\n`;

    if (event.description) {
      notes += `**Description/Agenda:**\n${event.description}\n\n`;
    }

    notes += "**Key Discussion Points (Suggested):**\n";
    const discussionPoints: string[] = [];
    if (titleLower.includes("budget") || descriptionLower.includes("budget")) {
      discussionPoints.push("Review budget figures and allocations.");
      const budgetDoc = documents.find(doc => doc.name.toLowerCase().includes("budget"));
      if (budgetDoc) {
        discussionPoints.push(`Analyze data in "${budgetDoc.name}".`);
      }
    }
    if (titleLower.includes("strategy") || titleLower.includes("planning") || descriptionLower.includes("strategy") || descriptionLower.includes("planning")) {
      discussionPoints.push("Define/Review strategic goals and next actions.");
    }
    if (titleLower.includes("phoenix") || descriptionLower.includes("phoenix")) {
      discussionPoints.push("Assess Project Phoenix progress and address blockers.");
    }
    if (titleLower.includes("1:1")) {
        const attendeeName = event.title.replace("1:1 with", "").trim(); // Simple extraction
        discussionPoints.push(`Discuss ${attendeeName}'s progress, goals, and any challenges.`);
    }
     if (discussionPoints.length === 0) {
      discussionPoints.push("Clarify meeting objectives and desired outcomes.");
      discussionPoints.push("Identify key topics based on participant roles.");
    }
    discussionPoints.forEach(point => notes += `- ${point}\n`);
    notes += "\n";

    notes += "**Relevant Materials & Context:**\n";
    if (documents.length > 0) {
      documents.forEach(doc => {
        notes += `- **${doc.name}** (${doc.type}): Review this document for relevant background/data. (Mocked Link: ${doc.url})\n`;
      });
    } else {
      notes += "- No specific documents were automatically linked (mocked). Consider searching manually if needed.\n";
    }
    notes += "\n";

    if (emails.length > 0) {
      notes += "**Recently Exchanged Emails (with attendees, around meeting date):**\n";
      emails.forEach(email => {
        const emailDate = email.date ? new Date(email.date).toLocaleDateString() : "N/A";
        notes += `- **Subject:** "${email.subject || '(No Subject)'}" (From: ${email.from || 'N/A'}, Date: ${emailDate})\n`;
        if (email.snippet) {
          notes += `  *Snippet:* ${email.snippet}...\n`;
        }
        if (email.link) {
            notes += `  *Link:* ${email.link}\n`;
        }
      });
      notes += "\n";
    } else {
        notes += "**Recently Exchanged Emails:**\n- No specific recent emails found with attendees around the meeting time.\n\n";
    }

    if (notionPages.length > 0) {
      notes += "**Related Notion Pages:**\n";
      notionPages.forEach(page => {
        notes += `- **Title:** "${page.title || 'Untitled Page'}"`;
        if (page.last_edited_time) {
          notes += ` (Last edited: ${new Date(page.last_edited_time).toLocaleDateString()})`;
        }
        notes += "\n";
        if (page.preview_text) {
          notes += `  *Preview:* ${page.preview_text}...\n`;
        }
        if (page.url) {
          notes += `  *Link:* ${page.url}\n`;
        }
      });
      notes += "\n";
    } else {
      notes += "**Related Notion Pages:**\n- No Notion pages automatically found related to this meeting's title or description keywords.\n\n";
    }

    // Section for Semantically Related Items
    if (semanticallyRelatedItems && semanticallyRelatedItems.length > 0) {
      notes += "📚 **Additional Context from Knowledge Base (Semantic Search)**\n\n";
      semanticallyRelatedItems.forEach(item => {
        let itemTypeDisplay = "Item";
        if (item.source_type === "document_chunk") itemTypeDisplay = "Document Chunk";
        else if (item.source_type === "email_snippet") itemTypeDisplay = "Email";
        else if (item.source_type === "notion_summary") itemTypeDisplay = "Notion Page";

        notes += `- **Type:** ${itemTypeDisplay}\n`;
        notes += `  - **Title/Subject:** "${item.title || 'N/A'}"\n`;
        if (item.source_type === "document_chunk" && item.parent_document_title && item.parent_document_title !== item.title) {
            notes += `    (From Document: "${item.parent_document_title}")\n`;
        }
        notes += `  - **Snippet:** ${item.snippet || 'N/A'}...\n`;
        if (item.original_url_or_link) {
          notes += `  - **Link:** ${item.original_url_or_link}\n`;
        }
        if (item.last_modified_at) {
          notes += `  - **Last Modified:** ${new Date(item.last_modified_at).toLocaleDateString()}\n`;
        } else if (item.email_date) { // For emails, email_date is more relevant than a generic last_modified
            notes += `  - **Date:** ${new Date(item.email_date).toLocaleDateString()}\n`;
        } else if (item.created_at) {
            notes += `  - **Created:** ${new Date(item.created_at).toLocaleDateString()}\n`;
        }
        // LanceDB distance score (lower is better). We might want to translate this to "relevance" where higher is better.
        // For now, just show the raw score.
        notes += `  - **Relevance Score (raw distance):** ${item.vector_score.toFixed(4)}\n`;
        notes += "\n";
      });
      notes += "---\n\n";
    }


    // Display any data fetching errors
    if (errors.length > 0) {
      notes += "**Data Retrieval Issues Encountered:**\n";
      errors.forEach(err => {
        notes += `- ${err}\n`;
      });
      notes += "\n";
    }

    notes += "**Potential Action Items to Consider from This Meeting (TODO):**\n";
    notes += "- [Assign owners and deadlines for new tasks]\n";
    notes += "- [Schedule follow-up meetings if necessary]\n\n";


    notes += "**Action Items from Previous Related Meetings (TODO):**\n";
    const actionItemDoc = documents.find(doc => doc.name.toLowerCase().includes("action items"));
    const minutesDoc = documents.find(doc => doc.name.toLowerCase().includes("minutes"));
    if (actionItemDoc) {
      notes += `- Review action items from "${actionItemDoc.name}".\n`;
    } else if (minutesDoc) {
      notes += `- Check for open action items in "${minutesDoc.name}".\n`;
    } else {
      notes += "- Check for any outstanding action items from prior relevant meetings.\n";
    }
    notes += "\n";

    // Enhanced Attendee Section - check for specific people and tailor notes
    if (event.attendees) {
        const lowerAttendees = event.attendees.map(a => a.toLowerCase());
        if (lowerAttendees.some(a => a.includes("alice"))) {
            const aliceDoc = documents.find(d => d.name.toLowerCase().includes("alice's action items"));
            if (aliceDoc) {
                notes += `**For Alice:** Please come prepared to discuss items from "${aliceDoc.name}".\n`;
            } else {
                notes += `**For Alice:** Be ready to provide updates on your current tasks.\n`;
            }
        }
         if (lowerAttendees.some(a => a.includes("mark"))) {
            const markDoc = documents.find(d => d.name.toLowerCase().includes("mark's proposal draft"));
            if (markDoc) {
                notes += `**For Mark:** Key discussion point will be your proposal: "${markDoc.name}".\n`;
            }
        }
        notes += "\n";
    }


    notes += "---\nGenerated by SmartMeetingPrepSkill";
    logger.info(`[SmartMeetingPrepSkill._generatePreparationNotes] Notes generated for "${event.title}". Length: ${notes.length}`);
    return notes;
  }
}

// Example of how this skill might be instantiated and used (for testing/demonstration)
// This would typically be done by a skill orchestrator or a higher-level application logic.

async function testSkill() {
  const skill = new SmartMeetingPrepSkill();
  const userId = "user123-test"; // Consistent user ID for tests

  console.log("\\n--- Test Case 1: General reference 'sync up tomorrow' ---");
  let testInput: SmartMeetingPrepSkillInput = {
    userId: userId,
    meeting_reference: "my sync up tomorrow"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (sync up tomorrow):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error executing skill (sync up tomorrow):", error);
  }

  console.log("\\n--- Test Case 2: Specific 'Marketing Strategy' ---");
  testInput = {
    userId: userId,
    meeting_reference: "Marketing Strategy meeting"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (Marketing Strategy):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error executing skill (Marketing Strategy):", error);
  }

  console.log("\\n--- Test Case 3: Reference with specific project name 'Project Phoenix discussion' ---");
  testInput = {
    userId: userId,
    meeting_reference: "Project Phoenix discussion"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (Phoenix discussion):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
     // It should pick "Project Phoenix - Critical Path Discussion" if "discussion" is a keyword and it's sooner or scores higher.
     // Or "Project Phoenix Sync-Up" if that scores higher due to "sync up" vs "discussion"
  } catch (error) {
    console.error("Error executing skill (Phoenix discussion):", error);
  }

  console.log("\\n--- Test Case 4: Vague reference 'my meeting' ---");
  testInput = {
    userId: userId,
    meeting_reference: "my meeting"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (my meeting):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
    // This should likely pick the soonest one if "meeting" is too generic or not a good keyword.
    // Current logic might give low scores to all if "meeting" isn't in titles.
  } catch (error) {
    console.error("Error executing skill (my meeting):", error);
  }

  console.log("\\n--- Test Case 5: Non-existent meeting 'board game night' ---");
  testInput = {
    userId: userId,
    meeting_reference: "board game night"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (board game night):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error executing skill (board game night):", error);
  }

  // To test date_hints, findCalendarEventByFuzzyReference would need to be called directly
  // or SmartMeetingPrepSkillInput would need to support date_hints.
  // For now, direct calls to findCalendarEventByFuzzyReference for date_hint testing:
  console.log("\\n--- Test Case 6: Direct call with specific date hint (past event) ---");
  try {
    const pastDate = new Date();
    pastDate.setDate(pastDate.getDate() - 7); // Targeting "Budget Review Q2"
    pastDate.setHours(12,0,0,0); // Set a specific time on that day to ensure it's within the event's day
    const event = await findCalendarEventByFuzzyReference(userId, "budget review", { specificDate: pastDate });
    console.log("Direct call result (budget review last week):", JSON.stringify(event?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error in direct call (budget review last week):", error);
  }
}

// To run the test:
// You would typically uncomment this in a local environment or run this through a test runner.
// For agent-based execution, we usually don't invoke testSkill() directly here
// unless specifically instructed for a one-off test run.
// testSkill();

import { findCalendarEventByFuzzyReference, CalendarEventSummary, DateHints } from './calendarSkills';
import { searchEmailsForPrep } from '../../atomic-docker/project/functions/atom-agent/skills/gmailSkills';
import {
  GmailSearchParameters,
  GmailMessageSnippet,
  NotionPageSummary,
  UniversalSearchResultItem,
  SearchResultSourceType
} from '../../atomic-docker/project/functions/atom-agent/types';
import { searchNotionNotes, getNotionPageSummaryById } from '../../atomic-docker/project/functions/atom-agent/skills/notionAndResearchSkills';
import { logger } from '../../../atomic-docker/project/functions/_utils/logger';
import { NOTION_NOTES_DATABASE_ID } from '../../../atomic-docker/project/functions/atom-agent/_libs/constants';
import {
  storeEmailSnippetInLanceDb,
  storeNotionPageSummaryInLanceDb,
  semanticSearchLanceDb,
  SemanticSearchFilters
} from './lanceDbStorageSkills';
import { AuthService } from '../services/authService';
// Changed: listGoogleDriveFiles removed, getGoogleDriveFileMetadata imported
import { getGoogleDriveFileMetadata, triggerGoogleDriveFileIngestion, GoogleDriveFile } from './gdriveSkills';

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
  'meeting', 'call', 'sync', 'update', 'discuss', 'review', 'agenda', 'minutes', 'notes', 'event', 'schedule',
  'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
  'am', 'pm', 'morning', 'afternoon', 'evening', 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
]);

export interface SmartMeetingPrepSkillInput {
  userId: string;
  meeting_reference: string;
}

export interface SmartMeetingPrepSkillOutput {
  resolvedEvent?: CalendarEventSummary;
  preparationNotes?: string;
  relatedDocuments?: any[];
  relatedEmails?: GmailMessageSnippet[];
  relatedNotionPages?: NotionPageSummary[];
  semanticallyRelatedItems?: UniversalSearchResultItem[];
  gdriveFilesTriggered?: GoogleDriveFile[];
  dataFetchingErrors?: string[];
}

export class SmartMeetingPrepSkill {
  constructor() {}

  private _extractKeywords(text: string, minLength = 3, maxKeywords = 10): string[] {
    if (!text) return [];
    const words = text.toLowerCase().split(/[^a-z0-9'-]+/);
    const keywords = words.filter(word => {
      if (word.length < minLength) return false;
      if (COMMON_STOP_WORDS.has(word)) return false;
      if (/^\d+$/.test(word)) return false;
      return true;
    });
    if (keywords.length > maxKeywords * 2) {
        const freqMap = new Map<string, number>();
        keywords.forEach(kw => freqMap.set(kw, (freqMap.get(kw) || 0) + 1));
        return Array.from(freqMap.entries()).sort((a, b) => b[1] - a[1]).slice(0, maxKeywords).map(entry => entry[0]);
    }
    return Array.from(new Set(keywords)).slice(0, maxKeywords);
  }

  private _getAttendeeEmails(attendees?: string[]): string[] {
    if (!attendees || attendees.length === 0) return [];
    const emailRegex = /<([^>]+)>/;
    const emails: string[] = [];
    attendees.forEach(attendeeString => {
      const match = attendeeString.match(emailRegex);
      if (match && match[1]) emails.push(match[1].toLowerCase().trim());
      else if (attendeeString.includes('@') && !attendeeString.includes('<') && !attendeeString.includes('>')) {
        const potentialEmail = attendeeString.split(/\s+/).find(part => part.includes('@'));
        if (potentialEmail) emails.push(potentialEmail.toLowerCase().trim());
      }
    });
    return [...new Set(emails)];
  }

  private _scoreEmailRelevance(email: GmailMessageSnippet, titleKeywords: string[], descriptionKeywords: string[], attendeeEmails: string[], meetingStartDate: Date): number {
    let score = 0; const eSub = (email.subject || '').toLowerCase(); const eSnip = (email.snippet || '').toLowerCase(); const eFrom = (email.from || '').toLowerCase();
    titleKeywords.forEach(kw => { if (eSub.includes(kw)) score += 3; if (eSnip.includes(kw)) score += 2; });
    descriptionKeywords.forEach(kw => { if (eSub.includes(kw)) score += 2; if (eSnip.includes(kw)) score += 1; });
    if (attendeeEmails.some(attE => eFrom.includes(attE))) score += 4;
    if (email.date) { try { const eDate = new Date(email.date); const dDiff = (meetingStartDate.getTime() - eDate.getTime()) / (1000*3600*24); if (dDiff >= 0 && dDiff <= 2) score += 3; else if (dDiff > 2 && dDiff <= 7) score += 2; else if (dDiff > 7 && dDiff <= 30) score += 1; } catch (e) { logger.warn(`Could not parse email date for scoring: ${email.date}`); } }
    return score;
  }

  private _scoreNotionPageRelevance(page: NotionPageSummary, titleKeywords: string[], descriptionKeywords: string[], meetingStartDate: Date, isExplicitLink: boolean): number {
    let score = 0; const pTitle = (page.title || '').toLowerCase(); const pPrev = (page.preview_text || '').toLowerCase();
    if (isExplicitLink) score += 10;
    titleKeywords.forEach(kw => { if (pTitle.includes(kw)) score += 3; if (pPrev.includes(kw)) score += 2; });
    descriptionKeywords.forEach(kw => { if (pTitle.includes(kw)) score += 2; if (pPrev.includes(kw)) score += 1; });
    if (page.last_edited_time) { try { const edDate = new Date(page.last_edited_time); const dDiff = (meetingStartDate.getTime() - edDate.getTime()) / (1000*3600*24); if (dDiff >= -7 && dDiff <= 7) score += 3; else if (dDiff > 7 && dDiff <= 30) score += 2; else if (dDiff > 30 && dDiff <= 90) score +=1; } catch (e) { logger.warn(`Could not parse Notion page last_edited_time for scoring: ${page.last_edited_time}`); } }
    return score;
  }

  private _getContextualSnippet(text: string | undefined | null, keywords: string[], maxLength: number = 150, contextWindow: number = 70): string {
    if (!text || text.trim() === "") return ""; const lowerText = text.toLowerCase(); let foundKI: { idx: number, len: number } | null = null;
    for (const kw of keywords) { if (!kw || kw.trim() === "") continue; const kwL = kw.toLowerCase(); const idx = lowerText.indexOf(kwL); if (idx !== -1) { foundKI = { idx, len: kwL.length }; break; } }
    if (foundKI) { const kSIdx = foundKI.idx; const kEIdx = kSIdx + foundKI.len; let start = Math.max(0, kSIdx - contextWindow); let end = Math.min(text.length, kEIdx + contextWindow); let prefix = start > 0 ? "... " : ""; let suffix = end < text.length ? " ..." : ""; let snippet = text.substring(start, end); if ((prefix + snippet + suffix).length > maxLength) { const remLen = maxLength - prefix.length - suffix.length; const kwVisStart = Math.max(0, kSIdx - start); const idealCutStart = Math.max(0, kwVisStart - Math.floor(remLen / 2)); snippet = snippet.substring(idealCutStart, idealCutStart + remLen); } if (snippet.length > maxLength) snippet = snippet.substring(0, maxLength -3) + "..."; return prefix + snippet + suffix; }
    else { if (text.length <= maxLength) return text; return text.substring(0, maxLength - 3) + "..."; }
  }

  public async execute(input: SmartMeetingPrepSkillInput): Promise<SmartMeetingPrepSkillOutput> {
    logger.info(`SmartMeetingPrepSkill: Received request for userId: ${input.userId}, meeting_reference: "${input.meeting_reference}"`);
    const date_hints: DateHints | undefined = undefined;
    const resolvedEvent = await findCalendarEventByFuzzyReference(input.userId, input.meeting_reference, date_hints);

    let preparationNotes: string | undefined = undefined;
    let relatedDocuments: any[] = [];
    let relatedEmails: GmailMessageSnippet[] = [];
    let relatedNotionPages: NotionPageSummary[] = [];
    const dataFetchingErrors: string[] = [];
    let semanticallyRelatedItems: UniversalSearchResultItem[] = [];
    let uniqueSemanticallyRelatedItems: UniversalSearchResultItem[] = [];
    const gdriveFilesTriggered: GoogleDriveFile[] = [];

    if (resolvedEvent) {
      logger.info(`SmartMeetingPrepSkill: Resolved event - Title: ${resolvedEvent.title}, StartTime: ${new Date(resolvedEvent.startTime).toISOString()}`);
      relatedDocuments = await this._findRelatedDocuments(resolvedEvent);

      const gmailSearchParams: GmailSearchParameters = { date_query: "recent" };
      try {
        logger.info(`SmartMeetingPrepSkill: Searching emails for event "${resolvedEvent.title}"`);
        const emailSearchResponse = await searchEmailsForPrep(input.userId, gmailSearchParams, resolvedEvent, 5);
        if (emailSearchResponse.ok && emailSearchResponse.data?.results) {
          relatedEmails = emailSearchResponse.data.results;
          logger.info(`SmartMeetingPrepSkill: Found ${relatedEmails.length} related emails.`);
        } else {
          const errorMsg = `Email search failed: ${emailSearchResponse.error?.message || 'Unknown error'}`;
          logger.warn(`SmartMeetingPrepSkill: ${errorMsg}`); dataFetchingErrors.push(errorMsg);
        }
      } catch (error: any) {
        const errorMsg = `Error calling searchEmailsForPrep: ${error.message}`;
        logger.error(`SmartMeetingPrepSkill: ${errorMsg}`, error); dataFetchingErrors.push(errorMsg);
      }

      const notionPageMap = new Map<string, NotionPageSummary>();
      const explicitNotionLinkPageIds = new Set<string>(); // For scoring
      if (resolvedEvent.description) {
        const notionUrlRegex = /https:\/\/www\.notion\.so\/([\w.-]+?\/)?([\w-]+)(?:\?pvs=[\w-]+)?(?:#[\w-]+)?/g;
        let match;
        while ((match = notionUrlRegex.exec(resolvedEvent.description)) !== null) {
          const potentialId = match[2].split('-').pop();
          if (potentialId && potentialId.length >= 32) { explicitNotionLinkPageIds.add(potentialId.replace(/[^a-f0-9]/gi, '')); }
        }
        if(explicitNotionLinkPageIds.size > 0) logger.info(`SmartMeetingPrepSkill: Found ${explicitNotionLinkPageIds.size} unique Notion page IDs from description.`);
        for (const pageId of explicitNotionLinkPageIds) {
          try {
            const pageSummaryResponse = await getNotionPageSummaryById(input.userId, pageId);
            if (pageSummaryResponse.ok && pageSummaryResponse.data) {
              notionPageMap.set(pageSummaryResponse.data.id, pageSummaryResponse.data);
            } else { dataFetchingErrors.push(`Failed to fetch Notion page ${pageId} from link: ${pageSummaryResponse.error?.message}`); }
          } catch (e: any) { dataFetchingErrors.push(`Error fetching Notion page ${pageId}: ${e.message}`); }
        }
      }

      const titleKeywords = this._extractKeywords(resolvedEvent.title, 3, 5); // Used for Notion keyword search & scoring
      const descriptionKeywords = resolvedEvent.description ? this._extractKeywords(resolvedEvent.description, 3, 7) : []; // Used for Notion keyword search & scoring
      let attendeeKeywords: string[] = [];
      if (resolvedEvent.attendees) {
        const attendeeNames = resolvedEvent.attendees.map(att => att.split('<')[0].trim().split(/\s+/).slice(0,2).join(' ')).join(' ');
        attendeeKeywords = this._extractKeywords(attendeeNames, 3, 5);
      }
      const combinedKeywordsForNotion = new Set([...titleKeywords, ...descriptionKeywords, ...attendeeKeywords]);
      const notionKeywordQueryText = Array.from(combinedKeywordsForNotion).join(' ');
      if (notionKeywordQueryText.trim().length > 0) {
        logger.info(`SmartMeetingPrepSkill: Notion keyword query: "${notionKeywordQueryText}"`);
        try {
          const searchLimit = Math.max(0, 5 - notionPageMap.size);
          if (searchLimit > 0) {
            const notionSearchResponse = await searchNotionNotes(input.userId, notionKeywordQueryText, NOTION_NOTES_DATABASE_ID || undefined, searchLimit);
            logger.info(`SmartMeetingPrepSkill: Notion keyword search using DB ID: ${NOTION_NOTES_DATABASE_ID || 'None (backend default)'}`);
            if (notionSearchResponse.ok && notionSearchResponse.data) {
              notionSearchResponse.data.forEach(page => { if (!notionPageMap.has(page.id)) notionPageMap.set(page.id, page); });
            } else { dataFetchingErrors.push(`Notion keyword search failed: ${notionSearchResponse.error?.message}`); }
          }
        } catch (e: any) { dataFetchingErrors.push(`Error in Notion keyword search: ${e.message}`); }
      }
      relatedNotionPages = Array.from(notionPageMap.values());

      const gDriveFileIdsFromDescription = new Set<string>();
      if (resolvedEvent.description) {
        const gDriveUrlRegex = /https:\/\/(?:drive\.google\.com\/(?:file\/d\/|open\?id=)|docs\.google\.com\/(?:document\/d\/|spreadsheets\/d\/|presentation\/d\/))([\w-]+)/g;
        let gDriveMatch;
        while ((gDriveMatch = gDriveUrlRegex.exec(resolvedEvent.description)) !== null) {
          if (gDriveMatch[1]) gDriveFileIdsFromDescription.add(gDriveMatch[1]);
        }
        if (gDriveFileIdsFromDescription.size > 0) logger.info(`SmartMeetingPrepSkill: Found GDrive file IDs in description: [${Array.from(gDriveFileIdsFromDescription).join(', ')}]`);
      }

      const linkedGDriveFilesMetadata: GoogleDriveFile[] = [];
      if (gDriveFileIdsFromDescription.size > 0 && AuthService && getGoogleDriveFileMetadata) {
        logger.info(`SmartMeetingPrepSkill: Fetching metadata for ${gDriveFileIdsFromDescription.size} GDrive file IDs using getGoogleDriveFileMetadata.`);
        for (const fileId of gDriveFileIdsFromDescription) {
          try {
            const metadataResp = await getGoogleDriveFileMetadata(input.userId, fileId); // Using the new direct metadata fetch skill
            if (metadataResp.ok && metadataResp.data) {
              linkedGDriveFilesMetadata.push(metadataResp.data);
              logger.info(`SmartMeetingPrepSkill: Successfully fetched GDrive metadata for: ${metadataResp.data.name} (ID: ${fileId})`);
            } else {
              const errorMsg = `Failed to get metadata for GDrive file ID ${fileId}: ${metadataResp.error?.message}`;
              logger.warn(`SmartMeetingPrepSkill: ${errorMsg}`); dataFetchingErrors.push(errorMsg);
            }
          } catch (e: any) {
            const errorMsg = `Error calling getGoogleDriveFileMetadata for GDrive file ID ${fileId}: ${e.message}`;
            logger.error(`SmartMeetingPrepSkill: ${errorMsg}`, e); dataFetchingErrors.push(errorMsg);
          }
        }
      }

      if (linkedGDriveFilesMetadata.length > 0 && triggerGoogleDriveFileIngestion) {
          logger.info(`SmartMeetingPrepSkill: Triggering ingestion for ${linkedGDriveFilesMetadata.length} GDrive files.`);
          linkedGDriveFilesMetadata.forEach(file => {
            gdriveFilesTriggered.push(file);
            triggerGoogleDriveFileIngestion(input.userId, file.id,
              { name: file.name, mimeType: file.mimeType, webViewLink: file.webViewLink }
            )
            .then(ingestionRes => {
              if (!ingestionRes.ok) {
                const errMsg = `GDrive ingestion trigger failed for ${file.id} (${file.name}): ${ingestionRes.error?.message}`;
                logger.warn(`SmartMeetingPrepSkill: ${errMsg}`); dataFetchingErrors.push(errMsg);
              } else {
                logger.info(`SmartMeetingPrepSkill: GDrive ingestion successfully triggered for ${file.id} (${file.name}). New Doc ID: ${ingestionRes.data?.doc_id}`);
              }
            })
            .catch(err => {
              const errMsg = `Error calling triggerGoogleDriveFileIngestion for ${file.id} (${file.name}): ${err.message}`;
              logger.error(`SmartMeetingPrepSkill: ${errMsg}`, err); dataFetchingErrors.push(errMsg);
            });
          });
      }

      const meetingStartDate = new Date(resolvedEvent.startTime);
      const eventTitleKeywords = this._extractKeywords(resolvedEvent.title, 2, 5);
      const eventDescKeywords = resolvedEvent.description ? this._extractKeywords(resolvedEvent.description, 3, 5) : [];
      const eventAttendeeEmails = this._getAttendeeEmails(resolvedEvent.attendees);
      const scoredEmails = relatedEmails.map(email => ({ item: email, score: this._scoreEmailRelevance(email, eventTitleKeywords, eventDescKeywords, eventAttendeeEmails, meetingStartDate) })).sort((a, b) => b.score - a.score);
      const scoredNotionPages = relatedNotionPages.map(page => ({ item: page, score: this._scoreNotionPageRelevance(page, eventTitleKeywords, eventDescKeywords, meetingStartDate, explicitNotionLinkPageIds.has(page.id)) })).sort((a, b) => b.score - a.score);
      const topEmails = scoredEmails.slice(0, 3);
      const topNotionPages = scoredNotionPages.slice(0, 2);
      // Logging for top items
      topEmails.forEach((se, idx) => logger.info(`TopEmail[${idx}] (Score: ${se.score.toFixed(1)}): ${se.item.subject?.substring(0,50)}... (From: ${se.item.from})`));
      topNotionPages.forEach((sp, idx) => logger.info(`TopNotion[${idx}] (Score: ${sp.score.toFixed(1)}): ${sp.item.title?.substring(0,50)}... (ExplicitLink: ${explicitNotionLinkPageIds.has(sp.item.id)})`));

      const semanticQueryText = resolvedEvent.title + (eventDescKeywords.length > 0 ? " " + eventDescKeywords.join(" ") : "");
      if (semanticQueryText.trim() && semanticSearchLanceDb) {
        const searchFilters: SemanticSearchFilters = { source_types: ["document_chunk", "email_snippet", "notion_summary"] };
        try {
          const semanticSearchResponse = await semanticSearchLanceDb(input.userId, semanticQueryText, searchFilters, 5);
          if (semanticSearchResponse.ok && semanticSearchResponse.data) semanticallyRelatedItems = semanticSearchResponse.data;
          else dataFetchingErrors.push(`Semantic search failed: ${semanticSearchResponse.error?.message || 'Unknown error'}`);
        } catch (e: any) { dataFetchingErrors.push(`Semantic search execution error: ${e.message}`); }
      }
      const existingItemIds = new Set<string>();
      relatedEmails.forEach(email => existingItemIds.add(email.id));
      relatedNotionPages.forEach(page => existingItemIds.add(page.id));
      uniqueSemanticallyRelatedItems = semanticallyRelatedItems.filter(item => item.source_type === "document_chunk" || !existingItemIds.has(item.id));
      if (semanticallyRelatedItems.length !== uniqueSemanticallyRelatedItems.length) {
        logger.info(`SmartMeetingPrepSkill: De-duplicated semantic results. Original: ${semanticallyRelatedItems.length}, Unique: ${uniqueSemanticallyRelatedItems.length}`);
      }

      preparationNotes = await this._generatePreparationNotes(
        resolvedEvent,
        relatedDocuments,
        relatedEmails,
        relatedNotionPages,
        dataFetchingErrors,
        topEmails.map(e => e.item),
        topNotionPages.map(p => p.item),
        eventTitleKeywords,
        eventDescKeywords,
        gdriveFilesTriggered,
        uniqueSemanticallyRelatedItems
      );
      logger.info(`SmartMeetingPrepSkill: Prep materials generated for "${resolvedEvent.title}".`);

      const storagePromises = [];
      if (relatedEmails.length > 0) { for (const email of relatedEmails) { storagePromises.push(storeEmailSnippetInLanceDb(input.userId, email).catch(err => logger.error(`LanceDB storeEmail error for ${email.id}: ${err.message}`))); } }
      if (relatedNotionPages.length > 0) { for (const page of relatedNotionPages) { storagePromises.push(storeNotionPageSummaryInLanceDb(input.userId, page).catch(err => logger.error(`LanceDB storeNotion error for ${page.id}: ${err.message}`))); } }
      if (storagePromises.length > 0) { Promise.allSettled(storagePromises).then(() => logger.info("LanceDB storage attempts (emails, notion) completed.")); }

    } else {
      logger.warn(`SmartMeetingPrepSkill: Could not resolve event for "${input.meeting_reference}".`);
      preparationNotes = `Could not resolve a specific calendar event for reference: "${input.meeting_reference}". Please try a more specific query.`;
    }

    const output: SmartMeetingPrepSkillOutput = {
      resolvedEvent, relatedDocuments, relatedEmails, relatedNotionPages,
      semanticallyRelatedItems: uniqueSemanticallyRelatedItems,
      gdriveFilesTriggered: gdriveFilesTriggered,
      preparationNotes,
      dataFetchingErrors
    };
    logger.info("[SmartMeetingPrepSkill.execute] Final output generated.");
    return output;
  }

  private async _findRelatedDocuments(event: CalendarEventSummary): Promise<any[]> {
    logger.info(`[SmartMeetingPrepSkill._findRelatedDocuments] Dynamically finding mock documents for event: "${event.title}" (ID: ${event.id})`);
    const mockDocs: any[] = []; const titleLower = event.title.toLowerCase(); const descriptionLower = event.description?.toLowerCase() || "";
    if (titleLower.includes("budget") || descriptionLower.includes("budget")) mockDocs.push({ name: `Budget Overview for ${event.title}.xlsx`, url: `internal://finance/budget-${event.id}.xlsx`, type: "spreadsheet" });
    if (titleLower.includes("phoenix") || descriptionLower.includes("phoenix")) mockDocs.push({ name: `Project Phoenix Status - ${event.id}.pptx`, url: `internal://projects/phoenix/status-${event.id}.pptx`, type: "presentation" });
    if (titleLower.includes("marketing") || titleLower.includes("strategy") || descriptionLower.includes("marketing") || descriptionLower.includes("strategy")) mockDocs.push({ name: `Marketing Strategy Brief - ${event.id}.pdf`, url: `internal://marketing/strategy-${event.id}.pdf`, type: "pdf" });
    if (event.attendees) { for (const attendeeString of event.attendees) { const namePart = attendeeString.split('<')[0].trim().toLowerCase(); const simpleName = namePart.split(' ')[0]; if (simpleName === "alice") mockDocs.push({ name: `Alice's Action Items from previous sessions.txt`, url: `internal://users/alice/actions-${event.id}.txt`, type: "text" }); if (simpleName === "mark") mockDocs.push({ name: `Mark's Proposal Draft for ${event.title}.docx`, url: `internal://users/mark/drafts/prop-${event.id}.docx`, type: "document" }); if (simpleName === "sarah" && titleLower.includes("1:1")) mockDocs.push({ name: `Performance Review Notes - Sarah Miller.pdf`, url: `internal://hr/reviews/sarahm-${event.id}.pdf`, type: "confidential" }); } }
    mockDocs.push({ name: `Minutes from last general meeting on '${event.title}'.pdf`, url: `internal://meetings/minutes/prev-${event.id}.pdf`, type: "minutes" });
    if (mockDocs.length === 0) mockDocs.push({ name: `Standard Agenda Template.docx`, url: "internal://templates/agenda.docx", type: "template" });
    const uniqueDocs = Array.from(new Set(mockDocs.map(doc => doc.name))).map(name => mockDocs.find(doc => doc.name === name));
    logger.info(`[SmartMeetingPrepSkill._findRelatedDocuments] Found ${uniqueDocs.length} mock documents dynamically.`);
    return uniqueDocs!.slice(0, 4);
  }

  private async _generatePreparationNotes(
    event: CalendarEventSummary, documents: any[], emails: GmailMessageSnippet[],
    notionPages: NotionPageSummary[], errors: string[], topEmails: GmailMessageSnippet[],
    topNotionPages: NotionPageSummary[], eventTitleKeywords: string[], eventDescKeywords: string[],
    gdriveFilesTriggered?: GoogleDriveFile[],
    semanticallyRelatedItems?: UniversalSearchResultItem[]
  ): Promise<string> {
    logger.info(`[SmartMeetingPrepSkill._generatePreparationNotes] Generating notes for event: "${event.title}", with ${emails.length} total emails (${topEmails.length} top), ${notionPages.length} total Notion pages (${topNotionPages.length} top), ${gdriveFilesTriggered?.length || 0} GDrive files triggered, ${semanticallyRelatedItems?.length || 0} semantic items, and ${errors.length} errors.`);
    const titleLower = event.title.toLowerCase(); const descriptionLower = event.description?.toLowerCase() || "";
    let notes = `## Meeting Preparation Notes: ${event.title}\n\n`;
    if (topEmails.length > 0 || topNotionPages.length > 0) {
      notes += "✨ **Key Highlights**\n\n";
      if (topEmails.length > 0) {
        notes += "**Potentially Relevant Emails:**\n";
        topEmails.forEach(email => {
          const emailDate = email.date ? new Date(email.date).toLocaleDateString() : "N/A";
          const combinedKeywords = [...eventTitleKeywords, ...eventDescKeywords];
          const contextualSnippet = this._getContextualSnippet(email.snippet, combinedKeywords);
          notes += `- **Subject:** "${email.subject || '(No Subject)'}" (From: ${email.from || 'N/A'}, Date: ${emailDate})\n`;
          if (contextualSnippet) notes += `  *Contextual Snippet:* ${contextualSnippet}\n`;
          else if (email.snippet) notes += `  *Snippet:* ${email.snippet.substring(0,150)}...\n`;
          if (email.link) notes += `  *Link:* ${email.link}\n`;
        });
        notes += "\n";
      }
      if (topNotionPages.length > 0) {
        notes += "**Potentially Relevant Notion Pages:**\n";
        topNotionPages.forEach(page => {
          const combinedKeywords = [...eventTitleKeywords, ...eventDescKeywords];
          const contextualPreview = this._getContextualSnippet(page.preview_text, combinedKeywords);
          notes += `- **Title:** "${page.title || 'Untitled Page'}"`;
          if (page.last_edited_time) notes += ` (Last edited: ${new Date(page.last_edited_time).toLocaleDateString()})`;
          notes += "\n";
          if (contextualPreview) notes += `  *Contextual Preview:* ${contextualPreview}\n`;
          else if (page.preview_text) notes += `  *Preview:* ${page.preview_text.substring(0,150)}...\n`;
          if (page.url) notes += `  *Link:* ${page.url}\n`;
        });
        notes += "\n";
      }
      notes += "---\n\n";
    }
    notes += `**Scheduled:** ${new Date(event.startTime).toLocaleString()} - ${new Date(event.endTime).toLocaleString()}\n`;
    notes += `**Location:** ${event.location || "Not specified"}\n`;
    notes += `**Organizer:** ${event.organizer || "N/A"}\n`;
    const attendeeList = event.attendees && event.attendees.length > 0 ? event.attendees.map(a => a.split('<')[0].trim()).join(", ") : "No attendees listed";
    notes += `**Attendees:** ${attendeeList}\n\n`;
    if (event.description) notes += `**Description/Agenda:**\n${event.description}\n\n`;
    notes += "**Key Discussion Points (Suggested):**\n";
    const discussionPoints: string[] = []; if (titleLower.includes("budget") || descriptionLower.includes("budget")) { discussionPoints.push("Review budget figures and allocations."); const budgetDoc = documents.find(doc => doc.name.toLowerCase().includes("budget")); if (budgetDoc) discussionPoints.push(`Analyze data in "${budgetDoc.name}".`); } if (titleLower.includes("strategy") || titleLower.includes("planning") || descriptionLower.includes("strategy") || descriptionLower.includes("planning")) discussionPoints.push("Define/Review strategic goals and next actions."); if (titleLower.includes("phoenix") || descriptionLower.includes("phoenix")) discussionPoints.push("Assess Project Phoenix progress and address blockers."); if (titleLower.includes("1:1")) { const attendeeName = event.title.replace("1:1 with", "").trim(); discussionPoints.push(`Discuss ${attendeeName}'s progress, goals, and any challenges.`); } if (discussionPoints.length === 0) { discussionPoints.push("Clarify meeting objectives and desired outcomes."); discussionPoints.push("Identify key topics based on participant roles."); } discussionPoints.forEach(point => notes += `- ${point}\n`); notes += "\n";
    notes += "**Relevant Materials & Context:**\n";
    if (documents.length > 0) { documents.forEach(doc => { notes += `- **${doc.name}** (${doc.type}): Review this document for relevant background/data. (Mocked Link: ${doc.url})\n`; }); } else { notes += "- No specific documents were automatically linked (mocked).\n"; }
    notes += "\n";
    if (emails.length > 0) { notes += "**Recently Exchanged Emails (with attendees, around meeting date):**\n"; emails.forEach(email => { const emailDate = email.date ? new Date(email.date).toLocaleDateString() : "N/A"; notes += `- **Subject:** "${email.subject || '(No Subject)'}" (From: ${email.from || 'N/A'}, Date: ${emailDate})\n`; if (email.snippet) notes += `  *Snippet:* ${email.snippet}...\n`; if (email.link) notes += `  *Link:* ${email.link}\n`; }); notes += "\n"; } else { notes += "**Recently Exchanged Emails:**\n- No specific recent emails found.\n\n"; }
    if (notionPages.length > 0) { notes += "**Related Notion Pages:**\n"; notionPages.forEach(page => { notes += `- **Title:** "${page.title || 'Untitled Page'}"`; if (page.last_edited_time) notes += ` (Last edited: ${new Date(page.last_edited_time).toLocaleDateString()})`; notes += "\n"; if (page.preview_text) notes += `  *Preview:* ${page.preview_text}...\n`; if (page.url) notes += `  *Link:* ${page.url}\n`; }); notes += "\n"; } else { notes += "**Related Notion Pages:**\n- No Notion pages found related to keywords.\n\n"; }
    if (gdriveFilesTriggered && gdriveFilesTriggered.length > 0) { notes += "ℹ️ **Google Drive Files Identified for Processing:**\n"; gdriveFilesTriggered.forEach(file => { notes += `- "${file.name}" (Type: ${file.mimeType})\n`; }); notes += "These files are being queued for processing and their content may be available for context in future preparations or searches.\n\n"; }
    if (semanticallyRelatedItems && semanticallyRelatedItems.length > 0) { notes += "📚 **Additional Context from Knowledge Base (Semantic Search)**\n\n"; semanticallyRelatedItems.forEach(item => { let itemTypeDisplay = "Contextual Item"; let titleDisplay = item.title || 'N/A'; if (item.source_type === "document_chunk") { itemTypeDisplay = item.document_doc_type ? `${item.document_doc_type.toUpperCase()} Document Excerpt` : "Document Excerpt"; } else if (item.source_type === "email_snippet") itemTypeDisplay = "Related Email"; else if (item.source_type === "notion_summary") itemTypeDisplay = "Related Notion Page"; notes += `- **Type:** ${itemTypeDisplay}\n`; notes += `  - **Title/Subject:** "${titleDisplay}"\n`; if (item.source_type === "document_chunk" && item.parent_document_title && item.parent_document_title !== item.title) { notes += `    (From Document: "${item.parent_document_title}")\n`; } notes += `  - **Relevant Snippet:** ${item.snippet || 'N/A'}...\n`; const linkToDisplay = item.source_type === "document_chunk" ? item.document_source_uri : item.original_url_or_link; if (linkToDisplay) { notes += `  - **Link:** ${linkToDisplay}\n`; } let itemDate: string | null = null; if (item.last_modified_at) itemDate = new Date(item.last_modified_at).toLocaleDateString(); else if (item.email_date && item.source_type === "email_snippet") itemDate = new Date(item.email_date).toLocaleDateString(); else if (item.created_at) itemDate = new Date(item.created_at).toLocaleDateString(); if (itemDate) notes += `  - **Date:** ${itemDate}\n`; notes += `  - **Relevance Score (raw distance):** ${item.vector_score.toFixed(4)}\n`; notes += "\n"; }); notes += "---\n\n"; }
    if (errors.length > 0) { notes += "**Data Retrieval Issues Encountered:**\n"; errors.forEach(err => { notes += `- ${err}\n`; }); notes += "\n"; }
    notes += "**Potential Action Items to Consider...**\n"; notes += "- [Assign owners and deadlines for new tasks]\n"; notes += "- [Schedule follow-up meetings if necessary]\n\n";
    notes += "**Action Items from Previous Related Meetings...**\n"; const actionItemDoc = documents.find(doc => doc.name.toLowerCase().includes("action items")); const minutesDoc = documents.find(doc => doc.name.toLowerCase().includes("minutes")); if (actionItemDoc) notes += `- Review action items from "${actionItemDoc.name}".\n`; else if (minutesDoc) notes += `- Check for open action items in "${minutesDoc.name}".\n`; else notes += "- Check for any outstanding action items from prior relevant meetings.\n"; notes += "\n";
    if (event.attendees) { const lowerAttendees = event.attendees.map(a => a.toLowerCase()); if (lowerAttendees.some(a => a.includes("alice"))) { const aliceDoc = documents.find(d => d.name.toLowerCase().includes("alice's action items")); if (aliceDoc) notes += `**For Alice:** Please come prepared to discuss items from "${aliceDoc.name}".\n`; else notes += `**For Alice:** Be ready to provide updates on your current tasks.\n`; } if (lowerAttendees.some(a => a.includes("mark"))) { const markDoc = documents.find(d => d.name.toLowerCase().includes("mark's proposal draft")); if (markDoc) notes += `**For Mark:** Key discussion point will be your proposal: "${markDoc.name}".\n`; } notes += "\n"; }
    notes += "---\nGenerated by SmartMeetingPrepSkill";
    logger.info(`[SmartMeetingPrepSkill._generatePreparationNotes] Notes generated for "${event.title}". Length: ${notes.length}`);
    return notes;
  }
}
```

import { findCalendarEventByFuzzyReference, CalendarEventSummary, DateHints } from './calendarSkills';
import { searchEmailsForPrep } from '../../atomic-docker/project/functions/atom-agent/skills/gmailSkills';
import {
  GmailSearchParameters,
  GmailMessageSnippet,
  NotionPageSummary,
  UniversalSearchResultItem, // Though not used in notes YET, it's part of output
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
import { listGoogleDriveFiles, triggerGoogleDriveFileIngestion, GoogleDriveFile } from './gdriveSkills';

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
  gdriveFilesTriggered?: GoogleDriveFile[]; // Renamed from gdriveFilesForIngestionTrigger for notes param
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
      const explicitNotionLinkPageIds = new Set<string>();
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

      const titleKeywords = this._extractKeywords(resolvedEvent.title, 3, 5);
      const descriptionKeywords = resolvedEvent.description ? this._extractKeywords(resolvedEvent.description, 3, 7) : [];
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
      if (gDriveFileIdsFromDescription.size > 0 && AuthService && listGoogleDriveFiles) {
        const gdriveAccessToken = await AuthService.getGoogleDriveAccessToken(input.userId);
        if (gdriveAccessToken) {
          logger.info(`SmartMeetingPrepSkill: Fetching metadata for ${gDriveFileIdsFromDescription.size} GDrive IDs.`);
          for (const fileId of gDriveFileIdsFromDescription) {
            try {
              const listResp = await listGoogleDriveFiles(input.userId, gdriveAccessToken, undefined, `'${fileId}' in ids`, 1);
              if (listResp.ok && listResp.data && listResp.data.files.length > 0) {
                const foundFile = listResp.data.files.find(f => f.id === fileId);
                if (foundFile) { linkedGDriveFilesMetadata.push(foundFile); logger.info(`SmartMeetingPrepSkill: Fetched GDrive metadata for: ${foundFile.name}`);}
                else { logger.warn(`GDrive file ID ${fileId} not precisely found via list query.`);}
              } else if (!listResp.ok) { dataFetchingErrors.push(`Failed to get GDrive metadata for ${fileId}: ${listResp.error?.message}`);}
            } catch (e: any) { dataFetchingErrors.push(`Error fetching GDrive metadata for ${fileId}: ${e.message}`); }
          }
        } else { dataFetchingErrors.push("Could not get GDrive access token for metadata fetch."); }
      }

      if (linkedGDriveFilesMetadata.length > 0 && AuthService && triggerGoogleDriveFileIngestion) {
        const gdriveAccessTokenForIngestion = await AuthService.getGoogleDriveAccessToken(input.userId);
        if (gdriveAccessTokenForIngestion) {
          logger.info(`SmartMeetingPrepSkill: Triggering ingestion for ${linkedGDriveFilesMetadata.length} GDrive files.`);
          linkedGDriveFilesMetadata.forEach(file => {
            gdriveFilesTriggered.push(file);
            triggerGoogleDriveFileIngestion(input.userId, gdriveAccessTokenForIngestion, file.id,
              { name: file.name, mimeType: file.mimeType, webViewLink: file.webViewLink }
            ).then(res => { if (!res.ok) dataFetchingErrors.push(`GDrive ingestion trigger failed for ${file.name}: ${res.error?.message}`); else logger.info(`GDrive ingestion triggered for ${file.name}`);})
             .catch(err => dataFetchingErrors.push(`Error calling GDrive ingestion for ${file.name}: ${err.message}`));
          });
        } else { dataFetchingErrors.push("Could not get GDrive access token for ingestion trigger.");}
      }

      const meetingStartDate = new Date(resolvedEvent.startTime);
      const eventTitleKeywords = this._extractKeywords(resolvedEvent.title, 2, 5);
      const eventDescKeywords = resolvedEvent.description ? this._extractKeywords(resolvedEvent.description, 3, 5) : [];
      const eventAttendeeEmails = this._getAttendeeEmails(resolvedEvent.attendees);
      const scoredEmails = relatedEmails.map(email => ({ item: email, score: this._scoreEmailRelevance(email, eventTitleKeywords, eventDescKeywords, eventAttendeeEmails, meetingStartDate) })).sort((a, b) => b.score - a.score);
      const scoredNotionPages = relatedNotionPages.map(page => ({ item: page, score: this._scoreNotionPageRelevance(page, eventTitleKeywords, eventDescKeywords, meetingStartDate, explicitNotionLinkPageIds.has(page.id)) })).sort((a, b) => b.score - a.score);
      const topEmails = scoredEmails.slice(0, 3);
      const topNotionPages = scoredNotionPages.slice(0, 2);

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

      preparationNotes = await this._generatePreparationNotes(resolvedEvent, relatedDocuments, relatedEmails, relatedNotionPages, dataFetchingErrors, topEmails.map(e => e.item), topNotionPages.map(p => p.item), eventTitleKeywords, eventDescKeywords, gdriveFilesTriggered);
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
    return uniqueDocs!.slice(0, 4); // uniqueDocs will have items if mockDocs has items
  }

  private async _generatePreparationNotes(
    event: CalendarEventSummary, documents: any[], emails: GmailMessageSnippet[],
    notionPages: NotionPageSummary[], errors: string[], topEmails: GmailMessageSnippet[],
    topNotionPages: NotionPageSummary[], eventTitleKeywords: string[], eventDescKeywords: string[],
    gdriveFilesTriggered?: GoogleDriveFile[] // Added for GDrive info
  ): Promise<string> {
    logger.info(`[SmartMeetingPrepSkill._generatePreparationNotes] Generating notes for event: "${event.title}", with ${emails.length} total emails (${topEmails.length} top), ${notionPages.length} total Notion pages (${topNotionPages.length} top), ${gdriveFilesTriggered?.length || 0} GDrive files triggered, and ${errors.length} errors.`);
    const titleLower = event.title.toLowerCase(); const descriptionLower = event.description?.toLowerCase() || "";
    let notes = `## Meeting Preparation Notes: ${event.title}\n\n`;
    // Key Highlights Section (Emails & Notion)
    if (topEmails.length > 0 || topNotionPages.length > 0) {
      notes += "✨ **Key Highlights**\n\n";
      if (topEmails.length > 0) { /* ... email highlights rendering ... */ }
      if (topNotionPages.length > 0) { /* ... Notion highlights rendering ... */ }
      notes += "---\n\n";
    }
    // Meeting Details
    notes += `**Scheduled:** ${new Date(event.startTime).toLocaleString()} - ${new Date(event.endTime).toLocaleString()}\n`;
    notes += `**Location:** ${event.location || "Not specified"}\n`;
    notes += `**Organizer:** ${event.organizer || "N/A"}\n`;
    const attendeeList = event.attendees && event.attendees.length > 0 ? event.attendees.map(a => a.split('<')[0].trim()).join(", ") : "No attendees listed";
    notes += `**Attendees:** ${attendeeList}\n\n`;
    if (event.description) notes += `**Description/Agenda:**\n${event.description}\n\n`;
    // Suggested Discussion Points (Mocked)
    notes += "**Key Discussion Points (Suggested):**\n"; /* ... */ notes += "\n";
    // Relevant Materials & Context (Full Lists)
    notes += "**Relevant Materials & Context:**\n";
    if (documents.length > 0) { /* ... mock documents rendering ... */ } else { notes += "- No specific documents were automatically linked (mocked).\n"; }
    notes += "\n";
    if (emails.length > 0) { /* ... all emails rendering ... */ } else { notes += "**Recently Exchanged Emails:**\n- No specific recent emails found.\n\n"; }
    if (notionPages.length > 0) { /* ... all Notion pages rendering ... */ } else { notes += "**Related Notion Pages:**\n- No Notion pages found related to keywords.\n\n"; }

    // GDrive Ingestion Info
    if (gdriveFilesTriggered && gdriveFilesTriggered.length > 0) {
      notes += "ℹ️ **Google Drive Files Identified for Processing:**\n";
      gdriveFilesTriggered.forEach(file => {
        notes += `- "${file.name}" (Type: ${file.mimeType})\n`;
      });
      notes += "These files are being queued for processing and their content may be available for context in future preparations or searches.\n\n";
    }

    // Semantically Related Items section (placeholder for now, will be implemented in a later step)
    // if (semanticallyRelatedItems && semanticallyRelatedItems.length > 0) { ... }

    if (errors.length > 0) { /* ... errors rendering ... */ }
    // Action Items (Mocked)
    notes += "**Potential Action Items to Consider...**\n"; /* ... */ notes += "\n";
    notes += "**Action Items from Previous Related Meetings...**\n"; /* ... */ notes += "\n";
    if (event.attendees) { /* ... attendee specific mock notes ... */ }
    notes += "---\nGenerated by SmartMeetingPrepSkill";
    logger.info(`[SmartMeetingPrepSkill._generatePreparationNotes] Notes generated for "${event.title}". Length: ${notes.length}`);
    return notes;
  }
}
```

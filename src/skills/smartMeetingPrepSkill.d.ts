import { CalendarEventSummary } from './calendarSkills';
import { GmailMessageSnippet, NotionPageSummary } from '../../atomic-docker/project/functions/atom-agent/types';
import { // Import the new hybrid search function
HybridSearchResultItem } from './lanceDbStorageSkills';
import { GoogleDriveFile } from './gdriveSkills';
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
    hybridSearchResults?: HybridSearchResultItem[];
    gdriveFilesTriggered?: GoogleDriveFile[];
    dataFetchingErrors?: string[];
}
export declare class SmartMeetingPrepSkill {
    constructor();
    private _extractKeywords;
    private _getAttendeeEmails;
    private _scoreEmailRelevance;
    private _scoreNotionPageRelevance;
    private _getContextualSnippet;
    execute(input: SmartMeetingPrepSkillInput): Promise<SmartMeetingPrepSkillOutput>;
    private _findRelatedDocuments;
    private _generatePreparationNotes;
}

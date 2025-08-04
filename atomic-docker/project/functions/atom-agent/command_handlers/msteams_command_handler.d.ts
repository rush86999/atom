export type MSTeamsActionType = 'GET_MSTEAMS_MESSAGE_CONTENT' | 'FIND_INFO_IN_MSTEAMS_MESSAGE' | 'GET_MSTEAMS_MESSAGE_LINK' | 'SUMMARIZE_MSTEAMS_MESSAGE';
export interface MSTeamsActionRequest {
    actionType: MSTeamsActionType;
    infoKeywords?: string[];
    naturalLanguageQuestion?: string;
}
export interface ParsedNluMSTeamsRequest {
    userId: string;
    rawMSTeamsSearchQuery: string;
    actionRequested: MSTeamsActionRequest;
    targetMessageId?: string;
    targetChatId?: string;
    targetTeamId?: string;
    targetChannelId?: string;
}
export declare function handleMSTeamsInquiry(request: ParsedNluMSTeamsRequest): Promise<string>;

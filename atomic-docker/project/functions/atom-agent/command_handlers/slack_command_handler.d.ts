export type SlackActionType = 'GET_SLACK_MESSAGE_CONTENT' | 'FIND_INFO_IN_SLACK_MESSAGE' | 'GET_SLACK_MESSAGE_LINK' | 'SUMMARIZE_SLACK_MESSAGE';
export interface SlackActionRequest {
    actionType: SlackActionType;
    infoKeywords?: string[];
    naturalLanguageQuestion?: string;
}
export interface ParsedNluSlackRequest {
    userId: string;
    rawSlackSearchQuery: string;
    actionRequested: SlackActionRequest;
    targetChannelId?: string;
    targetMessageTs?: string;
}
/**
 * Handles a generic Slack inquiry: understands the search query using an LLM,
 * finds a message, and performs an action on it (e.g., extracts info, gets content, gets link).
 */
export declare function handleSlackInquiry(request: ParsedNluSlackRequest): Promise<string>;

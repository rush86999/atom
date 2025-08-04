import { AccountInfo } from '@azure/msal-node';
import { MSGraphEvent, GraphSkillResponse, ListMSGraphEventsData } from '../atom-agent/types';
export interface MSGraphUserTokenDetails {
    accessToken: string;
    userAadObjectId: string | null;
    userPrincipalName: string | null;
    accountInfo?: AccountInfo;
}
export declare function getDelegatedMSGraphTokenForUser(userId: string): Promise<GraphSkillResponse<MSGraphUserTokenDetails>>;
export declare function generateTeamsAuthUrl(userIdForContext: string, state?: string): Promise<string | null>;
export declare function handleTeamsAuthCallback(userId: string, authorizationCode: string): Promise<GraphSkillResponse<boolean>>;
export declare function listMicrosoftTeamsMeetings(atomUserId: string, // Changed from userPrincipalNameOrId to Atom's internal userId
options?: {
    limit?: number;
    nextLink?: string;
    filterForTeamsMeetings?: boolean;
}): Promise<GraphSkillResponse<ListMSGraphEventsData>>;
export declare function getMicrosoftTeamsMeetingDetails(atomUserId: string, // Changed from userPrincipalNameOrId to Atom's internal userId
eventId: string): Promise<GraphSkillResponse<MSGraphEvent>>;
/**
 * Defines the structure for a Teams message object within the agent.
 * This should align with what the agent needs and what Graph API provides.
 */
export interface AgentMSTeamsMessage {
    id: string;
    chatId?: string;
    channelId?: string;
    teamId?: string;
    replyToId?: string;
    userId?: string;
    userName?: string;
    content: string;
    contentType: 'html' | 'text';
    createdDateTime: string;
    lastModifiedDateTime?: string;
    webUrl?: string;
    attachments?: {
        id: string;
        name?: string;
        contentType?: string;
        contentUrl?: string;
        size?: number;
    }[];
    mentions?: {
        id: number;
        mentionText?: string;
        mentioned?: {
            user?: {
                id: string;
                displayName?: string;
                userIdentityType?: string;
            };
        };
    }[];
    raw?: any;
}
/**
 * Searches Microsoft Teams messages using the Graph Search API.
 * @param atomUserId Atom's internal user ID.
 * @param searchQuery KQL query string.
 * @param maxResults Maximum number of messages to return.
 * @returns A promise resolving to an array of AgentMSTeamsMessage objects.
 */
export declare function searchTeamsMessages(atomUserId: string, searchQuery: string, // This will be the KQL query string
maxResults?: number, userAadObjectId?: string): Promise<GraphSkillResponse<AgentMSTeamsMessage[]>>;
/**
 * Gets the content of a specific chat message (1:1 or group chat).
 * @param atomUserId Atom's internal user ID.
 * @param chatId The ID of the chat.
 * @param messageId The ID of the message.
 * @returns A promise resolving to an AgentMSTeamsMessage object or null.
 */
export declare function getTeamsChatMessageContent(atomUserId: string, chatId: string, messageId: string): Promise<GraphSkillResponse<AgentMSTeamsMessage | null>>;
/**
 * Gets the content of a specific channel message.
 * @param atomUserId Atom's internal user ID.
 * @param teamId The ID of the team.
 * @param channelId The ID of the channel.
 * @param messageId The ID of the message.
 * @returns A promise resolving to an AgentMSTeamsMessage object or null.
 */
export declare function getTeamsChannelMessageContent(atomUserId: string, teamId: string, channelId: string, messageId: string): Promise<GraphSkillResponse<AgentMSTeamsMessage | null>>;

import { HubSpotContactProperties, HubSpotContact, HubSpotSkillResponse, CreateHubSpotContactResponse, HubSpotEmailEngagementProperties, LogEngagementResponse, GetContactActivitiesResponse } from '../types';
export declare function getHubSpotContactByEmail(userId: string, email: string): Promise<HubSpotSkillResponse<HubSpotContact | null>>;
export declare function createHubSpotContact(userId: string, contactProperties: HubSpotContactProperties): Promise<HubSpotSkillResponse<CreateHubSpotContactResponse>>;
export declare function logEmailToHubSpotContact(userId: string, contactId: string, emailDetails: HubSpotEmailEngagementProperties): Promise<HubSpotSkillResponse<LogEngagementResponse>>;
export declare function getHubSpotContactActivities(userId: string, contactId: string, filters?: {
    activityTypes?: ('EMAIL' | 'MEETING')[];
    limit?: number;
    after?: string;
    since?: string;
    sort?: 'ASC' | 'DESC';
}): Promise<HubSpotSkillResponse<GetContactActivitiesResponse>>;

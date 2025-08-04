import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createMailchimpCampaignFromSalesforceCampaign(userId: string, salesforceCampaignId: string): Promise<SkillResponse<any>>;
export declare function getMailchimpCampaignSummary(userId: string, campaignId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromMailchimpCampaign(userId: string, campaignId: string, trelloListId: string): Promise<SkillResponse<any>>;

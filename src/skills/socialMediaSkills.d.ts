import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function scheduleTweet(userId: string, status: string, sendAt: string): Promise<SkillResponse<any>>;
export declare function monitorTwitterMentions(userId: string, trelloListId: string): Promise<SkillResponse<any>>;
export declare function createSalesforceLeadFromTweet(userId: string, tweetId: string): Promise<SkillResponse<any>>;

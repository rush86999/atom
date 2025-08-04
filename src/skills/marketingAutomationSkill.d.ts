import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
import { SubAgentInput, AgentLLMService } from '../nlu_agents/nlu_types';
export declare function createDripCampaign(userId: string, campaignName: string, targetAudience: string, emailSequence: string[]): Promise<SkillResponse<any>>;
export declare function getCampaignStatus(userId: string, campaignId: string): Promise<SkillResponse<any>>;
export declare class MarketingAutomationAgent {
    private llmService;
    constructor(llmService: AgentLLMService);
    analyze(input: SubAgentInput): Promise<any>;
}

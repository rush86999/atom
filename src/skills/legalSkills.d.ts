import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createDocusignEnvelopeFromSalesforceOpportunity(userId: string, salesforceOpportunityId: string): Promise<SkillResponse<any>>;
export declare function getDocusignEnvelopeStatus(userId: string, envelopeId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromDocusignEnvelope(userId: string, envelopeId: string, trelloListId: string): Promise<SkillResponse<any>>;

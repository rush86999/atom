import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function getFinancialSummary(userId: string): Promise<SkillResponse<any>>;
export declare function createSalesforceOpportunityFromXeroInvoice(userId: string, invoiceId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromXeroInvoice(userId: string, invoiceId: string, trelloListId: string): Promise<SkillResponse<any>>;

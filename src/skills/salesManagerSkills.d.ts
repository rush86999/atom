import { SkillResponse, XeroInvoice, SalesforceOpportunity, TrelloCard } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createXeroInvoiceFromSalesforceOpportunity(userId: string, opportunityId: string): Promise<SkillResponse<XeroInvoice>>;
export declare function createTrelloCardFromSalesforceOpportunity(userId: string, opportunityId: string, trelloListId: string): Promise<SkillResponse<TrelloCard>>;
export declare function createSalesforceContactFromXeroContact(userId: string, xeroContactId: string): Promise<SkillResponse<any>>;
export declare function getOpenOpportunitiesForAccount(userId: string, accountId: string): Promise<SkillResponse<SalesforceOpportunity[]>>;

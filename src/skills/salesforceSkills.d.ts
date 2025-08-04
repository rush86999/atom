import { SkillResponse, SalesforceContact, SalesforceAccount, SalesforceOpportunity } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function listSalesforceContacts(userId: string): Promise<SkillResponse<{
    contacts: SalesforceContact[];
}>>;
export declare function listSalesforceAccounts(userId: string): Promise<SkillResponse<{
    accounts: SalesforceAccount[];
}>>;
export declare function listSalesforceOpportunities(userId: string): Promise<SkillResponse<{
    opportunities: SalesforceOpportunity[];
}>>;
export declare function createSalesforceContact(userId: string, lastName: string, firstName?: string, email?: string): Promise<SkillResponse<SalesforceContact>>;
export declare function createSalesforceAccount(userId: string, name: string): Promise<SkillResponse<SalesforceAccount>>;
export declare function createSalesforceOpportunity(userId: string, name: string, stageName: string, closeDate: string, amount?: number): Promise<SkillResponse<SalesforceOpportunity>>;
export declare function updateSalesforceOpportunity(userId: string, opportunityId: string, fields: Partial<SalesforceOpportunity>): Promise<SkillResponse<SalesforceOpportunity>>;
export declare function getSalesforceOpportunity(userId: string, opportunityId: string): Promise<SkillResponse<SalesforceOpportunity>>;

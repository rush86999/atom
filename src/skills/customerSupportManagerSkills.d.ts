import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createZendeskTicketFromSalesforceCase(userId: string, salesforceCaseId: string): Promise<SkillResponse<any>>;
export declare function getZendeskTicketSummary(userId: string, ticketId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromZendeskTicket(userId: string, ticketId: string, trelloListId: string): Promise<SkillResponse<any>>;

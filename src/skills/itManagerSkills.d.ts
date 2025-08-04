import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createJiraIssueFromSalesforceCase(userId: string, salesforceCaseId: string): Promise<SkillResponse<any>>;
export declare function getJiraIssueSummary(userId: string, issueId: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromJiraIssue(userId: string, issueId: string, trelloListId: string): Promise<SkillResponse<any>>;

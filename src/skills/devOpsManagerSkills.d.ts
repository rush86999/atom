import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function createGithubIssueFromJiraIssue(userId: string, jiraIssueId: string): Promise<SkillResponse<any>>;
export declare function getGithubPullRequestStatus(userId: string, pullRequestUrl: string): Promise<SkillResponse<any>>;
export declare function createTrelloCardFromGithubIssue(userId: string, issueUrl: string, trelloListId: string): Promise<SkillResponse<any>>;

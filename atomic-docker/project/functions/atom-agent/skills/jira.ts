import { SkillResponse } from '../../types';
import { JIRA_SERVER, JIRA_USERNAME, JIRA_PASSWORD } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';
import { JiraApi } from 'jira-client';

const jira = new JiraApi({
  protocol: 'https',
  host: JIRA_SERVER,
  username: JIRA_USERNAME,
  password: JIRA_PASSWORD,
  apiVersion: '2',
  strictSSL: true
});

export async function handleCreateJiraIssue(userId: string, entities: any): Promise<string> {
    try {
        const { summary, project_key, issue_type } = entities;

        if (!summary || typeof summary !== 'string') {
            return "Summary is required to create a Jira issue.";
        }

        if (!project_key || typeof project_key !== 'string') {
            return "Project key is required to create a Jira issue.";
        }

        if (!issue_type || typeof issue_type !== 'string') {
            return "Issue type is required to create a Jira issue.";
        }

        const issue = await jira.addNewIssue({
            fields: {
                project: {
                    key: project_key
                },
                summary: summary,
                issuetype: {
                    name: issue_type
                }
            }
        });

        return `Jira issue created: ${issue.key}`;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't create the Jira issue due to an error.");
    }
}

export async function handleQueryJiraIssues(userId: string, entities: any): Promise<string> {
    try {
        const { project_key } = entities;

        if (!project_key || typeof project_key !== 'string') {
            return "Project key is required to query Jira issues.";
        }

        const issues = await jira.searchJira(`project = ${project_key}`);

        if (!issues.issues.length) {
            return "No issues found in the specified Jira project.";
        }

        let issueList = "Here are the issues in the specified Jira project:\n";
        for (const issue of issues.issues) {
            issueList += `- ${issue.key}: ${issue.fields.summary}\n`;
        }

        return issueList;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't query the Jira issues due to an error.");
    }
}

export async function handleUpdateJiraIssue(userId: string, entities: any): Promise<string> {
    try {
        const { issue_key, summary } = entities;

        if (!issue_key || typeof issue_key !== 'string') {
            return "Issue key is required to update a Jira issue.";
        }

        if (!summary || typeof summary !== 'string') {
            return "Summary is required to update a Jira issue.";
        }

        await jira.updateIssue(issue_key, {
            fields: {
                summary: summary,
            }
        });

        return `Jira issue updated: ${issue_key}`;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't update the Jira issue due to an error.");
    }
}

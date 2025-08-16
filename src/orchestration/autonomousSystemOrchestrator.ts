import { handleCreateJiraIssue, getJiraCredentials } from 'atomic-docker/project/functions/atom-agent/skills/jira';
import { createGithubRepo, createGithubIssue } from 'atomic-docker/project/functions/atom-agent/skills/githubSkills';
import { sendSlackMessage } from 'atomic-docker/project/functions/atom-agent/skills/slackSkills';
import { runShellCommand } from '../skills/shellSkills';
import { runShopifyBusinessManager } from './shopifyBusinessManager';

interface AutonomousSystemResult {
    success: boolean;
    message: string;
    errors: string[];
}

export async function runAutonomousSystem(
    userId: string,
    owner: string,
    repo: string,
    jiraProjectKey: string,
    slackChannelId: string
): Promise<AutonomousSystemResult> {
    console.log(`[AutonomousSystemOrchestrator] Starting autonomous system for user ${userId}.`);

    const result: AutonomousSystemResult = {
        success: false,
        message: '',
        errors: [],
    };

    // 1. Create GitHub repository
    const repoResponse = await createGithubRepo(userId, owner, repo);

    if (!repoResponse.ok || !repoResponse.data) {
        const errorMsg = `Failed to create GitHub repository: ${repoResponse.error?.message}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }

    // 2. Create web app from template
    const appResponse = await runShellCommand(
        `npx create-react-app ${repo} --template file:../templates/create-react-app`
    );

    if (appResponse.exitCode !== 0) {
        const errorMsg = `Failed to create web app from template: ${appResponse.stderr}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }

    // 3. Get Jira credentials
    const jiraCredentials = await getJiraCredentials(userId);
    if (!jiraCredentials) {
        const errorMsg = 'Jira credentials not configured for this user.';
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }

    // 4. Create Jira issue
    const jiraEntities = {
        summary: `New web app created: ${repo}`,
        project_key: jiraProjectKey,
        issue_type: 'Task',
    };
    const jiraResponse = await handleCreateJiraIssue(userId, jiraEntities);

    if (!jiraResponse.startsWith('Jira issue created:')) {
        console.error(`[AutonomousSystemOrchestrator] Failed to create Jira issue: ${jiraResponse}`);
        result.message = `Failed to create Jira issue: ${jiraResponse}`;
        result.errors.push(jiraResponse);
        return result;
    }

    const jiraIssueKey = jiraResponse.replace('Jira issue created: ', '');

    // 5. Create GitHub issue
    const issueResponse = await createGithubIssue(
        userId,
        owner,
        repo,
        `New web app created: ${repo}`,
        `Jira issue: ${jiraIssueKey}`
    );

    if (!issueResponse.ok || !issueResponse.data) {
        const errorMsg = `Failed to create GitHub issue: ${issueResponse.error?.message}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }

    // 6. Send Slack message
    const slackMessage = `New web app created: ${repo}. Jira issue <https://${jiraCredentials.serverUrl}/browse/${jiraIssueKey}|${jiraIssueKey}> created.`;
    await sendSlackMessage(userId, slackChannelId, slackMessage);

    result.success = true;
    result.message = `Successfully created web app ${repo}.`;

    console.log(`[AutonomousSystemOrchestrator] ${result.message}`);
    return result;
}

export async function runShopifyReport(
    userId: string,
    slackChannelId: string
): Promise<AutonomousSystemResult> {
    console.log(`[AutonomousSystemOrchestrator] Starting Shopify report for user ${userId}.`);

    const result = await runShopifyBusinessManager(userId, slackChannelId);

    return {
        success: result.success,
        message: result.message,
        errors: result.errors,
    };
}

import { handleCreateJiraIssue, getJiraCredentials } from 'atomic-docker/project/functions/atom-agent/skills/jira';
import { createGithubRepo, createGithubIssue } from 'atomic-docker/project/functions/atom-agent/skills/githubSkills';
import { sendSlackMessage } from 'atomic-docker/project/functions/atom-agent/skills/slackSkills';
import { runShellCommand } from '../skills/shellSkills';
import { runShopifyBusinessManager } from './shopifyBusinessManager';
import { postTweet } from './socialMediaOrchestrator';

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
    slackChannelId: string,
    dependencies?: string[]
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

    // 3. Install dependencies
    if (dependencies && dependencies.length > 0) {
        console.log(`[AutonomousSystemOrchestrator] Installing dependencies: ${dependencies.join(' ')}`);
        const installResponse = await runShellCommand(
            `cd ${repo} && npm install ${dependencies.join(' ')}`
        );

        if (installResponse.exitCode !== 0) {
            const errorMsg = `Failed to install dependencies: ${installResponse.stderr}`;
            console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
            result.message = errorMsg;
            return result;
        }
    }

    // 4. Get Jira credentials
    const jiraCredentials = await getJiraCredentials(userId);
    if (!jiraCredentials) {
        const errorMsg = 'Jira credentials not configured for this user.';
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }

    // 5. Create Jira issue
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

    // 6. Create GitHub issue
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

    // 7. Send Slack message
    let slackMessage = `New web app created: ${repo}. Jira issue <https://${jiraCredentials.serverUrl}/browse/${jiraIssueKey}|${jiraIssueKey}> created.`;
    if (dependencies && dependencies.length > 0) {
        slackMessage += ` Installed dependencies: ${dependencies.join(', ')}.`;
    }
    await sendSlackMessage(userId, slackChannelId, slackMessage);

    result.success = true;
    result.message = `Successfully created web app ${repo}.`;
    if (dependencies && dependencies.length > 0) {
        result.message += ` Installed dependencies: ${dependencies.join(', ')}.`;
    }

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

export async function runSocialMediaAutoPost(
    userId: string,
    text: string
): Promise<AutonomousSystemResult> {
    console.log(`[AutonomousSystemOrchestrator] Starting social media auto post for user ${userId}.`);

    const result = await postTweet(userId, text);

    return {
        success: result.ok,
        message: result.ok ? 'Successfully posted tweet.' : result.error.message,
        errors: result.ok ? [] : [result.error.message],
    };
}

"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.runDevOpsFlow = runDevOpsFlow;
exports.runAutonomousWebAppFlow = runAutonomousWebAppFlow;
exports.handleGitHubWebhook = handleGitHubWebhook;
const githubSkills_1 = require("../skills/githubSkills");
const jira_1 = require("atomic-docker/project/functions/atom-agent/skills/jira");
const slackSkills_1 = require("atomic-docker/project/functions/atom-agent/skills/slackSkills");
const autonomousSystemOrchestrator_1 = require("./autonomousSystemOrchestrator");
const WEBHOOK_BASE_URL = 'https://atom.example.com/api/webhooks'; // This would be a real, deployed URL
async function runDevOpsFlow(userId, owner, repo, jiraProjectKey, slackChannelId) {
    console.log(`[DevOpsOrchestrator] Starting DevOps flow for user ${userId}.`);
    const result = {
        success: false,
        message: '',
        errors: [],
    };
    // 1. Create GitHub webhook
    const webhookUrl = `${WEBHOOK_BASE_URL}/github?userId=${userId}&jiraProjectKey=${jiraProjectKey}&slackChannelId=${slackChannelId}`;
    const webhookResponse = await (0, githubSkills_1.createRepoWebhook)(userId, owner, repo, webhookUrl);
    if (!webhookResponse.ok || !webhookResponse.data) {
        const errorMsg = `Failed to create GitHub webhook: ${webhookResponse.error?.message}`;
        console.error(`[DevOpsOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }
    result.success = true;
    result.webhookId = webhookResponse.data.id;
    result.message = `Successfully created webhook with ID ${result.webhookId}.`;
    console.log(`[DevOpsOrchestrator] ${result.message}`);
    return result;
}
async function runAutonomousWebAppFlow(userId, owner, repo, jiraProjectKey, slackChannelId) {
    console.log(`[DevOpsOrchestrator] Starting autonomous web app flow for user ${userId}.`);
    const result = await (0, autonomousSystemOrchestrator_1.runAutonomousSystem)(userId, owner, repo, jiraProjectKey, slackChannelId);
    return result;
}
// This would be in a separate file, e.g., pages/api/webhooks/github.ts
async function handleGitHubWebhook(payload, query) {
    console.log('[DevOpsOrchestrator] Received GitHub webhook.');
    const { userId, jiraProjectKey, slackChannelId } = query;
    if (!userId || !jiraProjectKey || !slackChannelId) {
        console.error('[DevOpsOrchestrator] Missing required query parameters in webhook URL.');
        return;
    }
    const commit = payload.commits[0];
    if (!commit) {
        console.log('[DevOpsOrchestrator] No commits in push event, ignoring.');
        return;
    }
    const commitMessage = commit.message;
    const commitUrl = commit.url;
    const commitAuthor = commit.author.name;
    // 2. Create Jira issue
    const jiraEntities = {
        summary: `New commit from ${commitAuthor}: ${commitMessage}`,
        project_key: jiraProjectKey,
        issue_type: 'Task',
    };
    const jiraResponse = await (0, jira_1.handleCreateJiraIssue)(userId, jiraEntities);
    if (!jiraResponse.startsWith('Jira issue created:')) {
        console.error(`[DevOpsOrchestrator] Failed to create Jira issue: ${jiraResponse}`);
        // In a real application, you might want to send a Slack message about the failure
        return;
    }
    const jiraIssueKey = jiraResponse.replace('Jira issue created: ', '');
    // 3. Send Slack message
    const slackMessage = `New commit by ${commitAuthor}: <${commitUrl}|${commitMessage}>. Jira issue <https://your-domain.atlassian.net/browse/${jiraIssueKey}|${jiraIssueKey}> created.`;
    await (0, slackSkills_1.sendSlackMessage)(userId, slackChannelId, slackMessage);
    console.log('[DevOpsOrchestrator] Successfully processed GitHub webhook.');
}
//# sourceMappingURL=devOpsOrchestrator.js.map
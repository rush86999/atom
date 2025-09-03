"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.runAutonomousSystem = runAutonomousSystem;
exports.runShopifyReport = runShopifyReport;
exports.runSocialMediaAutoPost = runSocialMediaAutoPost;
const jira_1 = require("atomic-docker/project/functions/atom-agent/skills/jira");
const githubSkills_1 = require("atomic-docker/project/functions/atom-agent/skills/githubSkills");
const slackSkills_1 = require("atomic-docker/project/functions/atom-agent/skills/slackSkills");
const shellSkills_1 = require("../skills/shellSkills");
const shopifyBusinessManager_1 = require("./shopifyBusinessManager");
const socialMediaOrchestrator_1 = require("./socialMediaOrchestrator");
async function runAutonomousSystem(userId, owner, repo, jiraProjectKey, slackChannelId) {
    console.log(`[AutonomousSystemOrchestrator] Starting autonomous system for user ${userId}.`);
    const result = {
        success: false,
        message: '',
        errors: [],
    };
    // 1. Create GitHub repository
    const repoResponse = await (0, githubSkills_1.createGithubRepo)(userId, owner, repo);
    if (!repoResponse.ok || !repoResponse.data) {
        const errorMsg = `Failed to create GitHub repository: ${repoResponse.error?.message}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }
    // 2. Create web app from template
    const appResponse = await (0, shellSkills_1.runShellCommand)(`npx create-react-app ${repo} --template file:../templates/create-react-app`);
    if (appResponse.exitCode !== 0) {
        const errorMsg = `Failed to create web app from template: ${appResponse.stderr}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }
    // 3. Get Jira credentials
    const jiraCredentials = await (0, jira_1.getJiraCredentials)(userId);
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
    const jiraResponse = await (0, jira_1.handleCreateJiraIssue)(userId, jiraEntities);
    if (!jiraResponse.startsWith('Jira issue created:')) {
        console.error(`[AutonomousSystemOrchestrator] Failed to create Jira issue: ${jiraResponse}`);
        result.message = `Failed to create Jira issue: ${jiraResponse}`;
        result.errors.push(jiraResponse);
        return result;
    }
    const jiraIssueKey = jiraResponse.replace('Jira issue created: ', '');
    // 5. Create GitHub issue
    const issueResponse = await (0, githubSkills_1.createGithubIssue)(userId, owner, repo, `New web app created: ${repo}`, `Jira issue: ${jiraIssueKey}`);
    if (!issueResponse.ok || !issueResponse.data) {
        const errorMsg = `Failed to create GitHub issue: ${issueResponse.error?.message}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }
    // 6. Send Slack message
    const slackMessage = `New web app created: ${repo}. Jira issue <https://${jiraCredentials.serverUrl}/browse/${jiraIssueKey}|${jiraIssueKey}> created.`;
    await (0, slackSkills_1.sendSlackMessage)(userId, slackChannelId, slackMessage);
    result.success = true;
    result.message = `Successfully created web app ${repo}.`;
    console.log(`[AutonomousSystemOrchestrator] ${result.message}`);
    return result;
}
async function runShopifyReport(userId, slackChannelId) {
    console.log(`[AutonomousSystemOrchestrator] Starting Shopify report for user ${userId}.`);
    const result = await (0, shopifyBusinessManager_1.runShopifyBusinessManager)(userId, slackChannelId);
    return {
        success: result.success,
        message: result.message,
        errors: result.errors,
    };
}
async function runSocialMediaAutoPost(userId, text) {
    console.log(`[AutonomousSystemOrchestrator] Starting social media auto post for user ${userId}.`);
    const result = await (0, socialMediaOrchestrator_1.postTweet)(userId, text);
    return {
        success: result.ok,
        message: result.ok ? 'Successfully posted tweet.' : result.error.message,
        errors: result.ok ? [] : [result.error.message],
    };
}
//# sourceMappingURL=autonomousSystemOrchestrator.js.map
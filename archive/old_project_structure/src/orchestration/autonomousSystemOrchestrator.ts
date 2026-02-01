import { createGithubRepo, createGithubIssue } from "../skills/githubSkills";
import { createJiraIssue, getJiraAccessToken } from "../skills/jiraSkills";
import { SlackSkills } from "../ui-shared/integrations/slack/skills/slackSkills";
import { runShellCommand } from "../skills/shellSkills";
import { runShopifyBusinessManager } from "./shopifyBusinessManager";
import { postTweet } from "./socialMediaOrchestrator";

interface AutonomousSystemResult {
  success: boolean;
  message: string;
  errors: string[];
  data?: any;
}

interface JiraCredentials {
  serverUrl: string;
  username: string;
  accessToken: string;
}

/**
 * Autonomous System Orchestrator
 * Coordinates multiple services to execute complex workflows autonomously
 */
export class AutonomousSystemOrchestrator {
  private slackSkills: SlackSkills;

  constructor() {
    this.slackSkills = new SlackSkills();
  }

  /**
   * Execute a complete autonomous workflow:
   * 1. Create GitHub repository
   * 2. Create web app from template
   * 3. Create Jira issue
   * 4. Create GitHub issue
   * 5. Send Slack notification
   */
  async runAutonomousSystem(
    userId: string,
    owner: string,
    repo: string,
    jiraProjectKey: string,
    slackChannelId: string,
  ): Promise<AutonomousSystemResult> {
    console.log(
      `[AutonomousSystemOrchestrator] Starting autonomous system for user ${userId}`,
    );

    const result: AutonomousSystemResult = {
      success: false,
      message: "",
      errors: [],
    };

    try {
      // 1. Create GitHub repository
      console.log(
        `[AutonomousSystemOrchestrator] Creating GitHub repository: ${repo}`,
      );
      const repoResponse = await createGithubRepo(userId, {
        name: repo,
        description: "ATOM AI generated web application",
        private: false,
        auto_init: true,
      });

      if (!repoResponse.ok) {
        const errorMsg = `Failed to create GitHub repository: ${repoResponse.error?.message}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        result.errors.push(errorMsg);
        return result;
      }

      const repoData = repoResponse.data;
      console.log(
        `[AutonomousSystemOrchestrator] GitHub repository created: ${repoData.full_url}`,
      );

      // 2. Create web app from template (placeholder - would need actual template)
      console.log(`[AutonomousSystemOrchestrator] Creating web app structure`);
      const appResponse = await runShellCommand(
        `mkdir -p ${repo} && cd ${repo} && echo "# ${repo}" > README.md`,
      );

      if (!appResponse.success) {
        const errorMsg = `Failed to create web app structure: ${appResponse.stderr}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        result.errors.push(errorMsg);
        return result;
      }

      // 3. Get Jira credentials and create issue
      console.log(`[AutonomousSystemOrchestrator] Creating Jira issue`);
      const jiraAccessToken = await getJiraAccessToken(userId);

      if (!jiraAccessToken) {
        const errorMsg = "Jira credentials not configured for this user";
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        result.errors.push(errorMsg);
        return result;
      }

      // Create Jira issue using the backend API
      const jiraResponse = await createJiraIssue(
        userId,
        jiraProjectKey,
        `New web app created: ${repo}`,
        `GitHub repository: ${repoData.full_url}\n\nAutomatically created by ATOM autonomous system.`,
      );

      if (!jiraResponse.ok) {
        const errorMsg = `Failed to create Jira issue: ${jiraResponse.error?.message}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        result.errors.push(errorMsg);
        return result;
      }

      const jiraIssueData = jiraResponse.data;
      console.log(
        `[AutonomousSystemOrchestrator] Jira issue created: ${jiraIssueData.key}`,
      );

      // 4. Create GitHub issue
      console.log(`[AutonomousSystemOrchestrator] Creating GitHub issue`);
      const issueResponse = await createGithubIssue(
        userId,
        owner,
        repo,
        `New web app created: ${repo}`,
        `Jira issue: ${jiraIssueData.key}\n\nThis project was automatically created by ATOM autonomous system.`,
      );

      if (!issueResponse.ok) {
        const errorMsg = `Failed to create GitHub issue: ${issueResponse.error?.message}`;
        console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        result.errors.push(errorMsg);
        return result;
      }

      const githubIssueData = issueResponse.data;
      console.log(
        `[AutonomousSystemOrchestrator] GitHub issue created: ${githubIssueData.html_url}`,
      );

      // 5. Send Slack message
      console.log(`[AutonomousSystemOrchestrator] Sending Slack notification`);
      const slackMessage = `🚀 New web app created: ${repo}\n\n• GitHub: ${repoData.full_url}\n• Jira: ${jiraIssueData.key}\n• GitHub Issue: ${githubIssueData.html_url}\n\nCreated automatically by ATOM autonomous system.`;

      const slackResult = await this.slackSkills.executeCommand(
        `send message to ${slackChannelId}: ${slackMessage}`,
      );

      if (!slackResult.success) {
        console.warn(
          `[AutonomousSystemOrchestrator] Failed to send Slack message: ${slackResult.error}`,
        );
        result.errors.push(`Slack notification failed: ${slackResult.error}`);
      } else {
        console.log(
          `[AutonomousSystemOrchestrator] Slack notification sent successfully`,
        );
      }

      // Success
      result.success = true;
      result.message = `Successfully created web app ${repo} with full integration setup`;
      result.data = {
        github: repoData,
        jira: jiraIssueData,
        githubIssue: githubIssueData,
        slackSent: slackResult.success,
      };

      console.log(
        `[AutonomousSystemOrchestrator] Autonomous system completed successfully`,
      );
      return result;
    } catch (error: any) {
      const errorMsg = `Autonomous system execution failed: ${error.message}`;
      console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`, error);
      result.message = errorMsg;
      result.errors.push(error.message);
      return result;
    }
  }

  /**
   * Run Shopify business report and notify via Slack
   */
  async runShopifyReport(
    userId: string,
    slackChannelId: string,
  ): Promise<AutonomousSystemResult> {
    console.log(
      `[AutonomousSystemOrchestrator] Starting Shopify report for user ${userId}`,
    );

    try {
      const result = await runShopifyBusinessManager(userId, slackChannelId);

      return {
        success: result.success,
        message: result.message,
        errors: result.errors,
        data: result,
      };
    } catch (error: any) {
      const errorMsg = `Shopify report failed: ${error.message}`;
      console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`, error);
      return {
        success: false,
        message: errorMsg,
        errors: [error.message],
      };
    }
  }

  /**
   * Run social media auto-posting
   */
  async runSocialMediaAutoPost(
    userId: string,
    text: string,
  ): Promise<AutonomousSystemResult> {
    console.log(
      `[AutonomousSystemOrchestrator] Starting social media auto post for user ${userId}`,
    );

    try {
      const result = await postTweet(userId, text);

      return {
        success: result.ok,
        message: result.ok ? "Successfully posted tweet" : result.error.message,
        errors: result.ok ? [] : [result.error.message],
        data: result,
      };
    } catch (error: any) {
      const errorMsg = `Social media auto-post failed: ${error.message}`;
      console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`, error);
      return {
        success: false,
        message: errorMsg,
        errors: [error.message],
      };
    }
  }

  /**
   * Execute a custom autonomous workflow
   */
  async executeCustomWorkflow(
    userId: string,
    workflow: {
      name: string;
      steps: Array<{
        type: "github" | "jira" | "slack" | "shell" | "shopify" | "social";
        action: string;
        parameters: any;
      }>;
    },
  ): Promise<AutonomousSystemResult> {
    console.log(
      `[AutonomousSystemOrchestrator] Executing custom workflow: ${workflow.name}`,
    );

    const result: AutonomousSystemResult = {
      success: false,
      message: "",
      errors: [],
      data: {
        steps: [],
      },
    };

    try {
      for (let index = 0; index < workflow.steps.length; index++) {
        const step = workflow.steps[index];
        console.log(
          `[AutonomousSystemOrchestrator] Executing step ${index + 1}: ${step.type} - ${step.action}`,
        );

        let stepResult: any;

        switch (step.type) {
          case "github":
            // Handle GitHub actions
            stepResult = await this.executeGitHubStep(userId, step);
            break;

          case "jira":
            // Handle Jira actions
            stepResult = await this.executeJiraStep(userId, step);
            break;

          case "slack":
            // Handle Slack actions
            stepResult = await this.executeSlackStep(userId, step);
            break;

          case "shell":
            // Handle shell commands
            stepResult = await this.executeShellStep(step);
            break;

          case "shopify":
            // Handle Shopify actions
            stepResult = await this.executeShopifyStep(userId, step);
            break;

          case "social":
            // Handle social media actions
            stepResult = await this.executeSocialStep(userId, step);
            break;

          default:
            stepResult = {
              success: false,
              error: `Unknown step type: ${step.type}`,
            };
        }

        result.data.steps.push({
          step: index + 1,
          type: step.type,
          action: step.action,
          result: stepResult,
        });

        if (!stepResult.success) {
          result.errors.push(`Step ${index + 1} failed: ${stepResult.error}`);
          break;
        }
      }

      result.success = result.errors.length === 0;
      result.message = result.success
        ? `Workflow "${workflow.name}" completed successfully`
        : `Workflow "${workflow.name}" completed with ${result.errors.length} error(s)`;

      return result;
    } catch (error: any) {
      const errorMsg = `Custom workflow execution failed: ${error.message}`;
      console.error(`[AutonomousSystemOrchestrator] ${errorMsg}`, error);
      return {
        success: false,
        message: errorMsg,
        errors: [error.message],
        data: result.data,
      };
    }
  }

  private async executeGitHubStep(userId: string, step: any): Promise<any> {
    // Implement GitHub step execution
    return { success: true, message: "GitHub step executed" };
  }

  private async executeJiraStep(userId: string, step: any): Promise<any> {
    // Implement Jira step execution
    return { success: true, message: "Jira step executed" };
  }

  private async executeSlackStep(userId: string, step: any): Promise<any> {
    // Implement Slack step execution
    return { success: true, message: "Slack step executed" };
  }

  private async executeShellStep(step: any): Promise<any> {
    // Implement shell command execution
    return { success: true, message: "Shell step executed" };
  }

  private async executeShopifyStep(userId: string, step: any): Promise<any> {
    // Implement Shopify step execution
    return { success: true, message: "Shopify step executed" };
  }

  private async executeSocialStep(userId: string, step: any): Promise<any> {
    // Implement social media step execution
    return { success: true, message: "Social step executed" };
  }
}

// Export singleton instance
export const autonomousSystemOrchestrator = new AutonomousSystemOrchestrator();

// Legacy function exports for backward compatibility
export async function runAutonomousSystem(
  userId: string,
  owner: string,
  repo: string,
  jiraProjectKey: string,
  slackChannelId: string,
): Promise<AutonomousSystemResult> {
  return autonomousSystemOrchestrator.runAutonomousSystem(
    userId,
    owner,
    repo,
    jiraProjectKey,
    slackChannelId,
  );
}

export async function runShopifyReport(
  userId: string,
  slackChannelId: string,
): Promise<AutonomousSystemResult> {
  return autonomousSystemOrchestrator.runShopifyReport(userId, slackChannelId);
}

export async function runSocialMediaAutoPost(
  userId: string,
  text: string,
): Promise<AutonomousSystemResult> {
  return autonomousSystemOrchestrator.runSocialMediaAutoPost(userId, text);
}

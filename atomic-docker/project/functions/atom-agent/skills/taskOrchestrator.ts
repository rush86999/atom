import {
  ComplexTask,
  ProcessedNLUResponse,
  ComplexTaskSubTaskNlu,
  ExecutedSubTaskResult,
  OrchestratedComplexTaskReport,
  AgentSkillContext,
} from "../types";
import * as conversationManager from "../conversationState";
import {
  handleSemanticSearchMeetingNotesSkill,
  handleSimpleTextSearch,
} from "./semanticSearchSkills";
import {
  createHubSpotContact,
  getHubSpotContactByEmail,
} from "./hubspotSkills";
import {
  createNotionTask,
  queryNotionTasks,
  updateNotionTask,
} from "./notionAndResearchSkills";
import { handleSearchGmail, handleExtractInfoFromGmail } from "./gmailSkills";
import {
  handleSearchSlackMessages,
  handleExtractInfoFromSlackMessage,
} from "./slackQuerySkills";
import {
  handleSearchMSTeamsMessages,
  handleExtractInfoFromMSTeamsMessage,
} from "./msTeamsQuerySkills";
import {
  listUpcomingEvents,
  createCalendarEvent,
  listUpcomingGoogleMeetEvents,
  getGoogleMeetEventDetails,
} from "./calendarSkills";
import {
  listMicrosoftTeamsMeetings,
  getMicrosoftTeamsMeetingDetails,
} from "./msTeamsSkills";
import { listRecentEmails, readEmail, sendEmail } from "./emailSkills";
import { searchWeb } from "./webResearchSkills";
import { logger } from "../../_utils/logger";
import { processGuidanceRequest } from "../../../src/orchestration/guidance_orchestrator";

/**
 * Core Task Orchestrator that connects synthesizing and orchestrating agents to skills
 * Handles ComplexTask decomposition and execution with inter-task context
 */
export class TaskOrchestrator {
  private context: AgentSkillContext;
  private subTaskExecutionLog: ExecutedSubTaskResult[] = [];

  constructor(context: AgentSkillContext) {
    this.context = context;
  }

  /**
   * Main entry point for orchestrating complex tasks
   */
  async orchestrateComplexTask(
    nluResponse: ProcessedNLUResponse,
    userId: string,
    interfaceType: string,
  ): Promise<OrchestratedComplexTaskReport> {
    if (
      !nluResponse.intent === "ComplexTask" ||
      !nluResponse.entities?.sub_tasks
    ) {
      throw new Error("Invalid ComplexTask response structure");
    }

    const { sub_tasks } = nluResponse.entities;
    const originalQuery =
      nluResponse.originalQuery || "Complex multi-step request";

    logger.info(
      `[TaskOrchestrator] Processing complex task with ${sub_tasks.length} sub-tasks`,
    );

    // Initialize execution context for inter-task data sharing
    const executionContext: Record<string, any> = {};
    const subTaskResults: ExecutedSubTaskResult[] = [];

    for (let i = 0; i < sub_tasks.length; i++) {
      const subTask = sub_tasks[i];
      try {
        logger.info(
          `[TaskOrchestrator] Executing sub-task ${i + 1}/${sub_tasks.length}: ${subTask.intent}`,
        );

        // Execute individual sub-task with context from previous tasks
        const result = await this.executeSubTask(
          subTask,
          i,
          userId,
          interfaceType,
          executionContext,
        );

        subTaskResults.push(result);

        // Stop execution chain if a critical task fails
        if (result.status === "failure" && subTask.intent !== "SearchWeb") {
          logger.warn(
            `[TaskOrchestrator] Critical task failed, stopping execution: ${result.error_details}`,
          );
          break;
        }

        // Store context for next tasks
        if (result.returned_data) {
          executionContext[subTask.intent] = result.returned_data;
        }
      } catch (error) {
        logger.error(
          `[TaskOrchestrator] Error executing sub-task ${i + 1}:`,
          error,
        );

        subTaskResults.push({
          sub_task_nlu: subTask,
          execution_order: i,
          status: "failure",
          error_details: error instanceof Error ? error.message : String(error),
          message_from_handler: "Task failed due to an unexpected error",
        });

        // Continue with next tasks for non-critical failures
        continue;
      }
    }

    // Generate comprehensive report
    return this.generateComplexTaskReport(
      originalQuery,
      subTaskResults,
      executionContext,
    );
  }

  /**
   * Execute individual sub-tasks within complex task workflow
   */
  private async executeSubTask(
    subTask: ComplexTaskSubTaskNlu,
    orderIndex: number,
    userId: string,
    interfaceType: string,
    context: Record<string, any>,
  ): Promise<ExecutedSubTaskResult> {
    const { intent, entities, summary_for_sub_task } = subTask;

    try {
      let result: any;
      let message: string;

      // Route sub-task to appropriate skill handler
      switch (intent) {
        case "SearchEmail":
          result = await handleSearchGmail(userId, entities);
          message = `Found ${result.results?.length || 0} relevant emails`;
          break;

        case "ReadEmail":
          result = await readEmail(userId, entities.emailId || entities.id);
          message = `Email retrieved successfully`;
          break;

        case "SearchSlackMessages":
          result = await handleSearchSlackMessages(userId, entities);
          message = `Found ${result.results?.length || 0} relevant Slack messages`;
          break;

        case "ReadSlackMessage":
          result = await handleExtractInfoFromSlackMessage(
            userId,
            entities.messageId,
          );
          message = `Slack message details retrieved`;
          break;

        case "SearchMSTeamsMessages":
          result = await handleSearchMSTeamsMessages(userId, entities);
          message = `Found ${result.results?.length || 0} relevant Teams messages`;
          break;

        case "GetCalendarEvents":
          result = await listUpcomingEvents(userId, entities);
          message = `Found ${result.events?.length || 0} upcoming calendar events`;
          break;

        case "CreateCalendarEvent":
          // Check context for related data
          if (context["SearchEmail"]) {
            entities.referenceContext = {
              relatedEmails: context["SearchEmail"].results?.slice(0, 3),
            };
          }
          result = await createCalendarEvent(userId, entities);
          message = `Calendar event created successfully`;
          break;

        case "CreateHubSpotContact":
          result = await createHubSpotContact(userId, entities);
          message = `HubSpot contact created successfully`;
          break;

        case "CreateNotionTask":
          // Pull context from previous tasks
          if (context["SearchEmail"]) {
            entities.emailReference = context["SearchEmail"].results?.[0];
          }
          if (context["SearchSlackMessages"]) {
            entities.slackReference =
              context["SearchSlackMessages"].results?.[0];
          }
          result = await createNotionTask(userId, entities);
          message = `Notion task created successfully`;
          break;

        case "WebSearch":
          result = await searchWeb(entities.query);
          message = `Web search completed`;
          break;

        case "SendEmail":
          // Use context from previous search/extraction tasks
          const emailTemplate = this.buildEmailFromContext(context, entities);
          result = await sendEmail(userId, emailTemplate);
          message = `Email sent successfully`;
          break;

        case "LearningAssistance":
          const guidanceResult = await processGuidanceRequest(
            entities.query || summary_for_sub_task || "Provide guidance",
            userId,
            entities.applicationContext,
          );
          result = guidanceResult;
          message = guidanceResult.messageToUser;
          break;

        case "SemanticSearch":
          const semanticResult = await handleSemanticSearchMeetingNotesSkill(
            userId,
            { query: entities.query || summary_for_sub_task },
          );
          result = semanticResult;
          message = `Semantic search completed`;
          break;

        default:
          const unsupportedError = `Sub-task intent "${intent}" not supported by orchestrator`;
          logger.warn(`[TaskOrchestrator] ${unsupportedError}`);
          return {
            sub_task_nlu: subTask,
            execution_order: orderIndex,
            status: "skipped" as const,
            message_from_handler: unsupportedError,
            error_details: unsupportedError,
          };
      }

      return {
        sub_task_nlu: subTask,
        execution_order: orderIndex,
        status: "success" as const,
        message_from_handler: message,
        returned_data: result,
      };
    } catch (error) {
      logger.error(`[TaskOrchestrator] Error in sub-task ${intent}:`, error);
      return {
        sub_task_nlu: subTask,
        execution_order: orderIndex,
        status: "failure" as const,
        error_details: error instanceof Error ? error.message : String(error),
        message_from_handler: `Failed to execute ${intent}`,
      };
    }
  }

  /**
   * Build email content using context from previous tasks
   */
  private buildEmailFromContext(
    context: Record<string, any>,
    entities: Record<string, any>,
  ): any {
    const email = {
      to: entities.to || [],
      subject: entities.subject || "Follow-up from automation",
      body: entities.body || entities.message || "",
    };

    // Incorporate context from search results
    if (context["SearchEmail"] && email.body.includes("{{EMAIL_CONTEXT}}")) {
      const emailSummaries =
        context["SearchEmail"].results
          ?.slice(0, 3)
          .map(
            (e: any) =>
              `- ${e.subject}: ${e.snippet || e.body?.substring(0, 200)}`,
          )
          .join("\n") || "No relevant emails found";
      email.body = email.body.replace("{{EMAIL_CONTEXT}}", emailSummaries);
    }

    if (
      context["SearchSlackMessages"] &&
      email.body.includes("{{SLACK_CONTEXT}}")
    ) {
      const slackSummaries =
        context["SearchSlackMessages"].results
          ?.slice(0, 3)
          .map((m: any) => `- ${m.text?.substring(0, 200)} (${m.channel})`)
          .join("\n") || "No relevant Slack messages";
      email.body = email.body.replace("{{SLACK_CONTEXT}}", slackSummaries);
    }

    return email;
  }

  /**
   * Generate comprehensive report for complex task execution
   */
  private generateComplexTaskReport(
    originalQuery: string,
    subTaskResults: ExecutedSubTaskResult[],
    context: Record<string, any>,
  ): OrchestratedComplexTaskReport {
    const successfulTasks = subTaskResults.filter(
      (r) => r.status === "success",
    );
    const failedTasks = subTaskResults.filter((r) => r.status === "failure");

    let finalStatus: OrchestratedComplexTaskReport["overall_status"];
    if (failedTasks.length === 0) {
      finalStatus = "completed_fully";
    } else if (successfulTasks.length > 0 && failedTasks.length > 0) {
      finalStatus = "completed_partially";
    } else if (failedTasks.length === subTaskResults.length) {
      finalStatus = "failed_entirely";
    } else {
      finalStatus = "completed_partially";
    }

    // Build user-friendly summary
    let finalMessage = `I completed your request to "${originalQuery}".\n\n`;

    if (successfulTasks.length > 0) {
      finalMessage += "Here's what I accomplished:\n";
      successfulTasks.forEach((task) => {
        const intentName = task.sub_task_nlu.intent || "Task";
        finalMessage += `- ${intentName}: ${task.message_from_handler}\n`;
      });
    }

    if (failedTasks.length > 0) {
      finalMessage += "\nTasks that couldn't be completed:\n";
      failedTasks.forEach((task) => {
        const intentName = task.sub_task_nlu.intent || "Task";
        finalMessage += `- ${intentName}: ${task.error_details}\n`;
      });
    }

    return {
      original_user_query: originalQuery,
      overall_status: finalStatus,
      final_summary_message_for_user: finalMessage,
      sub_task_results: subTaskResults,
      inter_task_context: context,
    };
  }

  /**
   * Simplified orchestration for sequential skills without full complex task
   */
  async orchestrateSequentialTasks(
    intents: Array<{
      intent: string;
      entities: Record<string, any>;
      context?: Record<string, any>;
    }>,
    userId: string,
  ): Promise<any> {
    const results = [];
    const sequentialContext: Record<string, any> = {};

    for (const item of intents) {
      const result = await this.executeSubTask(
        {
          intent: item.intent,
          entities: item.entities,
          summary_for_sub_task: `${item.intent} execution`,
        },
        results.length,
        userId,
        "text",
        { ...sequentialContext, ...item.context },
      );

      results.push(result);

      if (result.status === "success" && result.returned_data) {
        sequentialContext[item.intent] = result.returned_data;
      }
    }

    return {
      results,
      context: sequentialContext,
      summary: `Completed ${results.filter((r) => r.status === "success").length}/${results.length} tasks`,
    };
  }
}

// Export orchestrator instance and class
export const taskOrchestrator = new TaskOrchestrator({
  userId: "",
  sendCommandToClient: async () => true,
  settings: {},
});

// Convenience function for direct usage
export async function orchestrateComplexAgentTask(
  nluResponse: ProcessedNLUResponse,
  userId: string,
  interfaceType: string = "text",
): Promise<OrchestratedComplexTaskReport> {
  return taskOrchestrator.orchestrateComplexTask(
    nluResponse,
    userId,
    interfaceType,
  );
}

// Simplified orchestration function for quick integration
export function createTaskOrchestrator(
  context: AgentSkillContext,
): TaskOrchestrator {
  return new TaskOrchestrator(context);
}

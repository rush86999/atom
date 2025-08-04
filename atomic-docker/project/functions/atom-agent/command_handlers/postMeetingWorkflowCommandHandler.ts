import {
  ProcessMeetingOutcomesNluEntities,
  PostMeetingActionsResults,
  ProcessMeetingOutcomesSkillResponse,
} from '../types';
import { executePostMeetingActions } from '../skills/postMeetingWorkflowSkill';
import { logger } from '../../_utils/logger';

function formatPostMeetingActionResults(
  results: PostMeetingActionsResults
): string {
  let response = `Okay, I've processed the outcomes for "${results.processed_meeting_reference}":\n`;

  if (results.summary_of_decisions) {
    response += `\n**Key Decisions Summarized:**\n${results.summary_of_decisions}\n`;
  }

  if (results.extracted_action_items_summary) {
    response += `\n**Action Items Extracted:**\n${results.extracted_action_items_summary}\n`;
  }

  if (results.drafted_email_content) {
    response += `\n**Follow-up Email Drafted:**\n  To: ${results.drafted_email_content.to?.join(', ') || 'N/A'}\n  Subject: ${results.drafted_email_content.subject || 'N/A'}\n  (Full body is ready. You can ask me to show it or send it.)\n`;
    // In a real scenario, we might store the draft and provide an ID or options to send/edit.
  }

  if (results.created_notion_tasks && results.created_notion_tasks.length > 0) {
    response += `\n**Tasks Created in Notion:**\n`;
    results.created_notion_tasks.forEach((task) => {
      response += `  - "${task.description}" (URL: ${task.taskUrl})\n`;
    });
  } else if (results.created_notion_tasks) {
    // It exists but is empty
    response += `\n**Tasks Creation:** No new tasks were created in Notion based on the action items.\n`;
  }

  if (results.errors_encountered && results.errors_encountered.length > 0) {
    response += '\n**Some issues were encountered:**\n';
    results.errors_encountered.forEach((err) => {
      response += `  - Action: ${err.action_attempted}, Error: ${err.message}\n`;
    });
  }

  if (
    response ===
    `Okay, I've processed the outcomes for "${results.processed_meeting_reference}":\n`
  ) {
    response +=
      'No specific actions seem to have produced output, or no actions were successfully completed.';
  }

  return response;
}

/**
 * Handles the "ProcessMeetingOutcomes" intent.
 * Calls the post-meeting workflow skill and formats the results for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the ProcessMeetingOutcomes intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export async function handleProcessMeetingOutcomesRequest(
  userId: string,
  entities: ProcessMeetingOutcomesNluEntities
): Promise<string> {
  logger.info(
    `[PostMeetingWorkflowCommandHandler] Handling request for user ${userId}, meeting: "${entities.meeting_reference}"`
  );
  logger.debug(
    `[PostMeetingWorkflowCommandHandler] Received NLU entities: ${JSON.stringify(entities)}`
  );

  if (!entities.requested_actions || entities.requested_actions.length === 0) {
    logger.warn(
      `[PostMeetingWorkflowCommandHandler] No actions requested for meeting: "${entities.meeting_reference}"`
    );
    return "You asked me to process meeting outcomes, but didn't specify what actions to take (e.g., summarize, extract action items, draft email, create tasks).";
  }

  try {
    const skillResponse: ProcessMeetingOutcomesSkillResponse =
      await executePostMeetingActions(userId, entities);

    if (skillResponse.ok && skillResponse.data) {
      logger.info(
        `[PostMeetingWorkflowCommandHandler] Skill executed successfully for "${entities.meeting_reference}".`
      );
      const formattedResponse = formatPostMeetingActionResults(
        skillResponse.data
      );
      logger.debug(
        `[PostMeetingWorkflowCommandHandler] Formatted response: ${formattedResponse}`
      );
      return formattedResponse;
    } else {
      logger.error(
        `[PostMeetingWorkflowCommandHandler] Skill execution failed for "${entities.meeting_reference}": ${skillResponse.error?.message}`,
        skillResponse.error
      );
      return `I encountered an issue while processing the meeting outcomes for "${entities.meeting_reference}": ${skillResponse.error?.message || 'Unknown error from skill'}.`;
    }
  } catch (error: any) {
    logger.error(
      `[PostMeetingWorkflowCommandHandler] Critical error handling request for "${entities.meeting_reference}": ${error.message}`,
      error
    );
    return `I encountered an unexpected critical error while trying to process outcomes for "${entities.meeting_reference}": ${error.message}.`;
  }
}

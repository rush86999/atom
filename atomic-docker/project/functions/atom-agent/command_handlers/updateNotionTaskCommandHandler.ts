import {
  SkillResponse,
  UpdateTaskData,
  // Conceptual NLU entity types
} from '../types';
import { handleUpdateNotionTask } from '../skills/notionTaskSkills'; // The actual skill
import { logger } from '../../_utils/logger';

// NLU Entities expected by this handler for "UpdateTask" intent
interface UpdateTaskHandlerNluEntities {
  task_identifier_text: string; // Text to help identify the task
  new_status_text?: string;
  new_due_date_text?: string;
  new_priority_text?: string;
  new_list_name_text?: string;
  new_description_text?: string;
  // This entity helps differentiate simple updates from specific actions like "mark as complete"
  update_action?: 'complete' | 'set_due_date' | 'change_priority' | 'rename' | 'move_list' | 'add_notes';
}


/**
 * Handles the "UpdateTask" intent.
 * Calls the skill to update a Notion task and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the UpdateTask intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export async function handleUpdateTaskRequest(
  userId: string,
  entities: UpdateTaskHandlerNluEntities,
): Promise<string> {
  logger.info(`[UpdateNotionTaskCmdHandler] Handling request for user ${userId} to update task.`);
  logger.debug(`[UpdateNotionTaskCmdHandler] Received NLU entities: ${JSON.stringify(entities)}`);

  if (!entities.task_identifier_text) {
    logger.warn(`[UpdateNotionTaskCmdHandler] Missing task_identifier_text.`);
    return "Please specify which task you want to update (e.g., by its name or part of its description).";
  }

  // If a specific update_action is "complete", ensure new_status_text reflects "Done"
  // NLU should ideally handle this mapping, but we can enforce it here.
  let finalEntities = { ...entities };
  if (entities.update_action === 'complete' && entities.new_status_text?.toLowerCase() !== 'done') {
    logger.info(`[UpdateNotionTaskCmdHandler] 'complete' action detected, overriding status to 'Done'.`);
    finalEntities.new_status_text = 'Done';
  }


  try {
    const skillResponse: SkillResponse<UpdateTaskData & { userMessage: string }> = await handleUpdateNotionTask(userId, {
        task_identifier_text: finalEntities.task_identifier_text,
        new_status_text: finalEntities.new_status_text,
        new_due_date_text: finalEntities.new_due_date_text,
        new_priority_text: finalEntities.new_priority_text,
        new_list_name_text: finalEntities.new_list_name_text,
        new_description_text: finalEntities.new_description_text,
    });

    if (skillResponse.ok && skillResponse.data?.userMessage) {
      logger.info(`[UpdateNotionTaskCmdHandler] Task update successful: ${skillResponse.data.userMessage}`);
      return skillResponse.data.userMessage;
    } else {
      // If the error was about ambiguity, the skill itself returns a userMessage for clarification
      if (skillResponse.error?.code === 'AMBIGUOUS_TASK' && skillResponse.data?.userMessage) {
          logger.warn(`[UpdateNotionTaskCmdHandler] Task update ambiguous: ${skillResponse.data.userMessage}`);
          return skillResponse.data.userMessage;
      }
      const errorMsg = skillResponse.error?.message || skillResponse.data?.userMessage || 'Unknown error from skill';
      logger.error(`[UpdateNotionTaskCmdHandler] Skill execution failed or task update unsuccessful: ${errorMsg}`, skillResponse.error);
      return `I couldn't update the task. ${errorMsg}`;
    }
  } catch (error: any) {
    logger.error(`[UpdateNotionTaskCmdHandler] Critical error handling request: ${error.message}`, error);
    return `I encountered an unexpected critical error while trying to update the task: ${error.message}.`;
  }
}

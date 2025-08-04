import {
  // Assuming NLU entities for general task creation will be similar or a new type.
  // For now, using a generic Record<string, any> and will cast/validate inside.
  // Ideally, a CreateTaskNluEntities type would be defined in types.ts
  SkillResponse,
  CreateTaskData,
} from '../types';
import { handleCreateNotionTask } from '../skills/notionTaskSkills'; // The actual skill implementation
import { logger } from '../../_utils/logger';

// NLU Entities expected by this handler (should align with what NLU provides for "CreateTask" intent)
// This is based on the conceptual CreateTaskNluEntities from notionTaskSkills.ts
interface CreateTaskHandlerNluEntities {
  task_description: string;
  due_date_text?: string;
  priority_text?: string;
  list_name_text?: string;
  // any other entities NLU might provide for this intent
}

/**
 * Handles the "CreateTask" intent.
 * Calls the skill to create a Notion task and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the CreateTask intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export async function handleCreateTaskRequest(
  userId: string,
  nluEntities: CreateTaskHandlerNluEntities,
  integrations: any
): Promise<string> {
  logger.info(
    `[CreateNotionTaskCmdHandler] Handling request for user ${userId} to create task.`
  );
  logger.debug(
    `[CreateNotionTaskCmdHandler] Received NLU entities: ${JSON.stringify(entities)}`
  );

  if (!entities.task_description) {
    logger.warn(`[CreateNotionTaskCmdHandler] Missing task_description.`);
    return 'Please provide a description for the task you want to create.';
  }

  try {
    // The skill `handleCreateNotionTask` expects entities matching its internal CreateTaskNluEntities.
    // Ensure the structure passed matches.
    const skillResponse: SkillResponse<
      CreateTaskData & { userMessage: string }
    > = await handleCreateNotionTask(
      userId,
      {
        task_description: entities.task_description,
        due_date_text: entities.due_date_text,
        priority_text: entities.priority_text,
        list_name_text: entities.list_name_text,
      },
      integrations
    );

    if (skillResponse.ok && skillResponse.data?.userMessage) {
      logger.info(
        `[CreateNotionTaskCmdHandler] Task creation successful: ${skillResponse.data.userMessage}`
      );
      return skillResponse.data.userMessage;
    } else {
      const errorMsg =
        skillResponse.error?.message ||
        skillResponse.data?.userMessage ||
        'Unknown error from skill';
      logger.error(
        `[CreateNotionTaskCmdHandler] Skill execution failed or task creation unsuccessful: ${errorMsg}`,
        skillResponse.error
      );
      return `I couldn't create the task. ${errorMsg}`;
    }
  } catch (error: any) {
    logger.error(
      `[CreateNotionTaskCmdHandler] Critical error handling request: ${error.message}`,
      error
    );
    return `I encountered an unexpected critical error while trying to create the task: ${error.message}.`;
  }
}

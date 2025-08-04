import {
  CreateTaskFromChatMessageNluEntities,
  TaskCreationResultFromMessage,
  CreateTaskFromChatMessageSkillResponse,
} from '../types';
import { createTaskFromChatMessage } from '../skills/taskFromChatSkill';
import { logger } from '../../_utils/logger';

/**
 * Handles the "CreateTaskFromChatMessage" intent.
 * Calls the skill to create a task from a chat message and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the CreateTaskFromChatMessage intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export async function handleCreateTaskFromChatMessageRequest(
  userId: string,
  entities: CreateTaskFromChatMessageNluEntities
): Promise<string> {
  logger.info(
    `[TaskFromChatCmdHandler] Handling request for user ${userId} to create task from message: "${entities.chat_message_reference}" on ${entities.source_platform}`
  );
  logger.debug(
    `[TaskFromChatCmdHandler] Received NLU entities: ${JSON.stringify(entities)}`
  );

  if (!entities.chat_message_reference || !entities.source_platform) {
    logger.warn(
      `[TaskFromChatCmdHandler] Missing chat_message_reference or source_platform.`
    );
    return 'To create a task from a message, please tell me which message and from what platform (e.g., Slack, Teams).';
  }

  try {
    const skillResponse: CreateTaskFromChatMessageSkillResponse =
      await createTaskFromChatMessage(userId, entities);

    if (skillResponse.ok && skillResponse.data?.success) {
      const taskResult = skillResponse.data;
      logger.info(
        `[TaskFromChatCmdHandler] Task created successfully: ID ${taskResult.taskId}`
      );
      let responseText = `Okay, I've created a task: "${taskResult.taskTitle || 'Untitled Task'}"`;
      if (taskResult.taskUrl) {
        responseText += ` (Link: ${taskResult.taskUrl})`;
      }
      responseText += `. ${taskResult.message}`;
      return responseText;
    } else {
      const errorMsg =
        skillResponse.error?.message ||
        skillResponse.data?.message ||
        'Unknown error from skill';
      logger.error(
        `[TaskFromChatCmdHandler] Skill execution failed or task creation unsuccessful: ${errorMsg}`,
        skillResponse.error
      );
      return `I couldn't create a task from that message. ${errorMsg}`;
    }
  } catch (error: any) {
    logger.error(
      `[TaskFromChatCmdHandler] Critical error handling request: ${error.message}`,
      error
    );
    return `I encountered an unexpected critical error while trying to create a task from the message: ${error.message}.`;
  }
}

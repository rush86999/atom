import {
  SkillResponse,
  NotionTask,
  // Conceptual NLU entity types
} from '../types';
import { handleQueryNotionTasks } from '../skills/notionTaskSkills'; // The actual skill
import { logger } from '../../_utils/logger';

// NLU Entities expected by this handler for "QueryTasks" intent
interface QueryTasksHandlerNluEntities {
  date_condition_text?: string;
  priority_text?: string;
  list_name_text?: string;
  status_text?: string;
  description_contains_text?: string;
  sort_by_text?: 'dueDate' | 'priority' | 'createdDate';
  sort_order_text?: 'ascending' | 'descending';
  limit_number?: number;
  // any other entities NLU might provide
}

/**
 * Handles the "QueryTasks" intent.
 * Calls the skill to query Notion tasks and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the QueryTasks intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export async function handleQueryTasksRequest(
  userId: string,
  entities: QueryTasksHandlerNluEntities
): Promise<string> {
  logger.info(
    `[QueryNotionTasksCmdHandler] Handling request for user ${userId} to query tasks.`
  );
  logger.debug(
    `[QueryNotionTasksCmdHandler] Received NLU entities: ${JSON.stringify(entities)}`
  );

  try {
    const skillResponse: SkillResponse<{
      tasks: NotionTask[];
      userMessage: string;
    }> = await handleQueryNotionTasks(userId, {
      date_condition_text: entities.date_condition_text,
      priority_text: entities.priority_text,
      list_name_text: entities.list_name_text,
      status_text: entities.status_text,
      description_contains_text: entities.description_contains_text,
      sort_by_text: entities.sort_by_text,
      sort_order_text: entities.sort_order_text,
      limit_number: entities.limit_number,
    });

    if (skillResponse.ok && skillResponse.data?.userMessage) {
      logger.info(`[QueryNotionTasksCmdHandler] Task query successful.`);
      return skillResponse.data.userMessage;
    } else {
      const errorMsg =
        skillResponse.error?.message ||
        skillResponse.data?.userMessage ||
        'Unknown error from skill';
      logger.error(
        `[QueryNotionTasksCmdHandler] Skill execution failed or task query unsuccessful: ${errorMsg}`,
        skillResponse.error
      );
      return `I couldn't query tasks. ${errorMsg}`;
    }
  } catch (error: any) {
    logger.error(
      `[QueryNotionTasksCmdHandler] Critical error handling request: ${error.message}`,
      error
    );
    return `I encountered an unexpected critical error while trying to query tasks: ${error.message}.`;
  }
}

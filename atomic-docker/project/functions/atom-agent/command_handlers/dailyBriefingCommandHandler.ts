import {
  GetDailyPriorityBriefingNluEntities,
  DailyBriefingData,
  GetDailyPriorityBriefingSkillResponse,
  BriefingItem,
} from '../types';
import { generateDailyBriefing } from '../skills/dailyBriefingSkill';
import { logger } from '../../_utils/logger';

/**
 * Handles the "GetDailyPriorityBriefing" intent.
 * Calls the daily briefing skill and formats the results into a structured
 * message object for the frontend to render with a custom component.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the GetDailyPriorityBriefing intent.
 * @returns A promise that resolves to a message object for the client, or a simple string on error.
 */
export async function handleGetDailyBriefingRequest(
  userId: string,
  entities: GetDailyPriorityBriefingNluEntities,
): Promise<any> { // Return type is now 'any' to accommodate the structured message object
  const dateContext = entities.date_context || 'today';
  logger.info(`[DailyBriefingCommandHandler] Handling request for user ${userId} for briefing: "${dateContext}"`);
  logger.debug(`[DailyBriefingCommandHandler] Received NLU entities: ${JSON.stringify(entities)}`);

  try {
    const skillResponse: GetDailyPriorityBriefingSkillResponse = await generateDailyBriefing(userId, entities);

    if (skillResponse.ok && skillResponse.data) {
      const briefing = skillResponse.data;
      logger.info(`[DailyBriefingCommandHandler] Skill executed successfully for "${dateContext}". Found ${briefing.priority_items.length} items.`);

      // Construct the structured response for the frontend
      const structuredMessage = {
        content: briefing.overall_summary_message || `Here is your briefing for ${briefing.briefing_date}.`,
        customComponentType: 'daily_briefing_results',
        customComponentProps: {
          briefing: briefing,
        },
      };

      logger.debug(`[DailyBriefingCommandHandler] Sending structured message to client.`);
      return structuredMessage;

    } else {
      logger.error(`[DailyBriefingCommandHandler] Skill execution failed for "${dateContext}": ${skillResponse.error?.message}`, skillResponse.error);
      // Return a simple string error message on failure
      return `I encountered an issue while generating your daily briefing for "${dateContext}": ${skillResponse.error?.message || 'Unknown error from skill'}.`;
    }
  } catch (error: any) {
    logger.error(`[DailyBriefingCommandHandler] Critical error handling request for "${dateContext}": ${error.message}`, error);
    return `I encountered an unexpected critical error while trying to generate your briefing for "${dateContext}": ${error.message}.`;
  }
}

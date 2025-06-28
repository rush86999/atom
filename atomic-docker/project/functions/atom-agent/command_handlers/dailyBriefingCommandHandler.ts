import {
  GetDailyPriorityBriefingNluEntities,
  DailyBriefingData,
  GetDailyPriorityBriefingSkillResponse,
  BriefingItem,
} from '../types';
import { generateDailyBriefing } from '../skills/dailyBriefingSkill';
import { logger } from '../../_utils/logger';

function formatBriefingItem(item: BriefingItem): string {
  let formatted = `- **${item.title}** (${item.type})`;
  if (item.details) {
    formatted += `\n    Details: ${item.details}`;
  }
  if (item.link) {
    formatted += `\n    Link: ${item.link}`;
  }
  // Add more formatting based on item.urgency_score or item.raw_item if needed
  return formatted;
}

/**
 * Handles the "GetDailyPriorityBriefing" intent.
 * Calls the daily briefing skill and formats the results for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the GetDailyPriorityBriefing intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export async function handleGetDailyBriefingRequest(
  userId: string,
  entities: GetDailyPriorityBriefingNluEntities,
): Promise<string> {
  const dateContext = entities.date_context || 'today';
  logger.info(`[DailyBriefingCommandHandler] Handling request for user ${userId} for briefing: "${dateContext}"`);
  logger.debug(`[DailyBriefingCommandHandler] Received NLU entities: ${JSON.stringify(entities)}`);

  try {
    const skillResponse: GetDailyPriorityBriefingSkillResponse = await generateDailyBriefing(userId, entities);

    if (skillResponse.ok && skillResponse.data) {
      const briefing = skillResponse.data;
      logger.info(`[DailyBriefingCommandHandler] Skill executed successfully for "${dateContext}". Found ${briefing.priority_items.length} items.`);

      let responseText = `Okay, here's your priority briefing for ${briefing.briefing_date}:\n`;

      if (briefing.overall_summary_message) {
        responseText += `${briefing.overall_summary_message}\n`;
      }

      if (briefing.priority_items.length > 0) {
        responseText += "\n**Key Items:**\n";
        briefing.priority_items.forEach(item => {
          responseText += `${formatBriefingItem(item)}\n`;
        });
      } else if (!briefing.overall_summary_message) { // If no summary and no items
        responseText += "It looks like there are no specific priority items for you at the moment based on the current filters.\n";
      }

      if (briefing.errors_encountered && briefing.errors_encountered.length > 0) {
        responseText += "\n**Some issues were encountered while gathering your briefing:**\n";
        briefing.errors_encountered.forEach(err => {
          responseText += `  - Source: ${err.source_area}, Error: ${err.message}\n`;
        });
      }

      logger.debug(`[DailyBriefingCommandHandler] Formatted response: ${responseText}`);
      return responseText;

    } else {
      logger.error(`[DailyBriefingCommandHandler] Skill execution failed for "${dateContext}": ${skillResponse.error?.message}`, skillResponse.error);
      return `I encountered an issue while generating your daily briefing for "${dateContext}": ${skillResponse.error?.message || 'Unknown error from skill'}.`;
    }
  } catch (error: any) {
    logger.error(`[DailyBriefingCommandHandler] Critical error handling request for "${dateContext}": ${error.message}`, error);
    return `I encountered an unexpected critical error while trying to generate your briefing for "${dateContext}": ${error.message}.`;
  }
}

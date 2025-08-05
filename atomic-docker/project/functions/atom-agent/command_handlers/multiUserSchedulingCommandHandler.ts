import {
  MultiUserSchedulingNluEntities,
  MultiUserSchedulingResponse,
  UserAvailability,
  LLMSuggestedSchedule,
} from '../types';
import { orchestrateMultiUserMeeting } from '../skills/llmMultiUserScheduler';
import { logger } from '../../_utils/logger';
import { dayjs } from '../../_libs/datetime/date-utils';

/**
 * Handles multi-user scheduling requests using LLM intelligence
 * Delegates to atom-agent skills for actual processing
 */
export async function handleMultiUserSchedulingRequest(
  userId: string,
  entities: MultiUserSchedulingNluEntities
): Promise<MultiUserSchedulingResponse> {
  const operationName = 'MultiUserSchedulingHandler';
  logger.info({
    operation: operationName,
    userId,
    meetingTitle: entities.meeting_title,
    participantCount: entities.participant_emails?.length || 0,
  });

  try {
    // Validate required inputs
    if (!entities.meeting_title || !entities.participant_emails?.length) {
      return {
        success: false,
        error: 'Meeting title and participants are required',
        suggestions: [],
      };
    }

    // Build the multi-user scheduling request
    const scheduleRequest = {
      organizerUserId: userId,
      meetingTitle: entities.meeting_title,
      participantEmails: entities.participant_emails,
      preferredWindowStart: entities.preferred_window_start || dayjs().add(1, 'day').toISOString(),
      preferredWindowEnd: entities.preferred_window_end || dayjs().add(7, 'days').toISOString(),
      constraints: entities.constraints || [],
      meetingType: entities.meeting_type as ('internal' | 'client' | 'external' | 'team'),
      durationMinutes: entities.duration_minutes || 60,
    };

    // Use LLM-powered scheduler for complex multi-user coordination
    const result = await orchestrateMultiUserMeeting(scheduleRequest);

    if (!result.success) {
      return {
        success: false,
        error: result.error || 'Failed to schedule multi-user meeting',
        suggestions: [],
      };
    }

    // Format response for user
    let responseText = '';
    if (result.meetingCreated && result.meetingId) {
      responseText = `✅ Successfully scheduled "${entities.meeting_title}"! `;
      responseText += `The LLM found an optimal time considering all ${entities.participant_emails.length} participants. `;
    } else {
      responseText = `📅 I've analyzed availability for ${entities.participant_emails.length} participants. `;
    }

    if (result.suggestedTimes.suggestions.length > 0) {
      responseText += `\n\n**Top ${Math.min(3, result.suggestedTimes.suggestions.length)} LLM-recommended times:**\n`;

      result.suggestedTimes.suggestions.slice(0, 3).forEach((suggestion, index) => {
        const time = dayjs(suggestion.time).format('ddd, MMM D at h:mm A');
        responseText += `\n${index + 1}. ${time} (${suggestion.score}/100 score)`;
        responseText += `\n   - ${suggestion.participants.length}/${entities.participant_emails.length} participants available`;
        responseText += `\n   - ${suggestion.reasoning}`;
      });
    }

    responseText += `\n\n${result.suggestedTimes.recommendation || ''}`;

    return {
      success: true,
      meetingId: result.meetingId,
      suggestedTimes: result.suggestedTimes,
      message: responseText,
    };

  } catch (error) {
    logger.error({
      operation: operationName,
      error: error.message,
      stack: error.stack,
      userId,
    });

    return {
      success: false,
      error: `Scheduling failed: ${error.message}`,
      suggestions: [],
    };
  }
}

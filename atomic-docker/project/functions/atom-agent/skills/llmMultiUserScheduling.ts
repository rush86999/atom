import { OpenAI } from 'openai';
import { dayjs } from '../_libs/datetime/date-utils';
import { logger } from '../_utils/logger';
import { getUsersAvailability } from './schedulingSkills';
import { listCompanyContacts } from './contactSkills';
import { createCalendarEvent } from './calendarSkills';
import { sendEmail } from './gmailSkills';
import { sendSlackMessage } from './slackSkills';

// OpenAI client for LLM intelligence
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || '',
});

interface MultiUserMeetingRequest {
  organizerUserId: string;
  meetingTitle: string;
  participantEmails: string[];
  preferredWindowStart: string;
  preferredWindowEnd: string;
  constraints: string[];
  meetingType: 'internal' | 'client' | 'external' | 'team';
  durationMinutes: number;
}

interface UserAvailability {
  userId: string;
  email: string;
  displayName: string;
  availableSlots: TimeSlot[];
  conflicts: CalendarEvent[];
  timezone: string;
}

interface TimeSlot {
  start: Date;
  end: Date;
  priority: 'high' | 'medium' | 'low';
  reason?: string;
}

interface CalendarEvent {
  summary: string;
  start: string;
  end: string;
}

interface LLMSuggestedTimes {
  suggestions: {
    time: string;
    participants: string[];
    conflicts: string[];
    score: number;
    reasoning: string;
  }[];
  recommendation: string;
}

/**
 * LLM-powered multi-user scheduling coordinator
 * Uses natural language processing to find optimal meeting times
 * across multiple users with intelligent conflict resolution
 */
export class LLMMultiUserScheduler {
  /**
   * Main orchestration method for multi-user meeting scheduling
   */
  async scheduleMultiUserMeeting(request: MultiUserMeetingRequest): Promise<{
    success: boolean;
    suggestedTimes: LLMSuggestedTimes;
    meetingCreated?: boolean;
    meetingId?: string;
  }> {
    logger.info({
      operation: 'LLM_MULTI_USER_SCHEDULE',
      organizer: request.organizerUserId,
      participants: request.participantEmails.length,
      meeting: request.meetingTitle,
    });

    try {
      // 1. Get availability for all participants
      const availabilityData = await this.getAllParticipantsAvailability(request);

      // 2. Use LLM to find optimal times considering all constraints
      const suggestedTimes = await this.findOptimalMeetingTimes(
        availabilityData,
        request
      );

      // 3. If auto-approve criteria met, create meeting
      let meetingCreated = false;
      let meetingId: string | undefined;

      if (suggestedTimes.suggestions.length > 0 &&
          suggestedTimes.suggestions[0].participants.length >= Math.ceil(request.participantEmails.length * 0.75)) {

        const topSuggestion = suggestedTimes.suggestions[0];

        meetingData = await this.createOrProposeMeeting(
          topSuggestion,
          request
        );

        meetingCreated = meetingData.success;
        meetingId = meetingData.meetingId;
      }

      return {
        success: true,
        suggestedTimes,
        meetingCreated,
        meetingId,
      };

    } catch (error) {
      logger.error({
        operation: 'LLM_MULTI_USER_SCHEDULE_ERROR',
        error: error.message,
        stack: error.stack,
      });

      throw error;
    }
  }

  /**
   * LLM-powered time finding with intelligent analysis
   */
  private async findOptimalMeetingTimes(
    participants: UserAvailability[],
    request: MultiUserMeetingRequest
  ): Promise<LLMSuggestedTimes> {

    const prompt = this.buildLLMPrompt(participants, request);

    const response = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [{
        role: 'system',
        content: `You are an expert meeting scheduler AI. Find optimal meeting times for groups considering:
        - Work schedules and time zones
        - Meeting importance and participant roles
        - Corporate calendar patterns
        - Conflict severity and availability alternatives
        Return times ranked by suitability score (1-100). Format in JSON.`
      }, {
        role: 'user',
        content: prompt
      }],
      response_format: { type: 'json_object' },
    });

    const suggestions = JSON.parse(response.choices[0]?.message?.content || '{}');

    return {
      suggestions: suggestions.suggestions || [],
      recommendation: suggestions.recommendation || '',
    };
  }

  private buildLLMPrompt(
    participants: UserAvailability[],
    request: MultiUserMeetingRequest
  ): string {
    const participantDetails = participants.map(p => ({
      email: p.email,
      name: p.displayName,
      timezone: p.timezone,
      availableSlots: p.availableSlots.map(slot => ({
        start: slot.start.toISOString(),
        end: slot.end.toISOString(),
        priority: slot.priority
      })),
      conflicts: p.conflicts.map(c => ({
        summary: c.summary,
        start: c.start,
        end: c.end
      }))
    }));

    return JSON.stringify({
      meetingTitle: request.meetingTitle,
      participants: participantDetails,
      preferredWindow: {
        start: request.preferredWindowStart,
        end: request.preferredWindowEnd
      },
      durationMinutes: request.durationMinutes,
      meetingType: request.meetingType,
      constraints: request.constraints,
      instructions: `Find optimal meeting times by analyzing all participants' schedules.
      Consider:
      1. Minimize conflicts for key participants
      2. Respect time zones
      3. Prefer available slots over rescheduling conflicts
      4. Provide reasoning for each suggestion
      5. Include score from 1-100 based on participants available`
    });
  }

  /**
   * Get availability for all participants
   */
  private async getAllParticipantsAvailability(
    request: MultiUserMeetingRequest
  ): Promise<UserAvailability[]> {

    const participants = await Promise.all(
      request.participantEmails.map(async email => {
        // In real implementation, resolve email to userId
        const userAvailability = await getUsersAvailability(
          [email], // This would need userId resolution
          request.preferredWindowStart,
          request.preferredWindowEnd
        );

        return {
          userId: email, // Placeholder - would resolve to actual user ID
          email,
          displayName: email.split('@')[0],
          availableSlots: userAvailability.availableSlots || [],
          conflicts: userAvailability.conflicts || [],
          timezone: userAvailability.timezone || 'UTC'
        };
      })
    );

    return participants;
  }

  /**
   * Create meeting after LLM analysis, or send proposal
   */
  private async createOrProposeMeeting(
    suggestion: LLMSuggestedTimes['suggestions'][0],
    request: MultiUserMeetingRequest
  ): Promise<{ success: boolean; meetingId?: string; error?: string }> {
    try {
      const meetingStart = new Date(suggestion.time);
      const meetingEnd = new Date(meetingStart.getTime() + request.durationMinutes * 60000);

      // Create calendar event
      const meetingData = await createCalendarEvent(request.organizerUserId, {
        summary: request.meetingTitle,
        start: meetingStart.toISOString(),
        end: meetingEnd.toISOString(),
        attendees: suggestion.participants,
        sendInvites: suggestion.conflicts.length < 2, // Send invites if few conflicts
      });

      // Send coordinated notifications
      await this.sendCoordinatedInvitations(request, suggestion);

      return { success: true, meetingId: meetingData.eventId };

    } catch (error) {
      logger.error({
        operation: 'CREATE_MEETING_ERROR',
        error: error.message,
        meeting: request.meetingTitle
      });

      return { success: false, error: error.message };
    }
  }

  private async sendCoordinatedInvitations(
    request: MultiUserMeetingRequest,
    suggestion: LLMSuggestedTimes['suggestions'][0]
  ): Promise<void> {
    // Send personalized invitations
    const meetingStart = new Date(suggestion.time);

    for (const participant of suggestion.participants) {
      const personalizedMessage = suggestion.reasoning ||
        `Meeting scheduled: ${request.meetingTitle} at ${meetingStart.toLocaleString()}`;

      // Send via user's preferred communication method
      await sendEmail(request.organizerUserId, {
        to: [participant],
        subject: `Meeting Invitation: ${request.meetingTitle}`,
        body: personalizedMessage
      });
    }

    // Create Slack announcement for teams
    if (request.meetingType === 'team' || request.participantEmails.length > 3) {
      await sendSlackMessage(request.organizerUserId, {
        channel: '#general',
        text: `${request.meetingTitle} scheduled for ${meetingStart.toLocaleString()}. Please check your calendar.`
      });
    }
  }

  /**
   * LLM-powered conflict resolution assistance
   */
  async resolveConflicts(
    conflicts: Array<{
      userId: string;
      reason: string;
    }>,
    request: MultiUserMeetingRequest
  ): Promise<string> {
    const prompt = `Resolve meeting conflicts: ${conflicts.map(c => `${c.userId}: ${c.reason}`).join(', ')} for ${request.meetingTitle}`;

    const response = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [{
        role: 'system',
        content: 'Generate diplomatic conflict resolution suggestions with alternatives.'
      }, { role: 'user', content: prompt }]
    });

    return response.choices[0]?.message?.content || 'Unable to generate conflict resolution suggestions';
  }
}

/**
 * High-level orchestration service for multi-user scheduling
 */
export async function orchestrateMultiUserMeeting(
  request: MultiUserMeetingRequest
) {
  const scheduler = new LLMMultiUserScheduler();
  return await scheduler.scheduleMultiUserMeeting(request);
}

export { LLMMultiUserScheduler };

import { ChatBrainBodyType } from './types';
import { callOpenAI } from '@chat/_libs/api-helper';

import OpenAI from 'openai';
import {
  defaultOpenAIAPIKey,
  openAIChatGPT35Model,
} from '@chat/_libs/constants';
import {
  categorizeSkillFromUserInputExampleInput,
  categorizeSkillFromUserInputExampleOutput,
  categorizeSkillFromUserInputPrompt,
} from '@chat/_libs/prompts/categorizeSkillFromUserInput';
import {
  SkillMessageHistoryType,
  SkillType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { askAvailabilityControlCenterForPending } from '@chat/_libs/skills/askCalendar/askAvailability/api-helper';
import { askEventControlCenter } from '@chat/_libs/skills/askCalendar/findEvent/api-helper';
import { nextEventControlCenter } from '@chat/_libs/skills/askCalendar/nextEvent/api-helper';
import { addTaskControlCenter } from '@chat/_libs/skills/orderCalendar/addTask/api-helper';
import { blockOffTimeControlCenter } from '@chat/_libs/skills/orderCalendar/blockOffTime/api-helper';
import { cancelMeetingControlCenterPending } from '@chat/_libs/skills/orderCalendar/cancelMeeting/api-helper';
import { queryEventsControlCenter } from '@chat/_libs/skills/askCalendar/findEvents/api-helper';
import { createEventControlCenter } from '@chat/_libs/skills/orderCalendar/createEvent/api-helper';
import { deleteEventControlCenter } from '@chat/_libs/skills/orderCalendar/deleteEvent/api-helper';
import { deletePriorityControlCenter } from '@chat/_libs/skills/orderCalendar/deletePriority/api-helper';
import { deleteTaskControlCenter } from '@chat/_libs/skills/orderCalendar/deleteTask/api-helper';
import { EAPTToPreferredTimesControlCenter } from '@chat/_libs/skills/orderCalendar/editAddPreferredTimeToPreferredTimes/api-helper';
import { editEventControlCenter } from '@chat/_libs/skills/orderCalendar/editEvent/api-helper';
import { ERPT2PTControlCenter } from '@chat/_libs/skills/orderCalendar/editRemovePreferredTimeToPreferredTimes/api-helper';
import { FMTWPControlCenter } from '@chat/_libs/skills/orderCalendar/findMeetingTimeWithPermission/api-helper';
import { generateMeetingInviteControlCenter } from '@chat/_libs/skills/orderCalendar/generateMeetingInvite/api-helper';
import { RAPControlCenter } from '@chat/_libs/skills/orderCalendar/removeAllPreferedTimes/api-helper';
import { RCEControlCenter } from '@chat/_libs/skills/orderCalendar/resolveConflictingEvents/api-helper';
import { scheduleMeetingControlCenter } from '@chat/_libs/skills/orderCalendar/scheduleMeeting/api-helper';
import { sendMeetingInviteControlCenter } from '@chat/_libs/skills/orderCalendar/sendMeetingInvite/api-helper';
import { updateMeetingControlCenter } from '@chat/_libs/skills/orderCalendar/updateMeeting/api-helper';
import { updatePriorityControlCenter } from '@chat/_libs/skills/orderCalendar/updatePriority/api-helper';
import { updateTaskControlCenter } from '@chat/_libs/skills/orderCalendar/updateTask/api-helper';

const openai = new OpenAI({
  apiKey: defaultOpenAIAPIKey,
});

const processQueries = async (
  userId: string,
  timezone: string,
  messageHistoryObject: SkillMessageHistoryType
) => {
  try {
    // const userInput = messageHistoryObject?.messages?.[messageHistoryObject?.messages?.length - 1]?.content
    // extractQueryUserInputTimeToJSONTemplate
    const userCurrentTime = dayjs()
      .tz(timezone)
      .format('dddd, YYYY-MM-DDTHH:mm:ssZ');

    switch (messageHistoryObject.skill) {
      case 'ask-availability':
        const messageHistoryObjectReturnedAskAvailability =
          await askAvailabilityControlCenterForPending(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime
          );

        return messageHistoryObjectReturnedAskAvailability;

      case 'find-event':
        const messageHistoryObjectReturnedAskEvent =
          await askEventControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedAskEvent;
      case 'find-events':
        const messageHistoryObjectReturnedAskEvents =
          await queryEventsControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedAskEvents;
      case 'find-next-event':
        const messageHistoryObjectReturnedNextEvent =
          await nextEventControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedNextEvent;

      case 'add-task':
        const messageHistoryObjectReturnedAddTask = await addTaskControlCenter(
          openai,
          userId,
          timezone,
          messageHistoryObject,
          userCurrentTime,
          messageHistoryObject?.query
        );

        return messageHistoryObjectReturnedAddTask;

      case 'block-off-time':
        const messageHistoryObjectReturnedBockOffTime =
          await blockOffTimeControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject.query
          );

        return messageHistoryObjectReturnedBockOffTime;
      case 'cancel-meeting':
        const messageHistoryObjectReturnedCancelMeeting =
          await cancelMeetingControlCenterPending(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject.query
          );

        return messageHistoryObjectReturnedCancelMeeting;

      case 'create-event':
        const messageHistoryObjectReturnedCreateEvent =
          await createEventControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject.query
          );

        return messageHistoryObjectReturnedCreateEvent;

      case 'delete-event':
        const messageHistoryObjectReturnedDeleteEvent =
          await deleteEventControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject.query
          );

        return messageHistoryObjectReturnedDeleteEvent;

      case 'delete-priority':
        const messageHistoryObjectReturnedDeletePriority =
          await deletePriorityControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject.query
          );

        return messageHistoryObjectReturnedDeletePriority;

      case 'delete-task':
        const messageHistoryObjectReturnedDeleteTask =
          await deleteTaskControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );
        return messageHistoryObjectReturnedDeleteTask;
      case 'edit-add-preferred-time-to-preferred-times':
        // EAPTToPreferredTimesControlCenterPending
        const messageHistoryObjectReturnedEAPT =
          await EAPTToPreferredTimesControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );
        return messageHistoryObjectReturnedEAPT;

      case 'edit-event':
        // editEventControlCenterPending
        const messageHistoryObjectReturnedEditEvent =
          await editEventControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );
        return messageHistoryObjectReturnedEditEvent;

      case 'edit-remove-preferred-time-to-preferred-times':
        // ERPT2PTControlCenterPending
        const messageHistoryObjectReturnedERPT2PTs = await ERPT2PTControlCenter(
          openai,
          userId,
          timezone,
          messageHistoryObject,
          userCurrentTime,
          messageHistoryObject?.query
        );
        return messageHistoryObjectReturnedERPT2PTs;

      case 'find-meeting-time-with-permission':
        // findMeetingTimeWithPermissionControlCenterPending
        const messageHistoryObjectReturnedFMTWP = await FMTWPControlCenter(
          openai,
          userId,
          timezone,
          messageHistoryObject,
          userCurrentTime,
          messageHistoryObject?.query
        );

        return messageHistoryObjectReturnedFMTWP;
      case 'generate-meeting-invite':
        // generateMeetingInviteControlCenterPending
        const messageHistoryObjectReturnedGMI =
          await generateMeetingInviteControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedGMI;

      case 'remove-all-preferred-times':
        // RAPControlCenterPending
        const messageHistoryObjectReturnedRAP = await RAPControlCenter(
          openai,
          userId,
          timezone,
          messageHistoryObject,
          userCurrentTime,
          messageHistoryObject?.query
        );

        return messageHistoryObjectReturnedRAP;

      case 'resolve-conflicting-events':
        const messageHistoryObjectReturnedRCE = await RCEControlCenter(
          openai,
          userId,
          timezone,
          messageHistoryObject,
          userCurrentTime,
          messageHistoryObject?.query
        );

        return messageHistoryObjectReturnedRCE;

      case 'schedule-meeting':
        // scheduleMeetingControlCenterPending
        const messageHistoryObjectReturnedScheduleMeeting =
          await scheduleMeetingControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedScheduleMeeting;

      case 'send-meeting-invite':
        // sendMeetingInviteControlCenterPending
        const messageHistoryObjectReturnedSMI =
          await sendMeetingInviteControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedSMI;

      case 'update-meeting':
        // updateMeetingControlCenterPending
        const messageHistoryObjectReturnedUpdateMeeting =
          await updateMeetingControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedUpdateMeeting;

      case 'update-priority':
        // updatePriorityControlCenterPending
        const messageHistoryObjectReturnedUpdatePriority =
          await updatePriorityControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedUpdatePriority;

      case 'update-task':
        // updateTaskControlCenterPending
        const messageHistoryObjectReturnedUpdateTask =
          await updateTaskControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedUpdateTask;

      default:
        const messageHistoryObjectReturnedAskEventsDefault =
          await queryEventsControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );

        return messageHistoryObjectReturnedAskEventsDefault;
    }
  } catch (e) {
    console.log(e, ' unable to process pending queries');
  }
};

// Define AgentClientCommand and AgentContext interfaces locally or import from a shared types file
// This should align with definitions in atom-agent/handler.ts and functions_build_docker/server.ts
interface AgentClientCommand {
  command_id: string;
  action:
    | 'START_RECORDING_SESSION'
    | 'STOP_RECORDING_SESSION'
    | 'CANCEL_RECORDING_SESSION';
  payload?: {
    suggestedTitle?: string;
    linkedEventId?: string;
  };
}

interface AgentSkillContext {
  userId: string;
  sendCommandToClient: (
    userId: string,
    command: AgentClientCommand
  ) => Promise<boolean>;
}

// NLUResult structure expected by inPersonAudioNoteSkills
interface NluIntentResult {
  // Simplified for this context
  intent: { name: string; confidence?: number };
  entities?: { [key: string]: any };
  raw_input?: string;
}

// Modify processQueries to accept sendCommandToUserFunc
const processQueries = async (
  userId: string,
  timezone: string,
  messageHistoryObject: SkillMessageHistoryType,
  sendCommandToUserFunc?: (
    userId: string,
    command: AgentClientCommand
  ) => Promise<boolean> // New parameter
) => {
  try {
    const userCurrentTime = dayjs()
      .tz(timezone)
      .format('dddd, YYYY-MM-DDTHH:mm:ssZ');

    // Import the new skill handlers here if they are not too large,
    // or create a dedicated control center that imports them.
    // For now, let's assume we might call them more directly for simplicity of this step,
    // acknowledging this might be refactored into a proper "control center".
    // This dynamic import is for illustration; static imports are generally preferred.
    const ইনPersonAudioNoteSkills = await import(
      '../../../atom-agent/skills/inPersonAudioNoteSkills'
    );

    switch (messageHistoryObject.skill) {
      // --- NEW CASES FOR IN-PERSON AUDIO NOTES ---
      case 'IN_PERSON_AUDIO_NOTE_START': // Assuming NLU categorizes to this
      case 'IN_PERSON_AUDIO_NOTE_STOP':
      case 'IN_PERSON_AUDIO_NOTE_CANCEL':
        if (!sendCommandToUserFunc) {
          console.error(
            'sendCommandToUserFunc not provided to processQueries for audio note skill.'
          );
          // Fallback response or error
          messageHistoryObject.messages.push({
            role: 'assistant',
            content:
              "Sorry, I can't control audio recording right now due to a setup issue.",
          });
          return messageHistoryObject;
        }
        const agentSkillContext: AgentSkillContext = {
          userId,
          sendCommandToClient: sendCommandToUserFunc,
        };
        // Construct a simplified NLU result for the skill handler
        const nluResultForSkill: NluIntentResult = {
          intent: { name: messageHistoryObject.skill }, // e.g., "IN_PERSON_AUDIO_NOTE_START"
          entities: messageHistoryObject.prevData?.entities || {}, // Pass any entities gathered by NLU
          raw_input:
            messageHistoryObject.messages[
              messageHistoryObject.messages.length - 1
            ]?.content,
        };

        let skillResponse;
        if (messageHistoryObject.skill === 'IN_PERSON_AUDIO_NOTE_START') {
          skillResponse =
            await ইনPersonAudioNoteSkills.handleStartInPersonAudioNoteDirect(
              nluResultForSkill,
              agentSkillContext
            );
        } else if (messageHistoryObject.skill === 'IN_PERSON_AUDIO_NOTE_STOP') {
          skillResponse =
            await ইনPersonAudioNoteSkills.handleStopInPersonAudioNoteDirect(
              nluResultForSkill,
              agentSkillContext
            );
        } else {
          // CANCEL
          skillResponse =
            await ইনPersonAudioNoteSkills.handleCancelInPersonAudioNoteDirect(
              nluResultForSkill,
              agentSkillContext
            );
        }

        messageHistoryObject.messages.push({
          role: 'assistant',
          content: skillResponse.message,
        });
        messageHistoryObject.query = 'completed'; // Mark as completed
        return messageHistoryObject;

      // --- EXISTING CASES ---
      case 'ask-availability':
        const messageHistoryObjectReturnedAskAvailability =
          await askAvailabilityControlCenterForPending(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime
          );
        return messageHistoryObjectReturnedAskAvailability;

      // ... (all other existing cases remain unchanged) ...

      case 'update-task':
        // updateTaskControlCenterPending
        const messageHistoryObjectReturnedUpdateTask =
          await updateTaskControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );
        return messageHistoryObjectReturnedUpdateTask;

      default:
        // If skill is not one of the audio commands or other known skills,
        // it might fall through to a default handler or error.
        // For now, let's assume the existing default (queryEventsControlCenter) is fine if no match.
        console.warn(
          `processQueries: Unhandled or default skill: ${messageHistoryObject.skill}`
        );
        const messageHistoryObjectReturnedAskEventsDefault =
          await queryEventsControlCenter(
            openai,
            userId,
            timezone,
            messageHistoryObject,
            userCurrentTime,
            messageHistoryObject?.query
          );
        return messageHistoryObjectReturnedAskEventsDefault;
    }
  } catch (e) {
    console.log(e, ' unable to process pending queries in processQueries');
    // Ensure a valid SkillMessageHistoryType is returned even on error
    messageHistoryObject.messages.push({
      role: 'assistant',
      content: 'An error occurred while processing your request.',
    });
    messageHistoryObject.query = 'error';
    return messageHistoryObject;
  }
};

// Modify assistant_brain to accept and pass sendCommandToUserFunc
const assistant_brain = async (
  eventPayload: string | Buffer, // Changed 'event' to 'eventPayload' for clarity
  userIdFromWs: string, // Explicitly passed by server.ts
  // requestFromWs: any, // The original request object from WebSocket upgrade, if needed by any skill
  sendCommandToUserFunc?: (
    userId: string,
    command: AgentClientCommand
  ) => Promise<boolean> // New parameter
) => {
  // const body = eventPayload; // Keep if direct Buffer processing is needed

  try {
    // If eventPayload is Buffer, convert to string. If already string, use as is.
    const bodyString = Buffer.isBuffer(eventPayload)
      ? eventPayload.toString()
      : eventPayload;
    console.log(bodyString, ' bodyString inside assistant_brain');

    const bodyObject: ChatBrainBodyType = JSON.parse(bodyString);
    console.log(bodyObject, ' bodyObject inside assistant_brain');

    // userId should be the authenticated one from WebSocket connection, not from body if possible
    const userId = userIdFromWs || bodyObject?.userId;
    const timezone = bodyObject?.timezone;
    const messageHistoryObject = bodyObject?.chat;

    if (!userId) {
      throw new Error(
        'no userId provided (either from WebSocket auth or message body)'
      );
    }
    if (!timezone) {
      // Fallback timezone or error
      // For now, let's use a default or throw. Agent might need user's actual timezone.
      console.warn(
        `No timezone provided for user ${userId}, falling back to UTC or agent default.`
      );
      // throw new Error('no timezone provided');
    }
    if (!messageHistoryObject) {
      throw new Error('no messageHistoryObject (chat payload)');
    }

    // NLU Skill Categorization (existing logic)
    if (messageHistoryObject?.skill === 'pending') {
      const userInputForNlu =
        messageHistoryObject?.messages?.[
          messageHistoryObject?.messages?.length - 1
        ]?.content;
      if (userInputForNlu) {
        const openAIResSkill = await callOpenAI(
          openai,
          categorizeSkillFromUserInputPrompt,
          openAIChatGPT35Model,
          userInputForNlu,
          categorizeSkillFromUserInputExampleInput,
          categorizeSkillFromUserInputExampleOutput
        );
        console.log(openAIResSkill, ' openAIResSkill categorized by NLU');
        messageHistoryObject.skill = openAIResSkill as SkillType;
        // TODO: If NLU categorizes to IN_PERSON_AUDIO_NOTE_START, etc., it needs to also extract entities
        // like suggestedTitle and pass them. For now, this is a gap if relying on this NLU.
        // The `inPersonAudioNoteSkills` currently expect entities in `nluResult.entities`.
        // `messageHistoryObject.prevData.entities` might be a place to store them.
      } else {
        console.warn('User input for NLU skill categorization is empty.');
        messageHistoryObject.skill = 'unknown_or_empty_input'; // Handle gracefully
      }
    }

    // Call processQueries, now passing sendCommandToUserFunc
    const res = await processQueries(
      userId,
      timezone || 'UTC',
      messageHistoryObject,
      sendCommandToUserFunc
    );

    return JSON.stringify(res);
  } catch (e: any) {
    console.error('Error in assistant_brain:', e.message, e.stack);
    return JSON.stringify(e);
  }
};

export default assistant_brain;

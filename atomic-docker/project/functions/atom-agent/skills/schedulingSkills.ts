import axios, { AxiosResponse, AxiosError } from 'axios';

// Placeholder for actual logger if available, otherwise use console
const logger = {
  info: console.log,
  warn: console.warn,
  error: console.error,
};

// Configuration
const ATOMIC_SCHEDULER_API_BASE_URL = process.env.ATOMIC_SCHEDULER_API_BASE_URL || 'http://localhost:8080/api/scheduler'; // Example, should be configured
const AGENT_CALLBACK_BASE_URL = process.env.AGENT_PUBLIC_BASE_URL || 'http://localhost:3000/api'; // Agent's own public URL for callbacks

// ----- Placeholder Helper Functions -----
function generateUuid(): string {
  // Basic placeholder UUID generation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function normalizeDateTime(dateInput?: string, timeInput?: string): string {
  // VERY basic placeholder - real implementation needs robust date/time parsing library
  if (dateInput && dateInput.includes('T') && dateInput.endsWith('Z')) return dateInput;
  if (timeInput && timeInput.includes('T') && timeInput.endsWith('Z')) return timeInput;

  const now = new Date();

  if (dateInput) {
    if (dateInput.toLowerCase() === 'tomorrow') {
      now.setDate(now.getDate() + 1);
    } else if (dateInput.includes('-')) {
        const parts = dateInput.split('-');
        if (parts.length === 3) {
            now.setFullYear(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        } else if (parts.length === 2) {
            now.setMonth(parseInt(parts[0]) - 1, parseInt(parts[1]));
        }
    }
  } else {
      if (!timeInput || !timeInput.match(/(\d+)(?::(\d+))?\s*(am|pm)?/i)) {
         now.setDate(now.getDate() + 1);
      }
  }

  now.setHours(12, 0, 0, 0);

  if (timeInput) {
      const parts = timeInput.match(/(\d+)(?::(\d+))?\s*(am|pm)?/i);
      if (parts) {
          let hours = parseInt(parts[1]);
          const minutes = parts[2] ? parseInt(parts[2]) : 0;
          if (parts[3]?.toLowerCase() === 'pm' && hours < 12) hours += 12;
          if (parts[3]?.toLowerCase() === 'am' && hours === 12) hours = 0;
          now.setHours(hours, minutes, 0, 0);
      }
  }
  return now.toISOString();
}

function calculateEndTime(startTimeIso: string, durationStr?: string): string {
    const startDate = new Date(startTimeIso);
    if (durationStr) {
        const match = durationStr.match(/(\d+)\s*(hour|minute|hr|min)/i);
        if (match) {
            const value = parseInt(match[1]);
            const unit = match[2].toLowerCase();
            if (unit.startsWith('hour') || unit.startsWith('hr')) {
                startDate.setHours(startDate.getHours() + value);
            } else if (unit.startsWith('minute') || unit.startsWith('min')) {
                startDate.setMinutes(startDate.getMinutes() + value);
            }
        } else {
             startDate.setHours(startDate.getHours() + 1);
        }
    } else {
        startDate.setHours(startDate.getHours() + 1);
    }
    return startDate.toISOString();
}

function getCurrentUserBasic(userId: string): User {
    return {
        id: userId,
        hostId: userId,
        workTimes: [
            { userId, hostId: userId, dayOfWeek: "MONDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "TUESDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "WEDNESDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "THURSDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "FRIDAY", startTime: "09:00:00", endTime: "17:00:00" },
        ],
        maxWorkLoadPercent: 100,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };
}

// Based on NLU entities defined in nluService.ts and handler.ts
export interface NLUCreateTimePreferenceRuleEntities {
  activity_description: string;
  time_ranges: Array<{ start_time: string; end_time: string }>;
  days_of_week: string[];
  priority?: number | string;
  category_tags?: string[];
}

export interface NLUBlockTimeSlotEntities {
  task_name: string;
  start_time?: string;
  end_time?: string;
  duration?: string;
  date?: string;
  purpose?: string;
}

export interface NLUScheduleTeamMeetingEntities {
  attendees: string[];
  purpose?: string;
  duration_preference?: string;
  time_preference_details?: string;
  meeting_title?: string;
}

export interface SchedulingResponse {
  success: boolean;
  message: string;
  ruleId?: string;
  timeBlockId?: string;
  meetingRequestId?: string;
  details?: any;
  singletonId?: string;
}

// ----- Types for PostTableRequestBody -----
export interface Timeslot {
    hostId: string;
    dayOfWeek: string;
    startTime: string;
    endTime: string;
    monthDay: string;
    date: string;
}

export interface WorkTime {
    userId: string;
    hostId: string;
    dayOfWeek: string;
    startTime: string;
    endTime: string;
}

export interface User {
    id: string;
    hostId: string;
    workTimes: WorkTime[];
    maxWorkLoadPercent?: number;
    timeZone?: string;
    workingDays?: string[];
}

export interface PreferredTimeRange {
    eventId?: string;
    userId?: string;
    hostId?: string;
    startTime: string;
    endTime: string;
    dayOfWeek?: string;
}

export interface Event {
    id: string;
    userId: string;
    hostId: string;
    eventType: "TASK" | "ONE_ON_ONE_MEETING" | "GROUP_MEETING" | "EVENT";
    duration?: number;
    minChunkTime?: number;
    maxChunkTime?: number;
    preferredTimeRanges?: PreferredTimeRange[] | null;
    deadline?: string | null;
    priority?: number;
    title?: string;
    description?: string;
}

export interface EventPart {
    groupId: string;
    eventId: string;
    part: number;
    lastPart: number;
    startDate: string;
    endDate: string;
    userId: string;
    hostId: string;
    user?: User | null;
    event?: Event | null;
    preferredTime?: PreferredTimeRange[] | null;
    deadline?: string | null;
    priority?: number;
}

export interface PostTableRequestBody {
  singletonId: string;
  hostId: string;
  timeslots: Timeslot[];
  userList: User[];
  eventParts: EventPart[];
  fileKey: string;
  delay: number;
  callBackUrl: string;
}

// ----- Shared State Import -----
import { pendingSchedulingRequests, PendingRequestInfo } from '../sharedAgentState';

// ----- Real HTTP Client with Axios -----
interface HttpClientResponse {
  status: number;
  data?: any;
  error?: string;
  headers?: any;
}

const httpClient = {
  post: async (url: string, body: any): Promise<HttpClientResponse> => {
    logger.info(`[httpClient.post] Making actual HTTP POST request to ${url}`);
    // logger.info(`[httpClient.post] Body Summary: singletonId=${body?.singletonId}, fileKey=${body?.fileKey}, eventPartsCount=${body?.eventParts?.length}, userListCount=${body?.userList?.length}`);
    try {
      const response: AxiosResponse = await axios.post(url, body, {
        headers: {
          'Content-Type': 'application/json',
          // 'User-Agent': 'AtomicAgent/1.0', // Example User-Agent
        },
        timeout: 10000, // 10 seconds timeout
      });
      return {
        status: response.status,
        data: response.data,
        headers: response.headers,
      };
    } catch (error) {
      const axiosError = error as AxiosError;
      if (axiosError.response) {
        logger.error(`[httpClient.post] Error response from ${url}: Status ${axiosError.response.status}`, axiosError.response.data);
        return {
          status: axiosError.response.status,
          data: axiosError.response.data,
          error: (axiosError.response.data as any)?.message || axiosError.message, // Extract message from error data if possible
          headers: axiosError.response.headers,
        };
      } else if (axiosError.request) {
        logger.error(`[httpClient.post] No response received from ${url}:`, axiosError.request);
        return {
          status: -1, // Custom status for no response / network error
          error: 'No response received from server. Network error or timeout.',
        };
      } else {
        logger.error('[httpClient.post] Error setting up request:', axiosError.message);
        return {
          status: -2, // Custom status for request setup error
          error: `Error setting up request: ${axiosError.message}`,
        };
      }
    }
  }
};


// ----- Core Scheduling Skill -----
export async function submitSchedulingJobToAtomicScheduler(
  userId: string,
  data: PostTableRequestBody
): Promise<{ success: boolean; message: string; singletonId?: string }> {
  logger.info(`[submitSchedulingJobToAtomicScheduler] Called for userId: ${userId}, singletonId: ${data.singletonId}, hostId: ${data.hostId}, fileKey: ${data.fileKey}`);

  if (!data.singletonId || !data.hostId || !data.fileKey || !data.callBackUrl) {
    logger.error("[submitSchedulingJobToAtomicScheduler] Missing critical fields in PostTableRequestBody: singletonId, hostId, fileKey, or callBackUrl.");
    return {
      success: false,
      message: "Internal error: Critical information missing for scheduling request."
    };
  }

  const schedulerEndpoint = `${ATOMIC_SCHEDULER_API_BASE_URL}/timeTable/user/solve-day`;

  try {
    const requestInfo: PendingRequestInfo = {
      userId: userId,
      hostId: data.hostId,
      fileKey: data.fileKey,
      singletonId: data.singletonId, // Make sure PendingRequestInfo includes this
      // originalQuery: "Pass if available and part of PendingRequestInfo",
      submittedAt: new Date(),
    };
    pendingSchedulingRequests.set(data.fileKey, requestInfo);

    logger.info(`[submitSchedulingJobToAtomicScheduler] Sending job to scheduler: ${schedulerEndpoint}`);
    const response = await httpClient.post(schedulerEndpoint, data);

    if (response.status === 200 || response.status === 202) { // 202 Accepted is a common response for async job submissions
      logger.info(`[submitSchedulingJobToAtomicScheduler] Job successfully submitted to scheduler for singletonId: ${data.singletonId} (fileKey: ${data.fileKey}). Status: ${response.status}, Response Data:`, response.data);
      return {
        success: true,
        message: "Your scheduling request has been submitted. You will be notified when it's complete.", // Or use response.data.message if provided and suitable
        singletonId: data.singletonId,
      };
    } else {
      // Handle specific client/server errors from httpClient's structured response
      let userMessage = `Failed to submit scheduling request. Status code: ${response.status}.`;

      if (response.status === -1) { // Custom code for network error/no response
        userMessage = "Failed to submit scheduling request: Could not connect to the scheduling service. Please try again later.";
      } else if (response.status === -2) { // Custom code for request setup error
        userMessage = "Failed to submit scheduling request: Internal error setting up the request.";
      } else if (response.error) { // Error message provided by httpClient
        userMessage = `Failed to submit scheduling request: ${response.error}`;
      } else if (response.data) { // Fallback to data if error string is not specific
        // Try to get a more specific message if the server sent one
        const serverMessage = (response.data as any)?.message || (response.data as any)?.error;
        if (serverMessage) {
            userMessage = `Failed to submit scheduling request. Scheduler responded with status ${response.status}: ${serverMessage}`;
        } else {
            userMessage = `Failed to submit scheduling request. Scheduler responded with status ${response.status}.`;
        }
      }

      logger.error(`[submitSchedulingJobToAtomicScheduler] Error submitting job for fileKey: ${data.fileKey}. Status: ${response.status}, Error: ${response.error || 'N/A'}, Data:`, response.data);
      pendingSchedulingRequests.delete(data.fileKey);
      return {
        success: false,
        message: userMessage,
      };
    }
  } catch (error: any) {
    logger.error(`[submitSchedulingJobToAtomicScheduler] Exception during job submission for fileKey: ${data.fileKey}:`, error.stack || error);
    pendingSchedulingRequests.delete(data.fileKey);
    return {
      success: false,
      message: "An unexpected error occurred while submitting your scheduling request.",
    };
  }
}


// ----- Refactored Placeholder Skills -----

export async function createSchedulingRule(
  userId: string,
  ruleDetails: NLUCreateTimePreferenceRuleEntities,
): Promise<SchedulingResponse> {
  logger.info(`[schedulingSkills.createSchedulingRule] Called for userId: ${userId}`, ruleDetails);

  const message = `Received request to create scheduling rule for '${ruleDetails.activity_description}'. User preferences would be stored and applied to future scheduling actions. (This is a simulated storage action).`;
  logger.info(`[schedulingSkills.createSchedulingRule] ${message}`);

  return {
    success: true,
    message,
    ruleId: generateUuid(),
    details: {
      receivedUserId: userId,
      receivedRuleDetails: ruleDetails,
      action: "User preference noted for future scheduling.",
    },
  };
}

export async function blockCalendarTime(
  userId: string,
  blockDetails: NLUBlockTimeSlotEntities,
): Promise<SchedulingResponse> {
  logger.info(`[schedulingSkills.blockCalendarTime] Called for userId: ${userId}`, blockDetails);

  const hostId = userId;
  const singletonId = generateUuid();
  const eventId = generateUuid();
  const fileKey = `block_${hostId}_${singletonId}`;

  const startTimeIso = normalizeDateTime(blockDetails.date, blockDetails.start_time);
  const endTimeIso = blockDetails.end_time
                     ? normalizeDateTime(blockDetails.date, blockDetails.end_time)
                     : calculateEndTime(startTimeIso, blockDetails.duration);

  const currentUser = getCurrentUserBasic(userId);

  const eventStartDate = new Date(startTimeIso);
  const timeslots: Timeslot[] = [{
      hostId,
      dayOfWeek: eventStartDate.toLocaleString('en-US', { weekday: 'long' }).toUpperCase(),
      startTime: "00:00:00",
      endTime: "23:59:59",
      monthDay: startTimeIso.substring(5,7) + "-" + startTimeIso.substring(8,10),
      date: startTimeIso.substring(0, 10),
    }];

  const requestBody: PostTableRequestBody = {
    singletonId,
    hostId,
    timeslots,
    userList: [currentUser],
    eventParts: [{
      groupId: eventId,
      eventId: eventId,
      part: 1,
      lastPart: 1,
      startDate: startTimeIso,
      endDate: endTimeIso,
      userId: currentUser.id,
      hostId: hostId,
      user: currentUser,
      event: {
        id: eventId,
        userId: currentUser.id,
        hostId: hostId,
        eventType: "TASK",
        title: blockDetails.task_name,
        description: blockDetails.purpose,
        preferredTimeRanges: null,
      },
    }],
    fileKey,
    delay: 1000,
    callBackUrl: `${AGENT_CALLBACK_BASE_URL}/scheduler-callback`,
  };

  // logger.info(`[schedulingSkills.blockCalendarTime] Constructed PostTableRequestBody for fileKey ${fileKey}:`, JSON.stringify(requestBody, null, 2));
  const submissionResult = await submitSchedulingJobToAtomicScheduler(userId, requestBody);
  return {
      ...submissionResult,
      timeBlockId: submissionResult.success ? eventId : undefined,
      details: {
          receivedUserId: userId,
          receivedBlockDetails: blockDetails,
          // constructedBody: requestBody // Avoid logging full body in final response details for brevity
      }
  };
}

export async function initiateTeamMeetingScheduling(
  userId: string,
  meetingDetails: NLUScheduleTeamMeetingEntities,
): Promise<SchedulingResponse> {
  logger.info(`[schedulingSkills.initiateTeamMeetingScheduling] Called for userId: ${userId}`, meetingDetails);

  const hostId = userId;
  const singletonId = generateUuid();
  const eventId = generateUuid();
  const groupId = eventId;
  const fileKey = `meet_${hostId}_${singletonId}`;

  const organizerUser = getCurrentUserBasic(userId);
  const userList: User[] = [organizerUser];

  for (const attendeeIdentifier of meetingDetails.attendees) {
      if (attendeeIdentifier !== userId) {
          userList.push(getCurrentUserBasic(attendeeIdentifier));
      }
  }

  const schedulingWindowStart = normalizeDateTime(meetingDetails.time_preference_details, "00:00:00");
  let tempEndDate = new Date(schedulingWindowStart);
  tempEndDate.setDate(tempEndDate.getDate() + 7);
  const schedulingWindowEnd = tempEndDate.toISOString();

  const preferredTimeRanges: PreferredTimeRange[] = [];
  if (meetingDetails.time_preference_details?.toLowerCase().includes("afternoon")) {
      preferredTimeRanges.push({startTime: "13:00:00", endTime: "17:00:00"});
  } else if (meetingDetails.time_preference_details?.toLowerCase().includes("morning")) {
      preferredTimeRanges.push({startTime: "09:00:00", endTime: "12:00:00"});
  }

  const timeslots: Timeslot[] = [];
  let currentDayLoop = new Date(schedulingWindowStart);
  const finalDayLoop = new Date(schedulingWindowEnd);
  while(currentDayLoop <= finalDayLoop) {
      timeslots.push({
          hostId,
          dayOfWeek: currentDayLoop.toLocaleString('en-US', { weekday: 'long' }).toUpperCase(),
          startTime: "00:00:00",
          endTime: "23:59:59",
          monthDay: currentDayLoop.toISOString().substring(5,7) + "-" + currentDayLoop.toISOString().substring(8,10),
          date: currentDayLoop.toISOString().substring(0,10)
      });
      currentDayLoop.setDate(currentDayLoop.getDate() + 1);
  }

  const eventParts: EventPart[] = userList.map(user => ({
      groupId,
      eventId,
      part: 1,
      lastPart: 1,
      startDate: schedulingWindowStart,
      endDate: schedulingWindowEnd,
      userId: user.id,
      hostId: hostId,
      user: user,
      event: {
        id: eventId,
        userId: hostId,
        hostId,
        eventType: "GROUP_MEETING",
        title: meetingDetails.meeting_title || meetingDetails.purpose,
        description: meetingDetails.purpose,
        duration: meetingDetails.duration_preference ? parseInt(meetingDetails.duration_preference.split(" ")[0]) * (meetingDetails.duration_preference.includes("hour") ? 60 : 1) : 30,
        preferredTimeRanges: preferredTimeRanges.length > 0 ? preferredTimeRanges : null,
      },
  }));

  const requestBody: PostTableRequestBody = {
    singletonId,
    hostId,
    timeslots,
    userList,
    eventParts,
    fileKey,
    delay: 5000,
    callBackUrl: `${AGENT_CALLBACK_BASE_URL}/scheduler-callback`,
  };

  // logger.info(`[schedulingSkills.initiateTeamMeetingScheduling] Constructed PostTableRequestBody for fileKey ${fileKey}:`, JSON.stringify(requestBody, null, 2));
  const submissionResult = await submitSchedulingJobToAtomicScheduler(userId, requestBody);
  return {
      ...submissionResult,
      meetingRequestId: submissionResult.success ? groupId : undefined,
      details: {
          receivedUserId: userId,
          receivedMeetingDetails: meetingDetails,
          // constructedBody: requestBody
      }
  };
}

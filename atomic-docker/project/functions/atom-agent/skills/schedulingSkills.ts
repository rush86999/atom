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
  // This should combine date (e.g., "tomorrow", "2024-07-15") and time (e.g., "3pm", "15:00")
  // and return an ISO 8601 string: "YYYY-MM-DDTHH:mm:ssZ"
  // For now, if it looks like an ISO string, pass it, otherwise return a fixed future date.
  if (dateInput && dateInput.includes('T') && dateInput.endsWith('Z')) return dateInput;
  if (timeInput && timeInput.includes('T') && timeInput.endsWith('Z')) return timeInput; // if full datetime passed in timeInput

  const now = new Date();

  // Try to parse dateInput if provided (very rudimentary)
  if (dateInput) {
    if (dateInput.toLowerCase() === 'tomorrow') {
      now.setDate(now.getDate() + 1);
    } else if (dateInput.includes('-')) { // Attempt YYYY-MM-DD or MM-DD
        const parts = dateInput.split('-');
        if (parts.length === 3) { // YYYY-MM-DD
            now.setFullYear(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        } else if (parts.length === 2) { // MM-DD (assume current year)
            now.setMonth(parseInt(parts[0]) - 1, parseInt(parts[1]));
        }
    }
    // More date parsing logic for "next Monday", "June 15th" would be needed here.
  } else {
      // If no dateInput, and timeInput suggests a specific time today or it's just a duration,
      // it might default to today or require more context. For simplicity, if no date, default to tomorrow.
      if (!timeInput || !timeInput.match(/(\d+)(?::(\d+))?\s*(am|pm)?/i)) {
         now.setDate(now.getDate() + 1); // Default to tomorrow if no specific time/date info
      }
  }

  // Set default time to noon if not specified by timeInput
  now.setHours(12, 0, 0, 0);

  if (timeInput) { // Rudimentary time parsing
      const parts = timeInput.match(/(\d+)(?::(\d+))?\s*(am|pm)?/i);
      if (parts) {
          let hours = parseInt(parts[1]);
          const minutes = parts[2] ? parseInt(parts[2]) : 0;
          if (parts[3]?.toLowerCase() === 'pm' && hours < 12) hours += 12;
          if (parts[3]?.toLowerCase() === 'am' && hours === 12) hours = 0; // Midnight case
          now.setHours(hours, minutes, 0, 0); // Reset seconds and ms
      }
  }
  return now.toISOString();
}

function calculateEndTime(startTimeIso: string, durationStr?: string): string {
    // Placeholder: real implementation needs duration parsing (e.g., "1 hour", "30 minutes")
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
        } else { // Default if duration format is not recognized
             startDate.setHours(startDate.getHours() + 1);
        }
    } else { // Default duration if none provided
        startDate.setHours(startDate.getHours() + 1);
    }
    return startDate.toISOString();
}

function getCurrentUserBasic(userId: string): User {
    // Placeholder: Fetches or constructs a basic User object.
    // In a real scenario, this might fetch more details from a user profile service.
    // Also, hostId might be different from userId if the agent supports multi-tenant hosts.
    return {
        id: userId, // Assuming agent's internal userId can be used as scheduler's User ID
        hostId: userId, // Assuming hostId is same as userId for simplicity here
        workTimes: [ // Default work times, should be fetched from user's profile/preferences
            { userId, hostId: userId, dayOfWeek: "MONDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "TUESDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "WEDNESDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "THURSDAY", startTime: "09:00:00", endTime: "17:00:00" },
            { userId, hostId: userId, dayOfWeek: "FRIDAY", startTime: "09:00:00", endTime: "17:00:00" },
        ],
        maxWorkLoadPercent: 100, // example
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone, // User's local timezone
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
  singletonId?: string; // Added to align with submitSchedulingJobToAtomicScheduler return
}

// ----- Types for PostTableRequestBody -----
export interface Timeslot {
    hostId: string;
    dayOfWeek: string;
    startTime: string;
    endTime: string;
    monthDay: string; // Format --MM-DD (e.g. --07-16 for July 16th)
    date: string;     // Format YYYY-MM-DD
}

export interface WorkTime {
    userId: string;
    hostId: string;
    dayOfWeek: string;
    startTime: string; // "HH:mm:ss"
    endTime: string;   // "HH:mm:ss"
}

export interface User {
    id: string; // UUID
    hostId: string; // UUID
    workTimes: WorkTime[];
    maxWorkLoadPercent?: number;
    timeZone?: string;
    workingDays?: string[];
}

export interface PreferredTimeRange {
    eventId?: string;
    userId?: string;
    hostId?: string;
    startTime: string; // "HH:mm:ss"
    endTime: string;   // "HH:mm:ss"
    dayOfWeek?: string;
}

export interface Event {
    id: string; // UUID
    userId: string; // UUID
    hostId: string; // UUID
    eventType: "TASK" | "ONE_ON_ONE_MEETING" | "GROUP_MEETING" | "EVENT";
    duration?: number;
    minChunkTime?: number;
    maxChunkTime?: number;
    preferredTimeRanges?: PreferredTimeRange[] | null;
    deadline?: string | null; // ISO DateTime string
    priority?: number;
    title?: string;
    description?: string;
}

export interface EventPart {
    groupId: string; // UUID
    eventId: string; // UUID
    part: number;
    lastPart: number;
    startDate: string; // ISO DateTime string "YYYY-MM-DDTHH:mm:ss"
    endDate: string;   // ISO DateTime string "YYYY-MM-DDTHH:mm:ss"
    userId: string;    // UUID
    hostId: string;    // UUID
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

// ----- Conceptual Pending Request Store -----
interface PendingRequestInfo {
  userId: string;
  hostId: string;
  fileKey: string;
  submittedAt: Date;
  // originalQuery?: string;
}

const pendingSchedulingRequests = new Map<string, PendingRequestInfo>();

// ----- Conceptual HTTP Client -----
const httpClient = {
  post: async (url: string, body: any): Promise<{ status: number; data?: any; error?: string }> => {
    logger.info(`[httpClient.post] Faking HTTP POST to ${url}`);
    logger.info(`[httpClient.post] Body Summary: singletonId=${body?.singletonId}, fileKey=${body?.fileKey}, eventPartsCount=${body?.eventParts?.length}, userListCount=${body?.userList?.length}`);
    if (url.endsWith('/solve-day')) {
      return { status: 202, data: { message: "Job accepted by scheduler (simulated)" } };
    }
    return { status: 500, error: "Simulated HTTP client error for non /solve-day URL" };
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
    pendingSchedulingRequests.set(data.fileKey, {
      userId: userId,
      hostId: data.hostId,
      fileKey: data.fileKey,
      submittedAt: new Date(),
    });

    logger.info(`[submitSchedulingJobToAtomicScheduler] Sending job to scheduler: ${schedulerEndpoint}`);
    const response = await httpClient.post(schedulerEndpoint, data);

    if (response.status === 200 || response.status === 202) {
      logger.info(`[submitSchedulingJobToAtomicScheduler] Job successfully submitted to scheduler for singletonId: ${data.singletonId} (fileKey: ${data.fileKey}). Response:`, response.data);
      return {
        success: true,
        message: "Your scheduling request has been submitted. You will be notified when it's complete.",
        singletonId: data.singletonId,
      };
    } else {
      logger.error(`[submitSchedulingJobToAtomicScheduler] Error submitting job to scheduler for singletonId: ${data.singletonId} (fileKey: ${data.fileKey}). Status: ${response.status}, Error: ${response.error || JSON.stringify(response.data)}`);
      pendingSchedulingRequests.delete(data.fileKey);
      return {
        success: false,
        message: `Failed to submit scheduling request to the scheduler. Status: ${response.status}.`,
      };
    }
  } catch (error: any) {
    logger.error(`[submitSchedulingJobToAtomicScheduler] Exception while submitting job for singletonId: ${data.singletonId} (fileKey: ${data.fileKey}):`, error);
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

  // In a real implementation, this is where you would:
  // 1. Validate ruleDetails thoroughly.
  // 2. Connect to a database or user profile service.
  // 3. Store these preferences associated with the userId.
  //    - This might involve creating/updating records for preferred work times,
  //      activity-specific time preferences, etc.
  // 4. These stored preferences would then be retrieved and used when constructing
  //    the `PostTableRequestBody` for actual scheduling requests (like blockCalendarTime
  //    or initiateTeamMeetingScheduling), by influencing the `User.workTimes`,
  //    `Event.preferredTimeRanges`, or available `timeslots`.

  const message = `Received request to create scheduling rule for '${ruleDetails.activity_description}'. User preferences would be stored and applied to future scheduling actions. (This is a simulated storage action).`;
  logger.info(`[schedulingSkills.createSchedulingRule] ${message}`);

  // Simulate successful storage of preference
  // No call to submitSchedulingJobToAtomicScheduler as this intent is about *defining* preferences.
  return {
    success: true, // Indicate preference "storage" was successful
    message,
    ruleId: generateUuid(), // Provide a dummy ruleId
    details: {
      receivedUserId: userId,
      receivedRuleDetails: ruleDetails,
      action: "User preference noted for future scheduling.",
    },
  };
}

export async function blockCalendarTime(
  userId: string, // This is the agent's internal user ID
  blockDetails: NLUBlockTimeSlotEntities,
): Promise<SchedulingResponse> {
  logger.info(`[schedulingSkills.blockCalendarTime] Called for userId: ${userId}`, blockDetails);

  const hostId = userId; // Assuming agent's userId is the hostId for the scheduler
  const singletonId = generateUuid();
  const eventId = generateUuid();
  const fileKey = `block_${hostId}_${singletonId}`;

  const startTimeIso = normalizeDateTime(blockDetails.date, blockDetails.start_time);
  const endTimeIso = blockDetails.end_time
                     ? normalizeDateTime(blockDetails.date, blockDetails.end_time)
                     : calculateEndTime(startTimeIso, blockDetails.duration);

  const currentUser = getCurrentUserBasic(userId);

  // Create a minimal timeslot that covers the event.
  // A more sophisticated version would use the user's actual working hours for that day.
  const eventStartDate = new Date(startTimeIso);
  const timeslots: Timeslot[] = [{
      hostId,
      dayOfWeek: eventStartDate.toLocaleString('en-US', { weekday: 'long' }).toUpperCase(),
      startTime: "00:00:00",
      endTime: "23:59:59",
      monthDay: startTimeIso.substring(5,7) + "-" + startTimeIso.substring(8,10), // Format MM-DD from YYYY-MM-DDTHH...
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
      user: currentUser, // For scheduler to know this EventPart belongs to this user
      event: {
        id: eventId,
        userId: currentUser.id,
        hostId: hostId,
        eventType: "TASK",
        title: blockDetails.task_name, // Set title on the event
        description: blockDetails.purpose,
        preferredTimeRanges: null,
      },
    }],
    fileKey,
    delay: 1000,
    callBackUrl: `${AGENT_CALLBACK_BASE_URL}/scheduler-callback`,
  };

  logger.info(`[schedulingSkills.blockCalendarTime] Constructed PostTableRequestBody for fileKey ${fileKey}:`, JSON.stringify(requestBody, null, 2));
  const submissionResult = await submitSchedulingJobToAtomicScheduler(userId, requestBody);
  return {
      ...submissionResult, // Includes success, message, singletonId
      timeBlockId: submissionResult.success ? eventId : undefined, // Use eventId as a stand-in for timeBlockId
      details: {
          receivedUserId: userId,
          receivedBlockDetails: blockDetails,
          constructedBody: requestBody // For debugging
      }
  };
}

export async function initiateTeamMeetingScheduling(
  userId: string, // Organizer's agent internal ID
  meetingDetails: NLUScheduleTeamMeetingEntities,
): Promise<SchedulingResponse> {
  logger.info(`[schedulingSkills.initiateTeamMeetingScheduling] Called for userId: ${userId}`, meetingDetails);

  const hostId = userId;
  const singletonId = generateUuid();
  const eventId = generateUuid();
  const groupId = eventId; // For a single meeting event, groupId can be same as eventId
  const fileKey = `meet_${hostId}_${singletonId}`;

  const organizerUser = getCurrentUserBasic(userId);
  const userList: User[] = [organizerUser];

  for (const attendeeIdentifier of meetingDetails.attendees) {
      // In a real system, resolve attendeeIdentifier (email or name) to an existing User ID
      // or create a guest user representation. For now, use a placeholder.
      // Ensure not to duplicate the organizer if they are also in attendees list.
      if (attendeeIdentifier !== userId) { // Basic check to avoid duplication
          userList.push(getCurrentUserBasic(attendeeIdentifier)); // Uses identifier as ID
      }
  }

  const schedulingWindowStart = normalizeDateTime(meetingDetails.time_preference_details, "00:00:00"); // Default to start of day
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

  // Create one EventPart for each user in the meeting
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
      event: { // Shared event details for all parts of this group meeting
        id: eventId,
        userId: hostId, // Event is "owned" by the organizer
        hostId,
        eventType: "GROUP_MEETING",
        title: meetingDetails.meeting_title || meetingDetails.purpose,
        description: meetingDetails.purpose,
        duration: meetingDetails.duration_preference ? parseInt(meetingDetails.duration_preference.split(" ")[0]) * (meetingDetails.duration_preference.includes("hour") ? 60 : 1) : 30, // Basic duration parsing
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

  logger.info(`[schedulingSkills.initiateTeamMeetingScheduling] Constructed PostTableRequestBody for fileKey ${fileKey}:`, JSON.stringify(requestBody, null, 2));
  const submissionResult = await submitSchedulingJobToAtomicScheduler(userId, requestBody);
  return {
      ...submissionResult,
      meetingRequestId: submissionResult.success ? groupId : undefined, // Use groupId as a stand-in
      details: {
          receivedUserId: userId,
          receivedMeetingDetails: meetingDetails,
          constructedBody: requestBody // For debugging
      }
  };
}

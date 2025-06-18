import axios, { AxiosResponse, AxiosError } from 'axios';
import {
    parse as dateParse,
    format as dateFormat,
    addHours,
    addMinutes,
    addDays,
    nextMonday,
    nextTuesday,
    nextWednesday,
    nextThursday,
    nextFriday,
    nextSaturday,
    nextSunday,
    startOfDay,
    setHours,
    setMinutes,
    setSeconds,
    isDate as isValidDate,
    parseISO
} from 'date-fns';
import { utcToZonedTime, zonedTimeToUtc, formatInTimeZone } from 'date-fns-tz';

// Assume a default user timezone if not provided - this should ideally come from user profile
const DEFAULT_USER_TIMEZONE = 'America/New_York'; // Example, make this configurable or per-user


// Placeholder for actual logger if available, otherwise use console
const logger = {
  info: console.log,
  warn: console.warn,
  error: console.error,
};

// Configuration
const ATOMIC_SCHEDULER_API_BASE_URL = process.env.ATOMIC_SCHEDULER_API_BASE_URL || 'http://localhost:8080/api/scheduler';
const AGENT_CALLBACK_BASE_URL = process.env.AGENT_PUBLIC_BASE_URL || 'http://localhost:3000/api';

// ----- New Date/Time Helper Functions -----
interface NormalizedDateTime {
  isoDateTimeUtc?: string;    // For EventPart.startDate/endDate (UTC)
  localTime?: string;         // For Timeslot.startTime/endTime ("HH:MM:SS" in user's TZ)
  localDate?: string;         // For Timeslot.date ("YYYY-MM-DD" in user's TZ)
  localMonthDay?: string;     // For Timeslot.monthDay ("--MM-DD" in user's TZ)
  dayOfWeek?: string;         // For Timeslot.dayOfWeek (e.g., "MONDAY" in user's TZ)
}

// Helper to parse time strings like "3pm", "15:30", "10 AM"
function parseTimeStringToDate(timeString: string, referenceDate: Date, timeZone: string): Date | null {
    // referenceDate is expected to be already in the target user's timezone (e.g., startOfDay(utcToZonedTime(new Date(), timeZone)))
    let baseDate = referenceDate;

    const timeParts = timeString.match(/(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/i);
    if (!timeParts) return null;

    let hours = parseInt(timeParts[1], 10);
    const minutes = timeParts[2] ? parseInt(timeParts[2], 10) : 0;
    const ampm = timeParts[3]?.toLowerCase();

    if (isNaN(hours) || isNaN(minutes)) return null;

    if (ampm === 'pm' && hours < 12) hours += 12;
    if (ampm === 'am' && hours === 12) hours = 0; // Midnight case

    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;

    let dateWithTime = setHours(baseDate, hours);
    dateWithTime = setMinutes(dateWithTime, minutes);
    dateWithTime = setSeconds(dateWithTime, 0); // Reset seconds for consistency

    return dateWithTime; // This date is in the user's local timezone
}

// Main normalization function
function normalizeDateTime(
  dateString?: string,
  timeString?: string,
  userTimeZone: string = DEFAULT_USER_TIMEZONE,
  referenceDate: Date = new Date() // "Now" in system's local time, will be converted to user's TZ
): NormalizedDateTime {
  let targetDateInUserTz: Date;
  const nowInUserTz = utcToZonedTime(referenceDate, userTimeZone);
  let baseDateForRelative = startOfDay(nowInUserTz);

  if (dateString) {
    const lowerDateString = dateString.toLowerCase();
    if (lowerDateString === 'today') {
      targetDateInUserTz = baseDateForRelative;
    } else if (lowerDateString === 'tomorrow') {
      targetDateInUserTz = addDays(baseDateForRelative, 1);
    } else if (lowerDateString.startsWith('next ')) {
      const day = lowerDateString.split(' ')[1];
      switch (day) {
        case 'monday': targetDateInUserTz = nextMonday(baseDateForRelative); break;
        case 'tuesday': targetDateInUserTz = nextTuesday(baseDateForRelative); break;
        case 'wednesday': targetDateInUserTz = nextWednesday(baseDateForRelative); break;
        case 'thursday': targetDateInUserTz = nextThursday(baseDateForRelative); break;
        case 'friday': targetDateInUserTz = nextFriday(baseDateForRelative); break;
        case 'saturday': targetDateInUserTz = nextSaturday(baseDateForRelative); break;
        case 'sunday': targetDateInUserTz = nextSunday(baseDateForRelative); break;
        default: targetDateInUserTz = baseDateForRelative;
      }
    } else {
      let parsedDateAttempt: Date | undefined;
      try {
        // Try ISO format first (which might include time and timezone)
        const isoParsed = parseISO(dateString);
        if (isValidDate(isoParsed)) {
            parsedDateAttempt = utcToZonedTime(isoParsed, userTimeZone);
        }
      } catch {}

      if (!parsedDateAttempt || !isValidDate(parsedDateAttempt)) {
        // Try specific formats using the reference date's year/month if not fully specified
        parsedDateAttempt = dateParse(dateString, 'yyyy-MM-dd', baseDateForRelative);
         if (!isValidDate(parsedDateAttempt)) {
            // For MM-dd, we need to ensure it's for the correct year (baseDateForRelative has it)
            const tempDate = dateParse(dateString, 'MM-dd', new Date(baseDateForRelative.getFullYear(),0,1)); // Parse against start of year for month/day
            if (isValidDate(tempDate)) {
                 targetDateInUserTz = setHours(setMinutes(setSeconds(baseDateForRelative,0),tempDate.getMinutes()),tempDate.getHours());
                 targetDateInUserTz = addDays(startOfDay(targetDateInUserTz), tempDate.getDate()-1); // set day of month
                 targetDateInUserTz = addMinutes(targetDateInUserTz, tempDate.getMonth() * 31 * 24 * 60); // approximation for setMonth
                 // This is getting complicated, date-fns parse is strict.
                 // A simpler MM-dd approach:
                 const parts = dateString.match(/^(\d{2})-(\d{2})$/);
                 if (parts) {
                     parsedDateAttempt = new Date(nowInUserTz.getFullYear(), parseInt(parts[1]) -1, parseInt(parts[2]));
                 } else {
                      parsedDateAttempt = baseDateForRelative; // Fallback
                 }
            } else {
                 parsedDateAttempt = baseDateForRelative; // Fallback
            }
        }
      }
      targetDateInUserTz = parsedDateAttempt && isValidDate(parsedDateAttempt) ? parsedDateAttempt : baseDateForRelative;
      targetDateInUserTz = startOfDay(targetDateInUserTz); // Ensure we start from beginning of day before adding time
    }
  } else {
    targetDateInUserTz = baseDateForRelative;
  }

  if (timeString) {
    const parsedTimeDate = parseTimeStringToDate(timeString, targetDateInUserTz, userTimeZone);
    if (parsedTimeDate && isValidDate(parsedTimeDate)) {
      targetDateInUserTz = parsedTimeDate;
    } else {
      logger.warn(`[normalizeDateTime] Could not parse timeString: ${timeString}. Using date part or default time.`);
    }
  } else if (dateString && dateString.includes('T')) {
    // Time was already included in an ISO dateString, targetDateInUserTz should be set correctly.
  } else {
    // No time string, and dateString wasn't a full ISO with time.
    // Default to noon if no time is specified for an event, or handle as task without specific time.
    // For now, if it's still start of day, let's set a default time like 9 AM for tasks/events.
    if (targetDateInUserTz.getHours() === 0 && targetDateInUserTz.getMinutes() === 0 && targetDateInUserTz.getSeconds() === 0) {
       // targetDateInUserTz = setHours(targetDateInUserTz, 9); // Example: default to 9 AM
    }
  }

  const result: NormalizedDateTime = {};
  try {
    if (isValidDate(targetDateInUserTz)) {
        result.isoDateTimeUtc = zonedTimeToUtc(targetDateInUserTz, userTimeZone).toISOString();
        result.localTime = formatInTimeZone(targetDateInUserTz, userTimeZone, 'HH:mm:ss');
        result.localDate = formatInTimeZone(targetDateInUserTz, userTimeZone, 'yyyy-MM-dd');
        result.localMonthDay = formatInTimeZone(targetDateInUserTz, userTimeZone, 'MM-dd'); // Corrected format for --MM-DD
        result.dayOfWeek = formatInTimeZone(targetDateInUserTz, userTimeZone, 'EEEE').toUpperCase();
    } else {
        logger.warn(`[normalizeDateTime] Failed to produce a valid targetDateInUserTz for inputs: date='${dateString}', time='${timeString}'`);
    }
  } catch (tzError) {
      logger.error(`[normalizeDateTime] Error during time zone conversion or formatting: `, tzError);
  }
  return result;
}

function calculateEndTime(
  startTimeIsoUtc: string,
  durationStr?: string,
): string {
  if (!durationStr) {
    return addHours(parseISO(startTimeIsoUtc), 1).toISOString();
  }

  try {
    const baseTime = parseISO(startTimeIsoUtc);
    let endTime = baseTime;

    const durationParts = durationStr.toLowerCase().match(/(\d+)\s*(hour|minute|hr|min)/);
    if (durationParts) {
      const value = parseInt(durationParts[1], 10);
      const unit = durationParts[2];
      if (unit.startsWith('hour') || unit.startsWith('hr')) {
        endTime = addHours(baseTime, value);
      } else if (unit.startsWith('minute') || unit.startsWith('min')) {
        endTime = addMinutes(baseTime, value);
      } else {
        logger.warn(`[calculateEndTime] Unknown duration unit in: ${durationStr}. Defaulting to 1 hour.`);
        endTime = addHours(baseTime, 1);
      }
    } else {
      logger.warn(`[calculateEndTime] Could not parse duration: ${durationStr}. Defaulting to 1 hour.`);
      endTime = addHours(baseTime, 1);
    }
    return endTime.toISOString();
  } catch (error) {
    logger.error(`[calculateEndTime] Error parsing startTimeIsoUtc ('${startTimeIsoUtc}') or duration ('${durationStr}'):`, error);
    try {
        return addHours(parseISO(startTimeIsoUtc),1).toISOString();
    } catch {
        const fallbackDate = addHours(new Date(), 1);
        logger.error(`[calculateEndTime] Catastrophic fallback for end time calculation. Using current time + 1 hour.`);
        return fallbackDate.toISOString();
    }
  }
}

function getCurrentUserBasic(
  userId: string,
  hostId: string,
  // eventType?: string // Optional: context of what's being scheduled, to apply specific rules
): User {
  logger.info(`[getCurrentUserBasic] Fetching (placeholder) data for userId: ${userId}, hostId: ${hostId}`);

  // --- Placeholder for User Profile Fetching ---
  const userTimeZone = DEFAULT_USER_TIMEZONE; // Using the global default for now. Should be user-specific.

  // --- Placeholder for Stored Preference Rule Application ---
  const placeholderWorkTimes: WorkTime[] = [
    { userId, hostId, dayOfWeek: "MONDAY",    startTime: "09:00:00", endTime: "17:00:00" },
    { userId, hostId, dayOfWeek: "TUESDAY",   startTime: "09:00:00", endTime: "17:00:00" },
    { userId, hostId, dayOfWeek: "WEDNESDAY", startTime: "09:00:00", endTime: "17:00:00" },
    { userId, hostId, dayOfWeek: "THURSDAY",  startTime: "09:00:00", endTime: "17:00:00" },
    { userId, hostId, dayOfWeek: "FRIDAY",    startTime: "09:00:00", endTime: "15:00:00" }, // Example: shorter Friday
  ];
  // Simulate a "no meetings before 10am" preference if scheduling a meeting (conceptual)
  // if (eventType === "GROUP_MEETING" || eventType === "ONE_ON_ONE_MEETING") {
  //   placeholderWorkTimes = placeholderWorkTimes.map(wt => ({
  //     ...wt,
  //     startTime: wt.startTime < "10:00:00" ? "10:00:00" : wt.startTime
  //   })).filter(wt => wt.startTime < wt.endTime);
  // }

  return {
    id: userId,
    hostId: hostId,
    timeZone: userTimeZone,
    workTimes: placeholderWorkTimes,
    // maxWorkLoadPercent: 80, // Example
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
import { storePendingRequest, removePendingRequest, PendingRequestInfo } from '../sharedAgentState';

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
    try {
      const response: AxiosResponse = await axios.post(url, body, {
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: 10000,
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
          error: (axiosError.response.data as any)?.message || axiosError.message,
          headers: axiosError.response.headers,
        };
      } else if (axiosError.request) {
        logger.error(`[httpClient.post] No response received from ${url}:`, axiosError.request);
        return {
          status: -1,
          error: 'No response received from server. Network error or timeout.',
        };
      } else {
        logger.error('[httpClient.post] Error setting up request:', axiosError.message);
        return {
          status: -2,
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
    const jobInfo: PendingRequestInfo = {
      userId: userId,
      hostId: data.hostId,
      fileKey: data.fileKey,
      singletonId: data.singletonId,
      submittedAt: new Date(),
    };
    await storePendingRequest(jobInfo);

    logger.info(`[submitSchedulingJobToAtomicScheduler] Sending job to scheduler: ${schedulerEndpoint}`);
    const response = await httpClient.post(schedulerEndpoint, data);

    if (response.status === 200 || response.status === 202) {
      logger.info(`[submitSchedulingJobToAtomicScheduler] Job successfully submitted to scheduler for singletonId: ${data.singletonId} (fileKey: ${data.fileKey}). Status: ${response.status}, Response Data:`, response.data);
      return {
        success: true,
        message: "Your scheduling request has been submitted. You will be notified when it's complete.",
        singletonId: data.singletonId,
      };
    } else {
      let userMessage = `Failed to submit scheduling request. Status code: ${response.status}.`;

      if (response.status === -1) {
        userMessage = "Failed to submit scheduling request: Could not connect to the scheduling service. Please try again later.";
      } else if (response.status === -2) {
        userMessage = "Failed to submit scheduling request: Internal error setting up the request.";
      } else if (response.error) {
        userMessage = `Failed to submit scheduling request: ${response.error}`;
      } else if (response.data) {
        const serverMessage = (response.data as any)?.message || (response.data as any)?.error;
        if (serverMessage) {
            userMessage = `Failed to submit scheduling request. Scheduler responded with status ${response.status}: ${serverMessage}`;
        } else {
            userMessage = `Failed to submit scheduling request. Scheduler responded with status ${response.status}.`;
        }
      }

      logger.error(`[submitSchedulingJobToAtomicScheduler] Error submitting job for fileKey: ${data.fileKey}. Status: ${response.status}, Error: ${response.error || 'N/A'}, Data:`, response.data);
      await removePendingRequest(data.fileKey);
      return {
        success: false,
        message: userMessage,
      };
    }
  } catch (error: any) {
    logger.error(`[submitSchedulingJobToAtomicScheduler] Exception during job submission for fileKey: ${data.fileKey}:`, error.stack || error);
    await removePendingRequest(data.fileKey);
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

  const currentUser = getCurrentUserBasic(userId, hostId); // Pass hostId

  // Use the new normalizeDateTime which returns an object
  const normalizedStart = normalizeDateTime(blockDetails.date, blockDetails.start_time, currentUser.timeZone);
  let normalizedEnd: NormalizedDateTime;

  if (blockDetails.end_time) {
      normalizedEnd = normalizeDateTime(blockDetails.date, blockDetails.end_time, currentUser.timeZone);
  } else if (normalizedStart.isoDateTimeUtc) {
      const calculatedEndTimeUtc = calculateEndTime(normalizedStart.isoDateTimeUtc, blockDetails.duration);
      normalizedEnd = { isoDateTimeUtc: calculatedEndTimeUtc }; // Only UTC is strictly needed for end time calc
  } else { // Fallback if start time couldn't be normalized
      logger.error("[schedulingSkills.blockCalendarTime] Could not normalize start time, unable to proceed reliably.");
      return { success: false, message: "Error processing date/time for the time block."};
  }

  if (!normalizedStart.isoDateTimeUtc || !normalizedEnd.isoDateTimeUtc) {
    logger.error("[schedulingSkills.blockCalendarTime] Failed to get valid ISO UTC dateTimes after normalization/calculation.");
    return { success: false, message: "Error processing date/time for the time block (ISO UTC conversion failed)."};
  }

  const timeslots: Timeslot[] = [{
      hostId,
      dayOfWeek: normalizedStart.dayOfWeek || new Date(normalizedStart.isoDateTimeUtc).toLocaleString('en-US', { weekday: 'long' }).toUpperCase(),
      startTime: normalizedStart.localTime || "00:00:00",
      endTime: "23:59:59", // Broad timeslot for the day; scheduler will use eventPart start/end
      monthDay: normalizedStart.localMonthDay || normalizedStart.isoDateTimeUtc.substring(5,7) + "-" + normalizedStart.isoDateTimeUtc.substring(8,10),
      date: normalizedStart.localDate || normalizedStart.isoDateTimeUtc.substring(0, 10),
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
      startDate: normalizedStart.isoDateTimeUtc,
      endDate: normalizedEnd.isoDateTimeUtc,
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

  const submissionResult = await submitSchedulingJobToAtomicScheduler(userId, requestBody);
  return {
      ...submissionResult,
      timeBlockId: submissionResult.success ? eventId : undefined,
      details: {
          receivedUserId: userId,
          receivedBlockDetails: blockDetails,
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

  const userList: User[] = [];
  // Add organizer
  userList.push(getCurrentUserBasic(userId, hostId /*, "GROUP_MEETING" // Optional eventType context */));

  for (const attendeeIdentifier of meetingDetails.attendees) {
    // In a real system:
    // 1. Normalize attendeeIdentifier (e.g., if it's an email or name).
    // 2. Look up the internal userId and hostId for this attendee.
    // For this placeholder, assume attendeeIdentifier can be used directly as their userId and a shared/same hostId.
    const attendeeUserId = attendeeIdentifier;
    const attendeeHostId = hostId; // Assuming attendees are under the same host context for this scheduling operation

    if (attendeeUserId !== userId) { // Avoid re-adding the organizer
      logger.info(`[initiateTeamMeetingScheduling] Adding attendee: ${attendeeUserId} (placeholder resolution)`);
      userList.push(getCurrentUserBasic(attendeeUserId, attendeeHostId /*, "GROUP_MEETING" */));
    }
  }

  const organizerTimeZone = userList.find(u => u.id === userId)?.timeZone || DEFAULT_USER_TIMEZONE;

  // For scheduling window, use organizer's timezone
  const normalizedSchedulingWindowStart = normalizeDateTime(meetingDetails.time_preference_details, "00:00:00", organizerTimeZone);
  let tempEndDate = new Date(normalizedSchedulingWindowStart.isoDateTimeUtc || Date.now()); // Fallback to now if undefined
  tempEndDate.setDate(tempEndDate.getDate() + 7);
  const schedulingWindowEndIso = tempEndDate.toISOString();
  const schedulingWindowStartIso = normalizedSchedulingWindowStart.isoDateTimeUtc || new Date().toISOString();


  const preferredTimeRanges: PreferredTimeRange[] = [];
  if (meetingDetails.time_preference_details?.toLowerCase().includes("afternoon")) {
      preferredTimeRanges.push({startTime: "13:00:00", endTime: "17:00:00"});
  } else if (meetingDetails.time_preference_details?.toLowerCase().includes("morning")) {
      preferredTimeRanges.push({startTime: "09:00:00", endTime: "12:00:00"});
  }

  const timeslots: Timeslot[] = [];
  let currentDayLoop = new Date(schedulingWindowStartIso);
  const finalDayLoop = new Date(schedulingWindowEndIso);

  while(currentDayLoop <= finalDayLoop) {
      const zonedDay = utcToZonedTime(currentDayLoop, organizerTimeZone); // Use organizer's TZ for timeslot definition
      timeslots.push({
          hostId, // Timeslots are typically defined by the host/organizer
          dayOfWeek: formatInTimeZone(zonedDay, organizerTimeZone, 'EEEE').toUpperCase(),
          startTime: "00:00:00", // Broad for the day
          endTime: "23:59:59",
          monthDay: formatInTimeZone(zonedDay, organizerTimeZone, 'MM-dd'), // Corrected format
          date: formatInTimeZone(zonedDay, organizerTimeZone, 'yyyy-MM-dd')
      });
      currentDayLoop = addDays(currentDayLoop, 1);
  }

  const eventParts: EventPart[] = userList.map(user => ({
      groupId,
      eventId,
      part: 1,
      lastPart: 1,
      startDate: schedulingWindowStartIso,
      endDate: schedulingWindowEndIso,
      userId: user.id,
      hostId: user.hostId, // Use the respective user's hostId
      user: user,
      event: {
        id: eventId,
        userId: hostId, // Event is "owned" by the organizer (main userId)
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

  const submissionResult = await submitSchedulingJobToAtomicScheduler(userId, requestBody);
  return {
      ...submissionResult,
      meetingRequestId: submissionResult.success ? groupId : undefined,
      details: {
          receivedUserId: userId,
          receivedMeetingDetails: meetingDetails,
      }
  };
}

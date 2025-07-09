import {
  GetDailyPriorityBriefingNluEntities,
  DailyBriefingData,
  GetDailyPriorityBriefingSkillResponse,
  BriefingItem,
  SkillResponse, // Generic SkillResponse
  NotionTask,
  CalendarEventSummary,
  GmailMessageSnippet,
  SlackMessageSnippet,
  MSTeamsMessage,
  QueryNotionTasksParams, // For constructing parameters for task fetching
} from '../types';
import { logger } from '../../_utils/logger';
import * as calendarSkills from './calendarSkills'; // For fetching meetings
import { queryNotionTasks as queryNotionTasksBackend } from './notionAndResearchSkills'; // For querying tasks
import { ATOM_NOTION_TASKS_DATABASE_ID } from '../_libs/constants'; // For Notion Task DB ID
import * as gmailSkills from './gmailSkills'; // For fetching emails
import * as slackSkills from './slackSkills'; // For fetching Slack messages
import * as teamsSkills from './msTeamsSkills'; // For fetching MS Teams messages
// Placeholder for importing other skills that might be needed:
// import * as llmUtilities from './llmUtilities'; // For ranking urgency or summarizing

// --- Date Parsing Utility ---
interface ParsedDateContext {
  targetDate: Date;
  timeMinISO: string;
  timeMaxISO: string;
  targetDateISO: string; // YYYY-MM-DD format for the target date
  isDateRange: boolean; // Typically true for daily briefings
  status: 'parsed' | 'defaulted' | 'unparseable';
  originalInput?: string;
  warningMessage?: string;
}

function getUTCDateYYYYMMDD(date: Date): string {
  return date.toISOString().split('T')[0];
}

function getStartOfDayUTC(date: Date): Date {
  const d = new Date(date.valueOf()); // Clone to avoid modifying original
  d.setUTCHours(0, 0, 0, 0);
  return d;
}

function getEndOfDayUTC(date: Date): Date {
  const d = new Date(date.valueOf()); // Clone to avoid modifying original
  d.setUTCHours(23, 59, 59, 999);
  return d;
}

function parseDateContextLogic(
  dateContextInput?: string,
  baseDateOverride?: Date // For testing
): ParsedDateContext {
  const baseDate = baseDateOverride || new Date();
  const originalInput = dateContextInput;
  let status: ParsedDateContext['status'] = 'parsed';
  let warningMessage: string | undefined = undefined;
  let targetDate = getStartOfDayUTC(baseDate); // Default to start of baseDate (today)

  const input = (dateContextInput || 'today').toLowerCase().trim();
  let successfullyParsed = false;

  // Helper to set date components from a base and return a new Date object
  const adjustDate = (base: Date, dayAdjustment: number): Date => {
    const newDate = getStartOfDayUTC(new Date(base.valueOf())); // Start with a clean slate at UTC midnight
    newDate.setUTCDate(base.getUTCDate() + dayAdjustment);
    return newDate;
  };

  // Order of parsing: specific keywords first, then regex patterns.
  if (input === 'today') {
    targetDate = getStartOfDayUTC(baseDate);
    if (!dateContextInput) status = 'defaulted';
    successfullyParsed = true;
  } else if (input === 'tomorrow') {
    targetDate = adjustDate(baseDate, 1);
    successfullyParsed = true;
  } else if (input === 'yesterday') {
    targetDate = adjustDate(baseDate, -1);
    successfullyParsed = true;
  } else {
    // Try parsing YYYY-MM-DD
    const yyyyMmDdRegex = /^(\d{4})-(\d{2})-(\d{2})$/;
    const yyyyMmDdMatch = input.match(yyyyMmDdRegex);
    if (yyyyMmDdMatch) {
      const year = parseInt(yyyyMmDdMatch[1], 10);
      const month = parseInt(yyyyMmDdMatch[2], 10) - 1; // Month is 0-indexed
      const day = parseInt(yyyyMmDdMatch[3], 10);
      const parsed = new Date(Date.UTC(year, month, day));
      // Check if the constructed date is valid and matches the input numbers
      if (parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month && parsed.getUTCDate() === day) {
        targetDate = getStartOfDayUTC(parsed);
        successfullyParsed = true;
      } else {
        logger.warn(`[dailyBriefingSkill] Invalid YYYY-MM-DD date: ${input}`);
      }
    }

    if (!successfullyParsed) {
      const weekdayMap: { [key: string]: number } = {
        sunday: 0, monday: 1, tuesday: 2, wednesday: 3, thursday: 4, friday: 5, saturday: 6,
      };
      const relativeWeekdayRegex = /^(next|last)\s+(sunday|monday|tuesday|wednesday|thursday|friday|saturday)$/;
      const relativeMatch = input.match(relativeWeekdayRegex);

      if (relativeMatch) {
        const direction = relativeMatch[1]; // "next" or "last"
        const weekdayName = relativeMatch[2];
        const targetDayOfWeek = weekdayMap[weekdayName];

        let tempDate = getStartOfDayUTC(new Date(baseDate.valueOf()));
        const currentDayOfWeek = tempDate.getUTCDay();

        if (direction === 'next') {
          let daysToAdd = (targetDayOfWeek - currentDayOfWeek + 7) % 7;
          if (daysToAdd === 0) daysToAdd = 7; // If "next Monday" and today is Monday, go to next week's Monday
          tempDate.setUTCDate(tempDate.getUTCDate() + daysToAdd);
        } else { // "last"
          let daysToSubtract = (currentDayOfWeek - targetDayOfWeek + 7) % 7;
          if (daysToSubtract === 0) daysToSubtract = 7; // If "last Monday" and today is Monday, go to previous week's Monday
          tempDate.setUTCDate(tempDate.getUTCDate() - daysToSubtract);
        }
        targetDate = tempDate;
        successfullyParsed = true;
      }
    }
  }

  if (!successfullyParsed) {
    targetDate = getStartOfDayUTC(baseDate); // Default to today
    status = 'unparseable';
    warningMessage = `Date context "${originalInput}" is not recognized or is invalid. Defaulting to today.`;
    logger.warn(`[dailyBriefingSkill] ${warningMessage}`);
  }

  // Ensure targetDate itself is at the start of its day for consistent YYYY-MM-DD string
  targetDate = getStartOfDayUTC(targetDate); // This is crucial after any modifications

  return {
    targetDate: new Date(targetDate.valueOf()), // Return a clone
    timeMinISO: getStartOfDayUTC(targetDate).toISOString(),
    timeMaxISO: getEndOfDayUTC(targetDate).toISOString(),
    targetDateISO: getUTCDateYYYYMMDD(targetDate),
    isDateRange: true,
    status,
    originalInput,
    warningMessage,
  };
}

// --- Urgency Scoring Utility ---
function calculateUrgencyScore(item: BriefingItem, targetDate: Date, targetDateISO: string): number {
  let score = 0;
  const nowForContext = new Date(); // Used if targetDate is today, for "time until"

  switch (item.type) {
    case 'meeting':
      const meeting = item.raw_item as CalendarEventSummary;
      if (meeting && meeting.start) {
        const meetingStartDate = new Date(meeting.start);
        // Check if the meeting is on the targetDate
        if (getUTCDateYYYYMMDD(meetingStartDate) === targetDateISO) {
          score += 40; // Base score for being a meeting on the target day

          // Time proximity score: higher for earlier meetings on the targetDate
          const hoursFromStartOfDayToMeetingStart = meetingStartDate.getUTCHours() + (meetingStartDate.getUTCMinutes() / 60);
          // Ensure score is not negative if meeting is somehow before start of day (e.g. timezone issue in data)
          const timeProximityScore = Math.max(0, (24 - hoursFromStartOfDayToMeetingStart) * 2.5);
          score += Math.min(timeProximityScore, 60); // Cap at 60 for this component

          // Additional small bonus if the meeting is "upcoming" relative to 'now' (if targetDate is today)
          if (targetDateISO === getUTCDateYYYYMMDD(nowForContext) && meetingStartDate > nowForContext) {
            const hoursUntilMeeting = (meetingStartDate.getTime() - nowForContext.getTime()) / (1000 * 60 * 60);
            if (hoursUntilMeeting < 1) score += 5; // Very soon
            else if (hoursUntilMeeting < 3) score += 3; // Soon
          }
        }
      }
      break;
    case 'task':
      const task = item.raw_item as NotionTask;
      if (task) {
        const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 }; // Numerical priority
        const taskPriorityScore = (priorityOrder[task.priority || 'Low'] || 1) * 5; // Max 15 points for priority

        if (task.dueDate) {
          const dueDateISO = task.dueDate.split('T')[0]; // Ensure comparison is date-only
          if (dueDateISO < targetDateISO && task.status !== "Done" && task.status !== "Cancelled") { // Overdue
            score += 80 + taskPriorityScore;
          } else if (dueDateISO === targetDateISO && task.status !== "Done" && task.status !== "Cancelled") { // Due on targetDate
            score += 60 + taskPriorityScore;
          } else if (task.status !== "Done" && task.status !== "Cancelled") { // Not done, not cancelled, not overdue, not due today (e.g. future or no due date)
            score += 30 + taskPriorityScore; // Lower base for tasks not immediately due on targetDate
          }
        } else if (task.status !== "Done" && task.status !== "Cancelled") { // No due date, but active
          score += 30 + taskPriorityScore;
        }
      }
      break;
    case 'email':
      const email = item.raw_item as GmailMessageSnippet;
      score += 50; // Base score for being a recent, unread email for the targetDate
      if (email && email.date) {
        const emailDate = new Date(email.date);
        // If targetDate is today, and email is very recent (e.g. last few hours of 'now')
        if (targetDateISO === getUTCDateYYYYMMDD(nowForContext)) {
            const hoursAgoReceived = (nowForContext.getTime() - emailDate.getTime()) / (1000 * 60 * 60);
            if (hoursAgoReceived >= 0 && hoursAgoReceived < 4) { // Received in last 4 hours (relative to now)
                score += 5;
            }
        }
        // If targetDate is not today, this recency bonus based on 'now' is less relevant.
        // The fact it was fetched for that targetDate already implies its relevance for that day.
      }
      break;
    case 'slack_message':
      const slackMsg = item.raw_item as SlackMessageSnippet; // Or SlackMessage
      score += 45; // Base score for being a recent DM/mention on targetDate.
      if (slackMsg && slackMsg.timestamp) { // Slack 'ts' is usually a string like "1629878400.000100" or already an ISO string via our types
        // Assuming slackMsg.timestamp is an ISO string as per our SlackMessage type
        try {
            const messageDate = new Date(slackMsg.timestamp);
            if (targetDateISO === getUTCDateYYYYMMDD(nowForContext)) { // If briefing is for today
                const hoursAgoReceived = (nowForContext.getTime() - messageDate.getTime()) / (1000 * 60 * 60);
                if (hoursAgoReceived >= 0 && hoursAgoReceived < 2) { // Received in last 2 hours
                    score += 5;
                }
            }
        } catch (e) {
            logger.warn(`[calculateUrgencyScore] Could not parse Slack message timestamp: ${slackMsg.timestamp}`);
        }
      }
      break;
    case 'teams_message':
      const teamsMsg = item.raw_item as MSTeamsMessage;
      score += 45; // Base score for being a recent DM/mention on targetDate.
      if (teamsMsg && teamsMsg.createdDateTime) {
        try {
            const messageDate = new Date(teamsMsg.createdDateTime); // MS Graph uses ISO 8601
            if (targetDateISO === getUTCDateYYYYMMDD(nowForContext)) { // If briefing is for today
                const hoursAgoReceived = (nowForContext.getTime() - messageDate.getTime()) / (1000 * 60 * 60);
                if (hoursAgoReceived >= 0 && hoursAgoReceived < 2) { // Received in last 2 hours
                    score += 5;
                }
            }
        } catch (e) {
            logger.warn(`[calculateUrgencyScore] Could not parse MS Teams message createdDateTime: ${teamsMsg.createdDateTime}`);
        }
      }
      break;
    default:
      score = 20; // Default low score for unknown or other types
  }
  return Math.max(0, Math.min(Math.round(score), 100)); // Ensure score is between 0-100 and an integer
}

// Helper function to get a user-friendly date string
function getFriendlyDateString(date: Date, baseDateForComparison: Date = new Date()): string {
  const today = getStartOfDayUTC(new Date(baseDateForComparison.valueOf()));
  const tomorrow = getStartOfDayUTC(new Date(baseDateForComparison.valueOf()));
  tomorrow.setUTCDate(today.getUTCDate() + 1);
  const yesterday = getStartOfDayUTC(new Date(baseDateForComparison.valueOf()));
  yesterday.setUTCDate(today.getUTCDate() - 1);

  const target = getStartOfDayUTC(new Date(date.valueOf()));

  if (target.getTime() === today.getTime()) return "Today";
  if (target.getTime() === tomorrow.getTime()) return "Tomorrow";
  if (target.getTime() === yesterday.getTime()) return "Yesterday";

  return target.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}


/**
 * Generates a daily priority briefing for the user, consolidating information
 * from tasks, meetings, and potentially urgent messages.
 *
 * @param userId The ID of the user requesting the briefing.
 * @param nluEntities The parsed NLU entities from the GetDailyPriorityBriefing intent.
 * @returns A promise that resolves to GetDailyPriorityBriefingSkillResponse.
 */
export async function generateDailyBriefing(
  userId: string,
  nluEntities: GetDailyPriorityBriefingNluEntities,
): Promise<GetDailyPriorityBriefingSkillResponse> {
  // Use the new date parsing logic
  const parsedDateInfo = parseDateContextLogic(nluEntities.date_context);

  logger.info(`[dailyBriefingSkill] Generating daily briefing for user ${userId} for dateContext: "${nluEntities.date_context || 'today'}", resolved to: ${parsedDateInfo.targetDateISO}`);
  logger.debug(`[dailyBriefingSkill] NLU Entities: ${JSON.stringify(nluEntities)}`);
  logger.debug(`[dailyBriefingSkill] Parsed Date Info: ${JSON.stringify(parsedDateInfo)}`);

  const briefingData: DailyBriefingData = {
    briefing_date: parsedDateInfo.targetDateISO, // Use resolved date
    user_id: userId,
    priority_items: [],
    errors_encountered: [],
  };

  if (parsedDateInfo.warningMessage) {
    briefingData.errors_encountered?.push({
      source_area: 'date_parsing',
      message: parsedDateInfo.warningMessage,
      details: `Original input: ${parsedDateInfo.originalInput}`,
    });
  }

  const focusAreas = nluEntities.focus_areas || ['tasks', 'meetings', 'urgent_emails', 'urgent_slack_messages']; // Default focus areas

  try {
    // Fetch Tasks
    if (focusAreas.includes('tasks')) {
      logger.info(`[dailyBriefingSkill] Fetching tasks for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
      if (!ATOM_NOTION_TASKS_DATABASE_ID) {
        logger.error("[dailyBriefingSkill] ATOM_NOTION_TASKS_DATABASE_ID is not configured. Cannot fetch tasks.");
        briefingData.errors_encountered?.push({
          source_area: 'tasks',
          message: 'Notion tasks database ID is not configured.',
        });
      } else {
        try {
          // Define params for overdue tasks: due before targetDateISO, not Done or Cancelled
          const overdueTaskParams: QueryNotionTasksParams = {
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
            dueDateBefore: parsedDateInfo.targetDateISO,
            status_not_equals: ['Done', 'Cancelled'],
            limit: 10,
          };
          if (nluEntities.project_filter) overdueTaskParams.listName = nluEntities.project_filter;
          if (nluEntities.urgency_level && (nluEntities.urgency_level === 'high' || nluEntities.urgency_level === 'critical')) {
             overdueTaskParams.priority = nluEntities.urgency_level;
          }

          // Define params for tasks due on targetDateISO: due equals targetDateISO, not Done or Cancelled
          const dueOnTargetDateTaskParams: QueryNotionTasksParams = {
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
            dueDateEquals: parsedDateInfo.targetDateISO,
            status_not_equals: ['Done', 'Cancelled'],
            limit: 10,
          };
          if (nluEntities.project_filter) dueOnTargetDateTaskParams.listName = nluEntities.project_filter;
          if (nluEntities.urgency_level && (nluEntities.urgency_level === 'high' || nluEntities.urgency_level === 'critical')) {
            dueOnTargetDateTaskParams.priority = nluEntities.urgency_level;
          }

          const [overdueTasksResponse, dueOnTargetDateTasksResponse] = await Promise.all([
            queryNotionTasksBackend(userId, overdueTaskParams),
            queryNotionTasksBackend(userId, dueOnTargetDateTaskParams)
          ]);

          const fetchedTasks: NotionTask[] = [];
          if (overdueTasksResponse.success && overdueTasksResponse.tasks) {
            fetchedTasks.push(...overdueTasksResponse.tasks);
          } else if (!overdueTasksResponse.success) {
            logger.error(`[dailyBriefingSkill] Error fetching overdue tasks: ${overdueTasksResponse.error}`);
            briefingData.errors_encountered?.push({ source_area: 'tasks', message: `Error fetching overdue tasks (before ${parsedDateInfo.targetDateISO}): ${overdueTasksResponse.error}` });
          }

          if (dueOnTargetDateTasksResponse.success && dueOnTargetDateTasksResponse.tasks) {
            dueOnTargetDateTasksResponse.tasks.forEach(task => {
              if (!fetchedTasks.find(ft => ft.id === task.id)) {
                fetchedTasks.push(task);
              }
            });
          } else if (!dueOnTargetDateTasksResponse.success) {
            logger.error(`[dailyBriefingSkill] Error fetching tasks due on ${parsedDateInfo.targetDateISO}: ${dueOnTargetDateTasksResponse.error}`);
            briefingData.errors_encountered?.push({ source_area: 'tasks', message: `Error fetching tasks due on ${parsedDateInfo.targetDateISO}: ${dueOnTargetDateTasksResponse.error}` });
          }

          if (fetchedTasks.length > 0) {
            fetchedTasks.sort((a, b) => {
                const aIsOverdue = a.dueDate && a.dueDate < parsedDateInfo.targetDateISO;
                const bIsOverdue = b.dueDate && b.dueDate < parsedDateInfo.targetDateISO;
                if (aIsOverdue && !bIsOverdue) return -1;
                if (!aIsOverdue && bIsOverdue) return 1;

                const priorityOrder = { 'High': 1, 'Medium': 2, 'Low': 3 };
                const aPrio = priorityOrder[a.priority || 'Low'] || 3;
                const bPrio = priorityOrder[b.priority || 'Low'] || 3;
                if (aPrio !== bPrio) return aPrio - bPrio;

                const aDueDate = a.dueDate ? new Date(a.dueDate).getTime() : Infinity;
                const bDueDate = b.dueDate ? new Date(b.dueDate).getTime() : Infinity;
                return aDueDate - bDueDate;
            });

            fetchedTasks.forEach(task => {
              let details = `Status: ${task.status}`;
              if (task.dueDate) {
                const dueDate = new Date(task.dueDate);
                // Use targetDateISO for overdue comparison
                const isOverdue = dueDate.toISOString().split('T')[0] < parsedDateInfo.targetDateISO && task.status !== "Done" && task.status !== "Cancelled";
                details += `, Due: ${dueDate.toLocaleDateString([], { month: 'short', day: 'numeric', year: dueDate.getUTCFullYear() !== new Date().getUTCFullYear() ? 'numeric' : undefined })}`;
                if (isOverdue) details += " (OVERDUE)";
              } else {
                details += ", Due: N/A";
              }
              if (task.priority) details += `, Prio: ${task.priority}`;
              if (task.listName) details += `, List: ${task.listName}`;

              briefingData.priority_items.push({
                type: 'task',
                title: task.description,
                details: details,
                link: task.url,
                source_id: task.id,
                raw_item: task,
                urgency_score: calculateUrgencyScore({ type: 'task', title: task.description, raw_item: task } as BriefingItem, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
              });
            });
            logger.info(`[dailyBriefingSkill] Fetched and processed ${fetchedTasks.length} tasks.`);
          } else {
            logger.info(`[dailyBriefingSkill] No relevant tasks found for briefing.`);
          }

        } catch (e: any) {
          logger.error(`[dailyBriefingSkill] Exception during task fetching: ${e.message}`, e);
          briefingData.errors_encountered?.push({
            source_area: 'tasks',
            message: `Exception: ${e.message}`,
            details: e.stack,
          });
        }
      }
    } else {
        // Remove placeholder if tasks are not in focusAreas
        briefingData.priority_items = briefingData.priority_items.filter(item => item.type !== 'task');
    }


    // Fetch Meetings
    if (focusAreas.includes('meetings')) {
      logger.info(`[dailyBriefingSkill] Fetching meetings for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
      try {
        // Use timeMinISO and timeMaxISO from parsedDateInfo
        const eventsResponse = await calendarSkills.listUpcomingEvents(userId, 10, parsedDateInfo.timeMinISO, parsedDateInfo.timeMaxISO);

        if (eventsResponse.ok && eventsResponse.data) {
          const meetings: CalendarEventSummary[] = eventsResponse.data;
          // Make sure the date formatting for meeting details uses the targetDate, not necessarily 'today'
          const targetDateForDisplay = parsedDateInfo.targetDate;
          if (meetings.length > 0) {
            meetings.forEach(meeting => {
              const startTime = meeting.start ? new Date(meeting.start).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true }) : 'N/A';
              const endTime = meeting.end ? new Date(meeting.end).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true }) : '';

              briefingData.priority_items.push({
                type: 'meeting',
                title: meeting.summary || 'Untitled Meeting',
                details: `Time: ${startTime}${endTime ? ` - ${endTime}` : ''}`,
                link: meeting.htmlLink,
                source_id: meeting.id,
                raw_item: meeting,
                urgency_score: calculateUrgencyScore({ type: 'meeting', title: meeting.summary || 'Untitled Meeting', raw_item: meeting } as BriefingItem, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
              });
            });
            logger.info(`[dailyBriefingSkill] Fetched ${meetings.length} meetings.`);
          } else {
            logger.info(`[dailyBriefingSkill] No meetings found for ${dateContext}.`);
          }
        } else {
          logger.error(`[dailyBriefingSkill] Error fetching meetings: ${eventsResponse.error?.message}`);
          briefingData.errors_encountered?.push({
            source_area: 'meetings',
            message: eventsResponse.error?.message || 'Unknown error fetching calendar events.',
            details: JSON.stringify(eventsResponse.error?.details),
          });
        }
      } catch (e: any) {
        logger.error(`[dailyBriefingSkill] Exception during meeting fetching: ${e.message}`, e);
        briefingData.errors_encountered?.push({
          source_area: 'meetings',
          message: `Exception: ${e.message}`,
          details: e.stack,
        });
      }
    } else {
      // Remove placeholder if meetings are not in focusAreas
      briefingData.priority_items = briefingData.priority_items.filter(item => item.type !== 'meeting');
    }

    // Fetch Urgent Emails
    if (focusAreas.includes('urgent_emails')) {
      logger.info(`[dailyBriefingSkill] Fetching urgent emails for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
      try {
        const emailResponse = await gmailSkills.getRecentUnreadEmailsForBriefing(
          userId,
          parsedDateInfo.targetDate, // Pass the Date object
          3 // Fetch up to 3 emails
        );

        if (emailResponse.ok && emailResponse.data?.results) {
          const emails: GmailMessageSnippet[] = emailResponse.data.results;
          if (emails.length > 0) {
            emails.forEach(email => {
              briefingData.priority_items.push({
                type: 'email',
                title: email.subject || 'No Subject',
                details: `From: ${email.from || 'N/A'}${email.snippet ? `, Snippet: ${email.snippet.substring(0,70)}...` : ''}`,
                link: email.link,
                source_id: email.id,
                raw_item: email,
                urgency_score: calculateUrgencyScore({ type: 'email', title: email.subject || 'No Subject', raw_item: email } as BriefingItem, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
              });
            });
            logger.info(`[dailyBriefingSkill] Fetched ${emails.length} urgent/recent unread emails.`);
          } else {
            logger.info(`[dailyBriefingSkill] No urgent/recent unread emails found for ${parsedDateInfo.targetDateISO}.`);
          }
        } else {
          logger.error(`[dailyBriefingSkill] Error fetching urgent emails: ${emailResponse.error?.message}`);
          briefingData.errors_encountered?.push({
            source_area: 'emails',
            message: emailResponse.error?.message || 'Unknown error fetching urgent emails.',
            details: JSON.stringify(emailResponse.error?.details),
          });
        }
      } catch (e: any) {
        logger.error(`[dailyBriefingSkill] Exception during email fetching: ${e.message}`, e);
        briefingData.errors_encountered?.push({
          source_area: 'emails',
          message: `Exception: ${e.message}`,
          details: e.stack,
        });
      }
    }

    // Fetch Urgent Slack Messages
    if (focusAreas.includes('urgent_slack_messages')) {
      logger.info(`[dailyBriefingSkill] Fetching urgent Slack messages for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
      try {
        const slackResponse = await slackSkills.getRecentDMsAndMentionsForBriefing(
          userId, // atomUserId
          parsedDateInfo.targetDate, // targetDate
          3 // count
        );

        if (slackResponse.ok && slackResponse.data?.results) {
          const slackMessages: SlackMessageSnippet[] = slackResponse.data.results; // SlackMessage is compatible with SlackMessageSnippet for these fields
          if (slackMessages.length > 0) {
            slackMessages.forEach(msg => {
              let title = `Slack message`;
              if (msg.userName) title += ` from ${msg.userName}`;
              if (msg.channelName) title += ` in #${msg.channelName}`;
              else if (!msg.channelName && msg.userName) title += ` (DM)`; // Likely a DM if channelName is null but userName (sender) is present

              briefingData.priority_items.push({
                type: 'slack_message',
                title: title,
                details: msg.text ? msg.text.substring(0, 100) + (msg.text.length > 100 ? '...' : '') : '(No text content)',
                link: msg.permalink,
                source_id: msg.id, // 'ts' from SlackMessage
                raw_item: msg,
                urgency_score: calculateUrgencyScore({ type: 'slack_message', title: title, raw_item: msg } as BriefingItem, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
              });
            });
            logger.info(`[dailyBriefingSkill] Fetched ${slackMessages.length} urgent/recent Slack messages.`);
          } else {
            logger.info(`[dailyBriefingSkill] No urgent/recent Slack messages found for ${parsedDateInfo.targetDateISO}.`);
          }
        } else {
          logger.error(`[dailyBriefingSkill] Error fetching urgent Slack messages: ${slackResponse.error?.message}`);
          briefingData.errors_encountered?.push({
            source_area: 'slack',
            message: slackResponse.error?.message || 'Unknown error fetching urgent Slack messages.',
            details: JSON.stringify(slackResponse.error?.details),
          });
        }
      } catch (e: any) {
        logger.error(`[dailyBriefingSkill] Exception during Slack message fetching: ${e.message}`, e);
        briefingData.errors_encountered?.push({
          source_area: 'slack',
          message: `Exception: ${e.message}`,
          details: e.stack,
        });
      }
    }

    // Fetch Urgent MS Teams Messages
    if (focusAreas.includes('urgent_teams_messages')) {
      logger.info(`[dailyBriefingSkill] Fetching urgent MS Teams messages for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
      try {
        // Assuming getRecentChatsAndMentionsForBriefing exists and works similarly to Slack's
        const teamsResponse = await teamsSkills.getRecentChatsAndMentionsForBriefing(
          userId,
          parsedDateInfo.targetDate,
          3 // Fetch up to 3 messages
        );

        if (teamsResponse.ok && teamsResponse.data?.results) {
          const teamsMessages: MSTeamsMessage[] = teamsResponse.data.results;
          if (teamsMessages.length > 0) {
            teamsMessages.forEach(msg => {
              let title = `Teams message`;
              if (msg.userName) title += ` from ${msg.userName}`;
              // msg.chatId could be used to infer if it's a 1:1 or group chat if channel/team info isn't directly on msg
              // For now, keeping title simple.
              // if (msg.channelName) title += ` in ${msg.channelName}`; // MSTeamsMessage may not have channelName directly

              briefingData.priority_items.push({
                type: 'teams_message', // New BriefingItemType
                title: title,
                details: msg.content ? msg.content.substring(0, 100) + (msg.content.length > 100 ? '...' : '') : '(No text content)',
                link: msg.webUrl,
                source_id: msg.id,
                raw_item: msg,
                urgency_score: calculateUrgencyScore({ type: 'teams_message', title: title, raw_item: msg } as BriefingItem, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
              });
            });
            logger.info(`[dailyBriefingSkill] Fetched ${teamsMessages.length} urgent/recent MS Teams messages.`);
          } else {
            logger.info(`[dailyBriefingSkill] No urgent/recent MS Teams messages found for ${parsedDateInfo.targetDateISO}.`);
          }
        } else {
          logger.error(`[dailyBriefingSkill] Error fetching urgent MS Teams messages: ${teamsResponse.error?.message}`);
          briefingData.errors_encountered?.push({
            source_area: 'teams', // New source_area
            message: teamsResponse.error?.message || 'Unknown error fetching urgent MS Teams messages.',
            details: JSON.stringify(teamsResponse.error?.details),
          });
        }
      } catch (e: any) {
        logger.error(`[dailyBriefingSkill] Exception during MS Teams message fetching: ${e.message}`, e);
        briefingData.errors_encountered?.push({
          source_area: 'teams',
          message: `Exception: ${e.message}`,
          details: e.stack,
        });
      }
    }

    // Sort all collected priority_items by urgency_score (descending)
    // Secondary sort criteria:
    // - Meetings by start time (earlier first)
    // - Tasks by their inherent sort (overdue > due today > priority > due date) (already somewhat done, but explicit due date if scores equal)
    // - Emails by date (newer first)
    briefingData.priority_items.sort((a, b) => {
      const scoreDiff = (b.urgency_score || 0) - (a.urgency_score || 0);
      if (scoreDiff !== 0) {
        return scoreDiff;
      }

      // Secondary sorting if urgency scores are equal
      if (a.type === 'meeting' && b.type === 'meeting') {
        const aStart = a.raw_item?.start ? new Date(a.raw_item.start).getTime() : 0;
        const bStart = b.raw_item?.start ? new Date(b.raw_item.start).getTime() : 0;
        return aStart - bStart; // Earlier meeting first
      }
      if (a.type === 'task' && b.type === 'task') {
        // Tasks were already pre-sorted somewhat by due date and priority groups
        // Here, just ensure consistent ordering if scores are identical, e.g., by explicit due date
        const aDueDate = (a.raw_item as NotionTask)?.dueDate ? new Date((a.raw_item as NotionTask).dueDate!).getTime() : Infinity;
        const bDueDate = (b.raw_item as NotionTask)?.dueDate ? new Date((b.raw_item as NotionTask).dueDate!).getTime() : Infinity;
        if (aDueDate !== bDueDate) return aDueDate - bDueDate; // Earlier due date first
        // Could add further tie-breaking by priority if needed, though score should mostly cover it
      }
      if (a.type === 'email' && b.type === 'email') {
        const aDate = (a.raw_item as GmailMessageSnippet)?.date ? new Date((a.raw_item as GmailMessageSnippet).date!).getTime() : 0;
        const bDate = (b.raw_item as GmailMessageSnippet)?.date ? new Date((b.raw_item as GmailMessageSnippet).date!).getTime() : 0;
        return bDate - aDate; // Newer email first
      }

      // If types are different and scores are equal, maintain original relative order or define one
      // For now, if scores are equal and types differ, their relative order won't change from this sort pass.
      // A more explicit cross-type secondary sort could be: Meetings > Tasks > Emails > Slack > Teams if scores are identical.
      const typeOrder = { meeting: 1, task: 2, email: 3, slack_message: 4, teams_message: 5 };
      const aTypeOrder = typeOrder[a.type] || 99; // Items not in typeOrder go last
      const bTypeOrder = typeOrder[b.type] || 99; // Items not in typeOrder go last
      return aTypeOrder - bTypeOrder;

    });
    logger.info(`[dailyBriefingSkill] Sorted ${briefingData.priority_items.length} priority items.`);

    // Generate overall_summary_message
    // Generate overall_summary_message
    const numTasks = briefingData.priority_items.filter(item => item.type === 'task').length;
    const numMeetings = briefingData.priority_items.filter(item => item.type === 'meeting').length;
    const numEmails = briefingData.priority_items.filter(item => item.type === 'email').length;
    const numSlackMessages = briefingData.priority_items.filter(item => item.type === 'slack_message').length;
    const numTeamsMessages = briefingData.priority_items.filter(item => item.type === 'teams_message').length;

    const friendlyDateString = getFriendlyDateString(parsedDateInfo.targetDate);
    let summaryParts: string[] = [];

    // Construct message parts for each focus area
    if (focusAreas.includes('meetings')) {
      if (numMeetings > 0) {
        summaryParts.push(`${numMeetings} meeting(s) scheduled.`);
      } else {
        summaryParts.push("no meetings scheduled.");
      }
    }

    if (focusAreas.includes('tasks')) {
      if (numTasks > 0) {
        const overdueTasks = briefingData.priority_items.filter(item =>
          item.type === 'task' &&
          item.raw_item &&
          (item.raw_item as NotionTask).dueDate &&
          (item.raw_item as NotionTask).dueDate! < parsedDateInfo.targetDateISO &&
          (item.raw_item as NotionTask).status !== "Done" &&
          (item.raw_item as NotionTask).status !== "Cancelled"
        ).length;
        let taskPart = `${numTasks} task(s) require attention`;
        if (overdueTasks > 0) taskPart += ` (${overdueTasks} overdue)`;
        summaryParts.push(taskPart);
      } else {
        summaryParts.push("no pressing tasks.");
      }
    }

    if (focusAreas.includes('urgent_emails')) {
      if (numEmails > 0) {
        summaryParts.push(`${numEmails} recent unread email(s).`);
      } else {
        summaryParts.push("no recent unread emails.");
      }
    }

    if (focusAreas.includes('urgent_slack_messages')) {
      if (numSlackMessages > 0) {
        summaryParts.push(`${numSlackMessages} recent Slack message(s) (DMs/mentions).`);
      } else {
        summaryParts.push("no recent Slack DMs or mentions.");
      }
    }

    if (focusAreas.includes('urgent_teams_messages')) {
      if (numTeamsMessages > 0) {
        summaryParts.push(`${numTeamsMessages} recent MS Teams message(s) (chats/mentions).`);
      } else {
        summaryParts.push("no recent MS Teams chats or mentions.");
      }
    }

    // Assemble the final summary message
    let summaryContent = "";
    if (summaryParts.length > 0) {
      // Create a sentence from the parts
      if (summaryParts.length === 1) {
        summaryContent = `You have ${summaryParts[0]}`;
      } else {
        const lastPart = summaryParts.pop();
        summaryContent = `You have ${summaryParts.join(', ')}, and ${lastPart}`;
      }
    } else {
      summaryContent = `There are no specific items to highlight based on your requested focus areas.`;
    }

    briefingData.overall_summary_message = `Here is your briefing for ${friendlyDateString}: ${summaryContent}`;

    // Prepend date parsing warnings if any
    if (parsedDateInfo.status === 'unparseable' && parsedDateInfo.warningMessage) {
      briefingData.overall_summary_message = `${parsedDateInfo.warningMessage} ${briefingData.overall_summary_message}`;
    } else if (parsedDateInfo.status === 'defaulted' && parsedDateInfo.originalInput && parsedDateInfo.originalInput.toLowerCase().trim() !== 'today') {
      briefingData.overall_summary_message = `Showing briefing for today as date context '${parsedDateInfo.originalInput}' was processed as default. ${briefingData.overall_summary_message}`;
    }

    logger.info(`[dailyBriefingSkill] Generated summary: ${briefingData.overall_summary_message}`);

    return { ok: true, data: briefingData };

  } catch (error: any) {
    logger.error(`[dailyBriefingSkill] Error generating daily briefing: ${error.message}`, error);
    briefingData.errors_encountered?.push({
      source_area: 'overall',
      message: `Failed to generate briefing: ${error.message}`,
      details: error.stack,
    });
    return { ok: false, error: { code: "BRIEFING_GENERATION_ERROR", message: error.message }, data: briefingData };
  }
}

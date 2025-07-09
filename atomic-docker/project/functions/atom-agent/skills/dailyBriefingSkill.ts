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
// Placeholder for importing other skills that might be needed:
// import * as slackSkills from './slackSkills'; // For fetching urgent Slack messages
// import * as teamsSkills from './msTeamsSkills'; // For fetching urgent Teams messages
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

  if (input === 'today') {
    // targetDate is already set to today by default initialization
    if (!dateContextInput) status = 'defaulted'; // It was defaulted to today
  } else if (input === 'tomorrow') {
    targetDate.setUTCDate(baseDate.getUTCDate() + 1);
  } else if (input === 'yesterday') {
    targetDate.setUTCDate(baseDate.getUTCDate() - 1);
  } else {
    // Unparseable, default to today
    targetDate = getStartOfDayUTC(baseDate); // Reset to today if input was something else
    status = 'unparseable';
    warningMessage = `Date context "${originalInput}" is not recognized. Defaulting to today.`;
    logger.warn(`[dailyBriefingSkill] ${warningMessage}`);
  }

  // Ensure targetDate itself is at the start of its day for consistent YYYY-MM-DD
  targetDate = getStartOfDayUTC(targetDate);

  return {
    targetDate: new Date(targetDate.valueOf()), // Return a clone
    timeMinISO: getStartOfDayUTC(targetDate).toISOString(),
    timeMaxISO: getEndOfDayUTC(targetDate).toISOString(),
    targetDateISO: getUTCDateYYYYMMDD(targetDate),
    isDateRange: true, // For these keywords, we always mean the full day
    status,
    originalInput,
    warningMessage,
  };
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
                // TODO: urgency_score calculation
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
                // TODO: urgency_score calculation (e.g., based on proximity, attendees)
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
                // TODO: urgency_score calculation
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

    // TODO: Implement fetching for urgent_slack_messages and urgent_teams_messages similarly

    // TODO: Sort priority_items by urgency_score (descending) if urgency_score is implemented.
    // For now, items are added based on focusAreas processing order. Meetings are time-sensitive for today.

    // Generate overall_summary_message
    const numTasks = briefingData.priority_items.filter(item => item.type === 'task').length;
    const numMeetings = briefingData.priority_items.filter(item => item.type === 'meeting').length;
    const numEmails = briefingData.priority_items.filter(item => item.type === 'email').length;

    let summaryParts: string[] = [];
    if (focusAreas.includes('meetings')) {
      if (numMeetings > 0) {
        summaryParts.push(`You have ${numMeetings} meeting(s) scheduled for ${parsedDateInfo.targetDateISO === getUTCDateYYYYMMDD(new Date()) ? 'today' : `on ${parsedDateInfo.targetDateISO}`}.`);
      } else {
        summaryParts.push(`You have no meetings scheduled for ${parsedDateInfo.targetDateISO === getUTCDateYYYYMMDD(new Date()) ? 'today' : `on ${parsedDateInfo.targetDateISO}`}.`);
      }
    }

    if (focusAreas.includes('tasks')) {
      if (numTasks > 0) {
        const overdueTasks = briefingData.priority_items.filter(item =>
          item.type === 'task' &&
          item.raw_item &&
          (item.raw_item as NotionTask).dueDate &&
          (item.raw_item as NotionTask).dueDate! < parsedDateInfo.targetDateISO && // Compare with targetDateISO
          (item.raw_item as NotionTask).status !== "Done" &&
          (item.raw_item as NotionTask).status !== "Cancelled"
        ).length;

        let taskSummary = `${numTasks} task(s) require attention`;
        if (overdueTasks > 0) {
          taskSummary += ` (${overdueTasks} overdue)`;
        }
        taskSummary += ".";
        summaryParts.push(taskSummary);
      } else {
        summaryParts.push("You have no pressing tasks for this briefing.");
      }
    }

    if (focusAreas.includes('urgent_emails')) {
      if (numEmails > 0) {
        summaryParts.push(`There are ${numEmails} recent unread email(s) for you to review.`);
      } else {
        summaryParts.push("No recent unread emails to highlight.");
      }
    }

    let finalSummary = "";
    if (summaryParts.length > 0) {
      finalSummary = summaryParts.join(' ');
    } else {
      // This message is for when no items were found for the *processed* focus areas.
      // If focusAreas itself was empty or only contained unimplemented items, this might also be hit.
      finalSummary = `No specific items found for your ${parsedDateInfo.targetDateISO} briefing based on requested focus areas.`;
    }

    if (parsedDateInfo.status === 'unparseable' && parsedDateInfo.warningMessage) {
      // Prepend the date parsing warning to the summary.
      briefingData.overall_summary_message = `${parsedDateInfo.warningMessage} ${finalSummary}`;
    } else if (parsedDateInfo.status === 'defaulted' && parsedDateInfo.originalInput && parsedDateInfo.originalInput.toLowerCase().trim() !== 'today') {
      // This case covers if parseDateContextLogic defaulted to 'today' because originalInput was not 'today' but also not an error.
      // This path might not be hit if all non-"today" inputs that aren't "tomorrow"/"yesterday" become 'unparseable'.
      // Adding for completeness, in case parseDateContextLogic evolves.
      briefingData.overall_summary_message = `Showing briefing for today as date context '${parsedDateInfo.originalInput}' was processed as default. ${finalSummary}`;
    } else {
      briefingData.overall_summary_message = finalSummary;
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

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
// Placeholder for importing other skills that might be needed:
// import * as emailSkills from './emailSkills'; // For fetching urgent emails
// import * as slackSkills from './slackSkills'; // For fetching urgent Slack messages
// import * as teamsSkills from './msTeamsSkills'; // For fetching urgent Teams messages
// import * as llmUtilities from './llmUtilities'; // For ranking urgency or summarizing

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
  const dateContext = nluEntities.date_context || 'today';
  logger.info(`[dailyBriefingSkill] Generating daily briefing for user ${userId} for date: "${dateContext}"`);
  logger.debug(`[dailyBriefingSkill] NLU Entities: ${JSON.stringify(nluEntities)}`);

  const briefingData: DailyBriefingData = {
    briefing_date: new Date().toISOString().split('T')[0], // Default to today's date for now
    user_id: userId,
    priority_items: [],
    errors_encountered: [],
  };

  // TODO: Refine briefing_date based on parsed date_context from NLU

  const focusAreas = nluEntities.focus_areas || ['tasks', 'meetings', 'urgent_emails', 'urgent_slack_messages']; // Default focus areas

  try {
    // Fetch Tasks
    if (focusAreas.includes('tasks')) {
      logger.info(`[dailyBriefingSkill] Fetching tasks for briefing for dateContext: ${dateContext}.`);
      if (!ATOM_NOTION_TASKS_DATABASE_ID) {
        logger.error("[dailyBriefingSkill] ATOM_NOTION_TASKS_DATABASE_ID is not configured. Cannot fetch tasks.");
        briefingData.errors_encountered?.push({
          source_area: 'tasks',
          message: 'Notion tasks database ID is not configured.',
        });
      } else {
        try {
          const today = new Date();
          const todayISO = today.toISOString().split('T')[0];

          // Define params for overdue tasks: due before today, not Done or Cancelled
          const overdueTaskParams: QueryNotionTasksParams = {
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
            dueDateBefore: todayISO, // Due before today (exclusive of today)
            status_not_equals: ['Done', 'Cancelled'], // Using array for status_not_equals
            limit: 10, // Max 10 overdue tasks
          };
          if (nluEntities.project_filter) overdueTaskParams.listName = nluEntities.project_filter;
          if (nluEntities.urgency_level && (nluEntities.urgency_level === 'high' || nluEntities.urgency_level === 'critical')) {
             overdueTaskParams.priority = nluEntities.urgency_level;
          }


          // Define params for tasks due today: due equals today, not Done or Cancelled
          const dueTodayTaskParams: QueryNotionTasksParams = {
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
            dueDateEquals: todayISO, // Due exactly today
            status_not_equals: ['Done', 'Cancelled'],
            limit: 10, // Max 10 tasks due today
          };
          if (nluEntities.project_filter) dueTodayTaskParams.listName = nluEntities.project_filter;
          if (nluEntities.urgency_level && (nluEntities.urgency_level === 'high' || nluEntities.urgency_level === 'critical')) {
            dueTodayTaskParams.priority = nluEntities.urgency_level;
          }

          // TODO: Consider fetching tasks due "soon" (e.g., next 1-2 days) if 'today' yields few results.
          // For now, focusing on overdue and due today.

          const [overdueTasksResponse, dueTodayTasksResponse] = await Promise.all([
            queryNotionTasksBackend(userId, overdueTaskParams),
            queryNotionTasksBackend(userId, dueTodayTaskParams)
          ]);

          const fetchedTasks: NotionTask[] = [];
          if (overdueTasksResponse.success && overdueTasksResponse.tasks) {
            fetchedTasks.push(...overdueTasksResponse.tasks);
          } else if (!overdueTasksResponse.success) {
            logger.error(`[dailyBriefingSkill] Error fetching overdue tasks: ${overdueTasksResponse.error}`);
            briefingData.errors_encountered?.push({ source_area: 'tasks', message: `Error fetching overdue tasks: ${overdueTasksResponse.error}` });
          }

          if (dueTodayTasksResponse.success && dueTodayTasksResponse.tasks) {
            // Avoid duplicates if a task is somehow fetched by both queries (though unlikely with current logic)
            dueTodayTasksResponse.tasks.forEach(task => {
              if (!fetchedTasks.find(ft => ft.id === task.id)) {
                fetchedTasks.push(task);
              }
            });
          } else if (!dueTodayTasksResponse.success) {
            logger.error(`[dailyBriefingSkill] Error fetching tasks due today: ${dueTodayTasksResponse.error}`);
            briefingData.errors_encountered?.push({ source_area: 'tasks', message: `Error fetching tasks due today: ${dueTodayTasksResponse.error}` });
          }

          if (fetchedTasks.length > 0) {
            // Sort tasks: overdue first, then by priority (High > Medium > Low), then by due date (earlier first)
            fetchedTasks.sort((a, b) => {
                const aIsOverdue = a.dueDate && a.dueDate < todayISO;
                const bIsOverdue = b.dueDate && b.dueDate < todayISO;
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
                const isOverdue = dueDate.toISOString().split('T')[0] < todayISO && task.status !== "Done" && task.status !== "Cancelled";
                details += `, Due: ${dueDate.toLocaleDateString([], { month: 'short', day: 'numeric' })}`;
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
      logger.info(`[dailyBriefingSkill] Fetching meetings for briefing for dateContext: ${dateContext}.`);
      try {
        let timeMinISO: string;
        let timeMaxISO: string;

        // For simplicity, 'today' is the primary supported dateContext for now.
        // NLU should ideally parse dateContext into specific dates or ranges.
        // TODO: Robustly parse dateContext from NLU (e.g., "tomorrow", "next Monday")
        if (dateContext.toLowerCase() === 'today' || !dateContext) {
          const today = new Date();
          today.setHours(0, 0, 0, 0); // Start of today
          timeMinISO = today.toISOString();

          const endOfToday = new Date(today);
          endOfToday.setHours(23, 59, 59, 999); // End of today
          timeMaxISO = endOfToday.toISOString();

          briefingData.briefing_date = today.toISOString().split('T')[0]; // Set actual date used
        } else {
          // For other date contexts, this would need more sophisticated parsing.
          // As a fallback, if not 'today', we might not fetch meetings or log a warning.
          logger.warn(`[dailyBriefingSkill] Date context "${dateContext}" not fully supported for meeting fetching beyond 'today'. Defaulting to no specific date range for meetings.`);
          // Fallback: Fetch next few upcoming meetings without strict date range if not 'today'
          // This might require a different calendarSkills function or adjusting listUpcomingEvents.
          // For now, we'll proceed as if 'today' was requested if not explicitly 'today'.
          // This part definitely needs NLU to be more precise or this skill to parse better.
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          timeMinISO = today.toISOString();
          const endOfToday = new Date(today);
          endOfToday.setHours(23, 59, 59, 999);
          timeMaxISO = endOfToday.toISOString();
          briefingData.briefing_date = today.toISOString().split('T')[0];
        }

        // Using listUpcomingEvents from calendarSkills.ts
        // It's assumed CalendarEvent is compatible with CalendarEventSummary for the fields we use.
        const eventsResponse = await calendarSkills.listUpcomingEvents(userId, 10, timeMinISO, timeMaxISO);

        if (eventsResponse.ok && eventsResponse.data) {
          const meetings: CalendarEventSummary[] = eventsResponse.data;
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

    // Fetch Urgent Emails (Example)
    if (focusAreas.includes('urgent_emails')) {
      logger.info(`[dailyBriefingSkill] Fetching urgent emails for briefing.`);
      // const urgentEmails: GmailMessageSnippet[] = await emailSkills.getUrgentEmails(userId, dateContext, nluEntities.project_filter);
      // urgentEmails.forEach(email => {
      //   briefingData.priority_items.push({
      //     type: 'email',
      //     title: email.subject || 'No Subject',
      //     details: `From: ${email.from || 'N/A'}, Snippet: ${email.snippet?.substring(0,50)}...`,
      //     link: email.link,
      //     source_id: email.id,
      //     raw_item: email
      //     // TODO: urgency_score calculation
      //   });
      // });
      logger.warn(`[dailyBriefingSkill] Urgent email fetching not implemented; using placeholder if any.`);
    }

    // TODO: Implement fetching for urgent_slack_messages and urgent_teams_messages similarly

    // TODO: Sort priority_items by urgency_score (descending) if urgency_score is implemented.
    // For now, items are added based on focusAreas processing order. Meetings are time-sensitive for today.

    // Generate overall_summary_message
    const numTasks = briefingData.priority_items.filter(item => item.type === 'task').length;
    const numMeetings = briefingData.priority_items.filter(item => item.type === 'meeting').length;

    let summaryParts: string[] = [];
    if (numMeetings > 0) {
      summaryParts.push(`You have ${numMeetings} meeting(s) scheduled for today.`);
    } else if (focusAreas.includes('meetings')) {
      summaryParts.push("You have no meetings scheduled for today.");
    }

    if (numTasks > 0) {
      const overdueTasks = briefingData.priority_items.filter(item =>
        item.type === 'task' &&
        item.raw_item &&
        (item.raw_item as NotionTask).dueDate &&
        (item.raw_item as NotionTask).dueDate! < briefingData.briefing_date &&
        (item.raw_item as NotionTask).status !== "Done" &&
        (item.raw_item as NotionTask).status !== "Cancelled"
      ).length;

      let taskSummary = `You have ${numTasks} task(s) on your list`;
      if (overdueTasks > 0) {
        taskSummary += `, with ${overdueTasks} overdue`;
      }
      taskSummary += ".";
      summaryParts.push(taskSummary);
    } else if (focusAreas.includes('tasks')) {
      summaryParts.push("You have no relevant tasks for today's briefing.");
    }

    if (summaryParts.length > 0) {
      briefingData.overall_summary_message = summaryParts.join(' ');
    } else {
      briefingData.overall_summary_message = "No specific items for your briefing today based on current focus areas.";
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

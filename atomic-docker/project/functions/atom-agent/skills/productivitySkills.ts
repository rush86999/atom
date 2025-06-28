// In atomic-docker/project/functions/atom-agent/skills/productivitySkills.ts
import {
  CalendarEvent,
  PrepareForMeetingResponse,
  MeetingPreparationData,
  NotionPageContext,
  EmailContext,
  TaskContext,
  Email, // Assuming Email type is defined for results from emailSkills
  NotionTask, // Assuming NotionTask type is defined for results from notionAndResearchSkills
  NotionSearchResultData, // Assuming this is what searchNotionRaw might return items as
  SkillResponse, // Generic skill response
} from '../../types'; // Adjust path as needed
import { listUpcomingEvents } from './calendarSkills';
import { queryNotionTasks, searchNotionRaw } from './notionAndResearchSkills'; // Assuming searchNotionRaw or similar exists
import { searchEmailsNLU } from './emailSkills'; // Assuming searchEmailsNLU for targeted search; or use listRecentEmails with manual filtering
// import { getCurrentUserId } from '../handler'; // Not needed if userId is passed directly

const MAX_RESULTS_PER_CONTEXT = 3; // Max Notion pages, emails, tasks to show
const EMAIL_SEARCH_DAYS_PRIOR = 7; // How many days back to search for emails

// Helper to find the target meeting
async function findTargetMeeting(
  userId: string,
  meetingIdentifier?: string,
  meetingDateTime?: string // This could be a specific ISO string or a relative term like "tomorrow" handled by NLU/calendarSkill
): Promise<CalendarEvent | null> {
  // For simplicity, listUpcomingEvents might need to be enhanced or NLU should resolve meetingDateTime to a specific range
  // For now, we assume listUpcomingEvents can take a start/end range or the NLU provides one.
  // If meetingDateTime is a relative term, it should ideally be resolved to specific dates before this function.
  // If meetingIdentifier is "next meeting", we take the first one.
  // A more robust solution would involve better NLU parsing for date ranges and meeting name matching.

  const events = await listUpcomingEvents(userId, 20); // Fetch more events to allow better filtering
  if (!events || events.length === 0) {
    return null;
  }

  let filteredEvents = events;

  // Basic date filtering (example, needs robust date parsing for terms like "tomorrow")
  if (meetingDateTime) {
    // This is a placeholder. Real date parsing is complex.
    // NLU should ideally provide a date range for meetingDateTime.
    // For example, if meetingDateTime is "tomorrow", it resolves to tomorrow's date.
    // const targetDate = new Date(meetingDateTime); // This is too naive for "tomorrow"
    // filteredEvents = filteredEvents.filter(e => new Date(e.startTime).toDateString() === targetDate.toDateString());
    console.warn(`[findTargetMeeting] Date/time based filtering for "${meetingDateTime}" is not fully implemented here. Relies on NLU or specific date.`)
  }

  if (meetingIdentifier && meetingIdentifier.toLowerCase() !== 'next meeting' && meetingIdentifier.toLowerCase() !== 'my next meeting') {
    filteredEvents = filteredEvents.filter(e =>
      e.summary.toLowerCase().includes(meetingIdentifier.toLowerCase()) ||
      (e.attendees && e.attendees.some(a => a.email?.toLowerCase().includes(meetingIdentifier.toLowerCase()) || a.displayName?.toLowerCase().includes(meetingIdentifier.toLowerCase())))
    );
  }

  if (filteredEvents.length === 0) {
    return null;
  }

  // Sort by start time to get the "next" one if multiple match or if "next meeting" was specified
  return filteredEvents.sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime())[0];
}


export async function handlePrepareForMeeting(
  userId: string,
  meetingIdentifier?: string,
  meetingDateTime?: string
): Promise<PrepareForMeetingResponse> {
  console.log(`[handlePrepareForMeeting] User: ${userId}, Meeting ID: "${meetingIdentifier}", DateTime: "${meetingDateTime}"`);
  const targetMeeting = await findTargetMeeting(userId, meetingIdentifier, meetingDateTime);

  if (!targetMeeting) {
    console.log(`[handlePrepareForMeeting] No target meeting found.`);
    return {
      ok: false,
      error: { code: "MEETING_NOT_FOUND", message: "Could not find the specified meeting." },
    };
  }
  console.log(`[handlePrepareForMeeting] Target meeting found: "${targetMeeting.summary}" at ${targetMeeting.startTime}`);

  const preparationData: MeetingPreparationData = { targetMeeting };
  let accumulatedErrorMessages = "";

  const meetingKeywordsArray = [targetMeeting.summary];
  if (targetMeeting.description) {
    meetingKeywordsArray.push(...targetMeeting.description.split(' ').slice(0, 10)); // Add some keywords from description
  }
  targetMeeting.attendees?.forEach(attendee => {
    if (attendee.displayName) meetingKeywordsArray.push(attendee.displayName);
    // if (attendee.email) meetingKeywordsArray.push(attendee.email.split('@')[0]); // Add username part of email
  });
  const meetingKeywords = meetingKeywordsArray.join(' '); // Create a keyword string for searches

  // 1. Gather Notion Context
  try {
    // searchNotionRaw is expected to be a function that takes a user ID and a query string.
    // The actual implementation of searchNotionRaw might involve calling a Python service.
    const notionQuery = `content related to: ${targetMeeting.summary}`; // Simple query
    console.log(`[handlePrepareForMeeting] Querying Notion with: "${notionQuery}"`);
    const notionSearchResponse = await searchNotionRaw(userId, notionQuery, MAX_RESULTS_PER_CONTEXT);

    // Assuming searchNotionRaw returns a structure like: PythonApiResponse<NotionSearchResultData[]>
    if (notionSearchResponse && notionSearchResponse.ok && notionSearchResponse.data) {
      preparationData.relatedNotionPages = notionSearchResponse.data.map((p: NotionSearchResultData) => ({
        id: p.id,
        title: p.title || p.properties?.title?.title?.[0]?.plain_text || 'Untitled Notion Page',
        url: p.url || (p.properties?.URL?.url),
        briefSnippet: p.content_preview || p.content?.substring(0, 150) || (p.properties?.Description?.rich_text?.[0]?.plain_text.substring(0,150)),
      })).slice(0, MAX_RESULTS_PER_CONTEXT);
      console.log(`[handlePrepareForMeeting] Found ${preparationData.relatedNotionPages?.length || 0} Notion pages.`);
    } else if (notionSearchResponse && !notionSearchResponse.ok) {
        console.warn(`[handlePrepareForMeeting] Notion search failed: ${notionSearchResponse.error?.message}`);
        accumulatedErrorMessages += `Could not fetch Notion documents: ${notionSearchResponse.error?.message}. `;
    } else {
        console.log(`[handlePrepareForMeeting] No Notion pages found or unexpected response format from searchNotionRaw.`);
    }
  } catch (e: any) {
    console.error('[handlePrepareForMeeting] Error fetching Notion context:', e.message, e.stack);
    accumulatedErrorMessages += 'Error occurred while fetching Notion documents. ';
  }

  // 2. Gather Email Context
  try {
    const toDate = new Date();
    const fromDate = new Date();
    fromDate.setDate(toDate.getDate() - EMAIL_SEARCH_DAYS_PRIOR);

    // Construct a query for searchEmailsNLU. This may need refinement based on NLU capabilities.
    // For now, make it somewhat structured if searchEmailsNLU is a passthrough to an API.
    let emailQueryParts = [`about "${targetMeeting.summary}"`];
    if (targetMeeting.attendees && targetMeeting.attendees.length > 0) {
      const attendeeEmails = targetMeeting.attendees.map(a => a.email).filter(Boolean).join(' OR ');
      if (attendeeEmails) {
        emailQueryParts.push(`with attendees (${attendeeEmails})`);
      }
    }
    emailQueryParts.push(`between ${fromDate.toISOString().split('T')[0]} and ${toDate.toISOString().split('T')[0]}`);
    const emailQuery = emailQueryParts.join(' ');

    console.log(`[handlePrepareForMeeting] Querying Emails with: "${emailQuery}"`);
    // searchEmailsNLU should ideally handle parsing this query or accept structured input.
    const emailsResponse: SkillResponse<Email[]> = await searchEmailsNLU(userId, emailQuery, MAX_RESULTS_PER_CONTEXT);

    if (emailsResponse && emailsResponse.ok && emailsResponse.data) {
      preparationData.relatedEmails = emailsResponse.data.map((email: Email) => ({
        id: email.id,
        subject: email.subject,
        sender: email.sender,
        receivedDate: email.timestamp, // Assuming Email.timestamp is ISO string
        // url: email.webLink, // If available on your Email type
        briefSnippet: email.body?.substring(0, 150) + (email.body && email.body.length > 150 ? '...' : ''),
      })).slice(0, MAX_RESULTS_PER_CONTEXT);
      console.log(`[handlePrepareForMeeting] Found ${preparationData.relatedEmails?.length || 0} emails.`);
    } else if (emailsResponse && !emailsResponse.ok) {
        console.warn(`[handlePrepareForMeeting] Email search failed: ${emailsResponse.error?.message}`);
        accumulatedErrorMessages += `Could not fetch relevant emails: ${emailsResponse.error?.message}. `;
    } else {
        console.log(`[handlePrepareForMeeting] No emails found or unexpected response format from email search.`);
    }
  } catch (e: any) {
    console.error('[handlePrepareForMeeting] Error fetching Email context:', e.message, e.stack);
    accumulatedErrorMessages += 'Error occurred while fetching relevant emails. ';
  }

  // 3. Gather Task Context
  try {
    const notionTasksDbId = process.env.ATOM_NOTION_TASKS_DATABASE_ID;
    if (!notionTasksDbId) {
        console.warn('[handlePrepareForMeeting] ATOM_NOTION_TASKS_DATABASE_ID is not set. Skipping task search.');
        accumulatedErrorMessages += 'Notion tasks database ID not configured. ';
    } else {
        const taskQueryParams = {
            descriptionContains: targetMeeting.summary, // Basic search
            status_not_equals: 'Done' as any, // Assuming 'Done' is a status to exclude
            limit: MAX_RESULTS_PER_CONTEXT,
            notionTasksDbId: notionTasksDbId,
        };
        console.log(`[handlePrepareForMeeting] Querying Tasks with params:`, taskQueryParams);
        const tasksResponse = await queryNotionTasks(userId, taskQueryParams); // queryNotionTasks from notionAndResearchSkills

        if (tasksResponse.success && tasksResponse.tasks) {
            preparationData.relatedTasks = tasksResponse.tasks.map((task: NotionTask) => ({
                id: task.id,
                description: task.description,
                dueDate: task.dueDate,
                status: task.status,
                url: task.url,
            })).slice(0, MAX_RESULTS_PER_CONTEXT);
            console.log(`[handlePrepareForMeeting] Found ${preparationData.relatedTasks?.length || 0} tasks.`);
        } else if (!tasksResponse.success) {
            console.warn(`[handlePrepareForMeeting] Task query failed: ${tasksResponse.error}`);
            accumulatedErrorMessages += `Could not fetch related tasks: ${tasksResponse.error}. `;
        } else {
             console.log(`[handlePrepareForMeeting] No tasks found or unexpected response from task query.`);
        }
    }
  } catch (e: any) {
    console.error('[handlePrepareForMeeting] Error fetching Task context:', e.message, e.stack);
    accumulatedErrorMessages += 'Error occurred while fetching related tasks. ';
  }

  // 4. (Stretch Goal) Key points from last meeting - Placeholder for V1
  // preparationData.keyPointsFromLastMeeting = "Example: Decision X was made, Action Item Y was assigned.";

  if (accumulatedErrorMessages) {
      preparationData.errorMessage = accumulatedErrorMessages.trim();
  }

  console.log(`[handlePrepareForMeeting] Preparation data compiled:`, JSON.stringify(preparationData).substring(0,500) + "...");

  return {
    ok: true,
    data: preparationData,
  };
}

// --- Automated Weekly Digest Skill ---

interface DateRange {
  startDate: Date;
  endDate: Date;
  nextPeriodStartDate: Date;
  nextPeriodEndDate: Date;
  displayRange: string; // For user-facing messages e.g., "This Week (Mon, Jul 22 - Fri, Jul 26)"
}

/**
 * Determines the date ranges for the current/past week and the upcoming week.
 * @param timePeriod Optional string like "this week" or "last week". Defaults to "this week".
 * @returns Object containing startDate, endDate, nextPeriodStartDate, nextPeriodEndDate, and displayRange.
 */
export function determineDateRange(timePeriod?: "this week" | "last week" | string): DateRange {
  const now = new Date();
  let today = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // Normalize to start of today

  let startDate: Date;
  let endDate: Date;
  let displayRangeLabel: string;

  if (timePeriod === "last week") {
    displayRangeLabel = "Last Week";
    const dayOfWeek = today.getDay(); // 0 (Sun) - 6 (Sat)
    // Last week's Monday
    startDate = new Date(today.setDate(today.getDate() - dayOfWeek - 6));
    // Last week's Sunday
    endDate = new Date(new Date(startDate).setDate(startDate.getDate() + 6));
    endDate.setHours(23, 59, 59, 999); // End of Sunday
  } else { // Default to "this week"
    displayRangeLabel = "This Week";
    const dayOfWeek = today.getDay(); // 0 (Sun) - 6 (Sat)
    // This week's Monday (if today is Sunday, dayOfWeek is 0, so it goes to last Monday)
    startDate = new Date(today.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1) ));
    // Today, or this week's Friday if today is Sat/Sun (for a Mon-Fri digest view)
    // For a full Mon-Sun view, endDate would just be `new Date(new Date(startDate).setDate(startDate.getDate() + 6))`
    // Let's make "this week" end on the current day for ongoing digest, or end of Friday if past Friday.
    endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // End of current day for "this week"
    if (endDate.getDay() > 5 || (endDate.getDay() === 5 && now.getHours() >=17 )) { // If past Friday 5PM or weekend
        // Show Mon-Fri of current week
        endDate = new Date(new Date(startDate).setDate(startDate.getDate() + 4));
    }
    endDate.setHours(23, 59, 59, 999);
  }

  // Format displayRange for user
  const

options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
  const displayStartDate = startDate.toLocaleDateString('en-US', options);
  const displayEndDate = endDate.toLocaleDateString('en-US', options);
  const displayRange = `${displayRangeLabel} (${displayStartDate} - ${displayEndDate})`;


  // Next Period (e.g., next 7 days from the day after current endDate, or next Mon-Fri)
  const nextPeriodStartDate = new Date(endDate);
  nextPeriodStartDate.setDate(endDate.getDate() + 1); // Start from the day after current period ends
  nextPeriodStartDate.setHours(0,0,0,0); // Start of that day

  const nextPeriodEndDate = new Date(nextPeriodStartDate);
  nextPeriodEndDate.setDate(nextPeriodStartDate.getDate() + 6); // Default to a 7-day outlook
  nextPeriodEndDate.setHours(23,59,59,999);


  return { startDate, endDate, nextPeriodStartDate, nextPeriodEndDate, displayRange };
}


import {
  WeeklyDigestData,
  GenerateWeeklyDigestResponse,
  NotionTaskStatus // Already imported
} from '../../types';


const MAX_DIGEST_ITEMS = 5; // Max items for completed tasks, meetings, etc.

export async function handleGenerateWeeklyDigest(
  userId: string,
  timePeriodInput?: "this week" | "last week" | string
): Promise<GenerateWeeklyDigestResponse> {
  console.log(`[handleGenerateWeeklyDigest] User: ${userId}, Time Period: "${timePeriodInput}"`);

  const { startDate, endDate, nextPeriodStartDate, nextPeriodEndDate, displayRange } = determineDateRange(timePeriodInput);
  console.log(`[handleGenerateWeeklyDigest] Determined date range: ${startDate.toISOString()} to ${endDate.toISOString()}`);
  console.log(`[handleGenerateWeeklyDigest] Next period range: ${nextPeriodStartDate.toISOString()} to ${nextPeriodEndDate.toISOString()}`);


  const digestData: WeeklyDigestData = {
    periodStart: startDate.toISOString(),
    periodEnd: endDate.toISOString(),
    completedTasks: [],
    attendedMeetings: [],
    upcomingCriticalTasks: [],
    upcomingCriticalMeetings: [],
  };
  let accumulatedErrorMessages = "";

  const notionTasksDbId = process.env.ATOM_NOTION_TASKS_DATABASE_ID;

  // 1. Gather Completed Tasks
  if (!notionTasksDbId) {
    console.warn('[handleGenerateWeeklyDigest] ATOM_NOTION_TASKS_DATABASE_ID is not set. Skipping completed task search.');
    accumulatedErrorMessages += 'Notion tasks database ID not configured for completed tasks. ';
  } else {
    try {
      const completedTaskParams = {
        // This is tricky: Notion API doesn't easily filter by "completion date" directly.
        // We might need to fetch tasks last_edited within the range and then filter by status.
        // Or, if users have a "Completed Date" property, filter on that.
        // For V1, let's try filtering by last_edited_time and status "Done".
        // This is an approximation.
        status: "Done" as NotionTaskStatus,
        // To filter by date, queryNotionTasks might need to be enhanced or we filter locally.
        // For now, let's assume queryNotionTasks can take a date range for last_edited_time
        // or we fetch more and filter.
        // Let's simplify: get tasks marked Done and edited recently (e.g. last 2 weeks to catch late markings)
        // then filter locally by a "Completed At" custom property if it exists, or by last_edited_time.
        // This part requires more robust date handling in queryNotionTasks or post-filtering.
        limit: MAX_DIGEST_ITEMS * 2, // Fetch more to filter by date locally
        notionTasksDbId: notionTasksDbId,
      };
      console.log(`[handleGenerateWeeklyDigest] Querying completed tasks with params:`, completedTaskParams);
      const taskResponse = await queryNotionTasks(userId, completedTaskParams);
      if (taskResponse.success && taskResponse.tasks) {
        // Placeholder for date filtering:
        // This assumes tasks have a `completedAt` or similar custom field, or uses `lastEditedTime`
        // For a true digest, we need tasks *completed* in the window.
        // This is a simplification and might need a dedicated "Completed Date" field in Notion.
        digestData.completedTasks = taskResponse.tasks.filter(task => {
            const lastEdited = new Date(task.last_edited_time || task.createdDate); // NotionTask needs last_edited_time
            return lastEdited >= startDate && lastEdited <= endDate;
        }).slice(0, MAX_DIGEST_ITEMS);
        console.log(`[handleGenerateWeeklyDigest] Found ${digestData.completedTasks.length} completed tasks in period.`);
      } else if (!taskResponse.success) {
        accumulatedErrorMessages += `Could not fetch completed tasks: ${taskResponse.error}. `;
      }
    } catch (e: any) {
      console.error('[handleGenerateWeeklyDigest] Error fetching completed tasks:', e.message, e.stack);
      accumulatedErrorMessages += 'Error occurred while fetching completed tasks. ';
    }
  }

  // 2. Gather Key Meetings Attended
  try {
    // listUpcomingEvents needs to be adapted to query past events for a date range.
    // This might mean adding startDate and endDate parameters to listUpcomingEvents.
    // For now, assume it can take a date range (conceptual).
    // listUpcomingEvents(userId, limit, timeMin, timeMax)
    const meetingsAttended = await listUpcomingEvents(userId, MAX_DIGEST_ITEMS * 2, startDate.toISOString(), endDate.toISOString());
    if (meetingsAttended) {
        // Further filter for "significant" meetings if needed (e.g., duration > 30min, not "Focus Time")
        digestData.attendedMeetings = meetingsAttended.filter(event => {
            const durationMs = new Date(event.endTime).getTime() - new Date(event.startTime).getTime();
            const durationMinutes = durationMs / (1000 * 60);
            return durationMinutes > 25 && !event.summary.toLowerCase().includes("focus time"); // Example filter
        }).slice(0, MAX_DIGEST_ITEMS);
      console.log(`[handleGenerateWeeklyDigest] Found ${digestData.attendedMeetings.length} attended meetings.`);
    }
  } catch (e: any) {
    console.error('[handleGenerateWeeklyDigest] Error fetching attended meetings:', e.message, e.stack);
    accumulatedErrorMessages += 'Error occurred while fetching attended meetings. ';
  }

  // 3. Identify Upcoming Critical Tasks
  if (!notionTasksDbId) {
    console.warn('[handleGenerateWeeklyDigest] ATOM_NOTION_TASKS_DATABASE_ID is not set. Skipping upcoming task search.');
    accumulatedErrorMessages += 'Notion tasks database ID not configured for upcoming tasks. ';
  } else {
    try {
      const upcomingTaskParams = {
        // Query tasks due in the next period
        dueDateAfter: nextPeriodStartDate.toISOString().split('T')[0], // YYYY-MM-DD
        dueDateBefore: nextPeriodEndDate.toISOString().split('T')[0],   // YYYY-MM-DD
        priority: "High" as NotionTaskPriority, // Example: only high priority
        status_not_equals: ["Done", "Cancelled"] as any, // Exclude completed/cancelled
        limit: MAX_DIGEST_ITEMS,
        notionTasksDbId: notionTasksDbId,
      };
      console.log(`[handleGenerateWeeklyDigest] Querying upcoming critical tasks with params:`, upcomingTaskParams);
      const upcomingTaskResponse = await queryNotionTasks(userId, upcomingTaskParams);
      if (upcomingTaskResponse.success && upcomingTaskResponse.tasks) {
        digestData.upcomingCriticalTasks = upcomingTaskResponse.tasks.slice(0, MAX_DIGEST_ITEMS);
        console.log(`[handleGenerateWeeklyDigest] Found ${digestData.upcomingCriticalTasks.length} upcoming critical tasks.`);
      } else if (!upcomingTaskResponse.success) {
        accumulatedErrorMessages += `Could not fetch upcoming tasks: ${upcomingTaskResponse.error}. `;
      }
    } catch (e: any) {
      console.error('[handleGenerateWeeklyDigest] Error fetching upcoming tasks:', e.message, e.stack);
      accumulatedErrorMessages += 'Error occurred while fetching upcoming tasks. ';
    }
  }

  // 4. Identify Upcoming Critical Meetings
  try {
    // listUpcomingEvents for the next period
    const upcomingMeetings = await listUpcomingEvents(userId, MAX_DIGEST_ITEMS * 2, nextPeriodStartDate.toISOString(), nextPeriodEndDate.toISOString());
    if (upcomingMeetings) {
        // Filter for "significant" meetings
        digestData.upcomingCriticalMeetings = upcomingMeetings.filter(event => {
            const durationMs = new Date(event.endTime).getTime() - new Date(event.startTime).getTime();
            const durationMinutes = durationMs / (1000 * 60);
            // Example: duration > 45 min OR has external attendees (if attendee data is rich enough)
            return durationMinutes > 45 || (event.attendees && event.attendees.some(a => a.email && !a.email.endsWith('@yourcompany.com')));
        }).slice(0, MAX_DIGEST_ITEMS);
      console.log(`[handleGenerateWeeklyDigest] Found ${digestData.upcomingCriticalMeetings.length} upcoming critical meetings.`);
    }
  } catch (e: any) {
    console.error('[handleGenerateWeeklyDigest] Error fetching upcoming meetings:', e.message, e.stack);
    accumulatedErrorMessages += 'Error occurred while fetching upcoming meetings. ';
  }

  if (accumulatedErrorMessages) {
    digestData.errorMessage = accumulatedErrorMessages.trim();
  }

  // Construct formatted summary (moved to handler.ts for final presentation)
  // This skill will primarily return the data. The handler formats it.
  const formattedSummary = `Digest for ${displayRange} (data prepared, formatting in handler).`; // Placeholder

  return {
    ok: true,
    data: {
      digest: digestData,
      formattedSummary, // This will be properly built in handler.ts
    },
  };
}

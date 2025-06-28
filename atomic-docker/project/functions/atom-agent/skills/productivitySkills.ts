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

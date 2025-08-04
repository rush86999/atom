import { listUpcomingEvents } from './calendarSkills';
import { queryNotionTasks, searchNotionRaw } from './notionAndResearchSkills'; // Assuming searchNotionRaw or similar exists
import { searchEmailsNLU } from './emailSkills'; // Assuming searchEmailsNLU for targeted search; or use listRecentEmails with manual filtering
// import { getCurrentUserId } from '../handler'; // Not needed if userId is passed directly
const MAX_RESULTS_PER_CONTEXT = 3; // Max Notion pages, emails, tasks to show
const EMAIL_SEARCH_DAYS_PRIOR = 7; // How many days back to search for emails
// Helper to find the target meeting
async function findTargetMeeting(userId, meetingIdentifier, meetingDateTime // This could be a specific ISO string or a relative term like "tomorrow" handled by NLU/calendarSkill
) {
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
        console.warn(`[findTargetMeeting] Date/time based filtering for "${meetingDateTime}" is not fully implemented here. Relies on NLU or specific date.`);
    }
    if (meetingIdentifier &&
        meetingIdentifier.toLowerCase() !== 'next meeting' &&
        meetingIdentifier.toLowerCase() !== 'my next meeting') {
        filteredEvents = filteredEvents.filter((e) => e.summary.toLowerCase().includes(meetingIdentifier.toLowerCase()) ||
            (e.attendees &&
                e.attendees.some((a) => a.email
                    ?.toLowerCase()
                    .includes(meetingIdentifier.toLowerCase()) ||
                    a.displayName
                        ?.toLowerCase()
                        .includes(meetingIdentifier.toLowerCase()))));
    }
    if (filteredEvents.length === 0) {
        return null;
    }
    // Sort by start time to get the "next" one if multiple match or if "next meeting" was specified
    return filteredEvents.sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime())[0];
}
export async function handlePrepareForMeeting(userId, meetingIdentifier, meetingDateTime) {
    console.log(`[handlePrepareForMeeting] User: ${userId}, Meeting ID: "${meetingIdentifier}", DateTime: "${meetingDateTime}"`);
    const targetMeeting = await findTargetMeeting(userId, meetingIdentifier, meetingDateTime);
    if (!targetMeeting) {
        console.log(`[handlePrepareForMeeting] No target meeting found.`);
        return {
            ok: false,
            error: {
                code: 'MEETING_NOT_FOUND',
                message: 'Could not find the specified meeting.',
            },
        };
    }
    console.log(`[handlePrepareForMeeting] Target meeting found: "${targetMeeting.summary}" at ${targetMeeting.startTime}`);
    const preparationData = { targetMeeting };
    let accumulatedErrorMessages = '';
    const meetingKeywordsArray = [targetMeeting.summary];
    if (targetMeeting.description) {
        meetingKeywordsArray.push(...targetMeeting.description.split(' ').slice(0, 10)); // Add some keywords from description
    }
    targetMeeting.attendees?.forEach((attendee) => {
        if (attendee.displayName)
            meetingKeywordsArray.push(attendee.displayName);
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
        if (notionSearchResponse &&
            notionSearchResponse.ok &&
            notionSearchResponse.data) {
            preparationData.relatedNotionPages = notionSearchResponse.data
                .map((p) => ({
                id: p.id,
                title: p.title ||
                    p.properties?.title?.title?.[0]?.plain_text ||
                    'Untitled Notion Page',
                url: p.url || p.properties?.URL?.url,
                briefSnippet: p.content_preview ||
                    p.content?.substring(0, 150) ||
                    p.properties?.Description?.rich_text?.[0]?.plain_text.substring(0, 150),
            }))
                .slice(0, MAX_RESULTS_PER_CONTEXT);
            console.log(`[handlePrepareForMeeting] Found ${preparationData.relatedNotionPages?.length || 0} Notion pages.`);
        }
        else if (notionSearchResponse && !notionSearchResponse.ok) {
            console.warn(`[handlePrepareForMeeting] Notion search failed: ${notionSearchResponse.error?.message}`);
            accumulatedErrorMessages += `Could not fetch Notion documents: ${notionSearchResponse.error?.message}. `;
        }
        else {
            console.log(`[handlePrepareForMeeting] No Notion pages found or unexpected response format from searchNotionRaw.`);
        }
    }
    catch (e) {
        console.error('[handlePrepareForMeeting] Error fetching Notion context:', e.message, e.stack);
        accumulatedErrorMessages +=
            'Error occurred while fetching Notion documents. ';
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
            const attendeeEmails = targetMeeting.attendees
                .map((a) => a.email)
                .filter(Boolean)
                .join(' OR ');
            if (attendeeEmails) {
                emailQueryParts.push(`with attendees (${attendeeEmails})`);
            }
        }
        emailQueryParts.push(`between ${fromDate.toISOString().split('T')[0]} and ${toDate.toISOString().split('T')[0]}`);
        const emailQuery = emailQueryParts.join(' ');
        console.log(`[handlePrepareForMeeting] Querying Emails with: "${emailQuery}"`);
        // searchEmailsNLU should ideally handle parsing this query or accept structured input.
        const emailsResponse = await searchEmailsNLU(userId, emailQuery, MAX_RESULTS_PER_CONTEXT);
        if (emailsResponse && emailsResponse.ok && emailsResponse.data) {
            preparationData.relatedEmails = emailsResponse.data
                .map((email) => ({
                id: email.id,
                subject: email.subject,
                sender: email.sender,
                receivedDate: email.timestamp, // Assuming Email.timestamp is ISO string
                // url: email.webLink, // If available on your Email type
                briefSnippet: email.body?.substring(0, 150) +
                    (email.body && email.body.length > 150 ? '...' : ''),
            }))
                .slice(0, MAX_RESULTS_PER_CONTEXT);
            console.log(`[handlePrepareForMeeting] Found ${preparationData.relatedEmails?.length || 0} emails.`);
        }
        else if (emailsResponse && !emailsResponse.ok) {
            console.warn(`[handlePrepareForMeeting] Email search failed: ${emailsResponse.error?.message}`);
            accumulatedErrorMessages += `Could not fetch relevant emails: ${emailsResponse.error?.message}. `;
        }
        else {
            console.log(`[handlePrepareForMeeting] No emails found or unexpected response format from email search.`);
        }
    }
    catch (e) {
        console.error('[handlePrepareForMeeting] Error fetching Email context:', e.message, e.stack);
        accumulatedErrorMessages +=
            'Error occurred while fetching relevant emails. ';
    }
    // 3. Gather Task Context
    try {
        const notionTasksDbId = process.env.ATOM_NOTION_TASKS_DATABASE_ID;
        if (!notionTasksDbId) {
            console.warn('[handlePrepareForMeeting] ATOM_NOTION_TASKS_DATABASE_ID is not set. Skipping task search.');
            accumulatedErrorMessages += 'Notion tasks database ID not configured. ';
        }
        else {
            const taskQueryParams = {
                descriptionContains: targetMeeting.summary, // Basic search
                status_not_equals: 'Done', // Assuming 'Done' is a status to exclude
                limit: MAX_RESULTS_PER_CONTEXT,
                notionTasksDbId: notionTasksDbId,
            };
            console.log(`[handlePrepareForMeeting] Querying Tasks with params:`, taskQueryParams);
            const tasksResponse = await queryNotionTasks(userId, taskQueryParams); // queryNotionTasks from notionAndResearchSkills
            if (tasksResponse.success && tasksResponse.tasks) {
                preparationData.relatedTasks = tasksResponse.tasks
                    .map((task) => ({
                    id: task.id,
                    description: task.description,
                    dueDate: task.dueDate,
                    status: task.status,
                    url: task.url,
                }))
                    .slice(0, MAX_RESULTS_PER_CONTEXT);
                console.log(`[handlePrepareForMeeting] Found ${preparationData.relatedTasks?.length || 0} tasks.`);
            }
            else if (!tasksResponse.success) {
                console.warn(`[handlePrepareForMeeting] Task query failed: ${tasksResponse.error}`);
                accumulatedErrorMessages += `Could not fetch related tasks: ${tasksResponse.error}. `;
            }
            else {
                console.log(`[handlePrepareForMeeting] No tasks found or unexpected response from task query.`);
            }
        }
    }
    catch (e) {
        console.error('[handlePrepareForMeeting] Error fetching Task context:', e.message, e.stack);
        accumulatedErrorMessages += 'Error occurred while fetching related tasks. ';
    }
    // 4. (Stretch Goal) Key points from last meeting - Placeholder for V1
    // preparationData.keyPointsFromLastMeeting = "Example: Decision X was made, Action Item Y was assigned.";
    if (accumulatedErrorMessages) {
        preparationData.errorMessage = accumulatedErrorMessages.trim();
    }
    console.log(`[handlePrepareForMeeting] Preparation data compiled:`, JSON.stringify(preparationData).substring(0, 500) + '...');
    return {
        ok: true,
        data: preparationData,
    };
}
/**
 * Determines the date ranges for the current/past week and the upcoming week.
 * @param timePeriod Optional string like "this week" or "last week". Defaults to "this week".
 * @returns Object containing startDate, endDate, nextPeriodStartDate, nextPeriodEndDate, and displayRange.
 */
export function determineDateRange(timePeriod) {
    const now = new Date();
    let today = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // Normalize to start of today
    let startDate;
    let endDate;
    let displayRangeLabel;
    if (timePeriod === 'last week') {
        displayRangeLabel = 'Last Week';
        const dayOfWeek = today.getDay(); // 0 (Sun) - 6 (Sat)
        // Last week's Monday
        startDate = new Date(today.setDate(today.getDate() - dayOfWeek - 6));
        // Last week's Sunday
        endDate = new Date(new Date(startDate).setDate(startDate.getDate() + 6));
        endDate.setHours(23, 59, 59, 999); // End of Sunday
    }
    else {
        // Default to "this week"
        displayRangeLabel = 'This Week';
        const dayOfWeek = today.getDay(); // 0 (Sun) - 6 (Sat)
        // This week's Monday (if today is Sunday, dayOfWeek is 0, so it goes to last Monday)
        startDate = new Date(today.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1)));
        // Today, or this week's Friday if today is Sat/Sun (for a Mon-Fri digest view)
        // For a full Mon-Sun view, endDate would just be `new Date(new Date(startDate).setDate(startDate.getDate() + 6))`
        // Let's make "this week" end on the current day for ongoing digest, or end of Friday if past Friday.
        endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // End of current day for "this week"
        if (endDate.getDay() > 5 ||
            (endDate.getDay() === 5 && now.getHours() >= 17)) {
            // If past Friday 5PM or weekend
            // Show Mon-Fri of current week
            endDate = new Date(new Date(startDate).setDate(startDate.getDate() + 4));
        }
        endDate.setHours(23, 59, 59, 999);
    }
    // Format displayRange for user
    const options = {
        month: 'short',
        day: 'numeric',
    };
    const displayStartDate = startDate.toLocaleDateString('en-US', options);
    const displayEndDate = endDate.toLocaleDateString('en-US', options);
    const displayRange = `${displayRangeLabel} (${displayStartDate} - ${displayEndDate})`;
    // Next Period (e.g., next 7 days from the day after current endDate, or next Mon-Fri)
    const nextPeriodStartDate = new Date(endDate);
    nextPeriodStartDate.setDate(endDate.getDate() + 1); // Start from the day after current period ends
    nextPeriodStartDate.setHours(0, 0, 0, 0); // Start of that day
    const nextPeriodEndDate = new Date(nextPeriodStartDate);
    nextPeriodEndDate.setDate(nextPeriodStartDate.getDate() + 6); // Default to a 7-day outlook
    nextPeriodEndDate.setHours(23, 59, 59, 999);
    return {
        startDate,
        endDate,
        nextPeriodStartDate,
        nextPeriodEndDate,
        displayRange,
    };
}
const MAX_DIGEST_ITEMS = 5; // Max items for completed tasks, meetings, etc.
export async function handleGenerateWeeklyDigest(userId, timePeriodInput) {
    console.log(`[handleGenerateWeeklyDigest] User: ${userId}, Time Period: "${timePeriodInput}"`);
    const { startDate, endDate, nextPeriodStartDate, nextPeriodEndDate, displayRange, } = determineDateRange(timePeriodInput);
    console.log(`[handleGenerateWeeklyDigest] Determined date range: ${startDate.toISOString()} to ${endDate.toISOString()}`);
    console.log(`[handleGenerateWeeklyDigest] Next period range: ${nextPeriodStartDate.toISOString()} to ${nextPeriodEndDate.toISOString()}`);
    const digestData = {
        periodStart: startDate.toISOString(),
        periodEnd: endDate.toISOString(),
        completedTasks: [],
        attendedMeetings: [],
        upcomingCriticalTasks: [],
        upcomingCriticalMeetings: [],
    };
    let accumulatedErrorMessages = '';
    const notionTasksDbId = process.env.ATOM_NOTION_TASKS_DATABASE_ID;
    // 1. Gather Completed Tasks
    if (!notionTasksDbId) {
        console.warn('[handleGenerateWeeklyDigest] ATOM_NOTION_TASKS_DATABASE_ID is not set. Skipping completed task search.');
        accumulatedErrorMessages +=
            'Notion tasks database ID not configured for completed tasks. ';
    }
    else {
        try {
            const completedTaskParams = {
                status: 'Done',
                // NOTE on filtering completed tasks by date:
                // Ideally, `queryNotionTasks` would support filtering by a custom "Completed At" date property
                // from the Notion database. This would be the most accurate way to find tasks completed
                // within the specified `startDate` and `endDate`.
                //
                // Current V1 Approximation:
                // 1. Fetch tasks with status "Done".
                // 2. Filter these tasks locally based on `task.last_edited_time`.
                // This is an approximation because `last_edited_time` reflects the last time ANY property
                // of the task was changed, not necessarily its completion time.
                // A task marked "Done" long ago but edited recently for a minor correction would appear.
                // A task completed within the period but never touched again might be missed if its
                // `last_edited_time` is older due to `queryNotionTasks` internal limits or sorting before this local filter.
                //
                // To improve accuracy in future:
                // - Backend Enhancement: Modify `queryNotionTasks` (and its Python backend if applicable)
                //   to accept `completed_at_after: string` and `completed_at_before: string` parameters
                //   that filter on a specific "Completed At" date property in the Notion DB.
                // - Documentation: Advise users to maintain a "Completed At" date property in their tasks DB.
                limit: MAX_DIGEST_ITEMS * 3, // Fetch more to increase chance of catching relevant recently edited "Done" tasks.
                notionTasksDbId: notionTasksDbId,
            };
            console.log(`[handleGenerateWeeklyDigest] Querying completed tasks with params:`, completedTaskParams);
            const taskResponse = await queryNotionTasks(userId, completedTaskParams);
            if (taskResponse.success && taskResponse.tasks) {
                digestData.completedTasks = taskResponse.tasks
                    .filter((task) => {
                    // Ensure `task.last_edited_time` is available on the NotionTask type from `queryNotionTasks`.
                    // If `task.last_edited_time` is not reliably populated by `queryNotionTasks` from Notion's API,
                    // this filtering will be inaccurate. Defaulting to `task.createdDate` is a poor fallback for completion.
                    const relevantDate = task.last_edited_time
                        ? new Date(task.last_edited_time)
                        : null;
                    if (!relevantDate) {
                        console.warn(`[handleGenerateWeeklyDigest] Task ID ${task.id} has no last_edited_time. Cannot accurately determine if completed in period.`);
                        return false;
                    }
                    return relevantDate >= startDate && relevantDate <= endDate;
                })
                    .slice(0, MAX_DIGEST_ITEMS);
                console.log(`[handleGenerateWeeklyDigest] Found ${digestData.completedTasks.length} completed tasks in period (after date filtering).`);
            }
            else if (!taskResponse.success) {
                accumulatedErrorMessages += `Could not fetch completed tasks: ${taskResponse.error}. `;
            }
        }
        catch (e) {
            console.error('[handleGenerateWeeklyDigest] Error fetching completed tasks:', e.message, e.stack);
            accumulatedErrorMessages +=
                'Error occurred while fetching completed tasks. ';
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
            digestData.attendedMeetings = meetingsAttended
                .filter((event) => {
                const durationMs = new Date(event.endTime).getTime() -
                    new Date(event.startTime).getTime();
                const durationMinutes = durationMs / (1000 * 60);
                return (durationMinutes > 25 &&
                    !event.summary.toLowerCase().includes('focus time')); // Example filter
            })
                .slice(0, MAX_DIGEST_ITEMS);
            console.log(`[handleGenerateWeeklyDigest] Found ${digestData.attendedMeetings.length} attended meetings.`);
        }
    }
    catch (e) {
        console.error('[handleGenerateWeeklyDigest] Error fetching attended meetings:', e.message, e.stack);
        accumulatedErrorMessages +=
            'Error occurred while fetching attended meetings. ';
    }
    // 3. Identify Upcoming Critical Tasks
    if (!notionTasksDbId) {
        console.warn('[handleGenerateWeeklyDigest] ATOM_NOTION_TASKS_DATABASE_ID is not set. Skipping upcoming task search.');
        accumulatedErrorMessages +=
            'Notion tasks database ID not configured for upcoming tasks. ';
    }
    else {
        try {
            const upcomingTaskParams = {
                // Query tasks due in the next period
                dueDateAfter: nextPeriodStartDate.toISOString().split('T')[0], // YYYY-MM-DD
                dueDateBefore: nextPeriodEndDate.toISOString().split('T')[0], // YYYY-MM-DD
                priority: 'High', // Example: only high priority
                status_not_equals: ['Done', 'Cancelled'], // Exclude completed/cancelled
                limit: MAX_DIGEST_ITEMS,
                notionTasksDbId: notionTasksDbId,
            };
            console.log(`[handleGenerateWeeklyDigest] Querying upcoming critical tasks with params:`, upcomingTaskParams);
            const upcomingTaskResponse = await queryNotionTasks(userId, upcomingTaskParams);
            if (upcomingTaskResponse.success && upcomingTaskResponse.tasks) {
                digestData.upcomingCriticalTasks = upcomingTaskResponse.tasks.slice(0, MAX_DIGEST_ITEMS);
                console.log(`[handleGenerateWeeklyDigest] Found ${digestData.upcomingCriticalTasks.length} upcoming critical tasks.`);
            }
            else if (!upcomingTaskResponse.success) {
                accumulatedErrorMessages += `Could not fetch upcoming tasks: ${upcomingTaskResponse.error}. `;
            }
        }
        catch (e) {
            console.error('[handleGenerateWeeklyDigest] Error fetching upcoming tasks:', e.message, e.stack);
            accumulatedErrorMessages +=
                'Error occurred while fetching upcoming tasks. ';
        }
    }
    // 4. Identify Upcoming Critical Meetings
    try {
        // listUpcomingEvents for the next period
        const upcomingMeetings = await listUpcomingEvents(userId, MAX_DIGEST_ITEMS * 2, nextPeriodStartDate.toISOString(), nextPeriodEndDate.toISOString());
        if (upcomingMeetings) {
            // Filter for "significant" meetings
            digestData.upcomingCriticalMeetings = upcomingMeetings
                .filter((event) => {
                const durationMs = new Date(event.endTime).getTime() -
                    new Date(event.startTime).getTime();
                const durationMinutes = durationMs / (1000 * 60);
                // Example: duration > 45 min OR has external attendees (if attendee data is rich enough)
                return (durationMinutes > 45 ||
                    (event.attendees &&
                        event.attendees.some((a) => a.email && !a.email.endsWith('@yourcompany.com'))));
            })
                .slice(0, MAX_DIGEST_ITEMS);
            console.log(`[handleGenerateWeeklyDigest] Found ${digestData.upcomingCriticalMeetings.length} upcoming critical meetings.`);
        }
    }
    catch (e) {
        console.error('[handleGenerateWeeklyDigest] Error fetching upcoming meetings:', e.message, e.stack);
        accumulatedErrorMessages +=
            'Error occurred while fetching upcoming meetings. ';
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
// Conceptual import for the LLM utility
import { analyzeTextForFollowUps } from './llmUtilities'; // Assuming this file will be created
const MAX_FOLLOW_UPS_TO_SUGGEST = 7;
const MAX_CONTEXT_SEARCH_RESULTS = 1; // How many Notion pages to fetch for context
export async function handleSuggestFollowUps(userId, contextIdentifier, contextType) {
    console.log(`[handleSuggestFollowUps] User: ${userId}, Context: "${contextIdentifier}", Type: "${contextType}"`);
    let sourceDocumentText = null;
    let sourceDocumentTitle = contextIdentifier; // Default title
    let sourceDocumentUrl;
    let accumulatedErrorMessages = '';
    const followUpData = {
        contextName: contextIdentifier,
        suggestions: [],
    };
    // 1. Identify & Retrieve Context
    try {
        if (contextType === 'meeting' ||
            (!contextType &&
                (contextIdentifier.toLowerCase().includes('meeting') ||
                    contextIdentifier.toLowerCase().includes('call') ||
                    contextIdentifier.toLowerCase().includes('sync') ||
                    contextIdentifier.toLowerCase().includes('last meeting')))) {
            const meeting = await findTargetMeeting(userId, contextIdentifier.replace(/meeting|call|sync/i, '').trim()); // findTargetMeeting might need adjustment for "last meeting"
            if (meeting) {
                sourceDocumentTitle = `Meeting: ${meeting.summary} on ${new Date(meeting.startTime).toLocaleDateString()}`;
                followUpData.contextName = sourceDocumentTitle;
                sourceDocumentUrl = meeting.htmlLink;
                // Attempt to get notes/transcript for this meeting
                // Option A: Semantic search if transcripts are processed
                // const searchResponse = await handleSemanticSearchMeetingNotesSkill({ command: "search_meeting_notes", params: { query: `transcript for meeting ${meeting.id} OR ${meeting.summary}`, limit: 1 }, user_id: userId, raw_message: ""});
                // if (searchResponse && !searchResponse.startsWith("Sorry") && !searchResponse.startsWith("No results")) {
                //   sourceDocumentText = searchResponse; // Assuming it returns the text
                // } else { ... }
                // Option B: Search Notion for linked notes
                const notionQuery = `notes for meeting "${meeting.summary}" date ${new Date(meeting.startTime).toISOString().split('T')[0]}`;
                const notionSearchResponse = await searchNotionRaw(userId, notionQuery, MAX_CONTEXT_SEARCH_RESULTS);
                if (notionSearchResponse?.ok && notionSearchResponse.data?.[0]) {
                    const page = notionSearchResponse.data[0];
                    sourceDocumentText = page.content || page.title || ''; // Prefer full content if available
                    sourceDocumentTitle = page.title || sourceDocumentTitle;
                    sourceDocumentUrl = page.url || sourceDocumentUrl;
                    followUpData.sourceDocumentSummary = `Using Notion page: "${sourceDocumentTitle}"`;
                    console.log(`[handleSuggestFollowUps] Found Notion page for meeting: ${sourceDocumentTitle}`);
                }
                else {
                    accumulatedErrorMessages += `Could not find specific notes/transcript for meeting "${meeting.summary}". Analysis might be less accurate. `;
                    sourceDocumentText = `Meeting Title: ${meeting.summary}\nDescription: ${meeting.description || 'N/A'}\nAttendees: ${meeting.attendees?.map((a) => a.displayName || a.email).join(', ')}\nTime: ${meeting.startTime} - ${meeting.endTime}`;
                    followUpData.sourceDocumentSummary = `Using calendar event details for "${meeting.summary}" as context.`;
                }
            }
            else {
                return {
                    ok: false,
                    error: {
                        code: 'CONTEXT_NOT_FOUND',
                        message: `Could not find meeting: ${contextIdentifier}`,
                    },
                };
            }
        }
        else if (contextType === 'project') {
            followUpData.contextName = `Project: ${contextIdentifier}`;
            const notionQuery = `project plan or summary for "${contextIdentifier}"`;
            const notionSearchResponse = await searchNotionRaw(userId, notionQuery, MAX_CONTEXT_SEARCH_RESULTS);
            if (notionSearchResponse?.ok && notionSearchResponse.data?.[0]) {
                const page = notionSearchResponse.data[0];
                sourceDocumentText = page.content || page.title || '';
                sourceDocumentTitle = page.title || sourceDocumentTitle;
                sourceDocumentUrl = page.url;
                followUpData.sourceDocumentSummary = `Using Notion page: "${sourceDocumentTitle}" for project context.`;
                console.log(`[handleSuggestFollowUps] Found Notion page for project: ${sourceDocumentTitle}`);
            }
            else {
                return {
                    ok: false,
                    error: {
                        code: 'CONTEXT_NOT_FOUND',
                        message: `Could not find project document: ${contextIdentifier}`,
                    },
                };
            }
        }
        else {
            // Generic context search in Notion if type is unknown
            const notionSearchResponse = await searchNotionRaw(userId, contextIdentifier, MAX_CONTEXT_SEARCH_RESULTS);
            if (notionSearchResponse?.ok && notionSearchResponse.data?.[0]) {
                const page = notionSearchResponse.data[0];
                sourceDocumentText = page.content || page.title || '';
                sourceDocumentTitle = page.title || sourceDocumentTitle;
                sourceDocumentUrl = page.url;
                followUpData.contextName = `Context: ${sourceDocumentTitle}`;
                followUpData.sourceDocumentSummary = `Using Notion page: "${sourceDocumentTitle}" as context.`;
            }
            else {
                return {
                    ok: false,
                    error: {
                        code: 'CONTEXT_NOT_FOUND',
                        message: `Could not find document for context: ${contextIdentifier}`,
                    },
                };
            }
        }
    }
    catch (e) {
        console.error('[handleSuggestFollowUps] Error retrieving context:', e.message, e.stack);
        return {
            ok: false,
            error: {
                code: 'CONTEXT_RETRIEVAL_ERROR',
                message: `Error retrieving context: ${e.message}`,
            },
        };
    }
    if (!sourceDocumentText || sourceDocumentText.trim().length < 50) {
        // Arbitrary minimum length
        accumulatedErrorMessages += `The source document found for "${sourceDocumentTitle}" was too short or empty for useful analysis. `;
        followUpData.errorMessage = accumulatedErrorMessages;
        // Still return ok:true, but with the error message in data.
        return { ok: true, data: followUpData };
    }
    // 2. Analyze Content with LLM
    let extractedItems = {
        action_items: [],
        decisions: [],
        questions: [],
    };
    try {
        console.log(`[handleSuggestFollowUps] Analyzing text (length: ${sourceDocumentText.length}) for "${sourceDocumentTitle}" with LLM.`);
        const llmAnalysis = await analyzeTextForFollowUps(sourceDocumentText, sourceDocumentTitle); // Conceptual LLM call
        if (llmAnalysis.error) {
            accumulatedErrorMessages += `LLM analysis failed: ${llmAnalysis.error}. `;
        }
        else {
            extractedItems = llmAnalysis.extractedItems;
            console.log(`[handleSuggestFollowUps] LLM extracted: ${extractedItems.action_items.length} actions, ${extractedItems.decisions.length} decisions, ${extractedItems.questions.length} questions.`);
        }
    }
    catch (e) {
        console.error('[handleSuggestFollowUps] Error during LLM analysis:', e.message, e.stack);
        accumulatedErrorMessages += `Error during LLM analysis: ${e.message}. `;
    }
    const notionTasksDbId = process.env.ATOM_NOTION_TASKS_DATABASE_ID;
    // 3. Process Extracted Items and Cross-Reference Tasks
    const mapToPotentialFollowUp = async (item, type) => {
        const followUp = {
            type,
            description: item.description,
            suggestedAssignee: item.assignee,
            sourceContext: sourceDocumentTitle,
            existingTaskFound: false,
        };
        if (type === 'action_item' && notionTasksDbId) {
            try {
                // Search for existing tasks matching keywords from this action item's description
                // This query needs to be broad enough to find related tasks.
                const taskQuery = {
                    descriptionContains: item.description.substring(0, 50), // First 50 chars for query
                    status_not_equals: ['Done', 'Cancelled'],
                    limit: 1,
                    notionTasksDbId,
                };
                const existingTasksResponse = await queryNotionTasks(userId, taskQuery);
                if (existingTasksResponse.success &&
                    existingTasksResponse.tasks.length > 0) {
                    const existingTask = existingTasksResponse.tasks[0];
                    // Add more sophisticated matching logic here if needed (e.g., similarity score)
                    // For V1, if any non-done task contains a snippet of the action, mark as potentially existing.
                    followUp.existingTaskFound = true;
                    followUp.existingTaskId = existingTask.id;
                    followUp.existingTaskUrl = existingTask.url;
                    console.log(`[handleSuggestFollowUps] Found existing task '${existingTask.description}' for action item '${item.description}'`);
                }
            }
            catch (taskError) {
                console.warn(`[handleSuggestFollowUps] Error checking for existing task for "${item.description}": ${taskError.message}`);
            }
        }
        return followUp;
    };
    if (extractedItems.action_items) {
        for (const action of extractedItems.action_items) {
            followUpData.suggestions.push(await mapToPotentialFollowUp(action, 'action_item'));
        }
    }
    if (extractedItems.decisions) {
        for (const decision of extractedItems.decisions) {
            followUpData.suggestions.push(await mapToPotentialFollowUp(decision, 'decision'));
        }
    }
    if (extractedItems.questions) {
        for (const question of extractedItems.questions) {
            followUpData.suggestions.push(await mapToPotentialFollowUp(question, 'question'));
        }
    }
    followUpData.suggestions = followUpData.suggestions.slice(0, MAX_FOLLOW_UPS_TO_SUGGEST);
    if (accumulatedErrorMessages) {
        followUpData.errorMessage = accumulatedErrorMessages.trim();
    }
    if (followUpData.suggestions.length === 0 && !followUpData.errorMessage) {
        followUpData.errorMessage =
            (followUpData.errorMessage || '') +
                'No specific follow-up items were identified from the context provided. ';
    }
    console.log(`[handleSuggestFollowUps] Final suggestions compiled for "${followUpData.contextName}". Count: ${followUpData.suggestions.length}`);
    return { ok: true, data: followUpData };
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicHJvZHVjdGl2aXR5U2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicHJvZHVjdGl2aXR5U2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQWFBLE9BQU8sRUFBRSxrQkFBa0IsRUFBRSxNQUFNLGtCQUFrQixDQUFDO0FBQ3RELE9BQU8sRUFBRSxnQkFBZ0IsRUFBRSxlQUFlLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQyxDQUFDLDZDQUE2QztBQUM1SCxPQUFPLEVBQUUsZUFBZSxFQUFFLE1BQU0sZUFBZSxDQUFDLENBQUMsOEZBQThGO0FBQy9JLDRGQUE0RjtBQUU1RixNQUFNLHVCQUF1QixHQUFHLENBQUMsQ0FBQyxDQUFDLDBDQUEwQztBQUM3RSxNQUFNLHVCQUF1QixHQUFHLENBQUMsQ0FBQyxDQUFDLDBDQUEwQztBQUU3RSxvQ0FBb0M7QUFDcEMsS0FBSyxVQUFVLGlCQUFpQixDQUM5QixNQUFjLEVBQ2QsaUJBQTBCLEVBQzFCLGVBQXdCLENBQUMsc0dBQXNHOztJQUUvSCx5SEFBeUg7SUFDekgsNEZBQTRGO0lBQzVGLCtHQUErRztJQUMvRyxpRUFBaUU7SUFDakUscUdBQXFHO0lBRXJHLE1BQU0sTUFBTSxHQUFHLE1BQU0sa0JBQWtCLENBQUMsTUFBTSxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsOENBQThDO0lBQ25HLElBQUksQ0FBQyxNQUFNLElBQUksTUFBTSxDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQUUsQ0FBQztRQUNuQyxPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFFRCxJQUFJLGNBQWMsR0FBRyxNQUFNLENBQUM7SUFFNUIsc0ZBQXNGO0lBQ3RGLElBQUksZUFBZSxFQUFFLENBQUM7UUFDcEIsdURBQXVEO1FBQ3ZELCtEQUErRDtRQUMvRCxpRkFBaUY7UUFDakYsb0ZBQW9GO1FBQ3BGLG1IQUFtSDtRQUNuSCxPQUFPLENBQUMsSUFBSSxDQUNWLHNEQUFzRCxlQUFlLGtFQUFrRSxDQUN4SSxDQUFDO0lBQ0osQ0FB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QUFDMUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIEluIGF0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9za2lsbHMvcHJvZHVjdGl2aXR5U2tpbGxzLnRzXG5pbXBvcnQge1xuICBDYWxlbmRhckV2ZW50LFxuICBQcmVwYXJlRm9yTWVldGluZ1Jlc3BvbnNlLFxuICBNZWV0aW5nUHJlcGFyYXRpb25EYXRhLFxuICBOb3Rpb25QYWdlQ29udGV4dCxcbiAgRW1haWxDb250ZXh0LFxuICBUYXNrQ29udGV4dCxcbiAgRW1haWwsIC8vIEFzc3VtaW5nIEVtYWlsIHR5cGUgaXMgZGVmaW5lZCBmb3IgcmVzdWx0cyBmcm9tIGVtYWlsU2tpbGxzXG4gIE5vdGlvblRhc2ssIC8vIEFzc3VtaW5nIE5vdGlvblRhc2sgdHlwZSBpcyBkZWZpbmVkIGZvciByZXN1bHRzIGZyb20gbm90aW9uQW5kUmVzZWFyY2hTa2lsbHNcbiAgTm90aW9uU2VhcmNoUmVzdWx0RGF0YSwgLy8gQXNzdW1pbmcgdGhpcyBpcyB3aGF0IHNlYXJjaE5vdGlvblJhdyBtaWdodCByZXR1cm4gaXRlbXMgYXNcbiAgU2tpbGxSZXNwb25zZSwgLy8gR2VuZXJpYyBza2lsbCByZXNwb25zZVxufSBmcm9tICcuLi8uLi90eXBlcyc7IC8vIEFkanVzdCBwYXRoIGFzIG5lZWRlZFxuaW1wb3J0IHsgbGlzdFVwY29taW5nRXZlbnRzIH0gZnJvbSAnLi9jYWxlbmRhclNraWxscyc7XG5pbXBvcnQgeyBxdWVyeU5vdGlvblRhc2tzLCBzZWFyY2hOb3Rpb25SYXcgfSBmcm9tICcuL25vdGlvbkFuZFJlc2VhcmNoU2tpbGxzJzsgLy8gQXNzdW1pbmcgc2VhcmNoTm90aW9uUmF3IG9yIHNpbWlsYXIgZXhpc3RzXG5pbXBvcnQgeyBzZWFyY2hFbWFpbHNOTFUgfSBmcm9tICcuL2VtYWlsU2tpbGxzJzsgLy8gQXNzdW1pbmcgc2VhcmNoRW1haWxzTkxVIGZvciB0YXJnZXRlZCBzZWFyY2g7IG9yIHVzZSBsaXN0UmVjZW50RW1haWxzIHdpdGggbWFudWFsIGZpbHRlcmluZ1xuLy8gaW1wb3J0IHsgZ2V0Q3VycmVudFVzZXJJZCB9IGZyb20gJy4uL2hhbmRsZXInOyAvLyBOb3QgbmVlZGVkIGlmIHVzZXJJZCBpcyBwYXNzZWQgZGlyZWN0bHlcblxuY29uc3QgTUFYX1JFU1VMVFNfUEVSX0NPTlRFWFQgPSAzOyAvLyBNYXggTm90aW9uIHBhZ2VzLCBlbWFpbHMsIHRhc2tzIHRvIHNob3dcbmNvbnN0IEVNQUlMX1NFQVJDSF9EQVlTX1BSSU9SID0gNzsgLy8gSG93IG1hbnkgZGF5cyBiYWNrIHRvIHNlYXJjaCBmb3IgZW1haWxzXG5cbi8vIEhlbHBlciB0byBmaW5kIHRoZSB0YXJnZXQgbWVldGluZ1xuYXN5bmMgZnVuY3Rpb24gZmluZFRhcmdldE1lZXRpbmcoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBtZWV0aW5nSWRlbnRpZmllcj86IHN0cmluZyxcbiAgbWVldGluZ0RhdGVUaW1lPzogc3RyaW5nIC8vIFRoaXMgY291bGQgYmUgYSBzcGVjaWZpYyBJU08gc3RyaW5nIG9yIGEgcmVsYXRpdmUgdGVybSBsaWtlIFwidG9tb3Jyb3dcIiBoYW5kbGVkIGJ5IE5MVS9jYWxlbmRhclNraWxsXG4pOiBQcm9taXNlPENhbGVuZGFyRXZlbnQgfCBudWxsPiB7XG4gIC8vIEZvciBzaW1wbGljaXR5LCBsaXN0VXBjb21pbmdFdmVudHMgbWlnaHQgbmVlZCB0byBiZSBlbmhhbmNlZCBvciBOTFUgc2hvdWxkIHJlc29sdmUgbWVldGluZ0RhdGVUaW1lIHRvIGEgc3BlY2lmaWMgcmFuZ2VcbiAgLy8gRm9yIG5vdywgd2UgYXNzdW1lIGxpc3RVcGNvbWluZ0V2ZW50cyBjYW4gdGFrZSBhIHN0YXJ0L2VuZCByYW5nZSBvciB0aGUgTkxVIHByb3ZpZGVzIG9uZS5cbiAgLy8gSWYgbWVldGluZ0RhdGVUaW1lIGlzIGEgcmVsYXRpdmUgdGVybSwgaXQgc2hvdWxkIGlkZWFsbHkgYmUgcmVzb2x2ZWQgdG8gc3BlY2lmaWMgZGF0ZXMgYmVmb3JlIHRoaXMgZnVuY3Rpb24uXG4gIC8vIElmIG1lZXRpbmdJZGVudGlmaWVyIGlzIFwibmV4dCBtZWV0aW5nXCIsIHdlIHRha2UgdGhlIGZpcnN0IG9uZS5cbiAgLy8gQSBtb3JlIHJvYnVzdCBzb2x1dGlvbiB3b3VsZCBpbnZvbHZlIGJldHRlciBOTFUgcGFyc2luZyBmb3IgZGF0ZSByYW5nZXMgYW5kIG1lZXRpbmcgbmFtZSBtYXRjaGluZy5cblxuICBjb25zdCBldmVudHMgPSBhd2FpdCBsaXN0VXBjb21pbmdFdmVudHModXNlcklkLCAyMCk7IC8vIEZldGNoIG1vcmUgZXZlbnRzIHRvIGFsbG93IGJldHRlciBmaWx0ZXJpbmdcbiAgaWYgKCFldmVudHMgfHwgZXZlbnRzLmxlbmd0aCA9PT0gMCkge1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgbGV0IGZpbHRlcmVkRXZlbnRzID0gZXZlbnRzO1xuXG4gIC8vIEJhc2ljIGRhdGUgZmlsdGVyaW5nIChleGFtcGxlLCBuZWVkcyByb2J1c3QgZGF0ZSBwYXJzaW5nIGZvciB0ZXJtcyBsaWtlIFwidG9tb3Jyb3dcIilcbiAgaWYgKG1lZXRpbmdEYXRlVGltZSkge1xuICAgIC8vIFRoaXMgaXMgYSBwbGFjZWhvbGRlci4gUmVhbCBkYXRlIHBhcnNpbmcgaXMgY29tcGxleC5cbiAgICAvLyBOTFUgc2hvdWxkIGlkZWFsbHkgcHJvdmlkZSBhIGRhdGUgcmFuZ2UgZm9yIG1lZXRpbmdEYXRlVGltZS5cbiAgICAvLyBGb3IgZXhhbXBsZSwgaWYgbWVldGluZ0RhdGVUaW1lIGlzIFwidG9tb3Jyb3dcIiwgaXQgcmVzb2x2ZXMgdG8gdG9tb3Jyb3cncyBkYXRlLlxuICAgIC8vIGNvbnN0IHRhcmdldERhdGUgPSBuZXcgRGF0ZShtZWV0aW5nRGF0ZVRpbWUpOyAvLyBUaGlzIGlzIHRvbyBuYWl2ZSBmb3IgXCJ0b21vcnJvd1wiXG4gICAgLy8gZmlsdGVyZWRFdmVudHMgPSBmaWx0ZXJlZEV2ZW50cy5maWx0ZXIoZSA9PiBuZXcgRGF0ZShlLnN0YXJ0VGltZSkudG9EYXRlU3RyaW5nKCkgPT09IHRhcmdldERhdGUudG9EYXRlU3RyaW5nKCkpO1xuICAgIGNvbnNvbGUud2FybihcbiAgICAgIGBbZmluZFRhcmdldE1lZXRpbmddIERhdGUvdGltZSBiYXNlZCBmaWx0ZXJpbmcgZm9yIFwiJHttZWV0aW5nRGF0ZVRpbWV9XCIgaXMgbm90IGZ1bGx5IGltcGxlbWVudGVkIGhlcmUuIFJlbGllcyBvbiBOTFUgb3Igc3BlY2lmaWMgZGF0ZS5gXG4gICAgKTtcbiAgfVxuXG4gIGlmIChcbiAgICBtZWV0aW5nSWRlbnRpZmllciAmJlxuICAgIG1lZXRpbmdJZGVudGlmaWVyLnRvTG93ZXJDYXNlKCkgIT09ICduZXh0IG1lZXRpbmcnICYmXG4gICAgbWVldGluZ0lkZW50aWZpZXIudG9Mb3dlckNhc2UoKSAhPT0gJ215IG5leHQgbWVldGluZydcbiAgKSB7XG4gICAgZmlsdGVyZWRFdmVudHMgPSBmaWx0ZXJlZEV2ZW50cy5maWx0ZXIoXG4gICAgICAoZSkgPT5cbiAgICAgICAgZS5zdW1tYXJ5LnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMobWVldGluZ0lkZW50aWZpZXIudG9Mb3dlckNhc2UoKSkgfHxcbiAgICAgICAgKGUuYXR0ZW5kZWVzICYmXG4gICAgICAgICAgZS5hdHRlbmRlZXMuc29tZShcbiAgICAgICAgICAgIChhKSA9PlxuICAgICAgICAgICAgICBhLmVtYWlsXG4gICAgICAgICAgICAgICAgPy50b0xvd2VyQ2FzZSgpXG4gICAgICAgICAgICAgICAgLmluY2x1ZGVzKG1lZXRpbmdJZGVudGlmaWVyLnRvTG93ZXJDYXNlKCkpIHx8XG4gICAgICAgICAgICAgIGEuZGlzcGxheU5hbWVcbiAgICAgICAgICAgICAgICA/LnRvTG93ZXJDYXNlKClcbiAgICAgICAgICAgICAgICAuaW5jbHVkZXMobWVldGluZ0lkZW50aWZpZXIudG9Mb3dlckNhc2UoKSlcbiAgICAgICAgICApKVxuICAgICk7XG4gIH1cblxuICBpZiAoZmlsdGVyZWRFdmVudHMubGVuZ3RoID09PSAwKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICAvLyBTb3J0IGJ5IHN0YXJ0IHRpbWUgdG8gZ2V0IHRoZSBcIm5leHRcIiBvbmUgaWYgbXVsdGlwbGUgbWF0Y2ggb3IgaWYgXCJuZXh0IG1lZXRpbmdcIiB3YXMgc3BlY2lmaWVkXG4gIHJldHVybiBmaWx0ZXJlZEV2ZW50cy5zb3J0KFxuICAgIChhLCBiKSA9PiBuZXcgRGF0ZShhLnN0YXJ0VGltZSkuZ2V0VGltZSgpIC0gbmV3IERhdGUoYi5zdGFydFRpbWUpLmdldFRpbWUoKVxuICApWzBdO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlUHJlcGFyZUZvck1lZXRpbmcoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBtZWV0aW5nSWRlbnRpZmllcj86IHN0cmluZyxcbiAgbWVldGluZ0RhdGVUaW1lPzogc3RyaW5nXG4pOiBQcm9taXNlPFByZXBhcmVGb3JNZWV0aW5nUmVzcG9uc2U+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gVXNlcjogJHt1c2VySWR9LCBNZWV0aW5nIElEOiBcIiR7bWVldGluZ0lkZW50aWZpZXJ9XCIsIERhdGVUaW1lOiBcIiR7bWVldGluZ0RhdGVUaW1lfVwiYFxuICApO1xuICBjb25zdCB0YXJnZXRNZWV0aW5nID0gYXdhaXQgZmluZFRhcmdldE1lZXRpbmcoXG4gICAgdXNlcklkLFxuICAgIG1lZXRpbmdJZGVudGlmaWVyLFxuICAgIG1lZXRpbmdEYXRlVGltZVxuICApO1xuXG4gIGlmICghdGFyZ2V0TWVldGluZykge1xuICAgIGNvbnNvbGUubG9nKGBbaGFuZGxlUHJlcGFyZUZvck1lZXRpbmddIE5vIHRhcmdldCBtZWV0aW5nIGZvdW5kLmApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTUVFVElOR19OT1RfRk9VTkQnLFxuICAgICAgICBtZXNzYWdlOiAnQ291bGQgbm90IGZpbmQgdGhlIHNwZWNpZmllZCBtZWV0aW5nLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc29sZS5sb2coXG4gICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gVGFyZ2V0IG1lZXRpbmcgZm91bmQ6IFwiJHt0YXJnZXRNZWV0aW5nLnN1bW1hcnl9XCIgYXQgJHt0YXJnZXRNZWV0aW5nLnN0YXJ0VGltZX1gXG4gICk7XG5cbiAgY29uc3QgcHJlcGFyYXRpb25EYXRhOiBNZWV0aW5nUHJlcGFyYXRpb25EYXRhID0geyB0YXJnZXRNZWV0aW5nIH07XG4gIGxldCBhY2N1bXVsYXRlZEVycm9yTWVzc2FnZXMgPSAnJztcblxuICBjb25zdCBtZWV0aW5nS2V5d29yZHNBcnJheSA9IFt0YXJnZXRNZWV0aW5nLnN1bW1hcnldO1xuICBpZiAodGFyZ2V0TWVldGluZy5kZXNjcmlwdGlvbikge1xuICAgIG1lZXRpbmdLZXl3b3Jkc0FycmF5LnB1c2goXG4gICAgICAuLi50YXJnZXRNZWV0aW5nLmRlc2NyaXB0aW9uLnNwbGl0KCcgJykuc2xpY2UoMCwgMTApXG4gICAgKTsgLy8gQWRkIHNvbWUga2V5d29yZHMgZnJvbSBkZXNjcmlwdGlvblxuICB9XG4gIHRhcmdldE1lZXRpbmcuYXR0ZW5kZWVzPy5mb3JFYWNoKChhdHRlbmRlZSkgPT4ge1xuICAgIGlmIChhdHRlbmRlZS5kaXNwbGF5TmFtZSkgbWVldGluZ0tleXdvcmRzQXJyYXkucHVzaChhdHRlbmRlZS5kaXNwbGF5TmFtZSk7XG4gICAgLy8gaWYgKGF0dGVuZGVlLmVtYWlsKSBtZWV0aW5nS2V5d29yZHNBcnJheS5wdXNoKGF0dGVuZGVlLmVtYWlsLnNwbGl0KCdAJylbMF0pOyAvLyBBZGQgdXNlcm5hbWUgcGFydCBvZiBlbWFpbFxuICB9KTtcbiAgY29uc3QgbWVldGluZ0tleXdvcmRzID0gbWVldGluZ0tleXdvcmRzQXJyYXkuam9pbignICcpOyAvLyBDcmVhdGUgYSBrZXl3b3JkIHN0cmluZyBmb3Igc2VhcmNoZXNcblxuICAvLyAxLiBHYXRoZXIgTm90aW9uIENvbnRleHRcbiAgdHJ5IHtcbiAgICAvLyBzZWFyY2hOb3Rpb25SYXcgaXMgZXhwZWN0ZWQgdG8gYmUgYSBmdW5jdGlvbiB0aGF0IHRha2VzIGEgdXNlciBJRCBhbmQgYSBxdWVyeSBzdHJpbmcuXG4gICAgLy8gVGhlIGFjdHVhbCBpbXBsZW1lbnRhdGlvbiBvZiBzZWFyY2hOb3Rpb25SYXcgbWlnaHQgaW52b2x2ZSBjYWxsaW5nIGEgUHl0aG9uIHNlcnZpY2UuXG4gICAgY29uc3Qgbm90aW9uUXVlcnkgPSBgY29udGVudCByZWxhdGVkIHRvOiAke3RhcmdldE1lZXRpbmcuc3VtbWFyeX1gOyAvLyBTaW1wbGUgcXVlcnlcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbaGFuZGxlUHJlcGFyZUZvck1lZXRpbmddIFF1ZXJ5aW5nIE5vdGlvbiB3aXRoOiBcIiR7bm90aW9uUXVlcnl9XCJgXG4gICAgKTtcbiAgICBjb25zdCBub3Rpb25TZWFyY2hSZXNwb25zZSA9IGF3YWl0IHNlYXJjaE5vdGlvblJhdyhcbiAgICAgIHVzZXJJZCxcbiAgICAgIG5vdGlvblF1ZXJ5LFxuICAgICAgTUFYX1JFU1VMVFNfUEVSX0NPTlRFWFRcbiAgICApO1xuXG4gICAgLy8gQXNzdW1pbmcgc2VhcmNoTm90aW9uUmF3IHJldHVybnMgYSBzdHJ1Y3R1cmUgbGlrZTogUHl0aG9uQXBpUmVzcG9uc2U8Tm90aW9uU2VhcmNoUmVzdWx0RGF0YVtdPlxuICAgIGlmIChcbiAgICAgIG5vdGlvblNlYXJjaFJlc3BvbnNlICYmXG4gICAgICBub3Rpb25TZWFyY2hSZXNwb25zZS5vayAmJlxuICAgICAgbm90aW9uU2VhcmNoUmVzcG9uc2UuZGF0YVxuICAgICkge1xuICAgICAgcHJlcGFyYXRpb25EYXRhLnJlbGF0ZWROb3Rpb25QYWdlcyA9IG5vdGlvblNlYXJjaFJlc3BvbnNlLmRhdGFcbiAgICAgICAgLm1hcCgocDogTm90aW9uU2VhcmNoUmVzdWx0RGF0YSkgPT4gKHtcbiAgICAgICAgICBpZDogcC5pZCxcbiAgICAgICAgICB0aXRsZTpcbiAgICAgICAgICAgIHAudGl0bGUgfHxcbiAgICAgICAgICAgIHAucHJvcGVydGllcz8udGl0bGU/LnRpdGxlPy5bMF0/LnBsYWluX3RleHQgfHxcbiAgICAgICAgICAgICdVbnRpdGxlZCBOb3Rpb24gUGFnZScsXG4gICAgICAgICAgdXJsOiBwLnVybCB8fCBwLnByb3BlcnRpZXM/LlVSTD8udXJsLFxuICAgICAgICAgIGJyaWVmU25pcHBldDpcbiAgICAgICAgICAgIHAuY29udGVudF9wcmV2aWV3IHx8XG4gICAgICAgICAgICBwLmNvbnRlbnQ/LnN1YnN0cmluZygwLCAxNTApIHx8XG4gICAgICAgICAgICBwLnByb3BlcnRpZXM/LkRlc2NyaXB0aW9uPy5yaWNoX3RleHQ/LlswXT8ucGxhaW5fdGV4dC5zdWJzdHJpbmcoXG4gICAgICAgICAgICAgIDAsXG4gICAgICAgICAgICAgIDE1MFxuICAgICAgICAgICAgKSxcbiAgICAgICAgfSkpXG4gICAgICAgIC5zbGljZSgwLCBNQVhfUkVTVUxUU19QRVJfQ09OVEVYVCk7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gRm91bmQgJHtwcmVwYXJhdGlvbkRhdGEucmVsYXRlZE5vdGlvblBhZ2VzPy5sZW5ndGggfHwgMH0gTm90aW9uIHBhZ2VzLmBcbiAgICAgICk7XG4gICAgfSBlbHNlIGlmIChub3Rpb25TZWFyY2hSZXNwb25zZSAmJiAhbm90aW9uU2VhcmNoUmVzcG9uc2Uub2spIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gTm90aW9uIHNlYXJjaCBmYWlsZWQ6ICR7bm90aW9uU2VhcmNoUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgKTtcbiAgICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPSBgQ291bGQgbm90IGZldGNoIE5vdGlvbiBkb2N1bWVudHM6ICR7bm90aW9uU2VhcmNoUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9LiBgO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gTm8gTm90aW9uIHBhZ2VzIGZvdW5kIG9yIHVuZXhwZWN0ZWQgcmVzcG9uc2UgZm9ybWF0IGZyb20gc2VhcmNoTm90aW9uUmF3LmBcbiAgICAgICk7XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ1toYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gRXJyb3IgZmV0Y2hpbmcgTm90aW9uIGNvbnRleHQ6JyxcbiAgICAgIGUubWVzc2FnZSxcbiAgICAgIGUuc3RhY2tcbiAgICApO1xuICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPVxuICAgICAgJ0Vycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIE5vdGlvbiBkb2N1bWVudHMuICc7XG4gIH1cblxuICAvLyAyLiBHYXRoZXIgRW1haWwgQ29udGV4dFxuICB0cnkge1xuICAgIGNvbnN0IHRvRGF0ZSA9IG5ldyBEYXRlKCk7XG4gICAgY29uc3QgZnJvbURhdGUgPSBuZXcgRGF0ZSgpO1xuICAgIGZyb21EYXRlLnNldERhdGUodG9EYXRlLmdldERhdGUoKSAtIEVNQUlMX1NFQVJDSF9EQVlTX1BSSU9SKTtcblxuICAgIC8vIENvbnN0cnVjdCBhIHF1ZXJ5IGZvciBzZWFyY2hFbWFpbHNOTFUuIFRoaXMgbWF5IG5lZWQgcmVmaW5lbWVudCBiYXNlZCBvbiBOTFUgY2FwYWJpbGl0aWVzLlxuICAgIC8vIEZvciBub3csIG1ha2UgaXQgc29tZXdoYXQgc3RydWN0dXJlZCBpZiBzZWFyY2hFbWFpbHNOTFUgaXMgYSBwYXNzdGhyb3VnaCB0byBhbiBBUEkuXG4gICAgbGV0IGVtYWlsUXVlcnlQYXJ0cyA9IFtgYWJvdXQgXCIke3RhcmdldE1lZXRpbmcuc3VtbWFyeX1cImBdO1xuICAgIGlmICh0YXJnZXRNZWV0aW5nLmF0dGVuZGVlcyAmJiB0YXJnZXRNZWV0aW5nLmF0dGVuZGVlcy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBhdHRlbmRlZUVtYWlscyA9IHRhcmdldE1lZXRpbmcuYXR0ZW5kZWVzXG4gICAgICAgIC5tYXAoKGEpID0+IGEuZW1haWwpXG4gICAgICAgIC5maWx0ZXIoQm9vbGVhbilcbiAgICAgICAgLmpvaW4oJyBPUiAnKTtcbiAgICAgIGlmIChhdHRlbmRlZUVtYWlscykge1xuICAgICAgICBlbWFpbFF1ZXJ5UGFydHMucHVzaChgd2l0aCBhdHRlbmRlZXMgKCR7YXR0ZW5kZWVFbWFpbHN9KWApO1xuICAgICAgfVxuICAgIH1cbiAgICBlbWFpbFF1ZXJ5UGFydHMucHVzaChcbiAgICAgIGBiZXR3ZWVuICR7ZnJvbURhdGUudG9JU09TdHJpbmcoKS5zcGxpdCgnVCcpWzBdfSBhbmQgJHt0b0RhdGUudG9JU09TdHJpbmcoKS5zcGxpdCgnVCcpWzBdfWBcbiAgICApO1xuICAgIGNvbnN0IGVtYWlsUXVlcnkgPSBlbWFpbFF1ZXJ5UGFydHMuam9pbignICcpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW2hhbmRsZVByZXBhcmVGb3JNZWV0aW5nXSBRdWVyeWluZyBFbWFpbHMgd2l0aDogXCIke2VtYWlsUXVlcnl9XCJgXG4gICAgKTtcbiAgICAvLyBzZWFyY2hFbWFpbHNOTFUgc2hvdWxkIGlkZWFsbHkgaGFuZGxlIHBhcnNpbmcgdGhpcyBxdWVyeSBvciBhY2NlcHQgc3RydWN0dXJlZCBpbnB1dC5cbiAgICBjb25zdCBlbWFpbHNSZXNwb25zZTogU2tpbGxSZXNwb25zZTxFbWFpbFtdPiA9IGF3YWl0IHNlYXJjaEVtYWlsc05MVShcbiAgICAgIHVzZXJJZCxcbiAgICAgIGVtYWlsUXVlcnksXG4gICAgICBNQVhfUkVTVUxUU19QRVJfQ09OVEVYVFxuICAgICk7XG5cbiAgICBpZiAoZW1haWxzUmVzcG9uc2UgJiYgZW1haWxzUmVzcG9uc2Uub2sgJiYgZW1haWxzUmVzcG9uc2UuZGF0YSkge1xuICAgICAgcHJlcGFyYXRpb25EYXRhLnJlbGF0ZWRFbWFpbHMgPSBlbWFpbHNSZXNwb25zZS5kYXRhXG4gICAgICAgIC5tYXAoKGVtYWlsOiBFbWFpbCkgPT4gKHtcbiAgICAgICAgICBpZDogZW1haWwuaWQsXG4gICAgICAgICAgc3ViamVjdDogZW1haWwuc3ViamVjdCxcbiAgICAgICAgICBzZW5kZXI6IGVtYWlsLnNlbmRlcixcbiAgICAgICAgICByZWNlaXZlZERhdGU6IGVtYWlsLnRpbWVzdGFtcCwgLy8gQXNzdW1pbmcgRW1haWwudGltZXN0YW1wIGlzIElTTyBzdHJpbmdcbiAgICAgICAgICAvLyB1cmw6IGVtYWlsLndlYkxpbmssIC8vIElmIGF2YWlsYWJsZSBvbiB5b3VyIEVtYWlsIHR5cGVcbiAgICAgICAgICBicmllZlNuaXBwZXQ6XG4gICAgICAgICAgICBlbWFpbC5ib2R5Py5zdWJzdHJpbmcoMCwgMTUwKSArXG4gICAgICAgICAgICAoZW1haWwuYm9keSAmJiBlbWFpbC5ib2R5Lmxlbmd0aCA+IDE1MCA/ICcuLi4nIDogJycpLFxuICAgICAgICB9KSlcbiAgICAgICAgLnNsaWNlKDAsIE1BWF9SRVNVTFRTX1BFUl9DT05URVhUKTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgW2hhbmRsZVByZXBhcmVGb3JNZWV0aW5nXSBGb3VuZCAke3ByZXBhcmF0aW9uRGF0YS5yZWxhdGVkRW1haWxzPy5sZW5ndGggfHwgMH0gZW1haWxzLmBcbiAgICAgICk7XG4gICAgfSBlbHNlIGlmIChlbWFpbHNSZXNwb25zZSAmJiAhZW1haWxzUmVzcG9uc2Uub2spIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gRW1haWwgc2VhcmNoIGZhaWxlZDogJHtlbWFpbHNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICApO1xuICAgICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9IGBDb3VsZCBub3QgZmV0Y2ggcmVsZXZhbnQgZW1haWxzOiAke2VtYWlsc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfS4gYDtcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBbaGFuZGxlUHJlcGFyZUZvck1lZXRpbmddIE5vIGVtYWlscyBmb3VuZCBvciB1bmV4cGVjdGVkIHJlc3BvbnNlIGZvcm1hdCBmcm9tIGVtYWlsIHNlYXJjaC5gXG4gICAgICApO1xuICAgIH1cbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgICdbaGFuZGxlUHJlcGFyZUZvck1lZXRpbmddIEVycm9yIGZldGNoaW5nIEVtYWlsIGNvbnRleHQ6JyxcbiAgICAgIGUubWVzc2FnZSxcbiAgICAgIGUuc3RhY2tcbiAgICApO1xuICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPVxuICAgICAgJ0Vycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIHJlbGV2YW50IGVtYWlscy4gJztcbiAgfVxuXG4gIC8vIDMuIEdhdGhlciBUYXNrIENvbnRleHRcbiAgdHJ5IHtcbiAgICBjb25zdCBub3Rpb25UYXNrc0RiSWQgPSBwcm9jZXNzLmVudi5BVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRDtcbiAgICBpZiAoIW5vdGlvblRhc2tzRGJJZCkge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAnW2hhbmRsZVByZXBhcmVGb3JNZWV0aW5nXSBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCBpcyBub3Qgc2V0LiBTa2lwcGluZyB0YXNrIHNlYXJjaC4nXG4gICAgICApO1xuICAgICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9ICdOb3Rpb24gdGFza3MgZGF0YWJhc2UgSUQgbm90IGNvbmZpZ3VyZWQuICc7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnN0IHRhc2tRdWVyeVBhcmFtcyA9IHtcbiAgICAgICAgZGVzY3JpcHRpb25Db250YWluczogdGFyZ2V0TWVldGluZy5zdW1tYXJ5LCAvLyBCYXNpYyBzZWFyY2hcbiAgICAgICAgc3RhdHVzX25vdF9lcXVhbHM6ICdEb25lJyBhcyBhbnksIC8vIEFzc3VtaW5nICdEb25lJyBpcyBhIHN0YXR1cyB0byBleGNsdWRlXG4gICAgICAgIGxpbWl0OiBNQVhfUkVTVUxUU19QRVJfQ09OVEVYVCxcbiAgICAgICAgbm90aW9uVGFza3NEYklkOiBub3Rpb25UYXNrc0RiSWQsXG4gICAgICB9O1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBbaGFuZGxlUHJlcGFyZUZvck1lZXRpbmddIFF1ZXJ5aW5nIFRhc2tzIHdpdGggcGFyYW1zOmAsXG4gICAgICAgIHRhc2tRdWVyeVBhcmFtc1xuICAgICAgKTtcbiAgICAgIGNvbnN0IHRhc2tzUmVzcG9uc2UgPSBhd2FpdCBxdWVyeU5vdGlvblRhc2tzKHVzZXJJZCwgdGFza1F1ZXJ5UGFyYW1zKTsgLy8gcXVlcnlOb3Rpb25UYXNrcyBmcm9tIG5vdGlvbkFuZFJlc2VhcmNoU2tpbGxzXG5cbiAgICAgIGlmICh0YXNrc1Jlc3BvbnNlLnN1Y2Nlc3MgJiYgdGFza3NSZXNwb25zZS50YXNrcykge1xuICAgICAgICBwcmVwYXJhdGlvbkRhdGEucmVsYXRlZFRhc2tzID0gdGFza3NSZXNwb25zZS50YXNrc1xuICAgICAgICAgIC5tYXAoKHRhc2s6IE5vdGlvblRhc2spID0+ICh7XG4gICAgICAgICAgICBpZDogdGFzay5pZCxcbiAgICAgICAgICAgIGRlc2NyaXB0aW9uOiB0YXNrLmRlc2NyaXB0aW9uLFxuICAgICAgICAgICAgZHVlRGF0ZTogdGFzay5kdWVEYXRlLFxuICAgICAgICAgICAgc3RhdHVzOiB0YXNrLnN0YXR1cyxcbiAgICAgICAgICAgIHVybDogdGFzay51cmwsXG4gICAgICAgICAgfSkpXG4gICAgICAgICAgLnNsaWNlKDAsIE1BWF9SRVNVTFRTX1BFUl9DT05URVhUKTtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gRm91bmQgJHtwcmVwYXJhdGlvbkRhdGEucmVsYXRlZFRhc2tzPy5sZW5ndGggfHwgMH0gdGFza3MuYFxuICAgICAgICApO1xuICAgICAgfSBlbHNlIGlmICghdGFza3NSZXNwb25zZS5zdWNjZXNzKSB7XG4gICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICBgW2hhbmRsZVByZXBhcmVGb3JNZWV0aW5nXSBUYXNrIHF1ZXJ5IGZhaWxlZDogJHt0YXNrc1Jlc3BvbnNlLmVycm9yfWBcbiAgICAgICAgKTtcbiAgICAgICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9IGBDb3VsZCBub3QgZmV0Y2ggcmVsYXRlZCB0YXNrczogJHt0YXNrc1Jlc3BvbnNlLmVycm9yfS4gYDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGBbaGFuZGxlUHJlcGFyZUZvck1lZXRpbmddIE5vIHRhc2tzIGZvdW5kIG9yIHVuZXhwZWN0ZWQgcmVzcG9uc2UgZnJvbSB0YXNrIHF1ZXJ5LmBcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnW2hhbmRsZVByZXBhcmVGb3JNZWV0aW5nXSBFcnJvciBmZXRjaGluZyBUYXNrIGNvbnRleHQ6JyxcbiAgICAgIGUubWVzc2FnZSxcbiAgICAgIGUuc3RhY2tcbiAgICApO1xuICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPSAnRXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgcmVsYXRlZCB0YXNrcy4gJztcbiAgfVxuXG4gIC8vIDQuIChTdHJldGNoIEdvYWwpIEtleSBwb2ludHMgZnJvbSBsYXN0IG1lZXRpbmcgLSBQbGFjZWhvbGRlciBmb3IgVjFcbiAgLy8gcHJlcGFyYXRpb25EYXRhLmtleVBvaW50c0Zyb21MYXN0TWVldGluZyA9IFwiRXhhbXBsZTogRGVjaXNpb24gWCB3YXMgbWFkZSwgQWN0aW9uIEl0ZW0gWSB3YXMgYXNzaWduZWQuXCI7XG5cbiAgaWYgKGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcykge1xuICAgIHByZXBhcmF0aW9uRGF0YS5lcnJvck1lc3NhZ2UgPSBhY2N1bXVsYXRlZEVycm9yTWVzc2FnZXMudHJpbSgpO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgYFtoYW5kbGVQcmVwYXJlRm9yTWVldGluZ10gUHJlcGFyYXRpb24gZGF0YSBjb21waWxlZDpgLFxuICAgIEpTT04uc3RyaW5naWZ5KHByZXBhcmF0aW9uRGF0YSkuc3Vic3RyaW5nKDAsIDUwMCkgKyAnLi4uJ1xuICApO1xuXG4gIHJldHVybiB7XG4gICAgb2s6IHRydWUsXG4gICAgZGF0YTogcHJlcGFyYXRpb25EYXRhLFxuICB9O1xufVxuXG4vLyAtLS0gQXV0b21hdGVkIFdlZWtseSBEaWdlc3QgU2tpbGwgLS0tXG5cbmludGVyZmFjZSBEYXRlUmFuZ2Uge1xuICBzdGFydERhdGU6IERhdGU7XG4gIGVuZERhdGU6IERhdGU7XG4gIG5leHRQZXJpb2RTdGFydERhdGU6IERhdGU7XG4gIG5leHRQZXJpb2RFbmREYXRlOiBEYXRlO1xuICBkaXNwbGF5UmFuZ2U6IHN0cmluZzsgLy8gRm9yIHVzZXItZmFjaW5nIG1lc3NhZ2VzIGUuZy4sIFwiVGhpcyBXZWVrIChNb24sIEp1bCAyMiAtIEZyaSwgSnVsIDI2KVwiXG59XG5cbi8qKlxuICogRGV0ZXJtaW5lcyB0aGUgZGF0ZSByYW5nZXMgZm9yIHRoZSBjdXJyZW50L3Bhc3Qgd2VlayBhbmQgdGhlIHVwY29taW5nIHdlZWsuXG4gKiBAcGFyYW0gdGltZVBlcmlvZCBPcHRpb25hbCBzdHJpbmcgbGlrZSBcInRoaXMgd2Vla1wiIG9yIFwibGFzdCB3ZWVrXCIuIERlZmF1bHRzIHRvIFwidGhpcyB3ZWVrXCIuXG4gKiBAcmV0dXJucyBPYmplY3QgY29udGFpbmluZyBzdGFydERhdGUsIGVuZERhdGUsIG5leHRQZXJpb2RTdGFydERhdGUsIG5leHRQZXJpb2RFbmREYXRlLCBhbmQgZGlzcGxheVJhbmdlLlxuICovXG5leHBvcnQgZnVuY3Rpb24gZGV0ZXJtaW5lRGF0ZVJhbmdlKFxuICB0aW1lUGVyaW9kPzogJ3RoaXMgd2VlaycgfCAnbGFzdCB3ZWVrJyB8IHN0cmluZ1xuKTogRGF0ZVJhbmdlIHtcbiAgY29uc3Qgbm93ID0gbmV3IERhdGUoKTtcbiAgbGV0IHRvZGF5ID0gbmV3IERhdGUobm93LmdldEZ1bGxZZWFyKCksIG5vdy5nZXRNb250aCgpLCBub3cuZ2V0RGF0ZSgpKTsgLy8gTm9ybWFsaXplIHRvIHN0YXJ0IG9mIHRvZGF5XG5cbiAgbGV0IHN0YXJ0RGF0ZTogRGF0ZTtcbiAgbGV0IGVuZERhdGU6IERhdGU7XG4gIGxldCBkaXNwbGF5UmFuZ2VMYWJlbDogc3RyaW5nO1xuXG4gIGlmICh0aW1lUGVyaW9kID09PSAnbGFzdCB3ZWVrJykge1xuICAgIGRpc3BsYXlSYW5nZUxhYmVsID0gJ0xhc3QgV2Vlayc7XG4gICAgY29uc3QgZGF5T2ZXZWVrID0gdG9kYXkuZ2V0RGF5KCk7IC8vIDAgKFN1bikgLSA2IChTYXQpXG4gICAgLy8gTGFzdCB3ZWVrJ3MgTW9uZGF5XG4gICAgc3RhcnREYXRlID0gbmV3IERhdGUodG9kYXkuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgLSBkYXlPZldlZWsgLSA2KSk7XG4gICAgLy8gTGFzdCB3ZWVrJ3MgU3VuZGF5XG4gICAgZW5kRGF0ZSA9IG5ldyBEYXRlKG5ldyBEYXRlKHN0YXJ0RGF0ZSkuc2V0RGF0ZShzdGFydERhdGUuZ2V0RGF0ZSgpICsgNikpO1xuICAgIGVuZERhdGUuc2V0SG91cnMoMjMsIDU5LCA1OSwgOTk5KTsgLy8gRW5kIG9mIFN1bmRheVxuICB9IGVsc2Uge1xuICAgIC8vIERlZmF1bHQgdG8gXCJ0aGlzIHdlZWtcIlxuICAgIGRpc3BsYXlSYW5nZUxhYmVsID0gJ1RoaXMgV2Vlayc7XG4gICAgY29uc3QgZGF5T2ZXZWVrID0gdG9kYXkuZ2V0RGF5KCk7IC8vIDAgKFN1bikgLSA2IChTYXQpXG4gICAgLy8gVGhpcyB3ZWVrJ3MgTW9uZGF5IChpZiB0b2RheSBpcyBTdW5kYXksIGRheU9mV2VlayBpcyAwLCBzbyBpdCBnb2VzIHRvIGxhc3QgTW9uZGF5KVxuICAgIHN0YXJ0RGF0ZSA9IG5ldyBEYXRlKFxuICAgICAgdG9kYXkuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgLSAoZGF5T2ZXZWVrID09PSAwID8gNiA6IGRheU9mV2VlayAtIDEpKVxuICAgICk7XG4gICAgLy8gVG9kYXksIG9yIHRoaXMgd2VlaydzIEZyaWRheSBpZiB0b2RheSBpcyBTYXQvU3VuIChmb3IgYSBNb24tRnJpIGRpZ2VzdCB2aWV3KVxuICAgIC8vIEZvciBhIGZ1bGwgTW9uLVN1biB2aWV3LCBlbmREYXRlIHdvdWxkIGp1c3QgYmUgYG5ldyBEYXRlKG5ldyBEYXRlKHN0YXJ0RGF0ZSkuc2V0RGF0ZShzdGFydERhdGUuZ2V0RGF0ZSgpICsgNikpYFxuICAgIC8vIExldCdzIG1ha2UgXCJ0aGlzIHdlZWtcIiBlbmQgb24gdGhlIGN1cnJlbnQgZGF5IGZvciBvbmdvaW5nIGRpZ2VzdCwgb3IgZW5kIG9mIEZyaWRheSBpZiBwYXN0IEZyaWRheS5cbiAgICBlbmREYXRlID0gbmV3IERhdGUobm93LmdldEZ1bGxZZWFyKCksIG5vdy5nZXRNb250aCgpLCBub3cuZ2V0RGF0ZSgpKTsgLy8gRW5kIG9mIGN1cnJlbnQgZGF5IGZvciBcInRoaXMgd2Vla1wiXG4gICAgaWYgKFxuICAgICAgZW5kRGF0ZS5nZXREYXkoKSA+IDUgfHxcbiAgICAgIChlbmREYXRlLmdldERheSgpID09PSA1ICYmIG5vdy5nZXRIb3VycygpID49IDE3KVxuICAgICkge1xuICAgICAgLy8gSWYgcGFzdCBGcmlkYXkgNVBNIG9yIHdlZWtlbmRcbiAgICAgIC8vIFNob3cgTW9uLUZyaSBvZiBjdXJyZW50IHdlZWtcbiAgICAgIGVuZERhdGUgPSBuZXcgRGF0ZShuZXcgRGF0ZShzdGFydERhdGUpLnNldERhdGUoc3RhcnREYXRlLmdldERhdGUoKSArIDQpKTtcbiAgICB9XG4gICAgZW5kRGF0ZS5zZXRIb3VycygyMywgNTksIDU5LCA5OTkpO1xuICB9XG5cbiAgLy8gRm9ybWF0IGRpc3BsYXlSYW5nZSBmb3IgdXNlclxuICBjb25zdCBvcHRpb25zOiBJbnRsLkRhdGVUaW1lRm9ybWF0T3B0aW9ucyA9IHtcbiAgICBtb250aDogJ3Nob3J0JyxcbiAgICBkYXk6ICdudW1lcmljJyxcbiAgfTtcbiAgY29uc3QgZGlzcGxheVN0YXJ0RGF0ZSA9IHN0YXJ0RGF0ZS50b0xvY2FsZURhdGVTdHJpbmcoJ2VuLVVTJywgb3B0aW9ucyk7XG4gIGNvbnN0IGRpc3BsYXlFbmREYXRlID0gZW5kRGF0ZS50b0xvY2FsZURhdGVTdHJpbmcoJ2VuLVVTJywgb3B0aW9ucyk7XG4gIGNvbnN0IGRpc3BsYXlSYW5nZSA9IGAke2Rpc3BsYXlSYW5nZUxhYmVsfSAoJHtkaXNwbGF5U3RhcnREYXRlfSAtICR7ZGlzcGxheUVuZERhdGV9KWA7XG5cbiAgLy8gTmV4dCBQZXJpb2QgKGUuZy4sIG5leHQgNyBkYXlzIGZyb20gdGhlIGRheSBhZnRlciBjdXJyZW50IGVuZERhdGUsIG9yIG5leHQgTW9uLUZyaSlcbiAgY29uc3QgbmV4dFBlcmlvZFN0YXJ0RGF0ZSA9IG5ldyBEYXRlKGVuZERhdGUpO1xuICBuZXh0UGVyaW9kU3RhcnREYXRlLnNldERhdGUoZW5kRGF0ZS5nZXREYXRlKCkgKyAxKTsgLy8gU3RhcnQgZnJvbSB0aGUgZGF5IGFmdGVyIGN1cnJlbnQgcGVyaW9kIGVuZHNcbiAgbmV4dFBlcmlvZFN0YXJ0RGF0ZS5zZXRIb3VycygwLCAwLCAwLCAwKTsgLy8gU3RhcnQgb2YgdGhhdCBkYXlcblxuICBjb25zdCBuZXh0UGVyaW9kRW5kRGF0ZSA9IG5ldyBEYXRlKG5leHRQZXJpb2RTdGFydERhdGUpO1xuICBuZXh0UGVyaW9kRW5kRGF0ZS5zZXREYXRlKG5leHRQZXJpb2RTdGFydERhdGUuZ2V0RGF0ZSgpICsgNik7IC8vIERlZmF1bHQgdG8gYSA3LWRheSBvdXRsb29rXG4gIG5leHRQZXJpb2RFbmREYXRlLnNldEhvdXJzKDIzLCA1OSwgNTksIDk5OSk7XG5cbiAgcmV0dXJuIHtcbiAgICBzdGFydERhdGUsXG4gICAgZW5kRGF0ZSxcbiAgICBuZXh0UGVyaW9kU3RhcnREYXRlLFxuICAgIG5leHRQZXJpb2RFbmREYXRlLFxuICAgIGRpc3BsYXlSYW5nZSxcbiAgfTtcbn1cblxuaW1wb3J0IHtcbiAgV2Vla2x5RGlnZXN0RGF0YSxcbiAgR2VuZXJhdGVXZWVrbHlEaWdlc3RSZXNwb25zZSxcbiAgTm90aW9uVGFza1N0YXR1cywgLy8gQWxyZWFkeSBpbXBvcnRlZFxufSBmcm9tICcuLi8uLi90eXBlcyc7XG5cbmNvbnN0IE1BWF9ESUdFU1RfSVRFTVMgPSA1OyAvLyBNYXggaXRlbXMgZm9yIGNvbXBsZXRlZCB0YXNrcywgbWVldGluZ3MsIGV0Yy5cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUdlbmVyYXRlV2Vla2x5RGlnZXN0KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZVBlcmlvZElucHV0PzogJ3RoaXMgd2VlaycgfCAnbGFzdCB3ZWVrJyB8IHN0cmluZ1xuKTogUHJvbWlzZTxHZW5lcmF0ZVdlZWtseURpZ2VzdFJlc3BvbnNlPiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBbaGFuZGxlR2VuZXJhdGVXZWVrbHlEaWdlc3RdIFVzZXI6ICR7dXNlcklkfSwgVGltZSBQZXJpb2Q6IFwiJHt0aW1lUGVyaW9kSW5wdXR9XCJgXG4gICk7XG5cbiAgY29uc3Qge1xuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlLFxuICAgIG5leHRQZXJpb2RTdGFydERhdGUsXG4gICAgbmV4dFBlcmlvZEVuZERhdGUsXG4gICAgZGlzcGxheVJhbmdlLFxuICB9ID0gZGV0ZXJtaW5lRGF0ZVJhbmdlKHRpbWVQZXJpb2RJbnB1dCk7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBbaGFuZGxlR2VuZXJhdGVXZWVrbHlEaWdlc3RdIERldGVybWluZWQgZGF0ZSByYW5nZTogJHtzdGFydERhdGUudG9JU09TdHJpbmcoKX0gdG8gJHtlbmREYXRlLnRvSVNPU3RyaW5nKCl9YFxuICApO1xuICBjb25zb2xlLmxvZyhcbiAgICBgW2hhbmRsZUdlbmVyYXRlV2Vla2x5RGlnZXN0XSBOZXh0IHBlcmlvZCByYW5nZTogJHtuZXh0UGVyaW9kU3RhcnREYXRlLnRvSVNPU3RyaW5nKCl9IHRvICR7bmV4dFBlcmlvZEVuZERhdGUudG9JU09TdHJpbmcoKX1gXG4gICk7XG5cbiAgY29uc3QgZGlnZXN0RGF0YTogV2Vla2x5RGlnZXN0RGF0YSA9IHtcbiAgICBwZXJpb2RTdGFydDogc3RhcnREYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgcGVyaW9kRW5kOiBlbmREYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgY29tcGxldGVkVGFza3M6IFtdLFxuICAgIGF0dGVuZGVkTWVldGluZ3M6IFtdLFxuICAgIHVwY29taW5nQ3JpdGljYWxUYXNrczogW10sXG4gICAgdXBjb21pbmdDcml0aWNhbE1lZXRpbmdzOiBbXSxcbiAgfTtcbiAgbGV0IGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyA9ICcnO1xuXG4gIGNvbnN0IG5vdGlvblRhc2tzRGJJZCA9IHByb2Nlc3MuZW52LkFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEO1xuXG4gIC8vIDEuIEdhdGhlciBDb21wbGV0ZWQgVGFza3NcbiAgaWYgKCFub3Rpb25UYXNrc0RiSWQpIHtcbiAgICBjb25zb2xlLndhcm4oXG4gICAgICAnW2hhbmRsZUdlbmVyYXRlV2Vla2x5RGlnZXN0XSBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCBpcyBub3Qgc2V0LiBTa2lwcGluZyBjb21wbGV0ZWQgdGFzayBzZWFyY2guJ1xuICAgICk7XG4gICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9XG4gICAgICAnTm90aW9uIHRhc2tzIGRhdGFiYXNlIElEIG5vdCBjb25maWd1cmVkIGZvciBjb21wbGV0ZWQgdGFza3MuICc7XG4gIH0gZWxzZSB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGNvbXBsZXRlZFRhc2tQYXJhbXMgPSB7XG4gICAgICAgIHN0YXR1czogJ0RvbmUnIGFzIE5vdGlvblRhc2tTdGF0dXMsXG4gICAgICAgIC8vIE5PVEUgb24gZmlsdGVyaW5nIGNvbXBsZXRlZCB0YXNrcyBieSBkYXRlOlxuICAgICAgICAvLyBJZGVhbGx5LCBgcXVlcnlOb3Rpb25UYXNrc2Agd291bGQgc3VwcG9ydCBmaWx0ZXJpbmcgYnkgYSBjdXN0b20gXCJDb21wbGV0ZWQgQXRcIiBkYXRlIHByb3BlcnR5XG4gICAgICAgIC8vIGZyb20gdGhlIE5vdGlvbiBkYXRhYmFzZS4gVGhpcyB3b3VsZCBiZSB0aGUgbW9zdCBhY2N1cmF0ZSB3YXkgdG8gZmluZCB0YXNrcyBjb21wbGV0ZWRcbiAgICAgICAgLy8gd2l0aGluIHRoZSBzcGVjaWZpZWQgYHN0YXJ0RGF0ZWAgYW5kIGBlbmREYXRlYC5cbiAgICAgICAgLy9cbiAgICAgICAgLy8gQ3VycmVudCBWMSBBcHByb3hpbWF0aW9uOlxuICAgICAgICAvLyAxLiBGZXRjaCB0YXNrcyB3aXRoIHN0YXR1cyBcIkRvbmVcIi5cbiAgICAgICAgLy8gMi4gRmlsdGVyIHRoZXNlIHRhc2tzIGxvY2FsbHkgYmFzZWQgb24gYHRhc2subGFzdF9lZGl0ZWRfdGltZWAuXG4gICAgICAgIC8vIFRoaXMgaXMgYW4gYXBwcm94aW1hdGlvbiBiZWNhdXNlIGBsYXN0X2VkaXRlZF90aW1lYCByZWZsZWN0cyB0aGUgbGFzdCB0aW1lIEFOWSBwcm9wZXJ0eVxuICAgICAgICAvLyBvZiB0aGUgdGFzayB3YXMgY2hhbmdlZCwgbm90IG5lY2Vzc2FyaWx5IGl0cyBjb21wbGV0aW9uIHRpbWUuXG4gICAgICAgIC8vIEEgdGFzayBtYXJrZWQgXCJEb25lXCIgbG9uZyBhZ28gYnV0IGVkaXRlZCByZWNlbnRseSBmb3IgYSBtaW5vciBjb3JyZWN0aW9uIHdvdWxkIGFwcGVhci5cbiAgICAgICAgLy8gQSB0YXNrIGNvbXBsZXRlZCB3aXRoaW4gdGhlIHBlcmlvZCBidXQgbmV2ZXIgdG91Y2hlZCBhZ2FpbiBtaWdodCBiZSBtaXNzZWQgaWYgaXRzXG4gICAgICAgIC8vIGBsYXN0X2VkaXRlZF90aW1lYCBpcyBvbGRlciBkdWUgdG8gYHF1ZXJ5Tm90aW9uVGFza3NgIGludGVybmFsIGxpbWl0cyBvciBzb3J0aW5nIGJlZm9yZSB0aGlzIGxvY2FsIGZpbHRlci5cbiAgICAgICAgLy9cbiAgICAgICAgLy8gVG8gaW1wcm92ZSBhY2N1cmFjeSBpbiBmdXR1cmU6XG4gICAgICAgIC8vIC0gQmFja2VuZCBFbmhhbmNlbWVudDogTW9kaWZ5IGBxdWVyeU5vdGlvblRhc2tzYCAoYW5kIGl0cyBQeXRob24gYmFja2VuZCBpZiBhcHBsaWNhYmxlKVxuICAgICAgICAvLyAgIHRvIGFjY2VwdCBgY29tcGxldGVkX2F0X2FmdGVyOiBzdHJpbmdgIGFuZCBgY29tcGxldGVkX2F0X2JlZm9yZTogc3RyaW5nYCBwYXJhbWV0ZXJzXG4gICAgICAgIC8vICAgdGhhdCBmaWx0ZXIgb24gYSBzcGVjaWZpYyBcIkNvbXBsZXRlZCBBdFwiIGRhdGUgcHJvcGVydHkgaW4gdGhlIE5vdGlvbiBEQi5cbiAgICAgICAgLy8gLSBEb2N1bWVudGF0aW9uOiBBZHZpc2UgdXNlcnMgdG8gbWFpbnRhaW4gYSBcIkNvbXBsZXRlZCBBdFwiIGRhdGUgcHJvcGVydHkgaW4gdGhlaXIgdGFza3MgREIuXG4gICAgICAgIGxpbWl0OiBNQVhfRElHRVNUX0lURU1TICogMywgLy8gRmV0Y2ggbW9yZSB0byBpbmNyZWFzZSBjaGFuY2Ugb2YgY2F0Y2hpbmcgcmVsZXZhbnQgcmVjZW50bHkgZWRpdGVkIFwiRG9uZVwiIHRhc2tzLlxuICAgICAgICBub3Rpb25UYXNrc0RiSWQ6IG5vdGlvblRhc2tzRGJJZCxcbiAgICAgIH07XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFtoYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdF0gUXVlcnlpbmcgY29tcGxldGVkIHRhc2tzIHdpdGggcGFyYW1zOmAsXG4gICAgICAgIGNvbXBsZXRlZFRhc2tQYXJhbXNcbiAgICAgICk7XG4gICAgICBjb25zdCB0YXNrUmVzcG9uc2UgPSBhd2FpdCBxdWVyeU5vdGlvblRhc2tzKHVzZXJJZCwgY29tcGxldGVkVGFza1BhcmFtcyk7XG4gICAgICBpZiAodGFza1Jlc3BvbnNlLnN1Y2Nlc3MgJiYgdGFza1Jlc3BvbnNlLnRhc2tzKSB7XG4gICAgICAgIGRpZ2VzdERhdGEuY29tcGxldGVkVGFza3MgPSB0YXNrUmVzcG9uc2UudGFza3NcbiAgICAgICAgICAuZmlsdGVyKCh0YXNrKSA9PiB7XG4gICAgICAgICAgICAvLyBFbnN1cmUgYHRhc2subGFzdF9lZGl0ZWRfdGltZWAgaXMgYXZhaWxhYmxlIG9uIHRoZSBOb3Rpb25UYXNrIHR5cGUgZnJvbSBgcXVlcnlOb3Rpb25UYXNrc2AuXG4gICAgICAgICAgICAvLyBJZiBgdGFzay5sYXN0X2VkaXRlZF90aW1lYCBpcyBub3QgcmVsaWFibHkgcG9wdWxhdGVkIGJ5IGBxdWVyeU5vdGlvblRhc2tzYCBmcm9tIE5vdGlvbidzIEFQSSxcbiAgICAgICAgICAgIC8vIHRoaXMgZmlsdGVyaW5nIHdpbGwgYmUgaW5hY2N1cmF0ZS4gRGVmYXVsdGluZyB0byBgdGFzay5jcmVhdGVkRGF0ZWAgaXMgYSBwb29yIGZhbGxiYWNrIGZvciBjb21wbGV0aW9uLlxuICAgICAgICAgICAgY29uc3QgcmVsZXZhbnREYXRlID0gdGFzay5sYXN0X2VkaXRlZF90aW1lXG4gICAgICAgICAgICAgID8gbmV3IERhdGUodGFzay5sYXN0X2VkaXRlZF90aW1lKVxuICAgICAgICAgICAgICA6IG51bGw7XG4gICAgICAgICAgICBpZiAoIXJlbGV2YW50RGF0ZSkge1xuICAgICAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICAgICAgYFtoYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdF0gVGFzayBJRCAke3Rhc2suaWR9IGhhcyBubyBsYXN0X2VkaXRlZF90aW1lLiBDYW5ub3QgYWNjdXJhdGVseSBkZXRlcm1pbmUgaWYgY29tcGxldGVkIGluIHBlcmlvZC5gXG4gICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIHJldHVybiByZWxldmFudERhdGUgPj0gc3RhcnREYXRlICYmIHJlbGV2YW50RGF0ZSA8PSBlbmREYXRlO1xuICAgICAgICAgIH0pXG4gICAgICAgICAgLnNsaWNlKDAsIE1BWF9ESUdFU1RfSVRFTVMpO1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBgW2hhbmRsZUdlbmVyYXRlV2Vla2x5RGlnZXN0XSBGb3VuZCAke2RpZ2VzdERhdGEuY29tcGxldGVkVGFza3MubGVuZ3RofSBjb21wbGV0ZWQgdGFza3MgaW4gcGVyaW9kIChhZnRlciBkYXRlIGZpbHRlcmluZykuYFxuICAgICAgICApO1xuICAgICAgfSBlbHNlIGlmICghdGFza1Jlc3BvbnNlLnN1Y2Nlc3MpIHtcbiAgICAgICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9IGBDb3VsZCBub3QgZmV0Y2ggY29tcGxldGVkIHRhc2tzOiAke3Rhc2tSZXNwb25zZS5lcnJvcn0uIGA7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnW2hhbmRsZUdlbmVyYXRlV2Vla2x5RGlnZXN0XSBFcnJvciBmZXRjaGluZyBjb21wbGV0ZWQgdGFza3M6JyxcbiAgICAgICAgZS5tZXNzYWdlLFxuICAgICAgICBlLnN0YWNrXG4gICAgICApO1xuICAgICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9XG4gICAgICAgICdFcnJvciBvY2N1cnJlZCB3aGlsZSBmZXRjaGluZyBjb21wbGV0ZWQgdGFza3MuICc7XG4gICAgfVxuICB9XG5cbiAgLy8gMi4gR2F0aGVyIEtleSBNZWV0aW5ncyBBdHRlbmRlZFxuICB0cnkge1xuICAgIC8vIGxpc3RVcGNvbWluZ0V2ZW50cyBuZWVkcyB0byBiZSBhZGFwdGVkIHRvIHF1ZXJ5IHBhc3QgZXZlbnRzIGZvciBhIGRhdGUgcmFuZ2UuXG4gICAgLy8gVGhpcyBtaWdodCBtZWFuIGFkZGluZyBzdGFydERhdGUgYW5kIGVuZERhdGUgcGFyYW1ldGVycyB0byBsaXN0VXBjb21pbmdFdmVudHMuXG4gICAgLy8gRm9yIG5vdywgYXNzdW1lIGl0IGNhbiB0YWtlIGEgZGF0ZSByYW5nZSAoY29uY2VwdHVhbCkuXG4gICAgLy8gbGlzdFVwY29taW5nRXZlbnRzKHVzZXJJZCwgbGltaXQsIHRpbWVNaW4sIHRpbWVNYXgpXG4gICAgY29uc3QgbWVldGluZ3NBdHRlbmRlZCA9IGF3YWl0IGxpc3RVcGNvbWluZ0V2ZW50cyhcbiAgICAgIHVzZXJJZCxcbiAgICAgIE1BWF9ESUdFU1RfSVRFTVMgKiAyLFxuICAgICAgc3RhcnREYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgICBlbmREYXRlLnRvSVNPU3RyaW5nKClcbiAgICApO1xuICAgIGlmIChtZWV0aW5nc0F0dGVuZGVkKSB7XG4gICAgICAvLyBGdXJ0aGVyIGZpbHRlciBmb3IgXCJzaWduaWZpY2FudFwiIG1lZXRpbmdzIGlmIG5lZWRlZCAoZS5nLiwgZHVyYXRpb24gPiAzMG1pbiwgbm90IFwiRm9jdXMgVGltZVwiKVxuICAgICAgZGlnZXN0RGF0YS5hdHRlbmRlZE1lZXRpbmdzID0gbWVldGluZ3NBdHRlbmRlZFxuICAgICAgICAuZmlsdGVyKChldmVudCkgPT4ge1xuICAgICAgICAgIGNvbnN0IGR1cmF0aW9uTXMgPVxuICAgICAgICAgICAgbmV3IERhdGUoZXZlbnQuZW5kVGltZSkuZ2V0VGltZSgpIC1cbiAgICAgICAgICAgIG5ldyBEYXRlKGV2ZW50LnN0YXJ0VGltZSkuZ2V0VGltZSgpO1xuICAgICAgICAgIGNvbnN0IGR1cmF0aW9uTWludXRlcyA9IGR1cmF0aW9uTXMgLyAoMTAwMCAqIDYwKTtcbiAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgZHVyYXRpb25NaW51dGVzID4gMjUgJiZcbiAgICAgICAgICAgICFldmVudC5zdW1tYXJ5LnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ2ZvY3VzIHRpbWUnKVxuICAgICAgICAgICk7IC8vIEV4YW1wbGUgZmlsdGVyXG4gICAgICAgIH0pXG4gICAgICAgIC5zbGljZSgwLCBNQVhfRElHRVNUX0lURU1TKTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgW2hhbmRsZUdlbmVyYXRlV2Vla2x5RGlnZXN0XSBGb3VuZCAke2RpZ2VzdERhdGEuYXR0ZW5kZWRNZWV0aW5ncy5sZW5ndGh9IGF0dGVuZGVkIG1lZXRpbmdzLmBcbiAgICAgICk7XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ1toYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdF0gRXJyb3IgZmV0Y2hpbmcgYXR0ZW5kZWQgbWVldGluZ3M6JyxcbiAgICAgIGUubWVzc2FnZSxcbiAgICAgIGUuc3RhY2tcbiAgICApO1xuICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPVxuICAgICAgJ0Vycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIGF0dGVuZGVkIG1lZXRpbmdzLiAnO1xuICB9XG5cbiAgLy8gMy4gSWRlbnRpZnkgVXBjb21pbmcgQ3JpdGljYWwgVGFza3NcbiAgaWYgKCFub3Rpb25UYXNrc0RiSWQpIHtcbiAgICBjb25zb2xlLndhcm4oXG4gICAgICAnW2hhbmRsZUdlbmVyYXRlV2Vla2x5RGlnZXN0XSBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCBpcyBub3Qgc2V0LiBTa2lwcGluZyB1cGNvbWluZyB0YXNrIHNlYXJjaC4nXG4gICAgKTtcbiAgICBhY2N1bXVsYXRlZEVycm9yTWVzc2FnZXMgKz1cbiAgICAgICdOb3Rpb24gdGFza3MgZGF0YWJhc2UgSUQgbm90IGNvbmZpZ3VyZWQgZm9yIHVwY29taW5nIHRhc2tzLiAnO1xuICB9IGVsc2Uge1xuICAgIHRyeSB7XG4gICAgICBjb25zdCB1cGNvbWluZ1Rhc2tQYXJhbXMgPSB7XG4gICAgICAgIC8vIFF1ZXJ5IHRhc2tzIGR1ZSBpbiB0aGUgbmV4dCBwZXJpb2RcbiAgICAgICAgZHVlRGF0ZUFmdGVyOiBuZXh0UGVyaW9kU3RhcnREYXRlLnRvSVNPU3RyaW5nKCkuc3BsaXQoJ1QnKVswXSwgLy8gWVlZWS1NTS1ERFxuICAgICAgICBkdWVEYXRlQmVmb3JlOiBuZXh0UGVyaW9kRW5kRGF0ZS50b0lTT1N0cmluZygpLnNwbGl0KCdUJylbMF0sIC8vIFlZWVktTU0tRERcbiAgICAgICAgcHJpb3JpdHk6ICdIaWdoJyBhcyBOb3Rpb25UYXNrUHJpb3JpdHksIC8vIEV4YW1wbGU6IG9ubHkgaGlnaCBwcmlvcml0eVxuICAgICAgICBzdGF0dXNfbm90X2VxdWFsczogWydEb25lJywgJ0NhbmNlbGxlZCddIGFzIGFueSwgLy8gRXhjbHVkZSBjb21wbGV0ZWQvY2FuY2VsbGVkXG4gICAgICAgIGxpbWl0OiBNQVhfRElHRVNUX0lURU1TLFxuICAgICAgICBub3Rpb25UYXNrc0RiSWQ6IG5vdGlvblRhc2tzRGJJZCxcbiAgICAgIH07XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFtoYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdF0gUXVlcnlpbmcgdXBjb21pbmcgY3JpdGljYWwgdGFza3Mgd2l0aCBwYXJhbXM6YCxcbiAgICAgICAgdXBjb21pbmdUYXNrUGFyYW1zXG4gICAgICApO1xuICAgICAgY29uc3QgdXBjb21pbmdUYXNrUmVzcG9uc2UgPSBhd2FpdCBxdWVyeU5vdGlvblRhc2tzKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIHVwY29taW5nVGFza1BhcmFtc1xuICAgICAgKTtcbiAgICAgIGlmICh1cGNvbWluZ1Rhc2tSZXNwb25zZS5zdWNjZXNzICYmIHVwY29taW5nVGFza1Jlc3BvbnNlLnRhc2tzKSB7XG4gICAgICAgIGRpZ2VzdERhdGEudXBjb21pbmdDcml0aWNhbFRhc2tzID0gdXBjb21pbmdUYXNrUmVzcG9uc2UudGFza3Muc2xpY2UoXG4gICAgICAgICAgMCxcbiAgICAgICAgICBNQVhfRElHRVNUX0lURU1TXG4gICAgICAgICk7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGBbaGFuZGxlR2VuZXJhdGVXZWVrbHlEaWdlc3RdIEZvdW5kICR7ZGlnZXN0RGF0YS51cGNvbWluZ0NyaXRpY2FsVGFza3MubGVuZ3RofSB1cGNvbWluZyBjcml0aWNhbCB0YXNrcy5gXG4gICAgICAgICk7XG4gICAgICB9IGVsc2UgaWYgKCF1cGNvbWluZ1Rhc2tSZXNwb25zZS5zdWNjZXNzKSB7XG4gICAgICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPSBgQ291bGQgbm90IGZldGNoIHVwY29taW5nIHRhc2tzOiAke3VwY29taW5nVGFza1Jlc3BvbnNlLmVycm9yfS4gYDtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICdbaGFuZGxlR2VuZXJhdGVXZWVrbHlEaWdlc3RdIEVycm9yIGZldGNoaW5nIHVwY29taW5nIHRhc2tzOicsXG4gICAgICAgIGUubWVzc2FnZSxcbiAgICAgICAgZS5zdGFja1xuICAgICAgKTtcbiAgICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPVxuICAgICAgICAnRXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgdXBjb21pbmcgdGFza3MuICc7XG4gICAgfVxuICB9XG5cbiAgLy8gNC4gSWRlbnRpZnkgVXBjb21pbmcgQ3JpdGljYWwgTWVldGluZ3NcbiAgdHJ5IHtcbiAgICAvLyBsaXN0VXBjb21pbmdFdmVudHMgZm9yIHRoZSBuZXh0IHBlcmlvZFxuICAgIGNvbnN0IHVwY29taW5nTWVldGluZ3MgPSBhd2FpdCBsaXN0VXBjb21pbmdFdmVudHMoXG4gICAgICB1c2VySWQsXG4gICAgICBNQVhfRElHRVNUX0lURU1TICogMixcbiAgICAgIG5leHRQZXJpb2RTdGFydERhdGUudG9JU09TdHJpbmcoKSxcbiAgICAgIG5leHRQZXJpb2RFbmREYXRlLnRvSVNPU3RyaW5nKClcbiAgICApO1xuICAgIGlmICh1cGNvbWluZ01lZXRpbmdzKSB7XG4gICAgICAvLyBGaWx0ZXIgZm9yIFwic2lnbmlmaWNhbnRcIiBtZWV0aW5nc1xuICAgICAgZGlnZXN0RGF0YS51cGNvbWluZ0NyaXRpY2FsTWVldGluZ3MgPSB1cGNvbWluZ01lZXRpbmdzXG4gICAgICAgIC5maWx0ZXIoKGV2ZW50KSA9PiB7XG4gICAgICAgICAgY29uc3QgZHVyYXRpb25NcyA9XG4gICAgICAgICAgICBuZXcgRGF0ZShldmVudC5lbmRUaW1lKS5nZXRUaW1lKCkgLVxuICAgICAgICAgICAgbmV3IERhdGUoZXZlbnQuc3RhcnRUaW1lKS5nZXRUaW1lKCk7XG4gICAgICAgICAgY29uc3QgZHVyYXRpb25NaW51dGVzID0gZHVyYXRpb25NcyAvICgxMDAwICogNjApO1xuICAgICAgICAgIC8vIEV4YW1wbGU6IGR1cmF0aW9uID4gNDUgbWluIE9SIGhhcyBleHRlcm5hbCBhdHRlbmRlZXMgKGlmIGF0dGVuZGVlIGRhdGEgaXMgcmljaCBlbm91Z2gpXG4gICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIGR1cmF0aW9uTWludXRlcyA+IDQ1IHx8XG4gICAgICAgICAgICAoZXZlbnQuYXR0ZW5kZWVzICYmXG4gICAgICAgICAgICAgIGV2ZW50LmF0dGVuZGVlcy5zb21lKFxuICAgICAgICAgICAgICAgIChhKSA9PiBhLmVtYWlsICYmICFhLmVtYWlsLmVuZHNXaXRoKCdAeW91cmNvbXBhbnkuY29tJylcbiAgICAgICAgICAgICAgKSlcbiAgICAgICAgICApO1xuICAgICAgICB9KVxuICAgICAgICAuc2xpY2UoMCwgTUFYX0RJR0VTVF9JVEVNUyk7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFtoYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdF0gRm91bmQgJHtkaWdlc3REYXRhLnVwY29taW5nQ3JpdGljYWxNZWV0aW5ncy5sZW5ndGh9IHVwY29taW5nIGNyaXRpY2FsIG1lZXRpbmdzLmBcbiAgICAgICk7XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ1toYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdF0gRXJyb3IgZmV0Y2hpbmcgdXBjb21pbmcgbWVldGluZ3M6JyxcbiAgICAgIGUubWVzc2FnZSxcbiAgICAgIGUuc3RhY2tcbiAgICApO1xuICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPVxuICAgICAgJ0Vycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIHVwY29taW5nIG1lZXRpbmdzLiAnO1xuICB9XG5cbiAgaWYgKGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcykge1xuICAgIGRpZ2VzdERhdGEuZXJyb3JNZXNzYWdlID0gYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzLnRyaW0oKTtcbiAgfVxuXG4gIC8vIENvbnN0cnVjdCBmb3JtYXR0ZWQgc3VtbWFyeSAobW92ZWQgdG8gaGFuZGxlci50cyBmb3IgZmluYWwgcHJlc2VudGF0aW9uKVxuICAvLyBUaGlzIHNraWxsIHdpbGwgcHJpbWFyaWx5IHJldHVybiB0aGUgZGF0YS4gVGhlIGhhbmRsZXIgZm9ybWF0cyBpdC5cbiAgY29uc3QgZm9ybWF0dGVkU3VtbWFyeSA9IGBEaWdlc3QgZm9yICR7ZGlzcGxheVJhbmdlfSAoZGF0YSBwcmVwYXJlZCwgZm9ybWF0dGluZyBpbiBoYW5kbGVyKS5gOyAvLyBQbGFjZWhvbGRlclxuXG4gIHJldHVybiB7XG4gICAgb2s6IHRydWUsXG4gICAgZGF0YToge1xuICAgICAgZGlnZXN0OiBkaWdlc3REYXRhLFxuICAgICAgZm9ybWF0dGVkU3VtbWFyeSwgLy8gVGhpcyB3aWxsIGJlIHByb3Blcmx5IGJ1aWx0IGluIGhhbmRsZXIudHNcbiAgICB9LFxuICB9O1xufVxuXG4vLyAtLS0gSW50ZWxsaWdlbnQgRm9sbG93LXVwIFN1Z2dlc3RlciBTa2lsbCAtLS1cblxuaW1wb3J0IHtcbiAgU3VnZ2VzdEZvbGxvd1Vwc1Jlc3BvbnNlLFxuICBGb2xsb3dVcFN1Z2dlc3Rpb25EYXRhLFxuICBQb3RlbnRpYWxGb2xsb3dVcCxcbiAgUG90ZW50aWFsRm9sbG93VXBUeXBlLFxuICBFeHRyYWN0ZWRGb2xsb3dVcEl0ZW1zLCAvLyBDb25jZXB0dWFsIHR5cGUgZm9yIExMTSBvdXRwdXRcbiAgLy8gTm90aW9uVGFzaywgQ2FsZW5kYXJFdmVudCBhbHJlYWR5IGltcG9ydGVkXG59IGZyb20gJy4uLy4uL3R5cGVzJztcbmltcG9ydCB7IGhhbmRsZVNlbWFudGljU2VhcmNoTWVldGluZ05vdGVzU2tpbGwgfSBmcm9tICcuL3NlbWFudGljU2VhcmNoU2tpbGxzJzsgLy8gSWYgdXNlZCBmb3IgdHJhbnNjcmlwdCByZXRyaWV2YWxcbi8vIENvbmNlcHR1YWwgaW1wb3J0IGZvciB0aGUgTExNIHV0aWxpdHlcbmltcG9ydCB7IGFuYWx5emVUZXh0Rm9yRm9sbG93VXBzIH0gZnJvbSAnLi9sbG1VdGlsaXRpZXMnOyAvLyBBc3N1bWluZyB0aGlzIGZpbGUgd2lsbCBiZSBjcmVhdGVkXG5cbmNvbnN0IE1BWF9GT0xMT1dfVVBTX1RPX1NVR0dFU1QgPSA3O1xuY29uc3QgTUFYX0NPTlRFWFRfU0VBUkNIX1JFU1VMVFMgPSAxOyAvLyBIb3cgbWFueSBOb3Rpb24gcGFnZXMgdG8gZmV0Y2ggZm9yIGNvbnRleHRcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVN1Z2dlc3RGb2xsb3dVcHMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjb250ZXh0SWRlbnRpZmllcjogc3RyaW5nLFxuICBjb250ZXh0VHlwZT86ICdtZWV0aW5nJyB8ICdwcm9qZWN0JyB8IHN0cmluZ1xuKTogUHJvbWlzZTxTdWdnZXN0Rm9sbG93VXBzUmVzcG9uc2U+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYFtoYW5kbGVTdWdnZXN0Rm9sbG93VXBzXSBVc2VyOiAke3VzZXJJZH0sIENvbnRleHQ6IFwiJHtjb250ZXh0SWRlbnRpZmllcn1cIiwgVHlwZTogXCIke2NvbnRleHRUeXBlfVwiYFxuICApO1xuXG4gIGxldCBzb3VyY2VEb2N1bWVudFRleHQ6IHN0cmluZyB8IG51bGwgPSBudWxsO1xuICBsZXQgc291cmNlRG9jdW1lbnRUaXRsZSA9IGNvbnRleHRJZGVudGlmaWVyOyAvLyBEZWZhdWx0IHRpdGxlXG4gIGxldCBzb3VyY2VEb2N1bWVudFVybDogc3RyaW5nIHwgdW5kZWZpbmVkO1xuICBsZXQgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzID0gJyc7XG5cbiAgY29uc3QgZm9sbG93VXBEYXRhOiBGb2xsb3dVcFN1Z2dlc3Rpb25EYXRhID0ge1xuICAgIGNvbnRleHROYW1lOiBjb250ZXh0SWRlbnRpZmllcixcbiAgICBzdWdnZXN0aW9uczogW10sXG4gIH07XG5cbiAgLy8gMS4gSWRlbnRpZnkgJiBSZXRyaWV2ZSBDb250ZXh0XG4gIHRyeSB7XG4gICAgaWYgKFxuICAgICAgY29udGV4dFR5cGUgPT09ICdtZWV0aW5nJyB8fFxuICAgICAgKCFjb250ZXh0VHlwZSAmJlxuICAgICAgICAoY29udGV4dElkZW50aWZpZXIudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnbWVldGluZycpIHx8XG4gICAgICAgICAgY29udGV4dElkZW50aWZpZXIudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnY2FsbCcpIHx8XG4gICAgICAgICAgY29udGV4dElkZW50aWZpZXIudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnc3luYycpIHx8XG4gICAgICAgICAgY29udGV4dElkZW50aWZpZXIudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnbGFzdCBtZWV0aW5nJykpKVxuICAgICkge1xuICAgICAgY29uc3QgbWVldGluZyA9IGF3YWl0IGZpbmRUYXJnZXRNZWV0aW5nKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNvbnRleHRJZGVudGlmaWVyLnJlcGxhY2UoL21lZXRpbmd8Y2FsbHxzeW5jL2ksICcnKS50cmltKClcbiAgICAgICk7IC8vIGZpbmRUYXJnZXRNZWV0aW5nIG1pZ2h0IG5lZWQgYWRqdXN0bWVudCBmb3IgXCJsYXN0IG1lZXRpbmdcIlxuICAgICAgaWYgKG1lZXRpbmcpIHtcbiAgICAgICAgc291cmNlRG9jdW1lbnRUaXRsZSA9IGBNZWV0aW5nOiAke21lZXRpbmcuc3VtbWFyeX0gb24gJHtuZXcgRGF0ZShtZWV0aW5nLnN0YXJ0VGltZSkudG9Mb2NhbGVEYXRlU3RyaW5nKCl9YDtcbiAgICAgICAgZm9sbG93VXBEYXRhLmNvbnRleHROYW1lID0gc291cmNlRG9jdW1lbnRUaXRsZTtcbiAgICAgICAgc291cmNlRG9jdW1lbnRVcmwgPSBtZWV0aW5nLmh0bWxMaW5rO1xuICAgICAgICAvLyBBdHRlbXB0IHRvIGdldCBub3Rlcy90cmFuc2NyaXB0IGZvciB0aGlzIG1lZXRpbmdcbiAgICAgICAgLy8gT3B0aW9uIEE6IFNlbWFudGljIHNlYXJjaCBpZiB0cmFuc2NyaXB0cyBhcmUgcHJvY2Vzc2VkXG4gICAgICAgIC8vIGNvbnN0IHNlYXJjaFJlc3BvbnNlID0gYXdhaXQgaGFuZGxlU2VtYW50aWNTZWFyY2hNZWV0aW5nTm90ZXNTa2lsbCh7IGNvbW1hbmQ6IFwic2VhcmNoX21lZXRpbmdfbm90ZXNcIiwgcGFyYW1zOiB7IHF1ZXJ5OiBgdHJhbnNjcmlwdCBmb3IgbWVldGluZyAke21lZXRpbmcuaWR9IE9SICR7bWVldGluZy5zdW1tYXJ5fWAsIGxpbWl0OiAxIH0sIHVzZXJfaWQ6IHVzZXJJZCwgcmF3X21lc3NhZ2U6IFwiXCJ9KTtcbiAgICAgICAgLy8gaWYgKHNlYXJjaFJlc3BvbnNlICYmICFzZWFyY2hSZXNwb25zZS5zdGFydHNXaXRoKFwiU29ycnlcIikgJiYgIXNlYXJjaFJlc3BvbnNlLnN0YXJ0c1dpdGgoXCJObyByZXN1bHRzXCIpKSB7XG4gICAgICAgIC8vICAgc291cmNlRG9jdW1lbnRUZXh0ID0gc2VhcmNoUmVzcG9uc2U7IC8vIEFzc3VtaW5nIGl0IHJldHVybnMgdGhlIHRleHRcbiAgICAgICAgLy8gfSBlbHNlIHsgLi4uIH1cbiAgICAgICAgLy8gT3B0aW9uIEI6IFNlYXJjaCBOb3Rpb24gZm9yIGxpbmtlZCBub3Rlc1xuICAgICAgICBjb25zdCBub3Rpb25RdWVyeSA9IGBub3RlcyBmb3IgbWVldGluZyBcIiR7bWVldGluZy5zdW1tYXJ5fVwiIGRhdGUgJHtuZXcgRGF0ZShtZWV0aW5nLnN0YXJ0VGltZSkudG9JU09TdHJpbmcoKS5zcGxpdCgnVCcpWzBdfWA7XG4gICAgICAgIGNvbnN0IG5vdGlvblNlYXJjaFJlc3BvbnNlID0gYXdhaXQgc2VhcmNoTm90aW9uUmF3KFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBub3Rpb25RdWVyeSxcbiAgICAgICAgICBNQVhfQ09OVEVYVF9TRUFSQ0hfUkVTVUxUU1xuICAgICAgICApO1xuICAgICAgICBpZiAobm90aW9uU2VhcmNoUmVzcG9uc2U/Lm9rICYmIG5vdGlvblNlYXJjaFJlc3BvbnNlLmRhdGE/LlswXSkge1xuICAgICAgICAgIGNvbnN0IHBhZ2UgPSBub3Rpb25TZWFyY2hSZXNwb25zZS5kYXRhWzBdO1xuICAgICAgICAgIHNvdXJjZURvY3VtZW50VGV4dCA9IHBhZ2UuY29udGVudCB8fCBwYWdlLnRpdGxlIHx8ICcnOyAvLyBQcmVmZXIgZnVsbCBjb250ZW50IGlmIGF2YWlsYWJsZVxuICAgICAgICAgIHNvdXJjZURvY3VtZW50VGl0bGUgPSBwYWdlLnRpdGxlIHx8IHNvdXJjZURvY3VtZW50VGl0bGU7XG4gICAgICAgICAgc291cmNlRG9jdW1lbnRVcmwgPSBwYWdlLnVybCB8fCBzb3VyY2VEb2N1bWVudFVybDtcbiAgICAgICAgICBmb2xsb3dVcERhdGEuc291cmNlRG9jdW1lbnRTdW1tYXJ5ID0gYFVzaW5nIE5vdGlvbiBwYWdlOiBcIiR7c291cmNlRG9jdW1lbnRUaXRsZX1cImA7XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBgW2hhbmRsZVN1Z2dlc3RGb2xsb3dVcHNdIEZvdW5kIE5vdGlvbiBwYWdlIGZvciBtZWV0aW5nOiAke3NvdXJjZURvY3VtZW50VGl0bGV9YFxuICAgICAgICAgICk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9IGBDb3VsZCBub3QgZmluZCBzcGVjaWZpYyBub3Rlcy90cmFuc2NyaXB0IGZvciBtZWV0aW5nIFwiJHttZWV0aW5nLnN1bW1hcnl9XCIuIEFuYWx5c2lzIG1pZ2h0IGJlIGxlc3MgYWNjdXJhdGUuIGA7XG4gICAgICAgICAgc291cmNlRG9jdW1lbnRUZXh0ID0gYE1lZXRpbmcgVGl0bGU6ICR7bWVldGluZy5zdW1tYXJ5fVxcbkRlc2NyaXB0aW9uOiAke21lZXRpbmcuZGVzY3JpcHRpb24gfHwgJ04vQSd9XFxuQXR0ZW5kZWVzOiAke21lZXRpbmcuYXR0ZW5kZWVzPy5tYXAoKGEpID0+IGEuZGlzcGxheU5hbWUgfHwgYS5lbWFpbCkuam9pbignLCAnKX1cXG5UaW1lOiAke21lZXRpbmcuc3RhcnRUaW1lfSAtICR7bWVldGluZy5lbmRUaW1lfWA7XG4gICAgICAgICAgZm9sbG93VXBEYXRhLnNvdXJjZURvY3VtZW50U3VtbWFyeSA9IGBVc2luZyBjYWxlbmRhciBldmVudCBkZXRhaWxzIGZvciBcIiR7bWVldGluZy5zdW1tYXJ5fVwiIGFzIGNvbnRleHQuYDtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgIGNvZGU6ICdDT05URVhUX05PVF9GT1VORCcsXG4gICAgICAgICAgICBtZXNzYWdlOiBgQ291bGQgbm90IGZpbmQgbWVldGluZzogJHtjb250ZXh0SWRlbnRpZmllcn1gLFxuICAgICAgICAgIH0sXG4gICAgICAgIH07XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChjb250ZXh0VHlwZSA9PT0gJ3Byb2plY3QnKSB7XG4gICAgICBmb2xsb3dVcERhdGEuY29udGV4dE5hbWUgPSBgUHJvamVjdDogJHtjb250ZXh0SWRlbnRpZmllcn1gO1xuICAgICAgY29uc3Qgbm90aW9uUXVlcnkgPSBgcHJvamVjdCBwbGFuIG9yIHN1bW1hcnkgZm9yIFwiJHtjb250ZXh0SWRlbnRpZmllcn1cImA7XG4gICAgICBjb25zdCBub3Rpb25TZWFyY2hSZXNwb25zZSA9IGF3YWl0IHNlYXJjaE5vdGlvblJhdyhcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBub3Rpb25RdWVyeSxcbiAgICAgICAgTUFYX0NPTlRFWFRfU0VBUkNIX1JFU1VMVFNcbiAgICAgICk7XG4gICAgICBpZiAobm90aW9uU2VhcmNoUmVzcG9uc2U/Lm9rICYmIG5vdGlvblNlYXJjaFJlc3BvbnNlLmRhdGE/LlswXSkge1xuICAgICAgICBjb25zdCBwYWdlID0gbm90aW9uU2VhcmNoUmVzcG9uc2UuZGF0YVswXTtcbiAgICAgICAgc291cmNlRG9jdW1lbnRUZXh0ID0gcGFnZS5jb250ZW50IHx8IHBhZ2UudGl0bGUgfHwgJyc7XG4gICAgICAgIHNvdXJjZURvY3VtZW50VGl0bGUgPSBwYWdlLnRpdGxlIHx8IHNvdXJjZURvY3VtZW50VGl0bGU7XG4gICAgICAgIHNvdXJjZURvY3VtZW50VXJsID0gcGFnZS51cmw7XG4gICAgICAgIGZvbGxvd1VwRGF0YS5zb3VyY2VEb2N1bWVudFN1bW1hcnkgPSBgVXNpbmcgTm90aW9uIHBhZ2U6IFwiJHtzb3VyY2VEb2N1bWVudFRpdGxlfVwiIGZvciBwcm9qZWN0IGNvbnRleHQuYDtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgYFtoYW5kbGVTdWdnZXN0Rm9sbG93VXBzXSBGb3VuZCBOb3Rpb24gcGFnZSBmb3IgcHJvamVjdDogJHtzb3VyY2VEb2N1bWVudFRpdGxlfWBcbiAgICAgICAgKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICBjb2RlOiAnQ09OVEVYVF9OT1RfRk9VTkQnLFxuICAgICAgICAgICAgbWVzc2FnZTogYENvdWxkIG5vdCBmaW5kIHByb2plY3QgZG9jdW1lbnQ6ICR7Y29udGV4dElkZW50aWZpZXJ9YCxcbiAgICAgICAgICB9LFxuICAgICAgICB9O1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICAvLyBHZW5lcmljIGNvbnRleHQgc2VhcmNoIGluIE5vdGlvbiBpZiB0eXBlIGlzIHVua25vd25cbiAgICAgIGNvbnN0IG5vdGlvblNlYXJjaFJlc3BvbnNlID0gYXdhaXQgc2VhcmNoTm90aW9uUmF3KFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNvbnRleHRJZGVudGlmaWVyLFxuICAgICAgICBNQVhfQ09OVEVYVF9TRUFSQ0hfUkVTVUxUU1xuICAgICAgKTtcbiAgICAgIGlmIChub3Rpb25TZWFyY2hSZXNwb25zZT8ub2sgJiYgbm90aW9uU2VhcmNoUmVzcG9uc2UuZGF0YT8uWzBdKSB7XG4gICAgICAgIGNvbnN0IHBhZ2UgPSBub3Rpb25TZWFyY2hSZXNwb25zZS5kYXRhWzBdO1xuICAgICAgICBzb3VyY2VEb2N1bWVudFRleHQgPSBwYWdlLmNvbnRlbnQgfHwgcGFnZS50aXRsZSB8fCAnJztcbiAgICAgICAgc291cmNlRG9jdW1lbnRUaXRsZSA9IHBhZ2UudGl0bGUgfHwgc291cmNlRG9jdW1lbnRUaXRsZTtcbiAgICAgICAgc291cmNlRG9jdW1lbnRVcmwgPSBwYWdlLnVybDtcbiAgICAgICAgZm9sbG93VXBEYXRhLmNvbnRleHROYW1lID0gYENvbnRleHQ6ICR7c291cmNlRG9jdW1lbnRUaXRsZX1gO1xuICAgICAgICBmb2xsb3dVcERhdGEuc291cmNlRG9jdW1lbnRTdW1tYXJ5ID0gYFVzaW5nIE5vdGlvbiBwYWdlOiBcIiR7c291cmNlRG9jdW1lbnRUaXRsZX1cIiBhcyBjb250ZXh0LmA7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgY29kZTogJ0NPTlRFWFRfTk9UX0ZPVU5EJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6IGBDb3VsZCBub3QgZmluZCBkb2N1bWVudCBmb3IgY29udGV4dDogJHtjb250ZXh0SWRlbnRpZmllcn1gLFxuICAgICAgICAgIH0sXG4gICAgICAgIH07XG4gICAgICB9XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ1toYW5kbGVTdWdnZXN0Rm9sbG93VXBzXSBFcnJvciByZXRyaWV2aW5nIGNvbnRleHQ6JyxcbiAgICAgIGUubWVzc2FnZSxcbiAgICAgIGUuc3RhY2tcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09OVEVYVF9SRVRSSUVWQUxfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRXJyb3IgcmV0cmlldmluZyBjb250ZXh0OiAke2UubWVzc2FnZX1gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgaWYgKCFzb3VyY2VEb2N1bWVudFRleHQgfHwgc291cmNlRG9jdW1lbnRUZXh0LnRyaW0oKS5sZW5ndGggPCA1MCkge1xuICAgIC8vIEFyYml0cmFyeSBtaW5pbXVtIGxlbmd0aFxuICAgIGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcyArPSBgVGhlIHNvdXJjZSBkb2N1bWVudCBmb3VuZCBmb3IgXCIke3NvdXJjZURvY3VtZW50VGl0bGV9XCIgd2FzIHRvbyBzaG9ydCBvciBlbXB0eSBmb3IgdXNlZnVsIGFuYWx5c2lzLiBgO1xuICAgIGZvbGxvd1VwRGF0YS5lcnJvck1lc3NhZ2UgPSBhY2N1bXVsYXRlZEVycm9yTWVzc2FnZXM7XG4gICAgLy8gU3RpbGwgcmV0dXJuIG9rOnRydWUsIGJ1dCB3aXRoIHRoZSBlcnJvciBtZXNzYWdlIGluIGRhdGEuXG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IGZvbGxvd1VwRGF0YSB9O1xuICB9XG5cbiAgLy8gMi4gQW5hbHl6ZSBDb250ZW50IHdpdGggTExNXG4gIGxldCBleHRyYWN0ZWRJdGVtczogRXh0cmFjdGVkRm9sbG93VXBJdGVtcyA9IHtcbiAgICBhY3Rpb25faXRlbXM6IFtdLFxuICAgIGRlY2lzaW9uczogW10sXG4gICAgcXVlc3Rpb25zOiBbXSxcbiAgfTtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbaGFuZGxlU3VnZ2VzdEZvbGxvd1Vwc10gQW5hbHl6aW5nIHRleHQgKGxlbmd0aDogJHtzb3VyY2VEb2N1bWVudFRleHQubGVuZ3RofSkgZm9yIFwiJHtzb3VyY2VEb2N1bWVudFRpdGxlfVwiIHdpdGggTExNLmBcbiAgICApO1xuICAgIGNvbnN0IGxsbUFuYWx5c2lzID0gYXdhaXQgYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMoXG4gICAgICBzb3VyY2VEb2N1bWVudFRleHQsXG4gICAgICBzb3VyY2VEb2N1bWVudFRpdGxlXG4gICAgKTsgLy8gQ29uY2VwdHVhbCBMTE0gY2FsbFxuICAgIGlmIChsbG1BbmFseXNpcy5lcnJvcikge1xuICAgICAgYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzICs9IGBMTE0gYW5hbHlzaXMgZmFpbGVkOiAke2xsbUFuYWx5c2lzLmVycm9yfS4gYDtcbiAgICB9IGVsc2Uge1xuICAgICAgZXh0cmFjdGVkSXRlbXMgPSBsbG1BbmFseXNpcy5leHRyYWN0ZWRJdGVtcztcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgW2hhbmRsZVN1Z2dlc3RGb2xsb3dVcHNdIExMTSBleHRyYWN0ZWQ6ICR7ZXh0cmFjdGVkSXRlbXMuYWN0aW9uX2l0ZW1zLmxlbmd0aH0gYWN0aW9ucywgJHtleHRyYWN0ZWRJdGVtcy5kZWNpc2lvbnMubGVuZ3RofSBkZWNpc2lvbnMsICR7ZXh0cmFjdGVkSXRlbXMucXVlc3Rpb25zLmxlbmd0aH0gcXVlc3Rpb25zLmBcbiAgICAgICk7XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ1toYW5kbGVTdWdnZXN0Rm9sbG93VXBzXSBFcnJvciBkdXJpbmcgTExNIGFuYWx5c2lzOicsXG4gICAgICBlLm1lc3NhZ2UsXG4gICAgICBlLnN0YWNrXG4gICAgKTtcbiAgICBhY2N1bXVsYXRlZEVycm9yTWVzc2FnZXMgKz0gYEVycm9yIGR1cmluZyBMTE0gYW5hbHlzaXM6ICR7ZS5tZXNzYWdlfS4gYDtcbiAgfVxuXG4gIGNvbnN0IG5vdGlvblRhc2tzRGJJZCA9IHByb2Nlc3MuZW52LkFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEO1xuXG4gIC8vIDMuIFByb2Nlc3MgRXh0cmFjdGVkIEl0ZW1zIGFuZCBDcm9zcy1SZWZlcmVuY2UgVGFza3NcbiAgY29uc3QgbWFwVG9Qb3RlbnRpYWxGb2xsb3dVcCA9IGFzeW5jIChcbiAgICBpdGVtOiB7IGRlc2NyaXB0aW9uOiBzdHJpbmc7IGFzc2lnbmVlPzogc3RyaW5nIH0sXG4gICAgdHlwZTogUG90ZW50aWFsRm9sbG93VXBUeXBlXG4gICk6IFByb21pc2U8UG90ZW50aWFsRm9sbG93VXA+ID0+IHtcbiAgICBjb25zdCBmb2xsb3dVcDogUG90ZW50aWFsRm9sbG93VXAgPSB7XG4gICAgICB0eXBlLFxuICAgICAgZGVzY3JpcHRpb246IGl0ZW0uZGVzY3JpcHRpb24sXG4gICAgICBzdWdnZXN0ZWRBc3NpZ25lZTogaXRlbS5hc3NpZ25lZSxcbiAgICAgIHNvdXJjZUNvbnRleHQ6IHNvdXJjZURvY3VtZW50VGl0bGUsXG4gICAgICBleGlzdGluZ1Rhc2tGb3VuZDogZmFsc2UsXG4gICAgfTtcblxuICAgIGlmICh0eXBlID09PSAnYWN0aW9uX2l0ZW0nICYmIG5vdGlvblRhc2tzRGJJZCkge1xuICAgICAgdHJ5IHtcbiAgICAgICAgLy8gU2VhcmNoIGZvciBleGlzdGluZyB0YXNrcyBtYXRjaGluZyBrZXl3b3JkcyBmcm9tIHRoaXMgYWN0aW9uIGl0ZW0ncyBkZXNjcmlwdGlvblxuICAgICAgICAvLyBUaGlzIHF1ZXJ5IG5lZWRzIHRvIGJlIGJyb2FkIGVub3VnaCB0byBmaW5kIHJlbGF0ZWQgdGFza3MuXG4gICAgICAgIGNvbnN0IHRhc2tRdWVyeSA9IHtcbiAgICAgICAgICBkZXNjcmlwdGlvbkNvbnRhaW5zOiBpdGVtLmRlc2NyaXB0aW9uLnN1YnN0cmluZygwLCA1MCksIC8vIEZpcnN0IDUwIGNoYXJzIGZvciBxdWVyeVxuICAgICAgICAgIHN0YXR1c19ub3RfZXF1YWxzOiBbJ0RvbmUnLCAnQ2FuY2VsbGVkJ10gYXMgYW55LFxuICAgICAgICAgIGxpbWl0OiAxLFxuICAgICAgICAgIG5vdGlvblRhc2tzRGJJZCxcbiAgICAgICAgfTtcbiAgICAgICAgY29uc3QgZXhpc3RpbmdUYXNrc1Jlc3BvbnNlID0gYXdhaXQgcXVlcnlOb3Rpb25UYXNrcyh1c2VySWQsIHRhc2tRdWVyeSk7XG4gICAgICAgIGlmIChcbiAgICAgICAgICBleGlzdGluZ1Rhc2tzUmVzcG9uc2Uuc3VjY2VzcyAmJlxuICAgICAgICAgIGV4aXN0aW5nVGFza3NSZXNwb25zZS50YXNrcy5sZW5ndGggPiAwXG4gICAgICAgICkge1xuICAgICAgICAgIGNvbnN0IGV4aXN0aW5nVGFzayA9IGV4aXN0aW5nVGFza3NSZXNwb25zZS50YXNrc1swXTtcbiAgICAgICAgICAvLyBBZGQgbW9yZSBzb3BoaXN0aWNhdGVkIG1hdGNoaW5nIGxvZ2ljIGhlcmUgaWYgbmVlZGVkIChlLmcuLCBzaW1pbGFyaXR5IHNjb3JlKVxuICAgICAgICAgIC8vIEZvciBWMSwgaWYgYW55IG5vbi1kb25lIHRhc2sgY29udGFpbnMgYSBzbmlwcGV0IG9mIHRoZSBhY3Rpb24sIG1hcmsgYXMgcG90ZW50aWFsbHkgZXhpc3RpbmcuXG4gICAgICAgICAgZm9sbG93VXAuZXhpc3RpbmdUYXNrRm91bmQgPSB0cnVlO1xuICAgICAgICAgIGZvbGxvd1VwLmV4aXN0aW5nVGFza0lkID0gZXhpc3RpbmdUYXNrLmlkO1xuICAgICAgICAgIGZvbGxvd1VwLmV4aXN0aW5nVGFza1VybCA9IGV4aXN0aW5nVGFzay51cmw7XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBgW2hhbmRsZVN1Z2dlc3RGb2xsb3dVcHNdIEZvdW5kIGV4aXN0aW5nIHRhc2sgJyR7ZXhpc3RpbmdUYXNrLmRlc2NyaXB0aW9ufScgZm9yIGFjdGlvbiBpdGVtICcke2l0ZW0uZGVzY3JpcHRpb259J2BcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoICh0YXNrRXJyb3I6IGFueSkge1xuICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgYFtoYW5kbGVTdWdnZXN0Rm9sbG93VXBzXSBFcnJvciBjaGVja2luZyBmb3IgZXhpc3RpbmcgdGFzayBmb3IgXCIke2l0ZW0uZGVzY3JpcHRpb259XCI6ICR7dGFza0Vycm9yLm1lc3NhZ2V9YFxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4gZm9sbG93VXA7XG4gIH07XG5cbiAgaWYgKGV4dHJhY3RlZEl0ZW1zLmFjdGlvbl9pdGVtcykge1xuICAgIGZvciAoY29uc3QgYWN0aW9uIG9mIGV4dHJhY3RlZEl0ZW1zLmFjdGlvbl9pdGVtcykge1xuICAgICAgZm9sbG93VXBEYXRhLnN1Z2dlc3Rpb25zLnB1c2goXG4gICAgICAgIGF3YWl0IG1hcFRvUG90ZW50aWFsRm9sbG93VXAoYWN0aW9uLCAnYWN0aW9uX2l0ZW0nKVxuICAgICAgKTtcbiAgICB9XG4gIH1cbiAgaWYgKGV4dHJhY3RlZEl0ZW1zLmRlY2lzaW9ucykge1xuICAgIGZvciAoY29uc3QgZGVjaXNpb24gb2YgZXh0cmFjdGVkSXRlbXMuZGVjaXNpb25zKSB7XG4gICAgICBmb2xsb3dVcERhdGEuc3VnZ2VzdGlvbnMucHVzaChcbiAgICAgICAgYXdhaXQgbWFwVG9Qb3RlbnRpYWxGb2xsb3dVcChkZWNpc2lvbiwgJ2RlY2lzaW9uJylcbiAgICAgICk7XG4gICAgfVxuICB9XG4gIGlmIChleHRyYWN0ZWRJdGVtcy5xdWVzdGlvbnMpIHtcbiAgICBmb3IgKGNvbnN0IHF1ZXN0aW9uIG9mIGV4dHJhY3RlZEl0ZW1zLnF1ZXN0aW9ucykge1xuICAgICAgZm9sbG93VXBEYXRhLnN1Z2dlc3Rpb25zLnB1c2goXG4gICAgICAgIGF3YWl0IG1hcFRvUG90ZW50aWFsRm9sbG93VXAocXVlc3Rpb24sICdxdWVzdGlvbicpXG4gICAgICApO1xuICAgIH1cbiAgfVxuXG4gIGZvbGxvd1VwRGF0YS5zdWdnZXN0aW9ucyA9IGZvbGxvd1VwRGF0YS5zdWdnZXN0aW9ucy5zbGljZShcbiAgICAwLFxuICAgIE1BWF9GT0xMT1dfVVBTX1RPX1NVR0dFU1RcbiAgKTtcblxuICBpZiAoYWNjdW11bGF0ZWRFcnJvck1lc3NhZ2VzKSB7XG4gICAgZm9sbG93VXBEYXRhLmVycm9yTWVzc2FnZSA9IGFjY3VtdWxhdGVkRXJyb3JNZXNzYWdlcy50cmltKCk7XG4gIH1cbiAgaWYgKGZvbGxvd1VwRGF0YS5zdWdnZXN0aW9ucy5sZW5ndGggPT09IDAgJiYgIWZvbGxvd1VwRGF0YS5lcnJvck1lc3NhZ2UpIHtcbiAgICBmb2xsb3dVcERhdGEuZXJyb3JNZXNzYWdlID1cbiAgICAgIChmb2xsb3dVcERhdGEuZXJyb3JNZXNzYWdlIHx8ICcnKSArXG4gICAgICAnTm8gc3BlY2lmaWMgZm9sbG93LXVwIGl0ZW1zIHdlcmUgaWRlbnRpZmllZCBmcm9tIHRoZSBjb250ZXh0IHByb3ZpZGVkLiAnO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgYFtoYW5kbGVTdWdnZXN0Rm9sbG93VXBzXSBGaW5hbCBzdWdnZXN0aW9ucyBjb21waWxlZCBmb3IgXCIke2ZvbGxvd1VwRGF0YS5jb250ZXh0TmFtZX1cIi4gQ291bnQ6ICR7Zm9sbG93VXBEYXRhLnN1Z2dlc3Rpb25zLmxlbmd0aH1gXG4gICk7XG4gIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBmb2xsb3dVcERhdGEgfTtcbn1cbiJdfQ==
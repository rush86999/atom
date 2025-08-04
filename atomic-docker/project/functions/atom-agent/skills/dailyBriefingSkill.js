import { logger } from '../../_utils/logger';
import * as calendarSkills from './calendarSkills'; // For fetching meetings
import { queryNotionTasks as queryNotionTasksBackend } from './notionAndResearchSkills'; // For querying tasks
import { ATOM_NOTION_TASKS_DATABASE_ID } from '../_libs/constants'; // For Notion Task DB ID
import * as gmailSkills from './gmailSkills'; // For fetching emails
import * as slackSkills from './slackSkills'; // For fetching Slack messages
import * as teamsSkills from './msTeamsSkills'; // For fetching MS Teams messages
function getUTCDateYYYYMMDD(date) {
    return date.toISOString().split('T')[0];
}
function getStartOfDayUTC(date) {
    const d = new Date(date.valueOf()); // Clone to avoid modifying original
    d.setUTCHours(0, 0, 0, 0);
    return d;
}
function getEndOfDayUTC(date) {
    const d = new Date(date.valueOf()); // Clone to avoid modifying original
    d.setUTCHours(23, 59, 59, 999);
    return d;
}
function parseDateContextLogic(dateContextInput, baseDateOverride // For testing
) {
    const baseDate = baseDateOverride || new Date();
    const originalInput = dateContextInput;
    let status = 'parsed';
    let warningMessage = undefined;
    let targetDate = getStartOfDayUTC(baseDate); // Default to start of baseDate (today)
    const input = (dateContextInput || 'today').toLowerCase().trim();
    let successfullyParsed = false;
    let determinedTargetDate = getStartOfDayUTC(new Date(baseDate.valueOf())); // Use a mutable copy for calculations
    // Helper to adjust date by days, ensuring it's at UTC midnight
    const adjustDateDays = (base, dayAdjustment) => {
        const newDate = getStartOfDayUTC(new Date(base.valueOf()));
        newDate.setUTCDate(newDate.getUTCDate() + dayAdjustment);
        return newDate;
    };
    if (input === 'today') {
        targetDate = getStartOfDayUTC(baseDate); // Use original baseDate for 'today'
        if (!dateContextInput)
            status = 'defaulted';
        successfullyParsed = true;
    }
    else if (input === 'tomorrow') {
        targetDate = adjustDateDays(baseDate, 1);
        successfullyParsed = true;
    }
    else if (input === 'yesterday') {
        targetDate = adjustDateDays(baseDate, -1);
        successfullyParsed = true;
    }
    else {
        // Try parsing YYYY-MM-DD
        const yyyyMmDdRegex = /^(\d{4})-(\d{2})-(\d{2})$/;
        const yyyyMmDdMatch = input.match(yyyyMmDdRegex);
        if (yyyyMmDdMatch) {
            const year = parseInt(yyyyMmDdMatch[1], 10);
            const month = parseInt(yyyyMmDdMatch[2], 10) - 1; // Month is 0-indexed
            const day = parseInt(yyyyMmDdMatch[3], 10);
            const parsed = new Date(Date.UTC(year, month, day));
            if (parsed.getUTCFullYear() === year &&
                parsed.getUTCMonth() === month &&
                parsed.getUTCDate() === day) {
                targetDate = getStartOfDayUTC(parsed);
                successfullyParsed = true;
            }
            else {
                logger.warn(`[dailyBriefingSkill] Invalid YYYY-MM-DD date string: ${input}`);
            }
        }
        // Try parsing "next/last [weekday]"
        if (!successfullyParsed) {
            const weekdayMap = {
                sunday: 0,
                monday: 1,
                tuesday: 2,
                wednesday: 3,
                thursday: 4,
                friday: 5,
                saturday: 6,
            };
            const relativeWeekdayRegex = /^(next|last)\s+(sunday|monday|tuesday|wednesday|thursday|friday|saturday)/;
            const relativeMatch = input.match(relativeWeekdayRegex);
            if (relativeMatch) {
                const direction = relativeMatch[1];
                const weekdayName = relativeMatch[2];
                const targetDayOfWeek = weekdayMap[weekdayName];
                determinedTargetDate = getStartOfDayUTC(new Date(baseDate.valueOf())); // Start from baseDate
                const currentDayOfWeek = determinedTargetDate.getUTCDay();
                if (direction === 'next') {
                    let daysToAdd = (targetDayOfWeek - currentDayOfWeek + 7) % 7;
                    if (daysToAdd === 0)
                        daysToAdd = 7;
                    determinedTargetDate.setUTCDate(determinedTargetDate.getUTCDate() + daysToAdd);
                }
                else {
                    // "last"
                    let daysToSubtract = (currentDayOfWeek - targetDayOfWeek + 7) % 7;
                    if (daysToSubtract === 0)
                        daysToSubtract = 7;
                    determinedTargetDate.setUTCDate(determinedTargetDate.getUTCDate() - daysToSubtract);
                }
                targetDate = determinedTargetDate;
                successfullyParsed = true;
                // Note: Time part after weekday (e.g., "next monday at 3pm") is ignored for now.
                if (input.includes(' at ')) {
                    logger.info(`[dailyBriefingSkill] Time part in "${originalInput}" is currently ignored. Using start of day.`);
                }
            }
        }
        // Try parsing "Month Day" (e.g., "August 15", "Dec 1st")
        if (!successfullyParsed) {
            const monthDayRegex = /^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?/;
            // Further regex for time part if we were to parse it: (?: at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?
            const monthDayMatch = input.match(monthDayRegex);
            if (monthDayMatch) {
                const monthStr = monthDayMatch[1].substring(0, 3);
                const day = parseInt(monthDayMatch[2], 10);
                const yearStr = monthDayMatch[3];
                const monthMap = {
                    jan: 0,
                    feb: 1,
                    mar: 2,
                    apr: 3,
                    may: 4,
                    jun: 5,
                    jul: 6,
                    aug: 7,
                    sep: 8,
                    oct: 9,
                    nov: 10,
                    dec: 11,
                };
                const month = monthMap[monthStr];
                if (month !== undefined && day >= 1 && day <= 31) {
                    let year = yearStr
                        ? parseInt(yearStr, 10)
                        : baseDate.getUTCFullYear();
                    determinedTargetDate = new Date(Date.UTC(year, month, day));
                    // Check if valid date (e.g. Feb 30)
                    if (determinedTargetDate.getUTCFUTCDate() !== day ||
                        determinedTargetDate.getUTCMonth() !== month ||
                        determinedTargetDate.getUTCFullYear() !== year) {
                        logger.warn(`[dailyBriefingSkill] Invalid Month-Day-Year combination: ${input}`);
                    }
                    else {
                        // If no year specified and date has passed for current year, assume next year.
                        if (!yearStr &&
                            getStartOfDayUTC(determinedTargetDate) <
                                getStartOfDayUTC(baseDate)) {
                            year++;
                            determinedTargetDate.setUTCFullYear(year);
                            // Re-validate if year change made it invalid (e.g. Feb 29)
                            if (determinedTargetDate.getUTCMonth() !== month) {
                                // Day rolled over due to invalid date in new year
                                logger.warn(`[dailyBriefingSkill] Invalid Month-Day for next year: ${input}`);
                                successfullyParsed = false; // Keep it false
                            }
                            else {
                                targetDate = getStartOfDayUTC(determinedTargetDate);
                                successfullyParsed = true;
                            }
                        }
                        else {
                            targetDate = getStartOfDayUTC(determinedTargetDate);
                            successfullyParsed = true;
                        }
                        if (successfullyParsed && input.includes(' at ')) {
                            logger.info(`[dailyBriefingSkill] Time part in "${originalInput}" is currently ignored. Using start of day.`);
                        }
                    }
                }
                else {
                    logger.warn(`[dailyBriefingSkill] Could not parse month/day from: ${input}`);
                }
            }
        }
    }
    if (!successfullyParsed) {
        targetDate = getStartOfDayUTC(baseDate); // Default to today if all parsing fails
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
const HIGH_URGENCY_KEYWORDS = [
    'urgent',
    'asap',
    'critical',
    'action required',
    'outage',
    'important',
    'immediately',
];
const MEDIUM_URGENCY_KEYWORDS = [
    'please review',
    'feedback needed',
    'deadline',
    'reminder',
    'follow-up',
    'question',
];
function calculateUrgencyScore(item, targetDate, targetDateISO) {
    let score = 0;
    const nowForContext = new Date(); // Used if targetDate is today, for "time until"
    // --- Keyword and Context Scoring ---
    let keywordBonus = 0;
    const textToScan = `${item.title || ''} ${item.details || ''}`.toLowerCase();
    if (HIGH_URGENCY_KEYWORDS.some((kw) => textToScan.includes(kw))) {
        keywordBonus = 25;
    }
    else if (MEDIUM_URGENCY_KEYWORDS.some((kw) => textToScan.includes(kw))) {
        keywordBonus = 15;
    }
    switch (item.type) {
        case 'meeting':
            const meeting = item.raw_item;
            if (meeting && meeting.start) {
                const meetingStartDate = new Date(meeting.start);
                if (getUTCDateYYYYMMDD(meetingStartDate) === targetDateISO) {
                    score += 40; // Base score for being a meeting on the target day
                    const hoursFromStartOfDayToMeetingStart = meetingStartDate.getUTCHours() +
                        meetingStartDate.getUTCMinutes() / 60;
                    const timeProximityScore = Math.max(0, (24 - hoursFromStartOfDayToMeetingStart) * 2.5);
                    score += Math.min(timeProximityScore, 40); // Cap time proximity bonus
                    if (targetDateISO === getUTCDateYYYYMMDD(nowForContext) &&
                        meetingStartDate > nowForContext) {
                        const hoursUntilMeeting = (meetingStartDate.getTime() - nowForContext.getTime()) /
                            (1000 * 60 * 60);
                        if (hoursUntilMeeting < 1)
                            score += 5;
                        else if (hoursUntilMeeting < 3)
                            score += 3;
                    }
                    // Attendee count bonus
                    if (meeting.attendees && Array.isArray(meeting.attendees)) {
                        if (meeting.attendees.length <= 2) {
                            score += 20; // 1:1 or with one other person
                        }
                        else if (meeting.attendees.length <= 5) {
                            score += 10; // Small group
                        }
                    }
                }
            }
            break;
        case 'task':
            const task = item.raw_item;
            if (task) {
                if (task.status === 'Done' || task.status === 'Cancelled') {
                    score = 0;
                    break; // No further scoring for completed/cancelled tasks
                }
                const priorityBonusMap = { High: 10, Medium: 5, Low: 0 };
                const priorityBonus = priorityBonusMap[task.priority || 'Low'] || 0;
                if (task.dueDate) {
                    const dueDateOnlyISO = task.dueDate.split('T')[0];
                    const targetDateOnlyISO = targetDateISO; // Already YYYY-MM-DD
                    if (dueDateOnlyISO < targetDateOnlyISO) {
                        // Overdue relative to targetDate
                        score = 80 + priorityBonus;
                    }
                    else if (dueDateOnlyISO === targetDateOnlyISO) {
                        // Due on targetDate
                        score = 70 + priorityBonus;
                    }
                    else {
                        // Due in the future relative to targetDate
                        const dueDateObj = new Date(dueDateOnlyISO + 'T00:00:00Z'); // Ensure parsed as UTC
                        const targetDateObj = new Date(targetDateOnlyISO + 'T00:00:00Z'); // Ensure parsed as UTC
                        const diffDays = (dueDateObj.getTime() - targetDateObj.getTime()) /
                            (1000 * 60 * 60 * 24);
                        if (diffDays <= 3) {
                            // Due Soon (within 1-3 days after targetDate)
                            score = 50 + priorityBonus;
                        }
                        else {
                            // Due Future (beyond 3 days after targetDate)
                            score = 30 + (priorityBonus > 0 ? Math.min(5, priorityBonus) : 0); // Smaller priority bonus for distant tasks
                        }
                    }
                }
                else {
                    // No Due Date
                    score = 25 + priorityBonus;
                    // Recency of Activity bonus for tasks with no due date
                    const activityDateStr = task.last_edited_time || task.createdDate;
                    if (activityDateStr) {
                        try {
                            const activityDate = new Date(activityDateStr);
                            // Compare with 'nowForContext' which is the actual current date when skill runs
                            const daysSinceActivity = (nowForContext.getTime() - activityDate.getTime()) /
                                (1000 * 60 * 60 * 24);
                            if (daysSinceActivity <= 7) {
                                score += 5;
                            }
                        }
                        catch (e) {
                            logger.warn(`[calculateUrgencyScore] Could not parse task activity date: ${activityDateStr}`);
                        }
                    }
                }
            }
            break;
        case 'email':
            const email = item.raw_item;
            score += 50; // Base score for being a recent, unread email for the targetDate
            score += keywordBonus; // Add keyword bonus
            if (email && email.date) {
                const emailDate = new Date(email.date);
                if (targetDateISO === getUTCDateYYYYMMDD(nowForContext)) {
                    const hoursAgoReceived = (nowForContext.getTime() - emailDate.getTime()) / (1000 * 60 * 60);
                    if (hoursAgoReceived >= 0 && hoursAgoReceived < 4)
                        score += 5;
                }
            }
            break;
        case 'slack_message':
            const slackMsg = item.raw_item;
            score += 45; // Base score for being a recent DM/mention on targetDate.
            score += keywordBonus; // Add keyword bonus
            if (slackMsg && slackMsg.timestamp) {
                try {
                    const messageDate = new Date(slackMsg.timestamp);
                    if (targetDateISO === getUTCDateYYYYMMDD(nowForContext)) {
                        const hoursAgoReceived = (nowForContext.getTime() - messageDate.getTime()) /
                            (1000 * 60 * 60);
                        if (hoursAgoReceived >= 0 && hoursAgoReceived < 2)
                            score += 5;
                    }
                }
                catch (e) {
                    logger.warn(`[calculateUrgencyScore] Could not parse Slack message timestamp: ${slackMsg.timestamp}`);
                }
            }
            break;
        case 'teams_message':
            const teamsMsg = item.raw_item;
            score += 45; // Base score for being a recent DM/mention on targetDate.
            score += keywordBonus; // Add keyword bonus
            if (teamsMsg && teamsMsg.createdDateTime) {
                try {
                    const messageDate = new Date(teamsMsg.createdDateTime);
                    if (targetDateISO === getUTCDateYYYYMMDD(nowForContext)) {
                        const hoursAgoReceived = (nowForContext.getTime() - messageDate.getTime()) /
                            (1000 * 60 * 60);
                        if (hoursAgoReceived >= 0 && hoursAgoReceived < 2)
                            score += 5;
                    }
                }
                catch (e) {
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
function getFriendlyDateString(date, baseDateForComparison = new Date()) {
    const today = getStartOfDayUTC(new Date(baseDateForComparison.valueOf()));
    const tomorrow = getStartOfDayUTC(new Date(baseDateForComparison.valueOf()));
    tomorrow.setUTCDate(today.getUTCDate() + 1);
    const yesterday = getStartOfDayUTC(new Date(baseDateForComparison.valueOf()));
    yesterday.setUTCDate(today.getUTCDate() - 1);
    const target = getStartOfDayUTC(new Date(date.valueOf()));
    if (target.getTime() === today.getTime())
        return 'Today';
    if (target.getTime() === tomorrow.getTime())
        return 'Tomorrow';
    if (target.getTime() === yesterday.getTime())
        return 'Yesterday';
    return target.toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'UTC',
    });
}
/**
 * Generates a daily priority briefing for the user, consolidating information
 * from tasks, meetings, and potentially urgent messages.
 *
 * @param userId The ID of the user requesting the briefing.
 * @param nluEntities The parsed NLU entities from the GetDailyPriorityBriefing intent.
 * @returns A promise that resolves to GetDailyPriorityBriefingSkillResponse.
 */
export async function generateDailyBriefing(userId, nluEntities) {
    // Use the new date parsing logic
    const parsedDateInfo = parseDateContextLogic(nluEntities.date_context);
    logger.info(`[dailyBriefingSkill] Generating daily briefing for user ${userId} for dateContext: "${nluEntities.date_context || 'today'}", resolved to: ${parsedDateInfo.targetDateISO}`);
    logger.debug(`[dailyBriefingSkill] NLU Entities: ${JSON.stringify(nluEntities)}`);
    logger.debug(`[dailyBriefingSkill] Parsed Date Info: ${JSON.stringify(parsedDateInfo)}`);
    const briefingData = {
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
    const focusAreas = nluEntities.focus_areas || [
        'tasks',
        'meetings',
        'urgent_emails',
        'urgent_slack_messages',
    ]; // Default focus areas
    try {
        // Fetch Tasks
        if (focusAreas.includes('tasks')) {
            logger.info(`[dailyBriefingSkill] Fetching tasks for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
            if (!ATOM_NOTION_TASKS_DATABASE_ID) {
                logger.error('[dailyBriefingSkill] ATOM_NOTION_TASKS_DATABASE_ID is not configured. Cannot fetch tasks.');
                briefingData.errors_encountered?.push({
                    source_area: 'tasks',
                    message: 'Notion tasks database ID is not configured.',
                });
            }
            else {
                try {
                    // Define params for overdue tasks: due before targetDateISO, not Done or Cancelled
                    const overdueTaskParams = {
                        notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
                        dueDateBefore: parsedDateInfo.targetDateISO,
                        status_not_equals: ['Done', 'Cancelled'],
                        limit: 10,
                    };
                    if (nluEntities.project_filter)
                        overdueTaskParams.listName = nluEntities.project_filter;
                    if (nluEntities.urgency_level &&
                        (nluEntities.urgency_level === 'high' ||
                            nluEntities.urgency_level === 'critical')) {
                        overdueTaskParams.priority = nluEntities.urgency_level;
                    }
                    // Define params for tasks due on targetDateISO: due equals targetDateISO, not Done or Cancelled
                    const dueOnTargetDateTaskParams = {
                        notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
                        dueDateEquals: parsedDateInfo.targetDateISO,
                        status_not_equals: ['Done', 'Cancelled'],
                        limit: 10,
                    };
                    if (nluEntities.project_filter)
                        dueOnTargetDateTaskParams.listName = nluEntities.project_filter;
                    if (nluEntities.urgency_level &&
                        (nluEntities.urgency_level === 'high' ||
                            nluEntities.urgency_level === 'critical')) {
                        dueOnTargetDateTaskParams.priority = nluEntities.urgency_level;
                    }
                    const [overdueTasksResponse, dueOnTargetDateTasksResponse] = await Promise.all([
                        queryNotionTasksBackend(userId, overdueTaskParams),
                        queryNotionTasksBackend(userId, dueOnTargetDateTaskParams),
                    ]);
                    const fetchedTasks = [];
                    if (overdueTasksResponse.success && overdueTasksResponse.tasks) {
                        fetchedTasks.push(...overdueTasksResponse.tasks);
                    }
                    else if (!overdueTasksResponse.success) {
                        logger.error(`[dailyBriefingSkill] Error fetching overdue tasks: ${overdueTasksResponse.error}`);
                        briefingData.errors_encountered?.push({
                            source_area: 'tasks',
                            message: `Error fetching overdue tasks (before ${parsedDateInfo.targetDateISO}): ${overdueTasksResponse.error}`,
                        });
                    }
                    if (dueOnTargetDateTasksResponse.success &&
                        dueOnTargetDateTasksResponse.tasks) {
                        dueOnTargetDateTasksResponse.tasks.forEach((task) => {
                            if (!fetchedTasks.find((ft) => ft.id === task.id)) {
                                fetchedTasks.push(task);
                            }
                        });
                    }
                    else if (!dueOnTargetDateTasksResponse.success) {
                        logger.error(`[dailyBriefingSkill] Error fetching tasks due on ${parsedDateInfo.targetDateISO}: ${dueOnTargetDateTasksResponse.error}`);
                        briefingData.errors_encountered?.push({
                            source_area: 'tasks',
                            message: `Error fetching tasks due on ${parsedDateInfo.targetDateISO}: ${dueOnTargetDateTasksResponse.error}`,
                        });
                    }
                    if (fetchedTasks.length > 0) {
                        fetchedTasks.sort((a, b) => {
                            const aIsOverdue = a.dueDate && a.dueDate < parsedDateInfo.targetDateISO;
                            const bIsOverdue = b.dueDate && b.dueDate < parsedDateInfo.targetDateISO;
                            if (aIsOverdue && !bIsOverdue)
                                return -1;
                            if (!aIsOverdue && bIsOverdue)
                                return 1;
                            const priorityOrder = { High: 1, Medium: 2, Low: 3 };
                            const aPrio = priorityOrder[a.priority || 'Low'] || 3;
                            const bPrio = priorityOrder[b.priority || 'Low'] || 3;
                            if (aPrio !== bPrio)
                                return aPrio - bPrio;
                            const aDueDate = a.dueDate
                                ? new Date(a.dueDate).getTime()
                                : Infinity;
                            const bDueDate = b.dueDate
                                ? new Date(b.dueDate).getTime()
                                : Infinity;
                            return aDueDate - bDueDate;
                        });
                        fetchedTasks.forEach((task) => {
                            let details = `Status: ${task.status}`;
                            if (task.dueDate) {
                                const dueDate = new Date(task.dueDate);
                                // Use targetDateISO for overdue comparison
                                const isOverdue = dueDate.toISOString().split('T')[0] <
                                    parsedDateInfo.targetDateISO &&
                                    task.status !== 'Done' &&
                                    task.status !== 'Cancelled';
                                details += `, Due: ${dueDate.toLocaleDateString([], { month: 'short', day: 'numeric', year: dueDate.getUTCFullYear() !== new Date().getUTCFullYear() ? 'numeric' : undefined })}`;
                                if (isOverdue)
                                    details += ' (OVERDUE)';
                            }
                            else {
                                details += ', Due: N/A';
                            }
                            if (task.priority)
                                details += `, Prio: ${task.priority}`;
                            if (task.listName)
                                details += `, List: ${task.listName}`;
                            briefingData.priority_items.push({
                                type: 'task',
                                title: task.description,
                                details: details,
                                link: task.url,
                                source_id: task.id,
                                raw_item: task,
                                urgency_score: calculateUrgencyScore({
                                    type: 'task',
                                    title: task.description,
                                    raw_item: task,
                                }, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
                            });
                        });
                        logger.info(`[dailyBriefingSkill] Fetched and processed ${fetchedTasks.length} tasks.`);
                    }
                    else {
                        logger.info(`[dailyBriefingSkill] No relevant tasks found for briefing.`);
                    }
                }
                catch (e) {
                    logger.error(`[dailyBriefingSkill] Exception during task fetching: ${e.message}`, e);
                    briefingData.errors_encountered?.push({
                        source_area: 'tasks',
                        message: `Exception: ${e.message}`,
                        details: e.stack,
                    });
                }
            }
        }
        else {
            // Remove placeholder if tasks are not in focusAreas
            briefingData.priority_items = briefingData.priority_items.filter((item) => item.type !== 'task');
        }
        // Fetch Meetings
        if (focusAreas.includes('meetings')) {
            logger.info(`[dailyBriefingSkill] Fetching meetings for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
            try {
                // Use timeMinISO and timeMaxISO from parsedDateInfo
                const eventsResponse = await calendarSkills.listUpcomingEvents(userId, 10, parsedDateInfo.timeMinISO, parsedDateInfo.timeMaxISO);
                if (eventsResponse.ok && eventsResponse.data) {
                    const meetings = eventsResponse.data;
                    // Make sure the date formatting for meeting details uses the targetDate, not necessarily 'today'
                    const targetDateForDisplay = parsedDateInfo.targetDate;
                    if (meetings.length > 0) {
                        meetings.forEach((meeting) => {
                            const startTime = meeting.start
                                ? new Date(meeting.start).toLocaleTimeString([], {
                                    hour: 'numeric',
                                    minute: '2-digit',
                                    hour12: true,
                                })
                                : 'N/A';
                            const endTime = meeting.end
                                ? new Date(meeting.end).toLocaleTimeString([], {
                                    hour: 'numeric',
                                    minute: '2-digit',
                                    hour12: true,
                                })
                                : '';
                            briefingData.priority_items.push({
                                type: 'meeting',
                                title: meeting.summary || 'Untitled Meeting',
                                details: `Time: ${startTime}${endTime ? ` - ${endTime}` : ''}`,
                                link: meeting.htmlLink,
                                source_id: meeting.id,
                                raw_item: meeting,
                                urgency_score: calculateUrgencyScore({
                                    type: 'meeting',
                                    title: meeting.summary || 'Untitled Meeting',
                                    raw_item: meeting,
                                }, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
                            });
                        });
                        logger.info(`[dailyBriefingSkill] Fetched ${meetings.length} meetings.`);
                    }
                    else {
                        logger.info(`[dailyBriefingSkill] No meetings found for ${dateContext}.`);
                    }
                }
                else {
                    logger.error(`[dailyBriefingSkill] Error fetching meetings: ${eventsResponse.error?.message}`);
                    briefingData.errors_encountered?.push({
                        source_area: 'meetings',
                        message: eventsResponse.error?.message ||
                            'Unknown error fetching calendar events.',
                        details: JSON.stringify(eventsResponse.error?.details),
                    });
                }
            }
            catch (e) {
                logger.error(`[dailyBriefingSkill] Exception during meeting fetching: ${e.message}`, e);
                briefingData.errors_encountered?.push({
                    source_area: 'meetings',
                    message: `Exception: ${e.message}`,
                    details: e.stack,
                });
            }
        }
        else {
            // Remove placeholder if meetings are not in focusAreas
            briefingData.priority_items = briefingData.priority_items.filter((item) => item.type !== 'meeting');
        }
        // Fetch Urgent Emails
        if (focusAreas.includes('urgent_emails')) {
            logger.info(`[dailyBriefingSkill] Fetching urgent emails for briefing for targetDate: ${parsedDateInfo.targetDateISO}.`);
            try {
                const emailResponse = await gmailSkills.getRecentUnreadEmailsForBriefing(userId, parsedDateInfo.targetDate, // Pass the Date object
                3 // Fetch up to 3 emails
                );
                if (emailResponse.ok && emailResponse.data?.results) {
                    const emails = emailResponse.data.results;
                    if (emails.length > 0) {
                        emails.forEach((email) => {
                            briefingData.priority_items.push({
                                type: 'email',
                                title: email.subject || 'No Subject',
                                details: `From: ${email.from || 'N/A'}${email.snippet ? `, Snippet: ${email.snippet.substring(0, 70)}...` : ''}`,
                                link: email.link,
                                source_id: email.id,
                                raw_item: email,
                                urgency_score: calculateUrgencyScore({
                                    type: 'email',
                                    title: email.subject || 'No Subject',
                                    raw_item: email,
                                }, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
                            });
                        });
                        logger.info(`[dailyBriefingSkill] Fetched ${emails.length} urgent/recent unread emails.`);
                    }
                    else {
                        logger.info(`[dailyBriefingSkill] No urgent/recent unread emails found for ${parsedDateInfo.targetDateISO}.`);
                    }
                }
                else {
                    logger.error(`[dailyBriefingSkill] Error fetching urgent emails: ${emailResponse.error?.message}`);
                    briefingData.errors_encountered?.push({
                        source_area: 'emails',
                        message: emailResponse.error?.message ||
                            'Unknown error fetching urgent emails.',
                        details: JSON.stringify(emailResponse.error?.details),
                    });
                }
            }
            catch (e) {
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
                const slackResponse = await slackSkills.getRecentDMsAndMentionsForBriefing(userId, // atomUserId
                parsedDateInfo.targetDate, // targetDate
                3 // count
                );
                if (slackResponse.ok && slackResponse.data?.results) {
                    const slackMessages = slackResponse.data.results; // SlackMessage is compatible with SlackMessageSnippet for these fields
                    if (slackMessages.length > 0) {
                        slackMessages.forEach((msg) => {
                            let title = `Slack message`;
                            if (msg.userName)
                                title += ` from ${msg.userName}`;
                            if (msg.channelName)
                                title += ` in #${msg.channelName}`;
                            else if (!msg.channelName && msg.userName)
                                title += ` (DM)`; // Likely a DM if channelName is null but userName (sender) is present
                            briefingData.priority_items.push({
                                type: 'slack_message',
                                title: title,
                                details: msg.text
                                    ? msg.text.substring(0, 100) +
                                        (msg.text.length > 100 ? '...' : '')
                                    : '(No text content)',
                                link: msg.permalink,
                                source_id: msg.id, // 'ts' from SlackMessage
                                raw_item: msg,
                                urgency_score: calculateUrgencyScore({
                                    type: 'slack_message',
                                    title: title,
                                    raw_item: msg,
                                }, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
                            });
                        });
                        logger.info(`[dailyBriefingSkill] Fetched ${slackMessages.length} urgent/recent Slack messages.`);
                    }
                    else {
                        logger.info(`[dailyBriefingSkill] No urgent/recent Slack messages found for ${parsedDateInfo.targetDateISO}.`);
                    }
                }
                else {
                    logger.error(`[dailyBriefingSkill] Error fetching urgent Slack messages: ${slackResponse.error?.message}`);
                    briefingData.errors_encountered?.push({
                        source_area: 'slack',
                        message: slackResponse.error?.message ||
                            'Unknown error fetching urgent Slack messages.',
                        details: JSON.stringify(slackResponse.error?.details),
                    });
                }
            }
            catch (e) {
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
                const teamsResponse = await teamsSkills.getRecentChatsAndMentionsForBriefing(userId, parsedDateInfo.targetDate, 3 // Fetch up to 3 messages
                );
                if (teamsResponse.ok && teamsResponse.data?.results) {
                    const teamsMessages = teamsResponse.data.results;
                    if (teamsMessages.length > 0) {
                        teamsMessages.forEach((msg) => {
                            let title = `Teams message`;
                            if (msg.userName)
                                title += ` from ${msg.userName}`;
                            // msg.chatId could be used to infer if it's a 1:1 or group chat if channel/team info isn't directly on msg
                            // For now, keeping title simple.
                            // if (msg.channelName) title += ` in ${msg.channelName}`; // MSTeamsMessage may not have channelName directly
                            briefingData.priority_items.push({
                                type: 'teams_message', // New BriefingItemType
                                title: title,
                                details: msg.content
                                    ? msg.content.substring(0, 100) +
                                        (msg.content.length > 100 ? '...' : '')
                                    : '(No text content)',
                                link: msg.webUrl,
                                source_id: msg.id,
                                raw_item: msg,
                                urgency_score: calculateUrgencyScore({
                                    type: 'teams_message',
                                    title: title,
                                    raw_item: msg,
                                }, parsedDateInfo.targetDate, parsedDateInfo.targetDateISO),
                            });
                        });
                        logger.info(`[dailyBriefingSkill] Fetched ${teamsMessages.length} urgent/recent MS Teams messages.`);
                    }
                    else {
                        logger.info(`[dailyBriefingSkill] No urgent/recent MS Teams messages found for ${parsedDateInfo.targetDateISO}.`);
                    }
                }
                else {
                    logger.error(`[dailyBriefingSkill] Error fetching urgent MS Teams messages: ${teamsResponse.error?.message}`);
                    briefingData.errors_encountered?.push({
                        source_area: 'teams', // New source_area
                        message: teamsResponse.error?.message ||
                            'Unknown error fetching urgent MS Teams messages.',
                        details: JSON.stringify(teamsResponse.error?.details),
                    });
                }
            }
            catch (e) {
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
                const aStart = a.raw_item?.start
                    ? new Date(a.raw_item.start).getTime()
                    : 0;
                const bStart = b.raw_item?.start
                    ? new Date(b.raw_item.start).getTime()
                    : 0;
                return aStart - bStart; // Earlier meeting first
            }
            if (a.type === 'task' && b.type === 'task') {
                // Tasks were already pre-sorted somewhat by due date and priority groups
                // Here, just ensure consistent ordering if scores are identical, e.g., by explicit due date
                const aDueDate = a.raw_item?.dueDate
                    ? new Date(a.raw_item.dueDate).getTime()
                    : Infinity;
                const bDueDate = b.raw_item?.dueDate
                    ? new Date(b.raw_item.dueDate).getTime()
                    : Infinity;
                if (aDueDate !== bDueDate)
                    return aDueDate - bDueDate; // Earlier due date first
                // Could add further tie-breaking by priority if needed, though score should mostly cover it
            }
            if (a.type === 'email' && b.type === 'email') {
                const aDate = a.raw_item?.date
                    ? new Date(a.raw_item.date).getTime()
                    : 0;
                const bDate = b.raw_item?.date
                    ? new Date(b.raw_item.date).getTime()
                    : 0;
                return bDate - aDate; // Newer email first
            }
            // If types are different and scores are equal, maintain original relative order or define one
            // For now, if scores are equal and types differ, their relative order won't change from this sort pass.
            // A more explicit cross-type secondary sort could be: Meetings > Tasks > Emails > Slack > Teams if scores are identical.
            const typeOrder = {
                meeting: 1,
                task: 2,
                email: 3,
                slack_message: 4,
                teams_message: 5,
            };
            const aTypeOrder = typeOrder[a.type] || 99; // Items not in typeOrder go last
            const bTypeOrder = typeOrder[b.type] || 99; // Items not in typeOrder go last
            return aTypeOrder - bTypeOrder;
        });
        logger.info(`[dailyBriefingSkill] Sorted ${briefingData.priority_items.length} priority items.`);
        // Generate overall_summary_message
        // Generate overall_summary_message
        const numTasks = briefingData.priority_items.filter((item) => item.type === 'task').length;
        const numMeetings = briefingData.priority_items.filter((item) => item.type === 'meeting').length;
        const numEmails = briefingData.priority_items.filter((item) => item.type === 'email').length;
        const numSlackMessages = briefingData.priority_items.filter((item) => item.type === 'slack_message').length;
        const numTeamsMessages = briefingData.priority_items.filter((item) => item.type === 'teams_message').length;
        const friendlyDateString = getFriendlyDateString(parsedDateInfo.targetDate);
        let summaryParts = [];
        // Construct message parts for each focus area
        if (focusAreas.includes('meetings')) {
            if (numMeetings > 0) {
                summaryParts.push(`${numMeetings} meeting(s) scheduled.`);
            }
            else {
                summaryParts.push('no meetings scheduled.');
            }
        }
        if (focusAreas.includes('tasks')) {
            if (numTasks > 0) {
                const overdueTasks = briefingData.priority_items.filter((item) => item.type === 'task' &&
                    item.raw_item &&
                    item.raw_item.dueDate &&
                    item.raw_item.dueDate <
                        parsedDateInfo.targetDateISO &&
                    item.raw_item.status !== 'Done' &&
                    item.raw_item.status !== 'Cancelled').length;
                let taskPart = `${numTasks} task(s) require attention`;
                if (overdueTasks > 0)
                    taskPart += ` (${overdueTasks} overdue)`;
                summaryParts.push(taskPart);
            }
            else {
                summaryParts.push('no pressing tasks.');
            }
        }
        if (focusAreas.includes('urgent_emails')) {
            if (numEmails > 0) {
                summaryParts.push(`${numEmails} recent unread email(s).`);
            }
            else {
                summaryParts.push('no recent unread emails.');
            }
        }
        if (focusAreas.includes('urgent_slack_messages')) {
            if (numSlackMessages > 0) {
                summaryParts.push(`${numSlackMessages} recent Slack message(s) (DMs/mentions).`);
            }
            else {
                summaryParts.push('no recent Slack DMs or mentions.');
            }
        }
        if (focusAreas.includes('urgent_teams_messages')) {
            if (numTeamsMessages > 0) {
                summaryParts.push(`${numTeamsMessages} recent MS Teams message(s) (chats/mentions).`);
            }
            else {
                summaryParts.push('no recent MS Teams chats or mentions.');
            }
        }
        // Assemble the final summary message
        let summaryContent = '';
        if (summaryParts.length > 0) {
            // Create a sentence from the parts
            if (summaryParts.length === 1) {
                summaryContent = `You have ${summaryParts[0]}`;
            }
            else {
                const lastPart = summaryParts.pop();
                summaryContent = `You have ${summaryParts.join(', ')}, and ${lastPart}`;
            }
        }
        else {
            summaryContent = `There are no specific items to highlight based on your requested focus areas.`;
        }
        briefingData.overall_summary_message = `Here is your briefing for ${friendlyDateString}: ${summaryContent}`;
        // Prepend date parsing warnings if any
        if (parsedDateInfo.status === 'unparseable' &&
            parsedDateInfo.warningMessage) {
            briefingData.overall_summary_message = `${parsedDateInfo.warningMessage} ${briefingData.overall_summary_message}`;
        }
        else if (parsedDateInfo.status === 'defaulted' &&
            parsedDateInfo.originalInput &&
            parsedDateInfo.originalInput.toLowerCase().trim() !== 'today') {
            briefingData.overall_summary_message = `Showing briefing for today as date context '${parsedDateInfo.originalInput}' was processed as default. ${briefingData.overall_summary_message}`;
        }
        logger.info(`[dailyBriefingSkill] Generated summary: ${briefingData.overall_summary_message}`);
        return { ok: true, data: briefingData };
    }
    catch (error) {
        logger.error(`[dailyBriefingSkill] Error generating daily briefing: ${error.message}`, error);
        briefingData.errors_encountered?.push({
            source_area: 'overall',
            message: `Failed to generate briefing: ${error.message}`,
            details: error.stack,
        });
        return {
            ok: false,
            error: { code: 'BRIEFING_GENERATION_ERROR', message: error.message },
            data: briefingData,
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGFpbHlCcmllZmluZ1NraWxsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGFpbHlCcmllZmluZ1NraWxsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQWFBLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUM3QyxPQUFPLEtBQUssY0FBYyxNQUFNLGtCQUFrQixDQUFDLENBQUMsd0JBQXdCO0FBQzVFLE9BQU8sRUFBRSxnQkFBZ0IsSUFBSSx1QkFBdUIsRUFBRSxNQUFNLDJCQUEyQixDQUFDLENBQUMscUJBQXFCO0FBQzlHLE9BQU8sRUFBRSw2QkFBNkIsRUFBRSxNQUFNLG9CQUFvQixDQUFDLENBQUMsd0JBQXdCO0FBQzVGLE9BQU8sS0FBSyxXQUFXLE1BQU0sZUFBZSxDQUFDLENBQUMsc0JBQXNCO0FBQ3BFLE9BQU8sS0FBSyxXQUFXLE1BQU0sZUFBZSxDQUFDLENBQUMsOEJBQThCO0FBQzVFLE9BQU8sS0FBSyxXQUFXLE1BQU0saUJBQWlCLENBQUMsQ0FBQyxpQ0FBaUM7QUFnQmpGLFNBQVMsa0JBQWtCLENBQUMsSUFBVTtJQUNwQyxPQUFPLElBQUksQ0FBQyxXQUFXLEVBQUUsQ0FBQyxLQUFLLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7QUFDMUMsQ0FBQztBQUVELFNBQVMsZ0JBQWdCLENBQUMsSUFBVTtJQUNsQyxNQUFNLENBQUMsR0FBRyxJQUFJLElBQUksQ0FBQyxJQUFJLENBQUMsT0FBTyxFQUFFLENBQUMsQ0FBQyxDQUFDLG9DQUFvQztJQUN4RSxDQUFDLENBQUMsV0FBVyxDQUFDLENBQUMsRUFBRSxDQUFDLEVBQUUsQ0FBQyxFQUFFLENBQUMsQ0FBQyxDQUFDO0lBQzFCLE9BQU8sQ0FBQyxDQUFDO0FBQ1gsQ0FBQztBQUVELFNBQVMsY0FBYyxDQUFDLElBQVU7SUFDaEMsTUFBTSxDQUFDLEdBQUcsSUFBSSxJQUFJLENBQUMsSUFBSSxDQUFDLE9BQU8sRUFBRSxDQUFDLENBQUMsQ0FB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QVksQ0FBQyx1QkFBdUIsR0FBRywrQ0FBK0MsY0FBYyxDQUFDLGFBQWEsK0JBQStCLFlBQVksQ0FBQyx1QkFBdUIsRUFBRSxDQUFDO1FBQzFMLENBQUM7UUFFRCxNQUFNLENBQUMsSUFBSSxDQUNULDJDQUEyQyxZQUFZLENBQUMsdUJBQXVCLEVBQUUsQ0FDbEYsQ0FBQztRQUVGLE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxZQUFZLEVBQUUsQ0FBQztJQUMxQyxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixNQUFNLENBQUMsS0FBSyxDQUNWLHlEQUF5RCxLQUFLLENBQUMsT0FBTyxFQUFFLEVBQ3hFLEtBQUssQ0FDTixDQUFDO1FBQ0YsWUFBWSxDQUFDLGtCQUFrQixFQUFFLElBQUksQ0FBQztZQUNwQyxXQUFXLEVBQUUsU0FBUztZQUN0QixPQUFPLEVBQUUsZ0NBQWdDLEtBQUssQ0FBQyxPQUFPLEVBQUU7WUFDeEQsT0FBTyxFQUFFLEtBQUssQ0FBQyxLQUFLO1NBQ3JCLENBQUMsQ0FBQztRQUNILE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRSxFQUFFLElBQUksRUFBRSwyQkFBMkIsRUFBRSxPQUFPLEVBQUUsS0FBSyxDQUFDLE9BQU8sRUFBRTtZQUNwRSxJQUFJLEVBQUUsWUFBWTtTQUNuQixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBHZXREYWlseVByaW9yaXR5QnJpZWZpbmdObHVFbnRpdGllcyxcbiAgRGFpbHlCcmllZmluZ0RhdGEsXG4gIEdldERhaWx5UHJpb3JpdHlCcmllZmluZ1NraWxsUmVzcG9uc2UsXG4gIEJyaWVmaW5nSXRlbSxcbiAgU2tpbGxSZXNwb25zZSwgLy8gR2VuZXJpYyBTa2lsbFJlc3BvbnNlXG4gIE5vdGlvblRhc2ssXG4gIENhbGVuZGFyRXZlbnRTdW1tYXJ5LFxuICBHbWFpbE1lc3NhZ2VTbmlwcGV0LFxuICBTbGFja01lc3NhZ2VTbmlwcGV0LFxuICBNU1RlYW1zTWVzc2FnZSxcbiAgUXVlcnlOb3Rpb25UYXNrc1BhcmFtcywgLy8gRm9yIGNvbnN0cnVjdGluZyBwYXJhbWV0ZXJzIGZvciB0YXNrIGZldGNoaW5nXG59IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL191dGlscy9sb2dnZXInO1xuaW1wb3J0ICogYXMgY2FsZW5kYXJTa2lsbHMgZnJvbSAnLi9jYWxlbmRhclNraWxscyc7IC8vIEZvciBmZXRjaGluZyBtZWV0aW5nc1xuaW1wb3J0IHsgcXVlcnlOb3Rpb25UYXNrcyBhcyBxdWVyeU5vdGlvblRhc2tzQmFja2VuZCB9IGZyb20gJy4vbm90aW9uQW5kUmVzZWFyY2hTa2lsbHMnOyAvLyBGb3IgcXVlcnlpbmcgdGFza3NcbmltcG9ydCB7IEFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEIH0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJzsgLy8gRm9yIE5vdGlvbiBUYXNrIERCIElEXG5pbXBvcnQgKiBhcyBnbWFpbFNraWxscyBmcm9tICcuL2dtYWlsU2tpbGxzJzsgLy8gRm9yIGZldGNoaW5nIGVtYWlsc1xuaW1wb3J0ICogYXMgc2xhY2tTa2lsbHMgZnJvbSAnLi9zbGFja1NraWxscyc7IC8vIEZvciBmZXRjaGluZyBTbGFjayBtZXNzYWdlc1xuaW1wb3J0ICogYXMgdGVhbXNTa2lsbHMgZnJvbSAnLi9tc1RlYW1zU2tpbGxzJzsgLy8gRm9yIGZldGNoaW5nIE1TIFRlYW1zIG1lc3NhZ2VzXG4vLyBQbGFjZWhvbGRlciBmb3IgaW1wb3J0aW5nIG90aGVyIHNraWxscyB0aGF0IG1pZ2h0IGJlIG5lZWRlZDpcbi8vIGltcG9ydCAqIGFzIGxsbVV0aWxpdGllcyBmcm9tICcuL2xsbVV0aWxpdGllcyc7IC8vIEZvciByYW5raW5nIHVyZ2VuY3kgb3Igc3VtbWFyaXppbmdcblxuLy8gLS0tIERhdGUgUGFyc2luZyBVdGlsaXR5IC0tLVxuaW50ZXJmYWNlIFBhcnNlZERhdGVDb250ZXh0IHtcbiAgdGFyZ2V0RGF0ZTogRGF0ZTtcbiAgdGltZU1pbklTTzogc3RyaW5nO1xuICB0aW1lTWF4SVNPOiBzdHJpbmc7XG4gIHRhcmdldERhdGVJU086IHN0cmluZzsgLy8gWVlZWS1NTS1ERCBmb3JtYXQgZm9yIHRoZSB0YXJnZXQgZGF0ZVxuICBpc0RhdGVSYW5nZTogYm9vbGVhbjsgLy8gVHlwaWNhbGx5IHRydWUgZm9yIGRhaWx5IGJyaWVmaW5nc1xuICBzdGF0dXM6ICdwYXJzZWQnIHwgJ2RlZmF1bHRlZCcgfCAndW5wYXJzZWFibGUnO1xuICBvcmlnaW5hbElucHV0Pzogc3RyaW5nO1xuICB3YXJuaW5nTWVzc2FnZT86IHN0cmluZztcbn1cblxuZnVuY3Rpb24gZ2V0VVRDRGF0ZVlZWVlNTUREKGRhdGU6IERhdGUpOiBzdHJpbmcge1xuICByZXR1cm4gZGF0ZS50b0lTT1N0cmluZygpLnNwbGl0KCdUJylbMF07XG59XG5cbmZ1bmN0aW9uIGdldFN0YXJ0T2ZEYXlVVEMoZGF0ZTogRGF0ZSk6IERhdGUge1xuICBjb25zdCBkID0gbmV3IERhdGUoZGF0ZS52YWx1ZU9mKCkpOyAvLyBDbG9uZSB0byBhdm9pZCBtb2RpZnlpbmcgb3JpZ2luYWxcbiAgZC5zZXRVVENIb3VycygwLCAwLCAwLCAwKTtcbiAgcmV0dXJuIGQ7XG59XG5cbmZ1bmN0aW9uIGdldEVuZE9mRGF5VVRDKGRhdGU6IERhdGUpOiBEYXRlIHtcbiAgY29uc3QgZCA9IG5ldyBEYXRlKGRhdGUudmFsdWVPZigpKTsgLy8gQ2xvbmUgdG8gYXZvaWQgbW9kaWZ5aW5nIG9yaWdpbmFsXG4gIGQuc2V0VVRDSG91cnMoMjMsIDU5LCA1OSwgOTk5KTtcbiAgcmV0dXJuIGQ7XG59XG5cbmZ1bmN0aW9uIHBhcnNlRGF0ZUNvbnRleHRMb2dpYyhcbiAgZGF0ZUNvbnRleHRJbnB1dD86IHN0cmluZyxcbiAgYmFzZURhdGVPdmVycmlkZT86IERhdGUgLy8gRm9yIHRlc3Rpbmdcbik6IFBhcnNlZERhdGVDb250ZXh0IHtcbiAgY29uc3QgYmFzZURhdGUgPSBiYXNlRGF0ZU92ZXJyaWRlIHx8IG5ldyBEYXRlKCk7XG4gIGNvbnN0IG9yaWdpbmFsSW5wdXQgPSBkYXRlQ29udGV4dElucHV0O1xuICBsZXQgc3RhdHVzOiBQYXJzZWREYXRlQ29udGV4dFsnc3RhdHVzJ10gPSAncGFyc2VkJztcbiAgbGV0IHdhcm5pbmdNZXNzYWdlOiBzdHJpbmcgfCB1bmRlZmluZWQgPSB1bmRlZmluZWQ7XG4gIGxldCB0YXJnZXREYXRlID0gZ2V0U3RhcnRPZkRheVVUQyhiYXNlRGF0ZSk7IC8vIERlZmF1bHQgdG8gc3RhcnQgb2YgYmFzZURhdGUgKHRvZGF5KVxuXG4gIGNvbnN0IGlucHV0ID0gKGRhdGVDb250ZXh0SW5wdXQgfHwgJ3RvZGF5JykudG9Mb3dlckNhc2UoKS50cmltKCk7XG4gIGxldCBzdWNjZXNzZnVsbHlQYXJzZWQgPSBmYWxzZTtcbiAgbGV0IGRldGVybWluZWRUYXJnZXREYXRlID0gZ2V0U3RhcnRPZkRheVVUQyhuZXcgRGF0ZShiYXNlRGF0ZS52YWx1ZU9mKCkpKTsgLy8gVXNlIGEgbXV0YWJsZSBjb3B5IGZvciBjYWxjdWxhdGlvbnNcblxuICAvLyBIZWxwZXIgdG8gYWRqdXN0IGRhdGUgYnkgZGF5cywgZW5zdXJpbmcgaXQncyBhdCBVVEMgbWlkbmlnaHRcbiAgY29uc3QgYWRqdXN0RGF0ZURheXMgPSAoYmFzZTogRGF0ZSwgZGF5QWRqdXN0bWVudDogbnVtYmVyKTogRGF0ZSA9PiB7XG4gICAgY29uc3QgbmV3RGF0ZSA9IGdldFN0YXJ0T2ZEYXlVVEMobmV3IERhdGUoYmFzZS52YWx1ZU9mKCkpKTtcbiAgICBuZXdEYXRlLnNldFVUQ0RhdGUobmV3RGF0ZS5nZXRVVENEYXRlKCkgKyBkYXlBZGp1c3RtZW50KTtcbiAgICByZXR1cm4gbmV3RGF0ZTtcbiAgfTtcblxuICBpZiAoaW5wdXQgPT09ICd0b2RheScpIHtcbiAgICB0YXJnZXREYXRlID0gZ2V0U3RhcnRPZkRheVVUQyhiYXNlRGF0ZSk7IC8vIFVzZSBvcmlnaW5hbCBiYXNlRGF0ZSBmb3IgJ3RvZGF5J1xuICAgIGlmICghZGF0ZUNvbnRleHRJbnB1dCkgc3RhdHVzID0gJ2RlZmF1bHRlZCc7XG4gICAgc3VjY2Vzc2Z1bGx5UGFyc2VkID0gdHJ1ZTtcbiAgfSBlbHNlIGlmIChpbnB1dCA9PT0gJ3RvbW9ycm93Jykge1xuICAgIHRhcmdldERhdGUgPSBhZGp1c3REYXRlRGF5cyhiYXNlRGF0ZSwgMSk7XG4gICAgc3VjY2Vzc2Z1bGx5UGFyc2VkID0gdHJ1ZTtcbiAgfSBlbHNlIGlmIChpbnB1dCA9PT0gJ3llc3RlcmRheScpIHtcbiAgICB0YXJnZXREYXRlID0gYWRqdXN0RGF0ZURheXMoYmFzZURhdGUsIC0xKTtcbiAgICBzdWNjZXNzZnVsbHlQYXJzZWQgPSB0cnVlO1xuICB9IGVsc2Uge1xuICAgIC8vIFRyeSBwYXJzaW5nIFlZWVktTU0tRERcbiAgICBjb25zdCB5eXl5TW1EZFJlZ2V4ID0gL14oXFxkezR9KS0oXFxkezJ9KS0oXFxkezJ9KSQvO1xuICAgIGNvbnN0IHl5eXlNbURkTWF0Y2ggPSBpbnB1dC5tYXRjaCh5eXl5TW1EZFJlZ2V4KTtcbiAgICBpZiAoeXl5eU1tRGRNYXRjaCkge1xuICAgICAgY29uc3QgeWVhciA9IHBhcnNlSW50KHl5eXlNbURkTWF0Y2hbMV0sIDEwKTtcbiAgICAgIGNvbnN0IG1vbnRoID0gcGFyc2VJbnQoeXl5eU1tRGRNYXRjaFsyXSwgMTApIC0gMTsgLy8gTW9udGggaXMgMC1pbmRleGVkXG4gICAgICBjb25zdCBkYXkgPSBwYXJzZUludCh5eXl5TW1EZE1hdGNoWzNdLCAxMCk7XG4gICAgICBjb25zdCBwYXJzZWQgPSBuZXcgRGF0ZShEYXRlLlVUQyh5ZWFyLCBtb250aCwgZGF5KSk7XG4gICAgICBpZiAoXG4gICAgICAgIHBhcnNlZC5nZXRVVENGdWxsWWVhcigpID09PSB5ZWFyICYmXG4gICAgICAgIHBhcnNlZC5nZXRVVENNb250aCgpID09PSBtb250aCAmJlxuICAgICAgICBwYXJzZWQuZ2V0VVRDRGF0ZSgpID09PSBkYXlcbiAgICAgICkge1xuICAgICAgICB0YXJnZXREYXRlID0gZ2V0U3RhcnRPZkRheVVUQyhwYXJzZWQpO1xuICAgICAgICBzdWNjZXNzZnVsbHlQYXJzZWQgPSB0cnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEludmFsaWQgWVlZWS1NTS1ERCBkYXRlIHN0cmluZzogJHtpbnB1dH1gXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gVHJ5IHBhcnNpbmcgXCJuZXh0L2xhc3QgW3dlZWtkYXldXCJcbiAgICBpZiAoIXN1Y2Nlc3NmdWxseVBhcnNlZCkge1xuICAgICAgY29uc3Qgd2Vla2RheU1hcDogeyBba2V5OiBzdHJpbmddOiBudW1iZXIgfSA9IHtcbiAgICAgICAgc3VuZGF5OiAwLFxuICAgICAgICBtb25kYXk6IDEsXG4gICAgICAgIHR1ZXNkYXk6IDIsXG4gICAgICAgIHdlZG5lc2RheTogMyxcbiAgICAgICAgdGh1cnNkYXk6IDQsXG4gICAgICAgIGZyaWRheTogNSxcbiAgICAgICAgc2F0dXJkYXk6IDYsXG4gICAgICB9O1xuICAgICAgY29uc3QgcmVsYXRpdmVXZWVrZGF5UmVnZXggPVxuICAgICAgICAvXihuZXh0fGxhc3QpXFxzKyhzdW5kYXl8bW9uZGF5fHR1ZXNkYXl8d2VkbmVzZGF5fHRodXJzZGF5fGZyaWRheXxzYXR1cmRheSkvO1xuICAgICAgY29uc3QgcmVsYXRpdmVNYXRjaCA9IGlucHV0Lm1hdGNoKHJlbGF0aXZlV2Vla2RheVJlZ2V4KTtcblxuICAgICAgaWYgKHJlbGF0aXZlTWF0Y2gpIHtcbiAgICAgICAgY29uc3QgZGlyZWN0aW9uID0gcmVsYXRpdmVNYXRjaFsxXTtcbiAgICAgICAgY29uc3Qgd2Vla2RheU5hbWUgPSByZWxhdGl2ZU1hdGNoWzJdO1xuICAgICAgICBjb25zdCB0YXJnZXREYXlPZldlZWsgPSB3ZWVrZGF5TWFwW3dlZWtkYXlOYW1lXTtcblxuICAgICAgICBkZXRlcm1pbmVkVGFyZ2V0RGF0ZSA9IGdldFN0YXJ0T2ZEYXlVVEMobmV3IERhdGUoYmFzZURhdGUudmFsdWVPZigpKSk7IC8vIFN0YXJ0IGZyb20gYmFzZURhdGVcbiAgICAgICAgY29uc3QgY3VycmVudERheU9mV2VlayA9IGRldGVybWluZWRUYXJnZXREYXRlLmdldFVUQ0RheSgpO1xuXG4gICAgICAgIGlmIChkaXJlY3Rpb24gPT09ICduZXh0Jykge1xuICAgICAgICAgIGxldCBkYXlzVG9BZGQgPSAodGFyZ2V0RGF5T2ZXZWVrIC0gY3VycmVudERheU9mV2VlayArIDcpICUgNztcbiAgICAgICAgICBpZiAoZGF5c1RvQWRkID09PSAwKSBkYXlzVG9BZGQgPSA3O1xuICAgICAgICAgIGRldGVybWluZWRUYXJnZXREYXRlLnNldFVUQ0RhdGUoXG4gICAgICAgICAgICBkZXRlcm1pbmVkVGFyZ2V0RGF0ZS5nZXRVVENEYXRlKCkgKyBkYXlzVG9BZGRcbiAgICAgICAgICApO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIC8vIFwibGFzdFwiXG4gICAgICAgICAgbGV0IGRheXNUb1N1YnRyYWN0ID0gKGN1cnJlbnREYXlPZldlZWsgLSB0YXJnZXREYXlPZldlZWsgKyA3KSAlIDc7XG4gICAgICAgICAgaWYgKGRheXNUb1N1YnRyYWN0ID09PSAwKSBkYXlzVG9TdWJ0cmFjdCA9IDc7XG4gICAgICAgICAgZGV0ZXJtaW5lZFRhcmdldERhdGUuc2V0VVRDRGF0ZShcbiAgICAgICAgICAgIGRldGVybWluZWRUYXJnZXREYXRlLmdldFVUQ0RhdGUoKSAtIGRheXNUb1N1YnRyYWN0XG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgICB0YXJnZXREYXRlID0gZGV0ZXJtaW5lZFRhcmdldERhdGU7XG4gICAgICAgIHN1Y2Nlc3NmdWxseVBhcnNlZCA9IHRydWU7XG4gICAgICAgIC8vIE5vdGU6IFRpbWUgcGFydCBhZnRlciB3ZWVrZGF5IChlLmcuLCBcIm5leHQgbW9uZGF5IGF0IDNwbVwiKSBpcyBpZ25vcmVkIGZvciBub3cuXG4gICAgICAgIGlmIChpbnB1dC5pbmNsdWRlcygnIGF0ICcpKSB7XG4gICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gVGltZSBwYXJ0IGluIFwiJHtvcmlnaW5hbElucHV0fVwiIGlzIGN1cnJlbnRseSBpZ25vcmVkLiBVc2luZyBzdGFydCBvZiBkYXkuYFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBUcnkgcGFyc2luZyBcIk1vbnRoIERheVwiIChlLmcuLCBcIkF1Z3VzdCAxNVwiLCBcIkRlYyAxc3RcIilcbiAgICBpZiAoIXN1Y2Nlc3NmdWxseVBhcnNlZCkge1xuICAgICAgY29uc3QgbW9udGhEYXlSZWdleCA9XG4gICAgICAgIC9eKGphbig/OnVhcnkpP3xmZWIoPzpydWFyeSk/fG1hcig/OmNoKT98YXByKD86aWwpP3xtYXl8anVuKD86ZSk/fGp1bCg/OnkpP3xhdWcoPzp1c3QpP3xzZXAoPzp0ZW1iZXIpP3xvY3QoPzpvYmVyKT98bm92KD86ZW1iZXIpP3xkZWMoPzplbWJlcik/KVxccysoXFxkezEsMn0pKD86c3R8bmR8cmR8dGgpPyg/Oiw/XFxzKihcXGR7NH0pKT8vO1xuICAgICAgLy8gRnVydGhlciByZWdleCBmb3IgdGltZSBwYXJ0IGlmIHdlIHdlcmUgdG8gcGFyc2UgaXQ6ICg/OiBhdFxccysoXFxkezEsMn0oPzo6XFxkezJ9KT9cXHMqKD86YW18cG0pPykpP1xuICAgICAgY29uc3QgbW9udGhEYXlNYXRjaCA9IGlucHV0Lm1hdGNoKG1vbnRoRGF5UmVnZXgpO1xuXG4gICAgICBpZiAobW9udGhEYXlNYXRjaCkge1xuICAgICAgICBjb25zdCBtb250aFN0ciA9IG1vbnRoRGF5TWF0Y2hbMV0uc3Vic3RyaW5nKDAsIDMpO1xuICAgICAgICBjb25zdCBkYXkgPSBwYXJzZUludChtb250aERheU1hdGNoWzJdLCAxMCk7XG4gICAgICAgIGNvbnN0IHllYXJTdHIgPSBtb250aERheU1hdGNoWzNdO1xuXG4gICAgICAgIGNvbnN0IG1vbnRoTWFwOiB7IFtrZXk6IHN0cmluZ106IG51bWJlciB9ID0ge1xuICAgICAgICAgIGphbjogMCxcbiAgICAgICAgICBmZWI6IDEsXG4gICAgICAgICAgbWFyOiAyLFxuICAgICAgICAgIGFwcjogMyxcbiAgICAgICAgICBtYXk6IDQsXG4gICAgICAgICAganVuOiA1LFxuICAgICAgICAgIGp1bDogNixcbiAgICAgICAgICBhdWc6IDcsXG4gICAgICAgICAgc2VwOiA4LFxuICAgICAgICAgIG9jdDogOSxcbiAgICAgICAgICBub3Y6IDEwLFxuICAgICAgICAgIGRlYzogMTEsXG4gICAgICAgIH07XG4gICAgICAgIGNvbnN0IG1vbnRoID0gbW9udGhNYXBbbW9udGhTdHJdO1xuXG4gICAgICAgIGlmIChtb250aCAhPT0gdW5kZWZpbmVkICYmIGRheSA+PSAxICYmIGRheSA8PSAzMSkge1xuICAgICAgICAgIGxldCB5ZWFyID0geWVhclN0clxuICAgICAgICAgICAgPyBwYXJzZUludCh5ZWFyU3RyLCAxMClcbiAgICAgICAgICAgIDogYmFzZURhdGUuZ2V0VVRDRnVsbFllYXIoKTtcblxuICAgICAgICAgIGRldGVybWluZWRUYXJnZXREYXRlID0gbmV3IERhdGUoRGF0ZS5VVEMoeWVhciwgbW9udGgsIGRheSkpO1xuXG4gICAgICAgICAgLy8gQ2hlY2sgaWYgdmFsaWQgZGF0ZSAoZS5nLiBGZWIgMzApXG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgZGV0ZXJtaW5lZFRhcmdldERhdGUuZ2V0VVRDRlVUQ0RhdGUoKSAhPT0gZGF5IHx8XG4gICAgICAgICAgICBkZXRlcm1pbmVkVGFyZ2V0RGF0ZS5nZXRVVENNb250aCgpICE9PSBtb250aCB8fFxuICAgICAgICAgICAgZGV0ZXJtaW5lZFRhcmdldERhdGUuZ2V0VVRDRnVsbFllYXIoKSAhPT0geWVhclxuICAgICAgICAgICkge1xuICAgICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBJbnZhbGlkIE1vbnRoLURheS1ZZWFyIGNvbWJpbmF0aW9uOiAke2lucHV0fWBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIC8vIElmIG5vIHllYXIgc3BlY2lmaWVkIGFuZCBkYXRlIGhhcyBwYXNzZWQgZm9yIGN1cnJlbnQgeWVhciwgYXNzdW1lIG5leHQgeWVhci5cbiAgICAgICAgICAgIGlmIChcbiAgICAgICAgICAgICAgIXllYXJTdHIgJiZcbiAgICAgICAgICAgICAgZ2V0U3RhcnRPZkRheVVUQyhkZXRlcm1pbmVkVGFyZ2V0RGF0ZSkgPFxuICAgICAgICAgICAgICAgIGdldFN0YXJ0T2ZEYXlVVEMoYmFzZURhdGUpXG4gICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgeWVhcisrO1xuICAgICAgICAgICAgICBkZXRlcm1pbmVkVGFyZ2V0RGF0ZS5zZXRVVENGdWxsWWVhcih5ZWFyKTtcbiAgICAgICAgICAgICAgLy8gUmUtdmFsaWRhdGUgaWYgeWVhciBjaGFuZ2UgbWFkZSBpdCBpbnZhbGlkIChlLmcuIEZlYiAyOSlcbiAgICAgICAgICAgICAgaWYgKGRldGVybWluZWRUYXJnZXREYXRlLmdldFVUQ01vbnRoKCkgIT09IG1vbnRoKSB7XG4gICAgICAgICAgICAgICAgLy8gRGF5IHJvbGxlZCBvdmVyIGR1ZSB0byBpbnZhbGlkIGRhdGUgaW4gbmV3IHllYXJcbiAgICAgICAgICAgICAgICBsb2dnZXIud2FybihcbiAgICAgICAgICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBJbnZhbGlkIE1vbnRoLURheSBmb3IgbmV4dCB5ZWFyOiAke2lucHV0fWBcbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIHN1Y2Nlc3NmdWxseVBhcnNlZCA9IGZhbHNlOyAvLyBLZWVwIGl0IGZhbHNlXG4gICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgdGFyZ2V0RGF0ZSA9IGdldFN0YXJ0T2ZEYXlVVEMoZGV0ZXJtaW5lZFRhcmdldERhdGUpO1xuICAgICAgICAgICAgICAgIHN1Y2Nlc3NmdWxseVBhcnNlZCA9IHRydWU7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgIHRhcmdldERhdGUgPSBnZXRTdGFydE9mRGF5VVRDKGRldGVybWluZWRUYXJnZXREYXRlKTtcbiAgICAgICAgICAgICAgc3VjY2Vzc2Z1bGx5UGFyc2VkID0gdHJ1ZTtcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKHN1Y2Nlc3NmdWxseVBhcnNlZCAmJiBpbnB1dC5pbmNsdWRlcygnIGF0ICcpKSB7XG4gICAgICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBUaW1lIHBhcnQgaW4gXCIke29yaWdpbmFsSW5wdXR9XCIgaXMgY3VycmVudGx5IGlnbm9yZWQuIFVzaW5nIHN0YXJ0IG9mIGRheS5gXG4gICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIENvdWxkIG5vdCBwYXJzZSBtb250aC9kYXkgZnJvbTogJHtpbnB1dH1gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIGlmICghc3VjY2Vzc2Z1bGx5UGFyc2VkKSB7XG4gICAgdGFyZ2V0RGF0ZSA9IGdldFN0YXJ0T2ZEYXlVVEMoYmFzZURhdGUpOyAvLyBEZWZhdWx0IHRvIHRvZGF5IGlmIGFsbCBwYXJzaW5nIGZhaWxzXG4gICAgc3RhdHVzID0gJ3VucGFyc2VhYmxlJztcbiAgICB3YXJuaW5nTWVzc2FnZSA9IGBEYXRlIGNvbnRleHQgXCIke29yaWdpbmFsSW5wdXR9XCIgaXMgbm90IHJlY29nbml6ZWQgb3IgaXMgaW52YWxpZC4gRGVmYXVsdGluZyB0byB0b2RheS5gO1xuICAgIGxvZ2dlci53YXJuKGBbZGFpbHlCcmllZmluZ1NraWxsXSAke3dhcm5pbmdNZXNzYWdlfWApO1xuICB9XG5cbiAgLy8gRW5zdXJlIHRhcmdldERhdGUgaXRzZWxmIGlzIGF0IHRoZSBzdGFydCBvZiBpdHMgZGF5IGZvciBjb25zaXN0ZW50IFlZWVktTU0tREQgc3RyaW5nXG4gIHRhcmdldERhdGUgPSBnZXRTdGFydE9mRGF5VVRDKHRhcmdldERhdGUpOyAvLyBUaGlzIGlzIGNydWNpYWwgYWZ0ZXIgYW55IG1vZGlmaWNhdGlvbnNcblxuICByZXR1cm4ge1xuICAgIHRhcmdldERhdGU6IG5ldyBEYXRlKHRhcmdldERhdGUudmFsdWVPZigpKSwgLy8gUmV0dXJuIGEgY2xvbmVcbiAgICB0aW1lTWluSVNPOiBnZXRTdGFydE9mRGF5VVRDKHRhcmdldERhdGUpLnRvSVNPU3RyaW5nKCksXG4gICAgdGltZU1heElTTzogZ2V0RW5kT2ZEYXlVVEModGFyZ2V0RGF0ZSkudG9JU09TdHJpbmcoKSxcbiAgICB0YXJnZXREYXRlSVNPOiBnZXRVVENEYXRlWVlZWU1NREQodGFyZ2V0RGF0ZSksXG4gICAgaXNEYXRlUmFuZ2U6IHRydWUsXG4gICAgc3RhdHVzLFxuICAgIG9yaWdpbmFsSW5wdXQsXG4gICAgd2FybmluZ01lc3NhZ2UsXG4gIH07XG59XG5cbi8vIC0tLSBVcmdlbmN5IFNjb3JpbmcgVXRpbGl0eSAtLS1cblxuY29uc3QgSElHSF9VUkdFTkNZX0tFWVdPUkRTID0gW1xuICAndXJnZW50JyxcbiAgJ2FzYXAnLFxuICAnY3JpdGljYWwnLFxuICAnYWN0aW9uIHJlcXVpcmVkJyxcbiAgJ291dGFnZScsXG4gICdpbXBvcnRhbnQnLFxuICAnaW1tZWRpYXRlbHknLFxuXTtcbmNvbnN0IE1FRElVTV9VUkdFTkNZX0tFWVdPUkRTID0gW1xuICAncGxlYXNlIHJldmlldycsXG4gICdmZWVkYmFjayBuZWVkZWQnLFxuICAnZGVhZGxpbmUnLFxuICAncmVtaW5kZXInLFxuICAnZm9sbG93LXVwJyxcbiAgJ3F1ZXN0aW9uJyxcbl07XG5cbmZ1bmN0aW9uIGNhbGN1bGF0ZVVyZ2VuY3lTY29yZShcbiAgaXRlbTogQnJpZWZpbmdJdGVtLFxuICB0YXJnZXREYXRlOiBEYXRlLFxuICB0YXJnZXREYXRlSVNPOiBzdHJpbmdcbik6IG51bWJlciB7XG4gIGxldCBzY29yZSA9IDA7XG4gIGNvbnN0IG5vd0ZvckNvbnRleHQgPSBuZXcgRGF0ZSgpOyAvLyBVc2VkIGlmIHRhcmdldERhdGUgaXMgdG9kYXksIGZvciBcInRpbWUgdW50aWxcIlxuXG4gIC8vIC0tLSBLZXl3b3JkIGFuZCBDb250ZXh0IFNjb3JpbmcgLS0tXG4gIGxldCBrZXl3b3JkQm9udXMgPSAwO1xuICBjb25zdCB0ZXh0VG9TY2FuID0gYCR7aXRlbS50aXRsZSB8fCAnJ30gJHtpdGVtLmRldGFpbHMgfHwgJyd9YC50b0xvd2VyQ2FzZSgpO1xuICBpZiAoSElHSF9VUkdFTkNZX0tFWVdPUkRTLnNvbWUoKGt3KSA9PiB0ZXh0VG9TY2FuLmluY2x1ZGVzKGt3KSkpIHtcbiAgICBrZXl3b3JkQm9udXMgPSAyNTtcbiAgfSBlbHNlIGlmIChNRURJVU1fVVJHRU5DWV9LRVlXT1JEUy5zb21lKChrdykgPT4gdGV4dFRvU2Nhbi5pbmNsdWRlcyhrdykpKSB7XG4gICAga2V5d29yZEJvbnVzID0gMTU7XG4gIH1cblxuICBzd2l0Y2ggKGl0ZW0udHlwZSkge1xuICAgIGNhc2UgJ21lZXRpbmcnOlxuICAgICAgY29uc3QgbWVldGluZyA9IGl0ZW0ucmF3X2l0ZW0gYXMgQ2FsZW5kYXJFdmVudFN1bW1hcnk7XG4gICAgICBpZiAobWVldGluZyAmJiBtZWV0aW5nLnN0YXJ0KSB7XG4gICAgICAgIGNvbnN0IG1lZXRpbmdTdGFydERhdGUgPSBuZXcgRGF0ZShtZWV0aW5nLnN0YXJ0KTtcbiAgICAgICAgaWYgKGdldFVUQ0RhdGVZWVlZTU1ERChtZWV0aW5nU3RhcnREYXRlKSA9PT0gdGFyZ2V0RGF0ZUlTTykge1xuICAgICAgICAgIHNjb3JlICs9IDQwOyAvLyBCYXNlIHNjb3JlIGZvciBiZWluZyBhIG1lZXRpbmcgb24gdGhlIHRhcmdldCBkYXlcblxuICAgICAgICAgIGNvbnN0IGhvdXJzRnJvbVN0YXJ0T2ZEYXlUb01lZXRpbmdTdGFydCA9XG4gICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlLmdldFVUQ0hvdXJzKCkgK1xuICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZS5nZXRVVENNaW51dGVzKCkgLyA2MDtcbiAgICAgICAgICBjb25zdCB0aW1lUHJveGltaXR5U2NvcmUgPSBNYXRoLm1heChcbiAgICAgICAgICAgIDAsXG4gICAgICAgICAgICAoMjQgLSBob3Vyc0Zyb21TdGFydE9mRGF5VG9NZWV0aW5nU3RhcnQpICogMi41XG4gICAgICAgICAgKTtcbiAgICAgICAgICBzY29yZSArPSBNYXRoLm1pbih0aW1lUHJveGltaXR5U2NvcmUsIDQwKTsgLy8gQ2FwIHRpbWUgcHJveGltaXR5IGJvbnVzXG5cbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICB0YXJnZXREYXRlSVNPID09PSBnZXRVVENEYXRlWVlZWU1NREQobm93Rm9yQ29udGV4dCkgJiZcbiAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGUgPiBub3dGb3JDb250ZXh0XG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBjb25zdCBob3Vyc1VudGlsTWVldGluZyA9XG4gICAgICAgICAgICAgIChtZWV0aW5nU3RhcnREYXRlLmdldFRpbWUoKSAtIG5vd0ZvckNvbnRleHQuZ2V0VGltZSgpKSAvXG4gICAgICAgICAgICAgICgxMDAwICogNjAgKiA2MCk7XG4gICAgICAgICAgICBpZiAoaG91cnNVbnRpbE1lZXRpbmcgPCAxKSBzY29yZSArPSA1O1xuICAgICAgICAgICAgZWxzZSBpZiAoaG91cnNVbnRpbE1lZXRpbmcgPCAzKSBzY29yZSArPSAzO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIC8vIEF0dGVuZGVlIGNvdW50IGJvbnVzXG4gICAgICAgICAgaWYgKG1lZXRpbmcuYXR0ZW5kZWVzICYmIEFycmF5LmlzQXJyYXkobWVldGluZy5hdHRlbmRlZXMpKSB7XG4gICAgICAgICAgICBpZiAobWVldGluZy5hdHRlbmRlZXMubGVuZ3RoIDw9IDIpIHtcbiAgICAgICAgICAgICAgc2NvcmUgKz0gMjA7IC8vIDE6MSBvciB3aXRoIG9uZSBvdGhlciBwZXJzb25cbiAgICAgICAgICAgIH0gZWxzZSBpZiAobWVldGluZy5hdHRlbmRlZXMubGVuZ3RoIDw9IDUpIHtcbiAgICAgICAgICAgICAgc2NvcmUgKz0gMTA7IC8vIFNtYWxsIGdyb3VwXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9XG4gICAgICBicmVhaztcbiAgICBjYXNlICd0YXNrJzpcbiAgICAgIGNvbnN0IHRhc2sgPSBpdGVtLnJhd19pdGVtIGFzIE5vdGlvblRhc2s7XG4gICAgICBpZiAodGFzaykge1xuICAgICAgICBpZiAodGFzay5zdGF0dXMgPT09ICdEb25lJyB8fCB0YXNrLnN0YXR1cyA9PT0gJ0NhbmNlbGxlZCcpIHtcbiAgICAgICAgICBzY29yZSA9IDA7XG4gICAgICAgICAgYnJlYWs7IC8vIE5vIGZ1cnRoZXIgc2NvcmluZyBmb3IgY29tcGxldGVkL2NhbmNlbGxlZCB0YXNrc1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcHJpb3JpdHlCb251c01hcDoge1xuICAgICAgICAgIFtrZXkgaW4gTm90aW9uVGFza1ByaW9yaXR5IHwgc3RyaW5nXTogbnVtYmVyO1xuICAgICAgICB9ID0geyBIaWdoOiAxMCwgTWVkaXVtOiA1LCBMb3c6IDAgfTtcbiAgICAgICAgY29uc3QgcHJpb3JpdHlCb251cyA9IHByaW9yaXR5Qm9udXNNYXBbdGFzay5wcmlvcml0eSB8fCAnTG93J10gfHwgMDtcblxuICAgICAgICBpZiAodGFzay5kdWVEYXRlKSB7XG4gICAgICAgICAgY29uc3QgZHVlRGF0ZU9ubHlJU08gPSB0YXNrLmR1ZURhdGUuc3BsaXQoJ1QnKVswXTtcbiAgICAgICAgICBjb25zdCB0YXJnZXREYXRlT25seUlTTyA9IHRhcmdldERhdGVJU087IC8vIEFscmVhZHkgWVlZWS1NTS1ERFxuXG4gICAgICAgICAgaWYgKGR1ZURhdGVPbmx5SVNPIDwgdGFyZ2V0RGF0ZU9ubHlJU08pIHtcbiAgICAgICAgICAgIC8vIE92ZXJkdWUgcmVsYXRpdmUgdG8gdGFyZ2V0RGF0ZVxuICAgICAgICAgICAgc2NvcmUgPSA4MCArIHByaW9yaXR5Qm9udXM7XG4gICAgICAgICAgfSBlbHNlIGlmIChkdWVEYXRlT25seUlTTyA9PT0gdGFyZ2V0RGF0ZU9ubHlJU08pIHtcbiAgICAgICAgICAgIC8vIER1ZSBvbiB0YXJnZXREYXRlXG4gICAgICAgICAgICBzY29yZSA9IDcwICsgcHJpb3JpdHlCb251cztcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgLy8gRHVlIGluIHRoZSBmdXR1cmUgcmVsYXRpdmUgdG8gdGFyZ2V0RGF0ZVxuICAgICAgICAgICAgY29uc3QgZHVlRGF0ZU9iaiA9IG5ldyBEYXRlKGR1ZURhdGVPbmx5SVNPICsgJ1QwMDowMDowMFonKTsgLy8gRW5zdXJlIHBhcnNlZCBhcyBVVENcbiAgICAgICAgICAgIGNvbnN0IHRhcmdldERhdGVPYmogPSBuZXcgRGF0ZSh0YXJnZXREYXRlT25seUlTTyArICdUMDA6MDA6MDBaJyk7IC8vIEVuc3VyZSBwYXJzZWQgYXMgVVRDXG4gICAgICAgICAgICBjb25zdCBkaWZmRGF5cyA9XG4gICAgICAgICAgICAgIChkdWVEYXRlT2JqLmdldFRpbWUoKSAtIHRhcmdldERhdGVPYmouZ2V0VGltZSgpKSAvXG4gICAgICAgICAgICAgICgxMDAwICogNjAgKiA2MCAqIDI0KTtcblxuICAgICAgICAgICAgaWYgKGRpZmZEYXlzIDw9IDMpIHtcbiAgICAgICAgICAgICAgLy8gRHVlIFNvb24gKHdpdGhpbiAxLTMgZGF5cyBhZnRlciB0YXJnZXREYXRlKVxuICAgICAgICAgICAgICBzY29yZSA9IDUwICsgcHJpb3JpdHlCb251cztcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgIC8vIER1ZSBGdXR1cmUgKGJleW9uZCAzIGRheXMgYWZ0ZXIgdGFyZ2V0RGF0ZSlcbiAgICAgICAgICAgICAgc2NvcmUgPSAzMCArIChwcmlvcml0eUJvbnVzID4gMCA/IE1hdGgubWluKDUsIHByaW9yaXR5Qm9udXMpIDogMCk7IC8vIFNtYWxsZXIgcHJpb3JpdHkgYm9udXMgZm9yIGRpc3RhbnQgdGFza3NcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgLy8gTm8gRHVlIERhdGVcbiAgICAgICAgICBzY29yZSA9IDI1ICsgcHJpb3JpdHlCb251cztcbiAgICAgICAgICAvLyBSZWNlbmN5IG9mIEFjdGl2aXR5IGJvbnVzIGZvciB0YXNrcyB3aXRoIG5vIGR1ZSBkYXRlXG4gICAgICAgICAgY29uc3QgYWN0aXZpdHlEYXRlU3RyID0gdGFzay5sYXN0X2VkaXRlZF90aW1lIHx8IHRhc2suY3JlYXRlZERhdGU7XG4gICAgICAgICAgaWYgKGFjdGl2aXR5RGF0ZVN0cikge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgY29uc3QgYWN0aXZpdHlEYXRlID0gbmV3IERhdGUoYWN0aXZpdHlEYXRlU3RyKTtcbiAgICAgICAgICAgICAgLy8gQ29tcGFyZSB3aXRoICdub3dGb3JDb250ZXh0JyB3aGljaCBpcyB0aGUgYWN0dWFsIGN1cnJlbnQgZGF0ZSB3aGVuIHNraWxsIHJ1bnNcbiAgICAgICAgICAgICAgY29uc3QgZGF5c1NpbmNlQWN0aXZpdHkgPVxuICAgICAgICAgICAgICAgIChub3dGb3JDb250ZXh0LmdldFRpbWUoKSAtIGFjdGl2aXR5RGF0ZS5nZXRUaW1lKCkpIC9cbiAgICAgICAgICAgICAgICAoMTAwMCAqIDYwICogNjAgKiAyNCk7XG4gICAgICAgICAgICAgIGlmIChkYXlzU2luY2VBY3Rpdml0eSA8PSA3KSB7XG4gICAgICAgICAgICAgICAgc2NvcmUgKz0gNTtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgICBsb2dnZXIud2FybihcbiAgICAgICAgICAgICAgICBgW2NhbGN1bGF0ZVVyZ2VuY3lTY29yZV0gQ291bGQgbm90IHBhcnNlIHRhc2sgYWN0aXZpdHkgZGF0ZTogJHthY3Rpdml0eURhdGVTdHJ9YFxuICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuICAgICAgYnJlYWs7XG4gICAgY2FzZSAnZW1haWwnOlxuICAgICAgY29uc3QgZW1haWwgPSBpdGVtLnJhd19pdGVtIGFzIEdtYWlsTWVzc2FnZVNuaXBwZXQ7XG4gICAgICBzY29yZSArPSA1MDsgLy8gQmFzZSBzY29yZSBmb3IgYmVpbmcgYSByZWNlbnQsIHVucmVhZCBlbWFpbCBmb3IgdGhlIHRhcmdldERhdGVcbiAgICAgIHNjb3JlICs9IGtleXdvcmRCb251czsgLy8gQWRkIGtleXdvcmQgYm9udXNcbiAgICAgIGlmIChlbWFpbCAmJiBlbWFpbC5kYXRlKSB7XG4gICAgICAgIGNvbnN0IGVtYWlsRGF0ZSA9IG5ldyBEYXRlKGVtYWlsLmRhdGUpO1xuICAgICAgICBpZiAodGFyZ2V0RGF0ZUlTTyA9PT0gZ2V0VVRDRGF0ZVlZWVlNTUREKG5vd0ZvckNvbnRleHQpKSB7XG4gICAgICAgICAgY29uc3QgaG91cnNBZ29SZWNlaXZlZCA9XG4gICAgICAgICAgICAobm93Rm9yQ29udGV4dC5nZXRUaW1lKCkgLSBlbWFpbERhdGUuZ2V0VGltZSgpKSAvICgxMDAwICogNjAgKiA2MCk7XG4gICAgICAgICAgaWYgKGhvdXJzQWdvUmVjZWl2ZWQgPj0gMCAmJiBob3Vyc0Fnb1JlY2VpdmVkIDwgNCkgc2NvcmUgKz0gNTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgICAgYnJlYWs7XG4gICAgY2FzZSAnc2xhY2tfbWVzc2FnZSc6XG4gICAgICBjb25zdCBzbGFja01zZyA9IGl0ZW0ucmF3X2l0ZW0gYXMgU2xhY2tNZXNzYWdlU25pcHBldDtcbiAgICAgIHNjb3JlICs9IDQ1OyAvLyBCYXNlIHNjb3JlIGZvciBiZWluZyBhIHJlY2VudCBETS9tZW50aW9uIG9uIHRhcmdldERhdGUuXG4gICAgICBzY29yZSArPSBrZXl3b3JkQm9udXM7IC8vIEFkZCBrZXl3b3JkIGJvbnVzXG4gICAgICBpZiAoc2xhY2tNc2cgJiYgc2xhY2tNc2cudGltZXN0YW1wKSB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgY29uc3QgbWVzc2FnZURhdGUgPSBuZXcgRGF0ZShzbGFja01zZy50aW1lc3RhbXApO1xuICAgICAgICAgIGlmICh0YXJnZXREYXRlSVNPID09PSBnZXRVVENEYXRlWVlZWU1NREQobm93Rm9yQ29udGV4dCkpIHtcbiAgICAgICAgICAgIGNvbnN0IGhvdXJzQWdvUmVjZWl2ZWQgPVxuICAgICAgICAgICAgICAobm93Rm9yQ29udGV4dC5nZXRUaW1lKCkgLSBtZXNzYWdlRGF0ZS5nZXRUaW1lKCkpIC9cbiAgICAgICAgICAgICAgKDEwMDAgKiA2MCAqIDYwKTtcbiAgICAgICAgICAgIGlmIChob3Vyc0Fnb1JlY2VpdmVkID49IDAgJiYgaG91cnNBZ29SZWNlaXZlZCA8IDIpIHNjb3JlICs9IDU7XG4gICAgICAgICAgfVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICBgW2NhbGN1bGF0ZVVyZ2VuY3lTY29yZV0gQ291bGQgbm90IHBhcnNlIFNsYWNrIG1lc3NhZ2UgdGltZXN0YW1wOiAke3NsYWNrTXNnLnRpbWVzdGFtcH1gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgICAgYnJlYWs7XG4gICAgY2FzZSAndGVhbXNfbWVzc2FnZSc6XG4gICAgICBjb25zdCB0ZWFtc01zZyA9IGl0ZW0ucmF3X2l0ZW0gYXMgTVNUZWFtc01lc3NhZ2U7XG4gICAgICBzY29yZSArPSA0NTsgLy8gQmFzZSBzY29yZSBmb3IgYmVpbmcgYSByZWNlbnQgRE0vbWVudGlvbiBvbiB0YXJnZXREYXRlLlxuICAgICAgc2NvcmUgKz0ga2V5d29yZEJvbnVzOyAvLyBBZGQga2V5d29yZCBib251c1xuICAgICAgaWYgKHRlYW1zTXNnICYmIHRlYW1zTXNnLmNyZWF0ZWREYXRlVGltZSkge1xuICAgICAgICB0cnkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2VEYXRlID0gbmV3IERhdGUodGVhbXNNc2cuY3JlYXRlZERhdGVUaW1lKTtcbiAgICAgICAgICBpZiAodGFyZ2V0RGF0ZUlTTyA9PT0gZ2V0VVRDRGF0ZVlZWVlNTUREKG5vd0ZvckNvbnRleHQpKSB7XG4gICAgICAgICAgICBjb25zdCBob3Vyc0Fnb1JlY2VpdmVkID1cbiAgICAgICAgICAgICAgKG5vd0ZvckNvbnRleHQuZ2V0VGltZSgpIC0gbWVzc2FnZURhdGUuZ2V0VGltZSgpKSAvXG4gICAgICAgICAgICAgICgxMDAwICogNjAgKiA2MCk7XG4gICAgICAgICAgICBpZiAoaG91cnNBZ29SZWNlaXZlZCA+PSAwICYmIGhvdXJzQWdvUmVjZWl2ZWQgPCAyKSBzY29yZSArPSA1O1xuICAgICAgICAgIH1cbiAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgYFtjYWxjdWxhdGVVcmdlbmN5U2NvcmVdIENvdWxkIG5vdCBwYXJzZSBNUyBUZWFtcyBtZXNzYWdlIGNyZWF0ZWREYXRlVGltZTogJHt0ZWFtc01zZy5jcmVhdGVkRGF0ZVRpbWV9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICAgIGJyZWFrO1xuICAgIGRlZmF1bHQ6XG4gICAgICBzY29yZSA9IDIwOyAvLyBEZWZhdWx0IGxvdyBzY29yZSBmb3IgdW5rbm93biBvciBvdGhlciB0eXBlc1xuICB9XG4gIHJldHVybiBNYXRoLm1heCgwLCBNYXRoLm1pbihNYXRoLnJvdW5kKHNjb3JlKSwgMTAwKSk7IC8vIEVuc3VyZSBzY29yZSBpcyBiZXR3ZWVuIDAtMTAwIGFuZCBhbiBpbnRlZ2VyXG59XG5cbi8vIEhlbHBlciBmdW5jdGlvbiB0byBnZXQgYSB1c2VyLWZyaWVuZGx5IGRhdGUgc3RyaW5nXG5mdW5jdGlvbiBnZXRGcmllbmRseURhdGVTdHJpbmcoXG4gIGRhdGU6IERhdGUsXG4gIGJhc2VEYXRlRm9yQ29tcGFyaXNvbjogRGF0ZSA9IG5ldyBEYXRlKClcbik6IHN0cmluZyB7XG4gIGNvbnN0IHRvZGF5ID0gZ2V0U3RhcnRPZkRheVVUQyhuZXcgRGF0ZShiYXNlRGF0ZUZvckNvbXBhcmlzb24udmFsdWVPZigpKSk7XG4gIGNvbnN0IHRvbW9ycm93ID0gZ2V0U3RhcnRPZkRheVVUQyhuZXcgRGF0ZShiYXNlRGF0ZUZvckNvbXBhcmlzb24udmFsdWVPZigpKSk7XG4gIHRvbW9ycm93LnNldFVUQ0RhdGUodG9kYXkuZ2V0VVRDRGF0ZSgpICsgMSk7XG4gIGNvbnN0IHllc3RlcmRheSA9IGdldFN0YXJ0T2ZEYXlVVEMobmV3IERhdGUoYmFzZURhdGVGb3JDb21wYXJpc29uLnZhbHVlT2YoKSkpO1xuICB5ZXN0ZXJkYXkuc2V0VVRDRGF0ZSh0b2RheS5nZXRVVENEYXRlKCkgLSAxKTtcblxuICBjb25zdCB0YXJnZXQgPSBnZXRTdGFydE9mRGF5VVRDKG5ldyBEYXRlKGRhdGUudmFsdWVPZigpKSk7XG5cbiAgaWYgKHRhcmdldC5nZXRUaW1lKCkgPT09IHRvZGF5LmdldFRpbWUoKSkgcmV0dXJuICdUb2RheSc7XG4gIGlmICh0YXJnZXQuZ2V0VGltZSgpID09PSB0b21vcnJvdy5nZXRUaW1lKCkpIHJldHVybiAnVG9tb3Jyb3cnO1xuICBpZiAodGFyZ2V0LmdldFRpbWUoKSA9PT0geWVzdGVyZGF5LmdldFRpbWUoKSkgcmV0dXJuICdZZXN0ZXJkYXknO1xuXG4gIHJldHVybiB0YXJnZXQudG9Mb2NhbGVEYXRlU3RyaW5nKHVuZGVmaW5lZCwge1xuICAgIHdlZWtkYXk6ICdsb25nJyxcbiAgICBtb250aDogJ2xvbmcnLFxuICAgIGRheTogJ251bWVyaWMnLFxuICAgIHllYXI6ICdudW1lcmljJyxcbiAgICB0aW1lWm9uZTogJ1VUQycsXG4gIH0pO1xufVxuXG4vKipcbiAqIEdlbmVyYXRlcyBhIGRhaWx5IHByaW9yaXR5IGJyaWVmaW5nIGZvciB0aGUgdXNlciwgY29uc29saWRhdGluZyBpbmZvcm1hdGlvblxuICogZnJvbSB0YXNrcywgbWVldGluZ3MsIGFuZCBwb3RlbnRpYWxseSB1cmdlbnQgbWVzc2FnZXMuXG4gKlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIgcmVxdWVzdGluZyB0aGUgYnJpZWZpbmcuXG4gKiBAcGFyYW0gbmx1RW50aXRpZXMgVGhlIHBhcnNlZCBOTFUgZW50aXRpZXMgZnJvbSB0aGUgR2V0RGFpbHlQcmlvcml0eUJyaWVmaW5nIGludGVudC5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSB0aGF0IHJlc29sdmVzIHRvIEdldERhaWx5UHJpb3JpdHlCcmllZmluZ1NraWxsUmVzcG9uc2UuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZW5lcmF0ZURhaWx5QnJpZWZpbmcoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBubHVFbnRpdGllczogR2V0RGFpbHlQcmlvcml0eUJyaWVmaW5nTmx1RW50aXRpZXNcbik6IFByb21pc2U8R2V0RGFpbHlQcmlvcml0eUJyaWVmaW5nU2tpbGxSZXNwb25zZT4ge1xuICAvLyBVc2UgdGhlIG5ldyBkYXRlIHBhcnNpbmcgbG9naWNcbiAgY29uc3QgcGFyc2VkRGF0ZUluZm8gPSBwYXJzZURhdGVDb250ZXh0TG9naWMobmx1RW50aXRpZXMuZGF0ZV9jb250ZXh0KTtcblxuICBsb2dnZXIuaW5mbyhcbiAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gR2VuZXJhdGluZyBkYWlseSBicmllZmluZyBmb3IgdXNlciAke3VzZXJJZH0gZm9yIGRhdGVDb250ZXh0OiBcIiR7bmx1RW50aXRpZXMuZGF0ZV9jb250ZXh0IHx8ICd0b2RheSd9XCIsIHJlc29sdmVkIHRvOiAke3BhcnNlZERhdGVJbmZvLnRhcmdldERhdGVJU099YFxuICApO1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIE5MVSBFbnRpdGllczogJHtKU09OLnN0cmluZ2lmeShubHVFbnRpdGllcyl9YFxuICApO1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIFBhcnNlZCBEYXRlIEluZm86ICR7SlNPTi5zdHJpbmdpZnkocGFyc2VkRGF0ZUluZm8pfWBcbiAgKTtcblxuICBjb25zdCBicmllZmluZ0RhdGE6IERhaWx5QnJpZWZpbmdEYXRhID0ge1xuICAgIGJyaWVmaW5nX2RhdGU6IHBhcnNlZERhdGVJbmZvLnRhcmdldERhdGVJU08sIC8vIFVzZSByZXNvbHZlZCBkYXRlXG4gICAgdXNlcl9pZDogdXNlcklkLFxuICAgIHByaW9yaXR5X2l0ZW1zOiBbXSxcbiAgICBlcnJvcnNfZW5jb3VudGVyZWQ6IFtdLFxuICB9O1xuXG4gIGlmIChwYXJzZWREYXRlSW5mby53YXJuaW5nTWVzc2FnZSkge1xuICAgIGJyaWVmaW5nRGF0YS5lcnJvcnNfZW5jb3VudGVyZWQ/LnB1c2goe1xuICAgICAgc291cmNlX2FyZWE6ICdkYXRlX3BhcnNpbmcnLFxuICAgICAgbWVzc2FnZTogcGFyc2VkRGF0ZUluZm8ud2FybmluZ01lc3NhZ2UsXG4gICAgICBkZXRhaWxzOiBgT3JpZ2luYWwgaW5wdXQ6ICR7cGFyc2VkRGF0ZUluZm8ub3JpZ2luYWxJbnB1dH1gLFxuICAgIH0pO1xuICB9XG5cbiAgY29uc3QgZm9jdXNBcmVhcyA9IG5sdUVudGl0aWVzLmZvY3VzX2FyZWFzIHx8IFtcbiAgICAndGFza3MnLFxuICAgICdtZWV0aW5ncycsXG4gICAgJ3VyZ2VudF9lbWFpbHMnLFxuICAgICd1cmdlbnRfc2xhY2tfbWVzc2FnZXMnLFxuICBdOyAvLyBEZWZhdWx0IGZvY3VzIGFyZWFzXG5cbiAgdHJ5IHtcbiAgICAvLyBGZXRjaCBUYXNrc1xuICAgIGlmIChmb2N1c0FyZWFzLmluY2x1ZGVzKCd0YXNrcycpKSB7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEZldGNoaW5nIHRhc2tzIGZvciBicmllZmluZyBmb3IgdGFyZ2V0RGF0ZTogJHtwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPfS5gXG4gICAgICApO1xuICAgICAgaWYgKCFBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCkge1xuICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgJ1tkYWlseUJyaWVmaW5nU2tpbGxdIEFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEIGlzIG5vdCBjb25maWd1cmVkLiBDYW5ub3QgZmV0Y2ggdGFza3MuJ1xuICAgICAgICApO1xuICAgICAgICBicmllZmluZ0RhdGEuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICBzb3VyY2VfYXJlYTogJ3Rhc2tzJyxcbiAgICAgICAgICBtZXNzYWdlOiAnTm90aW9uIHRhc2tzIGRhdGFiYXNlIElEIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICAgIH0pO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAvLyBEZWZpbmUgcGFyYW1zIGZvciBvdmVyZHVlIHRhc2tzOiBkdWUgYmVmb3JlIHRhcmdldERhdGVJU08sIG5vdCBEb25lIG9yIENhbmNlbGxlZFxuICAgICAgICAgIGNvbnN0IG92ZXJkdWVUYXNrUGFyYW1zOiBRdWVyeU5vdGlvblRhc2tzUGFyYW1zID0ge1xuICAgICAgICAgICAgbm90aW9uVGFza3NEYklkOiBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCxcbiAgICAgICAgICAgIGR1ZURhdGVCZWZvcmU6IHBhcnNlZERhdGVJbmZvLnRhcmdldERhdGVJU08sXG4gICAgICAgICAgICBzdGF0dXNfbm90X2VxdWFsczogWydEb25lJywgJ0NhbmNlbGxlZCddLFxuICAgICAgICAgICAgbGltaXQ6IDEwLFxuICAgICAgICAgIH07XG4gICAgICAgICAgaWYgKG5sdUVudGl0aWVzLnByb2plY3RfZmlsdGVyKVxuICAgICAgICAgICAgb3ZlcmR1ZVRhc2tQYXJhbXMubGlzdE5hbWUgPSBubHVFbnRpdGllcy5wcm9qZWN0X2ZpbHRlcjtcbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICBubHVFbnRpdGllcy51cmdlbmN5X2xldmVsICYmXG4gICAgICAgICAgICAobmx1RW50aXRpZXMudXJnZW5jeV9sZXZlbCA9PT0gJ2hpZ2gnIHx8XG4gICAgICAgICAgICAgIG5sdUVudGl0aWVzLnVyZ2VuY3lfbGV2ZWwgPT09ICdjcml0aWNhbCcpXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBvdmVyZHVlVGFza1BhcmFtcy5wcmlvcml0eSA9IG5sdUVudGl0aWVzLnVyZ2VuY3lfbGV2ZWw7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgLy8gRGVmaW5lIHBhcmFtcyBmb3IgdGFza3MgZHVlIG9uIHRhcmdldERhdGVJU086IGR1ZSBlcXVhbHMgdGFyZ2V0RGF0ZUlTTywgbm90IERvbmUgb3IgQ2FuY2VsbGVkXG4gICAgICAgICAgY29uc3QgZHVlT25UYXJnZXREYXRlVGFza1BhcmFtczogUXVlcnlOb3Rpb25UYXNrc1BhcmFtcyA9IHtcbiAgICAgICAgICAgIG5vdGlvblRhc2tzRGJJZDogQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQsXG4gICAgICAgICAgICBkdWVEYXRlRXF1YWxzOiBwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPLFxuICAgICAgICAgICAgc3RhdHVzX25vdF9lcXVhbHM6IFsnRG9uZScsICdDYW5jZWxsZWQnXSxcbiAgICAgICAgICAgIGxpbWl0OiAxMCxcbiAgICAgICAgICB9O1xuICAgICAgICAgIGlmIChubHVFbnRpdGllcy5wcm9qZWN0X2ZpbHRlcilcbiAgICAgICAgICAgIGR1ZU9uVGFyZ2V0RGF0ZVRhc2tQYXJhbXMubGlzdE5hbWUgPSBubHVFbnRpdGllcy5wcm9qZWN0X2ZpbHRlcjtcbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICBubHVFbnRpdGllcy51cmdlbmN5X2xldmVsICYmXG4gICAgICAgICAgICAobmx1RW50aXRpZXMudXJnZW5jeV9sZXZlbCA9PT0gJ2hpZ2gnIHx8XG4gICAgICAgICAgICAgIG5sdUVudGl0aWVzLnVyZ2VuY3lfbGV2ZWwgPT09ICdjcml0aWNhbCcpXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBkdWVPblRhcmdldERhdGVUYXNrUGFyYW1zLnByaW9yaXR5ID0gbmx1RW50aXRpZXMudXJnZW5jeV9sZXZlbDtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBjb25zdCBbb3ZlcmR1ZVRhc2tzUmVzcG9uc2UsIGR1ZU9uVGFyZ2V0RGF0ZVRhc2tzUmVzcG9uc2VdID1cbiAgICAgICAgICAgIGF3YWl0IFByb21pc2UuYWxsKFtcbiAgICAgICAgICAgICAgcXVlcnlOb3Rpb25UYXNrc0JhY2tlbmQodXNlcklkLCBvdmVyZHVlVGFza1BhcmFtcyksXG4gICAgICAgICAgICAgIHF1ZXJ5Tm90aW9uVGFza3NCYWNrZW5kKHVzZXJJZCwgZHVlT25UYXJnZXREYXRlVGFza1BhcmFtcyksXG4gICAgICAgICAgICBdKTtcblxuICAgICAgICAgIGNvbnN0IGZldGNoZWRUYXNrczogTm90aW9uVGFza1tdID0gW107XG4gICAgICAgICAgaWYgKG92ZXJkdWVUYXNrc1Jlc3BvbnNlLnN1Y2Nlc3MgJiYgb3ZlcmR1ZVRhc2tzUmVzcG9uc2UudGFza3MpIHtcbiAgICAgICAgICAgIGZldGNoZWRUYXNrcy5wdXNoKC4uLm92ZXJkdWVUYXNrc1Jlc3BvbnNlLnRhc2tzKTtcbiAgICAgICAgICB9IGVsc2UgaWYgKCFvdmVyZHVlVGFza3NSZXNwb25zZS5zdWNjZXNzKSB7XG4gICAgICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBFcnJvciBmZXRjaGluZyBvdmVyZHVlIHRhc2tzOiAke292ZXJkdWVUYXNrc1Jlc3BvbnNlLmVycm9yfWBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBicmllZmluZ0RhdGEuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICAgICAgc291cmNlX2FyZWE6ICd0YXNrcycsXG4gICAgICAgICAgICAgIG1lc3NhZ2U6IGBFcnJvciBmZXRjaGluZyBvdmVyZHVlIHRhc2tzIChiZWZvcmUgJHtwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPfSk6ICR7b3ZlcmR1ZVRhc2tzUmVzcG9uc2UuZXJyb3J9YCxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChcbiAgICAgICAgICAgIGR1ZU9uVGFyZ2V0RGF0ZVRhc2tzUmVzcG9uc2Uuc3VjY2VzcyAmJlxuICAgICAgICAgICAgZHVlT25UYXJnZXREYXRlVGFza3NSZXNwb25zZS50YXNrc1xuICAgICAgICAgICkge1xuICAgICAgICAgICAgZHVlT25UYXJnZXREYXRlVGFza3NSZXNwb25zZS50YXNrcy5mb3JFYWNoKCh0YXNrKSA9PiB7XG4gICAgICAgICAgICAgIGlmICghZmV0Y2hlZFRhc2tzLmZpbmQoKGZ0KSA9PiBmdC5pZCA9PT0gdGFzay5pZCkpIHtcbiAgICAgICAgICAgICAgICBmZXRjaGVkVGFza3MucHVzaCh0YXNrKTtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgfSBlbHNlIGlmICghZHVlT25UYXJnZXREYXRlVGFza3NSZXNwb25zZS5zdWNjZXNzKSB7XG4gICAgICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBFcnJvciBmZXRjaGluZyB0YXNrcyBkdWUgb24gJHtwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPfTogJHtkdWVPblRhcmdldERhdGVUYXNrc1Jlc3BvbnNlLmVycm9yfWBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBicmllZmluZ0RhdGEuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICAgICAgc291cmNlX2FyZWE6ICd0YXNrcycsXG4gICAgICAgICAgICAgIG1lc3NhZ2U6IGBFcnJvciBmZXRjaGluZyB0YXNrcyBkdWUgb24gJHtwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPfTogJHtkdWVPblRhcmdldERhdGVUYXNrc1Jlc3BvbnNlLmVycm9yfWAsXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAoZmV0Y2hlZFRhc2tzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIGZldGNoZWRUYXNrcy5zb3J0KChhLCBiKSA9PiB7XG4gICAgICAgICAgICAgIGNvbnN0IGFJc092ZXJkdWUgPVxuICAgICAgICAgICAgICAgIGEuZHVlRGF0ZSAmJiBhLmR1ZURhdGUgPCBwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPO1xuICAgICAgICAgICAgICBjb25zdCBiSXNPdmVyZHVlID1cbiAgICAgICAgICAgICAgICBiLmR1ZURhdGUgJiYgYi5kdWVEYXRlIDwgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTTztcbiAgICAgICAgICAgICAgaWYgKGFJc092ZXJkdWUgJiYgIWJJc092ZXJkdWUpIHJldHVybiAtMTtcbiAgICAgICAgICAgICAgaWYgKCFhSXNPdmVyZHVlICYmIGJJc092ZXJkdWUpIHJldHVybiAxO1xuXG4gICAgICAgICAgICAgIGNvbnN0IHByaW9yaXR5T3JkZXIgPSB7IEhpZ2g6IDEsIE1lZGl1bTogMiwgTG93OiAzIH07XG4gICAgICAgICAgICAgIGNvbnN0IGFQcmlvID0gcHJpb3JpdHlPcmRlclthLnByaW9yaXR5IHx8ICdMb3cnXSB8fCAzO1xuICAgICAgICAgICAgICBjb25zdCBiUHJpbyA9IHByaW9yaXR5T3JkZXJbYi5wcmlvcml0eSB8fCAnTG93J10gfHwgMztcbiAgICAgICAgICAgICAgaWYgKGFQcmlvICE9PSBiUHJpbykgcmV0dXJuIGFQcmlvIC0gYlByaW87XG5cbiAgICAgICAgICAgICAgY29uc3QgYUR1ZURhdGUgPSBhLmR1ZURhdGVcbiAgICAgICAgICAgICAgICA/IG5ldyBEYXRlKGEuZHVlRGF0ZSkuZ2V0VGltZSgpXG4gICAgICAgICAgICAgICAgOiBJbmZpbml0eTtcbiAgICAgICAgICAgICAgY29uc3QgYkR1ZURhdGUgPSBiLmR1ZURhdGVcbiAgICAgICAgICAgICAgICA/IG5ldyBEYXRlKGIuZHVlRGF0ZSkuZ2V0VGltZSgpXG4gICAgICAgICAgICAgICAgOiBJbmZpbml0eTtcbiAgICAgICAgICAgICAgcmV0dXJuIGFEdWVEYXRlIC0gYkR1ZURhdGU7XG4gICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgZmV0Y2hlZFRhc2tzLmZvckVhY2goKHRhc2spID0+IHtcbiAgICAgICAgICAgICAgbGV0IGRldGFpbHMgPSBgU3RhdHVzOiAke3Rhc2suc3RhdHVzfWA7XG4gICAgICAgICAgICAgIGlmICh0YXNrLmR1ZURhdGUpIHtcbiAgICAgICAgICAgICAgICBjb25zdCBkdWVEYXRlID0gbmV3IERhdGUodGFzay5kdWVEYXRlKTtcbiAgICAgICAgICAgICAgICAvLyBVc2UgdGFyZ2V0RGF0ZUlTTyBmb3Igb3ZlcmR1ZSBjb21wYXJpc29uXG4gICAgICAgICAgICAgICAgY29uc3QgaXNPdmVyZHVlID1cbiAgICAgICAgICAgICAgICAgIGR1ZURhdGUudG9JU09TdHJpbmcoKS5zcGxpdCgnVCcpWzBdIDxcbiAgICAgICAgICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTTyAmJlxuICAgICAgICAgICAgICAgICAgdGFzay5zdGF0dXMgIT09ICdEb25lJyAmJlxuICAgICAgICAgICAgICAgICAgdGFzay5zdGF0dXMgIT09ICdDYW5jZWxsZWQnO1xuICAgICAgICAgICAgICAgIGRldGFpbHMgKz0gYCwgRHVlOiAke2R1ZURhdGUudG9Mb2NhbGVEYXRlU3RyaW5nKFtdLCB7IG1vbnRoOiAnc2hvcnQnLCBkYXk6ICdudW1lcmljJywgeWVhcjogZHVlRGF0ZS5nZXRVVENGdWxsWWVhcigpICE9PSBuZXcgRGF0ZSgpLmdldFVUQ0Z1bGxZZWFyKCkgPyAnbnVtZXJpYycgOiB1bmRlZmluZWQgfSl9YDtcbiAgICAgICAgICAgICAgICBpZiAoaXNPdmVyZHVlKSBkZXRhaWxzICs9ICcgKE9WRVJEVUUpJztcbiAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBkZXRhaWxzICs9ICcsIER1ZTogTi9BJztcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICBpZiAodGFzay5wcmlvcml0eSkgZGV0YWlscyArPSBgLCBQcmlvOiAke3Rhc2sucHJpb3JpdHl9YDtcbiAgICAgICAgICAgICAgaWYgKHRhc2subGlzdE5hbWUpIGRldGFpbHMgKz0gYCwgTGlzdDogJHt0YXNrLmxpc3ROYW1lfWA7XG5cbiAgICAgICAgICAgICAgYnJpZWZpbmdEYXRhLnByaW9yaXR5X2l0ZW1zLnB1c2goe1xuICAgICAgICAgICAgICAgIHR5cGU6ICd0YXNrJyxcbiAgICAgICAgICAgICAgICB0aXRsZTogdGFzay5kZXNjcmlwdGlvbixcbiAgICAgICAgICAgICAgICBkZXRhaWxzOiBkZXRhaWxzLFxuICAgICAgICAgICAgICAgIGxpbms6IHRhc2sudXJsLFxuICAgICAgICAgICAgICAgIHNvdXJjZV9pZDogdGFzay5pZCxcbiAgICAgICAgICAgICAgICByYXdfaXRlbTogdGFzayxcbiAgICAgICAgICAgICAgICB1cmdlbmN5X3Njb3JlOiBjYWxjdWxhdGVVcmdlbmN5U2NvcmUoXG4gICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6ICd0YXNrJyxcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6IHRhc2suZGVzY3JpcHRpb24sXG4gICAgICAgICAgICAgICAgICAgIHJhd19pdGVtOiB0YXNrLFxuICAgICAgICAgICAgICAgICAgfSBhcyBCcmllZmluZ0l0ZW0sXG4gICAgICAgICAgICAgICAgICBwYXJzZWREYXRlSW5mby50YXJnZXREYXRlLFxuICAgICAgICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT1xuICAgICAgICAgICAgICAgICksXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEZldGNoZWQgYW5kIHByb2Nlc3NlZCAke2ZldGNoZWRUYXNrcy5sZW5ndGh9IHRhc2tzLmBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gTm8gcmVsZXZhbnQgdGFza3MgZm91bmQgZm9yIGJyaWVmaW5nLmBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfVxuICAgICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gRXhjZXB0aW9uIGR1cmluZyB0YXNrIGZldGNoaW5nOiAke2UubWVzc2FnZX1gLFxuICAgICAgICAgICAgZVxuICAgICAgICAgICk7XG4gICAgICAgICAgYnJpZWZpbmdEYXRhLmVycm9yc19lbmNvdW50ZXJlZD8ucHVzaCh7XG4gICAgICAgICAgICBzb3VyY2VfYXJlYTogJ3Rhc2tzJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6IGBFeGNlcHRpb246ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgICAgICBkZXRhaWxzOiBlLnN0YWNrLFxuICAgICAgICAgIH0pO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIFJlbW92ZSBwbGFjZWhvbGRlciBpZiB0YXNrcyBhcmUgbm90IGluIGZvY3VzQXJlYXNcbiAgICAgIGJyaWVmaW5nRGF0YS5wcmlvcml0eV9pdGVtcyA9IGJyaWVmaW5nRGF0YS5wcmlvcml0eV9pdGVtcy5maWx0ZXIoXG4gICAgICAgIChpdGVtKSA9PiBpdGVtLnR5cGUgIT09ICd0YXNrJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICAvLyBGZXRjaCBNZWV0aW5nc1xuICAgIGlmIChmb2N1c0FyZWFzLmluY2x1ZGVzKCdtZWV0aW5ncycpKSB7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEZldGNoaW5nIG1lZXRpbmdzIGZvciBicmllZmluZyBmb3IgdGFyZ2V0RGF0ZTogJHtwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPfS5gXG4gICAgICApO1xuICAgICAgdHJ5IHtcbiAgICAgICAgLy8gVXNlIHRpbWVNaW5JU08gYW5kIHRpbWVNYXhJU08gZnJvbSBwYXJzZWREYXRlSW5mb1xuICAgICAgICBjb25zdCBldmVudHNSZXNwb25zZSA9IGF3YWl0IGNhbGVuZGFyU2tpbGxzLmxpc3RVcGNvbWluZ0V2ZW50cyhcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgMTAsXG4gICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGltZU1pbklTTyxcbiAgICAgICAgICBwYXJzZWREYXRlSW5mby50aW1lTWF4SVNPXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKGV2ZW50c1Jlc3BvbnNlLm9rICYmIGV2ZW50c1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgICAgICBjb25zdCBtZWV0aW5nczogQ2FsZW5kYXJFdmVudFN1bW1hcnlbXSA9IGV2ZW50c1Jlc3BvbnNlLmRhdGE7XG4gICAgICAgICAgLy8gTWFrZSBzdXJlIHRoZSBkYXRlIGZvcm1hdHRpbmcgZm9yIG1lZXRpbmcgZGV0YWlscyB1c2VzIHRoZSB0YXJnZXREYXRlLCBub3QgbmVjZXNzYXJpbHkgJ3RvZGF5J1xuICAgICAgICAgIGNvbnN0IHRhcmdldERhdGVGb3JEaXNwbGF5ID0gcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZTtcbiAgICAgICAgICBpZiAobWVldGluZ3MubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgbWVldGluZ3MuZm9yRWFjaCgobWVldGluZykgPT4ge1xuICAgICAgICAgICAgICBjb25zdCBzdGFydFRpbWUgPSBtZWV0aW5nLnN0YXJ0XG4gICAgICAgICAgICAgICAgPyBuZXcgRGF0ZShtZWV0aW5nLnN0YXJ0KS50b0xvY2FsZVRpbWVTdHJpbmcoW10sIHtcbiAgICAgICAgICAgICAgICAgICAgaG91cjogJ251bWVyaWMnLFxuICAgICAgICAgICAgICAgICAgICBtaW51dGU6ICcyLWRpZ2l0JyxcbiAgICAgICAgICAgICAgICAgICAgaG91cjEyOiB0cnVlLFxuICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICA6ICdOL0EnO1xuICAgICAgICAgICAgICBjb25zdCBlbmRUaW1lID0gbWVldGluZy5lbmRcbiAgICAgICAgICAgICAgICA/IG5ldyBEYXRlKG1lZXRpbmcuZW5kKS50b0xvY2FsZVRpbWVTdHJpbmcoW10sIHtcbiAgICAgICAgICAgICAgICAgICAgaG91cjogJ251bWVyaWMnLFxuICAgICAgICAgICAgICAgICAgICBtaW51dGU6ICcyLWRpZ2l0JyxcbiAgICAgICAgICAgICAgICAgICAgaG91cjEyOiB0cnVlLFxuICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICA6ICcnO1xuXG4gICAgICAgICAgICAgIGJyaWVmaW5nRGF0YS5wcmlvcml0eV9pdGVtcy5wdXNoKHtcbiAgICAgICAgICAgICAgICB0eXBlOiAnbWVldGluZycsXG4gICAgICAgICAgICAgICAgdGl0bGU6IG1lZXRpbmcuc3VtbWFyeSB8fCAnVW50aXRsZWQgTWVldGluZycsXG4gICAgICAgICAgICAgICAgZGV0YWlsczogYFRpbWU6ICR7c3RhcnRUaW1lfSR7ZW5kVGltZSA/IGAgLSAke2VuZFRpbWV9YCA6ICcnfWAsXG4gICAgICAgICAgICAgICAgbGluazogbWVldGluZy5odG1sTGluayxcbiAgICAgICAgICAgICAgICBzb3VyY2VfaWQ6IG1lZXRpbmcuaWQsXG4gICAgICAgICAgICAgICAgcmF3X2l0ZW06IG1lZXRpbmcsXG4gICAgICAgICAgICAgICAgdXJnZW5jeV9zY29yZTogY2FsY3VsYXRlVXJnZW5jeVNjb3JlKFxuICAgICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiAnbWVldGluZycsXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlOiBtZWV0aW5nLnN1bW1hcnkgfHwgJ1VudGl0bGVkIE1lZXRpbmcnLFxuICAgICAgICAgICAgICAgICAgICByYXdfaXRlbTogbWVldGluZyxcbiAgICAgICAgICAgICAgICAgIH0gYXMgQnJpZWZpbmdJdGVtLFxuICAgICAgICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZSxcbiAgICAgICAgICAgICAgICAgIHBhcnNlZERhdGVJbmZvLnRhcmdldERhdGVJU09cbiAgICAgICAgICAgICAgICApLFxuICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBGZXRjaGVkICR7bWVldGluZ3MubGVuZ3RofSBtZWV0aW5ncy5gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIE5vIG1lZXRpbmdzIGZvdW5kIGZvciAke2RhdGVDb250ZXh0fS5gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gRXJyb3IgZmV0Y2hpbmcgbWVldGluZ3M6ICR7ZXZlbnRzUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgICAgYnJpZWZpbmdEYXRhLmVycm9yc19lbmNvdW50ZXJlZD8ucHVzaCh7XG4gICAgICAgICAgICBzb3VyY2VfYXJlYTogJ21lZXRpbmdzJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAgIGV2ZW50c1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlIHx8XG4gICAgICAgICAgICAgICdVbmtub3duIGVycm9yIGZldGNoaW5nIGNhbGVuZGFyIGV2ZW50cy4nLFxuICAgICAgICAgICAgZGV0YWlsczogSlNPTi5zdHJpbmdpZnkoZXZlbnRzUmVzcG9uc2UuZXJyb3I/LmRldGFpbHMpLFxuICAgICAgICAgIH0pO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBFeGNlcHRpb24gZHVyaW5nIG1lZXRpbmcgZmV0Y2hpbmc6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgICAgZVxuICAgICAgICApO1xuICAgICAgICBicmllZmluZ0RhdGEuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICBzb3VyY2VfYXJlYTogJ21lZXRpbmdzJyxcbiAgICAgICAgICBtZXNzYWdlOiBgRXhjZXB0aW9uOiAke2UubWVzc2FnZX1gLFxuICAgICAgICAgIGRldGFpbHM6IGUuc3RhY2ssXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICAvLyBSZW1vdmUgcGxhY2Vob2xkZXIgaWYgbWVldGluZ3MgYXJlIG5vdCBpbiBmb2N1c0FyZWFzXG4gICAgICBicmllZmluZ0RhdGEucHJpb3JpdHlfaXRlbXMgPSBicmllZmluZ0RhdGEucHJpb3JpdHlfaXRlbXMuZmlsdGVyKFxuICAgICAgICAoaXRlbSkgPT4gaXRlbS50eXBlICE9PSAnbWVldGluZydcbiAgICAgICk7XG4gICAgfVxuXG4gICAgLy8gRmV0Y2ggVXJnZW50IEVtYWlsc1xuICAgIGlmIChmb2N1c0FyZWFzLmluY2x1ZGVzKCd1cmdlbnRfZW1haWxzJykpIHtcbiAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gRmV0Y2hpbmcgdXJnZW50IGVtYWlscyBmb3IgYnJpZWZpbmcgZm9yIHRhcmdldERhdGU6ICR7cGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT30uYFxuICAgICAgKTtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGVtYWlsUmVzcG9uc2UgPVxuICAgICAgICAgIGF3YWl0IGdtYWlsU2tpbGxzLmdldFJlY2VudFVucmVhZEVtYWlsc0ZvckJyaWVmaW5nKFxuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZSwgLy8gUGFzcyB0aGUgRGF0ZSBvYmplY3RcbiAgICAgICAgICAgIDMgLy8gRmV0Y2ggdXAgdG8gMyBlbWFpbHNcbiAgICAgICAgICApO1xuXG4gICAgICAgIGlmIChlbWFpbFJlc3BvbnNlLm9rICYmIGVtYWlsUmVzcG9uc2UuZGF0YT8ucmVzdWx0cykge1xuICAgICAgICAgIGNvbnN0IGVtYWlsczogR21haWxNZXNzYWdlU25pcHBldFtdID0gZW1haWxSZXNwb25zZS5kYXRhLnJlc3VsdHM7XG4gICAgICAgICAgaWYgKGVtYWlscy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICBlbWFpbHMuZm9yRWFjaCgoZW1haWwpID0+IHtcbiAgICAgICAgICAgICAgYnJpZWZpbmdEYXRhLnByaW9yaXR5X2l0ZW1zLnB1c2goe1xuICAgICAgICAgICAgICAgIHR5cGU6ICdlbWFpbCcsXG4gICAgICAgICAgICAgICAgdGl0bGU6IGVtYWlsLnN1YmplY3QgfHwgJ05vIFN1YmplY3QnLFxuICAgICAgICAgICAgICAgIGRldGFpbHM6IGBGcm9tOiAke2VtYWlsLmZyb20gfHwgJ04vQSd9JHtlbWFpbC5zbmlwcGV0ID8gYCwgU25pcHBldDogJHtlbWFpbC5zbmlwcGV0LnN1YnN0cmluZygwLCA3MCl9Li4uYCA6ICcnfWAsXG4gICAgICAgICAgICAgICAgbGluazogZW1haWwubGluayxcbiAgICAgICAgICAgICAgICBzb3VyY2VfaWQ6IGVtYWlsLmlkLFxuICAgICAgICAgICAgICAgIHJhd19pdGVtOiBlbWFpbCxcbiAgICAgICAgICAgICAgICB1cmdlbmN5X3Njb3JlOiBjYWxjdWxhdGVVcmdlbmN5U2NvcmUoXG4gICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6ICdlbWFpbCcsXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlOiBlbWFpbC5zdWJqZWN0IHx8ICdObyBTdWJqZWN0JyxcbiAgICAgICAgICAgICAgICAgICAgcmF3X2l0ZW06IGVtYWlsLFxuICAgICAgICAgICAgICAgICAgfSBhcyBCcmllZmluZ0l0ZW0sXG4gICAgICAgICAgICAgICAgICBwYXJzZWREYXRlSW5mby50YXJnZXREYXRlLFxuICAgICAgICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT1xuICAgICAgICAgICAgICAgICksXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEZldGNoZWQgJHtlbWFpbHMubGVuZ3RofSB1cmdlbnQvcmVjZW50IHVucmVhZCBlbWFpbHMuYFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBObyB1cmdlbnQvcmVjZW50IHVucmVhZCBlbWFpbHMgZm91bmQgZm9yICR7cGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT30uYFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEVycm9yIGZldGNoaW5nIHVyZ2VudCBlbWFpbHM6ICR7ZW1haWxSZXNwb25zZS5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICAgICAgKTtcbiAgICAgICAgICBicmllZmluZ0RhdGEuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICAgIHNvdXJjZV9hcmVhOiAnZW1haWxzJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAgIGVtYWlsUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2UgfHxcbiAgICAgICAgICAgICAgJ1Vua25vd24gZXJyb3IgZmV0Y2hpbmcgdXJnZW50IGVtYWlscy4nLFxuICAgICAgICAgICAgZGV0YWlsczogSlNPTi5zdHJpbmdpZnkoZW1haWxSZXNwb25zZS5lcnJvcj8uZGV0YWlscyksXG4gICAgICAgICAgfSk7XG4gICAgICAgIH1cbiAgICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEV4Y2VwdGlvbiBkdXJpbmcgZW1haWwgZmV0Y2hpbmc6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgICAgZVxuICAgICAgICApO1xuICAgICAgICBicmllZmluZ0RhdGEuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICBzb3VyY2VfYXJlYTogJ2VtYWlscycsXG4gICAgICAgICAgbWVzc2FnZTogYEV4Y2VwdGlvbjogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgICBkZXRhaWxzOiBlLnN0YWNrLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBGZXRjaCBVcmdlbnQgU2xhY2sgTWVzc2FnZXNcbiAgICBpZiAoZm9jdXNBcmVhcy5pbmNsdWRlcygndXJnZW50X3NsYWNrX21lc3NhZ2VzJykpIHtcbiAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gRmV0Y2hpbmcgdXJnZW50IFNsYWNrIG1lc3NhZ2VzIGZvciBicmllZmluZyBmb3IgdGFyZ2V0RGF0ZTogJHtwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPfS5gXG4gICAgICApO1xuICAgICAgdHJ5IHtcbiAgICAgICAgY29uc3Qgc2xhY2tSZXNwb25zZSA9XG4gICAgICAgICAgYXdhaXQgc2xhY2tTa2lsbHMuZ2V0UmVjZW50RE1zQW5kTWVudGlvbnNGb3JCcmllZmluZyhcbiAgICAgICAgICAgIHVzZXJJZCwgLy8gYXRvbVVzZXJJZFxuICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZSwgLy8gdGFyZ2V0RGF0ZVxuICAgICAgICAgICAgMyAvLyBjb3VudFxuICAgICAgICAgICk7XG5cbiAgICAgICAgaWYgKHNsYWNrUmVzcG9uc2Uub2sgJiYgc2xhY2tSZXNwb25zZS5kYXRhPy5yZXN1bHRzKSB7XG4gICAgICAgICAgY29uc3Qgc2xhY2tNZXNzYWdlczogU2xhY2tNZXNzYWdlU25pcHBldFtdID1cbiAgICAgICAgICAgIHNsYWNrUmVzcG9uc2UuZGF0YS5yZXN1bHRzOyAvLyBTbGFja01lc3NhZ2UgaXMgY29tcGF0aWJsZSB3aXRoIFNsYWNrTWVzc2FnZVNuaXBwZXQgZm9yIHRoZXNlIGZpZWxkc1xuICAgICAgICAgIGlmIChzbGFja01lc3NhZ2VzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIHNsYWNrTWVzc2FnZXMuZm9yRWFjaCgobXNnKSA9PiB7XG4gICAgICAgICAgICAgIGxldCB0aXRsZSA9IGBTbGFjayBtZXNzYWdlYDtcbiAgICAgICAgICAgICAgaWYgKG1zZy51c2VyTmFtZSkgdGl0bGUgKz0gYCBmcm9tICR7bXNnLnVzZXJOYW1lfWA7XG4gICAgICAgICAgICAgIGlmIChtc2cuY2hhbm5lbE5hbWUpIHRpdGxlICs9IGAgaW4gIyR7bXNnLmNoYW5uZWxOYW1lfWA7XG4gICAgICAgICAgICAgIGVsc2UgaWYgKCFtc2cuY2hhbm5lbE5hbWUgJiYgbXNnLnVzZXJOYW1lKSB0aXRsZSArPSBgIChETSlgOyAvLyBMaWtlbHkgYSBETSBpZiBjaGFubmVsTmFtZSBpcyBudWxsIGJ1dCB1c2VyTmFtZSAoc2VuZGVyKSBpcyBwcmVzZW50XG5cbiAgICAgICAgICAgICAgYnJpZWZpbmdEYXRhLnByaW9yaXR5X2l0ZW1zLnB1c2goe1xuICAgICAgICAgICAgICAgIHR5cGU6ICdzbGFja19tZXNzYWdlJyxcbiAgICAgICAgICAgICAgICB0aXRsZTogdGl0bGUsXG4gICAgICAgICAgICAgICAgZGV0YWlsczogbXNnLnRleHRcbiAgICAgICAgICAgICAgICAgID8gbXNnLnRleHQuc3Vic3RyaW5nKDAsIDEwMCkgK1xuICAgICAgICAgICAgICAgICAgICAobXNnLnRleHQubGVuZ3RoID4gMTAwID8gJy4uLicgOiAnJylcbiAgICAgICAgICAgICAgICAgIDogJyhObyB0ZXh0IGNvbnRlbnQpJyxcbiAgICAgICAgICAgICAgICBsaW5rOiBtc2cucGVybWFsaW5rLFxuICAgICAgICAgICAgICAgIHNvdXJjZV9pZDogbXNnLmlkLCAvLyAndHMnIGZyb20gU2xhY2tNZXNzYWdlXG4gICAgICAgICAgICAgICAgcmF3X2l0ZW06IG1zZyxcbiAgICAgICAgICAgICAgICB1cmdlbmN5X3Njb3JlOiBjYWxjdWxhdGVVcmdlbmN5U2NvcmUoXG4gICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6ICdzbGFja19tZXNzYWdlJyxcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6IHRpdGxlLFxuICAgICAgICAgICAgICAgICAgICByYXdfaXRlbTogbXNnLFxuICAgICAgICAgICAgICAgICAgfSBhcyBCcmllZmluZ0l0ZW0sXG4gICAgICAgICAgICAgICAgICBwYXJzZWREYXRlSW5mby50YXJnZXREYXRlLFxuICAgICAgICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT1xuICAgICAgICAgICAgICAgICksXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEZldGNoZWQgJHtzbGFja01lc3NhZ2VzLmxlbmd0aH0gdXJnZW50L3JlY2VudCBTbGFjayBtZXNzYWdlcy5gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIE5vIHVyZ2VudC9yZWNlbnQgU2xhY2sgbWVzc2FnZXMgZm91bmQgZm9yICR7cGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT30uYFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEVycm9yIGZldGNoaW5nIHVyZ2VudCBTbGFjayBtZXNzYWdlczogJHtzbGFja1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgICApO1xuICAgICAgICAgIGJyaWVmaW5nRGF0YS5lcnJvcnNfZW5jb3VudGVyZWQ/LnB1c2goe1xuICAgICAgICAgICAgc291cmNlX2FyZWE6ICdzbGFjaycsXG4gICAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgICBzbGFja1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlIHx8XG4gICAgICAgICAgICAgICdVbmtub3duIGVycm9yIGZldGNoaW5nIHVyZ2VudCBTbGFjayBtZXNzYWdlcy4nLFxuICAgICAgICAgICAgZGV0YWlsczogSlNPTi5zdHJpbmdpZnkoc2xhY2tSZXNwb25zZS5lcnJvcj8uZGV0YWlscyksXG4gICAgICAgICAgfSk7XG4gICAgICAgIH1cbiAgICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEV4Y2VwdGlvbiBkdXJpbmcgU2xhY2sgbWVzc2FnZSBmZXRjaGluZzogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgICBlXG4gICAgICAgICk7XG4gICAgICAgIGJyaWVmaW5nRGF0YS5lcnJvcnNfZW5jb3VudGVyZWQ/LnB1c2goe1xuICAgICAgICAgIHNvdXJjZV9hcmVhOiAnc2xhY2snLFxuICAgICAgICAgIG1lc3NhZ2U6IGBFeGNlcHRpb246ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgICAgZGV0YWlsczogZS5zdGFjayxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gRmV0Y2ggVXJnZW50IE1TIFRlYW1zIE1lc3NhZ2VzXG4gICAgaWYgKGZvY3VzQXJlYXMuaW5jbHVkZXMoJ3VyZ2VudF90ZWFtc19tZXNzYWdlcycpKSB7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEZldGNoaW5nIHVyZ2VudCBNUyBUZWFtcyBtZXNzYWdlcyBmb3IgYnJpZWZpbmcgZm9yIHRhcmdldERhdGU6ICR7cGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT30uYFxuICAgICAgKTtcbiAgICAgIHRyeSB7XG4gICAgICAgIC8vIEFzc3VtaW5nIGdldFJlY2VudENoYXRzQW5kTWVudGlvbnNGb3JCcmllZmluZyBleGlzdHMgYW5kIHdvcmtzIHNpbWlsYXJseSB0byBTbGFjaydzXG4gICAgICAgIGNvbnN0IHRlYW1zUmVzcG9uc2UgPVxuICAgICAgICAgIGF3YWl0IHRlYW1zU2tpbGxzLmdldFJlY2VudENoYXRzQW5kTWVudGlvbnNGb3JCcmllZmluZyhcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIHBhcnNlZERhdGVJbmZvLnRhcmdldERhdGUsXG4gICAgICAgICAgICAzIC8vIEZldGNoIHVwIHRvIDMgbWVzc2FnZXNcbiAgICAgICAgICApO1xuXG4gICAgICAgIGlmICh0ZWFtc1Jlc3BvbnNlLm9rICYmIHRlYW1zUmVzcG9uc2UuZGF0YT8ucmVzdWx0cykge1xuICAgICAgICAgIGNvbnN0IHRlYW1zTWVzc2FnZXM6IE1TVGVhbXNNZXNzYWdlW10gPSB0ZWFtc1Jlc3BvbnNlLmRhdGEucmVzdWx0cztcbiAgICAgICAgICBpZiAodGVhbXNNZXNzYWdlcy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICB0ZWFtc01lc3NhZ2VzLmZvckVhY2goKG1zZykgPT4ge1xuICAgICAgICAgICAgICBsZXQgdGl0bGUgPSBgVGVhbXMgbWVzc2FnZWA7XG4gICAgICAgICAgICAgIGlmIChtc2cudXNlck5hbWUpIHRpdGxlICs9IGAgZnJvbSAke21zZy51c2VyTmFtZX1gO1xuICAgICAgICAgICAgICAvLyBtc2cuY2hhdElkIGNvdWxkIGJlIHVzZWQgdG8gaW5mZXIgaWYgaXQncyBhIDE6MSBvciBncm91cCBjaGF0IGlmIGNoYW5uZWwvdGVhbSBpbmZvIGlzbid0IGRpcmVjdGx5IG9uIG1zZ1xuICAgICAgICAgICAgICAvLyBGb3Igbm93LCBrZWVwaW5nIHRpdGxlIHNpbXBsZS5cbiAgICAgICAgICAgICAgLy8gaWYgKG1zZy5jaGFubmVsTmFtZSkgdGl0bGUgKz0gYCBpbiAke21zZy5jaGFubmVsTmFtZX1gOyAvLyBNU1RlYW1zTWVzc2FnZSBtYXkgbm90IGhhdmUgY2hhbm5lbE5hbWUgZGlyZWN0bHlcblxuICAgICAgICAgICAgICBicmllZmluZ0RhdGEucHJpb3JpdHlfaXRlbXMucHVzaCh7XG4gICAgICAgICAgICAgICAgdHlwZTogJ3RlYW1zX21lc3NhZ2UnLCAvLyBOZXcgQnJpZWZpbmdJdGVtVHlwZVxuICAgICAgICAgICAgICAgIHRpdGxlOiB0aXRsZSxcbiAgICAgICAgICAgICAgICBkZXRhaWxzOiBtc2cuY29udGVudFxuICAgICAgICAgICAgICAgICAgPyBtc2cuY29udGVudC5zdWJzdHJpbmcoMCwgMTAwKSArXG4gICAgICAgICAgICAgICAgICAgIChtc2cuY29udGVudC5sZW5ndGggPiAxMDAgPyAnLi4uJyA6ICcnKVxuICAgICAgICAgICAgICAgICAgOiAnKE5vIHRleHQgY29udGVudCknLFxuICAgICAgICAgICAgICAgIGxpbms6IG1zZy53ZWJVcmwsXG4gICAgICAgICAgICAgICAgc291cmNlX2lkOiBtc2cuaWQsXG4gICAgICAgICAgICAgICAgcmF3X2l0ZW06IG1zZyxcbiAgICAgICAgICAgICAgICB1cmdlbmN5X3Njb3JlOiBjYWxjdWxhdGVVcmdlbmN5U2NvcmUoXG4gICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6ICd0ZWFtc19tZXNzYWdlJyxcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6IHRpdGxlLFxuICAgICAgICAgICAgICAgICAgICByYXdfaXRlbTogbXNnLFxuICAgICAgICAgICAgICAgICAgfSBhcyBCcmllZmluZ0l0ZW0sXG4gICAgICAgICAgICAgICAgICBwYXJzZWREYXRlSW5mby50YXJnZXREYXRlLFxuICAgICAgICAgICAgICAgICAgcGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT1xuICAgICAgICAgICAgICAgICksXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEZldGNoZWQgJHt0ZWFtc01lc3NhZ2VzLmxlbmd0aH0gdXJnZW50L3JlY2VudCBNUyBUZWFtcyBtZXNzYWdlcy5gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIE5vIHVyZ2VudC9yZWNlbnQgTVMgVGVhbXMgbWVzc2FnZXMgZm91bmQgZm9yICR7cGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZUlTT30uYFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEVycm9yIGZldGNoaW5nIHVyZ2VudCBNUyBUZWFtcyBtZXNzYWdlczogJHt0ZWFtc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgICApO1xuICAgICAgICAgIGJyaWVmaW5nRGF0YS5lcnJvcnNfZW5jb3VudGVyZWQ/LnB1c2goe1xuICAgICAgICAgICAgc291cmNlX2FyZWE6ICd0ZWFtcycsIC8vIE5ldyBzb3VyY2VfYXJlYVxuICAgICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICAgdGVhbXNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZSB8fFxuICAgICAgICAgICAgICAnVW5rbm93biBlcnJvciBmZXRjaGluZyB1cmdlbnQgTVMgVGVhbXMgbWVzc2FnZXMuJyxcbiAgICAgICAgICAgIGRldGFpbHM6IEpTT04uc3RyaW5naWZ5KHRlYW1zUmVzcG9uc2UuZXJyb3I/LmRldGFpbHMpLFxuICAgICAgICAgIH0pO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAgIGBbZGFpbHlCcmllZmluZ1NraWxsXSBFeGNlcHRpb24gZHVyaW5nIE1TIFRlYW1zIG1lc3NhZ2UgZmV0Y2hpbmc6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgICAgZVxuICAgICAgICApO1xuICAgICAgICBicmllZmluZ0RhdGEuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICBzb3VyY2VfYXJlYTogJ3RlYW1zJyxcbiAgICAgICAgICBtZXNzYWdlOiBgRXhjZXB0aW9uOiAke2UubWVzc2FnZX1gLFxuICAgICAgICAgIGRldGFpbHM6IGUuc3RhY2ssXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIFNvcnQgYWxsIGNvbGxlY3RlZCBwcmlvcml0eV9pdGVtcyBieSB1cmdlbmN5X3Njb3JlIChkZXNjZW5kaW5nKVxuICAgIC8vIFNlY29uZGFyeSBzb3J0IGNyaXRlcmlhOlxuICAgIC8vIC0gTWVldGluZ3MgYnkgc3RhcnQgdGltZSAoZWFybGllciBmaXJzdClcbiAgICAvLyAtIFRhc2tzIGJ5IHRoZWlyIGluaGVyZW50IHNvcnQgKG92ZXJkdWUgPiBkdWUgdG9kYXkgPiBwcmlvcml0eSA+IGR1ZSBkYXRlKSAoYWxyZWFkeSBzb21ld2hhdCBkb25lLCBidXQgZXhwbGljaXQgZHVlIGRhdGUgaWYgc2NvcmVzIGVxdWFsKVxuICAgIC8vIC0gRW1haWxzIGJ5IGRhdGUgKG5ld2VyIGZpcnN0KVxuICAgIGJyaWVmaW5nRGF0YS5wcmlvcml0eV9pdGVtcy5zb3J0KChhLCBiKSA9PiB7XG4gICAgICBjb25zdCBzY29yZURpZmYgPSAoYi51cmdlbmN5X3Njb3JlIHx8IDApIC0gKGEudXJnZW5jeV9zY29yZSB8fCAwKTtcbiAgICAgIGlmIChzY29yZURpZmYgIT09IDApIHtcbiAgICAgICAgcmV0dXJuIHNjb3JlRGlmZjtcbiAgICAgIH1cblxuICAgICAgLy8gU2Vjb25kYXJ5IHNvcnRpbmcgaWYgdXJnZW5jeSBzY29yZXMgYXJlIGVxdWFsXG4gICAgICBpZiAoYS50eXBlID09PSAnbWVldGluZycgJiYgYi50eXBlID09PSAnbWVldGluZycpIHtcbiAgICAgICAgY29uc3QgYVN0YXJ0ID0gYS5yYXdfaXRlbT8uc3RhcnRcbiAgICAgICAgICA/IG5ldyBEYXRlKGEucmF3X2l0ZW0uc3RhcnQpLmdldFRpbWUoKVxuICAgICAgICAgIDogMDtcbiAgICAgICAgY29uc3QgYlN0YXJ0ID0gYi5yYXdfaXRlbT8uc3RhcnRcbiAgICAgICAgICA/IG5ldyBEYXRlKGIucmF3X2l0ZW0uc3RhcnQpLmdldFRpbWUoKVxuICAgICAgICAgIDogMDtcbiAgICAgICAgcmV0dXJuIGFTdGFydCAtIGJTdGFydDsgLy8gRWFybGllciBtZWV0aW5nIGZpcnN0XG4gICAgICB9XG4gICAgICBpZiAoYS50eXBlID09PSAndGFzaycgJiYgYi50eXBlID09PSAndGFzaycpIHtcbiAgICAgICAgLy8gVGFza3Mgd2VyZSBhbHJlYWR5IHByZS1zb3J0ZWQgc29tZXdoYXQgYnkgZHVlIGRhdGUgYW5kIHByaW9yaXR5IGdyb3Vwc1xuICAgICAgICAvLyBIZXJlLCBqdXN0IGVuc3VyZSBjb25zaXN0ZW50IG9yZGVyaW5nIGlmIHNjb3JlcyBhcmUgaWRlbnRpY2FsLCBlLmcuLCBieSBleHBsaWNpdCBkdWUgZGF0ZVxuICAgICAgICBjb25zdCBhRHVlRGF0ZSA9IChhLnJhd19pdGVtIGFzIE5vdGlvblRhc2spPy5kdWVEYXRlXG4gICAgICAgICAgPyBuZXcgRGF0ZSgoYS5yYXdfaXRlbSBhcyBOb3Rpb25UYXNrKS5kdWVEYXRlISkuZ2V0VGltZSgpXG4gICAgICAgICAgOiBJbmZpbml0eTtcbiAgICAgICAgY29uc3QgYkR1ZURhdGUgPSAoYi5yYXdfaXRlbSBhcyBOb3Rpb25UYXNrKT8uZHVlRGF0ZVxuICAgICAgICAgID8gbmV3IERhdGUoKGIucmF3X2l0ZW0gYXMgTm90aW9uVGFzaykuZHVlRGF0ZSEpLmdldFRpbWUoKVxuICAgICAgICAgIDogSW5maW5pdHk7XG4gICAgICAgIGlmIChhRHVlRGF0ZSAhPT0gYkR1ZURhdGUpIHJldHVybiBhRHVlRGF0ZSAtIGJEdWVEYXRlOyAvLyBFYXJsaWVyIGR1ZSBkYXRlIGZpcnN0XG4gICAgICAgIC8vIENvdWxkIGFkZCBmdXJ0aGVyIHRpZS1icmVha2luZyBieSBwcmlvcml0eSBpZiBuZWVkZWQsIHRob3VnaCBzY29yZSBzaG91bGQgbW9zdGx5IGNvdmVyIGl0XG4gICAgICB9XG4gICAgICBpZiAoYS50eXBlID09PSAnZW1haWwnICYmIGIudHlwZSA9PT0gJ2VtYWlsJykge1xuICAgICAgICBjb25zdCBhRGF0ZSA9IChhLnJhd19pdGVtIGFzIEdtYWlsTWVzc2FnZVNuaXBwZXQpPy5kYXRlXG4gICAgICAgICAgPyBuZXcgRGF0ZSgoYS5yYXdfaXRlbSBhcyBHbWFpbE1lc3NhZ2VTbmlwcGV0KS5kYXRlISkuZ2V0VGltZSgpXG4gICAgICAgICAgOiAwO1xuICAgICAgICBjb25zdCBiRGF0ZSA9IChiLnJhd19pdGVtIGFzIEdtYWlsTWVzc2FnZVNuaXBwZXQpPy5kYXRlXG4gICAgICAgICAgPyBuZXcgRGF0ZSgoYi5yYXdfaXRlbSBhcyBHbWFpbE1lc3NhZ2VTbmlwcGV0KS5kYXRlISkuZ2V0VGltZSgpXG4gICAgICAgICAgOiAwO1xuICAgICAgICByZXR1cm4gYkRhdGUgLSBhRGF0ZTsgLy8gTmV3ZXIgZW1haWwgZmlyc3RcbiAgICAgIH1cblxuICAgICAgLy8gSWYgdHlwZXMgYXJlIGRpZmZlcmVudCBhbmQgc2NvcmVzIGFyZSBlcXVhbCwgbWFpbnRhaW4gb3JpZ2luYWwgcmVsYXRpdmUgb3JkZXIgb3IgZGVmaW5lIG9uZVxuICAgICAgLy8gRm9yIG5vdywgaWYgc2NvcmVzIGFyZSBlcXVhbCBhbmQgdHlwZXMgZGlmZmVyLCB0aGVpciByZWxhdGl2ZSBvcmRlciB3b24ndCBjaGFuZ2UgZnJvbSB0aGlzIHNvcnQgcGFzcy5cbiAgICAgIC8vIEEgbW9yZSBleHBsaWNpdCBjcm9zcy10eXBlIHNlY29uZGFyeSBzb3J0IGNvdWxkIGJlOiBNZWV0aW5ncyA+IFRhc2tzID4gRW1haWxzID4gU2xhY2sgPiBUZWFtcyBpZiBzY29yZXMgYXJlIGlkZW50aWNhbC5cbiAgICAgIGNvbnN0IHR5cGVPcmRlciA9IHtcbiAgICAgICAgbWVldGluZzogMSxcbiAgICAgICAgdGFzazogMixcbiAgICAgICAgZW1haWw6IDMsXG4gICAgICAgIHNsYWNrX21lc3NhZ2U6IDQsXG4gICAgICAgIHRlYW1zX21lc3NhZ2U6IDUsXG4gICAgICB9O1xuICAgICAgY29uc3QgYVR5cGVPcmRlciA9IHR5cGVPcmRlclthLnR5cGVdIHx8IDk5OyAvLyBJdGVtcyBub3QgaW4gdHlwZU9yZGVyIGdvIGxhc3RcbiAgICAgIGNvbnN0IGJUeXBlT3JkZXIgPSB0eXBlT3JkZXJbYi50eXBlXSB8fCA5OTsgLy8gSXRlbXMgbm90IGluIHR5cGVPcmRlciBnbyBsYXN0XG4gICAgICByZXR1cm4gYVR5cGVPcmRlciAtIGJUeXBlT3JkZXI7XG4gICAgfSk7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gU29ydGVkICR7YnJpZWZpbmdEYXRhLnByaW9yaXR5X2l0ZW1zLmxlbmd0aH0gcHJpb3JpdHkgaXRlbXMuYFxuICAgICk7XG5cbiAgICAvLyBHZW5lcmF0ZSBvdmVyYWxsX3N1bW1hcnlfbWVzc2FnZVxuICAgIC8vIEdlbmVyYXRlIG92ZXJhbGxfc3VtbWFyeV9tZXNzYWdlXG4gICAgY29uc3QgbnVtVGFza3MgPSBicmllZmluZ0RhdGEucHJpb3JpdHlfaXRlbXMuZmlsdGVyKFxuICAgICAgKGl0ZW0pID0+IGl0ZW0udHlwZSA9PT0gJ3Rhc2snXG4gICAgKS5sZW5ndGg7XG4gICAgY29uc3QgbnVtTWVldGluZ3MgPSBicmllZmluZ0RhdGEucHJpb3JpdHlfaXRlbXMuZmlsdGVyKFxuICAgICAgKGl0ZW0pID0+IGl0ZW0udHlwZSA9PT0gJ21lZXRpbmcnXG4gICAgKS5sZW5ndGg7XG4gICAgY29uc3QgbnVtRW1haWxzID0gYnJpZWZpbmdEYXRhLnByaW9yaXR5X2l0ZW1zLmZpbHRlcihcbiAgICAgIChpdGVtKSA9PiBpdGVtLnR5cGUgPT09ICdlbWFpbCdcbiAgICApLmxlbmd0aDtcbiAgICBjb25zdCBudW1TbGFja01lc3NhZ2VzID0gYnJpZWZpbmdEYXRhLnByaW9yaXR5X2l0ZW1zLmZpbHRlcihcbiAgICAgIChpdGVtKSA9PiBpdGVtLnR5cGUgPT09ICdzbGFja19tZXNzYWdlJ1xuICAgICkubGVuZ3RoO1xuICAgIGNvbnN0IG51bVRlYW1zTWVzc2FnZXMgPSBicmllZmluZ0RhdGEucHJpb3JpdHlfaXRlbXMuZmlsdGVyKFxuICAgICAgKGl0ZW0pID0+IGl0ZW0udHlwZSA9PT0gJ3RlYW1zX21lc3NhZ2UnXG4gICAgKS5sZW5ndGg7XG5cbiAgICBjb25zdCBmcmllbmRseURhdGVTdHJpbmcgPSBnZXRGcmllbmRseURhdGVTdHJpbmcocGFyc2VkRGF0ZUluZm8udGFyZ2V0RGF0ZSk7XG4gICAgbGV0IHN1bW1hcnlQYXJ0czogc3RyaW5nW10gPSBbXTtcblxuICAgIC8vIENvbnN0cnVjdCBtZXNzYWdlIHBhcnRzIGZvciBlYWNoIGZvY3VzIGFyZWFcbiAgICBpZiAoZm9jdXNBcmVhcy5pbmNsdWRlcygnbWVldGluZ3MnKSkge1xuICAgICAgaWYgKG51bU1lZXRpbmdzID4gMCkge1xuICAgICAgICBzdW1tYXJ5UGFydHMucHVzaChgJHtudW1NZWV0aW5nc30gbWVldGluZyhzKSBzY2hlZHVsZWQuYCk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzdW1tYXJ5UGFydHMucHVzaCgnbm8gbWVldGluZ3Mgc2NoZWR1bGVkLicpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChmb2N1c0FyZWFzLmluY2x1ZGVzKCd0YXNrcycpKSB7XG4gICAgICBpZiAobnVtVGFza3MgPiAwKSB7XG4gICAgICAgIGNvbnN0IG92ZXJkdWVUYXNrcyA9IGJyaWVmaW5nRGF0YS5wcmlvcml0eV9pdGVtcy5maWx0ZXIoXG4gICAgICAgICAgKGl0ZW0pID0+XG4gICAgICAgICAgICBpdGVtLnR5cGUgPT09ICd0YXNrJyAmJlxuICAgICAgICAgICAgaXRlbS5yYXdfaXRlbSAmJlxuICAgICAgICAgICAgKGl0ZW0ucmF3X2l0ZW0gYXMgTm90aW9uVGFzaykuZHVlRGF0ZSAmJlxuICAgICAgICAgICAgKGl0ZW0ucmF3X2l0ZW0gYXMgTm90aW9uVGFzaykuZHVlRGF0ZSEgPFxuICAgICAgICAgICAgICBwYXJzZWREYXRlSW5mby50YXJnZXREYXRlSVNPICYmXG4gICAgICAgICAgICAoaXRlbS5yYXdfaXRlbSBhcyBOb3Rpb25UYXNrKS5zdGF0dXMgIT09ICdEb25lJyAmJlxuICAgICAgICAgICAgKGl0ZW0ucmF3X2l0ZW0gYXMgTm90aW9uVGFzaykuc3RhdHVzICE9PSAnQ2FuY2VsbGVkJ1xuICAgICAgICApLmxlbmd0aDtcbiAgICAgICAgbGV0IHRhc2tQYXJ0ID0gYCR7bnVtVGFza3N9IHRhc2socykgcmVxdWlyZSBhdHRlbnRpb25gO1xuICAgICAgICBpZiAob3ZlcmR1ZVRhc2tzID4gMCkgdGFza1BhcnQgKz0gYCAoJHtvdmVyZHVlVGFza3N9IG92ZXJkdWUpYDtcbiAgICAgICAgc3VtbWFyeVBhcnRzLnB1c2godGFza1BhcnQpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgc3VtbWFyeVBhcnRzLnB1c2goJ25vIHByZXNzaW5nIHRhc2tzLicpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChmb2N1c0FyZWFzLmluY2x1ZGVzKCd1cmdlbnRfZW1haWxzJykpIHtcbiAgICAgIGlmIChudW1FbWFpbHMgPiAwKSB7XG4gICAgICAgIHN1bW1hcnlQYXJ0cy5wdXNoKGAke251bUVtYWlsc30gcmVjZW50IHVucmVhZCBlbWFpbChzKS5gKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHN1bW1hcnlQYXJ0cy5wdXNoKCdubyByZWNlbnQgdW5yZWFkIGVtYWlscy4nKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoZm9jdXNBcmVhcy5pbmNsdWRlcygndXJnZW50X3NsYWNrX21lc3NhZ2VzJykpIHtcbiAgICAgIGlmIChudW1TbGFja01lc3NhZ2VzID4gMCkge1xuICAgICAgICBzdW1tYXJ5UGFydHMucHVzaChcbiAgICAgICAgICBgJHtudW1TbGFja01lc3NhZ2VzfSByZWNlbnQgU2xhY2sgbWVzc2FnZShzKSAoRE1zL21lbnRpb25zKS5gXG4gICAgICAgICk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzdW1tYXJ5UGFydHMucHVzaCgnbm8gcmVjZW50IFNsYWNrIERNcyBvciBtZW50aW9ucy4nKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoZm9jdXNBcmVhcy5pbmNsdWRlcygndXJnZW50X3RlYW1zX21lc3NhZ2VzJykpIHtcbiAgICAgIGlmIChudW1UZWFtc01lc3NhZ2VzID4gMCkge1xuICAgICAgICBzdW1tYXJ5UGFydHMucHVzaChcbiAgICAgICAgICBgJHtudW1UZWFtc01lc3NhZ2VzfSByZWNlbnQgTVMgVGVhbXMgbWVzc2FnZShzKSAoY2hhdHMvbWVudGlvbnMpLmBcbiAgICAgICAgKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHN1bW1hcnlQYXJ0cy5wdXNoKCdubyByZWNlbnQgTVMgVGVhbXMgY2hhdHMgb3IgbWVudGlvbnMuJyk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gQXNzZW1ibGUgdGhlIGZpbmFsIHN1bW1hcnkgbWVzc2FnZVxuICAgIGxldCBzdW1tYXJ5Q29udGVudCA9ICcnO1xuICAgIGlmIChzdW1tYXJ5UGFydHMubGVuZ3RoID4gMCkge1xuICAgICAgLy8gQ3JlYXRlIGEgc2VudGVuY2UgZnJvbSB0aGUgcGFydHNcbiAgICAgIGlmIChzdW1tYXJ5UGFydHMubGVuZ3RoID09PSAxKSB7XG4gICAgICAgIHN1bW1hcnlDb250ZW50ID0gYFlvdSBoYXZlICR7c3VtbWFyeVBhcnRzWzBdfWA7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCBsYXN0UGFydCA9IHN1bW1hcnlQYXJ0cy5wb3AoKTtcbiAgICAgICAgc3VtbWFyeUNvbnRlbnQgPSBgWW91IGhhdmUgJHtzdW1tYXJ5UGFydHMuam9pbignLCAnKX0sIGFuZCAke2xhc3RQYXJ0fWA7XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIHN1bW1hcnlDb250ZW50ID0gYFRoZXJlIGFyZSBubyBzcGVjaWZpYyBpdGVtcyB0byBoaWdobGlnaHQgYmFzZWQgb24geW91ciByZXF1ZXN0ZWQgZm9jdXMgYXJlYXMuYDtcbiAgICB9XG5cbiAgICBicmllZmluZ0RhdGEub3ZlcmFsbF9zdW1tYXJ5X21lc3NhZ2UgPSBgSGVyZSBpcyB5b3VyIGJyaWVmaW5nIGZvciAke2ZyaWVuZGx5RGF0ZVN0cmluZ306ICR7c3VtbWFyeUNvbnRlbnR9YDtcblxuICAgIC8vIFByZXBlbmQgZGF0ZSBwYXJzaW5nIHdhcm5pbmdzIGlmIGFueVxuICAgIGlmIChcbiAgICAgIHBhcnNlZERhdGVJbmZvLnN0YXR1cyA9PT0gJ3VucGFyc2VhYmxlJyAmJlxuICAgICAgcGFyc2VkRGF0ZUluZm8ud2FybmluZ01lc3NhZ2VcbiAgICApIHtcbiAgICAgIGJyaWVmaW5nRGF0YS5vdmVyYWxsX3N1bW1hcnlfbWVzc2FnZSA9IGAke3BhcnNlZERhdGVJbmZvLndhcm5pbmdNZXNzYWdlfSAke2JyaWVmaW5nRGF0YS5vdmVyYWxsX3N1bW1hcnlfbWVzc2FnZX1gO1xuICAgIH0gZWxzZSBpZiAoXG4gICAgICBwYXJzZWREYXRlSW5mby5zdGF0dXMgPT09ICdkZWZhdWx0ZWQnICYmXG4gICAgICBwYXJzZWREYXRlSW5mby5vcmlnaW5hbElucHV0ICYmXG4gICAgICBwYXJzZWREYXRlSW5mby5vcmlnaW5hbElucHV0LnRvTG93ZXJDYXNlKCkudHJpbSgpICE9PSAndG9kYXknXG4gICAgKSB7XG4gICAgICBicmllZmluZ0RhdGEub3ZlcmFsbF9zdW1tYXJ5X21lc3NhZ2UgPSBgU2hvd2luZyBicmllZmluZyBmb3IgdG9kYXkgYXMgZGF0ZSBjb250ZXh0ICcke3BhcnNlZERhdGVJbmZvLm9yaWdpbmFsSW5wdXR9JyB3YXMgcHJvY2Vzc2VkIGFzIGRlZmF1bHQuICR7YnJpZWZpbmdEYXRhLm92ZXJhbGxfc3VtbWFyeV9tZXNzYWdlfWA7XG4gICAgfVxuXG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2RhaWx5QnJpZWZpbmdTa2lsbF0gR2VuZXJhdGVkIHN1bW1hcnk6ICR7YnJpZWZpbmdEYXRhLm92ZXJhbGxfc3VtbWFyeV9tZXNzYWdlfWBcbiAgICApO1xuXG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IGJyaWVmaW5nRGF0YSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtkYWlseUJyaWVmaW5nU2tpbGxdIEVycm9yIGdlbmVyYXRpbmcgZGFpbHkgYnJpZWZpbmc6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIGJyaWVmaW5nRGF0YS5lcnJvcnNfZW5jb3VudGVyZWQ/LnB1c2goe1xuICAgICAgc291cmNlX2FyZWE6ICdvdmVyYWxsJyxcbiAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gZ2VuZXJhdGUgYnJpZWZpbmc6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgZGV0YWlsczogZXJyb3Iuc3RhY2ssXG4gICAgfSk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6ICdCUklFRklOR19HRU5FUkFUSU9OX0VSUk9SJywgbWVzc2FnZTogZXJyb3IubWVzc2FnZSB9LFxuICAgICAgZGF0YTogYnJpZWZpbmdEYXRhLFxuICAgIH07XG4gIH1cbn1cbiJdfQ==
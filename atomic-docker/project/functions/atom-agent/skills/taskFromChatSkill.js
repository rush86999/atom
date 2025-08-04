import { logger } from '../../_utils/logger';
import { ATOM_NOTION_TASKS_DATABASE_ID } from '../_libs/constants'; // Import DB ID
import { createNotionTask as createNotionTaskBackend } from './notionAndResearchSkills'; // Import backend caller
// TODO: Import date/priority parsing utilities from notionTaskSkills.ts if NLU entities are expanded
// For now, CreateTaskFromChatMessageNluEntities doesn't have detailed date/priority fields beyond the override.
// import { parseDueDate, mapPriority } from './notionTaskSkills';
/**
 * Creates a task in a task management system based on a referenced chat message.
 *
 * @param userId The ID of the user requesting the task creation.
 * @param nluEntities The parsed NLU entities from the CreateTaskFromChatMessage intent.
 * @returns A promise that resolves to CreateTaskFromChatMessageSkillResponse.
 */
export async function createTaskFromChatMessage(userId, nluEntities) {
    logger.info(`[taskFromChatSkill] Starting task creation from chat message for user ${userId}. Reference: "${nluEntities.chat_message_reference}", Platform: ${nluEntities.source_platform}`);
    logger.debug(`[taskFromChatSkill] NLU Entities: ${JSON.stringify(nluEntities)}`);
    let fetchedMessageContent = null;
    // Step 1: Fetch the chat message content based on reference and platform
    try {
        logger.info(`[taskFromChatSkill] Fetching message content for reference: "${nluEntities.chat_message_reference}" from ${nluEntities.source_platform}`);
        // TODO: Implement or verify the actual message fetching skills below.
        // For now, they will likely return errors or mock data if not implemented.
        switch (nluEntities.source_platform) {
            case 'slack':
                // const slackRes = await slackSkills.getSlackMessageDetailsByReference(userId, nluEntities.chat_message_reference);
                // if (slackRes.ok && slackRes.data) fetchedMessageContent = slackRes.data; // Adapt data structure
                // else throw new Error(slackRes.error?.message || "Failed to fetch from Slack");
                logger.warn("[taskFromChatSkill] Slack message fetching not implemented yet.");
                throw new Error("Slack message fetching not implemented yet.");
                break;
            case 'msteams':
                // const teamsRes = await teamsSkills.getTeamsMessageDetailsByReference(userId, nluEntities.chat_message_reference);
                // if (teamsRes.ok && teamsRes.data) fetchedMessageContent = teamsRes.data; // Adapt data structure
                // else throw new Error(teamsRes.error?.message || "Failed to fetch from MS Teams");
                logger.warn("[taskFromChatSkill] MS Teams message fetching not implemented yet.");
                throw new Error("MS Teams message fetching not implemented yet.");
                break;
            case 'gmail_thread_item':
                // const gmailRes = await emailSkills.getGmailMessageDetailsByReference(userId, nluEntities.chat_message_reference);
                // if (gmailRes.ok && gmailRes.data) fetchedMessageContent = gmailRes.data; // Adapt data structure
                // else throw new Error(gmailRes.error?.message || "Failed to fetch from Gmail");
                logger.warn("[taskFromChatSkill] Gmail message fetching not implemented yet.");
                throw new Error("Gmail message fetching not implemented yet.");
                break;
            default:
                // This check ensures nluEntities.source_platform is one of the expected types
                // It's good for type safety if CreateTaskFromChatMessageNluEntities.source_platform is a union of literals.
                const exhaustiveCheck = nluEntities.source_platform;
                throw new Error(`Unsupported source platform: ${exhaustiveCheck}`);
        }
        // if (!fetchedMessageContent) {
        //   throw new Error("Failed to fetch message content from the specified platform.");
        // }
    }
    catch (error) {
        logger.error(`[taskFromChatSkill] Error fetching message content: ${error.message}`, error);
        // Fallback to using the reference as task description if fetching fails
        // This allows task creation even if message context isn't available.
        logger.warn(`[taskFromChatSkill] Using chat_message_reference as task description due to fetch error.`);
        fetchedMessageContent = {
            platform: nluEntities.source_platform,
            message_id: "fallback_" + Date.now(),
            text_content: nluEntities.chat_message_reference, // Use reference as content
            message_url: undefined, // No URL if content couldn't be fetched
            timestamp: new Date().toISOString(),
            sender_name: "Unknown (fetch failed)"
        };
        // Do not return error here, proceed with task creation using fallback content
    }
    // Step 2: Determine task description
    let taskDescription = nluEntities.task_description_override || fetchedMessageContent.text_content;
    // Optional: Use LLM to summarize if description is long and no override.
    // if (!nluEntities.task_description_override && taskDescription.length > 150) { // Example length check
    //   try {
    //     const summaryResult = await llmUtilities.generateTaskTitle(taskDescription); // Assuming such a utility
    //     if (summaryResult.ok && summaryResult.data?.title) {
    //       taskDescription = summaryResult.data.title;
    //       logger.info(`[taskFromChatSkill] Summarized task description to: "${taskDescription}"`);
    //     }
    //   } catch (llmError: any) {
    //     logger.warn(`[taskFromChatSkill] Could not summarize task description: ${llmError.message}`);
    //   }
    // }
    // Ensure taskDescription is not overly long for Notion title
    if (taskDescription.length > 200) { // Notion titles can be longer, but good to keep it reasonable
        logger.warn(`[taskFromChatSkill] Task description is long (${taskDescription.length} chars), consider summarizing for title and putting full text in notes.`);
        // taskDescription = taskDescription.substring(0, 197) + "..."; // Truncate if needed
    }
    const taskNotesParts = [`Task created from ${fetchedMessageContent.platform} message.`];
    if (fetchedMessageContent.message_url) {
        taskNotesParts.push(`Link: ${fetchedMessageContent.message_url}`);
    }
    if (fetchedMessageContent.sender_name && fetchedMessageContent.sender_name !== "Unknown (fetch failed)") {
        taskNotesParts.push(`Sender: ${fetchedMessageContent.sender_name}`);
    }
    taskNotesParts.push(`Time: ${new Date(fetchedMessageContent.timestamp).toLocaleString()}`);
    if (fetchedMessageContent.text_content !== nluEntities.chat_message_reference) { // Only add snippet if it's real fetched content
        taskNotesParts.push(`\nOriginal Message Snippet:\n"${fetchedMessageContent.text_content.substring(0, 200)}${fetchedMessageContent.text_content.length > 200 ? '...' : ''}"`);
    }
    const taskNotes = taskNotesParts.join('\n');
    // Step 3: Create the task in Notion (or other task system)
    try {
        logger.info(`[taskFromChatSkill] Creating Notion task with description: "${taskDescription.substring(0, 50)}..."`);
        const notionTaskParams = {
            description: taskDescription,
            // Assuming CreateTaskFromChatMessageNluEntities might get these fields in future:
            // dueDate: parseDueDate(nluEntities.due_date),
            // priority: mapPriority(nluEntities.priority),
            // listName: nluEntities.target_task_list_or_project,
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID || '',
            notes: taskNotes,
            status: 'To Do', // Default status for new tasks
        };
        if (!notionTaskParams.notionTasksDbId) {
            logger.error("[taskFromChatSkill] ATOM_NOTION_TASKS_DATABASE_ID is not configured. Cannot create Notion task.");
            throw new Error("Notion Tasks Database ID is not configured.");
        }
        const creationResult = await createNotionTaskBackend(userId, notionTaskParams);
        if (!creationResult.ok || !creationResult.data) {
            logger.error(`[taskFromChatSkill] Failed to create task in Notion via backend: ${creationResult.error?.message || 'Unknown error'}`);
            throw new Error(creationResult.error?.message || "Failed to create task in Notion via backend.");
        }
        const createdTaskData = creationResult.data;
        logger.info(`[taskFromChatSkill] Successfully created Notion task ID: ${createdTaskData.taskId}`);
        const resultData = {
            success: true,
            message: createdTaskData.message || "Task created successfully in Notion.",
            taskId: createdTaskData.taskId,
            taskUrl: createdTaskData.taskUrl,
            taskTitle: taskDescription, // The description used for creation
            original_message_link_included: !!fetchedMessageContent.message_url, // True if a URL was available
        };
        return {
            ok: false,
            error: { code: "MESSAGE_FETCH_ERROR", message: `Failed to fetch message: ${error.message}` },
            data: { success: false, message: `Failed to fetch message: ${error.message}` }
        };
    }
    // Step 2: Determine task description
    finally {
    }
    // Step 2: Determine task description
    let taskDescription = nluEntities.task_description_override || fetchedMessageContent.text_content;
    // Potentially use LLM to summarize or create a better task title from fetchedMessageContent.text_content
    // taskDescription = await llmUtilities.generateTaskTitle(fetchedMessageContent.text_content, nluEntities.task_description_override);
    const taskNotes = `Task created from ${fetchedMessageContent.platform} message:\nLink: ${fetchedMessageContent.message_url}\nSender: ${fetchedMessageContent.sender_name}\nTime: ${new Date(fetchedMessageContent.timestamp).toLocaleString()}\n\nOriginal Message Snippet:\n"${fetchedMessageContent.text_content.substring(0, 200)}${fetchedMessageContent.text_content.length > 200 ? '...' : ''}"`;
    // Step 3: Create the task in Notion (or other task system)
    try {
        logger.info(`[taskFromChatSkill] Creating Notion task with description: "${taskDescription.substring(0, 50)}..."`);
        // const notionTaskParams: CreateNotionTaskParams = {
        //   description: taskDescription,
        //   dueDate: nluEntities.due_date, // Needs parsing/validation if natural language
        //   priority: nluEntities.priority,
        //   assignee: nluEntities.assignee, // Needs resolution to Notion user
        //   listName: nluEntities.target_task_list_or_project,
        //   notionTasksDbId: process.env.ATOM_NOTION_TASKS_DATABASE_ID || 'YOUR_DEFAULT_TASK_DB_ID', // Use configured default
        //   notes: taskNotes,
        // };
        // const creationResult = await notionSkills.createNotionTask(userId, notionTaskParams);
        // if (!creationResult.ok || !creationResult.data) {
        //   throw new Error(creationResult.error?.message || "Failed to create task in Notion.");
        // }
        // Placeholder creation result:
        const placeholderTaskId = `notion_sim_${Date.now()}`;
        const placeholderTaskUrl = `https://notion.so/${placeholderTaskId}`;
        logger.warn(`[taskFromChatSkill] Notion task creation is using placeholder data.`);
        const resultData = {
            success: true,
            message: "Task created successfully in Notion (placeholder).",
            taskId: placeholderTaskId, //creationResult.data.taskId,
            taskUrl: placeholderTaskUrl, //creationResult.data.taskUrl,
            taskTitle: taskDescription,
            original_message_link_included: true,
        };
        return { ok: true, data: resultData };
    }
    catch (error) {
        logger.error(`[taskFromChatSkill] Error creating task: ${error.message}`, error);
        return {
            ok: false,
            error: { code: "TASK_CREATION_ERROR", message: `Failed to create task: ${error.message}` },
            data: { success: false, message: `Failed to create task: ${error.message}`, taskTitle: taskDescription }
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGFza0Zyb21DaGF0U2tpbGwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ0YXNrRnJvbUNoYXRTa2lsbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFVQSxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFDN0MsT0FBTyxFQUFFLDZCQUE2QixFQUFFLE1BQU0sb0JBQW9CLENBQUMsQ0FBQyxlQUFlO0FBQ25GLE9BQU8sRUFBRSxnQkFBZ0IsSUFBSSx1QkFBdUIsRUFBRSxNQUFNLDJCQUEyQixDQUFDLENBQUMsd0JBQXdCO0FBRWpILHFHQUFxRztBQUNyRyxnSEFBZ0g7QUFDaEgsa0VBQWtFO0FBRWxFOzs7Ozs7R0FNRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUseUJBQXlCLENBQzdDLE1BQWMsRUFDZCxXQUFpRDtJQUVqRCxNQUFNLENBQUMsSUFBSSxDQUFDLHlFQUF5RSxNQUFNLGlCQUFpQixXQUFXLENBQUMsc0JBQXNCLGdCQUFnQixXQUFXLENBQUMsZUFBZSxFQUFFLENBQUMsQ0FBQztJQUM3TCxNQUFNLENBQUMsS0FBSyxDQUFDLHFDQUFxQyxJQUFJLENBQUMsU0FBUyxDQUFDLFdBQVcsQ0FBQyxFQUFFLENBQUMsQ0FBQztJQUVqRixJQUFJLHFCQUFxQixHQUE4QixJQUFJLENBQUM7SUFFNUQseUVBQXlFO0lBQ3pFLElBQUksQ0FBQztRQUNILE1BQU0sQ0FBQyxJQUFJLENBQUMsZ0VBQWdFLFdBQVcsQ0FBQyxzQkFBc0IsVUFBVSxXQUFXLENBQUMsZUFBZSxFQUFFLENBQUMsQ0FBQztRQUN2SixzRUFBc0U7UUFDdEUsMkVBQTJFO1FBQzNFLFFBQVEsV0FBVyxDQUFDLGVBQWUsRUFBRSxDQUFDO1lBQ3BDLEtBQUssT0FBTztnQkFDVixvSEFBb0g7Z0JBQ3BILG1HQUFtRztnQkFDbkcsaUZBQWlGO2dCQUNqRixNQUFNLENBQUMsSUFBSSxDQUFDLGlFQUFpRSxDQUFDLENBQUM7Z0JBQy9FLE1BQU0sSUFBSSxLQUFL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QUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLFVBQVUsRUFBRSxDQUFDO0lBRXhDLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sQ0FBQyxLQUFLLENBQUMsNENBQTRDLEtBQUssQ0FBQyxPQUFPLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUNqRixPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUUsRUFBRSxJQUFJLEVBQUUscUJBQXFCLEVBQUUsT0FBTyxFQUFFLDBCQUEwQixLQUFLLENBQUMsT0FBTyxFQUFFLEVBQUU7WUFDMUYsSUFBSSxFQUFFLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsMEJBQTBCLEtBQUssQ0FBQyxPQUFPLEVBQUUsRUFBRSxTQUFTLEVBQUUsZUFBZSxFQUFFO1NBQ3pHLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIENyZWF0ZVRhc2tGcm9tQ2hhdE1lc3NhZ2VObHVFbnRpdGllcyxcbiAgQ2hhdE1lc3NhZ2VDb250ZW50LFxuICBUYXNrQ3JlYXRpb25SZXN1bHRGcm9tTWVzc2FnZSxcbiAgQ3JlYXRlVGFza0Zyb21DaGF0TWVzc2FnZVNraWxsUmVzcG9uc2UsXG4gIFNraWxsUmVzcG9uc2UsIC8vIEdlbmVyaWMgU2tpbGxSZXNwb25zZVxuICBOb3Rpb25UYXNrLCAvLyBBc3N1bWluZyB3ZSdsbCBjcmVhdGUgYSBOb3Rpb25UYXNrXG4gIENyZWF0ZU5vdGlvblRhc2tQYXJhbXMsXG4gIENyZWF0ZVRhc2tEYXRhLCAvLyBGb3IgdGhlIGFjdHVhbCByZXNwb25zZSBmcm9tIGNyZWF0ZU5vdGlvblRhc2tCYWNrZW5kXG59IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL191dGlscy9sb2dnZXInO1xuaW1wb3J0IHsgQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQgfSBmcm9tICcuLi9fbGlicy9jb25zdGFudHMnOyAvLyBJbXBvcnQgREIgSURcbmltcG9ydCB7IGNyZWF0ZU5vdGlvblRhc2sgYXMgY3JlYXRlTm90aW9uVGFza0JhY2tlbmQgfSBmcm9tICcuL25vdGlvbkFuZFJlc2VhcmNoU2tpbGxzJzsgLy8gSW1wb3J0IGJhY2tlbmQgY2FsbGVyXG5cbi8vIFRPRE86IEltcG9ydCBkYXRlL3ByaW9yaXR5IHBhcnNpbmcgdXRpbGl0aWVzIGZyb20gbm90aW9uVGFza1NraWxscy50cyBpZiBOTFUgZW50aXRpZXMgYXJlIGV4cGFuZGVkXG4vLyBGb3Igbm93LCBDcmVhdGVUYXNrRnJvbUNoYXRNZXNzYWdlTmx1RW50aXRpZXMgZG9lc24ndCBoYXZlIGRldGFpbGVkIGRhdGUvcHJpb3JpdHkgZmllbGRzIGJleW9uZCB0aGUgb3ZlcnJpZGUuXG4vLyBpbXBvcnQgeyBwYXJzZUR1ZURhdGUsIG1hcFByaW9yaXR5IH0gZnJvbSAnLi9ub3Rpb25UYXNrU2tpbGxzJztcblxuLyoqXG4gKiBDcmVhdGVzIGEgdGFzayBpbiBhIHRhc2sgbWFuYWdlbWVudCBzeXN0ZW0gYmFzZWQgb24gYSByZWZlcmVuY2VkIGNoYXQgbWVzc2FnZS5cbiAqXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlciByZXF1ZXN0aW5nIHRoZSB0YXNrIGNyZWF0aW9uLlxuICogQHBhcmFtIG5sdUVudGl0aWVzIFRoZSBwYXJzZWQgTkxVIGVudGl0aWVzIGZyb20gdGhlIENyZWF0ZVRhc2tGcm9tQ2hhdE1lc3NhZ2UgaW50ZW50LlxuICogQHJldHVybnMgQSBwcm9taXNlIHRoYXQgcmVzb2x2ZXMgdG8gQ3JlYXRlVGFza0Zyb21DaGF0TWVzc2FnZVNraWxsUmVzcG9uc2UuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjcmVhdGVUYXNrRnJvbUNoYXRNZXNzYWdlKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgbmx1RW50aXRpZXM6IENyZWF0ZVRhc2tGcm9tQ2hhdE1lc3NhZ2VObHVFbnRpdGllcyxcbik6IFByb21pc2U8Q3JlYXRlVGFza0Zyb21DaGF0TWVzc2FnZVNraWxsUmVzcG9uc2U+IHtcbiAgbG9nZ2VyLmluZm8oYFt0YXNrRnJvbUNoYXRTa2lsbF0gU3RhcnRpbmcgdGFzayBjcmVhdGlvbiBmcm9tIGNoYXQgbWVzc2FnZSBmb3IgdXNlciAke3VzZXJJZH0uIFJlZmVyZW5jZTogXCIke25sdUVudGl0aWVzLmNoYXRfbWVzc2FnZV9yZWZlcmVuY2V9XCIsIFBsYXRmb3JtOiAke25sdUVudGl0aWVzLnNvdXJjZV9wbGF0Zm9ybX1gKTtcbiAgbG9nZ2VyLmRlYnVnKGBbdGFza0Zyb21DaGF0U2tpbGxdIE5MVSBFbnRpdGllczogJHtKU09OLnN0cmluZ2lmeShubHVFbnRpdGllcyl9YCk7XG5cbiAgbGV0IGZldGNoZWRNZXNzYWdlQ29udGVudDogQ2hhdE1lc3NhZ2VDb250ZW50IHwgbnVsbCA9IG51bGw7XG5cbiAgLy8gU3RlcCAxOiBGZXRjaCB0aGUgY2hhdCBtZXNzYWdlIGNvbnRlbnQgYmFzZWQgb24gcmVmZXJlbmNlIGFuZCBwbGF0Zm9ybVxuICB0cnkge1xuICAgIGxvZ2dlci5pbmZvKGBbdGFza0Zyb21DaGF0U2tpbGxdIEZldGNoaW5nIG1lc3NhZ2UgY29udGVudCBmb3IgcmVmZXJlbmNlOiBcIiR7bmx1RW50aXRpZXMuY2hhdF9tZXNzYWdlX3JlZmVyZW5jZX1cIiBmcm9tICR7bmx1RW50aXRpZXMuc291cmNlX3BsYXRmb3JtfWApO1xuICAgIC8vIFRPRE86IEltcGxlbWVudCBvciB2ZXJpZnkgdGhlIGFjdHVhbCBtZXNzYWdlIGZldGNoaW5nIHNraWxscyBiZWxvdy5cbiAgICAvLyBGb3Igbm93LCB0aGV5IHdpbGwgbGlrZWx5IHJldHVybiBlcnJvcnMgb3IgbW9jayBkYXRhIGlmIG5vdCBpbXBsZW1lbnRlZC5cbiAgICBzd2l0Y2ggKG5sdUVudGl0aWVzLnNvdXJjZV9wbGF0Zm9ybSkge1xuICAgICAgY2FzZSAnc2xhY2snOlxuICAgICAgICAvLyBjb25zdCBzbGFja1JlcyA9IGF3YWl0IHNsYWNrU2tpbGxzLmdldFNsYWNrTWVzc2FnZURldGFpbHNCeVJlZmVyZW5jZSh1c2VySWQsIG5sdUVudGl0aWVzLmNoYXRfbWVzc2FnZV9yZWZlcmVuY2UpO1xuICAgICAgICAvLyBpZiAoc2xhY2tSZXMub2sgJiYgc2xhY2tSZXMuZGF0YSkgZmV0Y2hlZE1lc3NhZ2VDb250ZW50ID0gc2xhY2tSZXMuZGF0YTsgLy8gQWRhcHQgZGF0YSBzdHJ1Y3R1cmVcbiAgICAgICAgLy8gZWxzZSB0aHJvdyBuZXcgRXJyb3Ioc2xhY2tSZXMuZXJyb3I/Lm1lc3NhZ2UgfHwgXCJGYWlsZWQgdG8gZmV0Y2ggZnJvbSBTbGFja1wiKTtcbiAgICAgICAgbG9nZ2VyLndhcm4oXCJbdGFza0Zyb21DaGF0U2tpbGxdIFNsYWNrIG1lc3NhZ2UgZmV0Y2hpbmcgbm90IGltcGxlbWVudGVkIHlldC5cIik7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcihcIlNsYWNrIG1lc3NhZ2UgZmV0Y2hpbmcgbm90IGltcGxlbWVudGVkIHlldC5cIik7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnbXN0ZWFtcyc6XG4gICAgICAgIC8vIGNvbnN0IHRlYW1zUmVzID0gYXdhaXQgdGVhbXNTa2lsbHMuZ2V0VGVhbXNNZXNzYWdlRGV0YWlsc0J5UmVmZXJlbmNlKHVzZXJJZCwgbmx1RW50aXRpZXMuY2hhdF9tZXNzYWdlX3JlZmVyZW5jZSk7XG4gICAgICAgIC8vIGlmICh0ZWFtc1Jlcy5vayAmJiB0ZWFtc1Jlcy5kYXRhKSBmZXRjaGVkTWVzc2FnZUNvbnRlbnQgPSB0ZWFtc1Jlcy5kYXRhOyAvLyBBZGFwdCBkYXRhIHN0cnVjdHVyZVxuICAgICAgICAvLyBlbHNlIHRocm93IG5ldyBFcnJvcih0ZWFtc1Jlcy5lcnJvcj8ubWVzc2FnZSB8fCBcIkZhaWxlZCB0byBmZXRjaCBmcm9tIE1TIFRlYW1zXCIpO1xuICAgICAgICBsb2dnZXIud2FybihcIlt0YXNrRnJvbUNoYXRTa2lsbF0gTVMgVGVhbXMgbWVzc2FnZSBmZXRjaGluZyBub3QgaW1wbGVtZW50ZWQgeWV0LlwiKTtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKFwiTVMgVGVhbXMgbWVzc2FnZSBmZXRjaGluZyBub3QgaW1wbGVtZW50ZWQgeWV0LlwiKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdnbWFpbF90aHJlYWRfaXRlbSc6XG4gICAgICAgIC8vIGNvbnN0IGdtYWlsUmVzID0gYXdhaXQgZW1haWxTa2lsbHMuZ2V0R21haWxNZXNzYWdlRGV0YWlsc0J5UmVmZXJlbmNlKHVzZXJJZCwgbmx1RW50aXRpZXMuY2hhdF9tZXNzYWdlX3JlZmVyZW5jZSk7XG4gICAgICAgIC8vIGlmIChnbWFpbFJlcy5vayAmJiBnbWFpbFJlcy5kYXRhKSBmZXRjaGVkTWVzc2FnZUNvbnRlbnQgPSBnbWFpbFJlcy5kYXRhOyAvLyBBZGFwdCBkYXRhIHN0cnVjdHVyZVxuICAgICAgICAvLyBlbHNlIHRocm93IG5ldyBFcnJvcihnbWFpbFJlcy5lcnJvcj8ubWVzc2FnZSB8fCBcIkZhaWxlZCB0byBmZXRjaCBmcm9tIEdtYWlsXCIpO1xuICAgICAgICBsb2dnZXIud2FybihcIlt0YXNrRnJvbUNoYXRTa2lsbF0gR21haWwgbWVzc2FnZSBmZXRjaGluZyBub3QgaW1wbGVtZW50ZWQgeWV0LlwiKTtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKFwiR21haWwgbWVzc2FnZSBmZXRjaGluZyBub3QgaW1wbGVtZW50ZWQgeWV0LlwiKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBkZWZhdWx0OlxuICAgICAgICAvLyBUaGlzIGNoZWNrIGVuc3VyZXMgbmx1RW50aXRpZXMuc291cmNlX3BsYXRmb3JtIGlzIG9uZSBvZiB0aGUgZXhwZWN0ZWQgdHlwZXNcbiAgICAgICAgLy8gSXQncyBnb29kIGZvciB0eXBlIHNhZmV0eSBpZiBDcmVhdGVUYXNrRnJvbUNoYXRNZXNzYWdlTmx1RW50aXRpZXMuc291cmNlX3BsYXRmb3JtIGlzIGEgdW5pb24gb2YgbGl0ZXJhbHMuXG4gICAgICAgIGNvbnN0IGV4aGF1c3RpdmVDaGVjazogbmV2ZXIgPSBubHVFbnRpdGllcy5zb3VyY2VfcGxhdGZvcm07XG4gICAgICAgIHRocm93IG5ldyBFcnJvcihgVW5zdXBwb3J0ZWQgc291cmNlIHBsYXRmb3JtOiAke2V4aGF1c3RpdmVDaGVja31gKTtcbiAgICB9XG5cbiAgICAvLyBpZiAoIWZldGNoZWRNZXNzYWdlQ29udGVudCkge1xuICAgIC8vICAgdGhyb3cgbmV3IEVycm9yKFwiRmFpbGVkIHRvIGZldGNoIG1lc3NhZ2UgY29udGVudCBmcm9tIHRoZSBzcGVjaWZpZWQgcGxhdGZvcm0uXCIpO1xuICAgIC8vIH1cblxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbdGFza0Zyb21DaGF0U2tpbGxdIEVycm9yIGZldGNoaW5nIG1lc3NhZ2UgY29udGVudDogJHtlcnJvci5tZXNzYWdlfWAsIGVycm9yKTtcbiAgICAvLyBGYWxsYmFjayB0byB1c2luZyB0aGUgcmVmZXJlbmNlIGFzIHRhc2sgZGVzY3JpcHRpb24gaWYgZmV0Y2hpbmcgZmFpbHNcbiAgICAvLyBUaGlzIGFsbG93cyB0YXNrIGNyZWF0aW9uIGV2ZW4gaWYgbWVzc2FnZSBjb250ZXh0IGlzbid0IGF2YWlsYWJsZS5cbiAgICBsb2dnZXIud2FybihgW3Rhc2tGcm9tQ2hhdFNraWxsXSBVc2luZyBjaGF0X21lc3NhZ2VfcmVmZXJlbmNlIGFzIHRhc2sgZGVzY3JpcHRpb24gZHVlIHRvIGZldGNoIGVycm9yLmApO1xuICAgIGZldGNoZWRNZXNzYWdlQ29udGVudCA9IHtcbiAgICAgICAgcGxhdGZvcm06IG5sdUVudGl0aWVzLnNvdXJjZV9wbGF0Zm9ybSxcbiAgICAgICAgbWVzc2FnZV9pZDogXCJmYWxsYmFja19cIiArIERhdGUubm93KCksXG4gICAgICAgIHRleHRfY29udGVudDogbmx1RW50aXRpZXMuY2hhdF9tZXNzYWdlX3JlZmVyZW5jZSwgLy8gVXNlIHJlZmVyZW5jZSBhcyBjb250ZW50XG4gICAgICAgIG1lc3NhZ2VfdXJsOiB1bmRlZmluZWQsIC8vIE5vIFVSTCBpZiBjb250ZW50IGNvdWxkbid0IGJlIGZldGNoZWRcbiAgICAgICAgdGltZXN0YW1wOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIHNlbmRlcl9uYW1lOiBcIlVua25vd24gKGZldGNoIGZhaWxlZClcIlxuICAgIH07XG4gICAgLy8gRG8gbm90IHJldHVybiBlcnJvciBoZXJlLCBwcm9jZWVkIHdpdGggdGFzayBjcmVhdGlvbiB1c2luZyBmYWxsYmFjayBjb250ZW50XG4gIH1cblxuICAvLyBTdGVwIDI6IERldGVybWluZSB0YXNrIGRlc2NyaXB0aW9uXG4gIGxldCB0YXNrRGVzY3JpcHRpb24gPSBubHVFbnRpdGllcy50YXNrX2Rlc2NyaXB0aW9uX292ZXJyaWRlIHx8IGZldGNoZWRNZXNzYWdlQ29udGVudC50ZXh0X2NvbnRlbnQ7XG5cbiAgLy8gT3B0aW9uYWw6IFVzZSBMTE0gdG8gc3VtbWFyaXplIGlmIGRlc2NyaXB0aW9uIGlzIGxvbmcgYW5kIG5vIG92ZXJyaWRlLlxuICAvLyBpZiAoIW5sdUVudGl0aWVzLnRhc2tfZGVzY3JpcHRpb25fb3ZlcnJpZGUgJiYgdGFza0Rlc2NyaXB0aW9uLmxlbmd0aCA+IDE1MCkgeyAvLyBFeGFtcGxlIGxlbmd0aCBjaGVja1xuICAvLyAgIHRyeSB7XG4gIC8vICAgICBjb25zdCBzdW1tYXJ5UmVzdWx0ID0gYXdhaXQgbGxtVXRpbGl0aWVzLmdlbmVyYXRlVGFza1RpdGxlKHRhc2tEZXNjcmlwdGlvbik7IC8vIEFzc3VtaW5nIHN1Y2ggYSB1dGlsaXR5XG4gIC8vICAgICBpZiAoc3VtbWFyeVJlc3VsdC5vayAmJiBzdW1tYXJ5UmVzdWx0LmRhdGE/LnRpdGxlKSB7XG4gIC8vICAgICAgIHRhc2tEZXNjcmlwdGlvbiA9IHN1bW1hcnlSZXN1bHQuZGF0YS50aXRsZTtcbiAgLy8gICAgICAgbG9nZ2VyLmluZm8oYFt0YXNrRnJvbUNoYXRTa2lsbF0gU3VtbWFyaXplZCB0YXNrIGRlc2NyaXB0aW9uIHRvOiBcIiR7dGFza0Rlc2NyaXB0aW9ufVwiYCk7XG4gIC8vICAgICB9XG4gIC8vICAgfSBjYXRjaCAobGxtRXJyb3I6IGFueSkge1xuICAvLyAgICAgbG9nZ2VyLndhcm4oYFt0YXNrRnJvbUNoYXRTa2lsbF0gQ291bGQgbm90IHN1bW1hcml6ZSB0YXNrIGRlc2NyaXB0aW9uOiAke2xsbUVycm9yLm1lc3NhZ2V9YCk7XG4gIC8vICAgfVxuICAvLyB9XG4gICAgLy8gRW5zdXJlIHRhc2tEZXNjcmlwdGlvbiBpcyBub3Qgb3Zlcmx5IGxvbmcgZm9yIE5vdGlvbiB0aXRsZVxuICAgIGlmICh0YXNrRGVzY3JpcHRpb24ubGVuZ3RoID4gMjAwKSB7IC8vIE5vdGlvbiB0aXRsZXMgY2FuIGJlIGxvbmdlciwgYnV0IGdvb2QgdG8ga2VlcCBpdCByZWFzb25hYmxlXG4gICAgICAgIGxvZ2dlci53YXJuKGBbdGFza0Zyb21DaGF0U2tpbGxdIFRhc2sgZGVzY3JpcHRpb24gaXMgbG9uZyAoJHt0YXNrRGVzY3JpcHRpb24ubGVuZ3RofSBjaGFycyksIGNvbnNpZGVyIHN1bW1hcml6aW5nIGZvciB0aXRsZSBhbmQgcHV0dGluZyBmdWxsIHRleHQgaW4gbm90ZXMuYCk7XG4gICAgICAgIC8vIHRhc2tEZXNjcmlwdGlvbiA9IHRhc2tEZXNjcmlwdGlvbi5zdWJzdHJpbmcoMCwgMTk3KSArIFwiLi4uXCI7IC8vIFRydW5jYXRlIGlmIG5lZWRlZFxuICAgIH1cblxuXG4gIGNvbnN0IHRhc2tOb3Rlc1BhcnRzID0gW2BUYXNrIGNyZWF0ZWQgZnJvbSAke2ZldGNoZWRNZXNzYWdlQ29udGVudC5wbGF0Zm9ybX0gbWVzc2FnZS5gXTtcbiAgaWYoZmV0Y2hlZE1lc3NhZ2VDb250ZW50Lm1lc3NhZ2VfdXJsKSB7XG4gICAgdGFza05vdGVzUGFydHMucHVzaChgTGluazogJHtmZXRjaGVkTWVzc2FnZUNvbnRlbnQubWVzc2FnZV91cmx9YCk7XG4gIH1cbiAgaWYoZmV0Y2hlZE1lc3NhZ2VDb250ZW50LnNlbmRlcl9uYW1lICYmIGZldGNoZWRNZXNzYWdlQ29udGVudC5zZW5kZXJfbmFtZSAhPT0gXCJVbmtub3duIChmZXRjaCBmYWlsZWQpXCIpIHtcbiAgICB0YXNrTm90ZXNQYXJ0cy5wdXNoKGBTZW5kZXI6ICR7ZmV0Y2hlZE1lc3NhZ2VDb250ZW50LnNlbmRlcl9uYW1lfWApO1xuICB9XG4gIHRhc2tOb3Rlc1BhcnRzLnB1c2goYFRpbWU6ICR7bmV3IERhdGUoZmV0Y2hlZE1lc3NhZ2VDb250ZW50LnRpbWVzdGFtcCkudG9Mb2NhbGVTdHJpbmcoKX1gKTtcbiAgaWYgKGZldGNoZWRNZXNzYWdlQ29udGVudC50ZXh0X2NvbnRlbnQgIT09IG5sdUVudGl0aWVzLmNoYXRfbWVzc2FnZV9yZWZlcmVuY2UpIHsgLy8gT25seSBhZGQgc25pcHBldCBpZiBpdCdzIHJlYWwgZmV0Y2hlZCBjb250ZW50XG4gICAgICB0YXNrTm90ZXNQYXJ0cy5wdXNoKGBcXG5PcmlnaW5hbCBNZXNzYWdlIFNuaXBwZXQ6XFxuXCIke2ZldGNoZWRNZXNzYWdlQ29udGVudC50ZXh0X2NvbnRlbnQuc3Vic3RyaW5nKDAsIDIwMCl9JHtmZXRjaGVkTWVzc2FnZUNvbnRlbnQudGV4dF9jb250ZW50Lmxlbmd0aCA+IDIwMCA/ICcuLi4nIDogJyd9XCJgKTtcbiAgfVxuICBjb25zdCB0YXNrTm90ZXMgPSB0YXNrTm90ZXNQYXJ0cy5qb2luKCdcXG4nKTtcblxuICAvLyBTdGVwIDM6IENyZWF0ZSB0aGUgdGFzayBpbiBOb3Rpb24gKG9yIG90aGVyIHRhc2sgc3lzdGVtKVxuICB0cnkge1xuICAgIGxvZ2dlci5pbmZvKGBbdGFza0Zyb21DaGF0U2tpbGxdIENyZWF0aW5nIE5vdGlvbiB0YXNrIHdpdGggZGVzY3JpcHRpb246IFwiJHt0YXNrRGVzY3JpcHRpb24uc3Vic3RyaW5nKDAsNTApfS4uLlwiYCk7XG5cbiAgICBjb25zdCBub3Rpb25UYXNrUGFyYW1zOiBDcmVhdGVOb3Rpb25UYXNrUGFyYW1zID0ge1xuICAgICAgZGVzY3JpcHRpb246IHRhc2tEZXNjcmlwdGlvbixcbiAgICAgIC8vIEFzc3VtaW5nIENyZWF0ZVRhc2tGcm9tQ2hhdE1lc3NhZ2VObHVFbnRpdGllcyBtaWdodCBnZXQgdGhlc2UgZmllbGRzIGluIGZ1dHVyZTpcbiAgICAgIC8vIGR1ZURhdGU6IHBhcnNlRHVlRGF0ZShubHVFbnRpdGllcy5kdWVfZGF0ZSksXG4gICAgICAvLyBwcmlvcml0eTogbWFwUHJpb3JpdHkobmx1RW50aXRpZXMucHJpb3JpdHkpLFxuICAgICAgLy8gbGlzdE5hbWU6IG5sdUVudGl0aWVzLnRhcmdldF90YXNrX2xpc3Rfb3JfcHJvamVjdCxcbiAgICAgIG5vdGlvblRhc2tzRGJJZDogQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQgfHwgJycsXG4gICAgICBub3RlczogdGFza05vdGVzLFxuICAgICAgc3RhdHVzOiAnVG8gRG8nLCAvLyBEZWZhdWx0IHN0YXR1cyBmb3IgbmV3IHRhc2tzXG4gICAgfTtcblxuICAgIGlmICghbm90aW9uVGFza1BhcmFtcy5ub3Rpb25UYXNrc0RiSWQpIHtcbiAgICAgICAgbG9nZ2VyLmVycm9yKFwiW3Rhc2tGcm9tQ2hhdFNraWxsXSBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCBpcyBub3QgY29uZmlndXJlZC4gQ2Fubm90IGNyZWF0ZSBOb3Rpb24gdGFzay5cIik7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcihcIk5vdGlvbiBUYXNrcyBEYXRhYmFzZSBJRCBpcyBub3QgY29uZmlndXJlZC5cIik7XG4gICAgfVxuXG4gICAgY29uc3QgY3JlYXRpb25SZXN1bHQgPSBhd2FpdCBjcmVhdGVOb3Rpb25UYXNrQmFja2VuZCh1c2VySWQsIG5vdGlvblRhc2tQYXJhbXMpO1xuXG4gICAgaWYgKCFjcmVhdGlvblJlc3VsdC5vayB8fCAhY3JlYXRpb25SZXN1bHQuZGF0YSkge1xuICAgICAgbG9nZ2VyLmVycm9yKGBbdGFza0Zyb21DaGF0U2tpbGxdIEZhaWxlZCB0byBjcmVhdGUgdGFzayBpbiBOb3Rpb24gdmlhIGJhY2tlbmQ6ICR7Y3JlYXRpb25SZXN1bHQuZXJyb3I/Lm1lc3NhZ2UgfHwgJ1Vua25vd24gZXJyb3InfWApO1xuICAgICAgdGhyb3cgbmV3IEVycm9yKGNyZWF0aW9uUmVzdWx0LmVycm9yPy5tZXNzYWdlIHx8IFwiRmFpbGVkIHRvIGNyZWF0ZSB0YXNrIGluIE5vdGlvbiB2aWEgYmFja2VuZC5cIik7XG4gICAgfVxuXG4gICAgY29uc3QgY3JlYXRlZFRhc2tEYXRhID0gY3JlYXRpb25SZXN1bHQuZGF0YTtcblxuICAgIGxvZ2dlci5pbmZvKGBbdGFza0Zyb21DaGF0U2tpbGxdIFN1Y2Nlc3NmdWxseSBjcmVhdGVkIE5vdGlvbiB0YXNrIElEOiAke2NyZWF0ZWRUYXNrRGF0YS50YXNrSWR9YCk7XG5cbiAgICBjb25zdCByZXN1bHREYXRhOiBUYXNrQ3JlYXRpb25SZXN1bHRGcm9tTWVzc2FnZSA9IHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICBtZXNzYWdlOiBjcmVhdGVkVGFza0RhdGEubWVzc2FnZSB8fCBcIlRhc2sgY3JlYXRlZCBzdWNjZXNzZnVsbHkgaW4gTm90aW9uLlwiLFxuICAgICAgdGFza0lkOiBjcmVhdGVkVGFza0RhdGEudGFza0lkLFxuICAgICAgdGFza1VybDogY3JlYXRlZFRhc2tEYXRhLnRhc2tVcmwsXG4gICAgICB0YXNrVGl0bGU6IHRhc2tEZXNjcmlwdGlvbiwgLy8gVGhlIGRlc2NyaXB0aW9uIHVzZWQgZm9yIGNyZWF0aW9uXG4gICAgICBvcmlnaW5hbF9tZXNzYWdlX2xpbmtfaW5jbHVkZWQ6ICEhZmV0Y2hlZE1lc3NhZ2VDb250ZW50Lm1lc3NhZ2VfdXJsLCAvLyBUcnVlIGlmIGEgVVJMIHdhcyBhdmFpbGFibGVcbiAgICB9O1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiBcIk1FU1NBR0VfRkVUQ0hfRVJST1JcIiwgbWVzc2FnZTogYEZhaWxlZCB0byBmZXRjaCBtZXNzYWdlOiAke2Vycm9yLm1lc3NhZ2V9YCB9LFxuICAgICAgZGF0YTogeyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogYEZhaWxlZCB0byBmZXRjaCBtZXNzYWdlOiAke2Vycm9yLm1lc3NhZ2V9YCB9XG4gICAgfTtcbiAgfVxuXG4gIC8vIFN0ZXAgMjogRGV0ZXJtaW5lIHRhc2sgZGVzY3JpcHRpb25cbiAgbGV0IHRhc2tEZXNjcmlwdGlvbiA9IG5sdUVudGl0aWVzLnRhc2tfZGVzY3JpcHRpb25fb3ZlcnJpZGUgfHwgZmV0Y2hlZE1lc3NhZ2VDb250ZW50LnRleHRfY29udGVudDtcbiAgLy8gUG90ZW50aWFsbHkgdXNlIExMTSB0byBzdW1tYXJpemUgb3IgY3JlYXRlIGEgYmV0dGVyIHRhc2sgdGl0bGUgZnJvbSBmZXRjaGVkTWVzc2FnZUNvbnRlbnQudGV4dF9jb250ZW50XG4gIC8vIHRhc2tEZXNjcmlwdGlvbiA9IGF3YWl0IGxsbVV0aWxpdGllcy5nZW5lcmF0ZVRhc2tUaXRsZShmZXRjaGVkTWVzc2FnZUNvbnRlbnQudGV4dF9jb250ZW50LCBubHVFbnRpdGllcy50YXNrX2Rlc2NyaXB0aW9uX292ZXJyaWRlKTtcblxuICBjb25zdCB0YXNrTm90ZXMgPSBgVGFzayBjcmVhdGVkIGZyb20gJHtmZXRjaGVkTWVzc2FnZUNvbnRlbnQucGxhdGZvcm19IG1lc3NhZ2U6XFxuTGluazogJHtmZXRjaGVkTWVzc2FnZUNvbnRlbnQubWVzc2FnZV91cmx9XFxuU2VuZGVyOiAke2ZldGNoZWRNZXNzYWdlQ29udGVudC5zZW5kZXJfbmFtZX1cXG5UaW1lOiAke25ldyBEYXRlKGZldGNoZWRNZXNzYWdlQ29udGVudC50aW1lc3RhbXApLnRvTG9jYWxlU3RyaW5nKCl9XFxuXFxuT3JpZ2luYWwgTWVzc2FnZSBTbmlwcGV0OlxcblwiJHtmZXRjaGVkTWVzc2FnZUNvbnRlbnQudGV4dF9jb250ZW50LnN1YnN0cmluZygwLCAyMDApfSR7ZmV0Y2hlZE1lc3NhZ2VDb250ZW50LnRleHRfY29udGVudC5sZW5ndGggPiAyMDAgPyAnLi4uJyA6ICcnfVwiYDtcblxuICAvLyBTdGVwIDM6IENyZWF0ZSB0aGUgdGFzayBpbiBOb3Rpb24gKG9yIG90aGVyIHRhc2sgc3lzdGVtKVxuICB0cnkge1xuICAgIGxvZ2dlci5pbmZvKGBbdGFza0Zyb21DaGF0U2tpbGxdIENyZWF0aW5nIE5vdGlvbiB0YXNrIHdpdGggZGVzY3JpcHRpb246IFwiJHt0YXNrRGVzY3JpcHRpb24uc3Vic3RyaW5nKDAsNTApfS4uLlwiYCk7XG4gICAgLy8gY29uc3Qgbm90aW9uVGFza1BhcmFtczogQ3JlYXRlTm90aW9uVGFza1BhcmFtcyA9IHtcbiAgICAvLyAgIGRlc2NyaXB0aW9uOiB0YXNrRGVzY3JpcHRpb24sXG4gICAgLy8gICBkdWVEYXRlOiBubHVFbnRpdGllcy5kdWVfZGF0ZSwgLy8gTmVlZHMgcGFyc2luZy92YWxpZGF0aW9uIGlmIG5hdHVyYWwgbGFuZ3VhZ2VcbiAgICAvLyAgIHByaW9yaXR5OiBubHVFbnRpdGllcy5wcmlvcml0eSxcbiAgICAvLyAgIGFzc2lnbmVlOiBubHVFbnRpdGllcy5hc3NpZ25lZSwgLy8gTmVlZHMgcmVzb2x1dGlvbiB0byBOb3Rpb24gdXNlclxuICAgIC8vICAgbGlzdE5hbWU6IG5sdUVudGl0aWVzLnRhcmdldF90YXNrX2xpc3Rfb3JfcHJvamVjdCxcbiAgICAvLyAgIG5vdGlvblRhc2tzRGJJZDogcHJvY2Vzcy5lbnYuQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQgfHwgJ1lPVVJfREVGQVVMVF9UQVNLX0RCX0lEJywgLy8gVXNlIGNvbmZpZ3VyZWQgZGVmYXVsdFxuICAgIC8vICAgbm90ZXM6IHRhc2tOb3RlcyxcbiAgICAvLyB9O1xuICAgIC8vIGNvbnN0IGNyZWF0aW9uUmVzdWx0ID0gYXdhaXQgbm90aW9uU2tpbGxzLmNyZWF0ZU5vdGlvblRhc2sodXNlcklkLCBub3Rpb25UYXNrUGFyYW1zKTtcbiAgICAvLyBpZiAoIWNyZWF0aW9uUmVzdWx0Lm9rIHx8ICFjcmVhdGlvblJlc3VsdC5kYXRhKSB7XG4gICAgLy8gICB0aHJvdyBuZXcgRXJyb3IoY3JlYXRpb25SZXN1bHQuZXJyb3I/Lm1lc3NhZ2UgfHwgXCJGYWlsZWQgdG8gY3JlYXRlIHRhc2sgaW4gTm90aW9uLlwiKTtcbiAgICAvLyB9XG5cbiAgICAvLyBQbGFjZWhvbGRlciBjcmVhdGlvbiByZXN1bHQ6XG4gICAgY29uc3QgcGxhY2Vob2xkZXJUYXNrSWQgPSBgbm90aW9uX3NpbV8ke0RhdGUubm93KCl9YDtcbiAgICBjb25zdCBwbGFjZWhvbGRlclRhc2tVcmwgPSBgaHR0cHM6Ly9ub3Rpb24uc28vJHtwbGFjZWhvbGRlclRhc2tJZH1gO1xuICAgIGxvZ2dlci53YXJuKGBbdGFza0Zyb21DaGF0U2tpbGxdIE5vdGlvbiB0YXNrIGNyZWF0aW9uIGlzIHVzaW5nIHBsYWNlaG9sZGVyIGRhdGEuYCk7XG5cbiAgICBjb25zdCByZXN1bHREYXRhOiBUYXNrQ3JlYXRpb25SZXN1bHRGcm9tTWVzc2FnZSA9IHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICBtZXNzYWdlOiBcIlRhc2sgY3JlYXRlZCBzdWNjZXNzZnVsbHkgaW4gTm90aW9uIChwbGFjZWhvbGRlcikuXCIsXG4gICAgICB0YXNrSWQ6IHBsYWNlaG9sZGVyVGFza0lkLCAvL2NyZWF0aW9uUmVzdWx0LmRhdGEudGFza0lkLFxuICAgICAgdGFza1VybDogcGxhY2Vob2xkZXJUYXNrVXJsLCAvL2NyZWF0aW9uUmVzdWx0LmRhdGEudGFza1VybCxcbiAgICAgIHRhc2tUaXRsZTogdGFza0Rlc2NyaXB0aW9uLFxuICAgICAgb3JpZ2luYWxfbWVzc2FnZV9saW5rX2luY2x1ZGVkOiB0cnVlLFxuICAgIH07XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3VsdERhdGEgfTtcblxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbdGFza0Zyb21DaGF0U2tpbGxdIEVycm9yIGNyZWF0aW5nIHRhc2s6ICR7ZXJyb3IubWVzc2FnZX1gLCBlcnJvcik7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6IFwiVEFTS19DUkVBVElPTl9FUlJPUlwiLCBtZXNzYWdlOiBgRmFpbGVkIHRvIGNyZWF0ZSB0YXNrOiAke2Vycm9yLm1lc3NhZ2V9YCB9LFxuICAgICAgZGF0YTogeyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogYEZhaWxlZCB0byBjcmVhdGUgdGFzazogJHtlcnJvci5tZXNzYWdlfWAsIHRhc2tUaXRsZTogdGFza0Rlc2NyaXB0aW9uIH1cbiAgICB9O1xuICB9XG59XG4iXX0=
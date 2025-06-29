import {
  CreateTaskFromChatMessageNluEntities,
  ChatMessageContent,
  TaskCreationResultFromMessage,
  CreateTaskFromChatMessageSkillResponse,
  SkillResponse, // Generic SkillResponse
  NotionTask, // Assuming we'll create a NotionTask
  CreateNotionTaskParams,
  CreateTaskData, // For the actual response from createNotionTaskBackend
} from '../types';
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
export async function createTaskFromChatMessage(
  userId: string,
  nluEntities: CreateTaskFromChatMessageNluEntities,
): Promise<CreateTaskFromChatMessageSkillResponse> {
  logger.info(`[taskFromChatSkill] Starting task creation from chat message for user ${userId}. Reference: "${nluEntities.chat_message_reference}", Platform: ${nluEntities.source_platform}`);
  logger.debug(`[taskFromChatSkill] NLU Entities: ${JSON.stringify(nluEntities)}`);

  let fetchedMessageContent: ChatMessageContent | null = null;

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
        const exhaustiveCheck: never = nluEntities.source_platform;
        throw new Error(`Unsupported source platform: ${exhaustiveCheck}`);
    }

    // if (!fetchedMessageContent) {
    //   throw new Error("Failed to fetch message content from the specified platform.");
    // }

  } catch (error: any) {
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
  if(fetchedMessageContent.message_url) {
    taskNotesParts.push(`Link: ${fetchedMessageContent.message_url}`);
  }
  if(fetchedMessageContent.sender_name && fetchedMessageContent.sender_name !== "Unknown (fetch failed)") {
    taskNotesParts.push(`Sender: ${fetchedMessageContent.sender_name}`);
  }
  taskNotesParts.push(`Time: ${new Date(fetchedMessageContent.timestamp).toLocaleString()}`);
  if (fetchedMessageContent.text_content !== nluEntities.chat_message_reference) { // Only add snippet if it's real fetched content
      taskNotesParts.push(`\nOriginal Message Snippet:\n"${fetchedMessageContent.text_content.substring(0, 200)}${fetchedMessageContent.text_content.length > 200 ? '...' : ''}"`);
  }
  const taskNotes = taskNotesParts.join('\n');

  // Step 3: Create the task in Notion (or other task system)
  try {
    logger.info(`[taskFromChatSkill] Creating Notion task with description: "${taskDescription.substring(0,50)}..."`);

    const notionTaskParams: CreateNotionTaskParams = {
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

    const resultData: TaskCreationResultFromMessage = {
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
  let taskDescription = nluEntities.task_description_override || fetchedMessageContent.text_content;
  // Potentially use LLM to summarize or create a better task title from fetchedMessageContent.text_content
  // taskDescription = await llmUtilities.generateTaskTitle(fetchedMessageContent.text_content, nluEntities.task_description_override);

  const taskNotes = `Task created from ${fetchedMessageContent.platform} message:\nLink: ${fetchedMessageContent.message_url}\nSender: ${fetchedMessageContent.sender_name}\nTime: ${new Date(fetchedMessageContent.timestamp).toLocaleString()}\n\nOriginal Message Snippet:\n"${fetchedMessageContent.text_content.substring(0, 200)}${fetchedMessageContent.text_content.length > 200 ? '...' : ''}"`;

  // Step 3: Create the task in Notion (or other task system)
  try {
    logger.info(`[taskFromChatSkill] Creating Notion task with description: "${taskDescription.substring(0,50)}..."`);
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

    const resultData: TaskCreationResultFromMessage = {
      success: true,
      message: "Task created successfully in Notion (placeholder).",
      taskId: placeholderTaskId, //creationResult.data.taskId,
      taskUrl: placeholderTaskUrl, //creationResult.data.taskUrl,
      taskTitle: taskDescription,
      original_message_link_included: true,
    };
    return { ok: true, data: resultData };

  } catch (error: any) {
    logger.error(`[taskFromChatSkill] Error creating task: ${error.message}`, error);
    return {
      ok: false,
      error: { code: "TASK_CREATION_ERROR", message: `Failed to create task: ${error.message}` },
      data: { success: false, message: `Failed to create task: ${error.message}`, taskTitle: taskDescription }
    };
  }
}

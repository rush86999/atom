import {
  CreateTaskFromChatMessageNluEntities,
  ChatMessageContent,
  TaskCreationResultFromMessage,
  CreateTaskFromChatMessageSkillResponse,
  SkillResponse, // Generic SkillResponse
  NotionTask, // Assuming we'll create a NotionTask
  CreateNotionTaskParams, // For creating Notion tasks
} from '../types';
import { logger } from '../../_utils/logger';
// Placeholder for importing other skills that might be needed:
// import * as slackSkills from './slackSkills'; // For fetching Slack message content
// import * as teamsSkills from './msTeamsSkills'; // For fetching Teams message content
// import * as emailSkills from './emailSkills'; // For fetching Gmail item content
// import * as notionSkills from './notionAndResearchSkills'; // For creating Notion tasks
// import * as llmUtilities from './llmUtilities'; // For summarizing message or extracting task title

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
    logger.info(`[taskFromChatSkill] Placeholder: Fetching message content for reference: "${nluEntities.chat_message_reference}" from ${nluEntities.source_platform}`);
    // switch (nluEntities.source_platform) {
    //   case 'slack':
    //     // fetchedMessageContent = await slackSkills.getSlackMessageDetailsByReference(userId, nluEntities.chat_message_reference);
    //     break;
    //   case 'msteams':
    //     // fetchedMessageContent = await teamsSkills.getTeamsMessageDetailsByReference(userId, nluEntities.chat_message_reference);
    //     break;
    //   case 'gmail_thread_item':
    //     // fetchedMessageContent = await emailSkills.getGmailMessageDetailsByReference(userId, nluEntities.chat_message_reference);
    //     break;
    //   default:
    //     throw new Error(`Unsupported source platform: ${nluEntities.source_platform}`);
    // }

    // Placeholder fetched content:
    if (nluEntities.chat_message_reference.includes("error") || nluEntities.chat_message_reference.includes("bug")) {
        fetchedMessageContent = {
            platform: nluEntities.source_platform,
            message_id: "sim_" + Date.now(),
            text_content: `Simulated message content for: ${nluEntities.chat_message_reference}. This seems to be about an error that needs fixing. User @dev should look into it.`,
            message_url: `https://example.com/${nluEntities.source_platform}/message/sim_${Date.now()}`,
            timestamp: new Date().toISOString(),
            sender_name: "Simulated Sender"
        };
    } else {
         fetchedMessageContent = {
            platform: nluEntities.source_platform,
            message_id: "sim_other_" + Date.now(),
            text_content: `Simulated general message: ${nluEntities.chat_message_reference}.`,
            message_url: `https://example.com/${nluEntities.source_platform}/message/sim_other_${Date.now()}`,
            timestamp: new Date().toISOString(),
            sender_name: "Another User"
        };
    }
    logger.warn(`[taskFromChatSkill] Message content fetching is using placeholder data.`);
    if (!fetchedMessageContent) throw new Error("Failed to fetch message content (placeholder).");

  } catch (error: any) {
    logger.error(`[taskFromChatSkill] Error fetching message content: ${error.message}`, error);
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

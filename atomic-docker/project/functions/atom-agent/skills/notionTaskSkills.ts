import {
  SkillResponse,
  NotionTask,
  CreateNotionTaskParams,
  QueryNotionTasksParams,
  UpdateNotionTaskParams,
  CreateTaskData,
  UpdateTaskData,
  TaskQueryResponse,
  NotionTaskStatus,
  NotionTaskPriority,
  // Conceptual NLU entity types (assuming they'd be defined in types.ts or a dedicated nluTypes.ts)
  // For now, we'll define simple interfaces here or use 'any' for NLU input structure.
} from '../types';

import {
  createNotionTask as createNotionTaskBackend,
  queryNotionTasks as queryNotionTasksBackend,
  updateNotionTask as updateNotionTaskBackend,
} from './notionAndResearchSkills'; // Assuming these are the backend callers

import { ATOM_NOTION_TASKS_DATABASE_ID } from '../_libs/constants';
import { logger } from '../../_utils/logger';

// --- NLU Entity Interfaces (Conceptual - define more formally in types.ts later) ---
interface CreateTaskNluEntities {
  task_description: string;
  due_date_text?: string;
  priority_text?: string;
  list_name_text?: string;
  // notes_text?: string; // If NLU can pick up additional notes
}

interface QueryTasksNluEntities {
  date_condition_text?: string;
  priority_text?: string;
  list_name_text?: string;
  status_text?: string;
  description_contains_text?: string;
  sort_by_text?: "dueDate" | "priority" | "createdDate"; // Match NotionTask properties
  sort_order_text?: "ascending" | "descending";
  limit_number?: number;
}

interface UpdateTaskNluEntities {
  task_identifier_text: string; // Text to help identify the task
  new_status_text?: string;
  new_due_date_text?: string;
  new_priority_text?: string;
  new_list_name_text?: string;
  new_description_text?: string;
}


// --- Date Parsing (Simplified - Placeholder) ---
// A more robust library like date-fns, dayjs, or chrono-node would be needed for real-world parsing.
// NLU should ideally provide structured date objects.
function parseDueDate(dateText?: string): string | null {
  if (!dateText) return null;

  // Extremely basic examples, NOT production-ready
  if (dateText.toLowerCase() === 'today') {
    return new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  }
  if (dateText.toLowerCase() === 'tomorrow') {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0]; // YYYY-MM-DD
  }
  // Try to parse with Date.parse - very limited
  const parsed = Date.parse(dateText);
  if (!isNaN(parsed)) {
    return new Date(parsed).toISOString(); // Full ISO string, Notion API might prefer YYYY-MM-DD for date-only
  }
  logger.warn(`[notionTaskSkills] Could not parse due date: "${dateText}". Needs robust parsing.`);
  return null; // Indicate parsing failure
}

// --- Value Mapping ---
function mapPriority(priorityText?: string): NotionTaskPriority | null {
  if (!priorityText) return null;
  const lowerPriority = priorityText.toLowerCase();
  if (lowerPriority.includes('high')) return 'High';
  if (lowerPriority.includes('medium') || lowerPriority.includes('med')) return 'Medium';
  if (lowerPriority.includes('low')) return 'Low';
  return null;
}

function mapStatus(statusText?: string): NotionTaskStatus | null {
  if (!statusText) return null;
  const lowerStatus = statusText.toLowerCase();
  if (lowerStatus.includes('to do') || lowerStatus.includes('todo')) return 'To Do';
  if (lowerStatus.includes('in progress') || lowerStatus.includes('doing')) return 'In Progress';
  if (lowerStatus.includes('done') || lowerStatus.includes('completed')) return 'Done';
  if (lowerStatus.includes('blocked')) return 'Blocked';
  if (lowerStatus.includes('cancelled') || lowerStatus.includes('canceled')) return 'Cancelled';
  return null;
}


// --- Skill Implementations ---

export async function handleCreateNotionTask(
  userId: string,
  entities: CreateTaskNluEntities,
): Promise<SkillResponse<CreateTaskData & { userMessage: string }>> {
  logger.info(`[handleCreateNotionTask] User: ${userId}, Entities: ${JSON.stringify(entities)}`);

  if (!ATOM_NOTION_TASKS_DATABASE_ID) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Tasks Database ID (ATOM_NOTION_TASKS_DATABASE_ID) is not configured.' } };
  }
  if (!entities.task_description) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Task description is required.' } };
  }

  const dueDateISO = parseDueDate(entities.due_date_text);
  // If dueDateISO is null and entities.due_date_text was provided, it means parsing failed.
  // Depending on strictness, you might return an error here or proceed without a due date.
  if (entities.due_date_text && !dueDateISO) {
      logger.warn(`[handleCreateNotionTask] Due date text "${entities.due_date_text}" provided but could not be parsed.`);
      // Optionally, inform the user: `Could not understand the due date "${entities.due_date_text}". Task created without it.`
  }


  const params: CreateNotionTaskParams = {
    notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
    description: entities.task_description,
    dueDate: dueDateISO, // Use parsed date
    priority: mapPriority(entities.priority_text),
    listName: entities.list_name_text || null, // Default to null if not provided
    status: 'To Do', // Default status
    // notes: entities.notes_text || null, // If NLU provides notes
  };

  const result = await createNotionTaskBackend(userId, params);

  if (result.ok && result.data) {
    let userMessage = `Okay, I've created the task: "${params.description}".`;
    if (params.listName) userMessage += ` on your "${params.listName}" list`;
    if (dueDateISO) userMessage += ` due ${entities.due_date_text || new Date(dueDateISO).toLocaleDateString()}`; // Use original text if available
    if (params.priority) userMessage += ` (Priority: ${params.priority})`;
    userMessage += ".";

    return {
      ok: true,
      data: { ...result.data, userMessage },
    };
  } else {
    return {
      ok: false,
      error: result.error || { code: 'BACKEND_ERROR', message: 'Failed to create task in Notion via backend.' },
      data: { userMessage: `Sorry, I couldn't create the task. ${result.error?.message || 'There was an issue.'}` }
    };
  }
}

// Placeholder for handleQueryNotionTasks
export async function handleQueryNotionTasks(
  userId: string,
  entities: QueryTasksNluEntities,
): Promise<SkillResponse<{ tasks: NotionTask[], userMessage: string }>> {
  logger.info(`[handleQueryNotionTasks] User: ${userId}, Entities: ${JSON.stringify(entities)}`);
   if (!ATOM_NOTION_TASKS_DATABASE_ID) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Notion Tasks Database ID (ATOM_NOTION_TASKS_DATABASE_ID) is not configured.' } };
  }
  // TODO: Implement mapping from NLU entities to QueryNotionTasksParams
  // This includes parsing date_condition_text, mapping priority/status, etc.
  const queryParams: QueryNotionTasksParams = {
      notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
      descriptionContains: entities.description_contains_text || null,
      priority: mapPriority(entities.priority_text),
      status: mapStatus(entities.status_text),
      listName: entities.list_name_text || null,
      limit: entities.limit_number || 10,
      // Date parsing for conditions (dueDateBefore, dueDateAfter) is complex
      // sortBy and sortOrder also need mapping if NLU provides them.
  };

  // Basic date condition parsing
  if (entities.date_condition_text) {
    const now = new Date();
    const todayDateStr = now.toISOString().split('T')[0];

    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate() + 1);
    const tomorrowDateStr = tomorrow.toISOString().split('T')[0];

    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const yesterdayDateStr = yesterday.toISOString().split('T')[0];

    switch (entities.date_condition_text.toLowerCase()) {
      case 'today':
        queryParams.dueDateEquals = todayDateStr; // Python backend needs to support dueDateEquals
        // Or, if only Before/After supported:
        // queryParams.dueDateAfter = todayDateStr;
        // queryParams.dueDateBefore = todayDateStr; // Assuming inclusive, or adjust
        break;
      case 'tomorrow':
        queryParams.dueDateEquals = tomorrowDateStr;
        break;
      case 'yesterday':
        queryParams.dueDateEquals = yesterdayDateStr;
        break;
      case 'overdue':
        queryParams.dueDateBefore = todayDateStr; // Tasks due before today
        if (queryParams.status && queryParams.status !== 'Done') {
            // If status is already specified and not 'Done', it's fine.
            // If status is 'Done', this combination is contradictory.
            // If status is not specified, add not_equals 'Done'.
        } else if (!queryParams.status) {
            queryParams.status_not_equals = 'Done'; // Ensure we don't show completed overdue tasks unless specified
        }
        break;
      // "this week", "next week" would require more complex date range calculations.
      default:
        // Try to parse as a specific date if possible (very basic)
        const specificDate = parseDueDate(entities.date_condition_text);
        if (specificDate) {
            queryParams.dueDateEquals = specificDate.split('T')[0]; // Use YYYY-MM-DD part
        } else {
            logger.warn(`[handleQueryNotionTasks] Could not parse date_condition_text: "${entities.date_condition_text}"`);
        }
    }
  }

  if (entities.sort_by_text) {
      queryParams.sortBy = entities.sort_by_text;
      if (entities.sort_order_text) {
          queryParams.sortOrder = entities.sort_order_text;
      }
  }

  // logger.warn("[handleQueryNotionTasks] Date condition parsing and sorting not fully implemented yet.");


  const result = await queryNotionTasksBackend(userId, queryParams);

  if (result.success && result.tasks) {
    let userMessage = "";
    if (result.tasks.length === 0) {
      userMessage = "I couldn't find any tasks matching your criteria.";
    } else {
      userMessage = `Here are the tasks I found:\n`;
      result.tasks.forEach((task, index) => {
        userMessage += `${index + 1}. ${task.description}`;
        if (task.dueDate) userMessage += ` (Due: ${new Date(task.dueDate).toLocaleDateString()})`;
        if (task.priority) userMessage += ` [P: ${task.priority}]`;
        if (task.listName) userMessage += ` (List: ${task.listName})`;
        if (task.status) userMessage += ` (Status: ${task.status})`;
        userMessage += `\n`;
      });
    }
    return { ok: true, data: { tasks: result.tasks, userMessage } };
  } else {
    return {
        ok: false,
        error: { code: 'BACKEND_ERROR', message: result.error || 'Failed to query tasks.' },
        data: { tasks: [], userMessage: `Sorry, I couldn't fetch tasks. ${result.error || 'There was an issue.'}`}
    };
  }
}

// Placeholder for handleUpdateNotionTask
export async function handleUpdateNotionTask(
  userId: string,
  entities: UpdateTaskNluEntities,
): Promise<SkillResponse<UpdateTaskData & { userMessage: string }>> {
  logger.info(`[handleUpdateNotionTask] User: ${userId}, Entities: ${JSON.stringify(entities)}`);
  if (!ATOM_NOTION_TASKS_DATABASE_ID) {
    // While not strictly needed for update by ID, good to have for context or if task resolution queries this DB.
    logger.warn("[handleUpdateNotionTask] ATOM_NOTION_TASKS_DATABASE_ID not configured, might affect task resolution.");
  }

  // --- Task Resolution (Complex Step - V1: Basic name matching) ---
  // This needs to be robust. For V1, we might try a simple query.
  // A better approach involves NLU providing a task_id or the agent maintaining context.
  let taskIdToUpdate: string | null = null;

  if (entities.task_identifier_text) {
    logger.info(`[handleUpdateNotionTask] Attempting to resolve task by identifier: "${entities.task_identifier_text}"`);
    const potentialTasks = await queryNotionTasksBackend(userId, {
      notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID!, // Assume it's configured for this flow
      descriptionContains: entities.task_identifier_text,
      status_not_equals: "Done", // Prefer to update active tasks
      limit: 5, // Fetch a few to check for ambiguity
    });

    if (potentialTasks.success && potentialTasks.tasks.length === 1) {
      taskIdToUpdate = potentialTasks.tasks[0].id;
      logger.info(`[handleUpdateNotionTask] Resolved to task ID: ${taskIdToUpdate}`);
    } else if (potentialTasks.success && potentialTasks.tasks.length > 1) {
      // TODO: Implement disambiguation: Ask user which task they meant.
      const options = potentialTasks.tasks.map((t, i) => `${i+1}. ${t.description} (List: ${t.listName || 'N/A'})`).join('\n');
      const userMessage = `I found a few tasks matching "${entities.task_identifier_text}". Which one did you mean?\n${options}`;
      logger.warn(`[handleUpdateNotionTask] Multiple tasks found for "${entities.task_identifier_text}". Disambiguation needed.`);
      return { ok: false, error: { code: 'AMBIGUOUS_TASK', message: userMessage }, data: { userMessage } as any };

    } else {
      logger.warn(`[handleUpdateNotionTask] Could not find a unique task matching "${entities.task_identifier_text}".`);
      return { ok: false, error: { code: 'TASK_NOT_FOUND', message: `I couldn't find a task matching "${entities.task_identifier_text}".` }, data: { userMessage: `I couldn't find a task matching "${entities.task_identifier_text}".`} as any };
    }
  } else {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Task identifier is required to update a task.' } };
  }
  // --- End Task Resolution ---

  const newDueDateISO = parseDueDate(entities.new_due_date_text);
  if (entities.new_due_date_text && !newDueDateISO) {
      logger.warn(`[handleUpdateNotionTask] New due date text "${entities.new_due_date_text}" provided but could not be parsed.`);
  }


  const params: UpdateNotionTaskParams = {
    taskId: taskIdToUpdate!, // Asserting it's non-null after resolution logic
    description: entities.new_description_text,
    dueDate: newDueDateISO,
    status: mapStatus(entities.new_status_text),
    priority: mapPriority(entities.new_priority_text),
    listName: entities.new_list_name_text,
  };

  // Filter out undefined params so only provided fields are updated
  const filteredParams = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined)) as UpdateNotionTaskParams;
  if (Object.keys(filteredParams).length <= 1 && filteredParams.taskId) { // Only taskId means no actual updates
     return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'No properties provided to update for the task.' } };
  }


  const result = await updateNotionTaskBackend(userId, filteredParams);

  if (result.ok && result.data) {
    const userMessage = `Okay, I've updated the task (ID: ${result.data.taskId}). Properties changed: ${result.data.updatedProperties.join(', ')}.`;
    return {
      ok: true,
      data: { ...result.data, userMessage },
    };
  } else {
    return {
      ok: false,
      error: result.error || { code: 'BACKEND_ERROR', message: 'Failed to update task in Notion via backend.' },
      data: { userMessage: `Sorry, I couldn't update the task. ${result.error?.message || 'There was an issue.'}` }
    };
  }
}

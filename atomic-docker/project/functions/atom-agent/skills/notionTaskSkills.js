import { createNotionTask as createNotionTaskBackend, queryNotionTasks as queryNotionTasksBackend, updateNotionTask as updateNotionTaskBackend, } from './notionAndResearchSkills'; // Assuming these are the backend callers
import { ATOM_NOTION_TASKS_DATABASE_ID } from '../_libs/constants';
import { logger } from '../../_utils/logger';
// --- Date Parsing (Simplified - Placeholder) ---
// A more robust library like date-fns, dayjs, or chrono-node would be needed for real-world parsing.
// NLU should ideally provide structured date objects.
function parseDueDate(dateText) {
    if (!dateText)
        return null;
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
function mapPriority(priorityText) {
    if (!priorityText)
        return null;
    const lowerPriority = priorityText.toLowerCase();
    if (lowerPriority.includes('high'))
        return 'High';
    if (lowerPriority.includes('medium') || lowerPriority.includes('med'))
        return 'Medium';
    if (lowerPriority.includes('low'))
        return 'Low';
    return null;
}
function mapStatus(statusText) {
    if (!statusText)
        return null;
    const lowerStatus = statusText.toLowerCase();
    if (lowerStatus.includes('to do') || lowerStatus.includes('todo'))
        return 'To Do';
    if (lowerStatus.includes('in progress') || lowerStatus.includes('doing'))
        return 'In Progress';
    if (lowerStatus.includes('done') || lowerStatus.includes('completed'))
        return 'Done';
    if (lowerStatus.includes('blocked'))
        return 'Blocked';
    if (lowerStatus.includes('cancelled') || lowerStatus.includes('canceled'))
        return 'Cancelled';
    return null;
}
// --- Skill Implementations ---
export async function handleCreateNotionTask(userId, entities, integrations) {
    logger.info(`[handleCreateNotionTask] User: ${userId}, Entities: ${JSON.stringify(entities)}`);
    if (!ATOM_NOTION_TASKS_DATABASE_ID) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Notion Tasks Database ID (ATOM_NOTION_TASKS_DATABASE_ID) is not configured.',
            },
        };
    }
    if (!entities.task_description) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Task description is required.',
            },
        };
    }
    const dueDateISO = parseDueDate(entities.due_date_text);
    // If dueDateISO is null and entities.due_date_text was provided, it means parsing failed.
    // Depending on strictness, you might return an error here or proceed without a due date.
    if (entities.due_date_text && !dueDateISO) {
        logger.warn(`[handleCreateNotionTask] Due date text "${entities.due_date_text}" provided but could not be parsed.`);
        // Optionally, inform the user: `Could not understand the due date "${entities.due_date_text}". Task created without it.`
    }
    const params = {
        notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
        description: entities.task_description,
        dueDate: dueDateISO, // Use parsed date
        priority: mapPriority(entities.priority_text),
        listName: entities.list_name_text || null, // Default to null if not provided
        status: 'To Do', // Default status
        // notes: entities.notes_text || null, // If NLU provides notes
    };
    const result = await createNotionTaskBackend(userId, params, integrations);
    if (result.ok && result.data) {
        let userMessage = `Okay, I've created the task: "${params.description}".`;
        if (params.listName)
            userMessage += ` on your "${params.listName}" list`;
        if (dueDateISO)
            userMessage += ` due ${entities.due_date_text || new Date(dueDateISO).toLocaleDateString()}`; // Use original text if available
        if (params.priority)
            userMessage += ` (Priority: ${params.priority})`;
        userMessage += '.';
        return {
            ok: true,
            data: { ...result.data, userMessage },
        };
    }
    else {
        return {
            ok: false,
            error: result.error || {
                code: 'BACKEND_ERROR',
                message: 'Failed to create task in Notion via backend.',
            },
            data: {
                userMessage: `Sorry, I couldn't create the task. ${result.error?.message || 'There was an issue.'}`,
            },
        };
    }
}
export async function handleSetTaskReminder(userId, entities) {
    logger.info(`[handleSetTaskReminder] User: ${userId}, Entities: ${JSON.stringify(entities)}`);
    if (!entities.task_identifier_text) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Task identifier is required to set a reminder.',
            },
        };
    }
    if (!entities.reminder_date_text) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Reminder date is required to set a reminder.',
            },
        };
    }
    // 1. Resolve Task
    let taskIdToUpdate = null;
    if (entities.task_identifier_text) {
        const potentialTasks = await queryNotionTasksBackend(userId, {
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
            descriptionContains: entities.task_identifier_text,
            status_not_equals: 'Done',
            limit: 5,
        });
        if (potentialTasks.success && potentialTasks.tasks.length === 1) {
            taskIdToUpdate = potentialTasks.tasks[0].id;
        }
        else {
            const errorMessage = potentialTasks.tasks.length > 1
                ? `I found multiple tasks matching "${entities.task_identifier_text}". Please be more specific.`
                : `I couldn't find a task matching "${entities.task_identifier_text}".`;
            return {
                ok: false,
                error: { code: 'TASK_NOT_FOUND', message: errorMessage },
            };
        }
    }
    // 2. Parse Reminder Date
    const reminderDate = parseDueDate(entities.reminder_date_text);
    if (!reminderDate) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: `I couldn't understand the reminder date "${entities.reminder_date_text}".`,
            },
        };
    }
    // 3. Schedule Reminder
    try {
        const { agenda } = await import('../../agendaService');
        await agenda.schedule(reminderDate, 'send task reminder', {
            userId,
            taskId: taskIdToUpdate,
            taskDescription: entities.task_identifier_text,
        });
        const userMessage = `Okay, I've set a reminder for the task "${entities.task_identifier_text}" on ${new Date(reminderDate).toLocaleString()}.`;
        return { ok: true, data: { userMessage } };
    }
    catch (error) {
        return {
            ok: false,
            error: {
                code: 'SCHEDULING_ERROR',
                message: 'Failed to schedule reminder.',
            },
        };
    }
}
// Placeholder for handleQueryNotionTasks
export async function handleQueryNotionTasks(userId, entities) {
    logger.info(`[handleQueryNotionTasks] User: ${userId}, Entities: ${JSON.stringify(entities)}`);
    if (!ATOM_NOTION_TASKS_DATABASE_ID) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Notion Tasks Database ID (ATOM_NOTION_TASKS_DATABASE_ID) is not configured.',
            },
        };
    }
    // TODO: Implement mapping from NLU entities to QueryNotionTasksParams
    // This includes parsing date_condition_text, mapping priority/status, etc.
    const queryParams = {
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
                }
                else if (!queryParams.status) {
                    queryParams.status_not_equals = 'Done'; // Ensure we don't show completed overdue tasks unless specified
                }
                break;
            // "this week", "next week" would require more complex date range calculations.
            default:
                // Try to parse as a specific date if possible (very basic)
                const specificDate = parseDueDate(entities.date_condition_text);
                if (specificDate) {
                    queryParams.dueDateEquals = specificDate.split('T')[0]; // Use YYYY-MM-DD part
                }
                else {
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
        let userMessage = '';
        if (result.tasks.length === 0) {
            userMessage = "I couldn't find any tasks matching your criteria.";
        }
        else {
            userMessage = `Here are the tasks I found:\n`;
            result.tasks.forEach((task, index) => {
                userMessage += `${index + 1}. ${task.description}`;
                if (task.dueDate)
                    userMessage += ` (Due: ${new Date(task.dueDate).toLocaleDateString()})`;
                if (task.priority)
                    userMessage += ` [P: ${task.priority}]`;
                if (task.listName)
                    userMessage += ` (List: ${task.listName})`;
                if (task.status)
                    userMessage += ` (Status: ${task.status})`;
                userMessage += `\n`;
            });
        }
        return { ok: true, data: { tasks: result.tasks, userMessage } };
    }
    else {
        return {
            ok: false,
            error: {
                code: 'BACKEND_ERROR',
                message: result.error || 'Failed to query tasks.',
            },
            data: {
                tasks: [],
                userMessage: `Sorry, I couldn't fetch tasks. ${result.error || 'There was an issue.'}`,
            },
        };
    }
}
// Placeholder for handleUpdateNotionTask
export async function handleUpdateNotionTask(userId, entities) {
    logger.info(`[handleUpdateNotionTask] User: ${userId}, Entities: ${JSON.stringify(entities)}`);
    if (!ATOM_NOTION_TASKS_DATABASE_ID) {
        // While not strictly needed for update by ID, good to have for context or if task resolution queries this DB.
        logger.warn('[handleUpdateNotionTask] ATOM_NOTION_TASKS_DATABASE_ID not configured, might affect task resolution.');
    }
    // --- Task Resolution (Complex Step - V1: Basic name matching) ---
    // This needs to be robust. For V1, we might try a simple query.
    // A better approach involves NLU providing a task_id or the agent maintaining context.
    let taskIdToUpdate = null;
    if (entities.task_identifier_text) {
        logger.info(`[handleUpdateNotionTask] Attempting to resolve task by identifier: "${entities.task_identifier_text}"`);
        const potentialTasks = await queryNotionTasksBackend(userId, {
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID, // Assume it's configured for this flow
            descriptionContains: entities.task_identifier_text,
            status_not_equals: 'Done', // Prefer to update active tasks
            limit: 5, // Fetch a few to check for ambiguity
        });
        if (potentialTasks.success && potentialTasks.tasks.length === 1) {
            taskIdToUpdate = potentialTasks.tasks[0].id;
            logger.info(`[handleUpdateNotionTask] Resolved to task ID: ${taskIdToUpdate}`);
        }
        else if (potentialTasks.success && potentialTasks.tasks.length > 1) {
            // TODO: Implement disambiguation: Ask user which task they meant.
            const options = potentialTasks.tasks
                .map((t, i) => `${i + 1}. ${t.description} (List: ${t.listName || 'N/A'})`)
                .join('\n');
            const userMessage = `I found a few tasks matching "${entities.task_identifier_text}". Which one did you mean?\n${options}`;
            logger.warn(`[handleUpdateNotionTask] Multiple tasks found for "${entities.task_identifier_text}". Disambiguation needed.`);
            return {
                ok: false,
                error: { code: 'AMBIGUOUS_TASK', message: userMessage },
                data: { userMessage },
            };
        }
        else {
            logger.warn(`[handleUpdateNotionTask] Could not find a unique task matching "${entities.task_identifier_text}".`);
            return {
                ok: false,
                error: {
                    code: 'TASK_NOT_FOUND',
                    message: `I couldn't find a task matching "${entities.task_identifier_text}".`,
                },
                data: {
                    userMessage: `I couldn't find a task matching "${entities.task_identifier_text}".`,
                },
            };
        }
    }
    else {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Task identifier is required to update a task.',
            },
        };
    }
    // --- End Task Resolution ---
    const newDueDateISO = parseDueDate(entities.new_due_date_text);
    if (entities.new_due_date_text && !newDueDateISO) {
        logger.warn(`[handleUpdateNotionTask] New due date text "${entities.new_due_date_text}" provided but could not be parsed.`);
    }
    const params = {
        taskId: taskIdToUpdate, // Asserting it's non-null after resolution logic
        description: entities.new_description_text,
        dueDate: newDueDateISO,
        status: mapStatus(entities.new_status_text),
        priority: mapPriority(entities.new_priority_text),
        listName: entities.new_list_name_text,
    };
    // Filter out undefined params so only provided fields are updated
    const filteredParams = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined));
    if (Object.keys(filteredParams).length <= 1 && filteredParams.taskId) {
        // Only taskId means no actual updates
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'No properties provided to update for the task.',
            },
        };
    }
    const result = await updateNotionTaskBackend(userId, filteredParams);
    if (result.ok && result.data) {
        const userMessage = `Okay, I've updated the task (ID: ${result.data.taskId}). Properties changed: ${result.data.updatedProperties.join(', ')}.`;
        return {
            ok: true,
            data: { ...result.data, userMessage },
        };
    }
    else {
        return {
            ok: false,
            error: result.error || {
                code: 'BACKEND_ERROR',
                message: 'Failed to update task in Notion via backend.',
            },
            data: {
                userMessage: `Sorry, I couldn't update the task. ${result.error?.message || 'There was an issue.'}`,
            },
        };
    }
}
export async function handleAddSubtask(userId, entities) {
    logger.info(`[handleAddSubtask] User: ${userId}, Entities: ${JSON.stringify(entities)}`);
    if (!ATOM_NOTION_TASKS_DATABASE_ID) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Notion Tasks Database ID (ATOM_NOTION_TASKS_DATABASE_ID) is not configured.',
            },
        };
    }
    // 1. Resolve Parent Task
    let parentTaskId = null;
    if (entities.parent_task_identifier_text) {
        const potentialTasks = await queryNotionTasksBackend(userId, {
            notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
            descriptionContains: entities.parent_task_identifier_text,
            status_not_equals: 'Done',
            limit: 5,
        });
        if (potentialTasks.success && potentialTasks.tasks.length === 1) {
            parentTaskId = potentialTasks.tasks[0].id;
        }
        else {
            // Handle ambiguous or not found parent task
            const errorMessage = potentialTasks.tasks.length > 1
                ? `I found multiple tasks matching "${entities.parent_task_identifier_text}". Please be more specific.`
                : `I couldn't find a parent task matching "${entities.parent_task_identifier_text}".`;
            return {
                ok: false,
                error: { code: 'PARENT_TASK_NOT_FOUND', message: errorMessage },
            };
        }
    }
    else {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Parent task identifier is required to add a sub-task.',
            },
        };
    }
    // 2. Create Sub-task
    const params = {
        notionTasksDbId: ATOM_NOTION_TASKS_DATABASE_ID,
        description: entities.sub_task_description,
        status: 'To Do',
        parentId: parentTaskId,
    };
    const result = await createNotionTaskBackend(userId, params, integrations);
    if (result.ok && result.data) {
        const userMessage = `Okay, I've added "${entities.sub_task_description}" as a sub-task.`;
        return {
            ok: true,
            data: { ...result.data, userMessage },
        };
    }
    else {
        return {
            ok: false,
            error: result.error || {
                code: 'BACKEND_ERROR',
                message: 'Failed to create sub-task in Notion.',
            },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibm90aW9uVGFza1NraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm5vdGlvblRhc2tTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBZUEsT0FBTyxFQUNMLGdCQUFnQixJQUFJLHVCQUF1QixFQUMzQyxnQkFBZ0IsSUFBSSx1QkFBdUIsRUFDM0MsZ0JBQWdCLElBQUksdUJBQXVCLEdBQzVDLE1BQU0sMkJBQTJCLENBQUMsQ0FBQyx5Q0FBeUM7QUFFN0UsT0FBTyxFQUFFLDZCQUE2QixFQUFFLE1BQU0sb0JBQW9CLENBQUM7QUFDbkUsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBb0M3QyxrREFBa0Q7QUFDbEQscUdBQXFHO0FBQ3JHLHNEQUFzRDtBQUN0RCxTQUFTLFlBQVksQ0FBQyxRQUFpQjtJQUNyQyxJQUFJLENBQUMsUUFBUTtRQUFFLE9BQU8sSUFBSSxDQUFDO0lBRTNCLGlEQUFpRDtJQUNqRCxJQUFJLFFBQVEsQ0FBQyxXQUFXLEVBQUUsS0FBSyxPQUFPLEVBQUUsQ0FBQztRQUN2QyxPQUFPLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFLENBQUMsS0FBSyxDQUFDLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsYUFBYTtJQUM5RCxDQUFDO0lBQ0QsSUFBSSxRQUFRLENBQUMsV0FBVyxFQUFFLEtBQUssVUFBVSxFQUFFLENBQUM7UUFDMUMsTUFBTSxRQUFRLEdBQUcsSUFBSSxJQUFJLEVBQUUsQ0FBQztRQUM1QixRQUFRLENBQUMsT0FBTyxDQUFDLFFBQVEsQ0FBQyxPQUFPLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQztRQUN6QyxPQUFPLFFBQVEsQ0FBQyxXQUFXLEVBQUUsQ0FBQyxLQUFLLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxhQUFhO0lBQzVELENBQUM7SUFDRCw4Q0FBOEM7SUFDOUMsTUFBTSxNQUFNLEdBQUcsSUFBSSxDQUFDLEtB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SztnQkFDVCxLQUFLLEVBQUUsRUFBRSxJQUFJLEVBQUUsdUJBQXVCLEVBQUUsT0FBTyxFQUFFLFlBQVksRUFBRTthQUNoRSxDQUFDO1FBQ0osQ0FBQztJQUNILENBQUM7U0FBTSxDQUFDO1FBQ04sT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxrQkFBa0I7Z0JBQ3hCLE9BQU8sRUFBRSx1REFBdUQ7YUFDakU7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVELHFCQUFxQjtJQUNyQixNQUFNLE1BQU0sR0FBMkI7UUFDckMsZUFBZSxFQUFFLDZCQUE2QjtRQUM5QyxXQUFXLEVBQUUsUUFBUSxDQUFDLG9CQUFvQjtRQUMxQyxNQUFNLEVBQUUsT0FBTztRQUNmLFFBQVEsRUFBRSxZQUFZO0tBQ3ZCLENBQUM7SUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLHVCQUF1QixDQUFDLE1BQU0sRUFBRSxNQUFNLEVBQUUsWUFBWSxDQUFDLENBQUM7SUFFM0UsSUFBSSxNQUFNLENBQUMsRUFBRSxJQUFJLE1BQU0sQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUM3QixNQUFNLFdBQVcsR0FBRyxxQkFBcUIsUUFBUSxDQUFDLG9CQUFvQixrQkFBa0IsQ0FBQztRQUN6RixPQUFPO1lBQ0wsRUFBRSxFQUFFLElBQUk7WUFDUixJQUFJLEVBQUUsRUFBRSxHQUFHLE1BQU0sQ0FBQyxJQUFJLEVBQUUsV0FBVyxFQUFFO1NBQ3RDLENBQUM7SUFDSixDQUFDO1NBQU0sQ0FBQztRQUNOLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRSxNQUFNLENBQUMsS0FBSyxJQUFJO2dCQUNyQixJQUFJLEVBQUUsZUFBZTtnQkFDckIsT0FBTyxFQUFFLHNDQUFzQzthQUNoRDtTQUNGLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFNraWxsUmVzcG9uc2UsXG4gIE5vdGlvblRhc2ssXG4gIENyZWF0ZU5vdGlvblRhc2tQYXJhbXMsXG4gIFF1ZXJ5Tm90aW9uVGFza3NQYXJhbXMsXG4gIFVwZGF0ZU5vdGlvblRhc2tQYXJhbXMsXG4gIENyZWF0ZVRhc2tEYXRhLFxuICBVcGRhdGVUYXNrRGF0YSxcbiAgVGFza1F1ZXJ5UmVzcG9uc2UsXG4gIE5vdGlvblRhc2tTdGF0dXMsXG4gIE5vdGlvblRhc2tQcmlvcml0eSxcbiAgLy8gQ29uY2VwdHVhbCBOTFUgZW50aXR5IHR5cGVzIChhc3N1bWluZyB0aGV5J2QgYmUgZGVmaW5lZCBpbiB0eXBlcy50cyBvciBhIGRlZGljYXRlZCBubHVUeXBlcy50cylcbiAgLy8gRm9yIG5vdywgd2UnbGwgZGVmaW5lIHNpbXBsZSBpbnRlcmZhY2VzIGhlcmUgb3IgdXNlICdhbnknIGZvciBOTFUgaW5wdXQgc3RydWN0dXJlLlxufSBmcm9tICcuLi90eXBlcyc7XG5cbmltcG9ydCB7XG4gIGNyZWF0ZU5vdGlvblRhc2sgYXMgY3JlYXRlTm90aW9uVGFza0JhY2tlbmQsXG4gIHF1ZXJ5Tm90aW9uVGFza3MgYXMgcXVlcnlOb3Rpb25UYXNrc0JhY2tlbmQsXG4gIHVwZGF0ZU5vdGlvblRhc2sgYXMgdXBkYXRlTm90aW9uVGFza0JhY2tlbmQsXG59IGZyb20gJy4vbm90aW9uQW5kUmVzZWFyY2hTa2lsbHMnOyAvLyBBc3N1bWluZyB0aGVzZSBhcmUgdGhlIGJhY2tlbmQgY2FsbGVyc1xuXG5pbXBvcnQgeyBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCB9IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9fdXRpbHMvbG9nZ2VyJztcblxuLy8gLS0tIE5MVSBFbnRpdHkgSW50ZXJmYWNlcyAoQ29uY2VwdHVhbCAtIGRlZmluZSBtb3JlIGZvcm1hbGx5IGluIHR5cGVzLnRzIGxhdGVyKSAtLS1cbmludGVyZmFjZSBDcmVhdGVUYXNrTmx1RW50aXRpZXMge1xuICB0YXNrX2Rlc2NyaXB0aW9uOiBzdHJpbmc7XG4gIGR1ZV9kYXRlX3RleHQ/OiBzdHJpbmc7XG4gIHByaW9yaXR5X3RleHQ/OiBzdHJpbmc7XG4gIGxpc3RfbmFtZV90ZXh0Pzogc3RyaW5nO1xuICAvLyBub3Rlc190ZXh0Pzogc3RyaW5nOyAvLyBJZiBOTFUgY2FuIHBpY2sgdXAgYWRkaXRpb25hbCBub3Rlc1xufVxuXG5pbnRlcmZhY2UgUXVlcnlUYXNrc05sdUVudGl0aWVzIHtcbiAgZGF0ZV9jb25kaXRpb25fdGV4dD86IHN0cmluZztcbiAgcHJpb3JpdHlfdGV4dD86IHN0cmluZztcbiAgbGlzdF9uYW1lX3RleHQ/OiBzdHJpbmc7XG4gIHN0YXR1c190ZXh0Pzogc3RyaW5nO1xuICBkZXNjcmlwdGlvbl9jb250YWluc190ZXh0Pzogc3RyaW5nO1xuICBzb3J0X2J5X3RleHQ/OiAnZHVlRGF0ZScgfCAncHJpb3JpdHknIHwgJ2NyZWF0ZWREYXRlJzsgLy8gTWF0Y2ggTm90aW9uVGFzayBwcm9wZXJ0aWVzXG4gIHNvcnRfb3JkZXJfdGV4dD86ICdhc2NlbmRpbmcnIHwgJ2Rlc2NlbmRpbmcnO1xuICBsaW1pdF9udW1iZXI/OiBudW1iZXI7XG59XG5cbmludGVyZmFjZSBVcGRhdGVUYXNrTmx1RW50aXRpZXMge1xuICB0YXNrX2lkZW50aWZpZXJfdGV4dDogc3RyaW5nOyAvLyBUZXh0IHRvIGhlbHAgaWRlbnRpZnkgdGhlIHRhc2tcbiAgbmV3X3N0YXR1c190ZXh0Pzogc3RyaW5nO1xuICBuZXdfZHVlX2RhdGVfdGV4dD86IHN0cmluZztcbiAgbmV3X3ByaW9yaXR5X3RleHQ/OiBzdHJpbmc7XG4gIG5ld19saXN0X25hbWVfdGV4dD86IHN0cmluZztcbiAgbmV3X2Rlc2NyaXB0aW9uX3RleHQ/OiBzdHJpbmc7XG59XG5cbmludGVyZmFjZSBTZXRUYXNrUmVtaW5kZXJObHVFbnRpdGllcyB7XG4gIHRhc2tfaWRlbnRpZmllcl90ZXh0OiBzdHJpbmc7XG4gIHJlbWluZGVyX2RhdGVfdGV4dDogc3RyaW5nO1xufVxuXG4vLyAtLS0gRGF0ZSBQYXJzaW5nIChTaW1wbGlmaWVkIC0gUGxhY2Vob2xkZXIpIC0tLVxuLy8gQSBtb3JlIHJvYnVzdCBsaWJyYXJ5IGxpa2UgZGF0ZS1mbnMsIGRheWpzLCBvciBjaHJvbm8tbm9kZSB3b3VsZCBiZSBuZWVkZWQgZm9yIHJlYWwtd29ybGQgcGFyc2luZy5cbi8vIE5MVSBzaG91bGQgaWRlYWxseSBwcm92aWRlIHN0cnVjdHVyZWQgZGF0ZSBvYmplY3RzLlxuZnVuY3Rpb24gcGFyc2VEdWVEYXRlKGRhdGVUZXh0Pzogc3RyaW5nKTogc3RyaW5nIHwgbnVsbCB7XG4gIGlmICghZGF0ZVRleHQpIHJldHVybiBudWxsO1xuXG4gIC8vIEV4dHJlbWVseSBiYXNpYyBleGFtcGxlcywgTk9UIHByb2R1Y3Rpb24tcmVhZHlcbiAgaWYgKGRhdGVUZXh0LnRvTG93ZXJDYXNlKCkgPT09ICd0b2RheScpIHtcbiAgICByZXR1cm4gbmV3IERhdGUoKS50b0lTT1N0cmluZygpLnNwbGl0KCdUJylbMF07IC8vIFlZWVktTU0tRERcbiAgfVxuICBpZiAoZGF0ZVRleHQudG9Mb3dlckNhc2UoKSA9PT0gJ3RvbW9ycm93Jykge1xuICAgIGNvbnN0IHRvbW9ycm93ID0gbmV3IERhdGUoKTtcbiAgICB0b21vcnJvdy5zZXREYXRlKHRvbW9ycm93LmdldERhdGUoKSArIDEpO1xuICAgIHJldHVybiB0b21vcnJvdy50b0lTT1N0cmluZygpLnNwbGl0KCdUJylbMF07IC8vIFlZWVktTU0tRERcbiAgfVxuICAvLyBUcnkgdG8gcGFyc2Ugd2l0aCBEYXRlLnBhcnNlIC0gdmVyeSBsaW1pdGVkXG4gIGNvbnN0IHBhcnNlZCA9IERhdGUucGFyc2UoZGF0ZVRleHQpO1xuICBpZiAoIWlzTmFOKHBhcnNlZCkpIHtcbiAgICByZXR1cm4gbmV3IERhdGUocGFyc2VkKS50b0lTT1N0cmluZygpOyAvLyBGdWxsIElTTyBzdHJpbmcsIE5vdGlvbiBBUEkgbWlnaHQgcHJlZmVyIFlZWVktTU0tREQgZm9yIGRhdGUtb25seVxuICB9XG4gIGxvZ2dlci53YXJuKFxuICAgIGBbbm90aW9uVGFza1NraWxsc10gQ291bGQgbm90IHBhcnNlIGR1ZSBkYXRlOiBcIiR7ZGF0ZVRleHR9XCIuIE5lZWRzIHJvYnVzdCBwYXJzaW5nLmBcbiAgKTtcbiAgcmV0dXJuIG51bGw7IC8vIEluZGljYXRlIHBhcnNpbmcgZmFpbHVyZVxufVxuXG4vLyAtLS0gVmFsdWUgTWFwcGluZyAtLS1cbmZ1bmN0aW9uIG1hcFByaW9yaXR5KHByaW9yaXR5VGV4dD86IHN0cmluZyk6IE5vdGlvblRhc2tQcmlvcml0eSB8IG51bGwge1xuICBpZiAoIXByaW9yaXR5VGV4dCkgcmV0dXJuIG51bGw7XG4gIGNvbnN0IGxvd2VyUHJpb3JpdHkgPSBwcmlvcml0eVRleHQudG9Mb3dlckNhc2UoKTtcbiAgaWYgKGxvd2VyUHJpb3JpdHkuaW5jbHVkZXMoJ2hpZ2gnKSkgcmV0dXJuICdIaWdoJztcbiAgaWYgKGxvd2VyUHJpb3JpdHkuaW5jbHVkZXMoJ21lZGl1bScpIHx8IGxvd2VyUHJpb3JpdHkuaW5jbHVkZXMoJ21lZCcpKVxuICAgIHJldHVybiAnTWVkaXVtJztcbiAgaWYgKGxvd2VyUHJpb3JpdHkuaW5jbHVkZXMoJ2xvdycpKSByZXR1cm4gJ0xvdyc7XG4gIHJldHVybiBudWxsO1xufVxuXG5mdW5jdGlvbiBtYXBTdGF0dXMoc3RhdHVzVGV4dD86IHN0cmluZyk6IE5vdGlvblRhc2tTdGF0dXMgfCBudWxsIHtcbiAgaWYgKCFzdGF0dXNUZXh0KSByZXR1cm4gbnVsbDtcbiAgY29uc3QgbG93ZXJTdGF0dXMgPSBzdGF0dXNUZXh0LnRvTG93ZXJDYXNlKCk7XG4gIGlmIChsb3dlclN0YXR1cy5pbmNsdWRlcygndG8gZG8nKSB8fCBsb3dlclN0YXR1cy5pbmNsdWRlcygndG9kbycpKVxuICAgIHJldHVybiAnVG8gRG8nO1xuICBpZiAobG93ZXJTdGF0dXMuaW5jbHVkZXMoJ2luIHByb2dyZXNzJykgfHwgbG93ZXJTdGF0dXMuaW5jbHVkZXMoJ2RvaW5nJykpXG4gICAgcmV0dXJuICdJbiBQcm9ncmVzcyc7XG4gIGlmIChsb3dlclN0YXR1cy5pbmNsdWRlcygnZG9uZScpIHx8IGxvd2VyU3RhdHVzLmluY2x1ZGVzKCdjb21wbGV0ZWQnKSlcbiAgICByZXR1cm4gJ0RvbmUnO1xuICBpZiAobG93ZXJTdGF0dXMuaW5jbHVkZXMoJ2Jsb2NrZWQnKSkgcmV0dXJuICdCbG9ja2VkJztcbiAgaWYgKGxvd2VyU3RhdHVzLmluY2x1ZGVzKCdjYW5jZWxsZWQnKSB8fCBsb3dlclN0YXR1cy5pbmNsdWRlcygnY2FuY2VsZWQnKSlcbiAgICByZXR1cm4gJ0NhbmNlbGxlZCc7XG4gIHJldHVybiBudWxsO1xufVxuXG4vLyAtLS0gU2tpbGwgSW1wbGVtZW50YXRpb25zIC0tLVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlQ3JlYXRlTm90aW9uVGFzayhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBDcmVhdGVUYXNrTmx1RW50aXRpZXMsXG4gIGludGVncmF0aW9uczogYW55XG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8Q3JlYXRlVGFza0RhdGEgJiB7IHVzZXJNZXNzYWdlOiBzdHJpbmcgfT4+IHtcbiAgbG9nZ2VyLmluZm8oXG4gICAgYFtoYW5kbGVDcmVhdGVOb3Rpb25UYXNrXSBVc2VyOiAke3VzZXJJZH0sIEVudGl0aWVzOiAke0pTT04uc3RyaW5naWZ5KGVudGl0aWVzKX1gXG4gICk7XG5cbiAgaWYgKCFBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAnTm90aW9uIFRhc2tzIERhdGFiYXNlIElEIChBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCkgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBpZiAoIWVudGl0aWVzLnRhc2tfZGVzY3JpcHRpb24pIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnVGFzayBkZXNjcmlwdGlvbiBpcyByZXF1aXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgY29uc3QgZHVlRGF0ZUlTTyA9IHBhcnNlRHVlRGF0ZShlbnRpdGllcy5kdWVfZGF0ZV90ZXh0KTtcbiAgLy8gSWYgZHVlRGF0ZUlTTyBpcyBudWxsIGFuZCBlbnRpdGllcy5kdWVfZGF0ZV90ZXh0IHdhcyBwcm92aWRlZCwgaXQgbWVhbnMgcGFyc2luZyBmYWlsZWQuXG4gIC8vIERlcGVuZGluZyBvbiBzdHJpY3RuZXNzLCB5b3UgbWlnaHQgcmV0dXJuIGFuIGVycm9yIGhlcmUgb3IgcHJvY2VlZCB3aXRob3V0IGEgZHVlIGRhdGUuXG4gIGlmIChlbnRpdGllcy5kdWVfZGF0ZV90ZXh0ICYmICFkdWVEYXRlSVNPKSB7XG4gICAgbG9nZ2VyLndhcm4oXG4gICAgICBgW2hhbmRsZUNyZWF0ZU5vdGlvblRhc2tdIER1ZSBkYXRlIHRleHQgXCIke2VudGl0aWVzLmR1ZV9kYXRlX3RleHR9XCIgcHJvdmlkZWQgYnV0IGNvdWxkIG5vdCBiZSBwYXJzZWQuYFxuICAgICk7XG4gICAgLy8gT3B0aW9uYWxseSwgaW5mb3JtIHRoZSB1c2VyOiBgQ291bGQgbm90IHVuZGVyc3RhbmQgdGhlIGR1ZSBkYXRlIFwiJHtlbnRpdGllcy5kdWVfZGF0ZV90ZXh0fVwiLiBUYXNrIGNyZWF0ZWQgd2l0aG91dCBpdC5gXG4gIH1cblxuICBjb25zdCBwYXJhbXM6IENyZWF0ZU5vdGlvblRhc2tQYXJhbXMgPSB7XG4gICAgbm90aW9uVGFza3NEYklkOiBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCxcbiAgICBkZXNjcmlwdGlvbjogZW50aXRpZXMudGFza19kZXNjcmlwdGlvbixcbiAgICBkdWVEYXRlOiBkdWVEYXRlSVNPLCAvLyBVc2UgcGFyc2VkIGRhdGVcbiAgICBwcmlvcml0eTogbWFwUHJpb3JpdHkoZW50aXRpZXMucHJpb3JpdHlfdGV4dCksXG4gICAgbGlzdE5hbWU6IGVudGl0aWVzLmxpc3RfbmFtZV90ZXh0IHx8IG51bGwsIC8vIERlZmF1bHQgdG8gbnVsbCBpZiBub3QgcHJvdmlkZWRcbiAgICBzdGF0dXM6ICdUbyBEbycsIC8vIERlZmF1bHQgc3RhdHVzXG4gICAgLy8gbm90ZXM6IGVudGl0aWVzLm5vdGVzX3RleHQgfHwgbnVsbCwgLy8gSWYgTkxVIHByb3ZpZGVzIG5vdGVzXG4gIH07XG5cbiAgY29uc3QgcmVzdWx0ID0gYXdhaXQgY3JlYXRlTm90aW9uVGFza0JhY2tlbmQodXNlcklkLCBwYXJhbXMsIGludGVncmF0aW9ucyk7XG5cbiAgaWYgKHJlc3VsdC5vayAmJiByZXN1bHQuZGF0YSkge1xuICAgIGxldCB1c2VyTWVzc2FnZSA9IGBPa2F5LCBJJ3ZlIGNyZWF0ZWQgdGhlIHRhc2s6IFwiJHtwYXJhbXMuZGVzY3JpcHRpb259XCIuYDtcbiAgICBpZiAocGFyYW1zLmxpc3ROYW1lKSB1c2VyTWVzc2FnZSArPSBgIG9uIHlvdXIgXCIke3BhcmFtcy5saXN0TmFtZX1cIiBsaXN0YDtcbiAgICBpZiAoZHVlRGF0ZUlTTylcbiAgICAgIHVzZXJNZXNzYWdlICs9IGAgZHVlICR7ZW50aXRpZXMuZHVlX2RhdGVfdGV4dCB8fCBuZXcgRGF0ZShkdWVEYXRlSVNPKS50b0xvY2FsZURhdGVTdHJpbmcoKX1gOyAvLyBVc2Ugb3JpZ2luYWwgdGV4dCBpZiBhdmFpbGFibGVcbiAgICBpZiAocGFyYW1zLnByaW9yaXR5KSB1c2VyTWVzc2FnZSArPSBgIChQcmlvcml0eTogJHtwYXJhbXMucHJpb3JpdHl9KWA7XG4gICAgdXNlck1lc3NhZ2UgKz0gJy4nO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgZGF0YTogeyAuLi5yZXN1bHQuZGF0YSwgdXNlck1lc3NhZ2UgfSxcbiAgICB9O1xuICB9IGVsc2Uge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogcmVzdWx0LmVycm9yIHx8IHtcbiAgICAgICAgY29kZTogJ0JBQ0tFTkRfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIGNyZWF0ZSB0YXNrIGluIE5vdGlvbiB2aWEgYmFja2VuZC4nLFxuICAgICAgfSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgdXNlck1lc3NhZ2U6IGBTb3JyeSwgSSBjb3VsZG4ndCBjcmVhdGUgdGhlIHRhc2suICR7cmVzdWx0LmVycm9yPy5tZXNzYWdlIHx8ICdUaGVyZSB3YXMgYW4gaXNzdWUuJ31gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVTZXRUYXNrUmVtaW5kZXIoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogU2V0VGFza1JlbWluZGVyTmx1RW50aXRpZXNcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTx7IHVzZXJNZXNzYWdlOiBzdHJpbmcgfT4+IHtcbiAgbG9nZ2VyLmluZm8oXG4gICAgYFtoYW5kbGVTZXRUYXNrUmVtaW5kZXJdIFVzZXI6ICR7dXNlcklkfSwgRW50aXRpZXM6ICR7SlNPTi5zdHJpbmdpZnkoZW50aXRpZXMpfWBcbiAgKTtcblxuICBpZiAoIWVudGl0aWVzLnRhc2tfaWRlbnRpZmllcl90ZXh0KSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1Rhc2sgaWRlbnRpZmllciBpcyByZXF1aXJlZCB0byBzZXQgYSByZW1pbmRlci4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgaWYgKCFlbnRpdGllcy5yZW1pbmRlcl9kYXRlX3RleHQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUmVtaW5kZXIgZGF0ZSBpcyByZXF1aXJlZCB0byBzZXQgYSByZW1pbmRlci4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgLy8gMS4gUmVzb2x2ZSBUYXNrXG4gIGxldCB0YXNrSWRUb1VwZGF0ZTogc3RyaW5nIHwgbnVsbCA9IG51bGw7XG4gIGlmIChlbnRpdGllcy50YXNrX2lkZW50aWZpZXJfdGV4dCkge1xuICAgIGNvbnN0IHBvdGVudGlhbFRhc2tzID0gYXdhaXQgcXVlcnlOb3Rpb25UYXNrc0JhY2tlbmQodXNlcklkLCB7XG4gICAgICBub3Rpb25UYXNrc0RiSWQ6IEFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEISxcbiAgICAgIGRlc2NyaXB0aW9uQ29udGFpbnM6IGVudGl0aWVzLnRhc2tfaWRlbnRpZmllcl90ZXh0LFxuICAgICAgc3RhdHVzX25vdF9lcXVhbHM6ICdEb25lJyxcbiAgICAgIGxpbWl0OiA1LFxuICAgIH0pO1xuXG4gICAgaWYgKHBvdGVudGlhbFRhc2tzLnN1Y2Nlc3MgJiYgcG90ZW50aWFsVGFza3MudGFza3MubGVuZ3RoID09PSAxKSB7XG4gICAgICB0YXNrSWRUb1VwZGF0ZSA9IHBvdGVudGlhbFRhc2tzLnRhc2tzWzBdLmlkO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBlcnJvck1lc3NhZ2UgPVxuICAgICAgICBwb3RlbnRpYWxUYXNrcy50YXNrcy5sZW5ndGggPiAxXG4gICAgICAgICAgPyBgSSBmb3VuZCBtdWx0aXBsZSB0YXNrcyBtYXRjaGluZyBcIiR7ZW50aXRpZXMudGFza19pZGVudGlmaWVyX3RleHR9XCIuIFBsZWFzZSBiZSBtb3JlIHNwZWNpZmljLmBcbiAgICAgICAgICA6IGBJIGNvdWxkbid0IGZpbmQgYSB0YXNrIG1hdGNoaW5nIFwiJHtlbnRpdGllcy50YXNrX2lkZW50aWZpZXJfdGV4dH1cIi5gO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjogeyBjb2RlOiAnVEFTS19OT1RfRk9VTkQnLCBtZXNzYWdlOiBlcnJvck1lc3NhZ2UgfSxcbiAgICAgIH07XG4gICAgfVxuICB9XG5cbiAgLy8gMi4gUGFyc2UgUmVtaW5kZXIgRGF0ZVxuICBjb25zdCByZW1pbmRlckRhdGUgPSBwYXJzZUR1ZURhdGUoZW50aXRpZXMucmVtaW5kZXJfZGF0ZV90ZXh0KTtcbiAgaWYgKCFyZW1pbmRlckRhdGUpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgSSBjb3VsZG4ndCB1bmRlcnN0YW5kIHRoZSByZW1pbmRlciBkYXRlIFwiJHtlbnRpdGllcy5yZW1pbmRlcl9kYXRlX3RleHR9XCIuYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIC8vIDMuIFNjaGVkdWxlIFJlbWluZGVyXG4gIHRyeSB7XG4gICAgY29uc3QgeyBhZ2VuZGEgfSA9IGF3YWl0IGltcG9ydCgnLi4vLi4vYWdlbmRhU2VydmljZScpO1xuICAgIGF3YWl0IGFnZW5kYS5zY2hlZHVsZShyZW1pbmRlckRhdGUsICdzZW5kIHRhc2sgcmVtaW5kZXInLCB7XG4gICAgICB1c2VySWQsXG4gICAgICB0YXNrSWQ6IHRhc2tJZFRvVXBkYXRlLFxuICAgICAgdGFza0Rlc2NyaXB0aW9uOiBlbnRpdGllcy50YXNrX2lkZW50aWZpZXJfdGV4dCxcbiAgICB9KTtcblxuICAgIGNvbnN0IHVzZXJNZXNzYWdlID0gYE9rYXksIEkndmUgc2V0IGEgcmVtaW5kZXIgZm9yIHRoZSB0YXNrIFwiJHtlbnRpdGllcy50YXNrX2lkZW50aWZpZXJfdGV4dH1cIiBvbiAke25ldyBEYXRlKHJlbWluZGVyRGF0ZSkudG9Mb2NhbGVTdHJpbmcoKX0uYDtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyB1c2VyTWVzc2FnZSB9IH07XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdTQ0hFRFVMSU5HX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBzY2hlZHVsZSByZW1pbmRlci4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbi8vIFBsYWNlaG9sZGVyIGZvciBoYW5kbGVRdWVyeU5vdGlvblRhc2tzXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlUXVlcnlOb3Rpb25UYXNrcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBRdWVyeVRhc2tzTmx1RW50aXRpZXNcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTx7IHRhc2tzOiBOb3Rpb25UYXNrW107IHVzZXJNZXNzYWdlOiBzdHJpbmcgfT4+IHtcbiAgbG9nZ2VyLmluZm8oXG4gICAgYFtoYW5kbGVRdWVyeU5vdGlvblRhc2tzXSBVc2VyOiAke3VzZXJJZH0sIEVudGl0aWVzOiAke0pTT04uc3RyaW5naWZ5KGVudGl0aWVzKX1gXG4gICk7XG4gIGlmICghQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgJ05vdGlvbiBUYXNrcyBEYXRhYmFzZSBJRCAoQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQpIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgLy8gVE9ETzogSW1wbGVtZW50IG1hcHBpbmcgZnJvbSBOTFUgZW50aXRpZXMgdG8gUXVlcnlOb3Rpb25UYXNrc1BhcmFtc1xuICAvLyBUaGlzIGluY2x1ZGVzIHBhcnNpbmcgZGF0ZV9jb25kaXRpb25fdGV4dCwgbWFwcGluZyBwcmlvcml0eS9zdGF0dXMsIGV0Yy5cbiAgY29uc3QgcXVlcnlQYXJhbXM6IFF1ZXJ5Tm90aW9uVGFza3NQYXJhbXMgPSB7XG4gICAgbm90aW9uVGFza3NEYklkOiBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCxcbiAgICBkZXNjcmlwdGlvbkNvbnRhaW5zOiBlbnRpdGllcy5kZXNjcmlwdGlvbl9jb250YWluc190ZXh0IHx8IG51bGwsXG4gICAgcHJpb3JpdHk6IG1hcFByaW9yaXR5KGVudGl0aWVzLnByaW9yaXR5X3RleHQpLFxuICAgIHN0YXR1czogbWFwU3RhdHVzKGVudGl0aWVzLnN0YXR1c190ZXh0KSxcbiAgICBsaXN0TmFtZTogZW50aXRpZXMubGlzdF9uYW1lX3RleHQgfHwgbnVsbCxcbiAgICBsaW1pdDogZW50aXRpZXMubGltaXRfbnVtYmVyIHx8IDEwLFxuICAgIC8vIERhdGUgcGFyc2luZyBmb3IgY29uZGl0aW9ucyAoZHVlRGF0ZUJlZm9yZSwgZHVlRGF0ZUFmdGVyKSBpcyBjb21wbGV4XG4gICAgLy8gc29ydEJ5IGFuZCBzb3J0T3JkZXIgYWxzbyBuZWVkIG1hcHBpbmcgaWYgTkxVIHByb3ZpZGVzIHRoZW0uXG4gIH07XG5cbiAgLy8gQmFzaWMgZGF0ZSBjb25kaXRpb24gcGFyc2luZ1xuICBpZiAoZW50aXRpZXMuZGF0ZV9jb25kaXRpb25fdGV4dCkge1xuICAgIGNvbnN0IG5vdyA9IG5ldyBEYXRlKCk7XG4gICAgY29uc3QgdG9kYXlEYXRlU3RyID0gbm93LnRvSVNPU3RyaW5nKCkuc3BsaXQoJ1QnKVswXTtcblxuICAgIGNvbnN0IHRvbW9ycm93ID0gbmV3IERhdGUobm93KTtcbiAgICB0b21vcnJvdy5zZXREYXRlKG5vdy5nZXREYXRlKCkgKyAxKTtcbiAgICBjb25zdCB0b21vcnJvd0RhdGVTdHIgPSB0b21vcnJvdy50b0lTT1N0cmluZygpLnNwbGl0KCdUJylbMF07XG5cbiAgICBjb25zdCB5ZXN0ZXJkYXkgPSBuZXcgRGF0ZShub3cpO1xuICAgIHllc3RlcmRheS5zZXREYXRlKG5vdy5nZXREYXRlKCkgLSAxKTtcbiAgICBjb25zdCB5ZXN0ZXJkYXlEYXRlU3RyID0geWVzdGVyZGF5LnRvSVNPU3RyaW5nKCkuc3BsaXQoJ1QnKVswXTtcblxuICAgIHN3aXRjaCAoZW50aXRpZXMuZGF0ZV9jb25kaXRpb25fdGV4dC50b0xvd2VyQ2FzZSgpKSB7XG4gICAgICBjYXNlICd0b2RheSc6XG4gICAgICAgIHF1ZXJ5UGFyYW1zLmR1ZURhdGVFcXVhbHMgPSB0b2RheURhdGVTdHI7IC8vIFB5dGhvbiBiYWNrZW5kIG5lZWRzIHRvIHN1cHBvcnQgZHVlRGF0ZUVxdWFsc1xuICAgICAgICAvLyBPciwgaWYgb25seSBCZWZvcmUvQWZ0ZXIgc3VwcG9ydGVkOlxuICAgICAgICAvLyBxdWVyeVBhcmFtcy5kdWVEYXRlQWZ0ZXIgPSB0b2RheURhdGVTdHI7XG4gICAgICAgIC8vIHF1ZXJ5UGFyYW1zLmR1ZURhdGVCZWZvcmUgPSB0b2RheURhdGVTdHI7IC8vIEFzc3VtaW5nIGluY2x1c2l2ZSwgb3IgYWRqdXN0XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAndG9tb3Jyb3cnOlxuICAgICAgICBxdWVyeVBhcmFtcy5kdWVEYXRlRXF1YWxzID0gdG9tb3Jyb3dEYXRlU3RyO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ3llc3RlcmRheSc6XG4gICAgICAgIHF1ZXJ5UGFyYW1zLmR1ZURhdGVFcXVhbHMgPSB5ZXN0ZXJkYXlEYXRlU3RyO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ292ZXJkdWUnOlxuICAgICAgICBxdWVyeVBhcmFtcy5kdWVEYXRlQmVmb3JlID0gdG9kYXlEYXRlU3RyOyAvLyBUYXNrcyBkdWUgYmVmb3JlIHRvZGF5XG4gICAgICAgIGlmIChxdWVyeVBhcmFtcy5zdGF0dXMgJiYgcXVlcnlQYXJhbXMuc3RhdHVzICE9PSAnRG9uZScpIHtcbiAgICAgICAgICAvLyBJZiBzdGF0dXMgaXMgYWxyZWFkeSBzcGVjaWZpZWQgYW5kIG5vdCAnRG9uZScsIGl0J3MgZmluZS5cbiAgICAgICAgICAvLyBJZiBzdGF0dXMgaXMgJ0RvbmUnLCB0aGlzIGNvbWJpbmF0aW9uIGlzIGNvbnRyYWRpY3RvcnkuXG4gICAgICAgICAgLy8gSWYgc3RhdHVzIGlzIG5vdCBzcGVjaWZpZWQsIGFkZCBub3RfZXF1YWxzICdEb25lJy5cbiAgICAgICAgfSBlbHNlIGlmICghcXVlcnlQYXJhbXMuc3RhdHVzKSB7XG4gICAgICAgICAgcXVlcnlQYXJhbXMuc3RhdHVzX25vdF9lcXVhbHMgPSAnRG9uZSc7IC8vIEVuc3VyZSB3ZSBkb24ndCBzaG93IGNvbXBsZXRlZCBvdmVyZHVlIHRhc2tzIHVubGVzcyBzcGVjaWZpZWRcbiAgICAgICAgfVxuICAgICAgICBicmVhaztcbiAgICAgIC8vIFwidGhpcyB3ZWVrXCIsIFwibmV4dCB3ZWVrXCIgd291bGQgcmVxdWlyZSBtb3JlIGNvbXBsZXggZGF0ZSByYW5nZSBjYWxjdWxhdGlvbnMuXG4gICAgICBkZWZhdWx0OlxuICAgICAgICAvLyBUcnkgdG8gcGFyc2UgYXMgYSBzcGVjaWZpYyBkYXRlIGlmIHBvc3NpYmxlICh2ZXJ5IGJhc2ljKVxuICAgICAgICBjb25zdCBzcGVjaWZpY0RhdGUgPSBwYXJzZUR1ZURhdGUoZW50aXRpZXMuZGF0ZV9jb25kaXRpb25fdGV4dCk7XG4gICAgICAgIGlmIChzcGVjaWZpY0RhdGUpIHtcbiAgICAgICAgICBxdWVyeVBhcmFtcy5kdWVEYXRlRXF1YWxzID0gc3BlY2lmaWNEYXRlLnNwbGl0KCdUJylbMF07IC8vIFVzZSBZWVlZLU1NLUREIHBhcnRcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBsb2dnZXIud2FybihcbiAgICAgICAgICAgIGBbaGFuZGxlUXVlcnlOb3Rpb25UYXNrc10gQ291bGQgbm90IHBhcnNlIGRhdGVfY29uZGl0aW9uX3RleHQ6IFwiJHtlbnRpdGllcy5kYXRlX2NvbmRpdGlvbl90ZXh0fVwiYFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICB9XG4gIH1cblxuICBpZiAoZW50aXRpZXMuc29ydF9ieV90ZXh0KSB7XG4gICAgcXVlcnlQYXJhbXMuc29ydEJ5ID0gZW50aXRpZXMuc29ydF9ieV90ZXh0O1xuICAgIGlmIChlbnRpdGllcy5zb3J0X29yZGVyX3RleHQpIHtcbiAgICAgIHF1ZXJ5UGFyYW1zLnNvcnRPcmRlciA9IGVudGl0aWVzLnNvcnRfb3JkZXJfdGV4dDtcbiAgICB9XG4gIH1cblxuICAvLyBsb2dnZXIud2FybihcIltoYW5kbGVRdWVyeU5vdGlvblRhc2tzXSBEYXRlIGNvbmRpdGlvbiBwYXJzaW5nIGFuZCBzb3J0aW5nIG5vdCBmdWxseSBpbXBsZW1lbnRlZCB5ZXQuXCIpO1xuXG4gIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHF1ZXJ5Tm90aW9uVGFza3NCYWNrZW5kKHVzZXJJZCwgcXVlcnlQYXJhbXMpO1xuXG4gIGlmIChyZXN1bHQuc3VjY2VzcyAmJiByZXN1bHQudGFza3MpIHtcbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBpZiAocmVzdWx0LnRhc2tzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgdXNlck1lc3NhZ2UgPSBcIkkgY291bGRuJ3QgZmluZCBhbnkgdGFza3MgbWF0Y2hpbmcgeW91ciBjcml0ZXJpYS5cIjtcbiAgICB9IGVsc2Uge1xuICAgICAgdXNlck1lc3NhZ2UgPSBgSGVyZSBhcmUgdGhlIHRhc2tzIEkgZm91bmQ6XFxuYDtcbiAgICAgIHJlc3VsdC50YXNrcy5mb3JFYWNoKCh0YXNrLCBpbmRleCkgPT4ge1xuICAgICAgICB1c2VyTWVzc2FnZSArPSBgJHtpbmRleCArIDF9LiAke3Rhc2suZGVzY3JpcHRpb259YDtcbiAgICAgICAgaWYgKHRhc2suZHVlRGF0ZSlcbiAgICAgICAgICB1c2VyTWVzc2FnZSArPSBgIChEdWU6ICR7bmV3IERhdGUodGFzay5kdWVEYXRlKS50b0xvY2FsZURhdGVTdHJpbmcoKX0pYDtcbiAgICAgICAgaWYgKHRhc2sucHJpb3JpdHkpIHVzZXJNZXNzYWdlICs9IGAgW1A6ICR7dGFzay5wcmlvcml0eX1dYDtcbiAgICAgICAgaWYgKHRhc2subGlzdE5hbWUpIHVzZXJNZXNzYWdlICs9IGAgKExpc3Q6ICR7dGFzay5saXN0TmFtZX0pYDtcbiAgICAgICAgaWYgKHRhc2suc3RhdHVzKSB1c2VyTWVzc2FnZSArPSBgIChTdGF0dXM6ICR7dGFzay5zdGF0dXN9KWA7XG4gICAgICAgIHVzZXJNZXNzYWdlICs9IGBcXG5gO1xuICAgICAgfSk7XG4gICAgfVxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiB7IHRhc2tzOiByZXN1bHQudGFza3MsIHVzZXJNZXNzYWdlIH0gfTtcbiAgfSBlbHNlIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0JBQ0tFTkRfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiByZXN1bHQuZXJyb3IgfHwgJ0ZhaWxlZCB0byBxdWVyeSB0YXNrcy4nLFxuICAgICAgfSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgdGFza3M6IFtdLFxuICAgICAgICB1c2VyTWVzc2FnZTogYFNvcnJ5LCBJIGNvdWxkbid0IGZldGNoIHRhc2tzLiAke3Jlc3VsdC5lcnJvciB8fCAnVGhlcmUgd2FzIGFuIGlzc3VlLid9YCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG4vLyBQbGFjZWhvbGRlciBmb3IgaGFuZGxlVXBkYXRlTm90aW9uVGFza1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVVwZGF0ZU5vdGlvblRhc2soXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogVXBkYXRlVGFza05sdUVudGl0aWVzXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8VXBkYXRlVGFza0RhdGEgJiB7IHVzZXJNZXNzYWdlOiBzdHJpbmcgfT4+IHtcbiAgbG9nZ2VyLmluZm8oXG4gICAgYFtoYW5kbGVVcGRhdGVOb3Rpb25UYXNrXSBVc2VyOiAke3VzZXJJZH0sIEVudGl0aWVzOiAke0pTT04uc3RyaW5naWZ5KGVudGl0aWVzKX1gXG4gICk7XG4gIGlmICghQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQpIHtcbiAgICAvLyBXaGlsZSBub3Qgc3RyaWN0bHkgbmVlZGVkIGZvciB1cGRhdGUgYnkgSUQsIGdvb2QgdG8gaGF2ZSBmb3IgY29udGV4dCBvciBpZiB0YXNrIHJlc29sdXRpb24gcXVlcmllcyB0aGlzIERCLlxuICAgIGxvZ2dlci53YXJuKFxuICAgICAgJ1toYW5kbGVVcGRhdGVOb3Rpb25UYXNrXSBBVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCBub3QgY29uZmlndXJlZCwgbWlnaHQgYWZmZWN0IHRhc2sgcmVzb2x1dGlvbi4nXG4gICAgKTtcbiAgfVxuXG4gIC8vIC0tLSBUYXNrIFJlc29sdXRpb24gKENvbXBsZXggU3RlcCAtIFYxOiBCYXNpYyBuYW1lIG1hdGNoaW5nKSAtLS1cbiAgLy8gVGhpcyBuZWVkcyB0byBiZSByb2J1c3QuIEZvciBWMSwgd2UgbWlnaHQgdHJ5IGEgc2ltcGxlIHF1ZXJ5LlxuICAvLyBBIGJldHRlciBhcHByb2FjaCBpbnZvbHZlcyBOTFUgcHJvdmlkaW5nIGEgdGFza19pZCBvciB0aGUgYWdlbnQgbWFpbnRhaW5pbmcgY29udGV4dC5cbiAgbGV0IHRhc2tJZFRvVXBkYXRlOiBzdHJpbmcgfCBudWxsID0gbnVsbDtcblxuICBpZiAoZW50aXRpZXMudGFza19pZGVudGlmaWVyX3RleHQpIHtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbaGFuZGxlVXBkYXRlTm90aW9uVGFza10gQXR0ZW1wdGluZyB0byByZXNvbHZlIHRhc2sgYnkgaWRlbnRpZmllcjogXCIke2VudGl0aWVzLnRhc2tfaWRlbnRpZmllcl90ZXh0fVwiYFxuICAgICk7XG4gICAgY29uc3QgcG90ZW50aWFsVGFza3MgPSBhd2FpdCBxdWVyeU5vdGlvblRhc2tzQmFja2VuZCh1c2VySWQsIHtcbiAgICAgIG5vdGlvblRhc2tzRGJJZDogQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQhLCAvLyBBc3N1bWUgaXQncyBjb25maWd1cmVkIGZvciB0aGlzIGZsb3dcbiAgICAgIGRlc2NyaXB0aW9uQ29udGFpbnM6IGVudGl0aWVzLnRhc2tfaWRlbnRpZmllcl90ZXh0LFxuICAgICAgc3RhdHVzX25vdF9lcXVhbHM6ICdEb25lJywgLy8gUHJlZmVyIHRvIHVwZGF0ZSBhY3RpdmUgdGFza3NcbiAgICAgIGxpbWl0OiA1LCAvLyBGZXRjaCBhIGZldyB0byBjaGVjayBmb3IgYW1iaWd1aXR5XG4gICAgfSk7XG5cbiAgICBpZiAocG90ZW50aWFsVGFza3Muc3VjY2VzcyAmJiBwb3RlbnRpYWxUYXNrcy50YXNrcy5sZW5ndGggPT09IDEpIHtcbiAgICAgIHRhc2tJZFRvVXBkYXRlID0gcG90ZW50aWFsVGFza3MudGFza3NbMF0uaWQ7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtoYW5kbGVVcGRhdGVOb3Rpb25UYXNrXSBSZXNvbHZlZCB0byB0YXNrIElEOiAke3Rhc2tJZFRvVXBkYXRlfWBcbiAgICAgICk7XG4gICAgfSBlbHNlIGlmIChwb3RlbnRpYWxUYXNrcy5zdWNjZXNzICYmIHBvdGVudGlhbFRhc2tzLnRhc2tzLmxlbmd0aCA+IDEpIHtcbiAgICAgIC8vIFRPRE86IEltcGxlbWVudCBkaXNhbWJpZ3VhdGlvbjogQXNrIHVzZXIgd2hpY2ggdGFzayB0aGV5IG1lYW50LlxuICAgICAgY29uc3Qgb3B0aW9ucyA9IHBvdGVudGlhbFRhc2tzLnRhc2tzXG4gICAgICAgIC5tYXAoXG4gICAgICAgICAgKHQsIGkpID0+IGAke2kgKyAxfS4gJHt0LmRlc2NyaXB0aW9ufSAoTGlzdDogJHt0Lmxpc3ROYW1lIHx8ICdOL0EnfSlgXG4gICAgICAgIClcbiAgICAgICAgLmpvaW4oJ1xcbicpO1xuICAgICAgY29uc3QgdXNlck1lc3NhZ2UgPSBgSSBmb3VuZCBhIGZldyB0YXNrcyBtYXRjaGluZyBcIiR7ZW50aXRpZXMudGFza19pZGVudGlmaWVyX3RleHR9XCIuIFdoaWNoIG9uZSBkaWQgeW91IG1lYW4/XFxuJHtvcHRpb25zfWA7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtoYW5kbGVVcGRhdGVOb3Rpb25UYXNrXSBNdWx0aXBsZSB0YXNrcyBmb3VuZCBmb3IgXCIke2VudGl0aWVzLnRhc2tfaWRlbnRpZmllcl90ZXh0fVwiLiBEaXNhbWJpZ3VhdGlvbiBuZWVkZWQuYFxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHsgY29kZTogJ0FNQklHVU9VU19UQVNLJywgbWVzc2FnZTogdXNlck1lc3NhZ2UgfSxcbiAgICAgICAgZGF0YTogeyB1c2VyTWVzc2FnZSB9IGFzIGFueSxcbiAgICAgIH07XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW2hhbmRsZVVwZGF0ZU5vdGlvblRhc2tdIENvdWxkIG5vdCBmaW5kIGEgdW5pcXVlIHRhc2sgbWF0Y2hpbmcgXCIke2VudGl0aWVzLnRhc2tfaWRlbnRpZmllcl90ZXh0fVwiLmBcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1RBU0tfTk9UX0ZPVU5EJyxcbiAgICAgICAgICBtZXNzYWdlOiBgSSBjb3VsZG4ndCBmaW5kIGEgdGFzayBtYXRjaGluZyBcIiR7ZW50aXRpZXMudGFza19pZGVudGlmaWVyX3RleHR9XCIuYCxcbiAgICAgICAgfSxcbiAgICAgICAgZGF0YToge1xuICAgICAgICAgIHVzZXJNZXNzYWdlOiBgSSBjb3VsZG4ndCBmaW5kIGEgdGFzayBtYXRjaGluZyBcIiR7ZW50aXRpZXMudGFza19pZGVudGlmaWVyX3RleHR9XCIuYCxcbiAgICAgICAgfSBhcyBhbnksXG4gICAgICB9O1xuICAgIH1cbiAgfSBlbHNlIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnVGFzayBpZGVudGlmaWVyIGlzIHJlcXVpcmVkIHRvIHVwZGF0ZSBhIHRhc2suJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICAvLyAtLS0gRW5kIFRhc2sgUmVzb2x1dGlvbiAtLS1cblxuICBjb25zdCBuZXdEdWVEYXRlSVNPID0gcGFyc2VEdWVEYXRlKGVudGl0aWVzLm5ld19kdWVfZGF0ZV90ZXh0KTtcbiAgaWYgKGVudGl0aWVzLm5ld19kdWVfZGF0ZV90ZXh0ICYmICFuZXdEdWVEYXRlSVNPKSB7XG4gICAgbG9nZ2VyLndhcm4oXG4gICAgICBgW2hhbmRsZVVwZGF0ZU5vdGlvblRhc2tdIE5ldyBkdWUgZGF0ZSB0ZXh0IFwiJHtlbnRpdGllcy5uZXdfZHVlX2RhdGVfdGV4dH1cIiBwcm92aWRlZCBidXQgY291bGQgbm90IGJlIHBhcnNlZC5gXG4gICAgKTtcbiAgfVxuXG4gIGNvbnN0IHBhcmFtczogVXBkYXRlTm90aW9uVGFza1BhcmFtcyA9IHtcbiAgICB0YXNrSWQ6IHRhc2tJZFRvVXBkYXRlISwgLy8gQXNzZXJ0aW5nIGl0J3Mgbm9uLW51bGwgYWZ0ZXIgcmVzb2x1dGlvbiBsb2dpY1xuICAgIGRlc2NyaXB0aW9uOiBlbnRpdGllcy5uZXdfZGVzY3JpcHRpb25fdGV4dCxcbiAgICBkdWVEYXRlOiBuZXdEdWVEYXRlSVNPLFxuICAgIHN0YXR1czogbWFwU3RhdHVzKGVudGl0aWVzLm5ld19zdGF0dXNfdGV4dCksXG4gICAgcHJpb3JpdHk6IG1hcFByaW9yaXR5KGVudGl0aWVzLm5ld19wcmlvcml0eV90ZXh0KSxcbiAgICBsaXN0TmFtZTogZW50aXRpZXMubmV3X2xpc3RfbmFtZV90ZXh0LFxuICB9O1xuXG4gIC8vIEZpbHRlciBvdXQgdW5kZWZpbmVkIHBhcmFtcyBzbyBvbmx5IHByb3ZpZGVkIGZpZWxkcyBhcmUgdXBkYXRlZFxuICBjb25zdCBmaWx0ZXJlZFBhcmFtcyA9IE9iamVjdC5mcm9tRW50cmllcyhcbiAgICBPYmplY3QuZW50cmllcyhwYXJhbXMpLmZpbHRlcigoW18sIHZdKSA9PiB2ICE9PSB1bmRlZmluZWQpXG4gICkgYXMgVXBkYXRlTm90aW9uVGFza1BhcmFtcztcbiAgaWYgKE9iamVjdC5rZXlzKGZpbHRlcmVkUGFyYW1zKS5sZW5ndGggPD0gMSAmJiBmaWx0ZXJlZFBhcmFtcy50YXNrSWQpIHtcbiAgICAvLyBPbmx5IHRhc2tJZCBtZWFucyBubyBhY3R1YWwgdXBkYXRlc1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdObyBwcm9wZXJ0aWVzIHByb3ZpZGVkIHRvIHVwZGF0ZSBmb3IgdGhlIHRhc2suJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHVwZGF0ZU5vdGlvblRhc2tCYWNrZW5kKHVzZXJJZCwgZmlsdGVyZWRQYXJhbXMpO1xuXG4gIGlmIChyZXN1bHQub2sgJiYgcmVzdWx0LmRhdGEpIHtcbiAgICBjb25zdCB1c2VyTWVzc2FnZSA9IGBPa2F5LCBJJ3ZlIHVwZGF0ZWQgdGhlIHRhc2sgKElEOiAke3Jlc3VsdC5kYXRhLnRhc2tJZH0pLiBQcm9wZXJ0aWVzIGNoYW5nZWQ6ICR7cmVzdWx0LmRhdGEudXBkYXRlZFByb3BlcnRpZXMuam9pbignLCAnKX0uYDtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiB7IC4uLnJlc3VsdC5kYXRhLCB1c2VyTWVzc2FnZSB9LFxuICAgIH07XG4gIH0gZWxzZSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiByZXN1bHQuZXJyb3IgfHwge1xuICAgICAgICBjb2RlOiAnQkFDS0VORF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gdXBkYXRlIHRhc2sgaW4gTm90aW9uIHZpYSBiYWNrZW5kLicsXG4gICAgICB9LFxuICAgICAgZGF0YToge1xuICAgICAgICB1c2VyTWVzc2FnZTogYFNvcnJ5LCBJIGNvdWxkbid0IHVwZGF0ZSB0aGUgdGFzay4gJHtyZXN1bHQuZXJyb3I/Lm1lc3NhZ2UgfHwgJ1RoZXJlIHdhcyBhbiBpc3N1ZS4nfWAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUFkZFN1YnRhc2soXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczoge1xuICAgIHBhcmVudF90YXNrX2lkZW50aWZpZXJfdGV4dDogc3RyaW5nO1xuICAgIHN1Yl90YXNrX2Rlc2NyaXB0aW9uOiBzdHJpbmc7XG4gIH1cbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxDcmVhdGVUYXNrRGF0YSAmIHsgdXNlck1lc3NhZ2U6IHN0cmluZyB9Pj4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW2hhbmRsZUFkZFN1YnRhc2tdIFVzZXI6ICR7dXNlcklkfSwgRW50aXRpZXM6ICR7SlNPTi5zdHJpbmdpZnkoZW50aXRpZXMpfWBcbiAgKTtcblxuICBpZiAoIUFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdOb3Rpb24gVGFza3MgRGF0YWJhc2UgSUQgKEFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEKSBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgLy8gMS4gUmVzb2x2ZSBQYXJlbnQgVGFza1xuICBsZXQgcGFyZW50VGFza0lkOiBzdHJpbmcgfCBudWxsID0gbnVsbDtcbiAgaWYgKGVudGl0aWVzLnBhcmVudF90YXNrX2lkZW50aWZpZXJfdGV4dCkge1xuICAgIGNvbnN0IHBvdGVudGlhbFRhc2tzID0gYXdhaXQgcXVlcnlOb3Rpb25UYXNrc0JhY2tlbmQodXNlcklkLCB7XG4gICAgICBub3Rpb25UYXNrc0RiSWQ6IEFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lELFxuICAgICAgZGVzY3JpcHRpb25Db250YWluczogZW50aXRpZXMucGFyZW50X3Rhc2tfaWRlbnRpZmllcl90ZXh0LFxuICAgICAgc3RhdHVzX25vdF9lcXVhbHM6ICdEb25lJyxcbiAgICAgIGxpbWl0OiA1LFxuICAgIH0pO1xuXG4gICAgaWYgKHBvdGVudGlhbFRhc2tzLnN1Y2Nlc3MgJiYgcG90ZW50aWFsVGFza3MudGFza3MubGVuZ3RoID09PSAxKSB7XG4gICAgICBwYXJlbnRUYXNrSWQgPSBwb3RlbnRpYWxUYXNrcy50YXNrc1swXS5pZDtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gSGFuZGxlIGFtYmlndW91cyBvciBub3QgZm91bmQgcGFyZW50IHRhc2tcbiAgICAgIGNvbnN0IGVycm9yTWVzc2FnZSA9XG4gICAgICAgIHBvdGVudGlhbFRhc2tzLnRhc2tzLmxlbmd0aCA+IDFcbiAgICAgICAgICA/IGBJIGZvdW5kIG11bHRpcGxlIHRhc2tzIG1hdGNoaW5nIFwiJHtlbnRpdGllcy5wYXJlbnRfdGFza19pZGVudGlmaWVyX3RleHR9XCIuIFBsZWFzZSBiZSBtb3JlIHNwZWNpZmljLmBcbiAgICAgICAgICA6IGBJIGNvdWxkbid0IGZpbmQgYSBwYXJlbnQgdGFzayBtYXRjaGluZyBcIiR7ZW50aXRpZXMucGFyZW50X3Rhc2tfaWRlbnRpZmllcl90ZXh0fVwiLmA7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7IGNvZGU6ICdQQVJFTlRfVEFTS19OT1RfRk9VTkQnLCBtZXNzYWdlOiBlcnJvck1lc3NhZ2UgfSxcbiAgICAgIH07XG4gICAgfVxuICB9IGVsc2Uge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQYXJlbnQgdGFzayBpZGVudGlmaWVyIGlzIHJlcXVpcmVkIHRvIGFkZCBhIHN1Yi10YXNrLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICAvLyAyLiBDcmVhdGUgU3ViLXRhc2tcbiAgY29uc3QgcGFyYW1zOiBDcmVhdGVOb3Rpb25UYXNrUGFyYW1zID0ge1xuICAgIG5vdGlvblRhc2tzRGJJZDogQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQsXG4gICAgZGVzY3JpcHRpb246IGVudGl0aWVzLnN1Yl90YXNrX2Rlc2NyaXB0aW9uLFxuICAgIHN0YXR1czogJ1RvIERvJyxcbiAgICBwYXJlbnRJZDogcGFyZW50VGFza0lkLFxuICB9O1xuXG4gIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGNyZWF0ZU5vdGlvblRhc2tCYWNrZW5kKHVzZXJJZCwgcGFyYW1zLCBpbnRlZ3JhdGlvbnMpO1xuXG4gIGlmIChyZXN1bHQub2sgJiYgcmVzdWx0LmRhdGEpIHtcbiAgICBjb25zdCB1c2VyTWVzc2FnZSA9IGBPa2F5LCBJJ3ZlIGFkZGVkIFwiJHtlbnRpdGllcy5zdWJfdGFza19kZXNjcmlwdGlvbn1cIiBhcyBhIHN1Yi10YXNrLmA7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgZGF0YTogeyAuLi5yZXN1bHQuZGF0YSwgdXNlck1lc3NhZ2UgfSxcbiAgICB9O1xuICB9IGVsc2Uge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogcmVzdWx0LmVycm9yIHx8IHtcbiAgICAgICAgY29kZTogJ0JBQ0tFTkRfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIGNyZWF0ZSBzdWItdGFzayBpbiBOb3Rpb24uJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuIl19
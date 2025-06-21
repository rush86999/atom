import { agenda, ScheduledAgentTaskData } from '../../../agendaService'; // Adjusted path

// New ScheduleTaskParams interface for Agenda-based scheduling
export interface ScheduleTaskParams {
  taskDescription?: string; // Description of the task for logging/confirmation
  when: string | Date;       // Date string (ISO), human-readable ("tomorrow at 10am"), Date object, or cron string for recurring
  originalUserIntent: string; // The actual agent intent to be executed (e.g., "SEND_EMAIL", "CREATE_CALENDAR_EVENT")
  entities: Record<string, any>; // Entities required for the originalUserIntent
  userId: string;
  conversationId?: string;   // Optional: for context
  // For recurring tasks (using agenda.every)
  isRecurring?: boolean;         // Flag to indicate if the task is recurring
  repeatInterval?: string;     // e.g., "1 day", "2 hours", cron string. Used if isRecurring is true.
  repeatTimezone?: string;     // Optional: Timezone for recurring tasks, e.g., "America/New_York"
}

/**
 * Schedules a task (agent action) to be executed at a specified time or interval using Agenda.
 *
 * @param params - The parameters for scheduling the task.
 * @returns A promise that resolves to a string message indicating success or failure.
 */
export async function scheduleTask(params: ScheduleTaskParams): Promise<string> {
  const {
    when,
    originalUserIntent,
    entities,
    userId,
    conversationId,
    taskDescription, // Used for confirmation messages
    isRecurring,
    repeatInterval,
    repeatTimezone,
  } = params;

  // Validate essential parameters for scheduling
  if (!when) {
    return "Scheduling time ('when') must be provided.";
  }
  if (!originalUserIntent) {
    return "The original user intent to be scheduled must be provided.";
  }
  if (!userId) {
    return "User ID must be provided for scheduling.";
  }

  const jobData: ScheduledAgentTaskData = {
    originalUserIntent,
    entities: entities || {}, // Ensure entities is at least an empty object
    userId,
    conversationId,
  };

  try {
    // Ensure agenda is actually running. This is typically done at application bootstrap,
    // but a check or specific call here might be desired if agenda could be down.
    // For now, we assume agenda is started elsewhere.
    // if (!agenda.isRunning) { // agenda.isRunning is not a public property.
    //   console.warn("Agenda service does not seem to be running. Attempting to start it.");
    //   // await startAgenda(); // startAgenda() should be called at app level.
    //   // If agenda is not started, .schedule or .every might fail or queue indefinitely without processing.
    // }

    let jobDetailsMessage: string;

    if (isRecurring && repeatInterval) {
      // For recurring tasks using agenda.every()
      // 'repeatInterval' can be a human-readable string like "every 2 hours" or a cron string.
      // 'when' in this case might be an optional start date/time for the recurrence,
      // but agenda.every() primarily uses the interval.
      // If 'when' is a Date or date string, it can act as the first run time for `every`.
      const options: { timezone?: string; startDate?: Date } = {};
      if (repeatTimezone) {
        options.timezone = repeatTimezone;
      }
      if (when instanceof Date || (typeof when === 'string' && !when.includes('*') && !when.toLowerCase().startsWith('every'))) {
         // If 'when' looks like a specific date/time for the first run rather than an interval string itself.
         // Agenda's 'every' can take a startDate in options.
         // However, the first param of 'every' is the interval.
         // If 'when' is meant to be the start date, and repeatInterval is the actual interval.
         // This part might need more sophisticated handling of 'when' vs 'repeatInterval' for 'every'.
         // For now, we assume repeatInterval is the primary definition for recurrence.
         // Let's assume `repeatInterval` is the cron/interval string, and `when` is not used by `every` directly
         // unless `every`'s first param is a date (which is not its typical use for defining interval).
      }

      await agenda.every(repeatInterval, 'EXECUTE_AGENT_ACTION', jobData, options);
      jobDetailsMessage = `Recurring task "${taskDescription || originalUserIntent}" scheduled to run based on interval: ${repeatInterval}.`;
      console.log(`Recurring task for intent '${originalUserIntent}' for user '${userId}' scheduled. Interval: ${repeatInterval}. Data:`, JSON.stringify(jobData));

    } else {
      // For one-time tasks using agenda.schedule()
      // 'when' should be a Date object or a date string Agenda understands (e.g., ISO format, "tomorrow at 9am").
      if (typeof when !== 'string' && !(when instanceof Date)) {
        return "Invalid 'when' parameter for a one-time task. Must be a date string or Date object.";
      }
      await agenda.schedule(when, 'EXECUTE_AGENT_ACTION', jobData);
      jobDetailsMessage = `Task "${taskDescription || originalUserIntent}" has been scheduled for ${typeof when === 'string' ? when : when.toISOString()}.`;
      console.log(`One-time task for intent '${originalUserIntent}' for user '${userId}' scheduled for '${when}'. Data:`, JSON.stringify(jobData));
    }

    return jobDetailsMessage;

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`Error scheduling task for intent '${originalUserIntent}' for user '${userId}':`, errorMessage, error);
    return `Failed to schedule task: ${errorMessage}`;
  }
}

// Other scheduling-related utility functions could be added here if needed.
// e.g., listScheduledTasks, cancelScheduledTask etc.
// These would also use the `agenda` instance.
export interface CancelTaskParams {
  jobId?: string; // Database ID of the job
  jobName?: string; // Name of the job (e.g., EXECUTE_AGENT_ACTION)
  // Need criteria to find the job(s)
  userId?: string; // To scope cancellation by user
  originalUserIntent?: string; // To scope by intent
}

export async function cancelTask(params: CancelTaskParams): Promise<string> {
    try {
        const query: any = {};
        if (params.jobName) {
            query.name = params.jobName;
        }
        if (params.userId) {
            query['data.userId'] = params.userId;
        }
        if (params.originalUserIntent) {
            query['data.originalUserIntent'] = params.originalUserIntent;
        }

        // If a specific job ID is provided, it's more direct
        // However, Agenda's cancel method uses a query. If we have the _id,
        // we can use { _id: new ObjectId(params.jobId) } if using mongodb ObjectId directly.
        // Agenda's types for query in cancel are not explicitly ObjectId-aware in its simplified type definition.
        // For now, let's assume cancellation is based on properties in `data` or `name`.
        // A more robust cancel by _id might need to ensure ObjectId conversion if jobs are found that way.
        // The `agenda.cancel` method takes a query object.
        if (Object.keys(query).length === 0 && !params.jobId) {
            return "No criteria provided to cancel tasks. Please specify jobName, userId, or originalUserIntent.";
        }

        // If jobId is provided and it's a valid MongoDB ObjectId string,
        // we could construct a query for it.
        // For this example, we'll rely on cancelling based on other data properties for simplicity.
        // If a unique `jobId` (e.g. a custom one stored in `data`) is available, query by `data.customJobId`.
        // Agenda's own `_id` is an ObjectId.

        const numRemoved = await agenda.cancel(query);

        if (numRemoved > 0) {
            return `Successfully cancelled ${numRemoved} task(s) matching criteria.`;
        } else {
            return "No tasks found matching the criteria to cancel.";
        }
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error('Error cancelling task(s):', errorMessage, error);
        return `Failed to cancel task(s): ${errorMessage}`;
    }
}

import { Agenda, Job } from 'agenda';
import axios from 'axios'; // Added for making HTTP calls

// Define the structure for job data
export interface ScheduledAgentTaskData {
  originalUserIntent: string; // e.g., "CREATE_TASK", "SEND_EMAIL"
  entities: Record<string, any>;    // Store extracted NLU entities
  userId: string;
  conversationId?: string;         // Optional: if needed to maintain context
  // additionalContext?: Record<string, any>; // For any other necessary data
}

// Default MongoDB connection string - replace with your actual URI in production
const mongoConnectionString = process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/atomicAgentJobs';

// URL for the agent's internal invocation endpoint
const AGENT_INTERNAL_INVOKE_URL = process.env.AGENT_INTERNAL_INVOKE_URL || 'http://localhost:7071/api/agentMessageHandler'; // Adjust if your agent runs elsewhere or on a different port

// Initialize Agenda
export const agenda = new Agenda({
  db: { address: mongoConnectionString, collection: 'agentScheduledTasks' },
  processEvery: '1 minute', // How often Agenda checks for jobs
  maxConcurrency: 20,      // Max number of jobs to run at once
  // defaultLockLifetime: 10000, // 10 seconds, time before a job is considered timed out & re-queued
});

/**
 * Defines a job with Agenda.
 * @param name - The name of the job.
 * @param handler - The async function to execute for the job. It receives the job object as an argument.
 *
 * Example:
 * defineJob('send-welcome-email', async (job: Job) => {
 *   const { userId } = job.attrs.data;
 *   await sendEmail(userId, 'Welcome!');
 * });
 */
export function defineJob<T>(name: string, handler: (job: Job<T>) => Promise<void>): void {
  agenda.define<T>(name, handler);
  console.log(`Job defined: ${name}`);
}

/**
 * Starts the Agenda instance.
 * This should be called when the application starts.
 * It connects to MongoDB and starts processing jobs.
 */
export async function startAgenda(): Promise<void> {
  try {
    console.log('Attempting to start Agenda...');
    await agenda.start(); // This connects to MongoDB and starts job processing
    console.log('Agenda started successfully.');

    // Define the job processor for executing scheduled agent actions
    agenda.define<ScheduledAgentTaskData>('EXECUTE_AGENT_ACTION', async (job) => {
      const data = job.attrs.data;
      if (!data) {
        const errorMessage = `Job ${job.attrs.name} (ID: ${job.attrs._id}) is missing data.`;
        console.error(errorMessage);
        job.fail(errorMessage);
        await job.save();
        return;
      }

      const { originalUserIntent, entities, userId } = data;
      console.log(`Executing scheduled agent action for user ${userId} (Job ID: ${job.attrs._id}): intent ${originalUserIntent}`);
      console.log(`Entities: ${JSON.stringify(entities)}`);

      try {
        // Construct the payload for the agent's internal handler
        // This payload structure assumes the target endpoint can process it directly,
        // potentially bypassing NLU if `requestSource` indicates a scheduled job.
        const payload = {
          // If the target endpoint uses `handleConversationInputWrapper` which calls `_internalHandleMessage`
          // then the payload should be `{ text: "...", userId: userId }`
          // and "text" would need to be a phrase that NLU can convert back to originalUserIntent and entities.
          // However, the prompt suggests a more direct payload:
          message: `Scheduled task: ${originalUserIntent}`, // A descriptive text for logging or if NLU is still hit
          intentName: originalUserIntent, // For direct intent usage if endpoint supports it
          entities: entities,
          userId: userId,
          conversationId: data.conversationId, // Pass along if available
          requestSource: 'ScheduledJobExecutor' // To indicate this is from Agenda
        };
        console.log(`Invoking agent at ${AGENT_INTERNAL_INVOKE_URL} with payload:`, JSON.stringify(payload, null, 2));

        const response = await axios.post(AGENT_INTERNAL_INVOKE_URL, payload, {
          headers: { 'Content-Type': 'application/json' }
        });

        console.log(`Scheduled task ${job.attrs.name} (ID: ${job.attrs._id}) for user ${userId} processed by agent. Agent response status: ${response.status}`, response.data ? JSON.stringify(response.data) : '');
        // Job is considered successful if agent processes it without throwing an error here.
        // Actual success of the underlying task (e.g., email sent) is handled by the agent.
      } catch (error) {
        let errorMessage = 'Failed to execute agent action via HTTP.';
        if (axios.isAxiosError(error)) {
          errorMessage = error.response ? `Agent endpoint error: ${error.response.status} - ${JSON.stringify(error.response.data)}` : `Agent endpoint error: ${error.message}`;
        } else if (error instanceof Error) {
          errorMessage = error.message;
        }
        console.error(`Error executing scheduled task ${job.attrs.name} (ID: ${job.attrs._id}) for user ${userId}: ${errorMessage}`, error.stack);
        job.fail(errorMessage);
        // job.attrs.lastRunAt = new Date(); // Agenda updates this automatically
        // job.attrs.failedAt = new Date(); // Agenda updates this
        // job.attrs.failReason = errorMessage; // Agenda updates this
        await job.save(); // Persist failure information to the job
        // No re-throw, let Agenda handle retry based on its configuration for the job definition if any.
      }
    });

    // Example job definition (can be moved to where tasks are actually defined)
    // defineJob<{ userId: string }>('example-task', async job => {
    //   const { userId } = job.attrs.data;
    //   console.log(`Executing example-task for userId: ${userId} at ${new Date()}`);
    //   // Simulate some work
    //   await new Promise(resolve => setTimeout(resolve, 2000));
    //   console.log(`Finished example-task for userId: ${userId}`);
    // });

    // Schedule an example job to see it in action (optional, for testing)
    // if (process.env.NODE_ENV !== 'production') {
    //   agenda.every('2 minutes', 'example-task', { userId: 'test-user-agenda' });
    //   console.log('Scheduled example-task to run every 2 minutes.');
    // }

  } catch (error) {
    console.error('Failed to start Agenda:', error);
    // Depending on application requirements, might want to throw error or exit process
    // throw error;
  }
}

/**
 * Stops the Agenda instance gracefully.
 * This should be called on application shutdown to allow currently running jobs to complete.
 */
export async function stopAgenda(): Promise<void> {
  try {
    console.log('Attempting to stop Agenda...');
    // agenda.stop() waits for all currently running jobs to complete
    // and then disconnects from the database.
    await agenda.stop();
    console.log('Agenda stopped successfully.');
  } catch (error) {
    console.error('Failed to stop Agenda gracefully:', error);
  }
}

// Optional: Event listeners for Agenda can be useful for logging/monitoring
agenda.on('ready', () => console.log('Agenda ready and connected to MongoDB.'));
agenda.on('error', (err: Error) => console.error('Agenda connection error:', err));

agenda.on('start', (job: Job) => console.log(`Job ${job.attrs.name} starting. ID: ${job.attrs._id}`));
agenda.on('complete', (job: Job) => console.log(`Job ${job.attrs.name} completed. ID: ${job.attrs._id}`));
agenda.on('success', (job: Job) => console.log(`Job ${job.attrs.name} succeeded. ID: ${job.attrs._id}`));
agenda.on('fail', (err: Error, job: Job) => console.error(`Job ${job.attrs.name} failed with error: ${err.message}. ID: ${job.attrs._id}`));

// Export the agenda instance directly if needed for advanced use cases (e.g., scheduling from elsewhere)
// export const getAgendaInstance = () => agenda;

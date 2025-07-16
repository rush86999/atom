import { Agenda, Job } from 'agenda';
import axios from 'axios'; // Added for making HTTP calls
import { sendSlackMessage } from './atom-agent/skills/slackSkills';

// Define the structure for job data
export interface ScheduledAgentTaskData {
  originalUserIntent: string; // e.g., "CREATE_TASK", "SEND_EMAIL"
  entities: Record<string, any>;    // Store extracted NLU entities
  userId: string;
  conversationId?: string;         // Optional: if needed to maintain context
  // additionalContext?: Record<string, any>; // For any other necessary data
}

export interface SendTaskReminderData {
    userId: string;
    taskId: string;
    taskDescription: string;
}

// Default MongoDB connection string - replace with your actual URI in production
const mongoConnectionString = process.env.MONGODB_URI || 'mongodb://mongo:27017/atomicAgentJobs';

// URL for the agent's internal invocation endpoint
const AGENT_INTERNAL_INVOKE_URL = process.env.AGENT_INTERNAL_INVOKE_URL || 'http://localhost:3000/api/agent-handler';

// Initialize Agenda
export const agenda = new Agenda({
  db: { address: mongoConnectionString, collection: 'agentScheduledTasks' },
  processEvery: '1 minute', // How often Agenda checks for jobs
  maxConcurrency: 20,      // Max number of jobs to run at once
});

export function defineJob<T>(name: string, handler: (job: Job<T>) => Promise<void>): void {
  agenda.define<T>(name, handler);
  console.log(`Job defined: ${name}`);
}

export async function startAgenda(): Promise<void> {
  try {
    console.log('Attempting to start Agenda...');
    await agenda.start();
    console.log('Agenda started successfully.');

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
        const agentPayload = {
            message: `Execute scheduled task: ${originalUserIntent}`,
            userId: userId,
            intentName: originalUserIntent,
            entities: entities,
            conversationId: data.conversationId,
            requestSource: 'ScheduledJobExecutor',
          };
        console.log(`Invoking agent at ${AGENT_INTERNAL_INVOKE_URL} with payload:`, JSON.stringify(agentPayload, null, 2));

        const response = await axios.post(AGENT_INTERNAL_INVOKE_URL, agentPayload, {
          headers: { 'Content-Type': 'application/json' }
        });

        console.log(`Scheduled task ${job.attrs.name} (ID: ${job.attrs._id}) for user ${userId} processed by agent. Agent response status: ${response.status}, response data: ${response.data ? JSON.stringify(response.data, null, 2) : ''}`);
      } catch (error) {
        let errorMessage = 'Failed to execute agent action via HTTP.';
        if (axios.isAxiosError(error)) {
          errorMessage = error.response ? `Agent endpoint error: ${error.response.status} - ${JSON.stringify(error.response.data)}` : `Agent endpoint error: ${error.message}`;
        } else if (error instanceof Error) {
          errorMessage = error.message;
        }
        console.error(`Error executing scheduled task ${job.attrs.name} (ID: ${job.attrs._id}) for user ${userId}: ${errorMessage}`, error.stack);
        job.fail(errorMessage);
        await job.save();
      }
    });

    agenda.define<SendTaskReminderData>('send task reminder', async (job) => {
        const { userId, taskId, taskDescription } = job.attrs.data;
        console.log(`Sending reminder for task "${taskDescription}" (ID: ${taskId}) to user ${userId}`);
        try {
            await sendSlackMessage(userId, userId, `Reminder: Task "${taskDescription}" is due.`);
        } catch (error) {
            console.error(`Failed to send task reminder for task ${taskId} to user ${userId}:`, error);
        }
    });


  } catch (error) {
    console.error('Failed to start Agenda:', error);
  }
}

export async function stopAgenda(): Promise<void> {
  try {
    console.log('Attempting to stop Agenda...');
    await agenda.stop();
    console.log('Agenda stopped successfully.');
  } catch (error) {
    console.error('Failed to stop Agenda gracefully:', error);
  }
}

agenda.on('ready', () => console.log('Agenda ready and connected to MongoDB.'));
agenda.on('error', (err: Error) => console.error('Agenda connection error:', err));
agenda.on('start', (job: Job) => console.log(`Job ${job.attrs.name} starting. ID: ${job.attrs._id}`));
agenda.on('complete', (job: Job) => console.log(`Job ${job.attrs.name} completed. ID: ${job.attrs._id}`));
agenda.on('success', (job: Job) => console.log(`Job ${job.attrs.name} succeeded. ID: ${job.attrs._id}`));
agenda.on('fail', (err: Error, job: Job) => console.error(`Job ${job.attrs.name} failed with error: ${err.message}. ID: ${job.attrs._id}`));

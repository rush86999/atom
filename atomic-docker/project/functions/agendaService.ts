import { Agenda, Job } from 'agenda';
import axios from 'axios'; // Added for making HTTP calls
import { sendSlackMessage } from './atom-agent/skills/slackSkills';
import logger from './lib/logger';

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
  logger.info(`Job defined: ${name}`);
}

export async function startAgenda(): Promise<void> {
  try {
    logger.info('Attempting to start Agenda...');
    await agenda.start();
    logger.info('Agenda started successfully.');

    agenda.define<ScheduledAgentTaskData>('EXECUTE_AGENT_ACTION', async (job) => {
      const data = job.attrs.data;
      if (!data) {
        const errorMessage = `Job ${job.attrs.name} (ID: ${job.attrs._id}) is missing data.`;
        logger.error({
            job_name: job.attrs.name,
            job_id: job.attrs._id,
            error_message: errorMessage,
        }, errorMessage);
        job.fail(errorMessage);
        await job.save();
        return;
      }

      const { originalUserIntent, entities, userId } = data;
      logger.info({
        job_name: job.attrs.name,
        job_id: job.attrs._id,
        user_id: userId,
        intent: originalUserIntent,
        entities: entities,
      },`Executing scheduled agent action for user ${userId} (Job ID: ${job.attrs._id}): intent ${originalUserIntent}`);

      try {
        const agentPayload = {
            message: `Execute scheduled task: ${originalUserIntent}`,
            userId: userId,
            intentName: originalUserIntent,
            entities: entities,
            conversationId: data.conversationId,
            requestSource: 'ScheduledJobExecutor',
          };
        logger.info({
            job_name: job.attrs.name,
            job_id: job.attrs._id,
            user_id: userId,
            agent_url: AGENT_INTERNAL_INVOKE_URL,
            payload: agentPayload,
        },`Invoking agent at ${AGENT_INTERNAL_INVOKE_URL}`);

        const response = await axios.post(AGENT_INTERNAL_INVOKE_URL, agentPayload, {
          headers: { 'Content-Type': 'application/json' }
        });

        logger.info({
            job_name: job.attrs.name,
            job_id: job.attrs._id,
            user_id: userId,
            agent_response_status: response.status,
            agent_response_data: response.data,
        },`Scheduled task ${job.attrs.name} (ID: ${job.attrs._id}) for user ${userId} processed by agent. Agent response status: ${response.status}`);
      } catch (error) {
        let errorMessage = 'Failed to execute agent action via HTTP.';
        if (axios.isAxiosError(error)) {
          errorMessage = error.response ? `Agent endpoint error: ${error.response.status} - ${JSON.stringify(error.response.data)}` : `Agent endpoint error: ${error.message}`;
        } else if (error instanceof Error) {
          errorMessage = error.message;
        }
        logger.error({
            job_name: job.attrs.name,
            job_id: job.attrs._id,
            user_id: userId,
            error_message: errorMessage,
            error_stack: error instanceof Error ? error.stack : undefined,
        },`Error executing scheduled task ${job.attrs.name} (ID: ${job.attrs._id}) for user ${userId}: ${errorMessage}`);
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
    logger.error({
        error_message: error instanceof Error ? error.message : 'Unknown error',
        error_stack: error instanceof Error ? error.stack : undefined,
    },'Failed to start Agenda:');
  }
}

export async function stopAgenda(): Promise<void> {
  try {
    logger.info('Attempting to stop Agenda...');
    await agenda.stop();
    logger.info('Agenda stopped successfully.');
  } catch (error) {
    logger.error({
        error_message: error instanceof Error ? error.message : 'Unknown error',
        error_stack: error instanceof Error ? error.stack : undefined,
    },'Failed to stop Agenda gracefully:');
  }
}

agenda.on('ready', () => logger.info('Agenda ready and connected to MongoDB.'));
agenda.on('error', (err: Error) => logger.error({
    error_message: err.message,
    error_stack: err.stack,
},'Agenda connection error:'));
agenda.on('start', (job: Job) => logger.info({ job_name: job.attrs.name, job_id: job.attrs._id }, `Job ${job.attrs.name} starting.`));
agenda.on('complete', (job: Job) => logger.info({ job_name: job.attrs.name, job_id: job.attrs._id }, `Job ${job.attrs.name} completed.`));
agenda.on('success', (job: Job) => logger.info({ job_name: job.attrs.name, job_id: job.attrs._id }, `Job ${job.attrs.name} succeeded.`));
agenda.on('fail', (err: Error, job: Job) => logger.error({
    job_name: job.attrs.name,
    job_id: job.attrs._id,
    error_message: err.message,
    error_stack: err.stack,
},`Job ${job.attrs.name} failed with error: ${err.message}.`));

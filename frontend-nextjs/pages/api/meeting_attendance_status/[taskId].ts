import type { NextApiRequest, NextApiResponse } from 'next';
import { Pool } from 'pg';
import { getSession } from 'supertokens-node/nextjs';
import { SessionRequest } from 'supertokens-node/framework/express'; // May not be needed if getSession works directly with NextApiRequest
import supertokens from 'supertokens-node';
import { backendConfig } from '../../../config/backendConfig'; // Corrected path
import appServiceLogger from '../../../lib/logger'; // Import the shared logger

// Define a type for the expected response data
// This should match the structure of your meeting_attendance_status table
type MeetingAttendanceStatus = {
  task_id: string;
  user_id: string | null;
  platform: string | null;
  meeting_identifier: string | null;
  status_timestamp: string; // TIMESTAMPTZ will likely be a string
  current_status_message: string;
  final_notion_page_url: string | null;
  error_details: string | null;
  created_at: string; // TIMESTAMPTZ will likely be a string
};

type ErrorResponse = {
  error: string;
  details?: string;
};

// Initialize PostgreSQL pool
// Connection parameters will be sourced from environment variables:
// PGHOST, PGUSER, PGDATABASE, PGPASSWORD, PGPORT
let pool: Pool | null = null;

try {
  supertokens.init(backendConfig()); // Initialize Supertokens
  pool = new Pool(); // Reads environment variables automatically
  appServiceLogger.info(
    'PostgreSQL Pool and Supertokens initialized successfully for meeting_attendance_status API.'
  );
} catch (error: any) {
  appServiceLogger.fatal(
    { error: error.message, stack: error.stack, details: error },
    'Failed to initialize PostgreSQL Pool or Supertokens. API will not function correctly.'
  );
  // If pool init fails, subsequent calls will also fail the !pool check.
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<
    MeetingAttendanceStatus | MeetingAttendanceStatus[] | ErrorResponse
  >
) {
  const operationName = 'getMeetingAttendanceStatus'; // For logging

  if (!pool) {
    appServiceLogger.error(
      `[${operationName}] PostgreSQL pool not initialized. Cannot connect to database.`
    );
    return res
      .status(500)
      .json({ error: 'Database connection not configured.' });
  }

  let session;
  try {
    session = await getSession(req as any, res as any, true);
  } catch (error: any) {
    appServiceLogger.error(`[${operationName}] Supertokens getSession error.`, {
      error: error.message,
      stack: error.stack,
      details: error,
    });
    return res
      .status(500)
      .json({ error: 'Authentication error', details: error.message });
  }

  if (!session) {
    appServiceLogger.warn(
      `[${operationName}] Unauthorized attempt: No active session.`
    );
    return res.status(401).json({ error: 'Unauthorized. Please log in.' });
  }
  const authenticatedUserId = session.getUserId();
  appServiceLogger.info(`[${operationName}] Request received for user.`, {
    authenticatedUserId,
    taskId: req.query.taskId,
  });

  const { taskId } = req.query;

  if (req.method !== 'GET') {
    appServiceLogger.warn(`[${operationName}] Method not allowed.`, {
      method: req.method,
      authenticatedUserId,
      taskId,
    });
    res.setHeader('Allow', ['GET']);
    return res.status(405).json({ error: `Method ${req.method} Not Allowed` });
  }

  if (!taskId || typeof taskId !== 'string') {
    appServiceLogger.warn(`[${operationName}] Invalid or missing taskId.`, {
      taskId,
      authenticatedUserId,
    });
    return res
      .status(400)
      .json({ error: 'Task ID is required and must be a string.' });
  }
  // Duplicate check removed, one is sufficient.

  try {
    const client = await pool.connect();
    appServiceLogger.debug(`[${operationName}] DB client connected.`, {
      authenticatedUserId,
      taskId,
    });
    try {
      const queryText =
        'SELECT * FROM meeting_attendance_status WHERE task_id = $1 AND user_id = $2';
      appServiceLogger.debug(`[${operationName}] Executing query.`, {
        queryText,
        params: [taskId, authenticatedUserId],
      });
      const result = await client.query(queryText, [
        taskId,
        authenticatedUserId,
      ]);

      if (result.rows.length > 0) {
        const row = result.rows[0];
        const statusRecord: MeetingAttendanceStatus = {
          ...row,
          status_timestamp: new Date(row.status_timestamp).toISOString(),
          created_at: new Date(row.created_at).toISOString(),
        };
        appServiceLogger.info(`[${operationName}] Status found for task.`, {
          authenticatedUserId,
          taskId,
        });
        return res.status(200).json(statusRecord);
      } else {
        appServiceLogger.info(
          `[${operationName}] Task not found or not authorized for user.`,
          { authenticatedUserId, taskId }
        );
        return res
          .status(404)
          .json({ error: 'Task not found or not authorized.' });
      }
    } finally {
      client.release();
      appServiceLogger.debug(`[${operationName}] DB client released.`, {
        authenticatedUserId,
        taskId,
      });
    }
  } catch (error: any) {
    appServiceLogger.error(
      `[${operationName}] Database query or connection failed.`,
      {
        authenticatedUserId,
        taskId,
        error: error.message,
        stack: error.stack,
        details: error,
      }
    );
    return res
      .status(500)
      .json({ error: 'Internal Server Error', details: error.message });
  }
}

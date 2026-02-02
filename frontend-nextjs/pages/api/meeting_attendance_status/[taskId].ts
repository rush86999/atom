import type { NextApiRequest, NextApiResponse } from 'next';
import { Pool } from 'pg';
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";
import { USE_BACKEND_API, meetingAPI } from '../../../lib/api';
import appServiceLogger from '../../../lib/logger';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type MeetingAttendanceStatus = {
  task_id: string;
  user_id: string | null;
  platform: string | null;
  meeting_identifier: string | null;
  status_timestamp: string;
  current_status_message: string;
  final_notion_page_url: string | null;
  error_details: string | null;
  created_at: string;
};

type ErrorResponse = {
  error: string;
  details?: string;
};

let pool: Pool | null = null;

try {
  pool = new Pool();
  appServiceLogger.info('PostgreSQL Pool initialized successfully for meeting_attendance_status API.');
} catch (error: any) {
  appServiceLogger.fatal(
    { error: error.message, stack: error.stack },
    'Failed to initialize PostgreSQL Pool. API will not function correctly.'
  );
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<
    MeetingAttendanceStatus | MeetingAttendanceStatus[] | ErrorResponse
  >
) {
  const operationName = 'getMeetingAttendanceStatus';

  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    appServiceLogger.warn(`[${operationName}] Unauthorized attempt: No active session.`);
    return res.status(401).json({ error: 'Unauthorized. Please log in.' });
  }

  const authenticatedUserId = (session.user as any).id;

  const { taskId } = req.query;

  if (req.method !== 'GET') {
    appServiceLogger.warn(`[${operationName}] Method ${req.method} not allowed.`);
    res.setHeader('Allow', ['GET']);
    return res.status(405).json({ error: `Method ${req.method} Not Allowed` });
  }

  if (!taskId || typeof taskId !== 'string') {
    appServiceLogger.warn(`[${operationName}] Invalid or missing taskId.`);
    return res.status(400).json({ error: 'Task ID is required and must be a string.' });
  }

  // Use backend API if feature flag is enabled
  if (USE_BACKEND_API) {
    try {
      const token = (session as any).backendToken || (session as any).access_token;
      const response = await fetch(`${API_BASE_URL}/api/meetings/attendance/${taskId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        appServiceLogger.info(`[${operationName}] Status found for task: ${taskId} (via API)`);
        return res.status(200).json(data);
      } else if (response.status === 404) {
        appServiceLogger.info(`[${operationName}] Task not found or not authorized for user (via API).`);
        return res.status(404).json({ error: 'Task not found or not authorized.' });
      }
    } catch (error: any) {
      appServiceLogger.warn(`[${operationName}] Backend API error, falling back to direct DB: ${error.message}`);
    }
  }

  // Direct DB query (original implementation)
  if (!pool) {
    appServiceLogger.error(`[${operationName}] PostgreSQL pool not initialized.`);
    return res.status(500).json({ error: 'Database connection not configured.' });
  }

  try {
    const client = await pool.connect();
    appServiceLogger.debug(`[${operationName}] DB client connected.`);
    try {
      const queryText =
        'SELECT * FROM meeting_attendance_status WHERE task_id = $1 AND user_id = $2';
      appServiceLogger.debug(`[${operationName}] Executing query for taskId: ${taskId}`);
      const result = await client.query(queryText, [taskId, authenticatedUserId]);

      if (result.rows.length > 0) {
        const row = result.rows[0];
        const statusRecord: MeetingAttendanceStatus = {
          ...row,
          status_timestamp: new Date(row.status_timestamp).toISOString(),
          created_at: new Date(row.created_at).toISOString(),
        };
        appServiceLogger.info(`[${operationName}] Status found for task: ${taskId}`);
        return res.status(200).json(statusRecord);
      } else {
        appServiceLogger.info(`[${operationName}] Task not found or not authorized for user.`);
        return res.status(404).json({ error: 'Task not found or not authorized.' });
      }
    } finally {
      client.release();
      appServiceLogger.debug(`[${operationName}] DB client released.`);
    }
  } catch (error: any) {
    appServiceLogger.error(
      { error: error.message, stack: error.stack },
      `[${operationName}] Database query or connection failed.`
    );
    return res.status(500).json({ error: 'Internal Server Error', details: error.message });
  }
}

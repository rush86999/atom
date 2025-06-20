import type { NextApiRequest, NextApiResponse } from 'next';
import { Pool } from 'pg';
import { getSession } from 'supertokens-node/nextjs';
import { SessionRequest } from 'supertokens-node/framework/express';
import supertokens from 'supertokens-node';
import { backendConfig } from '../../../config/backendConfig'; // Corrected path

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
} catch (error) {
  console.error("Failed to initialize PostgreSQL Pool or Supertokens:", error);
}


export default async function handler(
  req: NextApiRequest, // SessionRequest is not directly compatible here, NextApiRequest is used by getSession
  res: NextApiResponse<MeetingAttendanceStatus | MeetingAttendanceStatus[] | ErrorResponse>
) {
  if (!pool) {
    console.error("PostgreSQL pool not initialized. Cannot connect to database.");
    return res.status(500).json({ error: 'Database connection not configured.' });
  }

  // Supertokens session verification
  let session;
  try {
    // Cast req to SessionRequest for getSession, or handle compatibility if direct cast is an issue
    // For Next.js, getSession typically takes http.IncomingMessage (which NextApiRequest extends)
    // and http.ServerResponse (which NextApiResponse extends)
    session = await getSession(req as any, res as any, true); // true for checkDatabase
  } catch (error: any) {
    console.error("Supertokens getSession error:", error);
    return res.status(500).json({ error: "Authentication error", details: error.message });
  }

  if (!session) {
    return res.status(401).json({ error: 'Unauthorized. Please log in.' });
  }
  const authenticatedUserId = session.getUserId();

  const { taskId } = req.query;

  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).json({ error: `Method ${req.method} Not Allowed` });
  }

  if (!taskId || typeof taskId !== 'string') {
    return res.status(400).json({ error: 'Task ID is required and must be a string.' });
  }

  if (!taskId || typeof taskId !== 'string') {
    return res.status(400).json({ error: 'Task ID is required and must be a string.' });
  }

  // Ensure pool is available (already checked at the beginning, but good practice if logic were structured differently)

  try {
    const client = await pool.connect();
    try {
      // Modify query to also check for user_id
      const query = 'SELECT * FROM meeting_attendance_status WHERE task_id = $1 AND user_id = $2';
      const result = await client.query(query, [taskId, authenticatedUserId]);

      if (result.rows.length > 0) {
        const row = result.rows[0];
        const statusRecord: MeetingAttendanceStatus = {
            ...row,
            status_timestamp: new Date(row.status_timestamp).toISOString(),
            created_at: new Date(row.created_at).toISOString(),
        };
        return res.status(200).json(statusRecord);
      } else {
        // If no row is found, it means either the task doesn't exist OR it doesn't belong to this user.
        // In either case, 404 is appropriate to avoid revealing existence of tasks for other users.
        return res.status(404).json({ error: 'Task not found or not authorized.' });
      }
    } finally {
      client.release();
    }
  } catch (error: any) {
    console.error(`[Task ${taskId}, User ${authenticatedUserId}]: Database query failed:`, error);
    return res.status(500).json({ error: 'Internal Server Error', details: error.message });
  }
}

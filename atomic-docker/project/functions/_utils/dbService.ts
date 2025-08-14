// atomic-docker/project/functions/_utils/dbService.ts

import { Pool, QueryResult } from 'pg';
import { PendingRequestInfo } from '../sharedAgentState'; // Assuming sharedAgentState.ts is in ../

// Assuming a logger is available or can be imported/passed
// For now, using console for simplicity.
const logger = {
  info: console.log,
  warn: console.warn,
  error: console.error,
};

let pool: Pool;

function getDbPool(): Pool {
  if (!pool) {
    logger.info('[dbService] Creating new PostgreSQL connection pool.');
    pool = new Pool({
      user: process.env.PG_USER || 'postgres', // Default for local dev
      host: process.env.PG_HOST || 'localhost', // Default for local dev
      database: process.env.PG_DATABASE || 'atomic', // Default for local dev
      password: process.env.PG_PASSWORD || 'postgres', // Default for local dev
      port: parseInt(process.env.PG_PORT || '5432', 10), // Default for local dev
      // Other pool options:
      // max: 20, // max number of clients in the pool
      // idleTimeoutMillis: 30000, // how long a client is allowed to remain idle before being closed
      // connectionTimeoutMillis: 2000, // how long to wait for a connection from the pool
    });

    pool.on('connect', (client) => {
      logger.info('[dbService] PostgreSQL client connected to the database.');
      // You can set session parameters here if needed, e.g., client.query('SET TIME ZONE 'UTC';')
    });

    pool.on('error', (err, client) => {
      logger.error(
        '[dbService] Unexpected error on idle PostgreSQL client',
        err
      );
      // Optionally, you might want to handle this more gracefully,
      // e.g., try to re-initialize the pool or exit the process.
      // For now, just logging.
    });
  }
  return pool;
}

// Call getDbPool() once at module load to initialize, or call it in each function.
// Initializing at module load is fine for many serverless/long-running function contexts.
// For very short-lived functions, lazy initialization within each exported function might be considered.
// Let's initialize it here for simplicity.
getDbPool();

export async function addPendingJob(
  jobInfo: PendingRequestInfo
): Promise<void> {
  const query = `
    INSERT INTO pending_scheduling_jobs (file_key, user_id, host_id, singleton_id, original_query, submitted_at, status)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (file_key) DO NOTHING; -- Or DO UPDATE if you want to update existing
  `;
  // Assuming 'status' is not part of PendingRequestInfo yet, default to 'PENDING'
  const values = [
    jobInfo.fileKey,
    jobInfo.userId,
    jobInfo.hostId,
    jobInfo.singletonId,
    jobInfo.originalQuery || null, // Handle optional field
    jobInfo.submittedAt, // Should be a Date object or ISO string
    'PENDING', // Default status
  ];

  try {
    logger.info(
      `[dbService.addPendingJob] Adding job with fileKey: ${jobInfo.fileKey}`
    );
    await getDbPool().query(query, values);
    logger.info(
      `[dbService.addPendingJob] Successfully added/updated job with fileKey: ${jobInfo.fileKey}`
    );
  } catch (error) {
    logger.error(
      `[dbService.addPendingJob] Error adding job with fileKey ${jobInfo.fileKey}:`,
      error
    );
    throw error; // Re-throw to allow caller to handle
  }
}

export async function getPendingJob(
  fileKey: string
): Promise<PendingRequestInfo | null> {
  const query = `
    SELECT file_key, user_id, host_id, singleton_id, original_query, submitted_at
    FROM pending_scheduling_jobs
    WHERE file_key = $1 AND status = 'PENDING'; -- Only retrieve if still pending
  `;
  // Note: status is not part of PendingRequestInfo interface, but used in DB query

  try {
    logger.info(
      `[dbService.getPendingJob] Getting job with fileKey: ${fileKey}`
    );
    const result: QueryResult = await getDbPool().query(query, [fileKey]);
    if (result.rows.length > 0) {
      const row = result.rows[0];
      // Map database row to PendingRequestInfo object
      // Ensure date types are handled correctly (pg library usually returns Date objects for TIMESTAMPTZ)
      return {
        fileKey: row.file_key,
        userId: row.user_id,
        hostId: row.host_id,
        singletonId: row.singleton_id,
        originalQuery: row.original_query,
        submittedAt: new Date(row.submitted_at), // Ensure it's a Date object
      };
    }
    logger.info(
      `[dbService.getPendingJob] No 'PENDING' job found with fileKey: ${fileKey}`
    );
    return null;
  } catch (error) {
    logger.error(
      `[dbService.getPendingJob] Error getting job with fileKey ${fileKey}:`,
      error
    );
    throw error;
  }
}

export async function deletePendingJob(fileKey: string): Promise<void> {
  const query = 'DELETE FROM pending_scheduling_jobs WHERE file_key = $1;';

  try {
    logger.info(
      `[dbService.deletePendingJob] Deleting job with fileKey: ${fileKey}`
    );
    const result = await getDbPool().query(query, [fileKey]);
    if (result.rowCount !== null && result.rowCount > 0) {
      logger.info(
        `[dbService.deletePendingJob] Successfully deleted job with fileKey: ${fileKey}`
      );
    } else {
      logger.warn(
        `[dbService.deletePendingJob] No job found with fileKey ${fileKey} to delete, or delete operation had no effect.`
      );
    }
  } catch (error) {
    logger.error(
      `[dbService.deletePendingJob] Error deleting job with fileKey ${fileKey}:`,
      error
    );
    throw error;
  }
}

// Optional: Function to update status, could be useful later
export async function updatePendingJobStatus(
  fileKey: string,
  status: string
): Promise<void> {
  const query =
    'UPDATE pending_scheduling_jobs SET status = $2 WHERE file_key = $1;';
  try {
    logger.info(
      `[dbService.updatePendingJobStatus] Updating status to '${status}' for fileKey: ${fileKey}`
    );
    const result = await getDbPool().query(query, [fileKey, status]);
    if (result.rowCount !== null && result.rowCount > 0) {
      logger.info(
        `[dbService.updatePendingJobStatus] Successfully updated status for fileKey: ${fileKey}`
      );
    } else {
      logger.warn(
        `[dbService.updatePendingJobStatus] No job found with fileKey ${fileKey} to update status, or status was already set.`
      );
    }
  } catch (error) {
    logger.error(
      `[dbService.updatePendingJobStatus] Error updating status for fileKey ${fileKey}:`,
      error
    );
    throw error;
  }
}

// Optional: Graceful shutdown for the pool (e.g., on application exit)
// This is more relevant for long-running applications, not typically serverless functions
// that might reuse connections across invocations.
export async function closeDbPool(): Promise<void> {
  if (pool) {
    logger.info('[dbService] Closing PostgreSQL connection pool.');
    await pool.end();
    logger.info('[dbService] PostgreSQL connection pool has been closed.');
    // pool = undefined; // Or some way to indicate it's closed if re-creation is possible
  }
}

export interface GitHubTokenInfo {
    userId: string;
    githubUserId: string;
    githubUsername: string;
    accessToken: string;
    refreshToken?: string;
    expiresAt?: Date;
    scopes: string;
}

export async function saveGitHubToken(tokenInfo: GitHubTokenInfo): Promise<void> {
    const query = `
        INSERT INTO user_github_oauth_tokens (user_id, github_user_id, github_username, access_token, refresh_token, expiry_timestamp_ms, scopes_granted)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (user_id) DO UPDATE SET
            github_user_id = EXCLUDED.github_user_id,
            github_username = EXCLUDED.github_username,
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expiry_timestamp_ms = EXCLUDED.expiry_timestamp_ms,
            scopes_granted = EXCLUDED.scopes_granted,
            last_updated_at = NOW() AT TIME ZONE 'UTC';
    `;
    const values = [
        tokenInfo.userId,
        tokenInfo.githubUserId,
        tokenInfo.githubUsername,
        tokenInfo.accessToken,
        tokenInfo.refreshToken,
        tokenInfo.expiresAt ? tokenInfo.expiresAt.getTime() : null,
        tokenInfo.scopes,
    ];

    try {
        await getDbPool().query(query, values);
    } catch (error) {
        logger.error(`[dbService.saveGitHubToken] Error saving GitHub token for user ${tokenInfo.userId}:`, error);
        throw error;
    }
}

export async function getGitHubToken(userId: string): Promise<GitHubTokenInfo | null> {
    const query = `
        SELECT user_id, github_user_id, github_username, access_token, refresh_token, expiry_timestamp_ms, scopes_granted
        FROM user_github_oauth_tokens
        WHERE user_id = $1;
    `;

    try {
        const result: QueryResult = await getDbPool().query(query, [userId]);
        if (result.rows.length > 0) {
            const row = result.rows[0];
            return {
                userId: row.user_id,
                githubUserId: row.github_user_id,
                githubUsername: row.github_username,
                accessToken: row.access_token,
                refreshToken: row.refresh_token,
                expiresAt: row.expiry_timestamp_ms ? new Date(row.expiry_timestamp_ms) : undefined,
                scopes: row.scopes_granted,
            };
        }
        return null;
    } catch (error) {
        logger.error(`[dbService.getGitHubToken] Error getting GitHub token for user ${userId}:`, error);
        throw error;
    }
}

export async function deleteGitHubToken(userId: string): Promise<void> {
    const query = 'DELETE FROM user_github_oauth_tokens WHERE user_id = $1;';

    try {
        await getDbPool().query(query, [userId]);
    } catch (error) {
        logger.error(`[dbService.deleteGitHubToken] Error deleting GitHub token for user ${userId}:`, error);
        throw error;
    }
}

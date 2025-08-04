// atomic-docker/project/functions/_utils/dbService.ts
import { Pool } from 'pg';
// Assuming a logger is available or can be imported/passed
// For now, using console for simplicity.
const logger = {
    info: console.log,
    warn: console.warn,
    error: console.error,
};
let pool;
function getDbPool() {
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
            logger.error('[dbService] Unexpected error on idle PostgreSQL client', err);
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
export async function addPendingJob(jobInfo) {
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
        logger.info(`[dbService.addPendingJob] Adding job with fileKey: ${jobInfo.fileKey}`);
        await getDbPool().query(query, values);
        logger.info(`[dbService.addPendingJob] Successfully added/updated job with fileKey: ${jobInfo.fileKey}`);
    }
    catch (error) {
        logger.error(`[dbService.addPendingJob] Error adding job with fileKey ${jobInfo.fileKey}:`, error);
        throw error; // Re-throw to allow caller to handle
    }
}
export async function getPendingJob(fileKey) {
    const query = `
    SELECT file_key, user_id, host_id, singleton_id, original_query, submitted_at
    FROM pending_scheduling_jobs
    WHERE file_key = $1 AND status = 'PENDING'; -- Only retrieve if still pending
  `;
    // Note: status is not part of PendingRequestInfo interface, but used in DB query
    try {
        logger.info(`[dbService.getPendingJob] Getting job with fileKey: ${fileKey}`);
        const result = await getDbPool().query(query, [fileKey]);
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
        logger.info(`[dbService.getPendingJob] No 'PENDING' job found with fileKey: ${fileKey}`);
        return null;
    }
    catch (error) {
        logger.error(`[dbService.getPendingJob] Error getting job with fileKey ${fileKey}:`, error);
        throw error;
    }
}
export async function deletePendingJob(fileKey) {
    const query = 'DELETE FROM pending_scheduling_jobs WHERE file_key = $1;';
    try {
        logger.info(`[dbService.deletePendingJob] Deleting job with fileKey: ${fileKey}`);
        const result = await getDbPool().query(query, [fileKey]);
        if (result.rowCount !== null && result.rowCount > 0) {
            logger.info(`[dbService.deletePendingJob] Successfully deleted job with fileKey: ${fileKey}`);
        }
        else {
            logger.warn(`[dbService.deletePendingJob] No job found with fileKey ${fileKey} to delete, or delete operation had no effect.`);
        }
    }
    catch (error) {
        logger.error(`[dbService.deletePendingJob] Error deleting job with fileKey ${fileKey}:`, error);
        throw error;
    }
}
// Optional: Function to update status, could be useful later
export async function updatePendingJobStatus(fileKey, status) {
    const query = 'UPDATE pending_scheduling_jobs SET status = $2 WHERE file_key = $1;';
    try {
        logger.info(`[dbService.updatePendingJobStatus] Updating status to '${status}' for fileKey: ${fileKey}`);
        const result = await getDbPool().query(query, [fileKey, status]);
        if (result.rowCount !== null && result.rowCount > 0) {
            logger.info(`[dbService.updatePendingJobStatus] Successfully updated status for fileKey: ${fileKey}`);
        }
        else {
            logger.warn(`[dbService.updatePendingJobStatus] No job found with fileKey ${fileKey} to update status, or status was already set.`);
        }
    }
    catch (error) {
        logger.error(`[dbService.updatePendingJobStatus] Error updating status for fileKey ${fileKey}:`, error);
        throw error;
    }
}
// Optional: Graceful shutdown for the pool (e.g., on application exit)
// This is more relevant for long-running applications, not typically serverless functions
// that might reuse connections across invocations.
export async function closeDbPool() {
    if (pool) {
        logger.info('[dbService] Closing PostgreSQL connection pool.');
        await pool.end();
        logger.info('[dbService] PostgreSQL connection pool has been closed.');
        // pool = undefined; // Or some way to indicate it's closed if re-creation is possible
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGJTZXJ2aWNlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGJTZXJ2aWNlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLHNEQUFzRDtBQUV0RCxPQUFPLEVBQUUsSUFBSSxFQUFlLE1BQU0sSUFBSSxDQUFDO0FBR3ZDLDJEQUEyRDtBQUMzRCx5Q0FBeUM7QUFDekMsTUFBTSxNQUFNLEdBQUc7SUFDYixJQUFJLEVBQUUsT0FBTyxDQUFDLEdBQUc7SUFDakIsSUFBSSxFQUFFLE9BQU8sQ0FBQyxJQUFJO0lBQ2xCLEtBQUssRUFBRSxPQUFPLENBQUMsS0FBSztDQUNyQixDQUFDO0FBRUYsSUFBSSxJQUFVLENBQUM7QUFFZixTQUFTLFNBQVM7SUFDaEIsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO1FBQ1YsTUFBTSxDQUFDLElBQUksQ0FBQyxzREFBc0QsQ0FBQyxDQUFDO1FBQ3BFLElBQUksR0FBRyxJQUFJLElBQUksQ0FBQztZQUNkLElBQUksRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLE9BQU8sSUFBSSxVQUFVLEVBQUUsd0JBQXdCO1lBQ2pFLElBQUksRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLE9BQU8sSUFBSSxXQUFXLEVBQUUsd0JBQXdCO1lBQ2xFLFFBQVEsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLFdBQVcsSUFBSSxRQUFRLEVBQUUsd0JBQXdCO1lBQ3ZFLFFBQVEsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLFdBQVcsSUFBSSxVQUFVLEVBQUUsd0JBQXdCO1lBQ3pFLElBQUksRUFBRSxRQUFRLENBQUMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxPQUFPLElBQUksTUFBTSxFQUFFLEVBQUUsQ0FBQyxFQUFFLHdCQUF3QjtZQUMzRSxzQkFBc0I7WUFDdEIsZ0RBQWdEO1lBQ2hELCtGQUErRjtZQUMvRixvRkFBb0Y7U0FDckYsQ0FBQyxDQUFDO1FBRUgsSUFBSSxDQUFDLEVBQUUsQ0FBQyxTQUFTLEVBQUUsQ0FBQyxNQUFNLEVBQUUs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Q0FBQyxPQUFPLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQztRQUNqRSxJQUFJLE1BQU0sQ0FBQyxRQUFRLEtBQUssSUFBSSxJQUFJLE1BQU0sQ0FBQyxRQUFRLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDcEQsTUFBTSxDQUFDLElBQUksQ0FDVCwrRUFBK0UsT0FBTyxFQUFFLENBQ3pGLENBQUM7UUFDSixDQUFDO2FBQU0sQ0FBQztZQUNOLE1BQU0sQ0FBQyxJQUFJLENBQ1QsZ0VBQWdFLE9BQU8sK0NBQStDLENBQ3ZILENBQUM7UUFDSixDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixNQUFNLENBQUMsS0FBSyxDQUNWLHdFQUF3RSxPQUFPLEdBQUcsRUFDbEYsS0FBSyxDQUNOLENBQUM7UUFDRixNQUFNLEtBQUssQ0FBQztJQUNkLENBQUM7QUFDSCxDQUFDO0FBRUQsdUVBQXVFO0FBQ3ZFLDBGQUEwRjtBQUMxRixtREFBbUQ7QUFDbkQsTUFBTSxDQUFDLEtBQUssVUFBVSxXQUFXO0lBQy9CLElBQUksSUFBSSxFQUFFLENBQUM7UUFDVCxNQUFNLENBQUMsSUFBSSxDQUFDLGlEQUFpRCxDQUFDLENBQUM7UUFDL0QsTUFBTSxJQUFJLENBQUMsR0FBRyxFQUFFLENBQUM7UUFDakIsTUFBTSxDQUFDLElBQUksQ0FBQyx5REFBeUQsQ0FBQyxDQUFDO1FBQ3ZFLHNGQUFzRjtJQUN4RixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIGF0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2RiU2VydmljZS50c1xuXG5pbXBvcnQgeyBQb29sLCBRdWVyeVJlc3VsdCB9IGZyb20gJ3BnJztcbmltcG9ydCB7IFBlbmRpbmdSZXF1ZXN0SW5mbyB9IGZyb20gJy4uL3NoYXJlZEFnZW50U3RhdGUnOyAvLyBBc3N1bWluZyBzaGFyZWRBZ2VudFN0YXRlLnRzIGlzIGluIC4uL1xuXG4vLyBBc3N1bWluZyBhIGxvZ2dlciBpcyBhdmFpbGFibGUgb3IgY2FuIGJlIGltcG9ydGVkL3Bhc3NlZFxuLy8gRm9yIG5vdywgdXNpbmcgY29uc29sZSBmb3Igc2ltcGxpY2l0eS5cbmNvbnN0IGxvZ2dlciA9IHtcbiAgaW5mbzogY29uc29sZS5sb2csXG4gIHdhcm46IGNvbnNvbGUud2FybixcbiAgZXJyb3I6IGNvbnNvbGUuZXJyb3IsXG59O1xuXG5sZXQgcG9vbDogUG9vbDtcblxuZnVuY3Rpb24gZ2V0RGJQb29sKCk6IFBvb2wge1xuICBpZiAoIXBvb2wpIHtcbiAgICBsb2dnZXIuaW5mbygnW2RiU2VydmljZV0gQ3JlYXRpbmcgbmV3IFBvc3RncmVTUUwgY29ubmVjdGlvbiBwb29sLicpO1xuICAgIHBvb2wgPSBuZXcgUG9vbCh7XG4gICAgICB1c2VyOiBwcm9jZXNzLmVudi5QR19VU0VSIHx8ICdwb3N0Z3JlcycsIC8vIERlZmF1bHQgZm9yIGxvY2FsIGRldlxuICAgICAgaG9zdDogcHJvY2Vzcy5lbnYuUEdfSE9TVCB8fCAnbG9jYWxob3N0JywgLy8gRGVmYXVsdCBmb3IgbG9jYWwgZGV2XG4gICAgICBkYXRhYmFzZTogcHJvY2Vzcy5lbnYuUEdfREFUQUJBU0UgfHwgJ2F0b21pYycsIC8vIERlZmF1bHQgZm9yIGxvY2FsIGRldlxuICAgICAgcGFzc3dvcmQ6IHByb2Nlc3MuZW52LlBHX1BBU1NXT1JEIHx8ICdwb3N0Z3JlcycsIC8vIERlZmF1bHQgZm9yIGxvY2FsIGRldlxuICAgICAgcG9ydDogcGFyc2VJbnQocHJvY2Vzcy5lbnYuUEdfUE9SVCB8fCAnNTQzMicsIDEwKSwgLy8gRGVmYXVsdCBmb3IgbG9jYWwgZGV2XG4gICAgICAvLyBPdGhlciBwb29sIG9wdGlvbnM6XG4gICAgICAvLyBtYXg6IDIwLCAvLyBtYXggbnVtYmVyIG9mIGNsaWVudHMgaW4gdGhlIHBvb2xcbiAgICAgIC8vIGlkbGVUaW1lb3V0TWlsbGlzOiAzMDAwMCwgLy8gaG93IGxvbmcgYSBjbGllbnQgaXMgYWxsb3dlZCB0byByZW1haW4gaWRsZSBiZWZvcmUgYmVpbmcgY2xvc2VkXG4gICAgICAvLyBjb25uZWN0aW9uVGltZW91dE1pbGxpczogMjAwMCwgLy8gaG93IGxvbmcgdG8gd2FpdCBmb3IgYSBjb25uZWN0aW9uIGZyb20gdGhlIHBvb2xcbiAgICB9KTtcblxuICAgIHBvb2wub24oJ2Nvbm5lY3QnLCAoY2xpZW50KSA9PiB7XG4gICAgICBsb2dnZXIuaW5mbygnW2RiU2VydmljZV0gUG9zdGdyZVNRTCBjbGllbnQgY29ubmVjdGVkIHRvIHRoZSBkYXRhYmFzZS4nKTtcbiAgICAgIC8vIFlvdSBjYW4gc2V0IHNlc3Npb24gcGFyYW1ldGVycyBoZXJlIGlmIG5lZWRlZCwgZS5nLiwgY2xpZW50LnF1ZXJ5KCdTRVQgVElNRSBaT05FICdVVEMnOycpXG4gICAgfSk7XG5cbiAgICBwb29sLm9uKCdlcnJvcicsIChlcnIsIGNsaWVudCkgPT4ge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAnW2RiU2VydmljZV0gVW5leHBlY3RlZCBlcnJvciBvbiBpZGxlIFBvc3RncmVTUUwgY2xpZW50JyxcbiAgICAgICAgZXJyXG4gICAgICApO1xuICAgICAgLy8gT3B0aW9uYWxseSwgeW91IG1pZ2h0IHdhbnQgdG8gaGFuZGxlIHRoaXMgbW9yZSBncmFjZWZ1bGx5LFxuICAgICAgLy8gZS5nLiwgdHJ5IHRvIHJlLWluaXRpYWxpemUgdGhlIHBvb2wgb3IgZXhpdCB0aGUgcHJvY2Vzcy5cbiAgICAgIC8vIEZvciBub3csIGp1c3QgbG9nZ2luZy5cbiAgICB9KTtcbiAgfVxuICByZXR1cm4gcG9vbDtcbn1cblxuLy8gQ2FsbCBnZXREYlBvb2woKSBvbmNlIGF0IG1vZHVsZSBsb2FkIHRvIGluaXRpYWxpemUsIG9yIGNhbGwgaXQgaW4gZWFjaCBmdW5jdGlvbi5cbi8vIEluaXRpYWxpemluZyBhdCBtb2R1bGUgbG9hZCBpcyBmaW5lIGZvciBtYW55IHNlcnZlcmxlc3MvbG9uZy1ydW5uaW5nIGZ1bmN0aW9uIGNvbnRleHRzLlxuLy8gRm9yIHZlcnkgc2hvcnQtbGl2ZWQgZnVuY3Rpb25zLCBsYXp5IGluaXRpYWxpemF0aW9uIHdpdGhpbiBlYWNoIGV4cG9ydGVkIGZ1bmN0aW9uIG1pZ2h0IGJlIGNvbnNpZGVyZWQuXG4vLyBMZXQncyBpbml0aWFsaXplIGl0IGhlcmUgZm9yIHNpbXBsaWNpdHkuXG5nZXREYlBvb2woKTtcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGFkZFBlbmRpbmdKb2IoXG4gIGpvYkluZm86IFBlbmRpbmdSZXF1ZXN0SW5mb1xuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGNvbnN0IHF1ZXJ5ID0gYFxuICAgIElOU0VSVCBJTlRPIHBlbmRpbmdfc2NoZWR1bGluZ19qb2JzIChmaWxlX2tleSwgdXNlcl9pZCwgaG9zdF9pZCwgc2luZ2xldG9uX2lkLCBvcmlnaW5hbF9xdWVyeSwgc3VibWl0dGVkX2F0LCBzdGF0dXMpXG4gICAgVkFMVUVTICgkMSwgJDIsICQzLCAkNCwgJDUsICQ2LCAkNylcbiAgICBPTiBDT05GTElDVCAoZmlsZV9rZXkpIERPIE5PVEhJTkc7IC0tIE9yIERPIFVQREFURSBpZiB5b3Ugd2FudCB0byB1cGRhdGUgZXhpc3RpbmdcbiAgYDtcbiAgLy8gQXNzdW1pbmcgJ3N0YXR1cycgaXMgbm90IHBhcnQgb2YgUGVuZGluZ1JlcXVlc3RJbmZvIHlldCwgZGVmYXVsdCB0byAnUEVORElORydcbiAgY29uc3QgdmFsdWVzID0gW1xuICAgIGpvYkluZm8uZmlsZUtleSxcbiAgICBqb2JJbmZvLnVzZXJJZCxcbiAgICBqb2JJbmZvLmhvc3RJZCxcbiAgICBqb2JJbmZvLnNpbmdsZXRvbklkLFxuICAgIGpvYkluZm8ub3JpZ2luYWxRdWVyeSB8fCBudWxsLCAvLyBIYW5kbGUgb3B0aW9uYWwgZmllbGRcbiAgICBqb2JJbmZvLnN1Ym1pdHRlZEF0LCAvLyBTaG91bGQgYmUgYSBEYXRlIG9iamVjdCBvciBJU08gc3RyaW5nXG4gICAgJ1BFTkRJTkcnLCAvLyBEZWZhdWx0IHN0YXR1c1xuICBdO1xuXG4gIHRyeSB7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2RiU2VydmljZS5hZGRQZW5kaW5nSm9iXSBBZGRpbmcgam9iIHdpdGggZmlsZUtleTogJHtqb2JJbmZvLmZpbGVLZXl9YFxuICAgICk7XG4gICAgYXdhaXQgZ2V0RGJQb29sKCkucXVlcnkocXVlcnksIHZhbHVlcyk7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2RiU2VydmljZS5hZGRQZW5kaW5nSm9iXSBTdWNjZXNzZnVsbHkgYWRkZWQvdXBkYXRlZCBqb2Igd2l0aCBmaWxlS2V5OiAke2pvYkluZm8uZmlsZUtleX1gXG4gICAgKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW2RiU2VydmljZS5hZGRQZW5kaW5nSm9iXSBFcnJvciBhZGRpbmcgam9iIHdpdGggZmlsZUtleSAke2pvYkluZm8uZmlsZUtleX06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICB0aHJvdyBlcnJvcjsgLy8gUmUtdGhyb3cgdG8gYWxsb3cgY2FsbGVyIHRvIGhhbmRsZVxuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRQZW5kaW5nSm9iKFxuICBmaWxlS2V5OiBzdHJpbmdcbik6IFByb21pc2U8UGVuZGluZ1JlcXVlc3RJbmZvIHwgbnVsbD4ge1xuICBjb25zdCBxdWVyeSA9IGBcbiAgICBTRUxFQ1QgZmlsZV9rZXksIHVzZXJfaWQsIGhvc3RfaWQsIHNpbmdsZXRvbl9pZCwgb3JpZ2luYWxfcXVlcnksIHN1Ym1pdHRlZF9hdFxuICAgIEZST00gcGVuZGluZ19zY2hlZHVsaW5nX2pvYnNcbiAgICBXSEVSRSBmaWxlX2tleSA9ICQxIEFORCBzdGF0dXMgPSAnUEVORElORyc7IC0tIE9ubHkgcmV0cmlldmUgaWYgc3RpbGwgcGVuZGluZ1xuICBgO1xuICAvLyBOb3RlOiBzdGF0dXMgaXMgbm90IHBhcnQgb2YgUGVuZGluZ1JlcXVlc3RJbmZvIGludGVyZmFjZSwgYnV0IHVzZWQgaW4gREIgcXVlcnlcblxuICB0cnkge1xuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtkYlNlcnZpY2UuZ2V0UGVuZGluZ0pvYl0gR2V0dGluZyBqb2Igd2l0aCBmaWxlS2V5OiAke2ZpbGVLZXl9YFxuICAgICk7XG4gICAgY29uc3QgcmVzdWx0OiBRdWVyeVJlc3VsdCA9IGF3YWl0IGdldERiUG9vbCgpLnF1ZXJ5KHF1ZXJ5LCBbZmlsZUtleV0pO1xuICAgIGlmIChyZXN1bHQucm93cy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCByb3cgPSByZXN1bHQucm93c1swXTtcbiAgICAgIC8vIE1hcCBkYXRhYmFzZSByb3cgdG8gUGVuZGluZ1JlcXVlc3RJbmZvIG9iamVjdFxuICAgICAgLy8gRW5zdXJlIGRhdGUgdHlwZXMgYXJlIGhhbmRsZWQgY29ycmVjdGx5IChwZyBsaWJyYXJ5IHVzdWFsbHkgcmV0dXJucyBEYXRlIG9iamVjdHMgZm9yIFRJTUVTVEFNUFRaKVxuICAgICAgcmV0dXJuIHtcbiAgICAgICAgZmlsZUtleTogcm93LmZpbGVfa2V5LFxuICAgICAgICB1c2VySWQ6IHJvdy51c2VyX2lkLFxuICAgICAgICBob3N0SWQ6IHJvdy5ob3N0X2lkLFxuICAgICAgICBzaW5nbGV0b25JZDogcm93LnNpbmdsZXRvbl9pZCxcbiAgICAgICAgb3JpZ2luYWxRdWVyeTogcm93Lm9yaWdpbmFsX3F1ZXJ5LFxuICAgICAgICBzdWJtaXR0ZWRBdDogbmV3IERhdGUocm93LnN1Ym1pdHRlZF9hdCksIC8vIEVuc3VyZSBpdCdzIGEgRGF0ZSBvYmplY3RcbiAgICAgIH07XG4gICAgfVxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtkYlNlcnZpY2UuZ2V0UGVuZGluZ0pvYl0gTm8gJ1BFTkRJTkcnIGpvYiBmb3VuZCB3aXRoIGZpbGVLZXk6ICR7ZmlsZUtleX1gXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW2RiU2VydmljZS5nZXRQZW5kaW5nSm9iXSBFcnJvciBnZXR0aW5nIGpvYiB3aXRoIGZpbGVLZXkgJHtmaWxlS2V5fTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHRocm93IGVycm9yO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBkZWxldGVQZW5kaW5nSm9iKGZpbGVLZXk6IHN0cmluZyk6IFByb21pc2U8dm9pZD4ge1xuICBjb25zdCBxdWVyeSA9ICdERUxFVEUgRlJPTSBwZW5kaW5nX3NjaGVkdWxpbmdfam9icyBXSEVSRSBmaWxlX2tleSA9ICQxOyc7XG5cbiAgdHJ5IHtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbZGJTZXJ2aWNlLmRlbGV0ZVBlbmRpbmdKb2JdIERlbGV0aW5nIGpvYiB3aXRoIGZpbGVLZXk6ICR7ZmlsZUtleX1gXG4gICAgKTtcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBnZXREYlBvb2woKS5xdWVyeShxdWVyeSwgW2ZpbGVLZXldKTtcbiAgICBpZiAocmVzdWx0LnJvd0NvdW50ICE9PSBudWxsICYmIHJlc3VsdC5yb3dDb3VudCA+IDApIHtcbiAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICBgW2RiU2VydmljZS5kZWxldGVQZW5kaW5nSm9iXSBTdWNjZXNzZnVsbHkgZGVsZXRlZCBqb2Igd2l0aCBmaWxlS2V5OiAke2ZpbGVLZXl9YFxuICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbZGJTZXJ2aWNlLmRlbGV0ZVBlbmRpbmdKb2JdIE5vIGpvYiBmb3VuZCB3aXRoIGZpbGVLZXkgJHtmaWxlS2V5fSB0byBkZWxldGUsIG9yIGRlbGV0ZSBvcGVyYXRpb24gaGFkIG5vIGVmZmVjdC5gXG4gICAgICApO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW2RiU2VydmljZS5kZWxldGVQZW5kaW5nSm9iXSBFcnJvciBkZWxldGluZyBqb2Igd2l0aCBmaWxlS2V5ICR7ZmlsZUtleX06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICB0aHJvdyBlcnJvcjtcbiAgfVxufVxuXG4vLyBPcHRpb25hbDogRnVuY3Rpb24gdG8gdXBkYXRlIHN0YXR1cywgY291bGQgYmUgdXNlZnVsIGxhdGVyXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdXBkYXRlUGVuZGluZ0pvYlN0YXR1cyhcbiAgZmlsZUtleTogc3RyaW5nLFxuICBzdGF0dXM6IHN0cmluZ1xuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGNvbnN0IHF1ZXJ5ID1cbiAgICAnVVBEQVRFIHBlbmRpbmdfc2NoZWR1bGluZ19qb2JzIFNFVCBzdGF0dXMgPSAkMiBXSEVSRSBmaWxlX2tleSA9ICQxOyc7XG4gIHRyeSB7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2RiU2VydmljZS51cGRhdGVQZW5kaW5nSm9iU3RhdHVzXSBVcGRhdGluZyBzdGF0dXMgdG8gJyR7c3RhdHVzfScgZm9yIGZpbGVLZXk6ICR7ZmlsZUtleX1gXG4gICAgKTtcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBnZXREYlBvb2woKS5xdWVyeShxdWVyeSwgW2ZpbGVLZXksIHN0YXR1c10pO1xuICAgIGlmIChyZXN1bHQucm93Q291bnQgIT09IG51bGwgJiYgcmVzdWx0LnJvd0NvdW50ID4gMCkge1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbZGJTZXJ2aWNlLnVwZGF0ZVBlbmRpbmdKb2JTdGF0dXNdIFN1Y2Nlc3NmdWxseSB1cGRhdGVkIHN0YXR1cyBmb3IgZmlsZUtleTogJHtmaWxlS2V5fWBcbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW2RiU2VydmljZS51cGRhdGVQZW5kaW5nSm9iU3RhdHVzXSBObyBqb2IgZm91bmQgd2l0aCBmaWxlS2V5ICR7ZmlsZUtleX0gdG8gdXBkYXRlIHN0YXR1cywgb3Igc3RhdHVzIHdhcyBhbHJlYWR5IHNldC5gXG4gICAgICApO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW2RiU2VydmljZS51cGRhdGVQZW5kaW5nSm9iU3RhdHVzXSBFcnJvciB1cGRhdGluZyBzdGF0dXMgZm9yIGZpbGVLZXkgJHtmaWxlS2V5fTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHRocm93IGVycm9yO1xuICB9XG59XG5cbi8vIE9wdGlvbmFsOiBHcmFjZWZ1bCBzaHV0ZG93biBmb3IgdGhlIHBvb2wgKGUuZy4sIG9uIGFwcGxpY2F0aW9uIGV4aXQpXG4vLyBUaGlzIGlzIG1vcmUgcmVsZXZhbnQgZm9yIGxvbmctcnVubmluZyBhcHBsaWNhdGlvbnMsIG5vdCB0eXBpY2FsbHkgc2VydmVybGVzcyBmdW5jdGlvbnNcbi8vIHRoYXQgbWlnaHQgcmV1c2UgY29ubmVjdGlvbnMgYWNyb3NzIGludm9jYXRpb25zLlxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNsb3NlRGJQb29sKCk6IFByb21pc2U8dm9pZD4ge1xuICBpZiAocG9vbCkge1xuICAgIGxvZ2dlci5pbmZvKCdbZGJTZXJ2aWNlXSBDbG9zaW5nIFBvc3RncmVTUUwgY29ubmVjdGlvbiBwb29sLicpO1xuICAgIGF3YWl0IHBvb2wuZW5kKCk7XG4gICAgbG9nZ2VyLmluZm8oJ1tkYlNlcnZpY2VdIFBvc3RncmVTUUwgY29ubmVjdGlvbiBwb29sIGhhcyBiZWVuIGNsb3NlZC4nKTtcbiAgICAvLyBwb29sID0gdW5kZWZpbmVkOyAvLyBPciBzb21lIHdheSB0byBpbmRpY2F0ZSBpdCdzIGNsb3NlZCBpZiByZS1jcmVhdGlvbiBpcyBwb3NzaWJsZVxuICB9XG59XG4iXX0=
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const pg_1 = require("pg");
const nextjs_1 = require("supertokens-node/nextjs");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../config/backendConfig"); // Corrected path
const logger_1 = __importDefault(require("../../../lib/logger")); // Import the shared logger
// Initialize PostgreSQL pool
// Connection parameters will be sourced from environment variables:
// PGHOST, PGUSER, PGDATABASE, PGPASSWORD, PGPORT
let pool = null;
try {
    supertokens_node_1.default.init((0, backendConfig_1.backendConfig)()); // Initialize Supertokens
    pool = new pg_1.Pool(); // Reads environment variables automatically
    logger_1.default.info('PostgreSQL Pool and Supertokens initialized successfully for meeting_attendance_status API.');
}
catch (error) {
    logger_1.default.fatal({ error: error.message, stack: error.stack, details: error }, 'Failed to initialize PostgreSQL Pool or Supertokens. API will not function correctly.');
    // If pool init fails, subsequent calls will also fail the !pool check.
}
async function handler(req, res) {
    const operationName = 'getMeetingAttendanceStatus'; // For logging
    if (!pool) {
        logger_1.default.error(`[${operationName}] PostgreSQL pool not initialized. Cannot connect to database.`);
        return res
            .status(500)
            .json({ error: 'Database connection not configured.' });
    }
    let session;
    try {
        session = await (0, nextjs_1.getSession)(req, res, true);
    }
    catch (error) {
        logger_1.default.error(`[${operationName}] Supertokens getSession error.`, {
            error: error.message,
            stack: error.stack,
            details: error,
        });
        return res
            .status(500)
            .json({ error: 'Authentication error', details: error.message });
    }
    if (!session) {
        logger_1.default.warn(`[${operationName}] Unauthorized attempt: No active session.`);
        return res.status(401).json({ error: 'Unauthorized. Please log in.' });
    }
    const authenticatedUserId = session.getUserId();
    logger_1.default.info(`[${operationName}] Request received for user.`, {
        authenticatedUserId,
        taskId: req.query.taskId,
    });
    const { taskId } = req.query;
    if (req.method !== 'GET') {
        logger_1.default.warn(`[${operationName}] Method not allowed.`, {
            method: req.method,
            authenticatedUserId,
            taskId,
        });
        res.setHeader('Allow', ['GET']);
        return res.status(405).json({ error: `Method ${req.method} Not Allowed` });
    }
    if (!taskId || typeof taskId !== 'string') {
        logger_1.default.warn(`[${operationName}] Invalid or missing taskId.`, {
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
        logger_1.default.debug(`[${operationName}] DB client connected.`, {
            authenticatedUserId,
            taskId,
        });
        try {
            const queryText = 'SELECT * FROM meeting_attendance_status WHERE task_id = $1 AND user_id = $2';
            logger_1.default.debug(`[${operationName}] Executing query.`, {
                queryText,
                params: [taskId, authenticatedUserId],
            });
            const result = await client.query(queryText, [
                taskId,
                authenticatedUserId,
            ]);
            if (result.rows.length > 0) {
                const row = result.rows[0];
                const statusRecord = {
                    ...row,
                    status_timestamp: new Date(row.status_timestamp).toISOString(),
                    created_at: new Date(row.created_at).toISOString(),
                };
                logger_1.default.info(`[${operationName}] Status found for task.`, {
                    authenticatedUserId,
                    taskId,
                });
                return res.status(200).json(statusRecord);
            }
            else {
                logger_1.default.info(`[${operationName}] Task not found or not authorized for user.`, { authenticatedUserId, taskId });
                return res
                    .status(404)
                    .json({ error: 'Task not found or not authorized.' });
            }
        }
        finally {
            client.release();
            logger_1.default.debug(`[${operationName}] DB client released.`, {
                authenticatedUserId,
                taskId,
            });
        }
    }
    catch (error) {
        logger_1.default.error(`[${operationName}] Database query or connection failed.`, {
            authenticatedUserId,
            taskId,
            error: error.message,
            stack: error.stack,
            details: error,
        });
        return res
            .status(500)
            .json({ error: 'Internal Server Error', details: error.message });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiW3Rhc2tJZF0uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJbdGFza0lkXS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQThDQSwwQkErSEM7QUE1S0QsMkJBQTBCO0FBQzFCLG9EQUFxRDtBQUVyRCx3RUFBMkM7QUFDM0MsaUVBQThELENBQUMsaUJBQWlCO0FBQ2hGLGlFQUFtRCxDQUFDLDJCQUEyQjtBQXFCL0UsNkJBQTZCO0FBQzdCLG9FQUFvRTtBQUNwRSxpREFBaUQ7QUFDakQsSUFBSSxJQUFJLEdBQWdCLElBQUksQ0FBQztBQUU3QixJQUFJLENBQUM7SUFDSCwwQkFBVyxDQUFDLElBQUksQ0FBQyxJQUFBLDZCQUFhLEdBQUUsQ0FBQyxDQUFDLENBQUMseUJBQXlCO0lBQzVELElBQUksR0FBRyxJQUFJLFNBQUksRUFBRSxDQUFDLENBQUMsNENBQTRDO0lBQy9ELGdCQUFnQixDQUFDLElBQUksQ0FDbkIsNkZBQTZGLENBQzlGLENBQUM7QUFDSixDQUFDO0FBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztJQUNwQixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLEVBQUUsS0FBSyxFQUFFLEtBQUssQ0FBQyxPQUFPLEVBQUUsS0FBSyxFQUFFLEtBQUssQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUM1RCx1RkFBdUYsQ0FDeEYsQ0FBQztJQUNGLHVFQUF1RTtBQUN6RSxDQUFDO0FBRWMsS0FBSyxVQUFVLE9BQU8sQ0FDbkMsR0FBbUIsRUFDbkIsR0FFQztJQUVELE1BQU0sYUFBYSxHQUFHLDRCQUE0QixDQUFDLENBQUMsY0FBYztJQUVsRSxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDVixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSxnRUFBZ0UsQ0FDbEYsQ0FBQztRQUNGLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxLQUFLLEVBQUUscUNBQXFDLEVB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QUM7UUFDTCxDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsZ0JBQWdCLENBQUMsS0FBSyxDQUNwQixJQUFJLGFBQWEsd0NBQXdDLEVBQ3pEO1lBQ0UsbUJBQW1CO1lBQ25CLE1BQU07WUFDTixLQUFLLEVBQUUsS0FBSyxDQUFDLE9BQU87WUFDcEIsS0FBSyxFQUFFLEtBQUssQ0FBQyxLQUFLO1lBQ2xCLE9BQU8sRUFBRSxLQUFLO1NBQ2YsQ0FDRixDQUFDO1FBQ0YsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSx1QkFBdUIsRUFBRSxPQUFPLEVBQUUsS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDLENBQUM7SUFDdEUsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7IFBvb2wgfSBmcm9tICdwZyc7XG5pbXBvcnQgeyBnZXRTZXNzaW9uIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9uZXh0anMnO1xuaW1wb3J0IHsgU2Vzc2lvblJlcXVlc3QgfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL2ZyYW1ld29yay9leHByZXNzJzsgLy8gTWF5IG5vdCBiZSBuZWVkZWQgaWYgZ2V0U2Vzc2lvbiB3b3JrcyBkaXJlY3RseSB3aXRoIE5leHRBcGlSZXF1ZXN0XG5pbXBvcnQgc3VwZXJ0b2tlbnMgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSc7XG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnLi4vLi4vLi4vY29uZmlnL2JhY2tlbmRDb25maWcnOyAvLyBDb3JyZWN0ZWQgcGF0aFxuaW1wb3J0IGFwcFNlcnZpY2VMb2dnZXIgZnJvbSAnLi4vLi4vLi4vbGliL2xvZ2dlcic7IC8vIEltcG9ydCB0aGUgc2hhcmVkIGxvZ2dlclxuXG4vLyBEZWZpbmUgYSB0eXBlIGZvciB0aGUgZXhwZWN0ZWQgcmVzcG9uc2UgZGF0YVxuLy8gVGhpcyBzaG91bGQgbWF0Y2ggdGhlIHN0cnVjdHVyZSBvZiB5b3VyIG1lZXRpbmdfYXR0ZW5kYW5jZV9zdGF0dXMgdGFibGVcbnR5cGUgTWVldGluZ0F0dGVuZGFuY2VTdGF0dXMgPSB7XG4gIHRhc2tfaWQ6IHN0cmluZztcbiAgdXNlcl9pZDogc3RyaW5nIHwgbnVsbDtcbiAgcGxhdGZvcm06IHN0cmluZyB8IG51bGw7XG4gIG1lZXRpbmdfaWRlbnRpZmllcjogc3RyaW5nIHwgbnVsbDtcbiAgc3RhdHVzX3RpbWVzdGFtcDogc3RyaW5nOyAvLyBUSU1FU1RBTVBUWiB3aWxsIGxpa2VseSBiZSBhIHN0cmluZ1xuICBjdXJyZW50X3N0YXR1c19tZXNzYWdlOiBzdHJpbmc7XG4gIGZpbmFsX25vdGlvbl9wYWdlX3VybDogc3RyaW5nIHwgbnVsbDtcbiAgZXJyb3JfZGV0YWlsczogc3RyaW5nIHwgbnVsbDtcbiAgY3JlYXRlZF9hdDogc3RyaW5nOyAvLyBUSU1FU1RBTVBUWiB3aWxsIGxpa2VseSBiZSBhIHN0cmluZ1xufTtcblxudHlwZSBFcnJvclJlc3BvbnNlID0ge1xuICBlcnJvcjogc3RyaW5nO1xuICBkZXRhaWxzPzogc3RyaW5nO1xufTtcblxuLy8gSW5pdGlhbGl6ZSBQb3N0Z3JlU1FMIHBvb2xcbi8vIENvbm5lY3Rpb24gcGFyYW1ldGVycyB3aWxsIGJlIHNvdXJjZWQgZnJvbSBlbnZpcm9ubWVudCB2YXJpYWJsZXM6XG4vLyBQR0hPU1QsIFBHVVNFUiwgUEdEQVRBQkFTRSwgUEdQQVNTV09SRCwgUEdQT1JUXG5sZXQgcG9vbDogUG9vbCB8IG51bGwgPSBudWxsO1xuXG50cnkge1xuICBzdXBlcnRva2Vucy5pbml0KGJhY2tlbmRDb25maWcoKSk7IC8vIEluaXRpYWxpemUgU3VwZXJ0b2tlbnNcbiAgcG9vbCA9IG5ldyBQb29sKCk7IC8vIFJlYWRzIGVudmlyb25tZW50IHZhcmlhYmxlcyBhdXRvbWF0aWNhbGx5XG4gIGFwcFNlcnZpY2VMb2dnZXIuaW5mbyhcbiAgICAnUG9zdGdyZVNRTCBQb29sIGFuZCBTdXBlcnRva2VucyBpbml0aWFsaXplZCBzdWNjZXNzZnVsbHkgZm9yIG1lZXRpbmdfYXR0ZW5kYW5jZV9zdGF0dXMgQVBJLidcbiAgKTtcbn0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgYXBwU2VydmljZUxvZ2dlci5mYXRhbChcbiAgICB7IGVycm9yOiBlcnJvci5tZXNzYWdlLCBzdGFjazogZXJyb3Iuc3RhY2ssIGRldGFpbHM6IGVycm9yIH0sXG4gICAgJ0ZhaWxlZCB0byBpbml0aWFsaXplIFBvc3RncmVTUUwgUG9vbCBvciBTdXBlcnRva2Vucy4gQVBJIHdpbGwgbm90IGZ1bmN0aW9uIGNvcnJlY3RseS4nXG4gICk7XG4gIC8vIElmIHBvb2wgaW5pdCBmYWlscywgc3Vic2VxdWVudCBjYWxscyB3aWxsIGFsc28gZmFpbCB0aGUgIXBvb2wgY2hlY2suXG59XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlPFxuICAgIE1lZXRpbmdBdHRlbmRhbmNlU3RhdHVzIHwgTWVldGluZ0F0dGVuZGFuY2VTdGF0dXNbXSB8IEVycm9yUmVzcG9uc2VcbiAgPlxuKSB7XG4gIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0TWVldGluZ0F0dGVuZGFuY2VTdGF0dXMnOyAvLyBGb3IgbG9nZ2luZ1xuXG4gIGlmICghcG9vbCkge1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFBvc3RncmVTUUwgcG9vbCBub3QgaW5pdGlhbGl6ZWQuIENhbm5vdCBjb25uZWN0IHRvIGRhdGFiYXNlLmBcbiAgICApO1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oeyBlcnJvcjogJ0RhdGFiYXNlIGNvbm5lY3Rpb24gbm90IGNvbmZpZ3VyZWQuJyB9KTtcbiAgfVxuXG4gIGxldCBzZXNzaW9uO1xuICB0cnkge1xuICAgIHNlc3Npb24gPSBhd2FpdCBnZXRTZXNzaW9uKHJlcSBhcyBhbnksIHJlcyBhcyBhbnksIHRydWUpO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIFN1cGVydG9rZW5zIGdldFNlc3Npb24gZXJyb3IuYCwge1xuICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UsXG4gICAgICBzdGFjazogZXJyb3Iuc3RhY2ssXG4gICAgICBkZXRhaWxzOiBlcnJvcixcbiAgICB9KTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgZXJyb3I6ICdBdXRoZW50aWNhdGlvbiBlcnJvcicsIGRldGFpbHM6IGVycm9yLm1lc3NhZ2UgfSk7XG4gIH1cblxuICBpZiAoIXNlc3Npb24pIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFVuYXV0aG9yaXplZCBhdHRlbXB0OiBObyBhY3RpdmUgc2Vzc2lvbi5gXG4gICAgKTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDEpLmpzb24oeyBlcnJvcjogJ1VuYXV0aG9yaXplZC4gUGxlYXNlIGxvZyBpbi4nIH0pO1xuICB9XG4gIGNvbnN0IGF1dGhlbnRpY2F0ZWRVc2VySWQgPSBzZXNzaW9uLmdldFVzZXJJZCgpO1xuICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBSZXF1ZXN0IHJlY2VpdmVkIGZvciB1c2VyLmAsIHtcbiAgICBhdXRoZW50aWNhdGVkVXNlcklkLFxuICAgIHRhc2tJZDogcmVxLnF1ZXJ5LnRhc2tJZCxcbiAgfSk7XG5cbiAgY29uc3QgeyB0YXNrSWQgfSA9IHJlcS5xdWVyeTtcblxuICBpZiAocmVxLm1ldGhvZCAhPT0gJ0dFVCcpIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oYFske29wZXJhdGlvbk5hbWV9XSBNZXRob2Qgbm90IGFsbG93ZWQuYCwge1xuICAgICAgbWV0aG9kOiByZXEubWV0aG9kLFxuICAgICAgYXV0aGVudGljYXRlZFVzZXJJZCxcbiAgICAgIHRhc2tJZCxcbiAgICB9KTtcbiAgICByZXMuc2V0SGVhZGVyKCdBbGxvdycsIFsnR0VUJ10pO1xuICAgIHJldHVybiByZXMuc3RhdHVzKDQwNSkuanNvbih7IGVycm9yOiBgTWV0aG9kICR7cmVxLm1ldGhvZH0gTm90IEFsbG93ZWRgIH0pO1xuICB9XG5cbiAgaWYgKCF0YXNrSWQgfHwgdHlwZW9mIHRhc2tJZCAhPT0gJ3N0cmluZycpIHtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oYFske29wZXJhdGlvbk5hbWV9XSBJbnZhbGlkIG9yIG1pc3NpbmcgdGFza0lkLmAsIHtcbiAgICAgIHRhc2tJZCxcbiAgICAgIGF1dGhlbnRpY2F0ZWRVc2VySWQsXG4gICAgfSk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAuanNvbih7IGVycm9yOiAnVGFzayBJRCBpcyByZXF1aXJlZCBhbmQgbXVzdCBiZSBhIHN0cmluZy4nIH0pO1xuICB9XG4gIC8vIER1cGxpY2F0ZSBjaGVjayByZW1vdmVkLCBvbmUgaXMgc3VmZmljaWVudC5cblxuICB0cnkge1xuICAgIGNvbnN0IGNsaWVudCA9IGF3YWl0IHBvb2wuY29ubmVjdCgpO1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZGVidWcoYFske29wZXJhdGlvbk5hbWV9XSBEQiBjbGllbnQgY29ubmVjdGVkLmAsIHtcbiAgICAgIGF1dGhlbnRpY2F0ZWRVc2VySWQsXG4gICAgICB0YXNrSWQsXG4gICAgfSk7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHF1ZXJ5VGV4dCA9XG4gICAgICAgICdTRUxFQ1QgKiBGUk9NIG1lZXRpbmdfYXR0ZW5kYW5jZV9zdGF0dXMgV0hFUkUgdGFza19pZCA9ICQxIEFORCB1c2VyX2lkID0gJDInO1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5kZWJ1ZyhgWyR7b3BlcmF0aW9uTmFtZX1dIEV4ZWN1dGluZyBxdWVyeS5gLCB7XG4gICAgICAgIHF1ZXJ5VGV4dCxcbiAgICAgICAgcGFyYW1zOiBbdGFza0lkLCBhdXRoZW50aWNhdGVkVXNlcklkXSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgY2xpZW50LnF1ZXJ5KHF1ZXJ5VGV4dCwgW1xuICAgICAgICB0YXNrSWQsXG4gICAgICAgIGF1dGhlbnRpY2F0ZWRVc2VySWQsXG4gICAgICBdKTtcblxuICAgICAgaWYgKHJlc3VsdC5yb3dzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3Qgcm93ID0gcmVzdWx0LnJvd3NbMF07XG4gICAgICAgIGNvbnN0IHN0YXR1c1JlY29yZDogTWVldGluZ0F0dGVuZGFuY2VTdGF0dXMgPSB7XG4gICAgICAgICAgLi4ucm93LFxuICAgICAgICAgIHN0YXR1c190aW1lc3RhbXA6IG5ldyBEYXRlKHJvdy5zdGF0dXNfdGltZXN0YW1wKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIGNyZWF0ZWRfYXQ6IG5ldyBEYXRlKHJvdy5jcmVhdGVkX2F0KS50b0lTT1N0cmluZygpLFxuICAgICAgICB9O1xuICAgICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBTdGF0dXMgZm91bmQgZm9yIHRhc2suYCwge1xuICAgICAgICAgIGF1dGhlbnRpY2F0ZWRVc2VySWQsXG4gICAgICAgICAgdGFza0lkLFxuICAgICAgICB9KTtcbiAgICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHN0YXR1c1JlY29yZCk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBUYXNrIG5vdCBmb3VuZCBvciBub3QgYXV0aG9yaXplZCBmb3IgdXNlci5gLFxuICAgICAgICAgIHsgYXV0aGVudGljYXRlZFVzZXJJZCwgdGFza0lkIH1cbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAgIC5zdGF0dXMoNDA0KVxuICAgICAgICAgIC5qc29uKHsgZXJyb3I6ICdUYXNrIG5vdCBmb3VuZCBvciBub3QgYXV0aG9yaXplZC4nIH0pO1xuICAgICAgfVxuICAgIH0gZmluYWxseSB7XG4gICAgICBjbGllbnQucmVsZWFzZSgpO1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5kZWJ1ZyhgWyR7b3BlcmF0aW9uTmFtZX1dIERCIGNsaWVudCByZWxlYXNlZC5gLCB7XG4gICAgICAgIGF1dGhlbnRpY2F0ZWRVc2VySWQsXG4gICAgICAgIHRhc2tJZCxcbiAgICAgIH0pO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIERhdGFiYXNlIHF1ZXJ5IG9yIGNvbm5lY3Rpb24gZmFpbGVkLmAsXG4gICAgICB7XG4gICAgICAgIGF1dGhlbnRpY2F0ZWRVc2VySWQsXG4gICAgICAgIHRhc2tJZCxcbiAgICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgIHN0YWNrOiBlcnJvci5zdGFjayxcbiAgICAgICAgZGV0YWlsczogZXJyb3IsXG4gICAgICB9XG4gICAgKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgZXJyb3I6ICdJbnRlcm5hbCBTZXJ2ZXIgRXJyb3InLCBkZXRhaWxzOiBlcnJvci5tZXNzYWdlIH0pO1xuICB9XG59XG4iXX0=
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuthService = void 0;
const axios_1 = __importDefault(require("axios"));
// Assuming constants.ts path relative to src/services/
const constants_1 = require("../../atomic-docker/project/functions/atom-agent/_libs/constants");
// Assuming logger.ts path relative to src/services/
const logger_1 = require("../../atomic-docker/project/functions/_utils/logger");
const AUTH_SERVICE_API_TIMEOUT = 10000; // 10 seconds timeout for auth related calls
// Local error handler, similar to helpers in other skill files
// TODO: Consolidate into a shared utility if this pattern is widespread
function handleAuthServiceAxiosError(error, operationName) {
    if (error.response) {
        logger_1.logger.error(`[AuthService:${operationName}] HTTP Error: ${error.response.status}`, error.response.data);
        const errData = error.response.data; // Backend returns {ok: false, error: {code, message}}
        return {
            ok: false,
            error: {
                code: errData?.error?.code || `HTTP_${error.response.status}`,
                message: errData?.error?.message || `Failed to ${operationName}. Status: ${error.response.status}`,
                details: errData?.error?.details || errData,
            },
        };
    }
    else if (error.request) {
        logger_1.logger.error(`[AuthService:${operationName}] Network Error: No response received for ${operationName}`, error.request);
        return {
            ok: false,
            error: { code: 'NETWORK_ERROR', message: `No response received for ${operationName}.` },
        };
    }
    else {
        logger_1.logger.error(`[AuthService:${operationName}] Request Setup Error: ${error.message}`);
        return {
            ok: false,
            error: { code: 'REQUEST_SETUP_ERROR', message: `Error setting up request for ${operationName}: ${error.message}` },
        };
    }
}
/**
 * Retrieves a valid Google Drive access token for the given user.
 * Calls a secure backend endpoint that handles token storage and refresh logic.
 * @param userId The ID of the user for whom to retrieve the token.
 * @returns A promise that resolves to the access token string if successful, or null if not.
 */
async function getGoogleDriveAccessToken(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        logger_1.logger.error("[AuthService:getGoogleDriveAccessToken] PYTHON_API_SERVICE_BASE_URL is not configured.");
        return null;
    }
    if (!userId || userId.trim() === "") {
        logger_1.logger.warn("[AuthService:getGoogleDriveAccessToken] userId is required and cannot be empty.");
        return null;
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/auth/gdrive/get-access-token`;
    try {
        logger_1.logger.info(`[AuthService:getGoogleDriveAccessToken] Requesting GDrive access token for user ${userId}`);
        const response = await axios_1.default.get(endpoint, {
            params: { user_id: userId }, // Python endpoint expects user_id as query param
            timeout: AUTH_SERVICE_API_TIMEOUT,
            // Headers for internal service authentication might be needed here if the Python endpoint is protected
            // e.g., headers: { 'X-Internal-Service-Key': 'INTERNAL_SECRET_KEY' }
        });
        if (response.data && response.data.ok && response.data.data?.access_token) {
            logger_1.logger.info(`[AuthService:getGoogleDriveAccessToken] Successfully retrieved GDrive access token for user ${userId}`);
            return response.data.data.access_token;
        }
        else {
            const errorMsg = response.data?.error?.message || 'Failed to retrieve GDrive access token from backend.';
            const errorCode = response.data?.error?.code || 'TOKEN_RETRIEVAL_FAILED';
            logger_1.logger.warn(`[AuthService:getGoogleDriveAccessToken] Failed for user ${userId}. Code: ${errorCode}, Msg: ${errorMsg}`, response.data?.error?.details);
            return null;
        }
    }
    catch (error) {
        const axiosErr = error;
        const errResponse = handleAuthServiceAxiosError(axiosErr, 'getGoogleDriveAccessToken');
        logger_1.logger.error(`[AuthService:getGoogleDriveAccessToken] Exception for user ${userId}: ${errResponse.error?.message}`, errResponse.error?.details);
        return null;
    }
}
/**
 * Constructs the URL to initiate the Google Drive OAuth flow.
 * This URL points to the backend endpoint that starts the OAuth dance with Google.
 * @param userId The Atom user ID to associate with the OAuth flow (will be passed in 'state').
 * @returns The URL string or null if configuration is missing.
 */
function getGoogleDriveAuthInitiateUrl(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        logger_1.logger.error("[AuthService:getGoogleDriveAuthInitiateUrl] PYTHON_API_SERVICE_BASE_URL is not configured.");
        return null;
    }
    if (!userId || userId.trim() === "") {
        logger_1.logger.warn("[AuthService:getGoogleDriveAuthInitiateUrl] userId is required and cannot be empty.");
        return null;
    }
    // This URL should point to the backend endpoint that starts the OAuth dance
    return `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/auth/gdrive/initiate?user_id=${encodeURIComponent(userId)}`;
}
exports.AuthService = {
    getGoogleDriveAccessToken,
    getGoogleDriveAuthInitiateUrl,
};
`` `
;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXV0aFNlcnZpY2UuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJhdXRoU2VydmljZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSxrREFBMEM7QUFHMUMsdURBQXVEO0FBQ3ZELGdHQUErRztBQUMvRyxvREFBb0Q7QUFDcEQsZ0ZBQTZFO0FBRTdFLE1BQU0sd0JBQXdCLEdBQUcsS0FBSyxDQUFDLENBQUMsNENBQTRDO0FBRXBGLCtEQUErRDtBQUMvRCx3RUFBd0U7QUFDeEUsU0FBUywyQkFBMkIsQ0FBQyxLQUFpQixFQUFFLGFBQXFCO0lBQzNFLElBQUksS0FBSyxDQUFDLFFBQVEsRUFBRSxDQUFDO1FBQ25CLGVBQU0sQ0FBQyxLQUFLLENBQUMsZ0JBQWdCLGFBQWEsaUJBQWlCLEtBQUssQ0FBQyxRQUFRLENBQUMsTUFBTSxFQUFFLEVBQUUsS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUN6RyxNQUFNLE9BQU8sR0FBRyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQVcsQ0FBQyxDQUFDLHNEQUFzRDtRQUNsRyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLE9BQU8sRUFBRSxLQUFLLEVBQUUsSUFBSSxJQUFJLFFBQVEsS0FBSyxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQUU7Z0JBQzdELE9BQU8sRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsYUFBYSxLQUFLLENBQUMsUUFBUSxDQUFDLE1BQU0sRUFBRTtnQkFDbEcsT0FBTyxFQUFFLE9BQU8sRUFBRSxLQUFLLEVBQUUsT0FBTyxJQUFJLE9BQU87YUFDNUM7U0FDRixDQUFDO0lBQ0osQ0FBQztTQUFNLElBQUksS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ3pCLGVBQU0sQ0FBQyxLQUFLLENBQUMsZ0JBQWdCLGFBQWEsNkNBQTZDLGFBQWEsRUFBRSxFQUFFLEtBQUssQ0FB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QUNqRCxJQUFJLENBQUMsdUNBQTJCLEVBQUUsQ0FBQztRQUMvQixlQUFNLENBQUMsS0FBSyxDQUFDLDRGQUE0RixDQUFDLENBQUM7UUFDM0csT0FBTyxJQUFJLENBQUM7SUFDaEIsQ0FBQztJQUNELElBQUksQ0FBQyxNQUFNLElBQUksTUFBTSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsRUFBRSxDQUFDO1FBQ2xDLGVBQU0sQ0FBQyxJQUFJLENBQUMscUZBQXFGLENBQUMsQ0FBQztRQUNuRyxPQUFPLElBQUksQ0FBQztJQUNoQixDQUFDO0lBQ0QsNEVBQTRFO0lBQzVFLE9BQU8sR0FBRyx1Q0FBMkIscUNBQXFDLGtCQUFrQixDQUFDLE1BQU0sQ0FBQyxFQUFFLENBQUM7QUFDM0csQ0FBQztBQUdZLFFBQUEsV0FBVyxHQUFHO0lBQ3pCLHlCQUF5QjtJQUN6Qiw2QkFBNkI7Q0FDOUIsQ0FBQztBQUNGLEVBQUUsQ0FBQTtBQUNGLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbi8vIEFzc3VtaW5nIHR5cGVzLnRzIHBhdGggcmVsYXRpdmUgdG8gc3JjL3NlcnZpY2VzL1xuaW1wb3J0IHsgU2tpbGxSZXNwb25zZSB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC90eXBlcyc7XG4vLyBBc3N1bWluZyBjb25zdGFudHMudHMgcGF0aCByZWxhdGl2ZSB0byBzcmMvc2VydmljZXMvXG5pbXBvcnQgeyBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJztcbi8vIEFzc3VtaW5nIGxvZ2dlci50cyBwYXRoIHJlbGF0aXZlIHRvIHNyYy9zZXJ2aWNlcy9cbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2xvZ2dlcic7XG5cbmNvbnN0IEFVVEhfU0VSVklDRV9BUElfVElNRU9VVCA9IDEwMDAwOyAvLyAxMCBzZWNvbmRzIHRpbWVvdXQgZm9yIGF1dGggcmVsYXRlZCBjYWxsc1xuXG4vLyBMb2NhbCBlcnJvciBoYW5kbGVyLCBzaW1pbGFyIHRvIGhlbHBlcnMgaW4gb3RoZXIgc2tpbGwgZmlsZXNcbi8vIFRPRE86IENvbnNvbGlkYXRlIGludG8gYSBzaGFyZWQgdXRpbGl0eSBpZiB0aGlzIHBhdHRlcm4gaXMgd2lkZXNwcmVhZFxuZnVuY3Rpb24gaGFuZGxlQXV0aFNlcnZpY2VBeGlvc0Vycm9yKGVycm9yOiBBeGlvc0Vycm9yLCBvcGVyYXRpb25OYW1lOiBzdHJpbmcpOiB7IG9rOiBmYWxzZTsgZXJyb3I6IFNraWxsUmVzcG9uc2U8bnVsbD5bJ2Vycm9yJ10gfSB7XG4gIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgIGxvZ2dlci5lcnJvcihgW0F1dGhTZXJ2aWNlOiR7b3BlcmF0aW9uTmFtZX1dIEhUVFAgRXJyb3I6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsIGVycm9yLnJlc3BvbnNlLmRhdGEpO1xuICAgIGNvbnN0IGVyckRhdGEgPSBlcnJvci5yZXNwb25zZS5kYXRhIGFzIGFueTsgLy8gQmFja2VuZCByZXR1cm5zIHtvazogZmFsc2UsIGVycm9yOiB7Y29kZSwgbWVzc2FnZX19XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGVyckRhdGE/LmVycm9yPy5jb2RlIHx8IGBIVFRQXyR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICAgIG1lc3NhZ2U6IGVyckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS4gU3RhdHVzOiAke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgICBkZXRhaWxzOiBlcnJEYXRhPy5lcnJvcj8uZGV0YWlscyB8fCBlcnJEYXRhLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGVsc2UgaWYgKGVycm9yLnJlcXVlc3QpIHtcbiAgICBsb2dnZXIuZXJyb3IoYFtBdXRoU2VydmljZToke29wZXJhdGlvbk5hbWV9XSBOZXR3b3JrIEVycm9yOiBObyByZXNwb25zZSByZWNlaXZlZCBmb3IgJHtvcGVyYXRpb25OYW1lfWAsIGVycm9yLnJlcXVlc3QpO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnTkVUV09SS19FUlJPUicsIG1lc3NhZ2U6IGBObyByZXNwb25zZSByZWNlaXZlZCBmb3IgJHtvcGVyYXRpb25OYW1lfS5gIH0sXG4gICAgfTtcbiAgfSBlbHNlIHtcbiAgICBsb2dnZXIuZXJyb3IoYFtBdXRoU2VydmljZToke29wZXJhdGlvbk5hbWV9XSBSZXF1ZXN0IFNldHVwIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6ICdSRVFVRVNUX1NFVFVQX0VSUk9SJywgbWVzc2FnZTogYEVycm9yIHNldHRpbmcgdXAgcmVxdWVzdCBmb3IgJHtvcGVyYXRpb25OYW1lfTogJHtlcnJvci5tZXNzYWdlfWAgfSxcbiAgICB9O1xuICB9XG59XG5cblxuLyoqXG4gKiBSZXRyaWV2ZXMgYSB2YWxpZCBHb29nbGUgRHJpdmUgYWNjZXNzIHRva2VuIGZvciB0aGUgZ2l2ZW4gdXNlci5cbiAqIENhbGxzIGEgc2VjdXJlIGJhY2tlbmQgZW5kcG9pbnQgdGhhdCBoYW5kbGVzIHRva2VuIHN0b3JhZ2UgYW5kIHJlZnJlc2ggbG9naWMuXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlciBmb3Igd2hvbSB0byByZXRyaWV2ZSB0aGUgdG9rZW4uXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byB0aGUgYWNjZXNzIHRva2VuIHN0cmluZyBpZiBzdWNjZXNzZnVsLCBvciBudWxsIGlmIG5vdC5cbiAqL1xuYXN5bmMgZnVuY3Rpb24gZ2V0R29vZ2xlRHJpdmVBY2Nlc3NUb2tlbih1c2VySWQ6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIGxvZ2dlci5lcnJvcihcIltBdXRoU2VydmljZTpnZXRHb29nbGVEcml2ZUFjY2Vzc1Rva2VuXSBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgaXMgbm90IGNvbmZpZ3VyZWQuXCIpO1xuICAgIHJldHVybiBudWxsO1xuICB9XG4gIGlmICghdXNlcklkIHx8IHVzZXJJZC50cmltKCkgPT09IFwiXCIpIHtcbiAgICBsb2dnZXIud2FybihcIltBdXRoU2VydmljZTpnZXRHb29nbGVEcml2ZUFjY2Vzc1Rva2VuXSB1c2VySWQgaXMgcmVxdWlyZWQgYW5kIGNhbm5vdCBiZSBlbXB0eS5cIik7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2F1dGgvZ2RyaXZlL2dldC1hY2Nlc3MtdG9rZW5gO1xuXG4gIHRyeSB7XG4gICAgbG9nZ2VyLmluZm8oYFtBdXRoU2VydmljZTpnZXRHb29nbGVEcml2ZUFjY2Vzc1Rva2VuXSBSZXF1ZXN0aW5nIEdEcml2ZSBhY2Nlc3MgdG9rZW4gZm9yIHVzZXIgJHt1c2VySWR9YCk7XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLmdldDx7IG9rOiBib29sZWFuOyBkYXRhPzogeyBhY2Nlc3NfdG9rZW46IHN0cmluZyB9OyBlcnJvcj86IGFueSB9PihcbiAgICAgIGVuZHBvaW50LFxuICAgICAge1xuICAgICAgICBwYXJhbXM6IHsgdXNlcl9pZDogdXNlcklkIH0sIC8vIFB5dGhvbiBlbmRwb2ludCBleHBlY3RzIHVzZXJfaWQgYXMgcXVlcnkgcGFyYW1cbiAgICAgICAgdGltZW91dDogQVVUSF9TRVJWSUNFX0FQSV9USU1FT1VULFxuICAgICAgICAvLyBIZWFkZXJzIGZvciBpbnRlcm5hbCBzZXJ2aWNlIGF1dGhlbnRpY2F0aW9uIG1pZ2h0IGJlIG5lZWRlZCBoZXJlIGlmIHRoZSBQeXRob24gZW5kcG9pbnQgaXMgcHJvdGVjdGVkXG4gICAgICAgIC8vIGUuZy4sIGhlYWRlcnM6IHsgJ1gtSW50ZXJuYWwtU2VydmljZS1LZXknOiAnSU5URVJOQUxfU0VDUkVUX0tFWScgfVxuICAgICAgfVxuICAgICk7XG5cbiAgICBpZiAocmVzcG9uc2UuZGF0YSAmJiByZXNwb25zZS5kYXRhLm9rICYmIHJlc3BvbnNlLmRhdGEuZGF0YT8uYWNjZXNzX3Rva2VuKSB7XG4gICAgICBsb2dnZXIuaW5mbyhgW0F1dGhTZXJ2aWNlOmdldEdvb2dsZURyaXZlQWNjZXNzVG9rZW5dIFN1Y2Nlc3NmdWxseSByZXRyaWV2ZWQgR0RyaXZlIGFjY2VzcyB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH1gKTtcbiAgICAgIHJldHVybiByZXNwb25zZS5kYXRhLmRhdGEuYWNjZXNzX3Rva2VuO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBlcnJvck1zZyA9IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gcmV0cmlldmUgR0RyaXZlIGFjY2VzcyB0b2tlbiBmcm9tIGJhY2tlbmQuJztcbiAgICAgIGNvbnN0IGVycm9yQ29kZSA9IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5jb2RlIHx8ICdUT0tFTl9SRVRSSUVWQUxfRkFJTEVEJztcbiAgICAgIGxvZ2dlci53YXJuKGBbQXV0aFNlcnZpY2U6Z2V0R29vZ2xlRHJpdmVBY2Nlc3NUb2tlbl0gRmFpbGVkIGZvciB1c2VyICR7dXNlcklkfS4gQ29kZTogJHtlcnJvckNvZGV9LCBNc2c6ICR7ZXJyb3JNc2d9YCwgcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmRldGFpbHMpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnN0IGF4aW9zRXJyID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICBjb25zdCBlcnJSZXNwb25zZSA9IGhhbmRsZUF1dGhTZXJ2aWNlQXhpb3NFcnJvcihheGlvc0VyciwgJ2dldEdvb2dsZURyaXZlQWNjZXNzVG9rZW4nKTtcbiAgICBsb2dnZXIuZXJyb3IoYFtBdXRoU2VydmljZTpnZXRHb29nbGVEcml2ZUFjY2Vzc1Rva2VuXSBFeGNlcHRpb24gZm9yIHVzZXIgJHt1c2VySWR9OiAke2VyclJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWAsIGVyclJlc3BvbnNlLmVycm9yPy5kZXRhaWxzKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufVxuXG4vKipcbiAqIENvbnN0cnVjdHMgdGhlIFVSTCB0byBpbml0aWF0ZSB0aGUgR29vZ2xlIERyaXZlIE9BdXRoIGZsb3cuXG4gKiBUaGlzIFVSTCBwb2ludHMgdG8gdGhlIGJhY2tlbmQgZW5kcG9pbnQgdGhhdCBzdGFydHMgdGhlIE9BdXRoIGRhbmNlIHdpdGggR29vZ2xlLlxuICogQHBhcmFtIHVzZXJJZCBUaGUgQXRvbSB1c2VyIElEIHRvIGFzc29jaWF0ZSB3aXRoIHRoZSBPQXV0aCBmbG93ICh3aWxsIGJlIHBhc3NlZCBpbiAnc3RhdGUnKS5cbiAqIEByZXR1cm5zIFRoZSBVUkwgc3RyaW5nIG9yIG51bGwgaWYgY29uZmlndXJhdGlvbiBpcyBtaXNzaW5nLlxuICovXG5mdW5jdGlvbiBnZXRHb29nbGVEcml2ZUF1dGhJbml0aWF0ZVVybCh1c2VySWQ6IHN0cmluZyk6IHN0cmluZyB8IG51bGwge1xuICAgIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgICAgIGxvZ2dlci5lcnJvcihcIltBdXRoU2VydmljZTpnZXRHb29nbGVEcml2ZUF1dGhJbml0aWF0ZVVybF0gUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIGlzIG5vdCBjb25maWd1cmVkLlwiKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIGlmICghdXNlcklkIHx8IHVzZXJJZC50cmltKCkgPT09IFwiXCIpIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oXCJbQXV0aFNlcnZpY2U6Z2V0R29vZ2xlRHJpdmVBdXRoSW5pdGlhdGVVcmxdIHVzZXJJZCBpcyByZXF1aXJlZCBhbmQgY2Fubm90IGJlIGVtcHR5LlwiKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIC8vIFRoaXMgVVJMIHNob3VsZCBwb2ludCB0byB0aGUgYmFja2VuZCBlbmRwb2ludCB0aGF0IHN0YXJ0cyB0aGUgT0F1dGggZGFuY2VcbiAgICByZXR1cm4gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvYXV0aC9nZHJpdmUvaW5pdGlhdGU/dXNlcl9pZD0ke2VuY29kZVVSSUNvbXBvbmVudCh1c2VySWQpfWA7XG59XG5cblxuZXhwb3J0IGNvbnN0IEF1dGhTZXJ2aWNlID0ge1xuICBnZXRHb29nbGVEcml2ZUFjY2Vzc1Rva2VuLFxuICBnZXRHb29nbGVEcml2ZUF1dGhJbml0aWF0ZVVybCxcbn07XG5gYGBcbiJdfQ==
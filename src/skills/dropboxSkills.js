"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getDropboxConnectionStatus = getDropboxConnectionStatus;
exports.disconnectDropbox = disconnectDropbox;
exports.listDropboxFiles = listDropboxFiles;
const axios_1 = __importDefault(require("axios"));
const constants_1 = require("../../atomic-docker/project/functions/atom-agent/_libs/constants");
const logger_1 = require("../../atomic-docker/project/functions/_utils/logger");
// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse(response, operationName) {
    if (response.ok && response.data !== undefined) {
        return { ok: true, data: response.data };
    }
    logger_1.logger.warn(`[${operationName}] Failed API call. API ok: ${response.ok}`, response.error);
    return {
        ok: false,
        error: {
            code: response.error?.code || 'PYTHON_API_ERROR',
            message: response.error?.message || `Failed to ${operationName}.`,
            details: response.error?.details,
        },
    };
}
// Helper to handle network/axios errors
function handleAxiosError(error, operationName) {
    if (error.response) {
        logger_1.logger.error(`[${operationName}] Error: ${error.response.status}`, error.response.data);
        const errData = error.response.data;
        return {
            ok: false,
            error: {
                code: `HTTP_${error.response.status}`,
                message: errData?.error?.message || `Failed to ${operationName}.`,
            },
        };
    }
    else if (error.request) {
        logger_1.logger.error(`[${operationName}] Error: No response received`, error.request);
        return {
            ok: false,
            error: {
                code: 'NETWORK_ERROR',
                message: `No response received for ${operationName}.`,
            },
        };
    }
    logger_1.logger.error(`[${operationName}] Error: ${error.message}`);
    return {
        ok: false,
        error: {
            code: 'REQUEST_SETUP_ERROR',
            message: `Error setting up request for ${operationName}: ${error.message}`,
        },
    };
}
async function getDropboxConnectionStatus(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/dropbox/status?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response.data, 'getDropboxConnectionStatus');
    }
    catch (error) {
        return handleAxiosError(error, 'getDropboxConnectionStatus');
    }
}
async function disconnectDropbox(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/dropbox/disconnect`;
    try {
        const response = await axios_1.default.post(endpoint, { user_id: userId });
        return handlePythonApiResponse(response.data, 'disconnectDropbox');
    }
    catch (error) {
        return handleAxiosError(error, 'disconnectDropbox');
    }
}
async function listDropboxFiles(userId, path = '') {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/dropbox/list-files`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            path: path,
        });
        return handlePythonApiResponse(response.data, 'listDropboxFiles');
    }
    catch (error) {
        return handleAxiosError(error, 'listDropboxFiles');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZHJvcGJveFNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRyb3Bib3hTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUF5RUEsZ0VBcUJDO0FBRUQsOENBdUJDO0FBRUQsNENBMEJDO0FBbkpELGtEQUEwQztBQU8xQyxnR0FBK0c7QUFDL0csZ0ZBQTZFO0FBRTdFLGtFQUFrRTtBQUNsRSxTQUFTLHVCQUF1QixDQUM5QixRQUE4QixFQUM5QixhQUFxQjtJQUVyQixJQUFJLFFBQVEsQ0FBQyxFQUFFLElBQUksUUFBUSxDQUFDLElBQUksS0FBSyxTQUFTLEVBQUUsQ0FBQztRQUMvQyxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQzNDLENBQUM7SUFDRCxlQUFNLENBQUMsSUFBSSxDQUNULElBQUksYUFBYSw4QkFBOEIsUUFBUSxDQUFDLEVBQUUsRUFBRSxFQUM1RCxRQUFRLENBQUMsS0FBSyxDQUNmLENBQUM7SUFDRixPQUFPO1FBQ0wsRUFBRSxFQUFFLEtBQUs7UUFDVCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsUUFBUSxDQUFDLEtBQUssRUFBRSxJQUFJLElBQUksa0JBQWtCO1lBQ2hELE9BQU8sRUFBRSxRQUFRLENBQUMsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsR0FBRztZQUNqRSxPQUFPLEVBQUUsUUFBUSxDQUFDLEtBQUssRUFBRSxPQUFPO1NBQ2pDO0tBQ0YsQ0FBQztBQUNKLENBQUM7QUFFRCx3Q0FBd0M7QUFDeEMsU0FBUyxnQkFBZ0IsQ0FDdkIsS0FBaUIsRUFDakIsYUFBcUI7SUFFckIsSUFBSSxLQUFLLENBQUMsUUFBUSxFQUFFLENBQUM7UUFDbkIsZUFBTSxDQUFDLEtBQUssQ0FDVixJQUFJLGFBQWEsWUFBWSxLQUFLLENBQUMsUUFBUSxDQUFDLE1BQU0sRUFBRSxFQUNwRCxLQUFLLENBQUMsUUFBUSxDQUFDLElB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QUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsY0FBYztnQkFDcEIsT0FBTyxFQUFFLDJDQUEyQzthQUNyRDtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxRQUFRLEdBQUcsR0FBRyx1Q0FBMkIseUJBQXlCLENBQUM7SUFFekUsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxlQUFLLENBQUMsSUFBSSxDQUUvQixRQUFRLEVBQUU7WUFDVixPQUFPLEVBQUUsTUFBTTtZQUNmLElBQUksRUFBRSxJQUFJO1NBQ1gsQ0FBQyxDQUFDO1FBQ0gsT0FBTyx1QkFBdUIsQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLGtCQUFrQixDQUFDLENBQUM7SUFDcEUsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLGdCQUFnQixDQUFDLEtBQW1CLEVBQUUsa0JBQWtCLENBQUMsQ0FBQztJQUNuRSxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBheGlvcywgeyBBeGlvc0Vycm9yIH0gZnJvbSAnYXhpb3MnO1xuaW1wb3J0IHtcbiAgU2tpbGxSZXNwb25zZSxcbiAgRHJvcGJveENvbm5lY3Rpb25TdGF0dXNJbmZvLFxuICBEcm9wYm94RmlsZSxcbiAgUHl0aG9uQXBpUmVzcG9uc2UsXG59IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC90eXBlcyc7IC8vIEFkanVzdCBwYXRoXG5pbXBvcnQgeyBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2xvZ2dlcic7XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgUHl0aG9uIEFQSSByZXNwb25zZXMsIGNhbiBiZSBjZW50cmFsaXplZCBsYXRlclxuZnVuY3Rpb24gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2U8VD4oXG4gIHJlc3BvbnNlOiBQeXRob25BcGlSZXNwb25zZTxUPixcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPFQ+IHtcbiAgaWYgKHJlc3BvbnNlLm9rICYmIHJlc3BvbnNlLmRhdGEgIT09IHVuZGVmaW5lZCkge1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXNwb25zZS5kYXRhIH07XG4gIH1cbiAgbG9nZ2VyLndhcm4oXG4gICAgYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgQVBJIGNhbGwuIEFQSSBvazogJHtyZXNwb25zZS5va31gLFxuICAgIHJlc3BvbnNlLmVycm9yXG4gICk7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiByZXNwb25zZS5lcnJvcj8uY29kZSB8fCAnUFlUSE9OX0FQSV9FUlJPUicsXG4gICAgICBtZXNzYWdlOiByZXNwb25zZS5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIGRldGFpbHM6IHJlc3BvbnNlLmVycm9yPy5kZXRhaWxzLFxuICAgIH0sXG4gIH07XG59XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgbmV0d29yay9heGlvcyBlcnJvcnNcbmZ1bmN0aW9uIGhhbmRsZUF4aW9zRXJyb3IoXG4gIGVycm9yOiBBeGlvc0Vycm9yLFxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8bnVsbD4ge1xuICBpZiAoZXJyb3IucmVzcG9uc2UpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgZXJyb3IucmVzcG9uc2UuZGF0YVxuICAgICk7XG4gICAgY29uc3QgZXJyRGF0YSA9IGVycm9yLnJlc3BvbnNlLmRhdGEgYXMgYW55O1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBgSFRUUF8ke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgICBtZXNzYWdlOiBlcnJEYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBlbHNlIGlmIChlcnJvci5yZXF1ZXN0KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogTm8gcmVzcG9uc2UgcmVjZWl2ZWRgLFxuICAgICAgZXJyb3IucmVxdWVzdFxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdORVRXT1JLX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYE5vIHJlc3BvbnNlIHJlY2VpdmVkIGZvciAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgbG9nZ2VyLmVycm9yKGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6ICdSRVFVRVNUX1NFVFVQX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IGBFcnJvciBzZXR0aW5nIHVwIHJlcXVlc3QgZm9yICR7b3BlcmF0aW9uTmFtZX06ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgIH0sXG4gIH07XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXREcm9wYm94Q29ubmVjdGlvblN0YXR1cyhcbiAgdXNlcklkOiBzdHJpbmdcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxEcm9wYm94Q29ubmVjdGlvblN0YXR1c0luZm8+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvZHJvcGJveC9zdGF0dXM/dXNlcl9pZD0ke3VzZXJJZH1gO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPVxuICAgICAgYXdhaXQgYXhpb3MuZ2V0PFB5dGhvbkFwaVJlc3BvbnNlPERyb3Bib3hDb25uZWN0aW9uU3RhdHVzSW5mbz4+KGVuZHBvaW50KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UuZGF0YSwgJ2dldERyb3Bib3hDb25uZWN0aW9uU3RhdHVzJyk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ2dldERyb3Bib3hDb25uZWN0aW9uU3RhdHVzJyk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGRpc2Nvbm5lY3REcm9wYm94KFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPHsgbWVzc2FnZTogc3RyaW5nIH0+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvZHJvcGJveC9kaXNjb25uZWN0YDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdDxQeXRob25BcGlSZXNwb25zZTx7IG1lc3NhZ2U6IHN0cmluZyB9Pj4oXG4gICAgICBlbmRwb2ludCxcbiAgICAgIHsgdXNlcl9pZDogdXNlcklkIH1cbiAgICApO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShyZXNwb25zZS5kYXRhLCAnZGlzY29ubmVjdERyb3Bib3gnKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihlcnJvciBhcyBBeGlvc0Vycm9yLCAnZGlzY29ubmVjdERyb3Bib3gnKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbGlzdERyb3Bib3hGaWxlcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHBhdGg6IHN0cmluZyA9ICcnXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8eyBlbnRyaWVzOiBEcm9wYm94RmlsZVtdIH0+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvZHJvcGJveC9saXN0LWZpbGVzYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdDxcbiAgICAgIFB5dGhvbkFwaVJlc3BvbnNlPHsgZW50cmllczogRHJvcGJveEZpbGVbXSB9PlxuICAgID4oZW5kcG9pbnQsIHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIHBhdGg6IHBhdGgsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdsaXN0RHJvcGJveEZpbGVzJyk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ2xpc3REcm9wYm94RmlsZXMnKTtcbiAgfVxufVxuIl19
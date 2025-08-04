"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.searchJira = searchJira;
exports.listJiraIssues = listJiraIssues;
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
async function searchJira(userId, projectId, query) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/jira/search`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            project_id: projectId,
            query: query,
        });
        return handlePythonApiResponse(response.data, 'searchJira');
    }
    catch (error) {
        return handleAxiosError(error, 'searchJira');
    }
}
async function listJiraIssues(userId, projectId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/jira/list-issues`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            project_id: projectId,
        });
        return handlePythonApiResponse(response.data, 'listJiraIssues');
    }
    catch (error) {
        return handleAxiosError(error, 'listJiraIssues');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiamlyYVNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImppcmFTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUF1RUEsZ0NBMEJDO0FBRUQsd0NBd0JDO0FBM0hELGtEQUEwQztBQUsxQyxnR0FBK0c7QUFDL0csZ0ZBQTZFO0FBRTdFLGtFQUFrRTtBQUNsRSxTQUFTLHVCQUF1QixDQUM5QixRQUE4QixFQUM5QixhQUFxQjtJQUVyQixJQUFJLFFBQVEsQ0FBQyxFQUFFLElBQUksUUFBUSxDQUFDLElBQUksS0FBSyxTQUFTLEVBQUUsQ0FBQztRQUMvQyxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQzNDLENBQUM7SUFDRCxlQUFNLENBQUMsSUFBSSxDQUNULElBQUksYUFBYSw4QkFBOEIsUUFBUSxDQUFDLEVBQUUsRUFBRSxFQUM1RCxRQUFRLENBQUMsS0FBSyxDQUNmLENBQUM7SUFDRixPQUFPO1FBQ0wsRUFBRSxFQUFFLEtBQUs7UUFDVCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsUUFBUSxDQUFDLEtBQUssRUFBRSxJQUFJLElBQUksa0JBQWtCO1lBQ2hELE9BQU8sRUFBRSxRQUFRLENBQUMsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsR0FBRztZQUNqRSxPQUFPLEVBQUUsUUFBUSxDQUFDLEtBQUssRUFBRSxPQUFPO1NBQ2pDO0tBQ0YsQ0FBQztBQUNKLENBQUM7QUFFRCx3Q0FBd0M7QUFDeEMsU0FBUyxnQkFBZ0IsQ0FDdkIsS0FBaUIsRUFDakIsYUFBcUI7SUFFckIsSUFBSSxLQUFLLENBQUMsUUFBUSxFQUFFLENBQUM7UUFDbkIsZUFBTSxDQUFDLEtBQUssQ0FDVixJQUFJLGFBQWEsWUFBWSxLQUFLLENBQUMsUUFBUSxDQUFDLE1BQU0sRUFBRSxFQUNwRCxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FDcEIsQ0FBQztRQUNG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aW9zLCB7IEF4aW9zRXJyb3IgfSBmcm9tICdheGlvcyc7XG5pbXBvcnQge1xuICBTa2lsbFJlc3BvbnNlLFxuICBQeXRob25BcGlSZXNwb25zZSxcbn0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3R5cGVzJzsgLy8gQWRqdXN0IHBhdGhcbmltcG9ydCB7IFBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9fdXRpbHMvbG9nZ2VyJztcblxuLy8gSGVscGVyIHRvIGhhbmRsZSBQeXRob24gQVBJIHJlc3BvbnNlcywgY2FuIGJlIGNlbnRyYWxpemVkIGxhdGVyXG5mdW5jdGlvbiBoYW5kbGVQeXRob25BcGlSZXNwb25zZTxUPihcbiAgcmVzcG9uc2U6IFB5dGhvbkFwaVJlc3BvbnNlPFQ+LFxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8VD4ge1xuICBpZiAocmVzcG9uc2Uub2sgJiYgcmVzcG9uc2UuZGF0YSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmRhdGEgfTtcbiAgfVxuICBsb2dnZXIud2FybihcbiAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCBBUEkgY2FsbC4gQVBJIG9rOiAke3Jlc3BvbnNlLm9rfWAsXG4gICAgcmVzcG9uc2UuZXJyb3JcbiAgKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6IHJlc3BvbnNlLmVycm9yPy5jb2RlIHx8ICdQWVRIT05fQVBJX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IHJlc3BvbnNlLmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgZGV0YWlsczogcmVzcG9uc2UuZXJyb3I/LmRldGFpbHMsXG4gICAgfSxcbiAgfTtcbn1cblxuLy8gSGVscGVyIHRvIGhhbmRsZSBuZXR3b3JrL2F4aW9zIGVycm9yc1xuZnVuY3Rpb24gaGFuZGxlQXhpb3NFcnJvcihcbiAgZXJyb3I6IEF4aW9zRXJyb3IsXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxudWxsPiB7XG4gIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICBlcnJvci5yZXNwb25zZS5kYXRhXG4gICAgKTtcbiAgICBjb25zdCBlcnJEYXRhID0gZXJyb3IucmVzcG9uc2UuZGF0YSBhcyBhbnk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGBIVFRQXyR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICAgIG1lc3NhZ2U6IGVyckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGVsc2UgaWYgKGVycm9yLnJlcXVlc3QpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiBObyByZXNwb25zZSByZWNlaXZlZGAsXG4gICAgICBlcnJvci5yZXF1ZXN0XG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ05FVFdPUktfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgTm8gcmVzcG9uc2UgcmVjZWl2ZWQgZm9yICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBsb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogJ1JFUVVFU1RfU0VUVVBfRVJST1InLFxuICAgICAgbWVzc2FnZTogYEVycm9yIHNldHRpbmcgdXAgcmVxdWVzdCBmb3IgJHtvcGVyYXRpb25OYW1lfTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgfSxcbiAgfTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlYXJjaEppcmEoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBwcm9qZWN0SWQ6IHN0cmluZyxcbiAgcXVlcnk6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9qaXJhL3NlYXJjaGA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3Q8UHl0aG9uQXBpUmVzcG9uc2U8YW55Pj4oZW5kcG9pbnQsIHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIHByb2plY3RfaWQ6IHByb2plY3RJZCxcbiAgICAgIHF1ZXJ5OiBxdWVyeSxcbiAgICB9KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UuZGF0YSwgJ3NlYXJjaEppcmEnKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihlcnJvciBhcyBBeGlvc0Vycm9yLCAnc2VhcmNoSmlyYScpO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0SmlyYUlzc3VlcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHByb2plY3RJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2ppcmEvbGlzdC1pc3N1ZXNgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPGFueT4+KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBwcm9qZWN0X2lkOiBwcm9qZWN0SWQsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdsaXN0SmlyYUlzc3VlcycpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yIGFzIEF4aW9zRXJyb3IsICdsaXN0SmlyYUlzc3VlcycpO1xuICB9XG59XG4iXX0=
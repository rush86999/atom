"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.searchAsana = searchAsana;
exports.listAsanaTasks = listAsanaTasks;
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
async function searchAsana(userId, projectId, query) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/asana/search`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            project_id: projectId,
            query: query,
        });
        return handlePythonApiResponse(response.data, 'searchAsana');
    }
    catch (error) {
        return handleAxiosError(error, 'searchAsana');
    }
}
async function listAsanaTasks(userId, projectId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/asana/list-tasks`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            project_id: projectId,
        });
        return handlePythonApiResponse(response.data, 'listAsanaTasks');
    }
    catch (error) {
        return handleAxiosError(error, 'listAsanaTasks');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXNhbmFTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJhc2FuYVNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQXVFQSxrQ0EwQkM7QUFFRCx3Q0F3QkM7QUEzSEQsa0RBQTBDO0FBSzFDLGdHQUErRztBQUMvRyxnRkFBNkU7QUFFN0Usa0VBQWtFO0FBQ2xFLFNBQVMsdUJBQXVCLENBQzlCLFFBQThCLEVBQzlCLGFBQXFCO0lBRXJCLElBQUksUUFBUSxDQUFDLEVBQUUsSUFBSSxRQUFRLENBQUMsSUFBSSxLQUFLLFNBQVMsRUFBRSxDQUFDO1FBQy9DLE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLENBQUM7SUFDM0MsQ0FBQztJQUNELGVBQU0sQ0FBQyxJQUFJLENBQ1QsSUFBSSxhQUFhLDhCQUE4QixRQUFRLENBQUMsRUFBRSxFQUFFLEVBQzVELFFBQVEsQ0FBQyxLQUFLLENBQ2YsQ0FBQztJQUNGLE9BQU87UUFDTCxFQUFFLEVBQUUsS0FBSztRQUNULEtBQUssRUFBRTtZQUNMLElBQUksRUFBRSxRQUFRLENBQUMsS0FBSyxFQUFFLElBQUksSUFBSSxrQkFBa0I7WUFDaEQsT0FBTyxFQUFFLFFBQVEsQ0FBQyxLQUFLLEVBQUUsT0FBTyxJQUFJLGFBQWEsYUFBYSxHQUFHO1lBQ2pFLE9BQU8sRUFBRSxRQUFRLENBQUMsS0FBSyxFQUFFLE9BQU87U0FDakM7S0FDRixDQUFDO0FBQ0osQ0FBQztBQUVELHdDQUF3QztBQUN4QyxTQUFTLGdCQUFnQixDQUN2QixLQUFpQixFQUNqQixhQUFxQjtJQUVyQixJQUFJLEtBQUssQ0FBQyxRQUFRLEVBQUUsQ0FBQztRQUNuQixlQUFNLENBQUMsS0FBSyxDQUNWLElBQUksYUFBYSxZQUFZLEtBQUssQ0FBQyxRQUFRLENBQUMsTUFBTSxFQUFFLEVBQ3BELEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUNwQixDQUFDO1FB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YXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7XG4gIFNraWxsUmVzcG9uc2UsXG4gIFB5dGhvbkFwaVJlc3BvbnNlLFxufSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvdHlwZXMnOyAvLyBBZGp1c3QgcGF0aFxuaW1wb3J0IHsgUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9sb2dnZXInO1xuXG4vLyBIZWxwZXIgdG8gaGFuZGxlIFB5dGhvbiBBUEkgcmVzcG9uc2VzLCBjYW4gYmUgY2VudHJhbGl6ZWQgbGF0ZXJcbmZ1bmN0aW9uIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlPFQ+KFxuICByZXNwb25zZTogUHl0aG9uQXBpUmVzcG9uc2U8VD4sXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxUPiB7XG4gIGlmIChyZXNwb25zZS5vayAmJiByZXNwb25zZS5kYXRhICE9PSB1bmRlZmluZWQpIHtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzcG9uc2UuZGF0YSB9O1xuICB9XG4gIGxvZ2dlci53YXJuKFxuICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRmFpbGVkIEFQSSBjYWxsLiBBUEkgb2s6ICR7cmVzcG9uc2Uub2t9YCxcbiAgICByZXNwb25zZS5lcnJvclxuICApO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogcmVzcG9uc2UuZXJyb3I/LmNvZGUgfHwgJ1BZVEhPTl9BUElfRVJST1InLFxuICAgICAgbWVzc2FnZTogcmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICBkZXRhaWxzOiByZXNwb25zZS5lcnJvcj8uZGV0YWlscyxcbiAgICB9LFxuICB9O1xufVxuXG4vLyBIZWxwZXIgdG8gaGFuZGxlIG5ldHdvcmsvYXhpb3MgZXJyb3JzXG5mdW5jdGlvbiBoYW5kbGVBeGlvc0Vycm9yKFxuICBlcnJvcjogQXhpb3NFcnJvcixcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPG51bGw+IHtcbiAgaWYgKGVycm9yLnJlc3BvbnNlKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgIGVycm9yLnJlc3BvbnNlLmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVyckRhdGEgPSBlcnJvci5yZXNwb25zZS5kYXRhIGFzIGFueTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogYEhUVFBfJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgICAgbWVzc2FnZTogZXJyRGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoZXJyb3IucmVxdWVzdCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6IE5vIHJlc3BvbnNlIHJlY2VpdmVkYCxcbiAgICAgIGVycm9yLnJlcXVlc3RcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTkVUV09SS19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBObyByZXNwb25zZSByZWNlaXZlZCBmb3IgJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiAnUkVRVUVTVF9TRVRVUF9FUlJPUicsXG4gICAgICBtZXNzYWdlOiBgRXJyb3Igc2V0dGluZyB1cCByZXF1ZXN0IGZvciAke29wZXJhdGlvbk5hbWV9OiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICB9LFxuICB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VhcmNoQXNhbmEoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBwcm9qZWN0SWQ6IHN0cmluZyxcbiAgcXVlcnk6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9hc2FuYS9zZWFyY2hgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPGFueT4+KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBwcm9qZWN0X2lkOiBwcm9qZWN0SWQsXG4gICAgICBxdWVyeTogcXVlcnksXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdzZWFyY2hBc2FuYScpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yIGFzIEF4aW9zRXJyb3IsICdzZWFyY2hBc2FuYScpO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0QXNhbmFUYXNrcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHByb2plY3RJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2FzYW5hL2xpc3QtdGFza3NgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0PFB5dGhvbkFwaVJlc3BvbnNlPGFueT4+KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBwcm9qZWN0X2lkOiBwcm9qZWN0SWQsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdsaXN0QXNhbmFUYXNrcycpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yIGFzIEF4aW9zRXJyb3IsICdsaXN0QXNhbmFUYXNrcycpO1xuICB9XG59XG4iXX0=
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createGreenhouseCandidateFromLinkedInProfile = createGreenhouseCandidateFromLinkedInProfile;
exports.getGreenhouseCandidateSummary = getGreenhouseCandidateSummary;
exports.createTrelloCardFromGreenhouseCandidate = createTrelloCardFromGreenhouseCandidate;
const axios_1 = __importDefault(require("axios"));
const constants_1 = require("../../atomic-docker/project/functions/atom-agent/_libs/constants");
const logger_1 = require("../../atomic-docker/project/functions/_utils/logger");
// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse(response, // Adjust type as per actual Python API response structure
operationName) {
    if (response.data && response.data.ok && response.data.data) {
        return { ok: true, data: response.data.data };
    }
    logger_1.logger.warn(`[${operationName}] Failed API call.`, response.data?.error);
    return {
        ok: false,
        error: {
            code: response.data?.error?.code || 'PYTHON_API_ERROR',
            message: response.data?.error?.message || `Failed to ${operationName}.`,
            details: response.data?.error?.details,
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
async function createGreenhouseCandidateFromLinkedInProfile(userId, linkedInProfileUrl) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/recruiting/create-greenhouse-candidate-from-linkedin-profile`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            linkedin_profile_url: linkedInProfileUrl,
        });
        return handlePythonApiResponse(response, 'createGreenhouseCandidateFromLinkedInProfile');
    }
    catch (error) {
        return handleAxiosError(error, 'createGreenhouseCandidateFromLinkedInProfile');
    }
}
async function getGreenhouseCandidateSummary(userId, candidateId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/recruiting/greenhouse-candidate-summary/${candidateId}?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response, 'getGreenhouseCandidateSummary');
    }
    catch (error) {
        return handleAxiosError(error, 'getGreenhouseCandidateSummary');
    }
}
async function createTrelloCardFromGreenhouseCandidate(userId, candidateId, trelloListId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/recruiting/create-trello-card-from-greenhouse-candidate`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            candidate_id: candidateId,
            trello_list_id: trelloListId,
        });
        return handlePythonApiResponse(response, 'createTrelloCardFromGreenhouseCandidate');
    }
    catch (error) {
        return handleAxiosError(error, 'createTrelloCardFromGreenhouseCandidate');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVjcnVpdGluZ01hbmFnZXJTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJyZWNydWl0aW5nTWFuYWdlclNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWlFQSxvR0E4QkM7QUFFRCxzRUF3QkM7QUFFRCwwRkFnQ0M7QUEzSkQsa0RBQTBDO0FBRTFDLGdHQUErRztBQUMvRyxnRkFBNkU7QUFFN0Usa0VBQWtFO0FBQ2xFLFNBQVMsdUJBQXVCLENBQzlCLFFBQWEsRUFBRSwwREFBMEQ7QUFDekUsYUFBcUI7SUFFckIsSUFBSSxRQUFRLENBQUMsSUFBSSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsRUFBRSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDNUQsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFDaEQsQ0FBQztJQUNELGVBQU0sQ0FBQyxJQUFJLENBQUMsSUFBSSxhQUFhLG9CQUFvQixFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxDQUFDLENBQUM7SUFDekUsT0FBTztRQUNMLEVBQUUsRUFBRSxLQUFLO1FBQ1QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxrQkFBa0I7WUFDdEQsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsR0FBRztZQUN2RSxPQUFPLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsT0FBTztTQUN2QztLQUNGLENBQUM7QUFDSixDQUFDO0FBRUQsd0NBQXdDO0FBQ3hDLFNBQVMsZ0JBQWdCLENBQ3ZCLEtBQWlCLEVBQ2pCLGFBQXFCO0lBRXJCLElBQUksS0FBSyxDQUFDLFFBQVEsRUFBRSxDQUFDO1FBQ25CLGVB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Q0FBQztBQUNILENBQUM7QUFFTSxLQUFLLFVBQVUsdUNBQXVDLENBQzNELE1BQWMsRUFDZCxXQUFtQixFQUNuQixZQUFvQjtJQUVwQixJQUFJLENBQUMsdUNBQTJCLEVBQUUsQ0FBQztRQUNqQyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGNBQWM7Z0JBQ3BCLE9BQU8sRUFBRSwyQ0FBMkM7YUFDckQ7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUNELE1BQU0sUUFBUSxHQUFHLEdBQUcsdUNBQTJCLDhEQUE4RCxDQUFDO0lBRTlHLElBQUksQ0FBQztRQUNILE1BQU0sUUFBUSxHQUFHLE1BQU0sZUFBSyxDQUFDLElBQUksQ0FBQyxRQUFRLEVBQUU7WUFDMUMsT0FBTyxFQUFFLE1BQU07WUFDZixZQUFZLEVBQUUsV0FBVztZQUN6QixjQUFjLEVBQUUsWUFBWTtTQUM3QixDQUFDLENBQUM7UUFDSCxPQUFPLHVCQUF1QixDQUM1QixRQUFRLEVBQ1IseUNBQXlDLENBQzFDLENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sZ0JBQWdCLENBQ3JCLEtBQW1CLEVBQ25CLHlDQUF5QyxDQUMxQyxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7IFNraWxsUmVzcG9uc2UgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvdHlwZXMnOyAvLyBBZGp1c3QgcGF0aFxuaW1wb3J0IHsgUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9sb2dnZXInO1xuXG4vLyBIZWxwZXIgdG8gaGFuZGxlIFB5dGhvbiBBUEkgcmVzcG9uc2VzLCBjYW4gYmUgY2VudHJhbGl6ZWQgbGF0ZXJcbmZ1bmN0aW9uIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlPFQ+KFxuICByZXNwb25zZTogYW55LCAvLyBBZGp1c3QgdHlwZSBhcyBwZXIgYWN0dWFsIFB5dGhvbiBBUEkgcmVzcG9uc2Ugc3RydWN0dXJlXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxUPiB7XG4gIGlmIChyZXNwb25zZS5kYXRhICYmIHJlc3BvbnNlLmRhdGEub2sgJiYgcmVzcG9uc2UuZGF0YS5kYXRhKSB7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmRhdGEuZGF0YSB9O1xuICB9XG4gIGxvZ2dlci53YXJuKGBbJHtvcGVyYXRpb25OYW1lfV0gRmFpbGVkIEFQSSBjYWxsLmAsIHJlc3BvbnNlLmRhdGE/LmVycm9yKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5jb2RlIHx8ICdQWVRIT05fQVBJX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgZGV0YWlsczogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmRldGFpbHMsXG4gICAgfSxcbiAgfTtcbn1cblxuLy8gSGVscGVyIHRvIGhhbmRsZSBuZXR3b3JrL2F4aW9zIGVycm9yc1xuZnVuY3Rpb24gaGFuZGxlQXhpb3NFcnJvcihcbiAgZXJyb3I6IEF4aW9zRXJyb3IsXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxudWxsPiB7XG4gIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICBlcnJvci5yZXNwb25zZS5kYXRhXG4gICAgKTtcbiAgICBjb25zdCBlcnJEYXRhID0gZXJyb3IucmVzcG9uc2UuZGF0YSBhcyBhbnk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGBIVFRQXyR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICAgIG1lc3NhZ2U6IGVyckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGVsc2UgaWYgKGVycm9yLnJlcXVlc3QpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiBObyByZXNwb25zZSByZWNlaXZlZGAsXG4gICAgICBlcnJvci5yZXF1ZXN0XG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ05FVFdPUktfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgTm8gcmVzcG9uc2UgcmVjZWl2ZWQgZm9yICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBsb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogJ1JFUVVFU1RfU0VUVVBfRVJST1InLFxuICAgICAgbWVzc2FnZTogYEVycm9yIHNldHRpbmcgdXAgcmVxdWVzdCBmb3IgJHtvcGVyYXRpb25OYW1lfTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgfSxcbiAgfTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZUdyZWVuaG91c2VDYW5kaWRhdGVGcm9tTGlua2VkSW5Qcm9maWxlKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgbGlua2VkSW5Qcm9maWxlVXJsOiBzdHJpbmdcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxhbnk+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvcmVjcnVpdGluZy9jcmVhdGUtZ3JlZW5ob3VzZS1jYW5kaWRhdGUtZnJvbS1saW5rZWRpbi1wcm9maWxlYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgbGlua2VkaW5fcHJvZmlsZV91cmw6IGxpbmtlZEluUHJvZmlsZVVybCxcbiAgICB9KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UoXG4gICAgICByZXNwb25zZSxcbiAgICAgICdjcmVhdGVHcmVlbmhvdXNlQ2FuZGlkYXRlRnJvbUxpbmtlZEluUHJvZmlsZSdcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKFxuICAgICAgZXJyb3IgYXMgQXhpb3NFcnJvcixcbiAgICAgICdjcmVhdGVHcmVlbmhvdXNlQ2FuZGlkYXRlRnJvbUxpbmtlZEluUHJvZmlsZSdcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRHcmVlbmhvdXNlQ2FuZGlkYXRlU3VtbWFyeShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbmRpZGF0ZUlkOiBzdHJpbmdcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxhbnk+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvcmVjcnVpdGluZy9ncmVlbmhvdXNlLWNhbmRpZGF0ZS1zdW1tYXJ5LyR7Y2FuZGlkYXRlSWR9P3VzZXJfaWQ9JHt1c2VySWR9YDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0KGVuZHBvaW50KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UsICdnZXRHcmVlbmhvdXNlQ2FuZGlkYXRlU3VtbWFyeScpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKFxuICAgICAgZXJyb3IgYXMgQXhpb3NFcnJvcixcbiAgICAgICdnZXRHcmVlbmhvdXNlQ2FuZGlkYXRlU3VtbWFyeSdcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjcmVhdGVUcmVsbG9DYXJkRnJvbUdyZWVuaG91c2VDYW5kaWRhdGUoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYW5kaWRhdGVJZDogc3RyaW5nLFxuICB0cmVsbG9MaXN0SWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9yZWNydWl0aW5nL2NyZWF0ZS10cmVsbG8tY2FyZC1mcm9tLWdyZWVuaG91c2UtY2FuZGlkYXRlYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgY2FuZGlkYXRlX2lkOiBjYW5kaWRhdGVJZCxcbiAgICAgIHRyZWxsb19saXN0X2lkOiB0cmVsbG9MaXN0SWQsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKFxuICAgICAgcmVzcG9uc2UsXG4gICAgICAnY3JlYXRlVHJlbGxvQ2FyZEZyb21HcmVlbmhvdXNlQ2FuZGlkYXRlJ1xuICAgICk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoXG4gICAgICBlcnJvciBhcyBBeGlvc0Vycm9yLFxuICAgICAgJ2NyZWF0ZVRyZWxsb0NhcmRGcm9tR3JlZW5ob3VzZUNhbmRpZGF0ZSdcbiAgICApO1xuICB9XG59XG4iXX0=
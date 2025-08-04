"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createJiraIssueFromSalesforceCase = createJiraIssueFromSalesforceCase;
exports.getJiraIssueSummary = getJiraIssueSummary;
exports.createTrelloCardFromJiraIssue = createTrelloCardFromJiraIssue;
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
async function createJiraIssueFromSalesforceCase(userId, salesforceCaseId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/it/create-jira-issue-from-salesforce-case`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            salesforce_case_id: salesforceCaseId,
        });
        return handlePythonApiResponse(response, 'createJiraIssueFromSalesforceCase');
    }
    catch (error) {
        return handleAxiosError(error, 'createJiraIssueFromSalesforceCase');
    }
}
async function getJiraIssueSummary(userId, issueId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/it/jira-issue-summary/${issueId}?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response, 'getJiraIssueSummary');
    }
    catch (error) {
        return handleAxiosError(error, 'getJiraIssueSummary');
    }
}
async function createTrelloCardFromJiraIssue(userId, issueId, trelloListId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/it/create-trello-card-from-jira-issue`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            issue_id: issueId,
            trello_list_id: trelloListId,
        });
        return handlePythonApiResponse(response, 'createTrelloCardFromJiraIssue');
    }
    catch (error) {
        return handleAxiosError(error, 'createTrelloCardFromJiraIssue');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaXRNYW5hZ2VyU2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaXRNYW5hZ2VyU2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBaUVBLDhFQThCQztBQUVELGtEQXFCQztBQUVELHNFQTZCQztBQXJKRCxrREFBMEM7QUFFMUMsZ0dBQStHO0FBQy9HLGdGQUE2RTtBQUU3RSxrRUFBa0U7QUFDbEUsU0FBUyx1QkFBdUIsQ0FDOUIsUUFBYSxFQUFFLDBEQUEwRDtBQUN6RSxhQUFxQjtJQUVyQixJQUFJLFFBQVEsQ0FBQyxJQUFJLElBQUksUUFBUSxDQUFDLElBQUksQ0FBQyxFQUFFLElBQUksUUFBUSxDQUFDLElBQUksQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUM1RCxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsUUFBUSxDQUFDLElBQUksQ0FBQyxJQUFJLEVBQUUsQ0FBQztJQUNoRCxDQUFDO0lBQ0QsZUFBTSxDQUFDLElBQUksQ0FBQyxJQUFJLGFBQWEsb0JBQW9CLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLENBQUMsQ0FBQztJQUN6RSxPQUFPO1FBQ0wsRUFBRSxFQUFFLEtBQUs7UUFDVCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsSUFBSSxJQUFJLGtCQUFrQjtZQUN0RCxPQUFPLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsT0FBTyxJQUFJLGFBQWEsYUFBYSxHQUFHO1lBQ3ZFLE9BQU8sRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPO1NBQ3ZDO0tBQ0YsQ0FBQztBQUNKLENBQUM7QUFFRCx3Q0FBd0M7QUFDeEMsU0FBUyxnQkFBZ0IsQ0FDdkIsS0FBaUIsRUFDakIsYUFBcUI7SUFFckIsSUFBSSxLQUFLLENBQUMsUUFBUSxFQUFFLENBQUM7UUFDbkIsZUFBTSxDQUFDLEtBQUssQ0FD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S0FBSyxVQUFVLDZCQUE2QixDQUNqRCxNQUFjLEVBQ2QsT0FBZSxFQUNmLFlBQW9CO0lBRXBCLElBQUksQ0FBQyx1Q0FBMkIsRUFBRSxDQUFDO1FBQ2pDLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsY0FBYztnQkFDcEIsT0FBTyxFQUFFLDJDQUEyQzthQUNyRDtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxRQUFRLEdBQUcsR0FBRyx1Q0FBMkIsNENBQTRDLENBQUM7SUFFNUYsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxlQUFLLENBQUMsSUFBSSxDQUFDLFFBQVEsRUFBRTtZQUMxQyxPQUFPLEVBQUUsTUFBTTtZQUNmLFFBQVEsRUFBRSxPQUFPO1lBQ2pCLGNBQWMsRUFBRSxZQUFZO1NBQzdCLENBQUMsQ0FBQztRQUNILE9BQU8sdUJBQXVCLENBQUMsUUFBUSxFQUFFLCtCQUErQixDQUFDLENBQUM7SUFDNUUsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLGdCQUFnQixDQUNyQixLQUFtQixFQUNuQiwrQkFBK0IsQ0FDaEMsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGF4aW9zLCB7IEF4aW9zRXJyb3IgfSBmcm9tICdheGlvcyc7XG5pbXBvcnQgeyBTa2lsbFJlc3BvbnNlIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3R5cGVzJzsgLy8gQWRqdXN0IHBhdGhcbmltcG9ydCB7IFBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9fdXRpbHMvbG9nZ2VyJztcblxuLy8gSGVscGVyIHRvIGhhbmRsZSBQeXRob24gQVBJIHJlc3BvbnNlcywgY2FuIGJlIGNlbnRyYWxpemVkIGxhdGVyXG5mdW5jdGlvbiBoYW5kbGVQeXRob25BcGlSZXNwb25zZTxUPihcbiAgcmVzcG9uc2U6IGFueSwgLy8gQWRqdXN0IHR5cGUgYXMgcGVyIGFjdHVhbCBQeXRob24gQVBJIHJlc3BvbnNlIHN0cnVjdHVyZVxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8VD4ge1xuICBpZiAocmVzcG9uc2UuZGF0YSAmJiByZXNwb25zZS5kYXRhLm9rICYmIHJlc3BvbnNlLmRhdGEuZGF0YSkge1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXNwb25zZS5kYXRhLmRhdGEgfTtcbiAgfVxuICBsb2dnZXIud2FybihgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCBBUEkgY2FsbC5gLCByZXNwb25zZS5kYXRhPy5lcnJvcik7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8uY29kZSB8fCAnUFlUSE9OX0FQSV9FUlJPUicsXG4gICAgICBtZXNzYWdlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIGRldGFpbHM6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5kZXRhaWxzLFxuICAgIH0sXG4gIH07XG59XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgbmV0d29yay9heGlvcyBlcnJvcnNcbmZ1bmN0aW9uIGhhbmRsZUF4aW9zRXJyb3IoXG4gIGVycm9yOiBBeGlvc0Vycm9yLFxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8bnVsbD4ge1xuICBpZiAoZXJyb3IucmVzcG9uc2UpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgZXJyb3IucmVzcG9uc2UuZGF0YVxuICAgICk7XG4gICAgY29uc3QgZXJyRGF0YSA9IGVycm9yLnJlc3BvbnNlLmRhdGEgYXMgYW55O1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBgSFRUUF8ke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgICBtZXNzYWdlOiBlcnJEYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBlbHNlIGlmIChlcnJvci5yZXF1ZXN0KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogTm8gcmVzcG9uc2UgcmVjZWl2ZWRgLFxuICAgICAgZXJyb3IucmVxdWVzdFxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdORVRXT1JLX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYE5vIHJlc3BvbnNlIHJlY2VpdmVkIGZvciAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgbG9nZ2VyLmVycm9yKGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6ICdSRVFVRVNUX1NFVFVQX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IGBFcnJvciBzZXR0aW5nIHVwIHJlcXVlc3QgZm9yICR7b3BlcmF0aW9uTmFtZX06ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgIH0sXG4gIH07XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjcmVhdGVKaXJhSXNzdWVGcm9tU2FsZXNmb3JjZUNhc2UoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBzYWxlc2ZvcmNlQ2FzZUlkOiBzdHJpbmdcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxhbnk+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvaXQvY3JlYXRlLWppcmEtaXNzdWUtZnJvbS1zYWxlc2ZvcmNlLWNhc2VgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBzYWxlc2ZvcmNlX2Nhc2VfaWQ6IHNhbGVzZm9yY2VDYXNlSWQsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKFxuICAgICAgcmVzcG9uc2UsXG4gICAgICAnY3JlYXRlSmlyYUlzc3VlRnJvbVNhbGVzZm9yY2VDYXNlJ1xuICAgICk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoXG4gICAgICBlcnJvciBhcyBBeGlvc0Vycm9yLFxuICAgICAgJ2NyZWF0ZUppcmFJc3N1ZUZyb21TYWxlc2ZvcmNlQ2FzZSdcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRKaXJhSXNzdWVTdW1tYXJ5KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgaXNzdWVJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2l0L2ppcmEtaXNzdWUtc3VtbWFyeS8ke2lzc3VlSWR9P3VzZXJfaWQ9JHt1c2VySWR9YDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0KGVuZHBvaW50KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UsICdnZXRKaXJhSXNzdWVTdW1tYXJ5Jyk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ2dldEppcmFJc3N1ZVN1bW1hcnknKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlVHJlbGxvQ2FyZEZyb21KaXJhSXNzdWUoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBpc3N1ZUlkOiBzdHJpbmcsXG4gIHRyZWxsb0xpc3RJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2l0L2NyZWF0ZS10cmVsbG8tY2FyZC1mcm9tLWppcmEtaXNzdWVgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBpc3N1ZV9pZDogaXNzdWVJZCxcbiAgICAgIHRyZWxsb19saXN0X2lkOiB0cmVsbG9MaXN0SWQsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLCAnY3JlYXRlVHJlbGxvQ2FyZEZyb21KaXJhSXNzdWUnKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihcbiAgICAgIGVycm9yIGFzIEF4aW9zRXJyb3IsXG4gICAgICAnY3JlYXRlVHJlbGxvQ2FyZEZyb21KaXJhSXNzdWUnXG4gICAgKTtcbiAgfVxufVxuIl19
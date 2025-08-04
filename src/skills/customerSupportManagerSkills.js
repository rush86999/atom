"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createZendeskTicketFromSalesforceCase = createZendeskTicketFromSalesforceCase;
exports.getZendeskTicketSummary = getZendeskTicketSummary;
exports.createTrelloCardFromZendeskTicket = createTrelloCardFromZendeskTicket;
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
async function createZendeskTicketFromSalesforceCase(userId, salesforceCaseId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/customer-support/create-zendesk-ticket-from-salesforce-case`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            salesforce_case_id: salesforceCaseId,
        });
        return handlePythonApiResponse(response, 'createZendeskTicketFromSalesforceCase');
    }
    catch (error) {
        return handleAxiosError(error, 'createZendeskTicketFromSalesforceCase');
    }
}
async function getZendeskTicketSummary(userId, ticketId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/customer-support/zendesk-ticket-summary/${ticketId}?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response, 'getZendeskTicketSummary');
    }
    catch (error) {
        return handleAxiosError(error, 'getZendeskTicketSummary');
    }
}
async function createTrelloCardFromZendeskTicket(userId, ticketId, trelloListId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/customer-support/create-trello-card-from-zendesk-ticket`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            ticket_id: ticketId,
            trello_list_id: trelloListId,
        });
        return handlePythonApiResponse(response, 'createTrelloCardFromZendeskTicket');
    }
    catch (error) {
        return handleAxiosError(error, 'createTrelloCardFromZendeskTicket');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY3VzdG9tZXJTdXBwb3J0TWFuYWdlclNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImN1c3RvbWVyU3VwcG9ydE1hbmFnZXJTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFpRUEsc0ZBOEJDO0FBRUQsMERBcUJDO0FBRUQsOEVBZ0NDO0FBeEpELGtEQUEwQztBQUUxQyxnR0FBK0c7QUFDL0csZ0ZBQTZFO0FBRTdFLGtFQUFrRTtBQUNsRSxTQUFTLHVCQUF1QixDQUM5QixRQUFhLEVBQUUsMERBQTBEO0FBQ3pFLGFBQXFCO0lBRXJCLElBQUksUUFBUSxDQUFDLElBQUksSUFBSSxRQUFRLENBQUMsSUFBSSxDQUFDLEVBQUUsSUFBSSxRQUFRLENBQUMsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO1FBQzVELE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxRQUFRLENBQUMsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQ2hELENBQUM7SUFDRCxlQUFNLENBQUMsSUFBSSxDQUFDLElBQUksYUFBYSxvQkFBb0IsRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssQ0FBQyxDQUFDO0lBQ3pFLE9BQU87UUFDTCxFQUFFLEVBQUUsS0FBSztRQUNULEtBQUssRUFBRTtZQUNMLElBQUksRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxJQUFJLElBQUksa0JBQWtCO1lBQ3RELE9BQU8sRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPLElBQUksYUFBYSxhQUFhLEdBQUc7WUFDdkUsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU87U0FDdkM7S0FDRixDQUFDO0FBQ0osQ0FBQztBQUVELHdDQUF3QztBQUN4QyxTQUFTLGdCQUFnQixDQUN2QixLQUFpQixFQUNqQixhQUFxQjtJQUVyQixJQUFJLEtBQUssQ0FBQyxRQUFRLEVBQUUsQ0FB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QztJQUMxRSxDQUFDO0FBQ0gsQ0FBQztBQUVNLEtBQUssVUFBVSxpQ0FBaUMsQ0FDckQsTUFBYyxFQUNkLFFBQWdCLEVBQ2hCLFlBQW9CO0lBRXBCLElBQUksQ0FBQyx1Q0FBMkIsRUFBRSxDQUFDO1FBQ2pDLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsY0FBYztnQkFDcEIsT0FBTyxFQUFFLDJDQUEyQzthQUNyRDtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxRQUFRLEdBQUcsR0FBRyx1Q0FBMkIsOERBQThELENBQUM7SUFFOUcsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxlQUFLLENBQUMsSUFBSSxDQUFDLFFBQVEsRUFBRTtZQUMxQyxPQUFPLEVBQUUsTUFBTTtZQUNmLFNBQVMsRUFBRSxRQUFRO1lBQ25CLGNBQWMsRUFBRSxZQUFZO1NBQzdCLENBQUMsQ0FBQztRQUNILE9BQU8sdUJBQXVCLENBQzVCLFFBQVEsRUFDUixtQ0FBbUMsQ0FDcEMsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxnQkFBZ0IsQ0FDckIsS0FBbUIsRUFDbkIsbUNBQW1DLENBQ3BDLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBheGlvcywgeyBBeGlvc0Vycm9yIH0gZnJvbSAnYXhpb3MnO1xuaW1wb3J0IHsgU2tpbGxSZXNwb25zZSB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC90eXBlcyc7IC8vIEFkanVzdCBwYXRoXG5pbXBvcnQgeyBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2xvZ2dlcic7XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgUHl0aG9uIEFQSSByZXNwb25zZXMsIGNhbiBiZSBjZW50cmFsaXplZCBsYXRlclxuZnVuY3Rpb24gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2U8VD4oXG4gIHJlc3BvbnNlOiBhbnksIC8vIEFkanVzdCB0eXBlIGFzIHBlciBhY3R1YWwgUHl0aG9uIEFQSSByZXNwb25zZSBzdHJ1Y3R1cmVcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPFQ+IHtcbiAgaWYgKHJlc3BvbnNlLmRhdGEgJiYgcmVzcG9uc2UuZGF0YS5vayAmJiByZXNwb25zZS5kYXRhLmRhdGEpIHtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzcG9uc2UuZGF0YS5kYXRhIH07XG4gIH1cbiAgbG9nZ2VyLndhcm4oYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgQVBJIGNhbGwuYCwgcmVzcG9uc2UuZGF0YT8uZXJyb3IpO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmNvZGUgfHwgJ1BZVEhPTl9BUElfRVJST1InLFxuICAgICAgbWVzc2FnZTogcmVzcG9uc2UuZGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICBkZXRhaWxzOiByZXNwb25zZS5kYXRhPy5lcnJvcj8uZGV0YWlscyxcbiAgICB9LFxuICB9O1xufVxuXG4vLyBIZWxwZXIgdG8gaGFuZGxlIG5ldHdvcmsvYXhpb3MgZXJyb3JzXG5mdW5jdGlvbiBoYW5kbGVBeGlvc0Vycm9yKFxuICBlcnJvcjogQXhpb3NFcnJvcixcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPG51bGw+IHtcbiAgaWYgKGVycm9yLnJlc3BvbnNlKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgIGVycm9yLnJlc3BvbnNlLmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVyckRhdGEgPSBlcnJvci5yZXNwb25zZS5kYXRhIGFzIGFueTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogYEhUVFBfJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgICAgbWVzc2FnZTogZXJyRGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoZXJyb3IucmVxdWVzdCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6IE5vIHJlc3BvbnNlIHJlY2VpdmVkYCxcbiAgICAgIGVycm9yLnJlcXVlc3RcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTkVUV09SS19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBObyByZXNwb25zZSByZWNlaXZlZCBmb3IgJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiAnUkVRVUVTVF9TRVRVUF9FUlJPUicsXG4gICAgICBtZXNzYWdlOiBgRXJyb3Igc2V0dGluZyB1cCByZXF1ZXN0IGZvciAke29wZXJhdGlvbk5hbWV9OiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICB9LFxuICB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlWmVuZGVza1RpY2tldEZyb21TYWxlc2ZvcmNlQ2FzZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHNhbGVzZm9yY2VDYXNlSWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9jdXN0b21lci1zdXBwb3J0L2NyZWF0ZS16ZW5kZXNrLXRpY2tldC1mcm9tLXNhbGVzZm9yY2UtY2FzZWA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoZW5kcG9pbnQsIHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIHNhbGVzZm9yY2VfY2FzZV9pZDogc2FsZXNmb3JjZUNhc2VJZCxcbiAgICB9KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UoXG4gICAgICByZXNwb25zZSxcbiAgICAgICdjcmVhdGVaZW5kZXNrVGlja2V0RnJvbVNhbGVzZm9yY2VDYXNlJ1xuICAgICk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoXG4gICAgICBlcnJvciBhcyBBeGlvc0Vycm9yLFxuICAgICAgJ2NyZWF0ZVplbmRlc2tUaWNrZXRGcm9tU2FsZXNmb3JjZUNhc2UnXG4gICAgKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0WmVuZGVza1RpY2tldFN1bW1hcnkoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aWNrZXRJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2N1c3RvbWVyLXN1cHBvcnQvemVuZGVzay10aWNrZXQtc3VtbWFyeS8ke3RpY2tldElkfT91c2VyX2lkPSR7dXNlcklkfWA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLmdldChlbmRwb2ludCk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLCAnZ2V0WmVuZGVza1RpY2tldFN1bW1hcnknKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihlcnJvciBhcyBBeGlvc0Vycm9yLCAnZ2V0WmVuZGVza1RpY2tldFN1bW1hcnknKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlVHJlbGxvQ2FyZEZyb21aZW5kZXNrVGlja2V0KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGlja2V0SWQ6IHN0cmluZyxcbiAgdHJlbGxvTGlzdElkOiBzdHJpbmdcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxhbnk+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvY3VzdG9tZXItc3VwcG9ydC9jcmVhdGUtdHJlbGxvLWNhcmQtZnJvbS16ZW5kZXNrLXRpY2tldGA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoZW5kcG9pbnQsIHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIHRpY2tldF9pZDogdGlja2V0SWQsXG4gICAgICB0cmVsbG9fbGlzdF9pZDogdHJlbGxvTGlzdElkLFxuICAgIH0pO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShcbiAgICAgIHJlc3BvbnNlLFxuICAgICAgJ2NyZWF0ZVRyZWxsb0NhcmRGcm9tWmVuZGVza1RpY2tldCdcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKFxuICAgICAgZXJyb3IgYXMgQXhpb3NFcnJvcixcbiAgICAgICdjcmVhdGVUcmVsbG9DYXJkRnJvbVplbmRlc2tUaWNrZXQnXG4gICAgKTtcbiAgfVxufVxuIl19
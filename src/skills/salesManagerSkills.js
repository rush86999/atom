"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createXeroInvoiceFromSalesforceOpportunity = createXeroInvoiceFromSalesforceOpportunity;
exports.createTrelloCardFromSalesforceOpportunity = createTrelloCardFromSalesforceOpportunity;
exports.createSalesforceContactFromXeroContact = createSalesforceContactFromXeroContact;
exports.getOpenOpportunitiesForAccount = getOpenOpportunitiesForAccount;
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
async function createXeroInvoiceFromSalesforceOpportunity(userId, opportunityId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/sales/create-invoice-from-opportunity`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            opportunity_id: opportunityId,
        });
        return handlePythonApiResponse(response, 'createXeroInvoiceFromSalesforceOpportunity');
    }
    catch (error) {
        return handleAxiosError(error, 'createXeroInvoiceFromSalesforceOpportunity');
    }
}
async function createTrelloCardFromSalesforceOpportunity(userId, opportunityId, trelloListId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/sales/create-card-from-opportunity`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            opportunity_id: opportunityId,
            trello_list_id: trelloListId,
        });
        return handlePythonApiResponse(response, 'createTrelloCardFromSalesforceOpportunity');
    }
    catch (error) {
        return handleAxiosError(error, 'createTrelloCardFromSalesforceOpportunity');
    }
}
async function createSalesforceContactFromXeroContact(userId, xeroContactId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/sales/create-salesforce-contact-from-xero-contact`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            xero_contact_id: xeroContactId,
        });
        return handlePythonApiResponse(response, 'createSalesforceContactFromXeroContact');
    }
    catch (error) {
        return handleAxiosError(error, 'createSalesforceContactFromXeroContact');
    }
}
async function getOpenOpportunitiesForAccount(userId, accountId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/sales/open-opportunities-for-account/${accountId}?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response, 'getOpenOpportunitiesForAccount');
    }
    catch (error) {
        return handleAxiosError(error, 'getOpenOpportunitiesForAccount');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2FsZXNNYW5hZ2VyU2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic2FsZXNNYW5hZ2VyU2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBc0VBLGdHQThCQztBQUVELDhGQWdDQztBQUVELHdGQThCQztBQUVELHdFQXdCQztBQWhNRCxrREFBMEM7QUFPMUMsZ0dBQStHO0FBQy9HLGdGQUE2RTtBQUU3RSxrRUFBa0U7QUFDbEUsU0FBUyx1QkFBdUIsQ0FDOUIsUUFBYSxFQUFFLDBEQUEwRDtBQUN6RSxhQUFxQjtJQUVyQixJQUFJLFFBQVEsQ0FBQyxJQUFJLElBQUksUUFBUSxDQUFDLElBQUksQ0FBQyxFQUFFLElBQUksUUFBUSxDQUFDLElBQUksQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUM1RCxPQUFPLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsUUFBUSxDQUFDLElBQUksQ0FBQyxJQUFJLEVBQUUsQ0FBQztJQUNoRCxDQUFDO0lBQ0QsZUFBTSxDQUFDLElBQUksQ0FBQyxJQUFJLGFBQWEsb0JBQW9CLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLENBQUMsQ0FBQztJQUN6RSxPQUFPO1FBQ0wsRUFBRSxFQUFFLEtBQUs7UUFDVCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsSUFBSSxJQUFJLGtCQUFrQjtZQUN0RCxPQUFPLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsT0FBTyxJQUFJLGFBQWEsYUFBYSxHQUFHO1lBQ3ZFLE9BQU8sRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPO1NBQ3ZDO0tBQ0YsQ0FBQztBQUNKLENBQUM7QUFFRCx3Q0FBd0M7QUFDeEMsU0FBUyxnQkFBZ0IsQ0FDdkIsS0FBaUIsRUFDakIsYUFBcUI7SUFFckIsSUFBSSxLQUFLLENBQUMsUUFBUSxFQUFFLENBQUM7UUFDbkIs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LGVBQUssQ0FBQyxHQUFHLENBQUMsUUFBUSxDQUFDLENBQUM7UUFDM0MsT0FBTyx1QkFBdUIsQ0FBQyxRQUFRLEVBQUUsZ0NBQWdDLENBQUMsQ0FBQztJQUM3RSxDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sZ0JBQWdCLENBQ3JCLEtBQW1CLEVBQ25CLGdDQUFnQyxDQUNqQyxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7XG4gIFNraWxsUmVzcG9uc2UsXG4gIFhlcm9JbnZvaWNlLFxuICBTYWxlc2ZvcmNlT3Bwb3J0dW5pdHksXG4gIFRyZWxsb0NhcmQsXG59IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC90eXBlcyc7IC8vIEFkanVzdCBwYXRoXG5pbXBvcnQgeyBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2xvZ2dlcic7XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgUHl0aG9uIEFQSSByZXNwb25zZXMsIGNhbiBiZSBjZW50cmFsaXplZCBsYXRlclxuZnVuY3Rpb24gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2U8VD4oXG4gIHJlc3BvbnNlOiBhbnksIC8vIEFkanVzdCB0eXBlIGFzIHBlciBhY3R1YWwgUHl0aG9uIEFQSSByZXNwb25zZSBzdHJ1Y3R1cmVcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPFQ+IHtcbiAgaWYgKHJlc3BvbnNlLmRhdGEgJiYgcmVzcG9uc2UuZGF0YS5vayAmJiByZXNwb25zZS5kYXRhLmRhdGEpIHtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzcG9uc2UuZGF0YS5kYXRhIH07XG4gIH1cbiAgbG9nZ2VyLndhcm4oYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgQVBJIGNhbGwuYCwgcmVzcG9uc2UuZGF0YT8uZXJyb3IpO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmNvZGUgfHwgJ1BZVEhPTl9BUElfRVJST1InLFxuICAgICAgbWVzc2FnZTogcmVzcG9uc2UuZGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICBkZXRhaWxzOiByZXNwb25zZS5kYXRhPy5lcnJvcj8uZGV0YWlscyxcbiAgICB9LFxuICB9O1xufVxuXG4vLyBIZWxwZXIgdG8gaGFuZGxlIG5ldHdvcmsvYXhpb3MgZXJyb3JzXG5mdW5jdGlvbiBoYW5kbGVBeGlvc0Vycm9yKFxuICBlcnJvcjogQXhpb3NFcnJvcixcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPG51bGw+IHtcbiAgaWYgKGVycm9yLnJlc3BvbnNlKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgIGVycm9yLnJlc3BvbnNlLmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVyckRhdGEgPSBlcnJvci5yZXNwb25zZS5kYXRhIGFzIGFueTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogYEhUVFBfJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgICAgbWVzc2FnZTogZXJyRGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoZXJyb3IucmVxdWVzdCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6IE5vIHJlc3BvbnNlIHJlY2VpdmVkYCxcbiAgICAgIGVycm9yLnJlcXVlc3RcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTkVUV09SS19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBObyByZXNwb25zZSByZWNlaXZlZCBmb3IgJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiAnUkVRVUVTVF9TRVRVUF9FUlJPUicsXG4gICAgICBtZXNzYWdlOiBgRXJyb3Igc2V0dGluZyB1cCByZXF1ZXN0IGZvciAke29wZXJhdGlvbk5hbWV9OiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICB9LFxuICB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlWGVyb0ludm9pY2VGcm9tU2FsZXNmb3JjZU9wcG9ydHVuaXR5KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgb3Bwb3J0dW5pdHlJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8WGVyb0ludm9pY2U+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvc2FsZXMvY3JlYXRlLWludm9pY2UtZnJvbS1vcHBvcnR1bml0eWA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoZW5kcG9pbnQsIHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIG9wcG9ydHVuaXR5X2lkOiBvcHBvcnR1bml0eUlkLFxuICAgIH0pO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShcbiAgICAgIHJlc3BvbnNlLFxuICAgICAgJ2NyZWF0ZVhlcm9JbnZvaWNlRnJvbVNhbGVzZm9yY2VPcHBvcnR1bml0eSdcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKFxuICAgICAgZXJyb3IgYXMgQXhpb3NFcnJvcixcbiAgICAgICdjcmVhdGVYZXJvSW52b2ljZUZyb21TYWxlc2ZvcmNlT3Bwb3J0dW5pdHknXG4gICAgKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlVHJlbGxvQ2FyZEZyb21TYWxlc2ZvcmNlT3Bwb3J0dW5pdHkoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBvcHBvcnR1bml0eUlkOiBzdHJpbmcsXG4gIHRyZWxsb0xpc3RJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8VHJlbGxvQ2FyZD4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9zYWxlcy9jcmVhdGUtY2FyZC1mcm9tLW9wcG9ydHVuaXR5YDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgb3Bwb3J0dW5pdHlfaWQ6IG9wcG9ydHVuaXR5SWQsXG4gICAgICB0cmVsbG9fbGlzdF9pZDogdHJlbGxvTGlzdElkLFxuICAgIH0pO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShcbiAgICAgIHJlc3BvbnNlLFxuICAgICAgJ2NyZWF0ZVRyZWxsb0NhcmRGcm9tU2FsZXNmb3JjZU9wcG9ydHVuaXR5J1xuICAgICk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoXG4gICAgICBlcnJvciBhcyBBeGlvc0Vycm9yLFxuICAgICAgJ2NyZWF0ZVRyZWxsb0NhcmRGcm9tU2FsZXNmb3JjZU9wcG9ydHVuaXR5J1xuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZVNhbGVzZm9yY2VDb250YWN0RnJvbVhlcm9Db250YWN0KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgeGVyb0NvbnRhY3RJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL3NhbGVzL2NyZWF0ZS1zYWxlc2ZvcmNlLWNvbnRhY3QtZnJvbS14ZXJvLWNvbnRhY3RgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICB4ZXJvX2NvbnRhY3RfaWQ6IHhlcm9Db250YWN0SWQsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKFxuICAgICAgcmVzcG9uc2UsXG4gICAgICAnY3JlYXRlU2FsZXNmb3JjZUNvbnRhY3RGcm9tWGVyb0NvbnRhY3QnXG4gICAgKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihcbiAgICAgIGVycm9yIGFzIEF4aW9zRXJyb3IsXG4gICAgICAnY3JlYXRlU2FsZXNmb3JjZUNvbnRhY3RGcm9tWGVyb0NvbnRhY3QnXG4gICAgKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0T3Blbk9wcG9ydHVuaXRpZXNGb3JBY2NvdW50KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYWNjb3VudElkOiBzdHJpbmdcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxTYWxlc2ZvcmNlT3Bwb3J0dW5pdHlbXT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9zYWxlcy9vcGVuLW9wcG9ydHVuaXRpZXMtZm9yLWFjY291bnQvJHthY2NvdW50SWR9P3VzZXJfaWQ9JHt1c2VySWR9YDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0KGVuZHBvaW50KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UsICdnZXRPcGVuT3Bwb3J0dW5pdGllc0ZvckFjY291bnQnKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihcbiAgICAgIGVycm9yIGFzIEF4aW9zRXJyb3IsXG4gICAgICAnZ2V0T3Blbk9wcG9ydHVuaXRpZXNGb3JBY2NvdW50J1xuICAgICk7XG4gIH1cbn1cbiJdfQ==
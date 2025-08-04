"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getFinancialSummary = getFinancialSummary;
exports.createSalesforceOpportunityFromXeroInvoice = createSalesforceOpportunityFromXeroInvoice;
exports.createTrelloCardFromXeroInvoice = createTrelloCardFromXeroInvoice;
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
async function getFinancialSummary(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/financial/summary?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response, 'getFinancialSummary');
    }
    catch (error) {
        return handleAxiosError(error, 'getFinancialSummary');
    }
}
async function createSalesforceOpportunityFromXeroInvoice(userId, invoiceId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/financial/create-opportunity-from-invoice`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            invoice_id: invoiceId,
        });
        return handlePythonApiResponse(response, 'createSalesforceOpportunityFromXeroInvoice');
    }
    catch (error) {
        return handleAxiosError(error, 'createSalesforceOpportunityFromXeroInvoice');
    }
}
async function createTrelloCardFromXeroInvoice(userId, invoiceId, trelloListId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/financial/create-card-from-invoice`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            invoice_id: invoiceId,
            trello_list_id: trelloListId,
        });
        return handlePythonApiResponse(response, 'createTrelloCardFromXeroInvoice');
    }
    catch (error) {
        return handleAxiosError(error, 'createTrelloCardFromXeroInvoice');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmluYW5jaWFsQW5hbHlzdFNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImZpbmFuY2lhbEFuYWx5c3RTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFpRUEsa0RBb0JDO0FBRUQsZ0dBOEJDO0FBRUQsMEVBNkJDO0FBcEpELGtEQUEwQztBQUUxQyxnR0FBK0c7QUFDL0csZ0ZBQTZFO0FBRTdFLGtFQUFrRTtBQUNsRSxTQUFTLHVCQUF1QixDQUM5QixRQUFhLEVBQUUsMERBQTBEO0FBQ3pFLGFBQXFCO0lBRXJCLElBQUksUUFBUSxDQUFDLElBQUksSUFBSSxRQUFRLENBQUMsSUFBSSxDQUFDLEVBQUUsSUFBSSxRQUFRLENBQUMsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO1FBQzVELE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxRQUFRLENBQUMsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQ2hELENBQUM7SUFDRCxlQUFNLENBQUMsSUFBSSxDQUFDLElBQUksYUFBYSxvQkFBb0IsRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssQ0FBQyxDQUFDO0lBQ3pFLE9BQU87UUFDTCxFQUFFLEVBQUUsS0FBSztRQUNULEtBQUssRUFBRTtZQUNMLElBQUksRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxJQUFJLElBQUksa0JBQWtCO1lBQ3RELE9BQU8sRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPLElBQUksYUFBYSxhQUFhLEdBQUc7WUFDdkUsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU87U0FDdkM7S0FDRixDQUFDO0FBQ0osQ0FBQztBQUVELHdDQUF3QztBQUN4QyxTQUFTLGdCQUFnQixDQUN2QixLQUFpQixFQUNqQixhQUFxQjtJQUVyQixJQUFJLEtBQUssQ0FBQyxRQUFRLEVBQUUsQ0FBQztRQUNuQixlQUFN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QkFBK0IsQ0FDbkQsTUFBYyxFQUNkLFNBQWlCLEVBQ2pCLFlBQW9CO0lBRXBCLElBQUksQ0FBQyx1Q0FBMkIsRUFBRSxDQUFDO1FBQ2pDLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsY0FBYztnQkFDcEIsT0FBTyxFQUFFLDJDQUEyQzthQUNyRDtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxRQUFRLEdBQUcsR0FBRyx1Q0FBMkIseUNBQXlDLENBQUM7SUFFekYsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxlQUFLLENBQUMsSUFBSSxDQUFDLFFBQVEsRUFBRTtZQUMxQyxPQUFPLEVBQUUsTUFBTTtZQUNmLFVBQVUsRUFBRSxTQUFTO1lBQ3JCLGNBQWMsRUFBRSxZQUFZO1NBQzdCLENBQUMsQ0FBQztRQUNILE9BQU8sdUJBQXVCLENBQUMsUUFBUSxFQUFFLGlDQUFpQyxDQUFDLENBQUM7SUFDOUUsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLGdCQUFnQixDQUNyQixLQUFtQixFQUNuQixpQ0FBaUMsQ0FDbEMsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGF4aW9zLCB7IEF4aW9zRXJyb3IgfSBmcm9tICdheGlvcyc7XG5pbXBvcnQgeyBTa2lsbFJlc3BvbnNlIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3R5cGVzJzsgLy8gQWRqdXN0IHBhdGhcbmltcG9ydCB7IFBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9fdXRpbHMvbG9nZ2VyJztcblxuLy8gSGVscGVyIHRvIGhhbmRsZSBQeXRob24gQVBJIHJlc3BvbnNlcywgY2FuIGJlIGNlbnRyYWxpemVkIGxhdGVyXG5mdW5jdGlvbiBoYW5kbGVQeXRob25BcGlSZXNwb25zZTxUPihcbiAgcmVzcG9uc2U6IGFueSwgLy8gQWRqdXN0IHR5cGUgYXMgcGVyIGFjdHVhbCBQeXRob24gQVBJIHJlc3BvbnNlIHN0cnVjdHVyZVxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8VD4ge1xuICBpZiAocmVzcG9uc2UuZGF0YSAmJiByZXNwb25zZS5kYXRhLm9rICYmIHJlc3BvbnNlLmRhdGEuZGF0YSkge1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXNwb25zZS5kYXRhLmRhdGEgfTtcbiAgfVxuICBsb2dnZXIud2FybihgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCBBUEkgY2FsbC5gLCByZXNwb25zZS5kYXRhPy5lcnJvcik7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8uY29kZSB8fCAnUFlUSE9OX0FQSV9FUlJPUicsXG4gICAgICBtZXNzYWdlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIGRldGFpbHM6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5kZXRhaWxzLFxuICAgIH0sXG4gIH07XG59XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgbmV0d29yay9heGlvcyBlcnJvcnNcbmZ1bmN0aW9uIGhhbmRsZUF4aW9zRXJyb3IoXG4gIGVycm9yOiBBeGlvc0Vycm9yLFxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8bnVsbD4ge1xuICBpZiAoZXJyb3IucmVzcG9uc2UpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgZXJyb3IucmVzcG9uc2UuZGF0YVxuICAgICk7XG4gICAgY29uc3QgZXJyRGF0YSA9IGVycm9yLnJlc3BvbnNlLmRhdGEgYXMgYW55O1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBgSFRUUF8ke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgICBtZXNzYWdlOiBlcnJEYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBlbHNlIGlmIChlcnJvci5yZXF1ZXN0KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogTm8gcmVzcG9uc2UgcmVjZWl2ZWRgLFxuICAgICAgZXJyb3IucmVxdWVzdFxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdORVRXT1JLX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYE5vIHJlc3BvbnNlIHJlY2VpdmVkIGZvciAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgbG9nZ2VyLmVycm9yKGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6ICdSRVFVRVNUX1NFVFVQX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IGBFcnJvciBzZXR0aW5nIHVwIHJlcXVlc3QgZm9yICR7b3BlcmF0aW9uTmFtZX06ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgIH0sXG4gIH07XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRGaW5hbmNpYWxTdW1tYXJ5KFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9maW5hbmNpYWwvc3VtbWFyeT91c2VyX2lkPSR7dXNlcklkfWA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLmdldChlbmRwb2ludCk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLCAnZ2V0RmluYW5jaWFsU3VtbWFyeScpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yIGFzIEF4aW9zRXJyb3IsICdnZXRGaW5hbmNpYWxTdW1tYXJ5Jyk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZVNhbGVzZm9yY2VPcHBvcnR1bml0eUZyb21YZXJvSW52b2ljZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGludm9pY2VJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2ZpbmFuY2lhbC9jcmVhdGUtb3Bwb3J0dW5pdHktZnJvbS1pbnZvaWNlYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgaW52b2ljZV9pZDogaW52b2ljZUlkLFxuICAgIH0pO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShcbiAgICAgIHJlc3BvbnNlLFxuICAgICAgJ2NyZWF0ZVNhbGVzZm9yY2VPcHBvcnR1bml0eUZyb21YZXJvSW52b2ljZSdcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKFxuICAgICAgZXJyb3IgYXMgQXhpb3NFcnJvcixcbiAgICAgICdjcmVhdGVTYWxlc2ZvcmNlT3Bwb3J0dW5pdHlGcm9tWGVyb0ludm9pY2UnXG4gICAgKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlVHJlbGxvQ2FyZEZyb21YZXJvSW52b2ljZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGludm9pY2VJZDogc3RyaW5nLFxuICB0cmVsbG9MaXN0SWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9maW5hbmNpYWwvY3JlYXRlLWNhcmQtZnJvbS1pbnZvaWNlYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgaW52b2ljZV9pZDogaW52b2ljZUlkLFxuICAgICAgdHJlbGxvX2xpc3RfaWQ6IHRyZWxsb0xpc3RJZCxcbiAgICB9KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UsICdjcmVhdGVUcmVsbG9DYXJkRnJvbVhlcm9JbnZvaWNlJyk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoXG4gICAgICBlcnJvciBhcyBBeGlvc0Vycm9yLFxuICAgICAgJ2NyZWF0ZVRyZWxsb0NhcmRGcm9tWGVyb0ludm9pY2UnXG4gICAgKTtcbiAgfVxufVxuIl19
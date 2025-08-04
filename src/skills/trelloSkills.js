"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.searchTrello = searchTrello;
exports.listTrelloCards = listTrelloCards;
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
async function searchTrello(userId, boardId, query) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/trello/search`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            board_id: boardId,
            query: query,
        });
        return handlePythonApiResponse(response.data, 'searchTrello');
    }
    catch (error) {
        return handleAxiosError(error, 'searchTrello');
    }
}
async function listTrelloCards(userId, boardId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/trello/list-cards`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            board_id: boardId,
        });
        return handlePythonApiResponse(response.data, 'listTrelloCards');
    }
    catch (error) {
        return handleAxiosError(error, 'listTrelloCards');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidHJlbGxvU2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidHJlbGxvU2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBdUVBLG9DQTBCQztBQUVELDBDQXdCQztBQTNIRCxrREFBMEM7QUFLMUMsZ0dBQStHO0FBQy9HLGdGQUE2RTtBQUU3RSxrRUFBa0U7QUFDbEUsU0FBUyx1QkFBdUIsQ0FDOUIsUUFBOEIsRUFDOUIsYUFBcUI7SUFFckIsSUFBSSxRQUFRLENBQUMsRUFBRSxJQUFJLFFBQVEsQ0FBQyxJQUFJLEtBQUssU0FBUyxFQUFFLENBQUM7UUFDL0MsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsQ0FBQztJQUMzQyxDQUFDO0lBQ0QsZUFBTSxDQUFDLElBQUksQ0FDVCxJQUFJLGFBQWEsOEJBQThCLFFBQVEsQ0FBQyxFQUFFLEVBQUUsRUFDNUQsUUFBUSxDQUFDLEtBQUssQ0FDZixDQUFDO0lBQ0YsT0FBTztRQUNMLEVBQUUsRUFBRSxLQUFLO1FBQ1QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLFFBQVEsQ0FBQyxLQUFLLEVBQUUsSUFBSSxJQUFJLGtCQUFrQjtZQUNoRCxPQUFPLEVBQUUsUUFBUSxDQUFDLEtBQUssRUFBRSxPQUFPLElBQUksYUFBYSxhQUFhLEdBQUc7WUFDakUsT0FBTyxFQUFFLFFBQVEsQ0FBQyxLQUFLLEVBQUUsT0FBTztTQUNqQztLQUNGLENBQUM7QUFDSixDQUFDO0FBRUQsd0NBQXdDO0FBQ3hDLFNBQVMsZ0JBQWdCLENBQ3ZCLEtBQWlCLEVBQ2pCLGFBQXFCO0lBRXJCLElBQUksS0FBSyxDQUFDLFFBQVEsRUFBRSxDQUFDO1FBQ25CLGVBQU0sQ0FBQyxLQUFLLENBQ1YsSUFBSSxhQUFhLFlBQVksS0FBSyxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQUUsRUFDcEQsS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQ3BCLENBQUM7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aW9zLCB7IEF4aW9zRXJyb3IgfSBmcm9tICdheGlvcyc7XG5pbXBvcnQge1xuICBTa2lsbFJlc3BvbnNlLFxuICBQeXRob25BcGlSZXNwb25zZSxcbn0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3R5cGVzJzsgLy8gQWRqdXN0IHBhdGhcbmltcG9ydCB7IFBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9fdXRpbHMvbG9nZ2VyJztcblxuLy8gSGVscGVyIHRvIGhhbmRsZSBQeXRob24gQVBJIHJlc3BvbnNlcywgY2FuIGJlIGNlbnRyYWxpemVkIGxhdGVyXG5mdW5jdGlvbiBoYW5kbGVQeXRob25BcGlSZXNwb25zZTxUPihcbiAgcmVzcG9uc2U6IFB5dGhvbkFwaVJlc3BvbnNlPFQ+LFxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8VD4ge1xuICBpZiAocmVzcG9uc2Uub2sgJiYgcmVzcG9uc2UuZGF0YSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmRhdGEgfTtcbiAgfVxuICBsb2dnZXIud2FybihcbiAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCBBUEkgY2FsbC4gQVBJIG9rOiAke3Jlc3BvbnNlLm9rfWAsXG4gICAgcmVzcG9uc2UuZXJyb3JcbiAgKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6IHJlc3BvbnNlLmVycm9yPy5jb2RlIHx8ICdQWVRIT05fQVBJX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IHJlc3BvbnNlLmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgZGV0YWlsczogcmVzcG9uc2UuZXJyb3I/LmRldGFpbHMsXG4gICAgfSxcbiAgfTtcbn1cblxuLy8gSGVscGVyIHRvIGhhbmRsZSBuZXR3b3JrL2F4aW9zIGVycm9yc1xuZnVuY3Rpb24gaGFuZGxlQXhpb3NFcnJvcihcbiAgZXJyb3I6IEF4aW9zRXJyb3IsXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxudWxsPiB7XG4gIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICBlcnJvci5yZXNwb25zZS5kYXRhXG4gICAgKTtcbiAgICBjb25zdCBlcnJEYXRhID0gZXJyb3IucmVzcG9uc2UuZGF0YSBhcyBhbnk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGBIVFRQXyR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICAgIG1lc3NhZ2U6IGVyckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGVsc2UgaWYgKGVycm9yLnJlcXVlc3QpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiBObyByZXNwb25zZSByZWNlaXZlZGAsXG4gICAgICBlcnJvci5yZXF1ZXN0XG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ05FVFdPUktfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgTm8gcmVzcG9uc2UgcmVjZWl2ZWQgZm9yICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBsb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogJ1JFUVVFU1RfU0VUVVBfRVJST1InLFxuICAgICAgbWVzc2FnZTogYEVycm9yIHNldHRpbmcgdXAgcmVxdWVzdCBmb3IgJHtvcGVyYXRpb25OYW1lfTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgfSxcbiAgfTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlYXJjaFRyZWxsbyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGJvYXJkSWQ6IHN0cmluZyxcbiAgcXVlcnk6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS90cmVsbG8vc2VhcmNoYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdDxQeXRob25BcGlSZXNwb25zZTxhbnk+PihlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgYm9hcmRfaWQ6IGJvYXJkSWQsXG4gICAgICBxdWVyeTogcXVlcnksXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLmRhdGEsICdzZWFyY2hUcmVsbG8nKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihlcnJvciBhcyBBeGlvc0Vycm9yLCAnc2VhcmNoVHJlbGxvJyk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGxpc3RUcmVsbG9DYXJkcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGJvYXJkSWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS90cmVsbG8vbGlzdC1jYXJkc2A7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3Q8UHl0aG9uQXBpUmVzcG9uc2U8YW55Pj4oZW5kcG9pbnQsIHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIGJvYXJkX2lkOiBib2FyZElkLFxuICAgIH0pO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShyZXNwb25zZS5kYXRhLCAnbGlzdFRyZWxsb0NhcmRzJyk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ2xpc3RUcmVsbG9DYXJkcycpO1xuICB9XG59XG4iXX0=
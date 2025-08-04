"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createGoogleDriveFolderFromTrelloBoard = createGoogleDriveFolderFromTrelloBoard;
exports.uploadTrelloAttachmentsToGoogleDrive = uploadTrelloAttachmentsToGoogleDrive;
exports.createTrelloBoardFromGoogleDriveFolder = createTrelloBoardFromGoogleDriveFolder;
exports.createTrelloCardForNewFileInGoogleDrive = createTrelloCardForNewFileInGoogleDrive;
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
async function createGoogleDriveFolderFromTrelloBoard(userId, boardId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/project/create-gdrive-folder-from-trello-board`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            board_id: boardId,
        });
        return handlePythonApiResponse(response, 'createGoogleDriveFolderFromTrelloBoard');
    }
    catch (error) {
        return handleAxiosError(error, 'createGoogleDriveFolderFromTrelloBoard');
    }
}
async function uploadTrelloAttachmentsToGoogleDrive(userId, cardId, folderId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/project/upload-trello-attachments-to-gdrive`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            card_id: cardId,
            folder_id: folderId,
        });
        return handlePythonApiResponse(response, 'uploadTrelloAttachmentsToGoogleDrive');
    }
    catch (error) {
        return handleAxiosError(error, 'uploadTrelloAttachmentsToGoogleDrive');
    }
}
async function createTrelloBoardFromGoogleDriveFolder(userId, folderId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/project/create-trello-board-from-gdrive-folder`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            folder_id: folderId,
        });
        return handlePythonApiResponse(response, 'createTrelloBoardFromGoogleDriveFolder');
    }
    catch (error) {
        return handleAxiosError(error, 'createTrelloBoardFromGoogleDriveFolder');
    }
}
async function createTrelloCardForNewFileInGoogleDrive(userId, folderId, trelloListId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/project/create-trello-card-for-new-gdrive-file`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            folder_id: folderId,
            trello_list_id: trelloListId,
        });
        return handlePythonApiResponse(response, 'createTrelloCardForNewFileInGoogleDrive');
    }
    catch (error) {
        return handleAxiosError(error, 'createTrelloCardForNewFileInGoogleDrive');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicHJvamVjdE1hbmFnZXJTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJwcm9qZWN0TWFuYWdlclNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQXFFQSx3RkE4QkM7QUFFRCxvRkFnQ0M7QUFFRCx3RkE4QkM7QUFFRCwwRkFnQ0M7QUF2TUQsa0RBQTBDO0FBTTFDLGdHQUErRztBQUMvRyxnRkFBNkU7QUFFN0Usa0VBQWtFO0FBQ2xFLFNBQVMsdUJBQXVCLENBQzlCLFFBQWEsRUFBRSwwREFBMEQ7QUFDekUsYUFBcUI7SUFFckIsSUFBSSxRQUFRLENBQUMsSUFBSSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsRUFBRSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDNUQsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFDaEQsQ0FBQztJQUNELGVBQU0sQ0FBQyxJQUFJLENBQUMsSUFBSSxhQUFhLG9CQUFvQixFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxDQUFDLENBQUM7SUFDekUsT0FBTztRQUNMLEVBQUUsRUFBRSxLQUFLO1FBQ1QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxrQkFBa0I7WUFDdEQsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsR0FBRztZQUN2RSxPQUFPLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsT0FBTztTQUN2QztLQUNGLENBQUM7QUFDSixDQUFDO0FBRUQsd0NBQXdDO0FBQ3hDLFNBQVMsZ0JBQWdCLENBQ3ZCLEtBQWlCLEVBQ2pCLGFBQXFCO0lBRXJCLElBQUksS0FBSyxDQUFDLFFBQVEsRUFBRSxDQUFDO1FB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QyxJQUFJLENBQUMsUUFBUSxFQUFFO1lBQzFDLE9BQU8sRUFBRSxNQUFNO1lBQ2YsU0FBUyxFQUFFLFFBQVE7WUFDbkIsY0FBYyxFQUFFLFlBQVk7U0FDN0IsQ0FBQyxDQUFDO1FBQ0gsT0FBTyx1QkFBdUIsQ0FDNUIsUUFBUSxFQUNSLHlDQUF5QyxDQUMxQyxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLGdCQUFnQixDQUNyQixLQUFtQixFQUNuQix5Q0FBeUMsQ0FDMUMsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGF4aW9zLCB7IEF4aW9zRXJyb3IgfSBmcm9tICdheGlvcyc7XG5pbXBvcnQge1xuICBTa2lsbFJlc3BvbnNlLFxuICBHb29nbGVEcml2ZUZpbGUsXG4gIFRyZWxsb0JvYXJkLFxufSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvdHlwZXMnOyAvLyBBZGp1c3QgcGF0aFxuaW1wb3J0IHsgUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9sb2dnZXInO1xuXG4vLyBIZWxwZXIgdG8gaGFuZGxlIFB5dGhvbiBBUEkgcmVzcG9uc2VzLCBjYW4gYmUgY2VudHJhbGl6ZWQgbGF0ZXJcbmZ1bmN0aW9uIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlPFQ+KFxuICByZXNwb25zZTogYW55LCAvLyBBZGp1c3QgdHlwZSBhcyBwZXIgYWN0dWFsIFB5dGhvbiBBUEkgcmVzcG9uc2Ugc3RydWN0dXJlXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxUPiB7XG4gIGlmIChyZXNwb25zZS5kYXRhICYmIHJlc3BvbnNlLmRhdGEub2sgJiYgcmVzcG9uc2UuZGF0YS5kYXRhKSB7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmRhdGEuZGF0YSB9O1xuICB9XG4gIGxvZ2dlci53YXJuKGBbJHtvcGVyYXRpb25OYW1lfV0gRmFpbGVkIEFQSSBjYWxsLmAsIHJlc3BvbnNlLmRhdGE/LmVycm9yKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5jb2RlIHx8ICdQWVRIT05fQVBJX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgZGV0YWlsczogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmRldGFpbHMsXG4gICAgfSxcbiAgfTtcbn1cblxuLy8gSGVscGVyIHRvIGhhbmRsZSBuZXR3b3JrL2F4aW9zIGVycm9yc1xuZnVuY3Rpb24gaGFuZGxlQXhpb3NFcnJvcihcbiAgZXJyb3I6IEF4aW9zRXJyb3IsXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxudWxsPiB7XG4gIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICBlcnJvci5yZXNwb25zZS5kYXRhXG4gICAgKTtcbiAgICBjb25zdCBlcnJEYXRhID0gZXJyb3IucmVzcG9uc2UuZGF0YSBhcyBhbnk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGBIVFRQXyR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICAgIG1lc3NhZ2U6IGVyckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGVsc2UgaWYgKGVycm9yLnJlcXVlc3QpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiBObyByZXNwb25zZSByZWNlaXZlZGAsXG4gICAgICBlcnJvci5yZXF1ZXN0XG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ05FVFdPUktfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgTm8gcmVzcG9uc2UgcmVjZWl2ZWQgZm9yICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBsb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogJ1JFUVVFU1RfU0VUVVBfRVJST1InLFxuICAgICAgbWVzc2FnZTogYEVycm9yIHNldHRpbmcgdXAgcmVxdWVzdCBmb3IgJHtvcGVyYXRpb25OYW1lfTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgfSxcbiAgfTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZUdvb2dsZURyaXZlRm9sZGVyRnJvbVRyZWxsb0JvYXJkKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYm9hcmRJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8R29vZ2xlRHJpdmVGaWxlPj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL3Byb2plY3QvY3JlYXRlLWdkcml2ZS1mb2xkZXItZnJvbS10cmVsbG8tYm9hcmRgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBib2FyZF9pZDogYm9hcmRJZCxcbiAgICB9KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UoXG4gICAgICByZXNwb25zZSxcbiAgICAgICdjcmVhdGVHb29nbGVEcml2ZUZvbGRlckZyb21UcmVsbG9Cb2FyZCdcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKFxuICAgICAgZXJyb3IgYXMgQXhpb3NFcnJvcixcbiAgICAgICdjcmVhdGVHb29nbGVEcml2ZUZvbGRlckZyb21UcmVsbG9Cb2FyZCdcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB1cGxvYWRUcmVsbG9BdHRhY2htZW50c1RvR29vZ2xlRHJpdmUoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYXJkSWQ6IHN0cmluZyxcbiAgZm9sZGVySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9wcm9qZWN0L3VwbG9hZC10cmVsbG8tYXR0YWNobWVudHMtdG8tZ2RyaXZlYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgY2FyZF9pZDogY2FyZElkLFxuICAgICAgZm9sZGVyX2lkOiBmb2xkZXJJZCxcbiAgICB9KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UoXG4gICAgICByZXNwb25zZSxcbiAgICAgICd1cGxvYWRUcmVsbG9BdHRhY2htZW50c1RvR29vZ2xlRHJpdmUnXG4gICAgKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihcbiAgICAgIGVycm9yIGFzIEF4aW9zRXJyb3IsXG4gICAgICAndXBsb2FkVHJlbGxvQXR0YWNobWVudHNUb0dvb2dsZURyaXZlJ1xuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZVRyZWxsb0JvYXJkRnJvbUdvb2dsZURyaXZlRm9sZGVyKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZm9sZGVySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPFRyZWxsb0JvYXJkPj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL3Byb2plY3QvY3JlYXRlLXRyZWxsby1ib2FyZC1mcm9tLWdkcml2ZS1mb2xkZXJgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBmb2xkZXJfaWQ6IGZvbGRlcklkLFxuICAgIH0pO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShcbiAgICAgIHJlc3BvbnNlLFxuICAgICAgJ2NyZWF0ZVRyZWxsb0JvYXJkRnJvbUdvb2dsZURyaXZlRm9sZGVyJ1xuICAgICk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoXG4gICAgICBlcnJvciBhcyBBeGlvc0Vycm9yLFxuICAgICAgJ2NyZWF0ZVRyZWxsb0JvYXJkRnJvbUdvb2dsZURyaXZlRm9sZGVyJ1xuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZVRyZWxsb0NhcmRGb3JOZXdGaWxlSW5Hb29nbGVEcml2ZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGZvbGRlcklkOiBzdHJpbmcsXG4gIHRyZWxsb0xpc3RJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL3Byb2plY3QvY3JlYXRlLXRyZWxsby1jYXJkLWZvci1uZXctZ2RyaXZlLWZpbGVgO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50LCB7XG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBmb2xkZXJfaWQ6IGZvbGRlcklkLFxuICAgICAgdHJlbGxvX2xpc3RfaWQ6IHRyZWxsb0xpc3RJZCxcbiAgICB9KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UoXG4gICAgICByZXNwb25zZSxcbiAgICAgICdjcmVhdGVUcmVsbG9DYXJkRm9yTmV3RmlsZUluR29vZ2xlRHJpdmUnXG4gICAgKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihcbiAgICAgIGVycm9yIGFzIEF4aW9zRXJyb3IsXG4gICAgICAnY3JlYXRlVHJlbGxvQ2FyZEZvck5ld0ZpbGVJbkdvb2dsZURyaXZlJ1xuICAgICk7XG4gIH1cbn1cbiJdfQ==
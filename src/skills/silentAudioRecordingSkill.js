"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.startSilentAudioRecording = startSilentAudioRecording;
exports.stopSilentAudioRecording = stopSilentAudioRecording;
const logger_1 = require("../../atomic-docker/project/functions/_utils/logger");
const constants_1 = require("../../atomic-docker/project/functions/atom-agent/_libs/constants");
const axios_1 = __importDefault(require("axios"));
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
function handlePythonApiResponse(response, operationName) {
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
async function startSilentAudioRecording(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/personal/start-silent-audio-recording?user_id=${userId}`;
    try {
        const response = await axios_1.default.post(endpoint);
        return handlePythonApiResponse(response, 'startSilentAudioRecording');
    }
    catch (error) {
        return handleAxiosError(error, 'startSilentAudioRecording');
    }
}
async function stopSilentAudioRecording(userId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/personal/stop-silent-audio-recording?user_id=${userId}`;
    try {
        const response = await axios_1.default.post(endpoint);
        return handlePythonApiResponse(response, 'stopSilentAudioRecording');
    }
    catch (error) {
        return handleAxiosError(error, 'stopSilentAudioRecording');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2lsZW50QXVkaW9SZWNvcmRpbmdTa2lsbC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNpbGVudEF1ZGlvUmVjb3JkaW5nU2tpbGwudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFnRUEsOERBb0JDO0FBRUQsNERBb0JDO0FBekdELGdGQUE2RTtBQUM3RSxnR0FBK0c7QUFDL0csa0RBQTBDO0FBRTFDLHdDQUF3QztBQUN4QyxTQUFTLGdCQUFnQixDQUN2QixLQUFpQixFQUNqQixhQUFxQjtJQUVyQixJQUFJLEtBQUssQ0FBQyxRQUFRLEVBQUUsQ0FBQztRQUNuQixlQUFNLENBQUMsS0FBSyxDQUNWLElBQUksYUFBYSxZQUFZLEtBQUssQ0FBQyxRQUFRLENBQUMsTUFBTSxFQUFFLEVBQ3BELEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUNwQixDQUFDO1FBQ0YsTUFBTSxPQUFPLEdBQUcsS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFXLENBQUM7UUFDM0MsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRLEtBQUssQ0FBQyxRQUFRLENBQUMsTUFBTSxFQUFFO2dCQUNyQyxPQUFPLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLElBQUksYUFBYSxhQUFhLEdBQUc7YUFDbEU7U0FDRixDQUFDO0lBQ0osQ0FBQztTQUFNLElBQUksS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ3pCLGVBQU0sQ0FBQyxLQUFLLENBQ1YsSUFBSSxhQUFhLCtCQUErQixFQUNoRCxLQUFLLENBQUMsT0FBTyxDQUNkLENBQUM7UUFDRixPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGVBQWU7Z0JBQ3JCLE9BQU8sRUFBRSw0QkFBNEIsYUFBYSxHQUFHO2FBQ3REO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFDRCxlQUFNLENBQUMsS0FBSyxDQUFDLElBQUksYUFBYSxZQUFZLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FBQyxDQUFDO0lBQzNELE9BQU87UUFDTCxFQUFFLEVBQUUsS0FBSztRQUNULEtBQUssRUFBRTtZQUNMLElBQUksRUFBRSxxQkFBcUI7WUFDM0IsT0FBTyxFQUFFLGdDQUFnQyxhQUFhLEtBQUssS0FBSyxDQUFDLE9BQU8sRUFBRTtTQUMzRTtLQUNGLENBQUM7QUFDSixDQUFDO0FBRUQsU0FBUyx1QkFBdUIsQ0FDOUIsUUFBYSxFQUNiLGFBQXFCO0lBRXJCLElBQUksUUFBUSxDQUFDLElBQUksSUFBSSxRQUFRLENBQUMsSUFBSSxDQUFDLEVBQUUsSUFBSSxRQUFRLENBQUMsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO1FBQzVELE9BQU8sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxRQUFRLENBQUMsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQ2hELENBQUM7SUFDRCxlQUFNLENBQUMsSUFBSSxDQUFDLElBQUksYUFBYSxvQkFBb0IsRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssQ0FBQyxDQUFDO0lBQ3pFLE9BQU87UUFDTCxFQUFFLEVBQUUsS0FBSztRQUNULEtBQUssRUFBRTtZQUNMLElBQUksRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxJQUFJLElBQUksa0JBQWtCO1lBQ3RELE9BQU8sRUFBRSxRQUFRLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPLElBQUksYUFBYSxhQUFhLEdBQUc7WUFDdkUsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU87U0FDdkM7S0FDRixDQUFDO0FBQ0osQ0FBQztBQUVNLEtBQUssVUFBVSx5QkFBeUIsQ0FDN0MsTUFBYztJQUVkLElBQUksQ0FBQyx1Q0FBMkIsRUFBRSxDQUFDO1FBQ2pDLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsY0FBYztnQkFDcEIsT0FBTyxFQUFFLDJDQUEyQzthQUNyRDtTQUNGLENBQUM7SUFDSixDQUFDO0lBQ0QsTUFBTSxRQUFRLEdBQUcsR0FBRyx1Q0FBMkIsc0RBQXNELE1BQU0sRUFBRSxDQUFDO0lBRTlHLElBQUksQ0FBQztRQUNILE1BQU0sUUFBUSxHQUFHLE1BQU0sZUFBSyxDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztRQUM1QyxPQUFPLHVCQUF1QixDQUFDLFFBQVEsRUFBRSwyQkFBMkIsQ0FBQyxDQUFDO0lBQ3hFLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxnQkFBZ0IsQ0FBQyxLQUFtQixFQUFFLDJCQUEyQixDQUFDLENBQUM7SUFDNUUsQ0FBQztBQUNILENBQUM7QUFFTSxLQUFLLFVBQVUsd0JBQXdCLENBQzVDLE1BQWM7SUFFZCxJQUFJLENBQUMsdUNBQTJCLEVBQUUsQ0FBQztRQUNqQyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGNBQWM7Z0JBQ3BCLE9BQU8sRUFBRSwyQ0FBMkM7YUFDckQ7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUNELE1BQU0sUUFBUSxHQUFHLEdBQUcsdUNBQTJCLHFEQUFxRCxNQUFNLEVBQUUsQ0FBQztJQUU3RyxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLGVBQUssQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLENBQUM7UUFDNUMsT0FBTyx1QkFBdUIsQ0FBQyxRQUFRLEVBQUUsMEJBQTBCLENBQUMsQ0FBQztJQUN2RSxDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sZ0JBQWdCLENBQUMsS0FBbUIsRUFBRSwwQkFBMEIsQ0FBQyxDQUFDO0lBQzNFLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgU2tpbGxSZXNwb25zZSB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC90eXBlcyc7XG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9sb2dnZXInO1xuaW1wb3J0IHsgUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcblxuLy8gSGVscGVyIHRvIGhhbmRsZSBuZXR3b3JrL2F4aW9zIGVycm9yc1xuZnVuY3Rpb24gaGFuZGxlQXhpb3NFcnJvcihcbiAgZXJyb3I6IEF4aW9zRXJyb3IsXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxudWxsPiB7XG4gIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICBlcnJvci5yZXNwb25zZS5kYXRhXG4gICAgKTtcbiAgICBjb25zdCBlcnJEYXRhID0gZXJyb3IucmVzcG9uc2UuZGF0YSBhcyBhbnk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGBIVFRQXyR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICAgIG1lc3NhZ2U6IGVyckRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGVsc2UgaWYgKGVycm9yLnJlcXVlc3QpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiBObyByZXNwb25zZSByZWNlaXZlZGAsXG4gICAgICBlcnJvci5yZXF1ZXN0XG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ05FVFdPUktfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgTm8gcmVzcG9uc2UgcmVjZWl2ZWQgZm9yICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBsb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogJ1JFUVVFU1RfU0VUVVBfRVJST1InLFxuICAgICAgbWVzc2FnZTogYEVycm9yIHNldHRpbmcgdXAgcmVxdWVzdCBmb3IgJHtvcGVyYXRpb25OYW1lfTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgfSxcbiAgfTtcbn1cblxuZnVuY3Rpb24gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2U8VD4oXG4gIHJlc3BvbnNlOiBhbnksXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZ1xuKTogU2tpbGxSZXNwb25zZTxUPiB7XG4gIGlmIChyZXNwb25zZS5kYXRhICYmIHJlc3BvbnNlLmRhdGEub2sgJiYgcmVzcG9uc2UuZGF0YS5kYXRhKSB7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmRhdGEuZGF0YSB9O1xuICB9XG4gIGxvZ2dlci53YXJuKGBbJHtvcGVyYXRpb25OYW1lfV0gRmFpbGVkIEFQSSBjYWxsLmAsIHJlc3BvbnNlLmRhdGE/LmVycm9yKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5jb2RlIHx8ICdQWVRIT05fQVBJX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5tZXNzYWdlIHx8IGBGYWlsZWQgdG8gJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgZGV0YWlsczogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmRldGFpbHMsXG4gICAgfSxcbiAgfTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHN0YXJ0U2lsZW50QXVkaW9SZWNvcmRpbmcoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8YW55Pj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1B5dGhvbiBBUEkgc2VydmljZSBVUkwgaXMgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL3BlcnNvbmFsL3N0YXJ0LXNpbGVudC1hdWRpby1yZWNvcmRpbmc/dXNlcl9pZD0ke3VzZXJJZH1gO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UsICdzdGFydFNpbGVudEF1ZGlvUmVjb3JkaW5nJyk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ3N0YXJ0U2lsZW50QXVkaW9SZWNvcmRpbmcnKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc3RvcFNpbGVudEF1ZGlvUmVjb3JkaW5nKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9wZXJzb25hbC9zdG9wLXNpbGVudC1hdWRpby1yZWNvcmRpbmc/dXNlcl9pZD0ke3VzZXJJZH1gO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UsICdzdG9wU2lsZW50QXVkaW9SZWNvcmRpbmcnKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihlcnJvciBhcyBBeGlvc0Vycm9yLCAnc3RvcFNpbGVudEF1ZGlvUmVjb3JkaW5nJyk7XG4gIH1cbn1cbiJdfQ==
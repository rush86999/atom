"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.scheduleLinkedInPost = scheduleLinkedInPost;
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
async function scheduleLinkedInPost(userId, content, sendAt // ISO 8601 string
) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/social/linkedin/schedule-post`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            content,
            send_at: sendAt,
        });
        return handlePythonApiResponse(response, 'scheduleLinkedInPost');
    }
    catch (error) {
        return handleAxiosError(error, 'scheduleLinkedInPost');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlua2VkaW5Ta2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaW5rZWRpblNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWlFQSxvREEwQkM7QUEzRkQsa0RBQTBDO0FBRTFDLGdHQUErRztBQUMvRyxnRkFBNkU7QUFFN0Usa0VBQWtFO0FBQ2xFLFNBQVMsdUJBQXVCLENBQzlCLFFBQWEsRUFBRSwwREFBMEQ7QUFDekUsYUFBcUI7SUFFckIsSUFBSSxRQUFRLENBQUMsSUFBSSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsRUFBRSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDNUQsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFDaEQsQ0FBQztJQUNELGVBQU0sQ0FBQyxJQUFJLENBQUMsSUFBSSxhQUFhLG9CQUFvQixFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxDQUFDLENBQUM7SUFDekUsT0FBTztRQUNMLEVBQUUsRUFBRSxLQUFLO1FBQ1QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxrQkFBa0I7WUFDdEQsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsR0FBRztZQUN2RSxPQUFPLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsT0FBTztTQUN2QztLQUNGLENBQUM7QUFDSixDQUFDO0FBRUQsd0NBQXdDO0FBQ3hDLFNBQVMsZ0JBQWdCLENBQ3ZCLEtBQWlCLEVBQ2pCLGFBQXFCO0lBRXJCLElBQUksS0FBSyxDQUFDLFFBQVEsRUFBRSxDQUFDO1FBQ25CLGVBQU0sQ0FBQyxLQUFLLENBQ1YsSUFBSSxhQUFhLFlBQVksS0FBSyxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQUUsRUFDcEQsS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQ3BCLENBQUM7UUFDRixNQUFNLE9BQU8sR0FBRyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQVcsQ0FBQztRQUMzQyxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVEsS0FBSyxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQUU7Z0JBQ3JDLE9BQU8sRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsR0FBRzthQUNsRTtTQUNGLENBQUM7SUFDSixDQUFDO1NBQU0sSUFBSSxLQUFLLENBQUMsT0FBTyxFQUFFLENBQUM7UUFDekIsZUFBTSxDQUFDLEtBQUssQ0FDVixJQUFJLGFBQWEsK0JBQStCLEVBQ2hELEtBQUssQ0FBQyxPQUFPLENBQ2QsQ0FBQztRQUNGLE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsZUFBZTtnQkFDckIsT0FBTyxFQUFFLDRCQUE0QixhQUFhLEdBQUc7YUFDdEQ7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUNELGVBQU0sQ0FBQyxLQUFLLENBQUMsSUFBSSxhQUFhLFlBQVksS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDLENBQUM7SUFDM0QsT0FBTztRQUNMLEVBQUUsRUFBRSxLQUFLO1FBQ1QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLHFCQUFxQjtZQUMzQixPQUFPLEVBQUUsZ0NBQWdDLGFBQWEsS0FBSyxLQUFLLENBQUMsT0FBTyxFQUFFO1NBQzNFO0tBQ0YsQ0FBQztBQUNKLENBQUM7QUFFTSxLQUFLLFVBQVUsb0JBQW9CLENBQ3hDLE1BQWMsRUFDZCxPQUFlLEVBQ2YsTUFBYyxDQUFDLGtCQUFrQjs7SUFFakMsSUFBSSxDQUFDLHVDQUEyQixFQUFFLENBQUM7UUFDakMsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxjQUFjO2dCQUNwQixPQUFPLEVBQUUsMkNBQTJDO2FBQ3JEO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFDRCxNQUFNLFFBQVEsR0FBRyxHQUFHLHVDQUEyQixvQ0FBb0MsQ0FBQztJQUVwRixJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLGVBQUssQ0FBQyxJQUFJLENBQUMsUUFBUSxFQUFFO1lBQzFDLE9BQU8sRUFBRSxNQUFNO1lBQ2YsT0FBTztZQUNQLE9BQU8sRUFBRSxNQUFNO1NBQ2hCLENBQUMsQ0FBQztRQUNILE9BQU8sdUJBQXVCLENBQUMsUUFBUSxFQUFFLHNCQUFzQixDQUFDLENBQUM7SUFDbkUsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLGdCQUFnQixDQUFDLEtBQW1CLEVBQUUsc0JBQXNCLENBQUMsQ0FBQztJQUN2RSxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBheGlvcywgeyBBeGlvc0Vycm9yIH0gZnJvbSAnYXhpb3MnO1xuaW1wb3J0IHsgU2tpbGxSZXNwb25zZSB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC90eXBlcyc7IC8vIEFkanVzdCBwYXRoXG5pbXBvcnQgeyBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2xvZ2dlcic7XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgUHl0aG9uIEFQSSByZXNwb25zZXMsIGNhbiBiZSBjZW50cmFsaXplZCBsYXRlclxuZnVuY3Rpb24gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2U8VD4oXG4gIHJlc3BvbnNlOiBhbnksIC8vIEFkanVzdCB0eXBlIGFzIHBlciBhY3R1YWwgUHl0aG9uIEFQSSByZXNwb25zZSBzdHJ1Y3R1cmVcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPFQ+IHtcbiAgaWYgKHJlc3BvbnNlLmRhdGEgJiYgcmVzcG9uc2UuZGF0YS5vayAmJiByZXNwb25zZS5kYXRhLmRhdGEpIHtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzcG9uc2UuZGF0YS5kYXRhIH07XG4gIH1cbiAgbG9nZ2VyLndhcm4oYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgQVBJIGNhbGwuYCwgcmVzcG9uc2UuZGF0YT8uZXJyb3IpO1xuICByZXR1cm4ge1xuICAgIG9rOiBmYWxzZSxcbiAgICBlcnJvcjoge1xuICAgICAgY29kZTogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmNvZGUgfHwgJ1BZVEhPTl9BUElfRVJST1InLFxuICAgICAgbWVzc2FnZTogcmVzcG9uc2UuZGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICBkZXRhaWxzOiByZXNwb25zZS5kYXRhPy5lcnJvcj8uZGV0YWlscyxcbiAgICB9LFxuICB9O1xufVxuXG4vLyBIZWxwZXIgdG8gaGFuZGxlIG5ldHdvcmsvYXhpb3MgZXJyb3JzXG5mdW5jdGlvbiBoYW5kbGVBeGlvc0Vycm9yKFxuICBlcnJvcjogQXhpb3NFcnJvcixcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nXG4pOiBTa2lsbFJlc3BvbnNlPG51bGw+IHtcbiAgaWYgKGVycm9yLnJlc3BvbnNlKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgIGVycm9yLnJlc3BvbnNlLmRhdGFcbiAgICApO1xuICAgIGNvbnN0IGVyckRhdGEgPSBlcnJvci5yZXNwb25zZS5kYXRhIGFzIGFueTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogYEhUVFBfJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgICAgbWVzc2FnZTogZXJyRGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoZXJyb3IucmVxdWVzdCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6IE5vIHJlc3BvbnNlIHJlY2VpdmVkYCxcbiAgICAgIGVycm9yLnJlcXVlc3RcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnTkVUV09SS19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBObyByZXNwb25zZSByZWNlaXZlZCBmb3IgJHtvcGVyYXRpb25OYW1lfS5gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiAnUkVRVUVTVF9TRVRVUF9FUlJPUicsXG4gICAgICBtZXNzYWdlOiBgRXJyb3Igc2V0dGluZyB1cCByZXF1ZXN0IGZvciAke29wZXJhdGlvbk5hbWV9OiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICB9LFxuICB9O1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2NoZWR1bGVMaW5rZWRJblBvc3QoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjb250ZW50OiBzdHJpbmcsXG4gIHNlbmRBdDogc3RyaW5nIC8vIElTTyA4NjAxIHN0cmluZ1xuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPGFueT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdQeXRob24gQVBJIHNlcnZpY2UgVVJMIGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9zb2NpYWwvbGlua2VkaW4vc2NoZWR1bGUtcG9zdGA7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoZW5kcG9pbnQsIHtcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIGNvbnRlbnQsXG4gICAgICBzZW5kX2F0OiBzZW5kQXQsXG4gICAgfSk7XG4gICAgcmV0dXJuIGhhbmRsZVB5dGhvbkFwaVJlc3BvbnNlKHJlc3BvbnNlLCAnc2NoZWR1bGVMaW5rZWRJblBvc3QnKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihlcnJvciBhcyBBeGlvc0Vycm9yLCAnc2NoZWR1bGVMaW5rZWRJblBvc3QnKTtcbiAgfVxufVxuIl19
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarketingAutomationAgent = void 0;
exports.createDripCampaign = createDripCampaign;
exports.getCampaignStatus = getCampaignStatus;
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
async function createDripCampaign(userId, campaignName, targetAudience, emailSequence) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/marketing/create-drip-campaign`;
    try {
        const response = await axios_1.default.post(endpoint, {
            user_id: userId,
            campaign_name: campaignName,
            target_audience: targetAudience,
            email_sequence: emailSequence,
        });
        return handlePythonApiResponse(response, 'createDripCampaign');
    }
    catch (error) {
        return handleAxiosError(error, 'createDripCampaign');
    }
}
async function getCampaignStatus(userId, campaignId) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'Python API service URL is not configured.',
            },
        };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/marketing/campaign-status/${campaignId}?user_id=${userId}`;
    try {
        const response = await axios_1.default.get(endpoint);
        return handlePythonApiResponse(response, 'getCampaignStatus');
    }
    catch (error) {
        return handleAxiosError(error, 'getCampaignStatus');
    }
}
class MarketingAutomationAgent {
    llmService;
    constructor(llmService) {
        this.llmService = llmService;
    }
    async analyze(input) {
        // For now, returning a mock response.
        // In a real implementation, this would involve an LLM call to analyze the input.
        if (input.userInput.toLowerCase().includes('status')) {
            return Promise.resolve({
                problemType: 'marketing_automation',
                summary: 'The user wants to get the status of a marketing campaign.',
                tasks: [
                    {
                        id: 'get_campaign_status',
                        description: 'Get the status of a marketing campaign.',
                        parameters: {
                            campaignId: 'campaign_123', // Mock campaign ID
                        },
                    },
                ],
            });
        }
        return Promise.resolve({
            problemType: 'marketing_automation',
            summary: 'The user wants to automate a marketing task.',
            tasks: [
                {
                    id: 'create_drip_campaign',
                    description: 'Create a new email drip campaign.',
                    parameters: {
                        campaignName: 'New Customer Welcome',
                        targetAudience: 'new_signups',
                        emailSequence: ['welcome_email_1', 'follow_up_email_2'],
                    },
                },
            ],
        });
    }
}
exports.MarketingAutomationAgent = MarketingAutomationAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWFya2V0aW5nQXV0b21hdGlvblNraWxsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibWFya2V0aW5nQXV0b21hdGlvblNraWxsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQWtFQSxnREE0QkM7QUFFRCw4Q0FxQkM7QUFySEQsa0RBQTBDO0FBRTFDLGdHQUErRztBQUMvRyxnRkFBNkU7QUFHN0Usa0VBQWtFO0FBQ2xFLFNBQVMsdUJBQXVCLENBQzlCLFFBQWEsRUFBRSwwREFBMEQ7QUFDekUsYUFBcUI7SUFFckIsSUFBSSxRQUFRLENBQUMsSUFBSSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsRUFBRSxJQUFJLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDNUQsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFDaEQsQ0FBQztJQUNELGVBQU0sQ0FBQyxJQUFJLENBQUMsSUFBSSxhQUFhLG9CQUFvQixFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxDQUFDLENBQUM7SUFDekUsT0FBTztRQUNMLEVBQUUsRUFBRSxLQUFLO1FBQ1QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxrQkFBa0I7WUFDdEQsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxhQUFhLGFBQWEsR0FBRztZQUN2RSxPQUFPLEVBQUUsUUFBUSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsT0FBTztTQUN2QztLQUNGLENBQUM7QUFDSixDQUFDO0FBRUQsd0NBQXdDO0FBQ3hDLFNBQVMsZ0JBQWdCLENBQ3ZCLEtBQWlCLEVBQ2pCLGFBQXFCO0lBRXJCLElBQUksS0FBSyxDQUFDLFFBQVEsRUFBRSxDQUFDO1FBQ25CLGVBQU0sQ0FBQyxL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cm9tICdheGlvcyc7XG5pbXBvcnQgeyBTa2lsbFJlc3BvbnNlIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3R5cGVzJzsgLy8gQWRqdXN0IHBhdGhcbmltcG9ydCB7IFBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9fdXRpbHMvbG9nZ2VyJztcbmltcG9ydCB7IFN1YkFnZW50SW5wdXQsIEFnZW50TExNU2VydmljZSB9IGZyb20gJy4uL25sdV9hZ2VudHMvbmx1X3R5cGVzJztcblxuLy8gSGVscGVyIHRvIGhhbmRsZSBQeXRob24gQVBJIHJlc3BvbnNlcywgY2FuIGJlIGNlbnRyYWxpemVkIGxhdGVyXG5mdW5jdGlvbiBoYW5kbGVQeXRob25BcGlSZXNwb25zZTxUPihcbiAgcmVzcG9uc2U6IGFueSwgLy8gQWRqdXN0IHR5cGUgYXMgcGVyIGFjdHVhbCBQeXRob24gQVBJIHJlc3BvbnNlIHN0cnVjdHVyZVxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8VD4ge1xuICBpZiAocmVzcG9uc2UuZGF0YSAmJiByZXNwb25zZS5kYXRhLm9rICYmIHJlc3BvbnNlLmRhdGEuZGF0YSkge1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXNwb25zZS5kYXRhLmRhdGEgfTtcbiAgfVxuICBsb2dnZXIud2FybihgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCBBUEkgY2FsbC5gLCByZXNwb25zZS5kYXRhPy5lcnJvcik7XG4gIHJldHVybiB7XG4gICAgb2s6IGZhbHNlLFxuICAgIGVycm9yOiB7XG4gICAgICBjb2RlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8uY29kZSB8fCAnUFlUSE9OX0FQSV9FUlJPUicsXG4gICAgICBtZXNzYWdlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIGRldGFpbHM6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5kZXRhaWxzLFxuICAgIH0sXG4gIH07XG59XG5cbi8vIEhlbHBlciB0byBoYW5kbGUgbmV0d29yay9heGlvcyBlcnJvcnNcbmZ1bmN0aW9uIGhhbmRsZUF4aW9zRXJyb3IoXG4gIGVycm9yOiBBeGlvc0Vycm9yLFxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmdcbik6IFNraWxsUmVzcG9uc2U8bnVsbD4ge1xuICBpZiAoZXJyb3IucmVzcG9uc2UpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiAke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgZXJyb3IucmVzcG9uc2UuZGF0YVxuICAgICk7XG4gICAgY29uc3QgZXJyRGF0YSA9IGVycm9yLnJlc3BvbnNlLmRhdGEgYXMgYW55O1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiBgSFRUUF8ke2Vycm9yLnJlc3BvbnNlLnN0YXR1c31gLFxuICAgICAgICBtZXNzYWdlOiBlcnJEYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCBgRmFpbGVkIHRvICR7b3BlcmF0aW9uTmFtZX0uYCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBlbHNlIGlmIChlcnJvci5yZXF1ZXN0KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogTm8gcmVzcG9uc2UgcmVjZWl2ZWRgLFxuICAgICAgZXJyb3IucmVxdWVzdFxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdORVRXT1JLX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYE5vIHJlc3BvbnNlIHJlY2VpdmVkIGZvciAke29wZXJhdGlvbk5hbWV9LmAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgbG9nZ2VyLmVycm9yKGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgcmV0dXJuIHtcbiAgICBvazogZmFsc2UsXG4gICAgZXJyb3I6IHtcbiAgICAgIGNvZGU6ICdSRVFVRVNUX1NFVFVQX0VSUk9SJyxcbiAgICAgIG1lc3NhZ2U6IGBFcnJvciBzZXR0aW5nIHVwIHJlcXVlc3QgZm9yICR7b3BlcmF0aW9uTmFtZX06ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgIH0sXG4gIH07XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjcmVhdGVEcmlwQ2FtcGFpZ24oXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYW1wYWlnbk5hbWU6IHN0cmluZyxcbiAgdGFyZ2V0QXVkaWVuY2U6IHN0cmluZyxcbiAgZW1haWxTZXF1ZW5jZTogc3RyaW5nW11cbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxhbnk+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvbWFya2V0aW5nL2NyZWF0ZS1kcmlwLWNhbXBhaWduYDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwge1xuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgY2FtcGFpZ25fbmFtZTogY2FtcGFpZ25OYW1lLFxuICAgICAgdGFyZ2V0X2F1ZGllbmNlOiB0YXJnZXRBdWRpZW5jZSxcbiAgICAgIGVtYWlsX3NlcXVlbmNlOiBlbWFpbFNlcXVlbmNlLFxuICAgIH0pO1xuICAgIHJldHVybiBoYW5kbGVQeXRob25BcGlSZXNwb25zZShyZXNwb25zZSwgJ2NyZWF0ZURyaXBDYW1wYWlnbicpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yIGFzIEF4aW9zRXJyb3IsICdjcmVhdGVEcmlwQ2FtcGFpZ24nKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0Q2FtcGFpZ25TdGF0dXMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYW1wYWlnbklkOiBzdHJpbmdcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxhbnk+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUHl0aG9uIEFQSSBzZXJ2aWNlIFVSTCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGNvbnN0IGVuZHBvaW50ID0gYCR7UFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMfS9hcGkvbWFya2V0aW5nL2NhbXBhaWduLXN0YXR1cy8ke2NhbXBhaWduSWR9P3VzZXJfaWQ9JHt1c2VySWR9YDtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0KGVuZHBvaW50KTtcbiAgICByZXR1cm4gaGFuZGxlUHl0aG9uQXBpUmVzcG9uc2UocmVzcG9uc2UsICdnZXRDYW1wYWlnblN0YXR1cycpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yIGFzIEF4aW9zRXJyb3IsICdnZXRDYW1wYWlnblN0YXR1cycpO1xuICB9XG59XG5cbmV4cG9ydCBjbGFzcyBNYXJrZXRpbmdBdXRvbWF0aW9uQWdlbnQge1xuICBwcml2YXRlIGxsbVNlcnZpY2U6IEFnZW50TExNU2VydmljZTtcblxuICBjb25zdHJ1Y3RvcihsbG1TZXJ2aWNlOiBBZ2VudExMTVNlcnZpY2UpIHtcbiAgICB0aGlzLmxsbVNlcnZpY2UgPSBsbG1TZXJ2aWNlO1xuICB9XG5cbiAgcHVibGljIGFzeW5jIGFuYWx5emUoaW5wdXQ6IFN1YkFnZW50SW5wdXQpOiBQcm9taXNlPGFueT4ge1xuICAgIC8vIEZvciBub3csIHJldHVybmluZyBhIG1vY2sgcmVzcG9uc2UuXG4gICAgLy8gSW4gYSByZWFsIGltcGxlbWVudGF0aW9uLCB0aGlzIHdvdWxkIGludm9sdmUgYW4gTExNIGNhbGwgdG8gYW5hbHl6ZSB0aGUgaW5wdXQuXG5cbiAgICBpZiAoaW5wdXQudXNlcklucHV0LnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ3N0YXR1cycpKSB7XG4gICAgICByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKHtcbiAgICAgICAgcHJvYmxlbVR5cGU6ICdtYXJrZXRpbmdfYXV0b21hdGlvbicsXG4gICAgICAgIHN1bW1hcnk6ICdUaGUgdXNlciB3YW50cyB0byBnZXQgdGhlIHN0YXR1cyBvZiBhIG1hcmtldGluZyBjYW1wYWlnbi4nLFxuICAgICAgICB0YXNrczogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIGlkOiAnZ2V0X2NhbXBhaWduX3N0YXR1cycsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ0dldCB0aGUgc3RhdHVzIG9mIGEgbWFya2V0aW5nIGNhbXBhaWduLicsXG4gICAgICAgICAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICAgICAgICAgIGNhbXBhaWduSWQ6ICdjYW1wYWlnbl8xMjMnLCAvLyBNb2NrIGNhbXBhaWduIElEXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIF0sXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKHtcbiAgICAgIHByb2JsZW1UeXBlOiAnbWFya2V0aW5nX2F1dG9tYXRpb24nLFxuICAgICAgc3VtbWFyeTogJ1RoZSB1c2VyIHdhbnRzIHRvIGF1dG9tYXRlIGEgbWFya2V0aW5nIHRhc2suJyxcbiAgICAgIHRhc2tzOiBbXG4gICAgICAgIHtcbiAgICAgICAgICBpZDogJ2NyZWF0ZV9kcmlwX2NhbXBhaWduJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBhIG5ldyBlbWFpbCBkcmlwIGNhbXBhaWduLicsXG4gICAgICAgICAgcGFyYW1ldGVyczoge1xuICAgICAgICAgICAgY2FtcGFpZ25OYW1lOiAnTmV3IEN1c3RvbWVyIFdlbGNvbWUnLFxuICAgICAgICAgICAgdGFyZ2V0QXVkaWVuY2U6ICduZXdfc2lnbnVwcycsXG4gICAgICAgICAgICBlbWFpbFNlcXVlbmNlOiBbJ3dlbGNvbWVfZW1haWxfMScsICdmb2xsb3dfdXBfZW1haWxfMiddLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgIH0pO1xuICB9XG59XG4iXX0=
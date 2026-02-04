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
//# sourceMappingURL=marketingAutomationSkill.js.map
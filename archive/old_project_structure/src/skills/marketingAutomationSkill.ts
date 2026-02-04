import axios, { AxiosError } from 'axios';
import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types'; // Adjust path
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';
import { logger } from '../../atomic-docker/project/functions/_utils/logger';
import { SubAgentInput, AgentLLMService } from '../nlu_agents/nlu_types';

// Helper to handle Python API responses, can be centralized later
function handlePythonApiResponse<T>(
  response: any, // Adjust type as per actual Python API response structure
  operationName: string
): SkillResponse<T> {
  if (response.data && response.data.ok && response.data.data) {
    return { ok: true, data: response.data.data };
  }
  logger.warn(`[${operationName}] Failed API call.`, response.data?.error);
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
function handleAxiosError(
  error: AxiosError,
  operationName: string
): SkillResponse<null> {
  if (error.response) {
    logger.error(
      `[${operationName}] Error: ${error.response.status}`,
      error.response.data
    );
    const errData = error.response.data as any;
    return {
      ok: false,
      error: {
        code: `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}.`,
      },
    };
  } else if (error.request) {
    logger.error(
      `[${operationName}] Error: No response received`,
      error.request
    );
    return {
      ok: false,
      error: {
        code: 'NETWORK_ERROR',
        message: `No response received for ${operationName}.`,
      },
    };
  }
  logger.error(`[${operationName}] Error: ${error.message}`);
  return {
    ok: false,
    error: {
      code: 'REQUEST_SETUP_ERROR',
      message: `Error setting up request for ${operationName}: ${error.message}`,
    },
  };
}

export async function createDripCampaign(
  userId: string,
  campaignName: string,
  targetAudience: string,
  emailSequence: string[]
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/create-drip-campaign`;

  try {
    const response = await axios.post(endpoint, {
      user_id: userId,
      campaign_name: campaignName,
      target_audience: targetAudience,
      email_sequence: emailSequence,
    });
    return handlePythonApiResponse(response, 'createDripCampaign');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'createDripCampaign');
  }
}

export async function getCampaignStatus(
  userId: string,
  campaignId: string
): Promise<SkillResponse<any>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    return {
      ok: false,
      error: {
        code: 'CONFIG_ERROR',
        message: 'Python API service URL is not configured.',
      },
    };
  }
  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/marketing/campaign-status/${campaignId}?user_id=${userId}`;

  try {
    const response = await axios.get(endpoint);
    return handlePythonApiResponse(response, 'getCampaignStatus');
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'getCampaignStatus');
  }
}

export class MarketingAutomationAgent {
  private llmService: AgentLLMService;

  constructor(llmService: AgentLLMService) {
    this.llmService = llmService;
  }

  public async analyze(input: SubAgentInput): Promise<any> {
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

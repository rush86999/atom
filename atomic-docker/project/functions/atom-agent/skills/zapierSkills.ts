import { ZapTriggerResponse } from '../types';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import got from 'got';

export interface ZapData {
  [key: string]: any;
}

async function getZapierWebhookUrl(userId: string): Promise<string | null> {
    const query = `
        query GetUserSetting($userId: String!, $key: String!) {
            user_settings(where: {user_id: {_eq: $userId}, key: {_eq: $key}}) {
                value
            }
        }
    `;
    const variables = {
        userId,
        key: 'zapier_webhook_url',
    };
    const response = await executeGraphQLQuery<{ user_settings: { value: string }[] }>(query, variables, 'GetUserSetting', userId);
    if (response.user_settings && response.user_settings.length > 0) {
        return response.user_settings[0].value;
    }
    return null;
}

export async function triggerZap(userId: string, zapName: string, data: ZapData): Promise<ZapTriggerResponse> {
  console.log(`Triggering Zap: "${zapName}" for user ${userId} with data:`, data);

  if (!zapName) {
    return { success: false, message: 'Zap name is required.' };
  }

  const webhookUrl = await getZapierWebhookUrl(userId);

  if (!webhookUrl) {
    return { success: false, message: 'Zapier webhook URL not configured.' };
  }

  try {
    await got.post(webhookUrl, {
        json: {
            zapName,
            ...data
        }
    });
    const mockZapRunId = `zapRun_${Date.now()}`;
    return {
        success: true,
        zapName,
        runId: mockZapRunId,
        message: `Zap "${zapName}" triggered successfully.`
    };
  } catch (error) {
    console.error(`Error triggering Zapier webhook for user ${userId}:`, error);
    return { success: false, message: 'Failed to trigger Zapier webhook.' };
  }
}

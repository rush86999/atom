import { ZapTriggerResponse } from '../types'; // Assuming ZapTriggerResponse is suitable
import { getZapierWebhookUrl } from '../_libs/zapier-utils';
import got from 'got';

// ZapData interface can be removed if 'any' is used directly for data, or kept for clarity
export interface ZapData {
  [key: string]: any;
}

export async function triggerZap(userId: string, zapName: string, data: ZapData): Promise<ZapTriggerResponse> {
    if (!userId) {
        console.error("User ID is required to trigger a Zap.");
        return { success: false, zapName, message: "User ID not provided." };
    }
    if (!zapName) {
        console.error("Zap name is required.");
        return { success: false, zapName, message: "Zap name not provided." };
    }

    let webhookUrl: string | null = null;
    try {
        webhookUrl = await getZapierWebhookUrl(userId, zapName);
    } catch (error: any) {
        console.error(`Error fetching webhook URL for Zap "${zapName}" for user ${userId}:`, error.message);
        return { success: false, zapName, message: `Could not retrieve configuration for Zap: ${zapName}. Error: ${error.message}` };
    }

    if (!webhookUrl) {
        console.log(`No webhook URL configured for Zap "${zapName}" for user ${userId}.`);
        return { success: false, zapName, message: `No webhook URL configured for Zap: ${zapName}. Please configure it in settings.` };
    }

    try {
        console.log(`Triggering Zap "${zapName}" for user ${userId} to URL ${webhookUrl} with data:`, data);

        // Zapier webhooks typically expect a JSON payload
        // The response from Zapier can vary. Some return a JSON with status, others just a simple status.
        // We use throwHttpErrors: false to manually inspect the response status and body.
        const response = await got.post(webhookUrl, {
            json: data,
            responseType: 'json', // Expect JSON response from Zapier, though it might be simple
            throwHttpErrors: false, // Handle HTTP errors manually to get response body
        });

        // Check for successful HTTP status codes
        if (response.statusCode >= 200 && response.statusCode < 300) {
            const responseBody: any = response.body;
            // Zapier success responses often include a "status": "success" field.
            // Some might return an attempt ID or similar.
            const message = responseBody?.message || responseBody?.status || `Zap "${zapName}" triggered successfully.`;
            const runId = responseBody?.id || responseBody?.attempt || undefined;
            console.log(`Zapier webhook for "${zapName}" triggered. Status: ${response.statusCode}. Response message: ${message}`, "Run ID:", runId);
            return { success: true, zapName, message, runId };
        } else {
            const responseBody: any = response.body;
            const errorMessage = responseBody?.message || responseBody?.error || (responseBody?.errors && responseBody.errors[0]?.message) || `Zapier webhook returned status ${response.statusCode}.`;
            console.error(`Zapier webhook for "${zapName}" returned an error or non-success status: ${response.statusCode}`, responseBody);
            return { success: false, zapName, message: errorMessage };
        }

    } catch (error: any) {
        console.error(`Error triggering Zap "${zapName}" (URL: ${webhookUrl}) for user ${userId}:`, error.message);
        // This catch block would typically handle network errors or issues with got itself,
        // as HTTP errors are handled above due to throwHttpErrors: false.
        // However, if responseType: 'json' fails to parse a non-JSON error response, it could land here.
        let detail = error.message;
        if (error.response?.body) {
            detail = typeof error.response.body === 'string' ? error.response.body : JSON.stringify(error.response.body);
        }
        return { success: false, zapName, message: `Failed to trigger Zap. Network or parsing error: ${detail}` };
    }
}

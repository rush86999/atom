import got from 'got';
import {
  HASURA_GRAPHQL_URL,
  HASURA_ADMIN_SECRET,
} from './constants';
import { encryptToken, decryptToken } from './token-utils';

export interface ZapierWebhook {
    id: string;
    zap_name: string;
    // webhook_url is not typically returned in list views for security
}

export async function addZapierWebhook(userId: string, zapName: string, webhookUrl: string): Promise<{ id: string; zap_name: string } | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot add Zapier webhook.');
        throw new Error('Server configuration error for Zapier webhook storage.');
    }
    if (!userId || !zapName || !webhookUrl) {
        console.error('Missing required fields (userId, zapName, webhookUrl) for adding Zapier webhook.');
        throw new Error('Invalid data provided for adding Zapier webhook.');
    }

    const encryptedUrl = await encryptToken(webhookUrl);
    if (!encryptedUrl) {
        console.error(`Failed to encrypt Zapier webhook URL for user ${userId}, zapName ${zapName}.`);
        throw new Error('Webhook URL encryption failed.');
    }

    const mutation = `
        mutation AddZapierWebhook($userId: uuid!, $zapName: String!, $encryptedUrl: String!) {
          insert_user_atom_agent_zapier_webhooks_one(object: {
            user_id: $userId,
            zap_name: $zapName,
            webhook_url: $encryptedUrl
          }, on_conflict: {
            constraint: user_atom_agent_zapier_webhooks_user_id_zap_name_key,
            update_columns: [webhook_url, updated_at]
          }) {
            id
            zap_name
          }
        }
    `;

    const variables = {
        userId,
        zapName,
        encryptedUrl,
    };

    try {
        console.log(`Adding/Updating Zapier webhook for user ${userId}, zapName: ${zapName}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query: mutation, variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error adding/updating Zapier webhook to Hasura:', response.errors);
            throw new Error(`Failed to save Zapier webhook: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }
        console.log('Successfully added/updated Zapier webhook:', response.data.insert_user_atom_agent_zapier_webhooks_one);
        return response.data.insert_user_atom_agent_zapier_webhooks_one;
    } catch (error: any) {
        console.error(`Exception while adding/updating Zapier webhook for user ${userId}:`, error.message);
        if (error.response?.body) console.error("Detailed error from got (Zapier save):", error.response.body);
        throw new Error(`An exception occurred while saving Zapier webhook: ${error.message}`);
    }
}

export async function listZapierWebhooks(userId: string): Promise<ZapierWebhook[]> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot list Zapier webhooks.');
        throw new Error('Server configuration error for Zapier webhook listing.');
    }
    if (!userId) {
        throw new Error('User ID is required to list Zapier webhooks.');
    }

    const query = `
        query ListZapierWebhooks($userId: uuid!) {
          user_atom_agent_zapier_webhooks(where: {user_id: {_eq: $userId}}, order_by: {zap_name: asc}) {
            id
            zap_name
          }
        }
    `;
    const variables = { userId };

    try {
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query, variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error listing Zapier webhooks from Hasura:', response.errors);
            return []; // Or throw
        }
        return response.data.user_atom_agent_zapier_webhooks || [];
    } catch (error: any) {
        console.error(`Exception while listing Zapier webhooks for user ${userId}:`, error.message);
        return []; // Or throw
    }
}

export async function deleteZapierWebhook(userId: string, zapId: string): Promise<{ affected_rows: number }> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot delete Zapier webhook.');
        throw new Error('Server configuration error for Zapier webhook deletion.');
    }
    if (!userId || !zapId) {
        throw new Error('User ID and Zap ID are required for deletion.');
    }

    const mutation = `
        mutation DeleteZapierWebhook($userId: uuid!, $zapId: uuid!) {
          delete_user_atom_agent_zapier_webhooks(where: {id: {_eq: $zapId}, user_id: {_eq: $userId}}) {
            affected_rows
          }
        }
    `;
    const variables = { userId, zapId };

    try {
        console.log(`Deleting Zapier webhook for user ${userId}, zapId: ${zapId}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query: mutation, variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error deleting Zapier webhook from Hasura:', response.errors);
            throw new Error(`Failed to delete Zapier webhook: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }
        console.log('Successfully deleted Zapier webhook. Affected rows:', response.data.delete_user_atom_agent_zapier_webhooks.affected_rows);
        return response.data.delete_user_atom_agent_zapier_webhooks;
    } catch (error: any) {
        console.error(`Exception while deleting Zapier webhook for user ${userId}, zapId ${zapId}:`, error.message);
        throw new Error(`An exception occurred while deleting Zapier webhook: ${error.message}`);
    }
}

export async function getZapierWebhookUrl(userId: string, zapName: string): Promise<string | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot get Zapier webhook URL.');
        throw new Error('Server configuration error.');
    }
    if (!userId || !zapName) {
        throw new Error('User ID and Zap Name are required to get webhook URL.');
    }

    const query = `
        query GetZapierWebhook($userId: uuid!, $zapName: String!) {
          user_atom_agent_zapier_webhooks(where: {user_id: {_eq: $userId}, zap_name: {_eq: $zapName}}, limit: 1) {
            webhook_url
          }
        }
    `;
    const variables = { userId, zapName };

    try {
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query, variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error fetching Zapier webhook URL from Hasura:', response.errors);
            return null;
        }

        const webhookRecord = response.data.user_atom_agent_zapier_webhooks?.[0];
        if (!webhookRecord || !webhookRecord.webhook_url) {
            console.log(`No Zapier webhook URL found for user ${userId}, zapName ${zapName}`);
            return null;
        }

        const decryptedUrl = await decryptToken(webhookRecord.webhook_url);
        if (!decryptedUrl) {
            console.error(`Failed to decrypt Zapier webhook URL for user ${userId}, zapName ${zapName}.`);
            return null; // Decryption failure
        }
        return decryptedUrl;

    } catch (error: any) {
        console.error(`Exception while fetching Zapier webhook URL for user ${userId}, zapName ${zapName}:`, error.message);
        return null;
    }
}

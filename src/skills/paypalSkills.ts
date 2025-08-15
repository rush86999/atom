import { SkillResponse } from 'atomic-docker/project/functions/atom-agent/types';
import { decrypt } from 'atomic-docker/project/functions/_libs/crypto';
import { executeGraphQLQuery } from 'atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { handleError } from 'atomic-docker/project/functions/_utils/errorHandler';
import axios from 'axios';

const PAYPAL_API_BASE_URL = 'https://api-m.sandbox.paypal.com';

export async function getPaypalAccessToken(userId: string): Promise<string | null> {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                encrypted_access_token
            }
        }
    `;
    const variables = {
        userId,
        service: 'paypal',
    };
    const response = await executeGraphQLQuery<{
        user_tokens: { encrypted_access_token: string }[];
    }>(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return decrypt(response.user_tokens[0].encrypted_access_token);
    }
    return null;
}

export async function getPaypalBalance(userId: string): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getPaypalAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'PayPal access token not configured for this user.',
                },
            };
        }

        // This is a placeholder. The PayPal REST API does not have a direct endpoint for getting the account balance.
        // You would need to use the Transaction Search API to calculate the balance.
        return { ok: true, data: { balance: 'not implemented' } };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'PAYPAL_API_ERROR',
                message: "Sorry, I couldn't get the PayPal balance due to an error.",
                details: error,
            },
        };
    }
}

export async function listPaypalTransactions(userId: string): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getPaypalAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'PayPal access token not configured for this user.',
                },
            };
        }

        const response = await axios.get(`${PAYPAL_API_BASE_URL}/v1/reporting/transactions`, {
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
            params: {
                start_date: '2023-01-01T00:00:00-0700',
                end_date: '2025-12-31T23:59:59-0700',
                fields: 'all'
            }
        });

        return { ok: true, data: response.data };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'PAYPAL_API_ERROR',
                message: "Sorry, I couldn't list the PayPal transactions due to an error.",
                details: error,
            },
        };
    }
}

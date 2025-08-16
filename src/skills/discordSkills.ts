import { SkillResponse } from 'atomic-docker/project/functions/atom-agent/types';
import { decrypt } from 'atomic-docker/project/functions/_libs/crypto';
import { executeGraphQLQuery } from 'atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { handleError } from 'atomic-docker/project/functions/_utils/errorHandler';
import axios from 'axios';

const DISCORD_API_BASE_URL = 'https://discord.com/api';

export async function getDiscordAccessToken(userId: string): Promise<string | null> {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                encrypted_access_token
            }
        }
    `;
    const variables = {
        userId,
        service: 'discord',
    };
    const response = await executeGraphQLQuery<{
        user_tokens: { encrypted_access_token: string }[];
    }>(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return decrypt(response.user_tokens[0].encrypted_access_token);
    }
    return null;
}

export async function listDiscordGuilds(userId: string): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getDiscordAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'Discord access token not configured for this user.',
                },
            };
        }

        const response = await axios.get(`${DISCORD_API_BASE_URL}/users/@me/guilds`, {
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        });

        return { ok: true, data: response.data };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'DISCORD_API_ERROR',
                message: "Sorry, I couldn't list the Discord servers due to an error.",
                details: error,
            },
        };
    }
}

export async function listDiscordChannels(userId: string, guildId: string): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getDiscordAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'Discord access token not configured for this user.',
                },
            };
        }

        const response = await axios.get(`${DISCORD_API_BASE_URL}/guilds/${guildId}/channels`, {
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        });

        return { ok: true, data: response.data };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'DISCORD_API_ERROR',
                message: "Sorry, I couldn't list the channels in the Discord server due to an error.",
                details: error,
            },
        };
    }
}

export async function sendDiscordMessage(userId: string, channelId: string, message: string): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getDiscordAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'Discord access token not configured for this user.',
                },
            };
        }

        const response = await axios.post(`${DISCORD_API_BASE_URL}/channels/${channelId}/messages`, {
            content: message,
        }, {
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        });

        return { ok: true, data: response.data };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'DISCORD_API_ERROR',
                message: "Sorry, I couldn't send the message to the Discord channel due to an error.",
                details: error,
            },
        };
    }
}

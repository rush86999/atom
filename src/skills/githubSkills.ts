import { SkillResponse } from 'atomic-docker/project/functions/atom-agent/types';
import { decrypt } from 'atomic-docker/project/functions/_libs/crypto';
import { executeGraphQLQuery } from 'atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { handleError } from 'atomic-docker/project/functions/_utils/errorHandler';
import axios from 'axios';

const GITHUB_API_BASE_URL = 'https://api.github.com';

async function getGitHubAccessToken(userId: string): Promise<string | null> {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                encrypted_access_token
            }
        }
    `;
    const variables = {
        userId,
        service: 'github',
    };
    const response = await executeGraphQLQuery<{
        user_tokens: { encrypted_access_token: string }[];
    }>(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return decrypt(response.user_tokens[0].encrypted_access_token);
    }
    return null;
}

export async function createRepoWebhook(
    userId: string,
    owner: string,
    repo: string,
    webhookUrl: string
): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getGitHubAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'GitHub access token not configured for this user.',
                },
            };
        }

        const response = await axios.post(
            `${GITHUB_API_BASE_URL}/repos/${owner}/${repo}/hooks`,
            {
                name: 'web',
                active: true,
                events: ['push'],
                config: {
                    url: webhookUrl,
                    content_type: 'json',
                },
            },
            {
                headers: {
                    Authorization: `token ${accessToken}`,
                },
            }
        );

        return { ok: true, data: response.data };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'GITHUB_API_ERROR',
                message: "Sorry, I couldn't create the GitHub webhook due to an error.",
                details: error,
            },
        };
    }
}

export async function createGithubIssue(
    userId: string,
    owner: string,
    repo: string,
    title: string,
    body: string
): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getGitHubAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'GitHub access token not configured for this user.',
                },
            };
        }

        const response = await axios.post(
            `${GITHUB_API_BASE_URL}/repos/${owner}/${repo}/issues`,
            {
                title,
                body,
            },
            {
                headers: {
                    Authorization: `token ${accessToken}`,
                },
            }
        );

        return { ok: true, data: response.data };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'GITHUB_API_ERROR',
                message: "Sorry, I couldn't create the GitHub issue due to an error.",
                details: error,
            },
        };
    }
}

export async function listGithubRepos(userId: string): Promise<SkillResponse<any>> {
    try {
        const accessToken = await getGitHubAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'GitHub access token not configured for this user.',
                },
            };
        }

        const response = await axios.get(`${GITHUB_API_BASE_URL}/user/repos`, {
            headers: {
                Authorization: `token ${accessToken}`,
            },
        });

        return { ok: true, data: response.data };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'GITHUB_API_ERROR',
                message: "Sorry, I couldn't list the GitHub repositories due to an error.",
                details: error,
            },
        };
    }
}

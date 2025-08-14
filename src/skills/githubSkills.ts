import { SkillResponse } from 'atomic-docker/project/functions/atom-agent/types';
import { decrypt } from 'atomic-docker/project/functions/_libs/crypto';
import { executeGraphQLQuery } from 'atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { handleError } from 'atomic-docker/project/functions/_utils/errorHandler';
import axios from 'axios';

const GITHUB_API_BASE_URL = 'https://api.github.com';

async function getGitHubAccessToken(userId: string): Promise<string | null> {
    const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
        serviceName: 'github_access_token',
    };
    const response = await executeGraphQLQuery<{
        user_credentials: { encrypted_secret: string }[];
    }>(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
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

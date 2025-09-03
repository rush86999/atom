"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createRepoWebhook = createRepoWebhook;
exports.createGithubIssue = createGithubIssue;
exports.listGithubRepos = listGithubRepos;
exports.createGithubRepo = createGithubRepo;
const crypto_1 = require("atomic-docker/project/functions/_libs/crypto");
const graphqlClient_1 = require("atomic-docker/project/functions/atom-agent/_libs/graphqlClient");
const axios_1 = __importDefault(require("axios"));
const GITHUB_API_BASE_URL = 'https://api.github.com';
async function getGitHubAccessToken(userId) {
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
    const response = await (0, graphqlClient_1.executeGraphQLQuery)(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return (0, crypto_1.decrypt)(response.user_tokens[0].encrypted_access_token);
    }
    return null;
}
async function createRepoWebhook(userId, owner, repo, webhookUrl) {
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
        const response = await axios_1.default.post(`${GITHUB_API_BASE_URL}/repos/${owner}/${repo}/hooks`, {
            name: 'web',
            active: true,
            events: ['push'],
            config: {
                url: webhookUrl,
                content_type: 'json',
            },
        }, {
            headers: {
                Authorization: `token ${accessToken}`,
            },
        });
        return { ok: true, data: response.data };
    }
    catch (error) {
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
async function createGithubIssue(userId, owner, repo, title, body) {
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
        const response = await axios_1.default.post(`${GITHUB_API_BASE_URL}/repos/${owner}/${repo}/issues`, {
            title,
            body,
        }, {
            headers: {
                Authorization: `token ${accessToken}`,
            },
        });
        return { ok: true, data: response.data };
    }
    catch (error) {
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
async function listGithubRepos(userId) {
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
        const response = await axios_1.default.get(`${GITHUB_API_BASE_URL}/user/repos`, {
            headers: {
                Authorization: `token ${accessToken}`,
            },
        });
        return { ok: true, data: response.data };
    }
    catch (error) {
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
async function createGithubRepo(userId, params) {
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
        // Sanitize repo name
        const safeName = params.name
            .toLowerCase()
            .replace(/[^a-z0-9-]/g, '-')
            .replace(/--+/g, '-')
            .replace(/^-|-$/g, '')
            .substring(0, 100);
        const timestamp = Date.now();
        const repoName = `${safeName}-${timestamp}`;
        // Create repository
        const repoResponse = await axios_1.default.post(`${GITHUB_API_BASE_URL}/user/repos`, {
            name: repoName,
            description: params.description || 'ATOM AI generated web application',
            private: params.private || false,
            auto_init: params.auto_init !== false,
            gitignore_template: 'node',
            license_template: 'mit'
        }, {
            headers: {
                Authorization: `token ${accessToken}`,
                'Accept': 'application/vnd.github.v3+json',
            },
        });
        // Get user info to construct full repo URL
        const userResponse = await axios_1.default.get(`${GITHUB_API_BASE_URL}/user`, {
            headers: {
                Authorization: `token ${accessToken}`,
            },
        });
        const repoData = {
            ...repoResponse.data,
            full_url: `https://github.com/${userResponse.data.login}/${repoName}`,
            clone_url: `https://github.com/${userResponse.data.login}/${repoName}.git`
        };
        return { ok: true, data: repoData };
    }
    catch (error) {
        return {
            ok: false,
            error: {
                code: 'GITHUB_API_ERROR',
                message: "Sorry, I couldn't create the GitHub repository due to an error.",
                details: error,
            },
        };
    }
}
//# sourceMappingURL=githubSkills.js.map
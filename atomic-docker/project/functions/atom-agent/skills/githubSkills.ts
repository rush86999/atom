import { Octokit } from '@octokit/rest';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';

async function getGithubApiKey(userId: string): Promise<string | null> {
  const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
  const variables = {
    userId,
    serviceName: 'github_api_key',
  };
  const response = await executeGraphQLQuery<{
    user_credentials: { encrypted_secret: string }[];
  }>(query, variables, 'GetUserCredential', userId);
  if (response.user_credentials && response.user_credentials.length > 0) {
    return decrypt(response.user_credentials[0].encrypted_secret);
  }
  return null;
}

export async function getRepoCommitActivity(
  userId: string,
  owner: string,
  repo: string
): Promise<any> {
  const apiKey = await getGithubApiKey(userId);
  if (!apiKey) {
    throw new Error('GitHub API key not configured for this user.');
  }
  const octokit = new Octokit({ auth: apiKey });

  try {
    const response = await octokit.repos.getCommitActivityStats({
      owner,
      repo,
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching commit activity:', error);
    return null;
  }
}

export async function createGithubRepo(
  userId: string,
  owner: string,
  repo: string
): Promise<any> {
  const apiKey = await getGithubApiKey(userId);
  if (!apiKey) {
    throw new Error('GitHub API key not configured for this user.');
  }
  const octokit = new Octokit({ auth: apiKey });

  try {
    const response = await octokit.repos.createForAuthenticatedUser({
      name: repo,
    });
    return response;
  } catch (error) {
    console.error('Error creating repository:', error);
    return null;
  }
}

export async function createGithubIssue(
  userId: string,
  owner: string,
  repo: string,
  title: string,
  body: string
): Promise<any> {
  const apiKey = await getGithubApiKey(userId);
  if (!apiKey) {
    throw new Error('GitHub API key not configured for this user.');
  }
  const octokit = new Octokit({ auth: apiKey });

  try {
    const response = await octokit.issues.create({
      owner,
      repo,
      title,
      body,
    });
    return response;
  } catch (error) {
    console.error('Error creating issue:', error);
    return null;
  }
}

export async function getRepoPullRequestActivity(
  userId: string,
  owner: string,
  repo: string
): Promise<any> {
  const apiKey = await getGithubApiKey(userId);
  if (!apiKey) {
    throw new Error('GitHub API key not configured for this user.');
  }
  const octokit = new Octokit({ auth: apiKey });

  try {
    const response = await octokit.pulls.list({
      owner,
      repo,
      state: 'all',
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching pull request activity:', error);
    return null;
  }
}

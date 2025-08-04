import { Octokit } from '@octokit/rest';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
async function getGithubApiKey(userId) {
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
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}
export async function getRepoCommitActivity(userId, owner, repo) {
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
    }
    catch (error) {
        console.error('Error fetching commit activity:', error);
        return null;
    }
}
export async function getRepoPullRequestActivity(userId, owner, repo) {
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
    }
    catch (error) {
        console.error('Error fetching pull request activity:', error);
        return null;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2l0aHViU2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2l0aHViU2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFBRSxPQUFPLEVBQUUsTUFBTSxlQUFlLENBQUM7QUFDeEMsT0FBTyxFQUFFLE9BQU8sRUFBRSxNQUFNLGlCQUFpQixDQUFDO0FBQzFDLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxNQUFNLHdCQUF3QixDQUFDO0FBRTdELEtBQUssVUFBVSxlQUFlLENBQUMsTUFBYztJQUMzQyxNQUFNLEtBQUssR0FBRzs7Ozs7O0tBTVgsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHO1FBQ2hCLE1BQU07UUFDTixXQUFXLEVBQUUsZ0JBQWdCO0tBQzlCLENBQUM7SUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLG1CQUFtQixDQUV2QyxLQUFLLEVBQUUsU0FBUyxFQUFFLG1CQUFtQixFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQ2xELElBQUksUUFBUSxDQUFDLGdCQUFnQixJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7UUFDdEUsT0FBTyxPQUFPLENBQUMsUUFBUSxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxDQUFDLGdCQUFnQixDQUFDLENBQUM7SUFDaEUsQ0FBQztJQUNELE9BQU8sSUFBSSxDQUFDO0FBQ2QsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUscUJBQXFCLENBQ3pDLE1BQWMsRUFDZCxLQUFhLEVBQ2IsSUFBWTtJQUVaLE1BQU0sTUFBTSxHQUFHLE1BQU0sZUFBZSxDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBQzdDLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNaLE1BQU0sSUFBSSxLQUFLLENBQUMsOENBQThDLENBQUMsQ0FBQztJQUNsRSxDQUFDO0lBQ0QsTUFBTSxPQUFPLEdBQUcsSUFBSSxPQUFPLENBQUMsRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQztJQUU5QyxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLE9BQU8sQ0FBQyxLQUFLLENBQUMsc0JBQXNCLENBQUM7WUFDMUQsS0FBSztZQUNMLElBQUk7U0FDTCxDQUFDLENBQUM7UUFDSCxPQUFPLFFBQVEsQ0FBQyxJQUFJLENBQUM7SUFDdkIsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsS0FBSyxDQUFDLGlDQUFpQyxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQ3hELE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztBQUNILENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLDBCQUEwQixDQUM5QyxNQUFjLEVBQ2QsS0FBYSxFQUNiLElBQVk7SUFFWixNQUFNLE1BQU0sR0FBRyxNQUFNLGVBQWUsQ0FBQyxNQUFNLENBQUMsQ0FBQztJQUM3QyxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDWixNQUFNLElBQUksS0FBSyxDQUFDLDhDQUE4QyxDQUFDLENBQUM7SUFDbEUsQ0FBQztJQUNELE1BQU0sT0FBTyxHQUFHLElBQUksT0FBTyxDQUFDLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRSxDQUFDLENBQUM7SUFFOUMsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxPQUFPLENBQUMsS0FBSyxDQUFDLElBQUksQ0FBQztZQUN4QyxLQUFLO1lBQ0wsSUFBSTtZQUNKLEtBQUssRUFBRSxLQUFLO1NBQ2IsQ0FBQyxDQUFDO1FBQ0gsT0FBTyxRQUFRLENBQUMsSUFBSSxDQUFDO0lBQ3ZCLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyx1Q0FBdUMsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUM5RCxPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgT2N0b2tpdCB9IGZyb20gJ0BvY3Rva2l0L3Jlc3QnO1xuaW1wb3J0IHsgZGVjcnlwdCB9IGZyb20gJy4uL19saWJzL2NyeXB0byc7XG5pbXBvcnQgeyBleGVjdXRlR3JhcGhRTFF1ZXJ5IH0gZnJvbSAnLi4vX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5cbmFzeW5jIGZ1bmN0aW9uIGdldEdpdGh1YkFwaUtleSh1c2VySWQ6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgR2V0VXNlckNyZWRlbnRpYWwoJHVzZXJJZDogU3RyaW5nISwgJHNlcnZpY2VOYW1lOiBTdHJpbmchKSB7XG4gICAgICAgICAgICB1c2VyX2NyZWRlbnRpYWxzKHdoZXJlOiB7dXNlcl9pZDoge19lcTogJHVzZXJJZH0sIHNlcnZpY2VfbmFtZToge19lcTogJHNlcnZpY2VOYW1lfX0pIHtcbiAgICAgICAgICAgICAgICBlbmNyeXB0ZWRfc2VjcmV0XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgdXNlcklkLFxuICAgIHNlcnZpY2VOYW1lOiAnZ2l0aHViX2FwaV9rZXknLFxuICB9O1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8e1xuICAgIHVzZXJfY3JlZGVudGlhbHM6IHsgZW5jcnlwdGVkX3NlY3JldDogc3RyaW5nIH1bXTtcbiAgfT4ocXVlcnksIHZhcmlhYmxlcywgJ0dldFVzZXJDcmVkZW50aWFsJywgdXNlcklkKTtcbiAgaWYgKHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMgJiYgcmVzcG9uc2UudXNlcl9jcmVkZW50aWFscy5sZW5ndGggPiAwKSB7XG4gICAgcmV0dXJuIGRlY3J5cHQocmVzcG9uc2UudXNlcl9jcmVkZW50aWFsc1swXS5lbmNyeXB0ZWRfc2VjcmV0KTtcbiAgfVxuICByZXR1cm4gbnVsbDtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFJlcG9Db21taXRBY3Rpdml0eShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG93bmVyOiBzdHJpbmcsXG4gIHJlcG86IHN0cmluZ1xuKTogUHJvbWlzZTxhbnk+IHtcbiAgY29uc3QgYXBpS2V5ID0gYXdhaXQgZ2V0R2l0aHViQXBpS2V5KHVzZXJJZCk7XG4gIGlmICghYXBpS2V5KSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKCdHaXRIdWIgQVBJIGtleSBub3QgY29uZmlndXJlZCBmb3IgdGhpcyB1c2VyLicpO1xuICB9XG4gIGNvbnN0IG9jdG9raXQgPSBuZXcgT2N0b2tpdCh7IGF1dGg6IGFwaUtleSB9KTtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgb2N0b2tpdC5yZXBvcy5nZXRDb21taXRBY3Rpdml0eVN0YXRzKHtcbiAgICAgIG93bmVyLFxuICAgICAgcmVwbyxcbiAgICB9KTtcbiAgICByZXR1cm4gcmVzcG9uc2UuZGF0YTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBmZXRjaGluZyBjb21taXQgYWN0aXZpdHk6JywgZXJyb3IpO1xuICAgIHJldHVybiBudWxsO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRSZXBvUHVsbFJlcXVlc3RBY3Rpdml0eShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG93bmVyOiBzdHJpbmcsXG4gIHJlcG86IHN0cmluZ1xuKTogUHJvbWlzZTxhbnk+IHtcbiAgY29uc3QgYXBpS2V5ID0gYXdhaXQgZ2V0R2l0aHViQXBpS2V5KHVzZXJJZCk7XG4gIGlmICghYXBpS2V5KSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKCdHaXRIdWIgQVBJIGtleSBub3QgY29uZmlndXJlZCBmb3IgdGhpcyB1c2VyLicpO1xuICB9XG4gIGNvbnN0IG9jdG9raXQgPSBuZXcgT2N0b2tpdCh7IGF1dGg6IGFwaUtleSB9KTtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgb2N0b2tpdC5wdWxscy5saXN0KHtcbiAgICAgIG93bmVyLFxuICAgICAgcmVwbyxcbiAgICAgIHN0YXRlOiAnYWxsJyxcbiAgICB9KTtcbiAgICByZXR1cm4gcmVzcG9uc2UuZGF0YTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBmZXRjaGluZyBwdWxsIHJlcXVlc3QgYWN0aXZpdHk6JywgZXJyb3IpO1xuICAgIHJldHVybiBudWxsO1xuICB9XG59XG4iXX0=
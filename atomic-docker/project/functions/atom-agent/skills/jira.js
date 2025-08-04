import { decrypt } from '../../_libs/crypto';
import { executeGraphQLQuery } from '../../_libs/graphqlClient';
import { handleError } from '../../_utils/errorHandler';
import { JiraApi } from 'jira-client';
async function getJiraCredentials(userId) {
    const query = `
        query GetUserCredentials($userId: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_in: ["jira_username", "jira_api_key", "jira_server_url"]}}) {
                service_name
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredentials', userId);
    if (response.user_credentials && response.user_credentials.length === 3) {
        const credentials = {};
        for (const cred of response.user_credentials) {
            credentials[cred.service_name] = decrypt(cred.encrypted_secret);
        }
        return {
            username: credentials.jira_username,
            apiKey: credentials.jira_api_key,
            serverUrl: credentials.jira_server_url,
        };
    }
    return null;
}
export async function handleCreateJiraIssue(userId, entities) {
    try {
        const credentials = await getJiraCredentials(userId);
        if (!credentials) {
            return 'Jira credentials not configured for this user.';
        }
        const jira = new JiraApi({
            protocol: 'https',
            host: credentials.serverUrl,
            username: credentials.username,
            password: credentials.apiKey,
            apiVersion: '2',
            strictSSL: true,
        });
        const { summary, project_key, issue_type } = entities;
        if (!summary || typeof summary !== 'string') {
            return 'Summary is required to create a Jira issue.';
        }
        if (!project_key || typeof project_key !== 'string') {
            return 'Project key is required to create a Jira issue.';
        }
        if (!issue_type || typeof issue_type !== 'string') {
            return 'Issue type is required to create a Jira issue.';
        }
        const issue = await jira.addNewIssue({
            fields: {
                project: {
                    key: project_key,
                },
                summary: summary,
                issuetype: {
                    name: issue_type,
                },
            },
        });
        return `Jira issue created: ${issue.key}`;
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't create the Jira issue due to an error.");
    }
}
export async function handleQueryJiraIssues(userId, entities) {
    try {
        const credentials = await getJiraCredentials(userId);
        if (!credentials) {
            return 'Jira credentials not configured for this user.';
        }
        const jira = new JiraApi({
            protocol: 'https',
            host: credentials.serverUrl,
            username: credentials.username,
            password: credentials.apiKey,
            apiVersion: '2',
            strictSSL: true,
        });
        const { project_key } = entities;
        if (!project_key || typeof project_key !== 'string') {
            return 'Project key is required to query Jira issues.';
        }
        const issues = await jira.searchJira(`project = ${project_key}`);
        if (!issues.issues.length) {
            return 'No issues found in the specified Jira project.';
        }
        let issueList = 'Here are the issues in the specified Jira project:\n';
        for (const issue of issues.issues) {
            issueList += `- ${issue.key}: ${issue.fields.summary}\n`;
        }
        return issueList;
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't query the Jira issues due to an error.");
    }
}
export async function handleUpdateJiraIssue(userId, entities) {
    try {
        const credentials = await getJiraCredentials(userId);
        if (!credentials) {
            return 'Jira credentials not configured for this user.';
        }
        const jira = new JiraApi({
            protocol: 'https',
            host: credentials.serverUrl,
            username: credentials.username,
            password: credentials.apiKey,
            apiVersion: '2',
            strictSSL: true,
        });
        const { issue_key, summary } = entities;
        if (!issue_key || typeof issue_key !== 'string') {
            return 'Issue key is required to update a Jira issue.';
        }
        if (!summary || typeof summary !== 'string') {
            return 'Summary is required to update a Jira issue.';
        }
        await jira.updateIssue(issue_key, {
            fields: {
                summary: summary,
            },
        });
        return `Jira issue updated: ${issue_key}`;
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't update the Jira issue due to an error.");
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiamlyYS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImppcmEudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQ0EsT0FBTyxFQUFFLE9BQU8sRUFBRSxNQUFNLG9CQUFvQixDQUFDO0FBQzdDLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxNQUFNLDJCQUEyQixDQUFDO0FBQ2hFLE9BQU8sRUFBRSxXQUFXLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQztBQUN4RCxPQUFPLEVBQUUsT0FBTyxFQUFFLE1BQU0sYUFBYSxDQUFDO0FBRXRDLEtBQUssVUFBVSxrQkFBa0IsQ0FDL0IsTUFBYztJQUVkLE1BQU0sS0FBSyxHQUFHOzs7Ozs7O0tBT1gsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHO1FBQ2hCLE1BQU07S0FDUCxDQUFDO0lBQ0YsTUFBTSxRQUFRLEdBQUcsTUFBTSxtQkFBbUIsQ0FFdkMsS0FBSyxFQUFFLFNBQVMsRUFBRSxvQkFBb0IsRUFBRSxNQUFNLENBQUMsQ0FBQztJQUNuRCxJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsSUFBSSxRQUFRLENBQUMsZ0JBQWdCLENBQUMsTUFBTSxLQUFLLENBQUMsRUFBRSxDQUFDO1FBQ3hFLE1BQU0sV0FBVyxHQUFRLEVBQUUsQ0FBQztRQUM1QixLQUFLLE1BQU0sSUFBSSxJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsRUFBRSxDQUFDO1lBQzdDLFdBQVcsQ0FBQyxJQUFJLENBQUMsWUFBWSxDQUFDLEdBQUcsT0FBTyxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1FBQ2xFLENBQUM7UUFDRCxPQUFPO1lBQ0wsUUFBUSxFQUFFLFdBQVcsQ0FBQyxhQUFhO1lBQ25DLE1BQU0sRUFBRSxXQUFXLENBQUMsWUFBWTtZQUNoQyxTQUFTLEVBQUUsV0FBVyxDQUFDLGVBQWU7U0FDdkMsQ0FBQztJQUNKLENBQUM7SUFDRCxPQUFPLElBQUksQ0FBQztBQUNkLENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLHFCQUFxQixDQUN6QyxNQUFjLEVBQ2QsUUFBYTtJQUViLElBQUksQ0FBQztRQUNILE1BQU0sV0FBVyxHQUFHLE1BQU0sa0JBQWtCLENBQUMsTUFBTSxDQUFDLENBQUM7UUFDckQsSUFBSSxDQUFDLFdBQVcsRUFBRSxDQUFDO1lBQ2pCLE9BQU8sZ0RBQWdELENBQUM7UUFDMUQsQ0FBQztRQUNELE1BQU0sSUFBSSxHQUFHLElBQUksT0FBTyxDQUFDO1lBQ3ZCLFFBQVEsRUFBRSxPQUFPO1lBQ2pCLElBQUksRUFBRSxXQUFXLENBQUMsU0FBUztZQUMzQixRQUFRLEVBQUUsV0FBVyxDQUFDLFFBQVE7WUFDOUIsUUFBUSxFQUFFLFdBQVcsQ0FBQyxNQUFNO1lBQzVCLFVBQVUsRUFBRSxHQUFHO1lBQ2YsU0FBUyxFQUFFLElBQUk7U0FDaEIsQ0FBQyxDQUFDO1FBRUgsTUFBTSxFQUFFLE9BQU8sRUFBRSxXQUFXLEVBQUUsVUFBVSxFQUFFLEdBQUcsUUFBUSxDQUFDO1FBRXRELElBQUksQ0FBQyxPQUFPLElBQUksT0FBTyxPQUFPLEtBQUssUUFBUSxFQUFFLENBQUM7WUFDNUMsT0FBTyw2Q0FBNkMsQ0FBQztRQUN2RCxDQUFDO1FBRUQsSUFBSSxDQUFDLFdBQVcsSUFBSSxPQUFPLFdBQVcsS0FBSyxRQUFRLEVBQUUsQ0FBQztZQUNwRCxPQUFPLGlEQUFpRCxDQUFDO1FBQzNELENBQUM7UUFFRCxJQUFJLENBQUMsVUFBVSxJQUFJLE9BQU8sVUFBVSxLQUFLLFFBQVEsRUFBRSxDQUFDO1lBQ2xELE9BQU8sZ0RBQWdELENBQUM7UUFDMUQsQ0FBQztRQUVELE1BQU0sS0FBSyxHQUFHLE1BQU0sSUFBSSxDQUFDLFdBQVcsQ0FBQztZQUNuQyxNQUFNLEVBQUU7Z0JBQ04sT0FBTyxFQUFFO29CQUNQLEdBQUcsRUFBRSxXQUFXO2lCQUNqQjtnQkFDRCxPQUFPLEVBQUUsT0FBTztnQkFDaEIsU0FBUyxFQUFFO29CQUNULElBQUksRUFBRSxVQUFVO2lCQUNqQjthQUNGO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsT0FBTyx1QkFBdUIsS0FBSyxDQUFDLEdBQUcsRUFBRSxDQUFDO0lBQzVDLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sV0FBVyxDQUNoQixLQUFLLEVBQ0wsMERBQTBELENBQzNELENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUscUJBQXFCLENBQ3pDLE1BQWMsRUFDZCxRQUFhO0lBRWIsSUFBSSxDQUFDO1FBQ0gsTUFBTSxXQUFXLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQyxNQUFNLENBQUMsQ0FBQztRQUNyRCxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7WUFDakIsT0FBTyxnREFBZ0QsQ0FBQztRQUMxRCxDQUFDO1FBQ0QsTUFBTSxJQUFJLEdBQUcsSUFBSSxPQUFPLENBQUM7WUFDdkIsUUFBUSxFQUFFLE9BQU87WUFDakIsSUFBSSxFQUFFLFdBQVcsQ0FBQyxTQUFTO1lBQzNCLFFBQVEsRUFBRSxXQUFXLENBQUMsUUFBUTtZQUM5QixRQUFRLEVBQUUsV0FBVyxDQUFDLE1BQU07WUFDNUIsVUFBVSxFQUFFLEdBQUc7WUFDZixTQUFTLEVBQUUsSUFBSTtTQUNoQixDQUFDLENBQUM7UUFFSCxNQUFNLEVBQUUsV0FBVyxFQUFFLEdBQUcsUUFBUSxDQUFDO1FBRWpDLElBQUksQ0FBQyxXQUFXLElBQUksT0FBTyxXQUFXLEtBQUssUUFBUSxFQUFFLENBQUM7WUFDcEQsT0FBTywrQ0FBK0MsQ0FBQztRQUN6RCxDQUFDO1FBRUQsTUFBTSxNQUFNLEdBQUcsTUFBTSxJQUFJLENBQUMsVUFBVSxDQUFDLGFBQWEsV0FBVyxFQUFFLENBQUMsQ0FBQztRQUVqRSxJQUFJLENBQUMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUMxQixPQUFPLGdEQUFnRCxDQUFDO1FBQzFELENBQUM7UUFFRCxJQUFJLFNBQVMsR0FBRyxzREFBc0QsQ0FBQztRQUN2RSxLQUFLLE1BQU0sS0FBSyxJQUFJLE1BQU0sQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUNsQyxTQUFTLElBQUksS0FBSyxLQUFLLENBQUMsR0FBRyxLQUFLLEtBQUssQ0FBQyxNQUFNLENBQUMsT0FBTyxJQUFJLENBQUM7UUFDM0QsQ0FBQztRQUVELE9BQU8sU0FBUyxDQUFDO0lBQ25CLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sV0FBVyxDQUNoQixLQUFLLEVBQ0wsMERBQTBELENBQzNELENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUscUJBQXFCLENBQ3pDLE1BQWMsRUFDZCxRQUFhO0lBRWIsSUFBSSxDQUFDO1FBQ0gsTUFBTSxXQUFXLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQyxNQUFNLENBQUMsQ0FBQztRQUNyRCxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7WUFDakIsT0FBTyxnREFBZ0QsQ0FBQztRQUMxRCxDQUFDO1FBQ0QsTUFBTSxJQUFJLEdBQUcsSUFBSSxPQUFPLENBQUM7WUFDdkIsUUFBUSxFQUFFLE9BQU87WUFDakIsSUFBSSxFQUFFLFdBQVcsQ0FBQyxTQUFTO1lBQzNCLFFBQVEsRUFBRSxXQUFXLENBQUMsUUFBUTtZQUM5QixRQUFRLEVBQUUsV0FBVyxDQUFDLE1BQU07WUFDNUIsVUFBVSxFQUFFLEdBQUc7WUFDZixTQUFTLEVBQUUsSUFBSTtTQUNoQixDQUFDLENBQUM7UUFFSCxNQUFNLEVBQUUsU0FBUyxFQUFFLE9BQU8sRUFBRSxHQUFHLFFBQVEsQ0FBQztRQUV4QyxJQUFJLENBQUMsU0FBUyxJQUFJLE9BQU8sU0FBUyxLQUFLLFFBQVEsRUFBRSxDQUFDO1lBQ2hELE9BQU8sK0NBQStDLENBQUM7UUFDekQsQ0FBQztRQUVELElBQUksQ0FBQyxPQUFPLElBQUksT0FBTyxPQUFPLEtBQUssUUFBUSxFQUFFLENBQUM7WUFDNUMsT0FBTyw2Q0FBNkMsQ0FBQztRQUN2RCxDQUFDO1FBRUQsTUFBTSxJQUFJLENBQUMsV0FBVyxDQUFDLFNBQVMsRUFBRTtZQUNoQyxNQUFNLEVBQUU7Z0JBQ04sT0FBTyxFQUFFLE9BQU87YUFDakI7U0FDRixDQUFDLENBQUM7UUFFSCxPQUFPLHVCQUF1QixTQUFTLEVBQUUsQ0FBQztJQUM1QyxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixPQUFPLFdBQVcsQ0FDaEIsS0FBSyxFQUNMLDBEQUEwRCxDQUMzRCxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBTa2lsbFJlc3BvbnNlIH0gZnJvbSAnLi4vLi4vdHlwZXMnO1xuaW1wb3J0IHsgZGVjcnlwdCB9IGZyb20gJy4uLy4uL19saWJzL2NyeXB0byc7XG5pbXBvcnQgeyBleGVjdXRlR3JhcGhRTFF1ZXJ5IH0gZnJvbSAnLi4vLi4vX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5pbXBvcnQgeyBoYW5kbGVFcnJvciB9IGZyb20gJy4uLy4uL191dGlscy9lcnJvckhhbmRsZXInO1xuaW1wb3J0IHsgSmlyYUFwaSB9IGZyb20gJ2ppcmEtY2xpZW50JztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0SmlyYUNyZWRlbnRpYWxzKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTx7IHVzZXJuYW1lOiBzdHJpbmc7IGFwaUtleTogc3RyaW5nOyBzZXJ2ZXJVcmw6IHN0cmluZyB9IHwgbnVsbD4ge1xuICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgR2V0VXNlckNyZWRlbnRpYWxzKCR1c2VySWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICAgIHVzZXJfY3JlZGVudGlhbHMod2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfSwgc2VydmljZV9uYW1lOiB7X2luOiBbXCJqaXJhX3VzZXJuYW1lXCIsIFwiamlyYV9hcGlfa2V5XCIsIFwiamlyYV9zZXJ2ZXJfdXJsXCJdfX0pIHtcbiAgICAgICAgICAgICAgICBzZXJ2aWNlX25hbWVcbiAgICAgICAgICAgICAgICBlbmNyeXB0ZWRfc2VjcmV0XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgdXNlcklkLFxuICB9O1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8e1xuICAgIHVzZXJfY3JlZGVudGlhbHM6IHsgc2VydmljZV9uYW1lOiBzdHJpbmc7IGVuY3J5cHRlZF9zZWNyZXQ6IHN0cmluZyB9W107XG4gIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsICdHZXRVc2VyQ3JlZGVudGlhbHMnLCB1c2VySWQpO1xuICBpZiAocmVzcG9uc2UudXNlcl9jcmVkZW50aWFscyAmJiByZXNwb25zZS51c2VyX2NyZWRlbnRpYWxzLmxlbmd0aCA9PT0gMykge1xuICAgIGNvbnN0IGNyZWRlbnRpYWxzOiBhbnkgPSB7fTtcbiAgICBmb3IgKGNvbnN0IGNyZWQgb2YgcmVzcG9uc2UudXNlcl9jcmVkZW50aWFscykge1xuICAgICAgY3JlZGVudGlhbHNbY3JlZC5zZXJ2aWNlX25hbWVdID0gZGVjcnlwdChjcmVkLmVuY3J5cHRlZF9zZWNyZXQpO1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgdXNlcm5hbWU6IGNyZWRlbnRpYWxzLmppcmFfdXNlcm5hbWUsXG4gICAgICBhcGlLZXk6IGNyZWRlbnRpYWxzLmppcmFfYXBpX2tleSxcbiAgICAgIHNlcnZlclVybDogY3JlZGVudGlhbHMuamlyYV9zZXJ2ZXJfdXJsLFxuICAgIH07XG4gIH1cbiAgcmV0dXJuIG51bGw7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVDcmVhdGVKaXJhSXNzdWUoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55XG4pOiBQcm9taXNlPHN0cmluZz4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNyZWRlbnRpYWxzID0gYXdhaXQgZ2V0SmlyYUNyZWRlbnRpYWxzKHVzZXJJZCk7XG4gICAgaWYgKCFjcmVkZW50aWFscykge1xuICAgICAgcmV0dXJuICdKaXJhIGNyZWRlbnRpYWxzIG5vdCBjb25maWd1cmVkIGZvciB0aGlzIHVzZXIuJztcbiAgICB9XG4gICAgY29uc3QgamlyYSA9IG5ldyBKaXJhQXBpKHtcbiAgICAgIHByb3RvY29sOiAnaHR0cHMnLFxuICAgICAgaG9zdDogY3JlZGVudGlhbHMuc2VydmVyVXJsLFxuICAgICAgdXNlcm5hbWU6IGNyZWRlbnRpYWxzLnVzZXJuYW1lLFxuICAgICAgcGFzc3dvcmQ6IGNyZWRlbnRpYWxzLmFwaUtleSxcbiAgICAgIGFwaVZlcnNpb246ICcyJyxcbiAgICAgIHN0cmljdFNTTDogdHJ1ZSxcbiAgICB9KTtcblxuICAgIGNvbnN0IHsgc3VtbWFyeSwgcHJvamVjdF9rZXksIGlzc3VlX3R5cGUgfSA9IGVudGl0aWVzO1xuXG4gICAgaWYgKCFzdW1tYXJ5IHx8IHR5cGVvZiBzdW1tYXJ5ICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdTdW1tYXJ5IGlzIHJlcXVpcmVkIHRvIGNyZWF0ZSBhIEppcmEgaXNzdWUuJztcbiAgICB9XG5cbiAgICBpZiAoIXByb2plY3Rfa2V5IHx8IHR5cGVvZiBwcm9qZWN0X2tleSAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnUHJvamVjdCBrZXkgaXMgcmVxdWlyZWQgdG8gY3JlYXRlIGEgSmlyYSBpc3N1ZS4nO1xuICAgIH1cblxuICAgIGlmICghaXNzdWVfdHlwZSB8fCB0eXBlb2YgaXNzdWVfdHlwZSAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnSXNzdWUgdHlwZSBpcyByZXF1aXJlZCB0byBjcmVhdGUgYSBKaXJhIGlzc3VlLic7XG4gICAgfVxuXG4gICAgY29uc3QgaXNzdWUgPSBhd2FpdCBqaXJhLmFkZE5ld0lzc3VlKHtcbiAgICAgIGZpZWxkczoge1xuICAgICAgICBwcm9qZWN0OiB7XG4gICAgICAgICAga2V5OiBwcm9qZWN0X2tleSxcbiAgICAgICAgfSxcbiAgICAgICAgc3VtbWFyeTogc3VtbWFyeSxcbiAgICAgICAgaXNzdWV0eXBlOiB7XG4gICAgICAgICAgbmFtZTogaXNzdWVfdHlwZSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICByZXR1cm4gYEppcmEgaXNzdWUgY3JlYXRlZDogJHtpc3N1ZS5rZXl9YDtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBjcmVhdGUgdGhlIEppcmEgaXNzdWUgZHVlIHRvIGFuIGVycm9yLlwiXG4gICAgKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlUXVlcnlKaXJhSXNzdWVzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjcmVkZW50aWFscyA9IGF3YWl0IGdldEppcmFDcmVkZW50aWFscyh1c2VySWQpO1xuICAgIGlmICghY3JlZGVudGlhbHMpIHtcbiAgICAgIHJldHVybiAnSmlyYSBjcmVkZW50aWFscyBub3QgY29uZmlndXJlZCBmb3IgdGhpcyB1c2VyLic7XG4gICAgfVxuICAgIGNvbnN0IGppcmEgPSBuZXcgSmlyYUFwaSh7XG4gICAgICBwcm90b2NvbDogJ2h0dHBzJyxcbiAgICAgIGhvc3Q6IGNyZWRlbnRpYWxzLnNlcnZlclVybCxcbiAgICAgIHVzZXJuYW1lOiBjcmVkZW50aWFscy51c2VybmFtZSxcbiAgICAgIHBhc3N3b3JkOiBjcmVkZW50aWFscy5hcGlLZXksXG4gICAgICBhcGlWZXJzaW9uOiAnMicsXG4gICAgICBzdHJpY3RTU0w6IHRydWUsXG4gICAgfSk7XG5cbiAgICBjb25zdCB7IHByb2plY3Rfa2V5IH0gPSBlbnRpdGllcztcblxuICAgIGlmICghcHJvamVjdF9rZXkgfHwgdHlwZW9mIHByb2plY3Rfa2V5ICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdQcm9qZWN0IGtleSBpcyByZXF1aXJlZCB0byBxdWVyeSBKaXJhIGlzc3Vlcy4nO1xuICAgIH1cblxuICAgIGNvbnN0IGlzc3VlcyA9IGF3YWl0IGppcmEuc2VhcmNoSmlyYShgcHJvamVjdCA9ICR7cHJvamVjdF9rZXl9YCk7XG5cbiAgICBpZiAoIWlzc3Vlcy5pc3N1ZXMubGVuZ3RoKSB7XG4gICAgICByZXR1cm4gJ05vIGlzc3VlcyBmb3VuZCBpbiB0aGUgc3BlY2lmaWVkIEppcmEgcHJvamVjdC4nO1xuICAgIH1cblxuICAgIGxldCBpc3N1ZUxpc3QgPSAnSGVyZSBhcmUgdGhlIGlzc3VlcyBpbiB0aGUgc3BlY2lmaWVkIEppcmEgcHJvamVjdDpcXG4nO1xuICAgIGZvciAoY29uc3QgaXNzdWUgb2YgaXNzdWVzLmlzc3Vlcykge1xuICAgICAgaXNzdWVMaXN0ICs9IGAtICR7aXNzdWUua2V5fTogJHtpc3N1ZS5maWVsZHMuc3VtbWFyeX1cXG5gO1xuICAgIH1cblxuICAgIHJldHVybiBpc3N1ZUxpc3Q7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICByZXR1cm4gaGFuZGxlRXJyb3IoXG4gICAgICBlcnJvcixcbiAgICAgIFwiU29ycnksIEkgY291bGRuJ3QgcXVlcnkgdGhlIEppcmEgaXNzdWVzIGR1ZSB0byBhbiBlcnJvci5cIlxuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVVwZGF0ZUppcmFJc3N1ZShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBhbnlcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY3JlZGVudGlhbHMgPSBhd2FpdCBnZXRKaXJhQ3JlZGVudGlhbHModXNlcklkKTtcbiAgICBpZiAoIWNyZWRlbnRpYWxzKSB7XG4gICAgICByZXR1cm4gJ0ppcmEgY3JlZGVudGlhbHMgbm90IGNvbmZpZ3VyZWQgZm9yIHRoaXMgdXNlci4nO1xuICAgIH1cbiAgICBjb25zdCBqaXJhID0gbmV3IEppcmFBcGkoe1xuICAgICAgcHJvdG9jb2w6ICdodHRwcycsXG4gICAgICBob3N0OiBjcmVkZW50aWFscy5zZXJ2ZXJVcmwsXG4gICAgICB1c2VybmFtZTogY3JlZGVudGlhbHMudXNlcm5hbWUsXG4gICAgICBwYXNzd29yZDogY3JlZGVudGlhbHMuYXBpS2V5LFxuICAgICAgYXBpVmVyc2lvbjogJzInLFxuICAgICAgc3RyaWN0U1NMOiB0cnVlLFxuICAgIH0pO1xuXG4gICAgY29uc3QgeyBpc3N1ZV9rZXksIHN1bW1hcnkgfSA9IGVudGl0aWVzO1xuXG4gICAgaWYgKCFpc3N1ZV9rZXkgfHwgdHlwZW9mIGlzc3VlX2tleSAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnSXNzdWUga2V5IGlzIHJlcXVpcmVkIHRvIHVwZGF0ZSBhIEppcmEgaXNzdWUuJztcbiAgICB9XG5cbiAgICBpZiAoIXN1bW1hcnkgfHwgdHlwZW9mIHN1bW1hcnkgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gJ1N1bW1hcnkgaXMgcmVxdWlyZWQgdG8gdXBkYXRlIGEgSmlyYSBpc3N1ZS4nO1xuICAgIH1cblxuICAgIGF3YWl0IGppcmEudXBkYXRlSXNzdWUoaXNzdWVfa2V5LCB7XG4gICAgICBmaWVsZHM6IHtcbiAgICAgICAgc3VtbWFyeTogc3VtbWFyeSxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICByZXR1cm4gYEppcmEgaXNzdWUgdXBkYXRlZDogJHtpc3N1ZV9rZXl9YDtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCB1cGRhdGUgdGhlIEppcmEgaXNzdWUgZHVlIHRvIGFuIGVycm9yLlwiXG4gICAgKTtcbiAgfVxufVxuIl19
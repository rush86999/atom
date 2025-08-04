import { decrypt } from '../../_libs/crypto';
import { executeGraphQLQuery } from '../../_libs/graphqlClient';
import { handleError } from '../../_utils/errorHandler';
import * as asana from 'asana';
async function getAsanaApiKey(userId) {
    const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
        serviceName: 'asana_api_key',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}
export async function handleCreateAsanaTask(userId, entities) {
    try {
        const apiKey = await getAsanaApiKey(userId);
        if (!apiKey) {
            return 'Asana API key not configured for this user.';
        }
        const client = asana.Client.create().useAccessToken(apiKey);
        const { task_name, project_id } = entities;
        if (!task_name || typeof task_name !== 'string') {
            return 'Task name is required to create an Asana task.';
        }
        if (!project_id || typeof project_id !== 'string') {
            return 'Project ID is required to create an Asana task.';
        }
        const task = await client.tasks.createTask({
            name: task_name,
            projects: [project_id],
        });
        return `Asana task created: ${task.name}`;
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't create the Asana task due to an error.");
    }
}
export async function handleQueryAsanaTasks(userId, entities) {
    try {
        const apiKey = await getAsanaApiKey(userId);
        if (!apiKey) {
            return 'Asana API key not configured for this user.';
        }
        const client = asana.Client.create().useAccessToken(apiKey);
        const { project_id } = entities;
        if (!project_id || typeof project_id !== 'string') {
            return 'Project ID is required to query Asana tasks.';
        }
        const tasks = await client.tasks.getTasks({ project: project_id });
        if (!tasks.data.length) {
            return 'No tasks found in the specified Asana project.';
        }
        let taskList = 'Here are the tasks in the specified Asana project:\n';
        for (const task of tasks.data) {
            taskList += `- ${task.name}\n`;
        }
        return taskList;
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't query the Asana tasks due to an error.");
    }
}
export async function handleUpdateAsanaTask(userId, entities) {
    try {
        const apiKey = await getAsanaApiKey(userId);
        if (!apiKey) {
            return 'Asana API key not configured for this user.';
        }
        const client = asana.Client.create().useAccessToken(apiKey);
        const { task_id, task_name } = entities;
        if (!task_id || typeof task_id !== 'string') {
            return 'Task ID is required to update an Asana task.';
        }
        if (!task_name || typeof task_name !== 'string') {
            return 'Task name is required to update an Asana task.';
        }
        const task = await client.tasks.updateTask(task_id, {
            name: task_name,
        });
        return `Asana task updated: ${task.name}`;
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't update the Asana task due to an error.");
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXNhbmEuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJhc2FuYS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBQUUsT0FBTyxFQUFFLE1BQU0sb0JBQW9CLENBQUM7QUFDN0MsT0FBTyxFQUFFLG1CQUFtQixFQUFFLE1BQU0sMkJBQTJCLENBQUM7QUFDaEUsT0FBTyxFQUFFLFdBQVcsRUFBRSxNQUFNLDJCQUEyQixDQUFDO0FBQ3hELE9BQU8sS0FBSyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBRS9CLEtBQUssVUFBVSxjQUFjLENBQUMsTUFBYztJQUMxQyxNQUFNLEtBQUssR0FBRzs7Ozs7O0tBTVgsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHO1FBQ2hCLE1BQU07UUFDTixXQUFXLEVBQUUsZUFBZTtLQUM3QixDQUFDO0lBQ0YsTUFBTSxRQUFRLEdBQUcsTUFBTSxtQkFBbUIsQ0FFdkMsS0FBSyxFQUFFLFNBQVMsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLENBQUMsQ0FBQztJQUNsRCxJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsSUFBSSxRQUFRLENBQUMsZ0JBQWdCLENBQUMsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1FBQ3RFLE9BQU8sT0FBTyxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO0lBQ2hFLENBQUM7SUFDRCxPQUFPLElBQUksQ0FBQztBQUNkLENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLHFCQUFxQixDQUN6QyxNQUFjLEVBQ2QsUUFBYTtJQUViLElBQUksQ0FBQztRQUNILE1BQU0sTUFBTSxHQUFHLE1BQU0sY0FBYyxDQUFDLE1BQU0sQ0FBQyxDQUFDO1FBQzVDLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUNaLE9BQU8sNkNBQTZDLENBQUM7UUFDdkQsQ0FBQztRQUNELE1BQU0sTUFBTSxHQUFHLEtBQUssQ0FBQyxNQUFNLENBQUMsTUFBTSxFQUFF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QVMsS0FBSyxRQUFRLEVBQUUsQ0FBQztZQUNoRCxPQUFPLGdEQUFnRCxDQUFDO1FBQzFELENBQUM7UUFFRCxNQUFNLElBQUksR0FBRyxNQUFNLE1BQU0sQ0FBQyxLQUFLLENBQUMsVUFBVSxDQUFDLE9BQU8sRUFBRTtZQUNsRCxJQUFJLEVBQUUsU0FBUztTQUNoQixDQUFDLENBQUM7UUFFSCxPQUFPLHVCQUF1QixJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFDNUMsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxXQUFXLENBQ2hCLEtBQUssRUFDTCwwREFBMEQsQ0FDM0QsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgU2tpbGxSZXNwb25zZSB9IGZyb20gJy4uLy4uL3R5cGVzJztcbmltcG9ydCB7IGRlY3J5cHQgfSBmcm9tICcuLi8uLi9fbGlicy9jcnlwdG8nO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSB9IGZyb20gJy4uLy4uL19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IHsgaGFuZGxlRXJyb3IgfSBmcm9tICcuLi8uLi9fdXRpbHMvZXJyb3JIYW5kbGVyJztcbmltcG9ydCAqIGFzIGFzYW5hIGZyb20gJ2FzYW5hJztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0QXNhbmFBcGlLZXkodXNlcklkOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZyB8IG51bGw+IHtcbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJDcmVkZW50aWFsKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlTmFtZTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl9jcmVkZW50aWFscyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBzZXJ2aWNlX25hbWU6IHtfZXE6ICRzZXJ2aWNlTmFtZX19KSB7XG4gICAgICAgICAgICAgICAgZW5jcnlwdGVkX3NlY3JldFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgIHVzZXJJZCxcbiAgICBzZXJ2aWNlTmFtZTogJ2FzYW5hX2FwaV9rZXknLFxuICB9O1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8e1xuICAgIHVzZXJfY3JlZGVudGlhbHM6IHsgZW5jcnlwdGVkX3NlY3JldDogc3RyaW5nIH1bXTtcbiAgfT4ocXVlcnksIHZhcmlhYmxlcywgJ0dldFVzZXJDcmVkZW50aWFsJywgdXNlcklkKTtcbiAgaWYgKHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMgJiYgcmVzcG9uc2UudXNlcl9jcmVkZW50aWFscy5sZW5ndGggPiAwKSB7XG4gICAgcmV0dXJuIGRlY3J5cHQocmVzcG9uc2UudXNlcl9jcmVkZW50aWFsc1swXS5lbmNyeXB0ZWRfc2VjcmV0KTtcbiAgfVxuICByZXR1cm4gbnVsbDtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUNyZWF0ZUFzYW5hVGFzayhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBhbnlcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgYXBpS2V5ID0gYXdhaXQgZ2V0QXNhbmFBcGlLZXkodXNlcklkKTtcbiAgICBpZiAoIWFwaUtleSkge1xuICAgICAgcmV0dXJuICdBc2FuYSBBUEkga2V5IG5vdCBjb25maWd1cmVkIGZvciB0aGlzIHVzZXIuJztcbiAgICB9XG4gICAgY29uc3QgY2xpZW50ID0gYXNhbmEuQ2xpZW50LmNyZWF0ZSgpLnVzZUFjY2Vzc1Rva2VuKGFwaUtleSk7XG5cbiAgICBjb25zdCB7IHRhc2tfbmFtZSwgcHJvamVjdF9pZCB9ID0gZW50aXRpZXM7XG5cbiAgICBpZiAoIXRhc2tfbmFtZSB8fCB0eXBlb2YgdGFza19uYW1lICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdUYXNrIG5hbWUgaXMgcmVxdWlyZWQgdG8gY3JlYXRlIGFuIEFzYW5hIHRhc2suJztcbiAgICB9XG5cbiAgICBpZiAoIXByb2plY3RfaWQgfHwgdHlwZW9mIHByb2plY3RfaWQgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gJ1Byb2plY3QgSUQgaXMgcmVxdWlyZWQgdG8gY3JlYXRlIGFuIEFzYW5hIHRhc2suJztcbiAgICB9XG5cbiAgICBjb25zdCB0YXNrID0gYXdhaXQgY2xpZW50LnRhc2tzLmNyZWF0ZVRhc2soe1xuICAgICAgbmFtZTogdGFza19uYW1lLFxuICAgICAgcHJvamVjdHM6IFtwcm9qZWN0X2lkXSxcbiAgICB9KTtcblxuICAgIHJldHVybiBgQXNhbmEgdGFzayBjcmVhdGVkOiAke3Rhc2submFtZX1gO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICBcIlNvcnJ5LCBJIGNvdWxkbid0IGNyZWF0ZSB0aGUgQXNhbmEgdGFzayBkdWUgdG8gYW4gZXJyb3IuXCJcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVRdWVyeUFzYW5hVGFza3MoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55XG4pOiBQcm9taXNlPHN0cmluZz4ge1xuICB0cnkge1xuICAgIGNvbnN0IGFwaUtleSA9IGF3YWl0IGdldEFzYW5hQXBpS2V5KHVzZXJJZCk7XG4gICAgaWYgKCFhcGlLZXkpIHtcbiAgICAgIHJldHVybiAnQXNhbmEgQVBJIGtleSBub3QgY29uZmlndXJlZCBmb3IgdGhpcyB1c2VyLic7XG4gICAgfVxuICAgIGNvbnN0IGNsaWVudCA9IGFzYW5hLkNsaWVudC5jcmVhdGUoKS51c2VBY2Nlc3NUb2tlbihhcGlLZXkpO1xuXG4gICAgY29uc3QgeyBwcm9qZWN0X2lkIH0gPSBlbnRpdGllcztcblxuICAgIGlmICghcHJvamVjdF9pZCB8fCB0eXBlb2YgcHJvamVjdF9pZCAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnUHJvamVjdCBJRCBpcyByZXF1aXJlZCB0byBxdWVyeSBBc2FuYSB0YXNrcy4nO1xuICAgIH1cblxuICAgIGNvbnN0IHRhc2tzID0gYXdhaXQgY2xpZW50LnRhc2tzLmdldFRhc2tzKHsgcHJvamVjdDogcHJvamVjdF9pZCB9KTtcblxuICAgIGlmICghdGFza3MuZGF0YS5sZW5ndGgpIHtcbiAgICAgIHJldHVybiAnTm8gdGFza3MgZm91bmQgaW4gdGhlIHNwZWNpZmllZCBBc2FuYSBwcm9qZWN0Lic7XG4gICAgfVxuXG4gICAgbGV0IHRhc2tMaXN0ID0gJ0hlcmUgYXJlIHRoZSB0YXNrcyBpbiB0aGUgc3BlY2lmaWVkIEFzYW5hIHByb2plY3Q6XFxuJztcbiAgICBmb3IgKGNvbnN0IHRhc2sgb2YgdGFza3MuZGF0YSkge1xuICAgICAgdGFza0xpc3QgKz0gYC0gJHt0YXNrLm5hbWV9XFxuYDtcbiAgICB9XG5cbiAgICByZXR1cm4gdGFza0xpc3Q7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICByZXR1cm4gaGFuZGxlRXJyb3IoXG4gICAgICBlcnJvcixcbiAgICAgIFwiU29ycnksIEkgY291bGRuJ3QgcXVlcnkgdGhlIEFzYW5hIHRhc2tzIGR1ZSB0byBhbiBlcnJvci5cIlxuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVVwZGF0ZUFzYW5hVGFzayhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBhbnlcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgYXBpS2V5ID0gYXdhaXQgZ2V0QXNhbmFBcGlLZXkodXNlcklkKTtcbiAgICBpZiAoIWFwaUtleSkge1xuICAgICAgcmV0dXJuICdBc2FuYSBBUEkga2V5IG5vdCBjb25maWd1cmVkIGZvciB0aGlzIHVzZXIuJztcbiAgICB9XG4gICAgY29uc3QgY2xpZW50ID0gYXNhbmEuQ2xpZW50LmNyZWF0ZSgpLnVzZUFjY2Vzc1Rva2VuKGFwaUtleSk7XG5cbiAgICBjb25zdCB7IHRhc2tfaWQsIHRhc2tfbmFtZSB9ID0gZW50aXRpZXM7XG5cbiAgICBpZiAoIXRhc2tfaWQgfHwgdHlwZW9mIHRhc2tfaWQgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gJ1Rhc2sgSUQgaXMgcmVxdWlyZWQgdG8gdXBkYXRlIGFuIEFzYW5hIHRhc2suJztcbiAgICB9XG5cbiAgICBpZiAoIXRhc2tfbmFtZSB8fCB0eXBlb2YgdGFza19uYW1lICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdUYXNrIG5hbWUgaXMgcmVxdWlyZWQgdG8gdXBkYXRlIGFuIEFzYW5hIHRhc2suJztcbiAgICB9XG5cbiAgICBjb25zdCB0YXNrID0gYXdhaXQgY2xpZW50LnRhc2tzLnVwZGF0ZVRhc2sodGFza19pZCwge1xuICAgICAgbmFtZTogdGFza19uYW1lLFxuICAgIH0pO1xuXG4gICAgcmV0dXJuIGBBc2FuYSB0YXNrIHVwZGF0ZWQ6ICR7dGFzay5uYW1lfWA7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICByZXR1cm4gaGFuZGxlRXJyb3IoXG4gICAgICBlcnJvcixcbiAgICAgIFwiU29ycnksIEkgY291bGRuJ3QgdXBkYXRlIHRoZSBBc2FuYSB0YXNrIGR1ZSB0byBhbiBlcnJvci5cIlxuICAgICk7XG4gIH1cbn1cbiJdfQ==
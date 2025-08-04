import { executeGraphQLQuery } from '../_libs/graphqlClient';
import got from 'got';
async function getZapierWebhookUrl(userId) {
    const query = `
        query GetUserSetting($userId: String!, $key: String!) {
            user_settings(where: {user_id: {_eq: $userId}, key: {_eq: $key}}) {
                value
            }
        }
    `;
    const variables = {
        userId,
        key: 'zapier_webhook_url',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserSetting', userId);
    if (response.user_settings && response.user_settings.length > 0) {
        return response.user_settings[0].value;
    }
    return null;
}
export async function triggerZap(userId, zapName, data) {
    console.log(`Triggering Zap: "${zapName}" for user ${userId} with data:`, data);
    if (!zapName) {
        return { success: false, message: 'Zap name is required.' };
    }
    const webhookUrl = await getZapierWebhookUrl(userId);
    if (!webhookUrl) {
        return { success: false, message: 'Zapier webhook URL not configured.' };
    }
    try {
        await got.post(webhookUrl, {
            json: {
                zapName,
                ...data,
            },
        });
        const mockZapRunId = `zapRun_${Date.now()}`;
        return {
            success: true,
            zapName,
            runId: mockZapRunId,
            message: `Zap "${zapName}" triggered successfully.`,
        };
    }
    catch (error) {
        console.error(`Error triggering Zapier webhook for user ${userId}:`, error);
        return { success: false, message: 'Failed to trigger Zapier webhook.' };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiemFwaWVyU2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiemFwaWVyU2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxNQUFNLHdCQUF3QixDQUFDO0FBQzdELE9BQU8sR0FBRyxNQUFNLEtBQUssQ0FBQztBQU10QixLQUFLLFVBQVUsbUJBQW1CLENBQUMsTUFBYztJQUMvQyxNQUFNLEtBQUssR0FBRzs7Ozs7O0tBTVgsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHO1FBQ2hCLE1BQU07UUFDTixHQUFHLEVBQUUsb0JBQW9CO0tBQzFCLENBQUM7SUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLG1CQUFtQixDQUV2QyxLQUFLLEVBQUUsU0FBUyxFQUFFLGdCQUFnQixFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQy9DLElBQUksUUFBUSxDQUFDLGFBQWEsSUFBSSxRQUFRLENBQUMsYUFBYSxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztRQUNoRSxPQUFPLFFBQVEsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDO0lBQ3pDLENBQUM7SUFDRCxPQUFPLElBQUksQ0FBQztBQUNkLENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLFVBQVUsQ0FDOUIsTUFBYyxFQUNkLE9BQWUsRUFDZixJQUFhO0lBRWIsT0FBTyxDQUFDLEdBQUcsQ0FDVCxvQkFBb0IsT0FBTyxjQUFjLE1BQU0sYUFBYSxFQUM1RCxJQUFJLENBQ0wsQ0FBQztJQUVGLElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUNiLE9BQU8sRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSx1QkFBdUIsRUFBRSxDQUFDO0lBQzlELENBQUM7SUFFRCxNQUFNLFVBQVUsR0FBRyxNQUFNLG1CQUFtQixDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBRXJELElBQUksQ0FBQyxVQUFVLEVBQUUsQ0FBQztRQUNoQixPQUFPLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsb0NBQW9DLEVBQUUsQ0FBQztJQUMzRSxDQUFDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxHQUFHLENBQUMsSUFBSSxDQUFDLFVBQVUsRUFBRTtZQUN6QixJQUFJLEVBQUU7Z0JBQ0osT0FBTztnQkFDUCxHQUFHLElBQUk7YUFDUjtTQUNGLENBQUMsQ0FBQztRQUNILE1BQU0sWUFBWSxHQUFHLFVBQVUsSUFBSSxDQUFDLEdBQUcsRUFBRSxFQUFFLENBQUM7UUFDNUMsT0FBTztZQUNMLE9BQU8sRUFBRSxJQUFJO1lBQ2IsT0FBTztZQUNQLEtBQUssRUFBRSxZQUFZO1lBQ25CLE9BQU8sRUFBRSxRQUFRLE9BQU8sMkJBQTJCO1NBQ3BELENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sQ0FBQyxLQUFLLENBQUMsNENBQTRDLE1BQU0sR0FBRyxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQzVFLE9BQU8sRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxtQ0FBbUMsRUFBRSxDQUFDO0lBQzFFLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgWmFwVHJpZ2dlclJlc3BvbnNlIH0gZnJvbSAnLi4vdHlwZXMnO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSB9IGZyb20gJy4uL19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuXG5leHBvcnQgaW50ZXJmYWNlIFphcERhdGEge1xuICBba2V5OiBzdHJpbmddOiBhbnk7XG59XG5cbmFzeW5jIGZ1bmN0aW9uIGdldFphcGllcldlYmhvb2tVcmwodXNlcklkOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZyB8IG51bGw+IHtcbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJTZXR0aW5nKCR1c2VySWQ6IFN0cmluZyEsICRrZXk6IFN0cmluZyEpIHtcbiAgICAgICAgICAgIHVzZXJfc2V0dGluZ3Mod2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfSwga2V5OiB7X2VxOiAka2V5fX0pIHtcbiAgICAgICAgICAgICAgICB2YWx1ZVxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgIHVzZXJJZCxcbiAgICBrZXk6ICd6YXBpZXJfd2ViaG9va191cmwnLFxuICB9O1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8e1xuICAgIHVzZXJfc2V0dGluZ3M6IHsgdmFsdWU6IHN0cmluZyB9W107XG4gIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsICdHZXRVc2VyU2V0dGluZycsIHVzZXJJZCk7XG4gIGlmIChyZXNwb25zZS51c2VyX3NldHRpbmdzICYmIHJlc3BvbnNlLnVzZXJfc2V0dGluZ3MubGVuZ3RoID4gMCkge1xuICAgIHJldHVybiByZXNwb25zZS51c2VyX3NldHRpbmdzWzBdLnZhbHVlO1xuICB9XG4gIHJldHVybiBudWxsO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdHJpZ2dlclphcChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHphcE5hbWU6IHN0cmluZyxcbiAgZGF0YTogWmFwRGF0YVxuKTogUHJvbWlzZTxaYXBUcmlnZ2VyUmVzcG9uc2U+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYFRyaWdnZXJpbmcgWmFwOiBcIiR7emFwTmFtZX1cIiBmb3IgdXNlciAke3VzZXJJZH0gd2l0aCBkYXRhOmAsXG4gICAgZGF0YVxuICApO1xuXG4gIGlmICghemFwTmFtZSkge1xuICAgIHJldHVybiB7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiAnWmFwIG5hbWUgaXMgcmVxdWlyZWQuJyB9O1xuICB9XG5cbiAgY29uc3Qgd2ViaG9va1VybCA9IGF3YWl0IGdldFphcGllcldlYmhvb2tVcmwodXNlcklkKTtcblxuICBpZiAoIXdlYmhvb2tVcmwpIHtcbiAgICByZXR1cm4geyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogJ1phcGllciB3ZWJob29rIFVSTCBub3QgY29uZmlndXJlZC4nIH07XG4gIH1cblxuICB0cnkge1xuICAgIGF3YWl0IGdvdC5wb3N0KHdlYmhvb2tVcmwsIHtcbiAgICAgIGpzb246IHtcbiAgICAgICAgemFwTmFtZSxcbiAgICAgICAgLi4uZGF0YSxcbiAgICAgIH0sXG4gICAgfSk7XG4gICAgY29uc3QgbW9ja1phcFJ1bklkID0gYHphcFJ1bl8ke0RhdGUubm93KCl9YDtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIHphcE5hbWUsXG4gICAgICBydW5JZDogbW9ja1phcFJ1bklkLFxuICAgICAgbWVzc2FnZTogYFphcCBcIiR7emFwTmFtZX1cIiB0cmlnZ2VyZWQgc3VjY2Vzc2Z1bGx5LmAsXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKGBFcnJvciB0cmlnZ2VyaW5nIFphcGllciB3ZWJob29rIGZvciB1c2VyICR7dXNlcklkfTpgLCBlcnJvcik7XG4gICAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6ICdGYWlsZWQgdG8gdHJpZ2dlciBaYXBpZXIgd2ViaG9vay4nIH07XG4gIH1cbn1cbiJdfQ==
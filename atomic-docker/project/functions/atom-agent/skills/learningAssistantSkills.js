import { createNotionPage } from './notionAndResearchSkills';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import PocketAPI from 'pocket-api';
async function getPocketToken(userId) {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                access_token
            }
        }
    `;
    const variables = {
        userId,
        service: 'pocket',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return decrypt(response.user_tokens[0].access_token);
    }
    return null;
}
async function getPocketArticles(userId) {
    const accessToken = await getPocketToken(userId);
    if (!accessToken) {
        throw new Error('Pocket token not configured for this user.');
    }
    const pocket = new PocketAPI({
        consumer_key: process.env.POCKET_CONSUMER_KEY,
        access_token: accessToken,
    });
    return new Promise((resolve, reject) => {
        pocket.get({ count: 10, detailType: 'complete' }, (err, data) => {
            if (err) {
                return reject(err);
            }
            resolve(Object.values(data.list));
        });
    });
}
export async function generateLearningPlan(userId, notionDatabaseId) {
    const articles = await getPocketArticles(userId);
    const articleTitles = articles
        .map((article) => article.resolved_title)
        .join('\n');
    const learningPlan = `
        Here is a personalized learning plan based on your recent articles:

        ${articleTitles}
    `;
    await createNotionPage(userId, {
        parent: { database_id: notionDatabaseId },
        properties: {
            title: {
                title: [
                    {
                        text: {
                            content: 'Personalized Learning Plan',
                        },
                    },
                ],
            },
        },
        children: [
            {
                object: 'block',
                type: 'paragraph',
                paragraph: {
                    rich_text: [
                        {
                            type: 'text',
                            text: {
                                content: learningPlan,
                            },
                        },
                    ],
                },
            },
        ],
    });
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGVhcm5pbmdBc3Npc3RhbnRTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsZWFybmluZ0Fzc2lzdGFudFNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsZ0JBQWdCLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQztBQUM3RCxPQUFPLEVBQUUsT0FBTyxFQUFFLE1BQU0saUJBQWlCLENBQUM7QUFDMUMsT0FBTyxFQUFFLG1CQUFtQixFQUFFLE1BQU0sd0JBQXdCLENBQUM7QUFDN0QsT0FBTyxTQUFTLE1BQU0sWUFBWSxDQUFDO0FBRW5DLEtBQUssVUFBVSxjQUFjLENBQUMsTUFBYztJQUMxQyxNQUFNLEtBQUssR0FBRzs7Ozs7O0tBTVgsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHO1FBQ2hCLE1BQU07UUFDTixPQUFPLEVBQUUsUUFBUTtLQUNsQixDQUFDO0lBQ0YsTUFBTSxRQUFRLEdBQUcsTUFBTSxtQkFBbUIsQ0FFdkMsS0FBSyxFQUFFLFNBQVMsRUFBRSxjQUFjLEVBQUUsTUFBTSxDQUFDLENBQUM7SUFDN0MsSUFBSSxRQUFRLENBQUMsV0FBVyxJQUFJLFFBQVEsQ0FBQyxXQUFXLENBQUMsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1FBQzVELE9BQU8sT0FBTyxDQUFDLFFBQVEsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLENBQUMsWUFBWSxDQUFDLENBQUM7SUFDdkQsQ0FBQztJQUNELE9BQU8sSUFBSSxDQUFDO0FBQ2QsQ0FBQztBQUVELEtBQUssVUFBVSxpQkFBaUIsQ0FBQyxNQUFjO0lBQzdDLE1BQU0sV0FBVyxHQUFHLE1BQU0sY0FBYyxDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBQ2pELElBQUksQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUNqQixNQUFNLElBQUksS0FBSyxDQUFDLDRDQUE0QyxDQUFDLENBQUM7SUFDaEUsQ0FBQztJQUVELE1BQU0sTUFBTSxHQUFHLElBQUksU0FBUyxDQUFDO1FBQzNCLFlBQVksRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLG1CQUFtQjtRQUM3QyxZQUFZLEVBQUUsV0FBVztLQUMxQixDQUFDLENBQUM7SUFFSCxPQUFPLElBQUksT0FBTyxDQUFDLENBQUMsT0FBTyxFQUFFLE1BQU0sRUFBRSxFQUFFO1FBQ3JDLE1BQU0sQ0FBQyxHQUFHLENBQUMsRUFBRSxLQUFLLEVBQUUsRUFBRSxFQUFFLFVBQVUsRUFBRSxVQUFVLEVBQUUsRUFBRSxDQUFDLEdBQUcsRUFBRSxJQUFJLEVBQUUsRUFBRTtZQUM5RCxJQUFJLEdBQUcsRUFBRSxDQUFDO2dCQUNSLE9BQU8sTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDO1lBQ3JCLENBQUM7WUFDRCxPQUFPLENBQUMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQztRQUNwQyxDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsb0JBQW9CLENBQ3hDLE1BQWMsRUFDZCxnQkFBd0I7SUFFeEIsTUFBTSxRQUFRLEdBQUcsTUFBTSxpQkFBaUIsQ0FBQyxNQUFNLENBQUMsQ0FBQztJQUVqRCxNQUFNLGFBQWEsR0FBRyxRQUFRO1NBQzNCLEdBQUcsQ0FBQyxDQUFDLE9BQU8sRUFBRSxFQUFFLENBQUMsT0FBTyxDQUFDLGNBQWMsQ0FBQztTQUN4QyxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUM7SUFFZCxNQUFNLFlBQVksR0FBRzs7O1VBR2IsYUFBYTtLQUNsQixDQUFDO0lBRUosTUFBTSxnQkFBZ0IsQ0FBQyxNQUFNLEVBQUU7UUFDN0IsTUFBTSxFQUFFLEVBQUUsV0FBVyxFQUFFLGdCQUFnQixFQUFFO1FBQ3pDLFVBQVUsRUFBRTtZQUNWLEtBQUssRUFBRTtnQkFDTCxLQUFLLEVBQUU7b0JBQ0w7d0JBQ0UsSUFBSSxFQUFFOzRCQUNKLE9BQU8sRUFBRSw0QkFBNEI7eUJBQ3RDO3FCQUNGO2lCQUNGO2FBQ0Y7U0FDRjtRQUNELFFBQVEsRUFBRTtZQUNSO2dCQUNFLE1BQU0sRUFBRSxPQUFPO2dCQUNmLElBQUksRUFBRSxXQUFXO2dCQUNqQixTQUFTLEVBQUU7b0JBQ1QsU0FBUyxFQUFFO3dCQUNUOzRCQUNFLElBQUksRUFBRSxNQUFNOzRCQUNaLElBQUksRUFBRTtnQ0FDSixPQUFPLEVBQUUsWUFBWTs2QkFDdEI7eUJBQ0Y7cUJBQ0Y7aUJBQ0Y7YUFDRjtTQUNGO0tBQ0YsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGNyZWF0ZU5vdGlvblBhZ2UgfSBmcm9tICcuL25vdGlvbkFuZFJlc2VhcmNoU2tpbGxzJztcbmltcG9ydCB7IGRlY3J5cHQgfSBmcm9tICcuLi9fbGlicy9jcnlwdG8nO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSB9IGZyb20gJy4uL19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IFBvY2tldEFQSSBmcm9tICdwb2NrZXQtYXBpJztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0UG9ja2V0VG9rZW4odXNlcklkOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZyB8IG51bGw+IHtcbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJUb2tlbigkdXNlcklkOiBTdHJpbmchLCAkc2VydmljZTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl90b2tlbnMod2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfSwgc2VydmljZToge19lcTogJHNlcnZpY2V9fSkge1xuICAgICAgICAgICAgICAgIGFjY2Vzc190b2tlblxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgIHVzZXJJZCxcbiAgICBzZXJ2aWNlOiAncG9ja2V0JyxcbiAgfTtcbiAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICB1c2VyX3Rva2VuczogeyBhY2Nlc3NfdG9rZW46IHN0cmluZyB9W107XG4gIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsICdHZXRVc2VyVG9rZW4nLCB1c2VySWQpO1xuICBpZiAocmVzcG9uc2UudXNlcl90b2tlbnMgJiYgcmVzcG9uc2UudXNlcl90b2tlbnMubGVuZ3RoID4gMCkge1xuICAgIHJldHVybiBkZWNyeXB0KHJlc3BvbnNlLnVzZXJfdG9rZW5zWzBdLmFjY2Vzc190b2tlbik7XG4gIH1cbiAgcmV0dXJuIG51bGw7XG59XG5cbmFzeW5jIGZ1bmN0aW9uIGdldFBvY2tldEFydGljbGVzKHVzZXJJZDogc3RyaW5nKTogUHJvbWlzZTxhbnlbXT4ge1xuICBjb25zdCBhY2Nlc3NUb2tlbiA9IGF3YWl0IGdldFBvY2tldFRva2VuKHVzZXJJZCk7XG4gIGlmICghYWNjZXNzVG9rZW4pIHtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ1BvY2tldCB0b2tlbiBub3QgY29uZmlndXJlZCBmb3IgdGhpcyB1c2VyLicpO1xuICB9XG5cbiAgY29uc3QgcG9ja2V0ID0gbmV3IFBvY2tldEFQSSh7XG4gICAgY29uc3VtZXJfa2V5OiBwcm9jZXNzLmVudi5QT0NLRVRfQ09OU1VNRVJfS0VZLFxuICAgIGFjY2Vzc190b2tlbjogYWNjZXNzVG9rZW4sXG4gIH0pO1xuXG4gIHJldHVybiBuZXcgUHJvbWlzZSgocmVzb2x2ZSwgcmVqZWN0KSA9PiB7XG4gICAgcG9ja2V0LmdldCh7IGNvdW50OiAxMCwgZGV0YWlsVHlwZTogJ2NvbXBsZXRlJyB9LCAoZXJyLCBkYXRhKSA9PiB7XG4gICAgICBpZiAoZXJyKSB7XG4gICAgICAgIHJldHVybiByZWplY3QoZXJyKTtcbiAgICAgIH1cbiAgICAgIHJlc29sdmUoT2JqZWN0LnZhbHVlcyhkYXRhLmxpc3QpKTtcbiAgICB9KTtcbiAgfSk7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZW5lcmF0ZUxlYXJuaW5nUGxhbihcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG5vdGlvbkRhdGFiYXNlSWQ6IHN0cmluZ1xuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGNvbnN0IGFydGljbGVzID0gYXdhaXQgZ2V0UG9ja2V0QXJ0aWNsZXModXNlcklkKTtcblxuICBjb25zdCBhcnRpY2xlVGl0bGVzID0gYXJ0aWNsZXNcbiAgICAubWFwKChhcnRpY2xlKSA9PiBhcnRpY2xlLnJlc29sdmVkX3RpdGxlKVxuICAgIC5qb2luKCdcXG4nKTtcblxuICBjb25zdCBsZWFybmluZ1BsYW4gPSBgXG4gICAgICAgIEhlcmUgaXMgYSBwZXJzb25hbGl6ZWQgbGVhcm5pbmcgcGxhbiBiYXNlZCBvbiB5b3VyIHJlY2VudCBhcnRpY2xlczpcblxuICAgICAgICAke2FydGljbGVUaXRsZXN9XG4gICAgYDtcblxuICBhd2FpdCBjcmVhdGVOb3Rpb25QYWdlKHVzZXJJZCwge1xuICAgIHBhcmVudDogeyBkYXRhYmFzZV9pZDogbm90aW9uRGF0YWJhc2VJZCB9LFxuICAgIHByb3BlcnRpZXM6IHtcbiAgICAgIHRpdGxlOiB7XG4gICAgICAgIHRpdGxlOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgdGV4dDoge1xuICAgICAgICAgICAgICBjb250ZW50OiAnUGVyc29uYWxpemVkIExlYXJuaW5nIFBsYW4nLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICB9LFxuICAgIGNoaWxkcmVuOiBbXG4gICAgICB7XG4gICAgICAgIG9iamVjdDogJ2Jsb2NrJyxcbiAgICAgICAgdHlwZTogJ3BhcmFncmFwaCcsXG4gICAgICAgIHBhcmFncmFwaDoge1xuICAgICAgICAgIHJpY2hfdGV4dDogW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICB0eXBlOiAndGV4dCcsXG4gICAgICAgICAgICAgIHRleHQ6IHtcbiAgICAgICAgICAgICAgICBjb250ZW50OiBsZWFybmluZ1BsYW4sXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIF0sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIF0sXG4gIH0pO1xufVxuIl19
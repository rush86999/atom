"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const nextjs_1 = require("supertokens-node/nextjs");
const graphqlClient_1 = require("../../../../../project/functions/_libs/graphqlClient");
async function handler(req, res) {
    let session;
    try {
        session = await (0, nextjs_1.getSession)(req, res, {
            overrideGlobalClaimValidators: () => [],
        });
    }
    catch (err) {
        return res.status(401).json({ message: 'Unauthorized' });
    }
    const userId = session.getUserId();
    const { code, state } = req.query;
    // In a real app, you should validate the 'state' parameter here
    const slackClientId = process.env.SLACK_CLIENT_ID;
    const slackClientSecret = process.env.SLACK_CLIENT_SECRET;
    const redirectUri = process.env.SLACK_REDIRECT_URI;
    if (!slackClientId || !slackClientSecret || !redirectUri) {
        return res
            .status(500)
            .json({ message: 'Slack environment variables not configured.' });
    }
    try {
        const response = await fetch('https://slack.com/api/oauth.v2.access', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                client_id: slackClientId,
                client_secret: slackClientSecret,
                code: code,
                redirect_uri: redirectUri,
            }),
        });
        const data = await response.json();
        if (data.ok) {
            const accessToken = data.authed_user.access_token;
            // Save the token to the user_tokens table
            const mutation = `
                mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!) {
                    insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken}) {
                        id
                    }
                }
            `;
            const variables = {
                userId,
                service: 'slack',
                accessToken,
            };
            await (0, graphqlClient_1.executeGraphQLQuery)(mutation, variables, 'InsertUserToken', userId);
            return res.redirect('/Settings/UserViewSettings');
        }
        else {
            return res
                .status(500)
                .json({ message: `Slack OAuth error: ${data.error}` });
        }
    }
    catch (error) {
        console.error('Error during Slack OAuth callback:', error);
        return res
            .status(500)
            .json({ message: 'Failed to complete Slack OAuth flow' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUtBLDBCQTBFQztBQTlFRCxvREFBcUQ7QUFFckQsd0ZBQTJGO0FBRTVFLEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLElBQUksT0FBeUIsQ0FBQztJQUM5QixJQUFJLENBQUM7UUFDSCxPQUFPLEdBQUcsTUFBTSxJQUFBLG1CQUFVLEVBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRTtZQUNuQyw2QkFBNkIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxFQUFFO1NBQ3hDLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLEdBQUcsRUFBRSxDQUFDO1FBQ2IsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxjQUFjLEVBQUUsQ0FBQyxDQUFDO0lBQzNELENBQUM7SUFFRCxNQUFNLE1BQU0sR0FBRyxPQUFPLENBQUMsU0FBUyxFQUFFLENBQUM7SUFDbkMsTUFBTSxFQUFFLElBQUksRUFBRSxLQUFLLEVBQUUsR0FBRyxHQUFHLENBQUMsS0FBSyxDQUFDO0lBRWxDLGdFQUFnRTtJQUVoRSxNQUFNLGFBQWEsR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLGVBQWUsQ0FBQztJQUNsRCxNQUFNLGlCQUFpQixHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsbUJBQW1CLENBQUM7SUFDMUQsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxrQkFBa0IsQ0FBQztJQUVuRCxJQUFJLENBQUMsYUFBYSxJQUFJLENBQUMsaUJBQWlCLElBQUksQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUN6RCxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLDZDQUE2QyxFQUFFLENBQUMsQ0FBQztJQUN0RSxDQUFDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxLQUFLLENBQUMsdUNBQXVDLEVBQUU7WUFDcEUsTUFBTSxFQUFFLE1BQU07WUFDZCxPQUFPLEVBQUU7Z0JBQ1AsY0FBYyxFQUFFLG1DQUFtQzthQUNwRDtZQUNELElBQUksRUFBRSxJQUFJLGVBQWUsQ0FBQztnQkFDeEIsU0FBUyxFQUFFLGFBQWE7Z0JBQ3hCLGFBQWEsRUFBRSxpQkFBaUI7Z0JBQ2hDLElBQUksRUFBRSxJQUFjO2dCQUNwQixZQUFZLEVBQUUsV0FBVzthQUMxQixDQUFDO1NBQ0gsQ0FBQyxDQUFDO1FBRUgsTUFBTSxJQUFJLEdBQUcsTUFBTSxRQUFRLENBQUMsSUFBSSxFQUFFLENBQUM7UUFFbkMsSUFBSSxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7WUFDWixNQUFNLFdBQVcsR0FBRyxJQUFJLENBQUMsV0FBVyxDQUFDLFlBQVksQ0FBQztZQUVsRCwwQ0FBMEM7WUFDMUMsTUFBTSxRQUFRLEdBQUc7Ozs7OzthQU1WLENBQUM7WUFDUixNQUFNLFNBQVMsR0FBRztnQkFDaEIsTUFBTTtnQkFDTixPQUFPLEVBQUUsT0FBTztnQkFDaEIsV0FBVzthQUNaLENBQUM7WUFDRixNQUFNLElBQUEsbUNBQW1CLEVBQUMsUUFBUSxFQUFFLFNBQVMsRUFBRSxpQkFBaUIsRUFBRSxNQUFNLENBQUMsQ0FBQztZQUUxRSxPQUFPLEdBQUcsQ0FBQyxRQUFRLENBQUMsNEJBQTRCLENBQUMsQ0FBQztRQUNwRCxDQUFDO2FBQU0sQ0FBQztZQUNOLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxzQkFBc0IsSUFBSSxDQUFDLEtBQUssRUFBRSxFQUFFLENBQUMsQ0FBQztRQUMzRCxDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsS0FBSyxDQUFDLG9DQUFvQyxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQzNELE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUscUNBQXFDLEVBQUUsQ0FBQyxDQUFDO0lBQzlELENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHsgZ2V0U2Vzc2lvbiB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvbmV4dGpzJztcbmltcG9ydCB7IFNlc3Npb25Db250YWluZXIgfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMUXVlcnkgfSBmcm9tICcuLi8uLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9fbGlicy9ncmFwaHFsQ2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2Vcbikge1xuICBsZXQgc2Vzc2lvbjogU2Vzc2lvbkNvbnRhaW5lcjtcbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6ICgpID0+IFtdLFxuICAgIH0pO1xuICB9IGNhdGNoIChlcnIpIHtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDEpLmpzb24oeyBtZXNzYWdlOiAnVW5hdXRob3JpemVkJyB9KTtcbiAgfVxuXG4gIGNvbnN0IHVzZXJJZCA9IHNlc3Npb24uZ2V0VXNlcklkKCk7XG4gIGNvbnN0IHsgY29kZSwgc3RhdGUgfSA9IHJlcS5xdWVyeTtcblxuICAvLyBJbiBhIHJlYWwgYXBwLCB5b3Ugc2hvdWxkIHZhbGlkYXRlIHRoZSAnc3RhdGUnIHBhcmFtZXRlciBoZXJlXG5cbiAgY29uc3Qgc2xhY2tDbGllbnRJZCA9IHByb2Nlc3MuZW52LlNMQUNLX0NMSUVOVF9JRDtcbiAgY29uc3Qgc2xhY2tDbGllbnRTZWNyZXQgPSBwcm9jZXNzLmVudi5TTEFDS19DTElFTlRfU0VDUkVUO1xuICBjb25zdCByZWRpcmVjdFVyaSA9IHByb2Nlc3MuZW52LlNMQUNLX1JFRElSRUNUX1VSSTtcblxuICBpZiAoIXNsYWNrQ2xpZW50SWQgfHwgIXNsYWNrQ2xpZW50U2VjcmV0IHx8ICFyZWRpcmVjdFVyaSkge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oeyBtZXNzYWdlOiAnU2xhY2sgZW52aXJvbm1lbnQgdmFyaWFibGVzIG5vdCBjb25maWd1cmVkLicgfSk7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJ2h0dHBzOi8vc2xhY2suY29tL2FwaS9vYXV0aC52Mi5hY2Nlc3MnLCB7XG4gICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgfSxcbiAgICAgIGJvZHk6IG5ldyBVUkxTZWFyY2hQYXJhbXMoe1xuICAgICAgICBjbGllbnRfaWQ6IHNsYWNrQ2xpZW50SWQsXG4gICAgICAgIGNsaWVudF9zZWNyZXQ6IHNsYWNrQ2xpZW50U2VjcmV0LFxuICAgICAgICBjb2RlOiBjb2RlIGFzIHN0cmluZyxcbiAgICAgICAgcmVkaXJlY3RfdXJpOiByZWRpcmVjdFVyaSxcbiAgICAgIH0pLFxuICAgIH0pO1xuXG4gICAgY29uc3QgZGF0YSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcblxuICAgIGlmIChkYXRhLm9rKSB7XG4gICAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGRhdGEuYXV0aGVkX3VzZXIuYWNjZXNzX3Rva2VuO1xuXG4gICAgICAvLyBTYXZlIHRoZSB0b2tlbiB0byB0aGUgdXNlcl90b2tlbnMgdGFibGVcbiAgICAgIGNvbnN0IG11dGF0aW9uID0gYFxuICAgICAgICAgICAgICAgIG11dGF0aW9uIEluc2VydFVzZXJUb2tlbigkdXNlcklkOiBTdHJpbmchLCAkc2VydmljZTogU3RyaW5nISwgJGFjY2Vzc1Rva2VuOiBTdHJpbmchKSB7XG4gICAgICAgICAgICAgICAgICAgIGluc2VydF91c2VyX3Rva2Vuc19vbmUob2JqZWN0OiB7dXNlcl9pZDogJHVzZXJJZCwgc2VydmljZTogJHNlcnZpY2UsIGFjY2Vzc190b2tlbjogJGFjY2Vzc1Rva2VufSkge1xuICAgICAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGA7XG4gICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgc2VydmljZTogJ3NsYWNrJyxcbiAgICAgICAgYWNjZXNzVG9rZW4sXG4gICAgICB9O1xuICAgICAgYXdhaXQgZXhlY3V0ZUdyYXBoUUxRdWVyeShtdXRhdGlvbiwgdmFyaWFibGVzLCAnSW5zZXJ0VXNlclRva2VuJywgdXNlcklkKTtcblxuICAgICAgcmV0dXJuIHJlcy5yZWRpcmVjdCgnL1NldHRpbmdzL1VzZXJWaWV3U2V0dGluZ3MnKTtcbiAgICB9IGVsc2Uge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oeyBtZXNzYWdlOiBgU2xhY2sgT0F1dGggZXJyb3I6ICR7ZGF0YS5lcnJvcn1gIH0pO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBkdXJpbmcgU2xhY2sgT0F1dGggY2FsbGJhY2s6JywgZXJyb3IpO1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oeyBtZXNzYWdlOiAnRmFpbGVkIHRvIGNvbXBsZXRlIFNsYWNrIE9BdXRoIGZsb3cnIH0pO1xuICB9XG59XG4iXX0=
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
    const msTeamsClientId = process.env.MSTEAMS_CLIENT_ID;
    const msTeamsClientSecret = process.env.MSTEAMS_CLIENT_SECRET;
    const redirectUri = process.env.MSTEAMS_REDIRECT_URI;
    if (!msTeamsClientId || !msTeamsClientSecret || !redirectUri) {
        return res
            .status(500)
            .json({
            message: 'Microsoft Teams environment variables not configured.',
        });
    }
    try {
        const response = await fetch('https://login.microsoftonline.com/common/oauth2/v2.0/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                client_id: msTeamsClientId,
                client_secret: msTeamsClientSecret,
                code: code,
                redirect_uri: redirectUri,
                grant_type: 'authorization_code',
                scope: 'offline_access User.Read Mail.ReadWrite Calendars.ReadWrite',
            }),
        });
        const data = await response.json();
        if (response.ok) {
            const accessToken = data.access_token;
            const refreshToken = data.refresh_token;
            const expiresIn = data.expires_in;
            const expiresAt = new Date(Date.now() + expiresIn * 1000).toISOString();
            // Save the tokens to the user_tokens table
            const mutation = `
                mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!, $refreshToken: String, $expiresAt: timestamptz!) {
                    insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken, refresh_token: $refreshToken, expires_at: $expiresAt}) {
                        id
                    }
                }
            `;
            const variables = {
                userId,
                service: 'msteams',
                accessToken,
                refreshToken,
                expiresAt,
            };
            await (0, graphqlClient_1.executeGraphQLQuery)(mutation, variables, 'InsertUserToken', userId);
            return res.redirect('/Settings/UserViewSettings');
        }
        else {
            return res
                .status(500)
                .json({
                message: `Microsoft Teams OAuth error: ${data.error_description}`,
            });
        }
    }
    catch (error) {
        console.error('Error during Microsoft Teams OAuth callback:', error);
        return res
            .status(500)
            .json({ message: 'Failed to complete Microsoft Teams OAuth flow' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUtBLDBCQXdGQztBQTVGRCxvREFBcUQ7QUFFckQsd0ZBQTJGO0FBRTVFLEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLElBQUksT0FBeUIsQ0FBQztJQUM5QixJQUFJLENBQUM7UUFDSCxPQUFPLEdBQUcsTUFBTSxJQUFBLG1CQUFVLEVBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRTtZQUNuQyw2QkFBNkIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxFQUFFO1NBQ3hDLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLEdBQUcsRUFBRSxDQUFDO1FBQ2IsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxjQUFjLEVBQUUsQ0FBQyxDQUFDO0lBQzNELENBQUM7SUFFRCxNQUFNLE1BQU0sR0FBRyxPQUFPLENBQUMsU0FBUyxFQUFFLENBQUM7SUFDbkMsTUFBTSxFQUFFLElBQUksRUFBRSxLQUFLLEVBQUUsR0FBRyxHQUFHLENBQUMsS0FBSyxDQUFDO0lBRWxDLGdFQUFnRTtJQUVoRSxNQUFNLGVBQWUsR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLGlCQUFpQixDQUFDO0lBQ3RELE1BQU0sbUJBQW1CLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxxQkFBcUIsQ0FBQztJQUM5RCxNQUFNLFdBQVcsR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLG9CQUFvQixDQUFDO0lBRXJELElBQUksQ0FBQyxlQUFlLElBQUksQ0FBQyxtQkFBbUIsSUFBSSxDQUFDLFdBQVcsRUFBRSxDQUFDO1FBQzdELE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUM7WUFDSixPQUFPLEVBQUUsdURBQXVEO1NBQ2pFLENBQUMsQ0FBQztJQUNQLENBQUM7SUFFRCxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FDMUIsNERBQTRELEVBQzVEO1lBQ0UsTUFBTSxFQUFFLE1BQU07WUFDZCxPQUFPLEVBQUU7Z0JBQ1AsY0FBYyxFQUFFLG1DQUFtQzthQUNwRDtZQUNELElBQUksRUFBRSxJQUFJLGVBQWUsQ0FBQztnQkFDeEIsU0FBUyxFQUFFLGVBQWU7Z0JBQzFCLGFBQWEsRUFBRSxtQkFBbUI7Z0JBQ2xDLElBQUksRUFBRSxJQUFjO2dCQUNwQixZQUFZLEVBQUUsV0FBVztnQkFDekIsVUFBVSxFQUFFLG9CQUFvQjtnQkFDaEMsS0FBSyxFQUFFLDZEQUE2RDthQUNyRSxDQUFDO1NBQ0gsQ0FDRixDQUFDO1FBRUYsTUFBTSxJQUFJLEdBQUcsTUFBTSxRQUFRLENBQUMsSUFBSSxFQUFFLENBQUM7UUFFbkMsSUFBSSxRQUFRLENBQUMsRUFBRSxFQUFFLENBQUM7WUFDaEIsTUFBTSxXQUFXLEdBQUcsSUFBSSxDQUFDLFlBQVksQ0FBQztZQUN0QyxNQUFNLFlBQVksR0FBRyxJQUFJLENBQUMsYUFBYSxDQUFDO1lBQ3hDLE1BQU0sU0FBUyxHQUFHLElBQUksQ0FBQyxVQUFVLENBQUM7WUFDbEMsTUFBTSxTQUFTLEdBQUcsSUFBSSxJQUFJLENBQUMsSUFBSSxDQUFDLEdBQUcsRUFBRSxHQUFHLFNBQVMsR0FBRyxJQUFJLENBQUMsQ0FBQyxXQUFXLEVBQUUsQ0FBQztZQUV4RSwyQ0FBMkM7WUFDM0MsTUFBTSxRQUFRLEdBQUc7Ozs7OzthQU1WLENBQUM7WUFDUixNQUFNLFNBQVMsR0FBRztnQkFDaEIsTUFBTTtnQkFDTixPQUFPLEVBQUUsU0FBUztnQkFDbEIsV0FBVztnQkFDWCxZQUFZO2dCQUNaLFNBQVM7YUFDVixDQUFDO1lBQ0YsTUFBTSxJQUFBLG1DQUFtQixFQUFDLFFBQVEsRUFBRSxTQUFTLEVBQUUsaUJBQWlCLEVBQUUsTUFBTSxDQUFDLENBQUM7WUFFMUUsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUFDLDRCQUE0QixDQUFDLENBQUM7UUFDcEQsQ0FBQzthQUFNLENBQUM7WUFDTixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUM7Z0JBQ0osT0FBTyxFQUFFLGdDQUFnQyxJQUFJLENBQUMsaUJBQWlCLEVBQUU7YUFDbEUsQ0FBQyxDQUFDO1FBQ1AsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyw4Q0FBOEMsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUNyRSxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLCtDQUErQyxFQUFFLENBQUMsQ0FBQztJQUN4RSxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7IGdldFNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL25leHRqcyc7XG5pbXBvcnQgeyBTZXNzaW9uQ29udGFpbmVyIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgeyBleGVjdXRlR3JhcGhRTFF1ZXJ5IH0gZnJvbSAnLi4vLi4vLi4vLi4vLi4vcHJvamVjdC9mdW5jdGlvbnMvX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgbGV0IHNlc3Npb246IFNlc3Npb25Db250YWluZXI7XG4gIHRyeSB7XG4gICAgc2Vzc2lvbiA9IGF3YWl0IGdldFNlc3Npb24ocmVxLCByZXMsIHtcbiAgICAgIG92ZXJyaWRlR2xvYmFsQ2xhaW1WYWxpZGF0b3JzOiAoKSA9PiBbXSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZXJyKSB7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAxKS5qc29uKHsgbWVzc2FnZTogJ1VuYXV0aG9yaXplZCcgfSk7XG4gIH1cblxuICBjb25zdCB1c2VySWQgPSBzZXNzaW9uLmdldFVzZXJJZCgpO1xuICBjb25zdCB7IGNvZGUsIHN0YXRlIH0gPSByZXEucXVlcnk7XG5cbiAgLy8gSW4gYSByZWFsIGFwcCwgeW91IHNob3VsZCB2YWxpZGF0ZSB0aGUgJ3N0YXRlJyBwYXJhbWV0ZXIgaGVyZVxuXG4gIGNvbnN0IG1zVGVhbXNDbGllbnRJZCA9IHByb2Nlc3MuZW52Lk1TVEVBTVNfQ0xJRU5UX0lEO1xuICBjb25zdCBtc1RlYW1zQ2xpZW50U2VjcmV0ID0gcHJvY2Vzcy5lbnYuTVNURUFNU19DTElFTlRfU0VDUkVUO1xuICBjb25zdCByZWRpcmVjdFVyaSA9IHByb2Nlc3MuZW52Lk1TVEVBTVNfUkVESVJFQ1RfVVJJO1xuXG4gIGlmICghbXNUZWFtc0NsaWVudElkIHx8ICFtc1RlYW1zQ2xpZW50U2VjcmV0IHx8ICFyZWRpcmVjdFVyaSkge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oe1xuICAgICAgICBtZXNzYWdlOiAnTWljcm9zb2Z0IFRlYW1zIGVudmlyb25tZW50IHZhcmlhYmxlcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSk7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goXG4gICAgICAnaHR0cHM6Ly9sb2dpbi5taWNyb3NvZnRvbmxpbmUuY29tL2NvbW1vbi9vYXV0aDIvdjIuMC90b2tlbicsXG4gICAgICB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgICB9LFxuICAgICAgICBib2R5OiBuZXcgVVJMU2VhcmNoUGFyYW1zKHtcbiAgICAgICAgICBjbGllbnRfaWQ6IG1zVGVhbXNDbGllbnRJZCxcbiAgICAgICAgICBjbGllbnRfc2VjcmV0OiBtc1RlYW1zQ2xpZW50U2VjcmV0LFxuICAgICAgICAgIGNvZGU6IGNvZGUgYXMgc3RyaW5nLFxuICAgICAgICAgIHJlZGlyZWN0X3VyaTogcmVkaXJlY3RVcmksXG4gICAgICAgICAgZ3JhbnRfdHlwZTogJ2F1dGhvcml6YXRpb25fY29kZScsXG4gICAgICAgICAgc2NvcGU6ICdvZmZsaW5lX2FjY2VzcyBVc2VyLlJlYWQgTWFpbC5SZWFkV3JpdGUgQ2FsZW5kYXJzLlJlYWRXcml0ZScsXG4gICAgICAgIH0pLFxuICAgICAgfVxuICAgICk7XG5cbiAgICBjb25zdCBkYXRhID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuXG4gICAgaWYgKHJlc3BvbnNlLm9rKSB7XG4gICAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGRhdGEuYWNjZXNzX3Rva2VuO1xuICAgICAgY29uc3QgcmVmcmVzaFRva2VuID0gZGF0YS5yZWZyZXNoX3Rva2VuO1xuICAgICAgY29uc3QgZXhwaXJlc0luID0gZGF0YS5leHBpcmVzX2luO1xuICAgICAgY29uc3QgZXhwaXJlc0F0ID0gbmV3IERhdGUoRGF0ZS5ub3coKSArIGV4cGlyZXNJbiAqIDEwMDApLnRvSVNPU3RyaW5nKCk7XG5cbiAgICAgIC8vIFNhdmUgdGhlIHRva2VucyB0byB0aGUgdXNlcl90b2tlbnMgdGFibGVcbiAgICAgIGNvbnN0IG11dGF0aW9uID0gYFxuICAgICAgICAgICAgICAgIG11dGF0aW9uIEluc2VydFVzZXJUb2tlbigkdXNlcklkOiBTdHJpbmchLCAkc2VydmljZTogU3RyaW5nISwgJGFjY2Vzc1Rva2VuOiBTdHJpbmchLCAkcmVmcmVzaFRva2VuOiBTdHJpbmcsICRleHBpcmVzQXQ6IHRpbWVzdGFtcHR6ISkge1xuICAgICAgICAgICAgICAgICAgICBpbnNlcnRfdXNlcl90b2tlbnNfb25lKG9iamVjdDoge3VzZXJfaWQ6ICR1c2VySWQsIHNlcnZpY2U6ICRzZXJ2aWNlLCBhY2Nlc3NfdG9rZW46ICRhY2Nlc3NUb2tlbiwgcmVmcmVzaF90b2tlbjogJHJlZnJlc2hUb2tlbiwgZXhwaXJlc19hdDogJGV4cGlyZXNBdH0pIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICBgO1xuICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICB1c2VySWQsXG4gICAgICAgIHNlcnZpY2U6ICdtc3RlYW1zJyxcbiAgICAgICAgYWNjZXNzVG9rZW4sXG4gICAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgICAgZXhwaXJlc0F0LFxuICAgICAgfTtcbiAgICAgIGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnkobXV0YXRpb24sIHZhcmlhYmxlcywgJ0luc2VydFVzZXJUb2tlbicsIHVzZXJJZCk7XG5cbiAgICAgIHJldHVybiByZXMucmVkaXJlY3QoJy9TZXR0aW5ncy9Vc2VyVmlld1NldHRpbmdzJyk7XG4gICAgfSBlbHNlIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBtZXNzYWdlOiBgTWljcm9zb2Z0IFRlYW1zIE9BdXRoIGVycm9yOiAke2RhdGEuZXJyb3JfZGVzY3JpcHRpb259YCxcbiAgICAgICAgfSk7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGR1cmluZyBNaWNyb3NvZnQgVGVhbXMgT0F1dGggY2FsbGJhY2s6JywgZXJyb3IpO1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oeyBtZXNzYWdlOiAnRmFpbGVkIHRvIGNvbXBsZXRlIE1pY3Jvc29mdCBUZWFtcyBPQXV0aCBmbG93JyB9KTtcbiAgfVxufVxuIl19
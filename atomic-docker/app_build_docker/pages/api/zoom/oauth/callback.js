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
    const zoomClientId = process.env.ZOOM_CLIENT_ID;
    const zoomClientSecret = process.env.ZOOM_CLIENT_SECRET;
    const redirectUri = process.env.ZOOM_REDIRECT_URI;
    if (!zoomClientId || !zoomClientSecret || !redirectUri) {
        return res
            .status(500)
            .json({ message: 'Zoom environment variables not configured.' });
    }
    try {
        const response = await fetch('https://zoom.us/oauth/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                Authorization: `Basic ${Buffer.from(`${zoomClientId}:${zoomClientSecret}`).toString('base64')}`,
            },
            body: new URLSearchParams({
                grant_type: 'authorization_code',
                code: code,
                redirect_uri: redirectUri,
            }),
        });
        const data = await response.json();
        if (response.ok) {
            const accessToken = data.access_token;
            const refreshToken = data.refresh_token;
            // Save the tokens to the user_tokens table
            const mutation = `
                mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!, $refreshToken: String) {
                    insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken, refresh_token: $refreshToken}) {
                        id
                    }
                }
            `;
            const variables = {
                userId,
                service: 'zoom',
                accessToken,
                refreshToken,
            };
            await (0, graphqlClient_1.executeGraphQLQuery)(mutation, variables, 'InsertUserToken', userId);
            return res.redirect('/Settings/UserViewSettings');
        }
        else {
            return res
                .status(500)
                .json({ message: `Zoom OAuth error: ${data.reason}` });
        }
    }
    catch (error) {
        console.error('Error during Zoom OAuth callback:', error);
        return res
            .status(500)
            .json({ message: 'Failed to complete Zoom OAuth flow' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUtBLDBCQTRFQztBQWhGRCxvREFBcUQ7QUFFckQsd0ZBQTJGO0FBRTVFLEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLElBQUksT0FBeUIsQ0FBQztJQUM5QixJQUFJLENBQUM7UUFDSCxPQUFPLEdBQUcsTUFBTSxJQUFBLG1CQUFVLEVBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRTtZQUNuQyw2QkFBNkIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxFQUFFO1NBQ3hDLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLEdBQUcsRUFBRSxDQUFDO1FBQ2IsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxjQUFjLEVBQUUsQ0FBQyxDQUFDO0lBQzNELENBQUM7SUFFRCxNQUFNLE1BQU0sR0FBRyxPQUFPLENBQUMsU0FBUyxFQUFFLENBQUM7SUFDbkMsTUFBTSxFQUFFLElBQUksRUFBRSxLQUFLLEVBQUUsR0FBRyxHQUFHLENBQUMsS0FBSyxDQUFDO0lBRWxDLGdFQUFnRTtJQUVoRSxNQUFNLFlBQVksR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWMsQ0FBQztJQUNoRCxNQUFNLGdCQUFnQixHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsa0JBQWtCLENBQUM7SUFDeEQsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxpQkFBaUIsQ0FBQztJQUVsRCxJQUFJLENBQUMsWUFBWSxJQUFJLENBQUMsZ0JBQWdCLElBQUksQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUN2RCxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLDRDQUE0QyxFQUFFLENBQUMsQ0FBQztJQUNyRSxDQUFDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxLQUFLLENBQUMsNkJBQTZCLEVBQUU7WUFDMUQsTUFBTSxFQUFFLE1BQU07WUFDZCxPQUFPLEVBQUU7Z0JBQ1AsY0FBYyxFQUFFLG1DQUFtQztnQkFDbkQsYUFBYSxFQUFFLFNBQVMsTUFBTSxDQUFDLElBQUksQ0FBQyxHQUFHLFlBQVksSUFBSSxnQkFBZ0IsRUFBRSxDQUFDLENBQUMsUUFBUSxDQUFDLFFBQVEsQ0FBQyxFQUFFO2FBQ2hHO1lBQ0QsSUFBSSxFQUFFLElBQUksZUFBZSxDQUFDO2dCQUN4QixVQUFVLEVBQUUsb0JBQW9CO2dCQUNoQyxJQUFJLEVBQUUsSUFBYztnQkFDcEIsWUFBWSxFQUFFLFdBQVc7YUFDMUIsQ0FBQztTQUNILENBQUMsQ0FBQztRQUVILE1BQU0sSUFBSSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1FBRW5DLElBQUksUUFBUSxDQUFDLEVBQUUsRUFBRSxDQUFDO1lBQ2hCLE1BQU0sV0FBVyxHQUFHLElBQUksQ0FBQyxZQUFZLENBQUM7WUFDdEMsTUFBTSxZQUFZLEdBQUcsSUFBSSxDQUFDLGFBQWEsQ0FBQztZQUV4QywyQ0FBMkM7WUFDM0MsTUFBTSxRQUFRLEdBQUc7Ozs7OzthQU1WLENBQUM7WUFDUixNQUFNLFNBQVMsR0FBRztnQkFDaEIsTUFBTTtnQkFDTixPQUFPLEVBQUUsTUFBTTtnQkFDZixXQUFXO2dCQUNYLFlBQVk7YUFDYixDQUFDO1lBQ0YsTUFBTSxJQUFBLG1DQUFtQixFQUFDLFFBQVEsRUFBRSxTQUFTLEVBQUUsaUJBQWlCLEVBQUUsTUFBTSxDQUFDLENBQUM7WUFFMUUsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUFDLDRCQUE0QixDQUFDLENBQUM7UUFDcEQsQ0FBQzthQUFNLENBQUM7WUFDTixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUscUJBQXFCLElBQUksQ0FBQyxNQUFNLEVBQUUsRUFBRSxDQUFDLENBQUM7UUFDM0QsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyxtQ0FBbUMsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUMxRCxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLG9DQUFvQyxFQUFFLENBQUMsQ0FBQztJQUM3RCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7IGdldFNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL25leHRqcyc7XG5pbXBvcnQgeyBTZXNzaW9uQ29udGFpbmVyIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgeyBleGVjdXRlR3JhcGhRTFF1ZXJ5IH0gZnJvbSAnLi4vLi4vLi4vLi4vLi4vcHJvamVjdC9mdW5jdGlvbnMvX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgbGV0IHNlc3Npb246IFNlc3Npb25Db250YWluZXI7XG4gIHRyeSB7XG4gICAgc2Vzc2lvbiA9IGF3YWl0IGdldFNlc3Npb24ocmVxLCByZXMsIHtcbiAgICAgIG92ZXJyaWRlR2xvYmFsQ2xhaW1WYWxpZGF0b3JzOiAoKSA9PiBbXSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZXJyKSB7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAxKS5qc29uKHsgbWVzc2FnZTogJ1VuYXV0aG9yaXplZCcgfSk7XG4gIH1cblxuICBjb25zdCB1c2VySWQgPSBzZXNzaW9uLmdldFVzZXJJZCgpO1xuICBjb25zdCB7IGNvZGUsIHN0YXRlIH0gPSByZXEucXVlcnk7XG5cbiAgLy8gSW4gYSByZWFsIGFwcCwgeW91IHNob3VsZCB2YWxpZGF0ZSB0aGUgJ3N0YXRlJyBwYXJhbWV0ZXIgaGVyZVxuXG4gIGNvbnN0IHpvb21DbGllbnRJZCA9IHByb2Nlc3MuZW52LlpPT01fQ0xJRU5UX0lEO1xuICBjb25zdCB6b29tQ2xpZW50U2VjcmV0ID0gcHJvY2Vzcy5lbnYuWk9PTV9DTElFTlRfU0VDUkVUO1xuICBjb25zdCByZWRpcmVjdFVyaSA9IHByb2Nlc3MuZW52LlpPT01fUkVESVJFQ1RfVVJJO1xuXG4gIGlmICghem9vbUNsaWVudElkIHx8ICF6b29tQ2xpZW50U2VjcmV0IHx8ICFyZWRpcmVjdFVyaSkge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oeyBtZXNzYWdlOiAnWm9vbSBlbnZpcm9ubWVudCB2YXJpYWJsZXMgbm90IGNvbmZpZ3VyZWQuJyB9KTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaCgnaHR0cHM6Ly96b29tLnVzL29hdXRoL3Rva2VuJywge1xuICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJhc2ljICR7QnVmZmVyLmZyb20oYCR7em9vbUNsaWVudElkfToke3pvb21DbGllbnRTZWNyZXR9YCkudG9TdHJpbmcoJ2Jhc2U2NCcpfWAsXG4gICAgICB9LFxuICAgICAgYm9keTogbmV3IFVSTFNlYXJjaFBhcmFtcyh7XG4gICAgICAgIGdyYW50X3R5cGU6ICdhdXRob3JpemF0aW9uX2NvZGUnLFxuICAgICAgICBjb2RlOiBjb2RlIGFzIHN0cmluZyxcbiAgICAgICAgcmVkaXJlY3RfdXJpOiByZWRpcmVjdFVyaSxcbiAgICAgIH0pLFxuICAgIH0pO1xuXG4gICAgY29uc3QgZGF0YSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcblxuICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgY29uc3QgYWNjZXNzVG9rZW4gPSBkYXRhLmFjY2Vzc190b2tlbjtcbiAgICAgIGNvbnN0IHJlZnJlc2hUb2tlbiA9IGRhdGEucmVmcmVzaF90b2tlbjtcblxuICAgICAgLy8gU2F2ZSB0aGUgdG9rZW5zIHRvIHRoZSB1c2VyX3Rva2VucyB0YWJsZVxuICAgICAgY29uc3QgbXV0YXRpb24gPSBgXG4gICAgICAgICAgICAgICAgbXV0YXRpb24gSW5zZXJ0VXNlclRva2VuKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlOiBTdHJpbmchLCAkYWNjZXNzVG9rZW46IFN0cmluZyEsICRyZWZyZXNoVG9rZW46IFN0cmluZykge1xuICAgICAgICAgICAgICAgICAgICBpbnNlcnRfdXNlcl90b2tlbnNfb25lKG9iamVjdDoge3VzZXJfaWQ6ICR1c2VySWQsIHNlcnZpY2U6ICRzZXJ2aWNlLCBhY2Nlc3NfdG9rZW46ICRhY2Nlc3NUb2tlbiwgcmVmcmVzaF90b2tlbjogJHJlZnJlc2hUb2tlbn0pIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICBgO1xuICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICB1c2VySWQsXG4gICAgICAgIHNlcnZpY2U6ICd6b29tJyxcbiAgICAgICAgYWNjZXNzVG9rZW4sXG4gICAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgIH07XG4gICAgICBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5KG11dGF0aW9uLCB2YXJpYWJsZXMsICdJbnNlcnRVc2VyVG9rZW4nLCB1c2VySWQpO1xuXG4gICAgICByZXR1cm4gcmVzLnJlZGlyZWN0KCcvU2V0dGluZ3MvVXNlclZpZXdTZXR0aW5ncycpO1xuICAgIH0gZWxzZSB7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgICAuanNvbih7IG1lc3NhZ2U6IGBab29tIE9BdXRoIGVycm9yOiAke2RhdGEucmVhc29ufWAgfSk7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGR1cmluZyBab29tIE9BdXRoIGNhbGxiYWNrOicsIGVycm9yKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgbWVzc2FnZTogJ0ZhaWxlZCB0byBjb21wbGV0ZSBab29tIE9BdXRoIGZsb3cnIH0pO1xuICB9XG59XG4iXX0=
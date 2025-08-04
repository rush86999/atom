"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const nextjs_1 = require("supertokens-node/nextjs");
const graphqlClient_1 = require("../../../../../project/functions/_libs/graphqlClient");
const pocket_api_1 = __importDefault(require("pocket-api"));
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
    const { code } = req.query;
    const consumerKey = process.env.POCKET_CONSUMER_KEY;
    if (!consumerKey) {
        return res
            .status(500)
            .json({ message: 'Pocket consumer key not configured.' });
    }
    const pocket = new pocket_api_1.default({ consumer_key: consumerKey });
    try {
        const { access_token } = await pocket.getAccessToken({
            request_token: code,
        });
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
            service: 'pocket',
            accessToken: access_token,
        };
        await (0, graphqlClient_1.executeGraphQLQuery)(mutation, variables, 'InsertUserToken', userId);
        return res.redirect('/Settings/UserViewSettings');
    }
    catch (error) {
        console.error('Error during Pocket OAuth callback:', error);
        return res
            .status(500)
            .json({ message: 'Failed to complete Pocket OAuth flow' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQU1BLDBCQW9EQztBQXpERCxvREFBcUQ7QUFFckQsd0ZBQTJGO0FBQzNGLDREQUFtQztBQUVwQixLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUFvQjtJQUVwQixJQUFJLE9BQXlCLENBQUM7SUFDOUIsSUFBSSxDQUFDO1FBQ0gsT0FBTyxHQUFHLE1BQU0sSUFBQSxtQkFBVSxFQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDbkMsNkJBQTZCLEVBQUUsR0FBRyxFQUFFLENBQUMsRUFBRTtTQUN4QyxDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxHQUFHLEVBQUUsQ0FBQztRQUNiLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsY0FBYyxFQUFFLENBQUMsQ0FBQztJQUMzRCxDQUFDO0lBRUQsTUFBTSxNQUFNLEdBQUcsT0FBTyxDQUFDLFNBQVMsRUFBRSxDQUFDO0lBQ25DLE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxHQUFHLENBQUMsS0FBSyxDQUFDO0lBRTNCLE1BQU0sV0FBVyxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsbUJBQW1CLENBQUM7SUFDcEQsSUFBSSxDQUFDLFdBQVcsRUFBRSxDQUFDO1FBQ2pCLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUscUNBQXFDLEVBQUUsQ0FBQyxDQUFDO0lBQzlELENBQUM7SUFFRCxNQUFNLE1BQU0sR0FBRyxJQUFJLG9CQUFTLENBQUMsRUFBRSxZQUFZLEVBQUUsV0FBVyxFQUFFLENBQUMsQ0FBQztJQUU1RCxJQUFJLENBQUM7UUFDSCxNQUFNLEVBQUUsWUFBWSxFQUFFLEdBQUcsTUFBTSxNQUFNLENBQUMsY0FBYyxDQUFDO1lBQ25ELGFBQWEsRUFBRSxJQUFjO1NBQzlCLENBQUMsQ0FBQztRQUVILDBDQUEwQztRQUMxQyxNQUFNLFFBQVEsR0FBRzs7Ozs7O1NBTVosQ0FBQztRQUNOLE1BQU0sU0FBUyxHQUFHO1lBQ2hCLE1BQU07WUFDTixPQUFPLEVBQUUsUUFBUTtZQUNqQixXQUFXLEVBQUUsWUFBWTtTQUMxQixDQUFDO1FBQ0YsTUFBTSxJQUFBLG1DQUFtQixFQUFDLFFBQVEsRUFBRSxTQUFTLEVBQUUsaUJBQWlCLEVBQUUsTUFBTSxDQUFDLENBQUM7UUFFMUUsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUFDLDRCQUE0QixDQUFDLENBQUM7SUFDcEQsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsS0FBSyxDQUFDLHFDQUFxQyxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQzVELE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsc0NBQXNDLEVBQUUsQ0FBQyxDQUFDO0lBQy9ELENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHsgZ2V0U2Vzc2lvbiB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvbmV4dGpzJztcbmltcG9ydCB7IFNlc3Npb25Db250YWluZXIgfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMUXVlcnkgfSBmcm9tICcuLi8uLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9fbGlicy9ncmFwaHFsQ2xpZW50JztcbmltcG9ydCBQb2NrZXRBUEkgZnJvbSAncG9ja2V0LWFwaSc7XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgbGV0IHNlc3Npb246IFNlc3Npb25Db250YWluZXI7XG4gIHRyeSB7XG4gICAgc2Vzc2lvbiA9IGF3YWl0IGdldFNlc3Npb24ocmVxLCByZXMsIHtcbiAgICAgIG92ZXJyaWRlR2xvYmFsQ2xhaW1WYWxpZGF0b3JzOiAoKSA9PiBbXSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZXJyKSB7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAxKS5qc29uKHsgbWVzc2FnZTogJ1VuYXV0aG9yaXplZCcgfSk7XG4gIH1cblxuICBjb25zdCB1c2VySWQgPSBzZXNzaW9uLmdldFVzZXJJZCgpO1xuICBjb25zdCB7IGNvZGUgfSA9IHJlcS5xdWVyeTtcblxuICBjb25zdCBjb25zdW1lcktleSA9IHByb2Nlc3MuZW52LlBPQ0tFVF9DT05TVU1FUl9LRVk7XG4gIGlmICghY29uc3VtZXJLZXkpIHtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgbWVzc2FnZTogJ1BvY2tldCBjb25zdW1lciBrZXkgbm90IGNvbmZpZ3VyZWQuJyB9KTtcbiAgfVxuXG4gIGNvbnN0IHBvY2tldCA9IG5ldyBQb2NrZXRBUEkoeyBjb25zdW1lcl9rZXk6IGNvbnN1bWVyS2V5IH0pO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgeyBhY2Nlc3NfdG9rZW4gfSA9IGF3YWl0IHBvY2tldC5nZXRBY2Nlc3NUb2tlbih7XG4gICAgICByZXF1ZXN0X3Rva2VuOiBjb2RlIGFzIHN0cmluZyxcbiAgICB9KTtcblxuICAgIC8vIFNhdmUgdGhlIHRva2VuIHRvIHRoZSB1c2VyX3Rva2VucyB0YWJsZVxuICAgIGNvbnN0IG11dGF0aW9uID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gSW5zZXJ0VXNlclRva2VuKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlOiBTdHJpbmchLCAkYWNjZXNzVG9rZW46IFN0cmluZyEpIHtcbiAgICAgICAgICAgICAgICBpbnNlcnRfdXNlcl90b2tlbnNfb25lKG9iamVjdDoge3VzZXJfaWQ6ICR1c2VySWQsIHNlcnZpY2U6ICRzZXJ2aWNlLCBhY2Nlc3NfdG9rZW46ICRhY2Nlc3NUb2tlbn0pIHtcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgc2VydmljZTogJ3BvY2tldCcsXG4gICAgICBhY2Nlc3NUb2tlbjogYWNjZXNzX3Rva2VuLFxuICAgIH07XG4gICAgYXdhaXQgZXhlY3V0ZUdyYXBoUUxRdWVyeShtdXRhdGlvbiwgdmFyaWFibGVzLCAnSW5zZXJ0VXNlclRva2VuJywgdXNlcklkKTtcblxuICAgIHJldHVybiByZXMucmVkaXJlY3QoJy9TZXR0aW5ncy9Vc2VyVmlld1NldHRpbmdzJyk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgZHVyaW5nIFBvY2tldCBPQXV0aCBjYWxsYmFjazonLCBlcnJvcik7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7IG1lc3NhZ2U6ICdGYWlsZWQgdG8gY29tcGxldGUgUG9ja2V0IE9BdXRoIGZsb3cnIH0pO1xuICB9XG59XG4iXX0=
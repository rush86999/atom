"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const cors_1 = __importDefault(require("cors"));
const api_backend_helper_1 = require("@lib/api-backend-helper");
const nextjs_1 = require("supertokens-node/nextjs");
const express_1 = require("supertokens-node/recipe/session/framework/express");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../../../config/backendConfig"); // Adjusted path
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
// Initializing the cors middleware
const cors = (0, cors_1.default)({
    methods: ['POST', 'GET', 'HEAD'],
    // Allow all origins for simplicity in dev, or specify your frontend URL
    // origin: process.env.NODE_ENV === 'production' ? ["https://atomiclife.app", /\.atomiclife\.app$/] : "*",
});
// Helper method to wait for a middleware to execute before continuing
function runMiddleware(req, res, fn) {
    return new Promise((resolve, reject) => {
        fn(req, res, (result) => {
            if (result instanceof Error) {
                return reject(result);
            }
            return resolve(result);
        });
    });
}
async function handler(req, res) {
    // Changed req: any, res: any to NextApiRequest, NextApiResponse
    try {
        await runMiddleware(req, res, cors);
        await (0, nextjs_1.superTokensNextWrapper)(async (next) => {
            // Added type assertion for req and res as per SuperTokens examples for Next.js
            return await (0, express_1.verifySession)()(req, res, next);
        }, req, res);
        const userId = req.session?.getUserId(); // Use optional chaining and get userId
        if (!userId) {
            // It's generally better to return a 401 Unauthorized status
            // or redirect to a login page if this is directly accessed by a user's browser.
            // For an API, 401 is more appropriate.
            return res.status(401).json({ message: 'Authentication required.' });
        }
        // Pass the userId as state to be used in the callback
        const authorizationUrl = (0, api_backend_helper_1.generateGoogleAuthUrl)(userId);
        return res.redirect(authorizationUrl);
    }
    catch (e) {
        // Changed type of e to unknown for better error handling
        console.error('Error in Google OAuth initiation:', e); // console.error for errors
        const errorMessage = e instanceof Error
            ? e.message
            : 'Internal server error during OAuth initiation.';
        // It's good practice to avoid sending detailed internal error messages to the client.
        return res
            .status(500)
            .json({
            statusCode: 500,
            message: 'Failed to initiate Google authentication.',
        });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5pdGlhdGUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbml0aWF0ZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQW1DQSwwQkE2Q0M7QUE5RUQsZ0RBQXdCO0FBQ3hCLGdFQUFnRTtBQUVoRSxvREFBaUU7QUFDakUsK0VBQWtGO0FBQ2xGLHdFQUEyQztBQUMzQyx1RUFBb0UsQ0FBQyxnQkFBZ0I7QUFFckYsMEJBQVcsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQztBQUVsQyxtQ0FBbUM7QUFDbkMsTUFBTSxJQUFJLEdBQUcsSUFBQSxjQUFJLEVBQUM7SUFDaEIsT0FBTyxFQUFFLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxNQUFNLENBQUM7SUFDaEMsd0VBQXdFO0lBQ3hFLDBHQUEwRztDQUMzRyxDQUFDLENBQUM7QUFFSCxzRUFBc0U7QUFDdEUsU0FBUyxhQUFhLENBQ3BCLEdBQW1CLEVBQ25CLEdBQW9CLEVBQ3BCLEVBQVk7SUFFWixPQUFPLElBQUksT0FBTyxDQUFDLENBQUMsT0FBTyxFQUFFLE1BQU0sRUFBRSxFQUFFO1FBQ3JDLEVBQUUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFLENBQUMsTUFBVyxFQUFFLEVBQUU7WUFDM0IsSUFBSSxNQUFNLFlBQVksS0FBSyxFQUFFLENBQUM7Z0JBQzVCLE9BQU8sTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDO1lBQ3hCLENBQUM7WUFDRCxPQUFPLE9BQU8sQ0FBQyxNQUFNLENBQUMsQ0FBQztRQUN6QixDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQztBQUVjLEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLGdFQUFnRTtJQUNoRSxJQUFJLENBQUM7UUFDSCxNQUFNLGFBQWEsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFLElBQUksQ0FBQyxDQUFDO1FBRXBDLE1BQU0sSUFBQSwrQkFBc0IsRUFDMUIsS0FBSyxFQUFFLElBQUksRUFBRSxFQUFFO1lBQ2IsK0VBQStFO1lBQy9FLE9BQU8sTUFBTSxJQUFBLHVCQUFhLEdBQUUsQ0FBQyxHQUFVLEVBQUUsR0FBVSxFQUFFLElBQUksQ0FBQyxDQUFDO1FBQzdELENBQUMsRUFDRCxHQUFHLEVBQ0gsR0FBRyxDQUNKLENBQUM7UUFFRixNQUFNLE1BQU0sR0FBRyxHQUFHLENBQUMsT0FBTyxFQUFFLFNBQVMsRUFBRSxDQUFDLENBQUMsdUNBQXVDO1FBRWhGLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUNaLDREQUE0RDtZQUM1RCxnRkFBZ0Y7WUFDaEYsdUNBQXVDO1lBQ3ZDLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsMEJBQTBCLEVBQUUsQ0FBQyxDQUFDO1FBQ3ZFLENBQUM7UUFFRCxzREFBc0Q7UUFDdEQsTUFBTSxnQkFBZ0IsR0FBRyxJQUFBLDBDQUFxQixFQUFDLE1BQU0sQ0FBQyxDQUFDO1FBRXZELE9BQU8sR0FBRyxDQUFDLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO0lBQ3hDLENBQUM7SUFBQyxPQUFPLENBQVUsRUFBRSxDQUFDO1FBQ3BCLHlEQUF5RDtRQUN6RCxPQUFPLENBQUMsS0FBSyxDQUFDLG1DQUFtQyxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsMkJBQTJCO1FBQ2xGLE1BQU0sWUFBWSxHQUNoQixDQUFDLFlBQVksS0FBSztZQUNoQixDQUFDLENBQUMsQ0FBQyxDQUFDLE9BQU87WUFDWCxDQUFDLENBQUMsZ0RBQWdELENBQUM7UUFDdkQsc0ZBQXNGO1FBQ3RGLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUM7WUFDSixVQUFVLEVBQUUsR0FBRztZQUNmLE9BQU8sRUFBRSwyQ0FBMkM7U0FDckQsQ0FBQyxDQUFDO0lBQ1AsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBxcyBmcm9tICdxcyc7XG5pbXBvcnQgQ29ycyBmcm9tICdjb3JzJztcbmltcG9ydCB7IGdlbmVyYXRlR29vZ2xlQXV0aFVybCB9IGZyb20gJ0BsaWIvYXBpLWJhY2tlbmQtaGVscGVyJztcblxuaW1wb3J0IHsgc3VwZXJUb2tlbnNOZXh0V3JhcHBlciB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvbmV4dGpzJztcbmltcG9ydCB7IHZlcmlmeVNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uL2ZyYW1ld29yay9leHByZXNzJztcbmltcG9ydCBzdXBlcnRva2VucyBmcm9tICdzdXBlcnRva2Vucy1ub2RlJztcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi8uLi8uLi8uLi9jb25maWcvYmFja2VuZENvbmZpZyc7IC8vIEFkanVzdGVkIHBhdGhcblxuc3VwZXJ0b2tlbnMuaW5pdChiYWNrZW5kQ29uZmlnKCkpO1xuXG4vLyBJbml0aWFsaXppbmcgdGhlIGNvcnMgbWlkZGxld2FyZVxuY29uc3QgY29ycyA9IENvcnMoe1xuICBtZXRob2RzOiBbJ1BPU1QnLCAnR0VUJywgJ0hFQUQnXSxcbiAgLy8gQWxsb3cgYWxsIG9yaWdpbnMgZm9yIHNpbXBsaWNpdHkgaW4gZGV2LCBvciBzcGVjaWZ5IHlvdXIgZnJvbnRlbmQgVVJMXG4gIC8vIG9yaWdpbjogcHJvY2Vzcy5lbnYuTk9ERV9FTlYgPT09ICdwcm9kdWN0aW9uJyA/IFtcImh0dHBzOi8vYXRvbWljbGlmZS5hcHBcIiwgL1xcLmF0b21pY2xpZmVcXC5hcHAkL10gOiBcIipcIixcbn0pO1xuXG4vLyBIZWxwZXIgbWV0aG9kIHRvIHdhaXQgZm9yIGEgbWlkZGxld2FyZSB0byBleGVjdXRlIGJlZm9yZSBjb250aW51aW5nXG5mdW5jdGlvbiBydW5NaWRkbGV3YXJlKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZSxcbiAgZm46IEZ1bmN0aW9uXG4pIHtcbiAgcmV0dXJuIG5ldyBQcm9taXNlKChyZXNvbHZlLCByZWplY3QpID0+IHtcbiAgICBmbihyZXEsIHJlcywgKHJlc3VsdDogYW55KSA9PiB7XG4gICAgICBpZiAocmVzdWx0IGluc3RhbmNlb2YgRXJyb3IpIHtcbiAgICAgICAgcmV0dXJuIHJlamVjdChyZXN1bHQpO1xuICAgICAgfVxuICAgICAgcmV0dXJuIHJlc29sdmUocmVzdWx0KTtcbiAgICB9KTtcbiAgfSk7XG59XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgLy8gQ2hhbmdlZCByZXE6IGFueSwgcmVzOiBhbnkgdG8gTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZVxuICB0cnkge1xuICAgIGF3YWl0IHJ1bk1pZGRsZXdhcmUocmVxLCByZXMsIGNvcnMpO1xuXG4gICAgYXdhaXQgc3VwZXJUb2tlbnNOZXh0V3JhcHBlcihcbiAgICAgIGFzeW5jIChuZXh0KSA9PiB7XG4gICAgICAgIC8vIEFkZGVkIHR5cGUgYXNzZXJ0aW9uIGZvciByZXEgYW5kIHJlcyBhcyBwZXIgU3VwZXJUb2tlbnMgZXhhbXBsZXMgZm9yIE5leHQuanNcbiAgICAgICAgcmV0dXJuIGF3YWl0IHZlcmlmeVNlc3Npb24oKShyZXEgYXMgYW55LCByZXMgYXMgYW55LCBuZXh0KTtcbiAgICAgIH0sXG4gICAgICByZXEsXG4gICAgICByZXNcbiAgICApO1xuXG4gICAgY29uc3QgdXNlcklkID0gcmVxLnNlc3Npb24/LmdldFVzZXJJZCgpOyAvLyBVc2Ugb3B0aW9uYWwgY2hhaW5pbmcgYW5kIGdldCB1c2VySWRcblxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICAvLyBJdCdzIGdlbmVyYWxseSBiZXR0ZXIgdG8gcmV0dXJuIGEgNDAxIFVuYXV0aG9yaXplZCBzdGF0dXNcbiAgICAgIC8vIG9yIHJlZGlyZWN0IHRvIGEgbG9naW4gcGFnZSBpZiB0aGlzIGlzIGRpcmVjdGx5IGFjY2Vzc2VkIGJ5IGEgdXNlcidzIGJyb3dzZXIuXG4gICAgICAvLyBGb3IgYW4gQVBJLCA0MDEgaXMgbW9yZSBhcHByb3ByaWF0ZS5cbiAgICAgIHJldHVybiByZXMuc3RhdHVzKDQwMSkuanNvbih7IG1lc3NhZ2U6ICdBdXRoZW50aWNhdGlvbiByZXF1aXJlZC4nIH0pO1xuICAgIH1cblxuICAgIC8vIFBhc3MgdGhlIHVzZXJJZCBhcyBzdGF0ZSB0byBiZSB1c2VkIGluIHRoZSBjYWxsYmFja1xuICAgIGNvbnN0IGF1dGhvcml6YXRpb25VcmwgPSBnZW5lcmF0ZUdvb2dsZUF1dGhVcmwodXNlcklkKTtcblxuICAgIHJldHVybiByZXMucmVkaXJlY3QoYXV0aG9yaXphdGlvblVybCk7XG4gIH0gY2F0Y2ggKGU6IHVua25vd24pIHtcbiAgICAvLyBDaGFuZ2VkIHR5cGUgb2YgZSB0byB1bmtub3duIGZvciBiZXR0ZXIgZXJyb3IgaGFuZGxpbmdcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBpbiBHb29nbGUgT0F1dGggaW5pdGlhdGlvbjonLCBlKTsgLy8gY29uc29sZS5lcnJvciBmb3IgZXJyb3JzXG4gICAgY29uc3QgZXJyb3JNZXNzYWdlID1cbiAgICAgIGUgaW5zdGFuY2VvZiBFcnJvclxuICAgICAgICA/IGUubWVzc2FnZVxuICAgICAgICA6ICdJbnRlcm5hbCBzZXJ2ZXIgZXJyb3IgZHVyaW5nIE9BdXRoIGluaXRpYXRpb24uJztcbiAgICAvLyBJdCdzIGdvb2QgcHJhY3RpY2UgdG8gYXZvaWQgc2VuZGluZyBkZXRhaWxlZCBpbnRlcm5hbCBlcnJvciBtZXNzYWdlcyB0byB0aGUgY2xpZW50LlxuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oe1xuICAgICAgICBzdGF0dXNDb2RlOiA1MDAsXG4gICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gaW5pdGlhdGUgR29vZ2xlIGF1dGhlbnRpY2F0aW9uLicsXG4gICAgICB9KTtcbiAgfVxufVxuIl19
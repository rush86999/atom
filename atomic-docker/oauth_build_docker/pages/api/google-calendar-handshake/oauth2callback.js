"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const qs_1 = __importDefault(require("qs"));
const cors_1 = __importDefault(require("cors"));
const constants_1 = require("@lib/constants");
const api_helper_1 = require("@lib/api-helper");
// Initializing the cors middleware
// You can read more about the available options here: https://github.com/expressjs/cors#configuration-options
const cors = (0, cors_1.default)({
    methods: ['POST', 'GET', 'HEAD'],
});
// Helper method to wait for a middleware to execute before continuing
// And to throw an error when an error happens in a middleware
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
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../../../config/backendConfig");
const session_1 = __importDefault(require("supertokens-node/recipe/session"));
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
async function handler(req, res) {
    try {
        // Run the middleware
        await runMiddleware(req, res, cors);
        const session = await session_1.default.getSession(req, res, {
            overrideGlobalClaimValidators: async function () {
                return [];
            },
        });
        const userId = session.getUserId();
        const thisUrl = new URL(req.url, `https://${req.headers.host}`);
        if (thisUrl.searchParams.get('error')) {
            const error = thisUrl.searchParams.get('error');
            // pass the error to handshakUrl
            if (error === 'access_denied') {
                return res.redirect(`${constants_1.handshakeUrl}?${qs_1.default.stringify({ error })}`);
            }
        }
        // example: https://oauth2.example.com/auth?code=4/P7q7W91a-oMsCeLvIaQm6bTrgtp7
        const code = thisUrl.searchParams.get('code');
        // console.log(code, ' code')
        const stateString = thisUrl.searchParams.get('state');
        const meetingId = stateString?.split('#')?.[0];
        console.log(meetingId, ' meetingId');
        const attendeeId = stateString?.split('#')?.[1];
        console.log(attendeeId, ' attendeeId');
        const tokens = await (0, api_helper_1.exchangeCodeForTokens)(code, userId);
        // console.log(tokens, ' tokens')
        return res.redirect(`${constants_1.handshakeUrl}/meeting/callback-calendar-sync?${qs_1.default.stringify({ meetingId, attendeeId })}`);
    }
    catch (e) {
        console.log(e, ' unable to auth');
        if (e.type === session_1.default.Error.TRY_REFRESH_TOKEN) {
            return res.status(401).send('Refresh token expired');
        }
        else if (e.type === session_1.default.Error.UNAUTHORISED) {
            return res.status(401).send('Unauthorized');
        }
        return res.status(500).send('Internal server error');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoib2F1dGgyY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJvYXV0aDJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQW9DQSwwQkF5REM7QUE1RkQsNENBQW9CO0FBQ3BCLGdEQUF3QjtBQUN4Qiw4Q0FBOEM7QUFDOUMsZ0RBQXdEO0FBRXhELG1DQUFtQztBQUNuQyw4R0FBOEc7QUFDOUcsTUFBTSxJQUFJLEdBQUcsSUFBQSxjQUFJLEVBQUM7SUFDaEIsT0FBTyxFQUFFLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxNQUFNLENBQUM7Q0FDakMsQ0FBQyxDQUFDO0FBRUgsc0VBQXNFO0FBQ3RFLDhEQUE4RDtBQUM5RCxTQUFTLGFBQWEsQ0FDcEIsR0FBbUIsRUFDbkIsR0FBb0IsRUFDcEIsRUFBWTtJQUVaLE9BQU8sSUFBSSxPQUFPLENBQUMsQ0FBQyxPQUFPLEVBQUUsTUFBTSxFQUFFLEVBQUU7UUFDckMsRUFBRSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUUsQ0FBQyxNQUFXLEVBQUUsRUFBRTtZQUMzQixJQUFJLE1BQU0sWUFBWSxLQUFLLEVBQUUsQ0FBQztnQkFDNUIsT0FBTyxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUM7WUFDeEIsQ0FBQztZQUVELE9BQU8sT0FBTyxDQUFDLE1BQU0sQ0FBQyxDQUFDO1FBQ3pCLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDO0FBRUQsd0VBQStDO0FBQy9DLHVFQUFvRTtBQUNwRSw4RUFBc0Q7QUFFdEQsMEJBQWUsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQztBQUV2QixLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUFvQjtJQUVwQixJQUFJLENBQUM7UUFDSCxxQkFBcUI7UUFDckIsTUFBTSxhQUFhLENBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRSxJQUFJLENBQUMsQ0FBQztRQUVwQyxNQUFNLE9BQU8sR0FBRyxNQUFNLGlCQUFPLENBQUMsVUFBVSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDakQsNkJBQTZCLEVBQUUsS0FBSztnQkFDbEMsT0FBTyxFQUFFLENBQUM7WUFDWixDQUFDO1NBQ0YsQ0FBQyxDQUFDO1FBQ0gsTUFBTSxNQUFNLEdBQUcsT0FBTyxDQUFDLFNBQVMsRUFBRSxDQUFDO1FBRW5DLE1BQU0sT0FBTyxHQUFHLElBQUksR0FBRyxDQUFDLEdBQUcsQ0FBQyxHQUFhLEVBQUUsV0FBVyxHQUFHLENBQUMsT0FBTyxDQUFDLElBQUksRUFBRSxDQUFDLENBQUM7UUFFMUUsSUFBSSxPQUFPLENBQUMsWUFBWSxDQUFDLEdBQUcsQ0FBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1lBQ3RDLE1BQU0sS0FBSyxHQUFHLE9BQU8sQ0FBQyxZQUFZLENBQUMsR0FBRyxDQUFDLE9BQU8sQ0FBVyxDQUFDO1lBRTFELGdDQUFnQztZQUNoQyxJQUFJLEtBQUssS0FBSyxlQUFlLEVBQUUsQ0FBQztnQkFDOUIsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUFDLEdBQUcsd0JBQVksSUFBSSxZQUFFLENBQUMsU0FBUyxDQUFDLEVBQUUsS0FBSyxFQUFFLENBQUMsRUFBRSxDQUFDLENBQUM7WUFDcEUsQ0FBQztRQUNILENBQUM7UUFFRCwrRUFBK0U7UUFFL0UsTUFBTSxJQUFJLEdBQUcsT0FBTyxDQUFDLFlBQVksQ0FBQyxHQUFHLENBQUMsTUFBTSxDQUFXLENBQUM7UUFDeEQsNkJBQTZCO1FBRTdCLE1BQU0sV0FBVyxHQUFHLE9BQU8sQ0FBQyxZQUFZLENBQUMsR0FBRyxDQUFDLE9BQU8sQ0FBVyxDQUFDO1FBRWhFLE1BQU0sU0FBUyxHQUFHLFdBQVcsRUFBRSxLQUFLLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUUvQyxPQUFPLENBQUMsR0FBRyxDQUFDLFNBQVMsRUFBRSxZQUFZLENBQUMsQ0FBQztRQUVyQyxNQUFNLFVBQVUsR0FBRyxXQUFXLEVBQUUsS0FBSyxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFFaEQsT0FBTyxDQUFDLEdBQUcsQ0FBQyxVQUFVLEVBQUUsYUFBYSxDQUFDLENBQUM7UUFFdkMsTUFBTSxNQUFNLEdBQUcsTUFBTSxJQUFBLGtDQUFxQixFQUFDLElBQWMsRUFBRSxNQUFNLENBQUMsQ0FBQztRQUVuRSxpQ0FBaUM7UUFFakMsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUNqQixHQUFHLHdCQUFZLG1DQUFtQyxZQUFFLENBQUMsU0FBUyxDQUFDLEVBQUUsU0FBUyxFQUFFLFVBQVUsRUFBRSxDQUFDLEVBQUUsQ0FDNUYsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsaUJBQWlCLENBQUMsQ0FBQztRQUNsQyxJQUFJLENBQUMsQ0FBQyxJQUFJLEtBQUssaUJBQU8sQ0FBQyxLQUFLLENBQUMsaUJBQWlCLEVBQUUsQ0FBQztZQUMvQyxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLHVCQUF1QixDQUFDLENBQUM7UUFDdkQsQ0FBQzthQUFNLElBQUksQ0FBQyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxZQUFZLEVBQUUsQ0FBQztZQUNqRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLGNBQWMsQ0FBQyxDQUFDO1FBQzlDLENBQUM7UUFDRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLHVCQUF1QixDQUFDLENBQUM7SUFDdkQsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBxcyBmcm9tICdxcyc7XG5pbXBvcnQgQ29ycyBmcm9tICdjb3JzJztcbmltcG9ydCB7IGhhbmRzaGFrZVVybCB9IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcbmltcG9ydCB7IGV4Y2hhbmdlQ29kZUZvclRva2VucyB9IGZyb20gJ0BsaWIvYXBpLWhlbHBlcic7XG5cbi8vIEluaXRpYWxpemluZyB0aGUgY29ycyBtaWRkbGV3YXJlXG4vLyBZb3UgY2FuIHJlYWQgbW9yZSBhYm91dCB0aGUgYXZhaWxhYmxlIG9wdGlvbnMgaGVyZTogaHR0cHM6Ly9naXRodWIuY29tL2V4cHJlc3Nqcy9jb3JzI2NvbmZpZ3VyYXRpb24tb3B0aW9uc1xuY29uc3QgY29ycyA9IENvcnMoe1xuICBtZXRob2RzOiBbJ1BPU1QnLCAnR0VUJywgJ0hFQUQnXSxcbn0pO1xuXG4vLyBIZWxwZXIgbWV0aG9kIHRvIHdhaXQgZm9yIGEgbWlkZGxld2FyZSB0byBleGVjdXRlIGJlZm9yZSBjb250aW51aW5nXG4vLyBBbmQgdG8gdGhyb3cgYW4gZXJyb3Igd2hlbiBhbiBlcnJvciBoYXBwZW5zIGluIGEgbWlkZGxld2FyZVxuZnVuY3Rpb24gcnVuTWlkZGxld2FyZShcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2UsXG4gIGZuOiBGdW5jdGlvblxuKSB7XG4gIHJldHVybiBuZXcgUHJvbWlzZSgocmVzb2x2ZSwgcmVqZWN0KSA9PiB7XG4gICAgZm4ocmVxLCByZXMsIChyZXN1bHQ6IGFueSkgPT4ge1xuICAgICAgaWYgKHJlc3VsdCBpbnN0YW5jZW9mIEVycm9yKSB7XG4gICAgICAgIHJldHVybiByZWplY3QocmVzdWx0KTtcbiAgICAgIH1cblxuICAgICAgcmV0dXJuIHJlc29sdmUocmVzdWx0KTtcbiAgICB9KTtcbiAgfSk7XG59XG5cbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSc7XG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnLi4vLi4vLi4vLi4vLi4vY29uZmlnL2JhY2tlbmRDb25maWcnO1xuaW1wb3J0IFNlc3Npb24gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbic7XG5cbnN1cGVydG9rZW5zTm9kZS5pbml0KGJhY2tlbmRDb25maWcoKSk7XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgdHJ5IHtcbiAgICAvLyBSdW4gdGhlIG1pZGRsZXdhcmVcbiAgICBhd2FpdCBydW5NaWRkbGV3YXJlKHJlcSwgcmVzLCBjb3JzKTtcblxuICAgIGNvbnN0IHNlc3Npb24gPSBhd2FpdCBTZXNzaW9uLmdldFNlc3Npb24ocmVxLCByZXMsIHtcbiAgICAgIG92ZXJyaWRlR2xvYmFsQ2xhaW1WYWxpZGF0b3JzOiBhc3luYyBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiBbXTtcbiAgICAgIH0sXG4gICAgfSk7XG4gICAgY29uc3QgdXNlcklkID0gc2Vzc2lvbi5nZXRVc2VySWQoKTtcblxuICAgIGNvbnN0IHRoaXNVcmwgPSBuZXcgVVJMKHJlcS51cmwgYXMgc3RyaW5nLCBgaHR0cHM6Ly8ke3JlcS5oZWFkZXJzLmhvc3R9YCk7XG5cbiAgICBpZiAodGhpc1VybC5zZWFyY2hQYXJhbXMuZ2V0KCdlcnJvcicpKSB7XG4gICAgICBjb25zdCBlcnJvciA9IHRoaXNVcmwuc2VhcmNoUGFyYW1zLmdldCgnZXJyb3InKSBhcyBzdHJpbmc7XG5cbiAgICAgIC8vIHBhc3MgdGhlIGVycm9yIHRvIGhhbmRzaGFrVXJsXG4gICAgICBpZiAoZXJyb3IgPT09ICdhY2Nlc3NfZGVuaWVkJykge1xuICAgICAgICByZXR1cm4gcmVzLnJlZGlyZWN0KGAke2hhbmRzaGFrZVVybH0/JHtxcy5zdHJpbmdpZnkoeyBlcnJvciB9KX1gKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBleGFtcGxlOiBodHRwczovL29hdXRoMi5leGFtcGxlLmNvbS9hdXRoP2NvZGU9NC9QN3E3VzkxYS1vTXNDZUx2SWFRbTZiVHJndHA3XG5cbiAgICBjb25zdCBjb2RlID0gdGhpc1VybC5zZWFyY2hQYXJhbXMuZ2V0KCdjb2RlJykgYXMgc3RyaW5nO1xuICAgIC8vIGNvbnNvbGUubG9nKGNvZGUsICcgY29kZScpXG5cbiAgICBjb25zdCBzdGF0ZVN0cmluZyA9IHRoaXNVcmwuc2VhcmNoUGFyYW1zLmdldCgnc3RhdGUnKSBhcyBzdHJpbmc7XG5cbiAgICBjb25zdCBtZWV0aW5nSWQgPSBzdGF0ZVN0cmluZz8uc3BsaXQoJyMnKT8uWzBdO1xuXG4gICAgY29uc29sZS5sb2cobWVldGluZ0lkLCAnIG1lZXRpbmdJZCcpO1xuXG4gICAgY29uc3QgYXR0ZW5kZWVJZCA9IHN0YXRlU3RyaW5nPy5zcGxpdCgnIycpPy5bMV07XG5cbiAgICBjb25zb2xlLmxvZyhhdHRlbmRlZUlkLCAnIGF0dGVuZGVlSWQnKTtcblxuICAgIGNvbnN0IHRva2VucyA9IGF3YWl0IGV4Y2hhbmdlQ29kZUZvclRva2Vucyhjb2RlIGFzIHN0cmluZywgdXNlcklkKTtcblxuICAgIC8vIGNvbnNvbGUubG9nKHRva2VucywgJyB0b2tlbnMnKVxuXG4gICAgcmV0dXJuIHJlcy5yZWRpcmVjdChcbiAgICAgIGAke2hhbmRzaGFrZVVybH0vbWVldGluZy9jYWxsYmFjay1jYWxlbmRhci1zeW5jPyR7cXMuc3RyaW5naWZ5KHsgbWVldGluZ0lkLCBhdHRlbmRlZUlkIH0pfWBcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gYXV0aCcpO1xuICAgIGlmIChlLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgIHJldHVybiByZXMuc3RhdHVzKDQwMSkuc2VuZCgnUmVmcmVzaCB0b2tlbiBleHBpcmVkJyk7XG4gICAgfSBlbHNlIGlmIChlLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVU5BVVRIT1JJU0VEKSB7XG4gICAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDEpLnNlbmQoJ1VuYXV0aG9yaXplZCcpO1xuICAgIH1cbiAgICByZXR1cm4gcmVzLnN0YXR1cyg1MDApLnNlbmQoJ0ludGVybmFsIHNlcnZlciBlcnJvcicpO1xuICB9XG59XG4iXX0=
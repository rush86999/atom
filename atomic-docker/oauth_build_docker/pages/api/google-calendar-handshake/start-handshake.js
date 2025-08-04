"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const cors_1 = __importDefault(require("cors"));
const api_helper_1 = require("@lib/api-helper");
// Initializing the cors middleware
// You can read more about the available options here: https://github.com/expressjs/cors#configuration-options
const cors = (0, cors_1.default)({
    methods: ['POST', 'GET', 'HEAD'],
    origin: ['https://atomiclife.app', /\.atomiclife\.app$/],
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
async function handler(req, res) {
    try {
        // Run the middleware
        await runMiddleware(req, res, cors);
        // attendeeId, meetingId
        const attendeeId = req?.query?.attendeeId;
        const meetingId = req?.query?.meetingId;
        console.log(attendeeId, ' ateendeeId');
        console.log(meetingId, ' meetingId');
        const state = `${meetingId}#${attendeeId}`;
        const authorizationUrl = (0, api_helper_1.generateGoogleAuthUrl)(state);
        // return res.writeHead(301, { "Location": authorizationUrl });
        return res.redirect(authorizationUrl);
    }
    catch (e) {
        console.log(e, ' unable to auth');
        return res.status(404).json(e);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RhcnQtaGFuZHNoYWtlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic3RhcnQtaGFuZHNoYWtlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBOEJBLDBCQXdCQztBQXBERCxnREFBd0I7QUFDeEIsZ0RBQXdEO0FBRXhELG1DQUFtQztBQUNuQyw4R0FBOEc7QUFDOUcsTUFBTSxJQUFJLEdBQUcsSUFBQSxjQUFJLEVBQUM7SUFDaEIsT0FBTyxFQUFFLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxNQUFNLENBQUM7SUFDaEMsTUFBTSxFQUFFLENBQUMsd0JBQXdCLEVBQUUsb0JBQW9CLENBQUM7Q0FDekQsQ0FBQyxDQUFDO0FBRUgsc0VBQXNFO0FBQ3RFLDhEQUE4RDtBQUM5RCxTQUFTLGFBQWEsQ0FDcEIsR0FBbUIsRUFDbkIsR0FBb0IsRUFDcEIsRUFBWTtJQUVaLE9BQU8sSUFBSSxPQUFPLENBQUMsQ0FBQyxPQUFPLEVBQUUsTUFBTSxFQUFFLEVBQUU7UUFDckMsRUFBRSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUUsQ0FBQyxNQUFXLEVBQUUsRUFBRTtZQUMzQixJQUFJLE1BQU0sWUFBWSxLQUFLLEVBQUUsQ0FBQztnQkFDNUIsT0FBTyxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUM7WUFDeEIsQ0FBQztZQUVELE9BQU8sT0FBTyxDQUFDLE1BQU0sQ0FBQyxDQUFDO1FBQ3pCLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDO0FBRWMsS0FBSyxVQUFVLE9BQU8sQ0FDbkMsR0FBbUIsRUFDbkIsR0FBb0I7SUFFcEIsSUFBSSxDQUFDO1FBQ0gscUJBQXFCO1FBQ3JCLE1BQU0sYUFBYSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUUsSUFBSSxDQUFDLENBQUM7UUFFcEMsd0JBQXdCO1FBQ3hCLE1BQU0sVUFBVSxHQUFHLEdBQUcsRUFBRSxLQUFLLEVBQUUsVUFBVSxDQUFDO1FBQzFDLE1BQU0sU0FBUyxHQUFHLEdBQUcsRUFBRSxLQUFLLEVBQUUsU0FBUyxDQUFDO1FBQ3hDLE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFLGFBQWEsQ0FBQyxDQUFDO1FBQ3ZDLE9BQU8sQ0FBQyxHQUFHLENBQUMsU0FBUyxFQUFFLFlBQVksQ0FBQyxDQUFDO1FBRXJDLE1BQU0sS0FBSyxHQUFHLEdBQUcsU0FBUyxJQUFJLFVBQVUsRUFBRSxDQUFDO1FBRTNDLE1BQU0sZ0JBQWdCLEdBQUcsSUFBQSxrQ0FBcUIsRUFBQyxLQUFLLENBQUMsQ0FBQztRQUV0RCwrREFBK0Q7UUFDL0QsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUFDLGdCQUFnQixDQUFDLENBQUM7SUFDeEMsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxpQkFBaUIsQ0FBQyxDQUFDO1FBQ2xDLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFDakMsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBxcyBmcm9tICdxcyc7XG5pbXBvcnQgQ29ycyBmcm9tICdjb3JzJztcbmltcG9ydCB7IGdlbmVyYXRlR29vZ2xlQXV0aFVybCB9IGZyb20gJ0BsaWIvYXBpLWhlbHBlcic7XG5cbi8vIEluaXRpYWxpemluZyB0aGUgY29ycyBtaWRkbGV3YXJlXG4vLyBZb3UgY2FuIHJlYWQgbW9yZSBhYm91dCB0aGUgYXZhaWxhYmxlIG9wdGlvbnMgaGVyZTogaHR0cHM6Ly9naXRodWIuY29tL2V4cHJlc3Nqcy9jb3JzI2NvbmZpZ3VyYXRpb24tb3B0aW9uc1xuY29uc3QgY29ycyA9IENvcnMoe1xuICBtZXRob2RzOiBbJ1BPU1QnLCAnR0VUJywgJ0hFQUQnXSxcbiAgb3JpZ2luOiBbJ2h0dHBzOi8vYXRvbWljbGlmZS5hcHAnLCAvXFwuYXRvbWljbGlmZVxcLmFwcCQvXSxcbn0pO1xuXG4vLyBIZWxwZXIgbWV0aG9kIHRvIHdhaXQgZm9yIGEgbWlkZGxld2FyZSB0byBleGVjdXRlIGJlZm9yZSBjb250aW51aW5nXG4vLyBBbmQgdG8gdGhyb3cgYW4gZXJyb3Igd2hlbiBhbiBlcnJvciBoYXBwZW5zIGluIGEgbWlkZGxld2FyZVxuZnVuY3Rpb24gcnVuTWlkZGxld2FyZShcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2UsXG4gIGZuOiBGdW5jdGlvblxuKSB7XG4gIHJldHVybiBuZXcgUHJvbWlzZSgocmVzb2x2ZSwgcmVqZWN0KSA9PiB7XG4gICAgZm4ocmVxLCByZXMsIChyZXN1bHQ6IGFueSkgPT4ge1xuICAgICAgaWYgKHJlc3VsdCBpbnN0YW5jZW9mIEVycm9yKSB7XG4gICAgICAgIHJldHVybiByZWplY3QocmVzdWx0KTtcbiAgICAgIH1cblxuICAgICAgcmV0dXJuIHJlc29sdmUocmVzdWx0KTtcbiAgICB9KTtcbiAgfSk7XG59XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgdHJ5IHtcbiAgICAvLyBSdW4gdGhlIG1pZGRsZXdhcmVcbiAgICBhd2FpdCBydW5NaWRkbGV3YXJlKHJlcSwgcmVzLCBjb3JzKTtcblxuICAgIC8vIGF0dGVuZGVlSWQsIG1lZXRpbmdJZFxuICAgIGNvbnN0IGF0dGVuZGVlSWQgPSByZXE/LnF1ZXJ5Py5hdHRlbmRlZUlkO1xuICAgIGNvbnN0IG1lZXRpbmdJZCA9IHJlcT8ucXVlcnk/Lm1lZXRpbmdJZDtcbiAgICBjb25zb2xlLmxvZyhhdHRlbmRlZUlkLCAnIGF0ZWVuZGVlSWQnKTtcbiAgICBjb25zb2xlLmxvZyhtZWV0aW5nSWQsICcgbWVldGluZ0lkJyk7XG5cbiAgICBjb25zdCBzdGF0ZSA9IGAke21lZXRpbmdJZH0jJHthdHRlbmRlZUlkfWA7XG5cbiAgICBjb25zdCBhdXRob3JpemF0aW9uVXJsID0gZ2VuZXJhdGVHb29nbGVBdXRoVXJsKHN0YXRlKTtcblxuICAgIC8vIHJldHVybiByZXMud3JpdGVIZWFkKDMwMSwgeyBcIkxvY2F0aW9uXCI6IGF1dGhvcml6YXRpb25VcmwgfSk7XG4gICAgcmV0dXJuIHJlcy5yZWRpcmVjdChhdXRob3JpemF0aW9uVXJsKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGF1dGgnKTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDQpLmpzb24oZSk7XG4gIH1cbn1cbiJdfQ==
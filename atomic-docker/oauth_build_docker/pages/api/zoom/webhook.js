"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const cors_1 = __importDefault(require("cors"));
const api_helper_1 = require("@lib/api-helper");
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
        (0, api_helper_1.verifyZoomWebhook)(req);
        console.log(req?.body, ' req?.body');
        switch (req?.body?.event) {
            case 'endpoint.url_validation':
                return (0, api_helper_1.validateZoomWebook)(req, res);
            case 'app_deauthorized':
                await (0, api_helper_1.deAuthZoomGivenUserId)(req?.body?.payload?.user_id);
                return res.status(204).end();
            default:
                return res.status(204).end();
        }
    }
    catch (e) {
        console.log(e, ' unable to handle webhook request');
        return res.status(400).end();
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoid2ViaG9vay5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIndlYmhvb2sudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFxQ0EsMEJBMkJDO0FBOURELGdEQUF3QjtBQUN4QixnREFJeUI7QUFPekIsTUFBTSxJQUFJLEdBQUcsSUFBQSxjQUFJLEVBQUM7SUFDaEIsT0FBTyxFQUFFLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxNQUFNLENBQUM7SUFDaEMsTUFBTSxFQUFFLENBQUMsd0JBQXdCLEVBQUUsb0JBQW9CLENBQUM7Q0FDekQsQ0FBQyxDQUFDO0FBRUgsc0VBQXNFO0FBQ3RFLDhEQUE4RDtBQUM5RCxTQUFTLGFBQWEsQ0FDcEIsR0FBbUIsRUFDbkIsR0FBb0IsRUFDcEIsRUFBWTtJQUVaLE9BQU8sSUFBSSxPQUFPLENBQUMsQ0FBQyxPQUFPLEVBQUUsTUFBTSxFQUFFLEVBQUU7UUFDckMsRUFBRSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUUsQ0FBQyxNQUFXLEVBQUUsRUFBRTtZQUMzQixJQUFJLE1BQU0sWUFBWSxLQUFLLEVBQUUsQ0FBQztnQkFDNUIsT0FBTyxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUM7WUFDeEIsQ0FBQztZQUVELE9BQU8sT0FBTyxDQUFDLE1BQU0sQ0FBQyxDQUFDO1FBQ3pCLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDO0FBRWMsS0FBSyxVQUFVLE9BQU8sQ0FDbkMsR0FBbUIsRUFDbkIsR0FBb0I7SUFFcEIsSUFBSSxDQUFDO1FBQ0gscUJBQXFCO1FBQ3JCLE1BQU0sYUFBYSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUUsSUFBSSxDQUFDLENBQUM7UUFFcEMsSUFBQSw4QkFBaUIsRUFBQyxHQUE2QixDQUFDLENBQUM7UUFFakQsT0FBTyxDQUFDLEdBQUcsQ0FBQyxHQUFHLEVBQUUsSUFBSSxFQUFFLFlBQVksQ0FBQyxDQUFDO1FBRXJDLFFBQVEsR0FBRyxFQUFFLElBQUksRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUN6QixLQUFLLHlCQUF5QjtnQkFDNUIsT0FBTyxJQUFBLCtCQUFrQixFQUFDLEdBQXVDLEVBQUUsR0FBRyxDQUFDLENBQUM7WUFDMUUsS0FBSyxrQkFBa0I7Z0JBQ3JCLE1BQU0sSUFBQSxrQ0FBcUIsRUFDeEIsR0FBb0MsRUFBRSxJQUFJLEVBQUUsT0FBTyxFQUFFLE9BQU8sQ0FDOUQsQ0FBQztnQkFDRixPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsR0FBRyxFQUFFLENBQUM7WUFDL0I7Z0JBQ0UsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsRUFBRSxDQUFDO1FBQ2pDLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLG1DQUFtQyxDQUFDLENBQUM7UUFDcEQsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsRUFBRSxDQUFDO0lBQy9CLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHR5cGUgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgcXMgZnJvbSAncXMnO1xuaW1wb3J0IENvcnMgZnJvbSAnY29ycyc7XG5pbXBvcnQge1xuICBkZUF1dGhab29tR2l2ZW5Vc2VySWQsXG4gIHZhbGlkYXRlWm9vbVdlYm9vayxcbiAgdmVyaWZ5Wm9vbVdlYmhvb2ssXG59IGZyb20gJ0BsaWIvYXBpLWhlbHBlcic7XG5pbXBvcnQge1xuICBab29tV2ViaG9va0RlQXV0aFJlcXVlc3RUeXBlLFxuICBab29tV2ViaG9va1JlcXVlc3RUeXBlLFxuICBab29tV2ViaG9va1ZhbGlkYXRpb25SZXF1ZXN0VHlwZSxcbn0gZnJvbSAnQGxpYi90eXBlcyc7XG5cbmNvbnN0IGNvcnMgPSBDb3JzKHtcbiAgbWV0aG9kczogWydQT1NUJywgJ0dFVCcsICdIRUFEJ10sXG4gIG9yaWdpbjogWydodHRwczovL2F0b21pY2xpZmUuYXBwJywgL1xcLmF0b21pY2xpZmVcXC5hcHAkL10sXG59KTtcblxuLy8gSGVscGVyIG1ldGhvZCB0byB3YWl0IGZvciBhIG1pZGRsZXdhcmUgdG8gZXhlY3V0ZSBiZWZvcmUgY29udGludWluZ1xuLy8gQW5kIHRvIHRocm93IGFuIGVycm9yIHdoZW4gYW4gZXJyb3IgaGFwcGVucyBpbiBhIG1pZGRsZXdhcmVcbmZ1bmN0aW9uIHJ1bk1pZGRsZXdhcmUoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlLFxuICBmbjogRnVuY3Rpb25cbikge1xuICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4ge1xuICAgIGZuKHJlcSwgcmVzLCAocmVzdWx0OiBhbnkpID0+IHtcbiAgICAgIGlmIChyZXN1bHQgaW5zdGFuY2VvZiBFcnJvcikge1xuICAgICAgICByZXR1cm4gcmVqZWN0KHJlc3VsdCk7XG4gICAgICB9XG5cbiAgICAgIHJldHVybiByZXNvbHZlKHJlc3VsdCk7XG4gICAgfSk7XG4gIH0pO1xufVxuXG5leHBvcnQgZGVmYXVsdCBhc3luYyBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZVxuKSB7XG4gIHRyeSB7XG4gICAgLy8gUnVuIHRoZSBtaWRkbGV3YXJlXG4gICAgYXdhaXQgcnVuTWlkZGxld2FyZShyZXEsIHJlcywgY29ycyk7XG5cbiAgICB2ZXJpZnlab29tV2ViaG9vayhyZXEgYXMgWm9vbVdlYmhvb2tSZXF1ZXN0VHlwZSk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXE/LmJvZHksICcgcmVxPy5ib2R5Jyk7XG5cbiAgICBzd2l0Y2ggKHJlcT8uYm9keT8uZXZlbnQpIHtcbiAgICAgIGNhc2UgJ2VuZHBvaW50LnVybF92YWxpZGF0aW9uJzpcbiAgICAgICAgcmV0dXJuIHZhbGlkYXRlWm9vbVdlYm9vayhyZXEgYXMgWm9vbVdlYmhvb2tWYWxpZGF0aW9uUmVxdWVzdFR5cGUsIHJlcyk7XG4gICAgICBjYXNlICdhcHBfZGVhdXRob3JpemVkJzpcbiAgICAgICAgYXdhaXQgZGVBdXRoWm9vbUdpdmVuVXNlcklkKFxuICAgICAgICAgIChyZXEgYXMgWm9vbVdlYmhvb2tEZUF1dGhSZXF1ZXN0VHlwZSk/LmJvZHk/LnBheWxvYWQ/LnVzZXJfaWRcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoMjA0KS5lbmQoKTtcbiAgICAgIGRlZmF1bHQ6XG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDIwNCkuZW5kKCk7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaGFuZGxlIHdlYmhvb2sgcmVxdWVzdCcpO1xuICAgIHJldHVybiByZXMuc3RhdHVzKDQwMCkuZW5kKCk7XG4gIH1cbn1cbiJdfQ==
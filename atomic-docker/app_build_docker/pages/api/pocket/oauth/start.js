"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const pocket_api_1 = __importDefault(require("pocket-api"));
async function handler(req, res) {
    const consumerKey = process.env.POCKET_CONSUMER_KEY;
    const redirectUri = process.env.POCKET_REDIRECT_URI;
    if (!consumerKey || !redirectUri) {
        return res
            .status(500)
            .json({ message: 'Pocket environment variables not configured.' });
    }
    const pocket = new pocket_api_1.default({
        consumer_key: consumerKey,
        redirect_uri: redirectUri,
    });
    try {
        const { code } = await pocket.getRequestToken();
        // In a real app, you would save this request token in the user's session
        // or a temporary store to verify it on callback.
        const authorizationUrl = pocket.getAuthorizationURL({
            request_token: code,
        });
        res.redirect(authorizationUrl);
    }
    catch (error) {
        console.error('Error getting Pocket request token:', error);
        return res
            .status(500)
            .json({ message: 'Failed to start Pocket authentication' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RhcnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzdGFydC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQUdBLDBCQWlDQztBQW5DRCw0REFBbUM7QUFFcEIsS0FBSyxVQUFVLE9BQU8sQ0FDbkMsR0FBbUIsRUFDbkIsR0FBb0I7SUFFcEIsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxtQkFBbUIsQ0FBQztJQUNwRCxNQUFNLFdBQVcsR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLG1CQUFtQixDQUFDO0lBRXBELElBQUksQ0FBQyxXQUFXLElBQUksQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUNqQyxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLDhDQUE4QyxFQUFFLENBQUMsQ0FBQztJQUN2RSxDQUFDO0lBRUQsTUFBTSxNQUFNLEdBQUcsSUFBSSxvQkFBUyxDQUFDO1FBQzNCLFlBQVksRUFBRSxXQUFXO1FBQ3pCLFlBQVksRUFBRSxXQUFXO0tBQzFCLENBQUMsQ0FBQztJQUVILElBQUksQ0FBQztRQUNILE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxNQUFNLE1BQU0sQ0FBQyxlQUFlLEVBQUUsQ0FBQztRQUNoRCx5RUFBeUU7UUFDekUsaURBQWlEO1FBQ2pELE1BQU0sZ0JBQWdCLEdBQUcsTUFBTSxDQUFDLG1CQUFtQixDQUFDO1lBQ2xELGFBQWEsRUFBRSxJQUFJO1NBQ3BCLENBQUMsQ0FBQztRQUVILEdBQUcsQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztJQUNqQyxDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sQ0FBQyxLQUFLLENBQUMscUNBQXFDLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDNUQsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSx1Q0FBdUMsRUFBRSxDQUFDLENBQUM7SUFDaEUsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgUG9ja2V0QVBJIGZyb20gJ3BvY2tldC1hcGknO1xuXG5leHBvcnQgZGVmYXVsdCBhc3luYyBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZVxuKSB7XG4gIGNvbnN0IGNvbnN1bWVyS2V5ID0gcHJvY2Vzcy5lbnYuUE9DS0VUX0NPTlNVTUVSX0tFWTtcbiAgY29uc3QgcmVkaXJlY3RVcmkgPSBwcm9jZXNzLmVudi5QT0NLRVRfUkVESVJFQ1RfVVJJO1xuXG4gIGlmICghY29uc3VtZXJLZXkgfHwgIXJlZGlyZWN0VXJpKSB7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7IG1lc3NhZ2U6ICdQb2NrZXQgZW52aXJvbm1lbnQgdmFyaWFibGVzIG5vdCBjb25maWd1cmVkLicgfSk7XG4gIH1cblxuICBjb25zdCBwb2NrZXQgPSBuZXcgUG9ja2V0QVBJKHtcbiAgICBjb25zdW1lcl9rZXk6IGNvbnN1bWVyS2V5LFxuICAgIHJlZGlyZWN0X3VyaTogcmVkaXJlY3RVcmksXG4gIH0pO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgeyBjb2RlIH0gPSBhd2FpdCBwb2NrZXQuZ2V0UmVxdWVzdFRva2VuKCk7XG4gICAgLy8gSW4gYSByZWFsIGFwcCwgeW91IHdvdWxkIHNhdmUgdGhpcyByZXF1ZXN0IHRva2VuIGluIHRoZSB1c2VyJ3Mgc2Vzc2lvblxuICAgIC8vIG9yIGEgdGVtcG9yYXJ5IHN0b3JlIHRvIHZlcmlmeSBpdCBvbiBjYWxsYmFjay5cbiAgICBjb25zdCBhdXRob3JpemF0aW9uVXJsID0gcG9ja2V0LmdldEF1dGhvcml6YXRpb25VUkwoe1xuICAgICAgcmVxdWVzdF90b2tlbjogY29kZSxcbiAgICB9KTtcblxuICAgIHJlcy5yZWRpcmVjdChhdXRob3JpemF0aW9uVXJsKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBnZXR0aW5nIFBvY2tldCByZXF1ZXN0IHRva2VuOicsIGVycm9yKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgbWVzc2FnZTogJ0ZhaWxlZCB0byBzdGFydCBQb2NrZXQgYXV0aGVudGljYXRpb24nIH0pO1xuICB9XG59XG4iXX0=
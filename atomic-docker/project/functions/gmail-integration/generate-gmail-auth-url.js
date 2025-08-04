import { google } from 'googleapis';
// Adjust the path based on the final location of gmail-integration relative to google-api-auth
import { googleClientIdGmail, googleClientSecretGmail, googleGmailRedirectUrl, googleGmailScopes, } from '../google-api-auth/_libs/constants';
const handler = async (req, res) => {
    try {
        // const userId = req.body.session_variables['x-hasura-user-id'];
        const redirectUri = googleGmailRedirectUrl;
        if (!redirectUri) {
            console.error('GOOGLE_GMAIL_REDIRECT_URL environment variable is not configured.');
            return res
                .status(500)
                .json({
                message: 'Server configuration error: Missing redirect URL for Gmail integration.',
            });
        }
        if (!googleClientIdGmail) {
            console.error('GOOGLE_CLIENT_ID_GMAIL environment variable is not configured.');
            return res
                .status(500)
                .json({
                message: 'Server configuration error: Missing Client ID for Gmail integration.',
            });
        }
        // googleClientSecretGmail is not strictly required to generate the auth URL but the oauth2Client expects it.
        // It will be used in the callback handler.
        if (!googleClientSecretGmail) {
            console.error('GOOGLE_CLIENT_SECRET_GMAIL environment variable is not configured.');
            return res
                .status(500)
                .json({
                message: 'Server configuration error: Missing Client Secret for Gmail integration.',
            });
        }
        const oauth2Client = new google.auth.OAuth2(googleClientIdGmail, googleClientSecretGmail, redirectUri);
        const authorizationUrl = oauth2Client.generateAuthUrl({
            access_type: 'offline', // Request a refresh token
            scope: googleGmailScopes,
            prompt: 'consent', // Important to ensure the user is prompted for consent and a refresh token is issued,
            // especially if they've authorized before with fewer scopes or for a different app version.
        });
        return res.status(200).json({
            authorizationUrl: authorizationUrl,
        });
    }
    catch (e) {
        console.error('Error generating Gmail auth URL:', e);
        return res.status(500).json({
            message: 'Error generating Gmail authorization URL: ' +
                (e.message || 'Unknown error'),
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2VuZXJhdGUtZ21haWwtYXV0aC11cmwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZW5lcmF0ZS1nbWFpbC1hdXRoLXVybC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0sWUFBWSxDQUFDO0FBQ3BDLCtGQUErRjtBQUMvRixPQUFPLEVBQ0wsbUJBQW1CLEVBQ25CLHVCQUF1QixFQUN2QixzQkFBc0IsRUFDdEIsaUJBQWlCLEdBQ2xCLE1BQU0sb0NBQW9DLENBQUM7QUFXNUMsTUFBTSxPQUFPLEdBQUcsS0FBSyxFQUNuQixHQUFxRCxFQUNyRCxHQUFhLEVBQ2IsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILGlFQUFpRTtRQUVqRSxNQUFNLFdBQVcsR0FBRyxzQkFBc0IsQ0FBQztRQUMzQyxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7WUFDakIsT0FBTyxDQUFDLEtBQUssQ0FDWCxtRUFBbUUsQ0FDcEUsQ0FBQztZQUNGLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixPQUFPLEVBQ0wseUVBQXlFO2FBQzVFLENBQUMsQ0FBQztRQUNQLENBQUM7UUFFRCxJQUFJLENBQUMsbUJBQW1CLEVBQUUsQ0FBQztZQUN6QixPQUFPLENBQUMsS0FBSyxDQUNYLGdFQUFnRSxDQUNqRSxDQUFDO1lBQ0YsT0FBTyxHQUFHO2lCQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7aUJBQ1gsSUFBSSxDQUFDO2dCQUNKLE9BQU8sRUFDTCxzRUFBc0U7YUFDekUsQ0FBQyxDQUFDO1FBQ1AsQ0FBQztRQUNELDZHQUE2RztRQUM3RywyQ0FBMkM7UUFDM0MsSUFBSSxDQUFDLHVCQUF1QixFQUFFLENBQUM7WUFDN0IsT0FBTyxDQUFDLEtBQUssQ0FDWCxvRUFBb0UsQ0FDckUsQ0FBQztZQUNGLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixPQUFPLEVBQ0wsMEVBQTBFO2FBQzdFLENBQUMsQ0FBQztRQUNQLENBQUM7UUFFRCxNQUFNLFlBQVksR0FBRyxJQUFJLE1BQU0sQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUN6QyxtQkFBbUIsRUFDbkIsdUJBQXVCLEVBQ3ZCLFdBQVcsQ0FDWixDQUFDO1FBRUYsTUFBTSxnQkFBZ0IsR0FBRyxZQUFZLENBQUMsZUFBZSxDQUFDO1lBQ3BELFdBQVcsRUFBRSxTQUFTLEVBQUUsMEJBQTBCO1lBQ2xELEtBQUssRUFBRSxpQkFBaUI7WUFDeEIsTUFBTSxFQUFFLFNBQVMsRUFBRSxzRkFBc0Y7WUFDekcsNEZBQTRGO1NBQzdGLENBQUMsQ0FBQztRQUVILE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsZ0JBQWdCLEVBQUUsZ0JBQWdCO1NBQ25DLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLE9BQU8sQ0FBQyxLQUFLLENBQUMsa0NBQWtDLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDckQsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixPQUFPLEVBQ0wsNENBQTRDO2dCQUM1QyxDQUFDLENBQUMsQ0FBQyxPQUFPLElBQUksZUFBZSxDQUFDO1NBQ2pDLENBQUMsQ0FBQztJQUNMLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixlQUFlLE9BQU8sQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFJlcXVlc3QsIFJlc3BvbnNlIH0gZnJvbSAnZXhwcmVzcyc7XG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tICdnb29nbGVhcGlzJztcbi8vIEFkanVzdCB0aGUgcGF0aCBiYXNlZCBvbiB0aGUgZmluYWwgbG9jYXRpb24gb2YgZ21haWwtaW50ZWdyYXRpb24gcmVsYXRpdmUgdG8gZ29vZ2xlLWFwaS1hdXRoXG5pbXBvcnQge1xuICBnb29nbGVDbGllbnRJZEdtYWlsLFxuICBnb29nbGVDbGllbnRTZWNyZXRHbWFpbCxcbiAgZ29vZ2xlR21haWxSZWRpcmVjdFVybCxcbiAgZ29vZ2xlR21haWxTY29wZXMsXG59IGZyb20gJy4uL2dvb2dsZS1hcGktYXV0aC9fbGlicy9jb25zdGFudHMnO1xuXG5pbnRlcmZhY2UgR2VuZXJhdGVHbWFpbEF1dGhVcmxSZXF1ZXN0Qm9keSB7XG4gIHNlc3Npb25fdmFyaWFibGVzOiB7XG4gICAgJ3gtaGFzdXJhLXVzZXItaWQnOiBzdHJpbmc7XG4gIH07XG4gIGlucHV0OiB7XG4gICAgLy8gY2xpZW50UmVkaXJlY3RVcmk/OiBzdHJpbmc7IC8vIElmIHlvdSBuZWVkIHRvIHN1cHBvcnQgbXVsdGlwbGUgcmVkaXJlY3QgVVJJcyBmcm9tIGRpZmZlcmVudCBjbGllbnRzXG4gIH07XG59XG5cbmNvbnN0IGhhbmRsZXIgPSBhc3luYyAoXG4gIHJlcTogUmVxdWVzdDx7fSwge30sIEdlbmVyYXRlR21haWxBdXRoVXJsUmVxdWVzdEJvZHk+LFxuICByZXM6IFJlc3BvbnNlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBjb25zdCB1c2VySWQgPSByZXEuYm9keS5zZXNzaW9uX3ZhcmlhYmxlc1sneC1oYXN1cmEtdXNlci1pZCddO1xuXG4gICAgY29uc3QgcmVkaXJlY3RVcmkgPSBnb29nbGVHbWFpbFJlZGlyZWN0VXJsO1xuICAgIGlmICghcmVkaXJlY3RVcmkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICdHT09HTEVfR01BSUxfUkVESVJFQ1RfVVJMIGVudmlyb25tZW50IHZhcmlhYmxlIGlzIG5vdCBjb25maWd1cmVkLidcbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgICAuanNvbih7XG4gICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICdTZXJ2ZXIgY29uZmlndXJhdGlvbiBlcnJvcjogTWlzc2luZyByZWRpcmVjdCBVUkwgZm9yIEdtYWlsIGludGVncmF0aW9uLicsXG4gICAgICAgIH0pO1xuICAgIH1cblxuICAgIGlmICghZ29vZ2xlQ2xpZW50SWRHbWFpbCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0dPT0dMRV9DTElFTlRfSURfR01BSUwgZW52aXJvbm1lbnQgdmFyaWFibGUgaXMgbm90IGNvbmZpZ3VyZWQuJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgJ1NlcnZlciBjb25maWd1cmF0aW9uIGVycm9yOiBNaXNzaW5nIENsaWVudCBJRCBmb3IgR21haWwgaW50ZWdyYXRpb24uJyxcbiAgICAgICAgfSk7XG4gICAgfVxuICAgIC8vIGdvb2dsZUNsaWVudFNlY3JldEdtYWlsIGlzIG5vdCBzdHJpY3RseSByZXF1aXJlZCB0byBnZW5lcmF0ZSB0aGUgYXV0aCBVUkwgYnV0IHRoZSBvYXV0aDJDbGllbnQgZXhwZWN0cyBpdC5cbiAgICAvLyBJdCB3aWxsIGJlIHVzZWQgaW4gdGhlIGNhbGxiYWNrIGhhbmRsZXIuXG4gICAgaWYgKCFnb29nbGVDbGllbnRTZWNyZXRHbWFpbCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0dPT0dMRV9DTElFTlRfU0VDUkVUX0dNQUlMIGVudmlyb25tZW50IHZhcmlhYmxlIGlzIG5vdCBjb25maWd1cmVkLidcbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgICAuanNvbih7XG4gICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICdTZXJ2ZXIgY29uZmlndXJhdGlvbiBlcnJvcjogTWlzc2luZyBDbGllbnQgU2VjcmV0IGZvciBHbWFpbCBpbnRlZ3JhdGlvbi4nLFxuICAgICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zdCBvYXV0aDJDbGllbnQgPSBuZXcgZ29vZ2xlLmF1dGguT0F1dGgyKFxuICAgICAgZ29vZ2xlQ2xpZW50SWRHbWFpbCxcbiAgICAgIGdvb2dsZUNsaWVudFNlY3JldEdtYWlsLFxuICAgICAgcmVkaXJlY3RVcmlcbiAgICApO1xuXG4gICAgY29uc3QgYXV0aG9yaXphdGlvblVybCA9IG9hdXRoMkNsaWVudC5nZW5lcmF0ZUF1dGhVcmwoe1xuICAgICAgYWNjZXNzX3R5cGU6ICdvZmZsaW5lJywgLy8gUmVxdWVzdCBhIHJlZnJlc2ggdG9rZW5cbiAgICAgIHNjb3BlOiBnb29nbGVHbWFpbFNjb3BlcyxcbiAgICAgIHByb21wdDogJ2NvbnNlbnQnLCAvLyBJbXBvcnRhbnQgdG8gZW5zdXJlIHRoZSB1c2VyIGlzIHByb21wdGVkIGZvciBjb25zZW50IGFuZCBhIHJlZnJlc2ggdG9rZW4gaXMgaXNzdWVkLFxuICAgICAgLy8gZXNwZWNpYWxseSBpZiB0aGV5J3ZlIGF1dGhvcml6ZWQgYmVmb3JlIHdpdGggZmV3ZXIgc2NvcGVzIG9yIGZvciBhIGRpZmZlcmVudCBhcHAgdmVyc2lvbi5cbiAgICB9KTtcblxuICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7XG4gICAgICBhdXRob3JpemF0aW9uVXJsOiBhdXRob3JpemF0aW9uVXJsLFxuICAgIH0pO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBnZW5lcmF0aW5nIEdtYWlsIGF1dGggVVJMOicsIGUpO1xuICAgIHJldHVybiByZXMuc3RhdHVzKDUwMCkuanNvbih7XG4gICAgICBtZXNzYWdlOlxuICAgICAgICAnRXJyb3IgZ2VuZXJhdGluZyBHbWFpbCBhdXRob3JpemF0aW9uIFVSTDogJyArXG4gICAgICAgIChlLm1lc3NhZ2UgfHwgJ1Vua25vd24gZXJyb3InKSxcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==
import { google } from 'googleapis';
// Adjust the path based on the final location of mcp-service relative to google-api-auth
import { googleClientIdMcp, googleClientSecretMcp, googleMcpRedirectUrl, googleMcpScopes, } from '../google-api-auth/_libs/constants';
const handler = async (req, res) => {
    try {
        // const userId = req.body.session_variables['x-hasura-user-id'];
        const redirectUri = googleMcpRedirectUrl;
        if (!redirectUri) {
            console.error('GOOGLE_MCP_REDIRECT_URL environment variable is not configured.');
            return res
                .status(500)
                .json({
                message: 'Server configuration error: Missing redirect URL for Mcp integration.',
            });
        }
        if (!googleClientIdMcp) {
            console.error('GOOGLE_CLIENT_ID_MCP environment variable is not configured.');
            return res
                .status(500)
                .json({
                message: 'Server configuration error: Missing Client ID for Mcp integration.',
            });
        }
        // googleClientSecretMcp is not strictly required to generate the auth URL but the oauth2Client expects it.
        // It will be used in the callback handler.
        if (!googleClientSecretMcp) {
            console.error('GOOGLE_CLIENT_SECRET_MCP environment variable is not configured.');
            return res
                .status(500)
                .json({
                message: 'Server configuration error: Missing Client Secret for Mcp integration.',
            });
        }
        const oauth2Client = new google.auth.OAuth2(googleClientIdMcp, googleClientSecretMcp, redirectUri);
        const authorizationUrl = oauth2Client.generateAuthUrl({
            access_type: 'offline', // Request a refresh token
            scope: googleMcpScopes,
            prompt: 'consent', // Important to ensure the user is prompted for consent and a refresh token is issued,
            // especially if they've authorized before with fewer scopes or for a different app version.
        });
        return res.status(200).json({
            authorizationUrl: authorizationUrl,
        });
    }
    catch (e) {
        console.error('Error generating Mcp auth URL:', e);
        return res.status(500).json({
            message: 'Error generating Mcp authorization URL: ' +
                (e.message || 'Unknown error'),
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2VuZXJhdGUtYXV0aC11cmwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZW5lcmF0ZS1hdXRoLXVybC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0sWUFBWSxDQUFDO0FBQ3BDLHlGQUF5RjtBQUN6RixPQUFPLEVBQ0wsaUJBQWlCLEVBQ2pCLHFCQUFxQixFQUNyQixvQkFBb0IsRUFDcEIsZUFBZSxHQUNoQixNQUFNLG9DQUFvQyxDQUFDO0FBVzVDLE1BQU0sT0FBTyxHQUFHLEtBQUssRUFDbkIsR0FBbUQsRUFDbkQsR0FBYSxFQUNiLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxpRUFBaUU7UUFFakUsTUFBTSxXQUFXLEdBQUcsb0JBQW9CLENBQUM7UUFDekMsSUFBSSxDQUFDLFdBQVcsRUFBRSxDQUFDO1lBQ2pCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsaUVBQWlFLENBQ2xFLENBQUM7WUFDRixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUM7Z0JBQ0osT0FBTyxFQUNMLHVFQUF1RTthQUMxRSxDQUFDLENBQUM7UUFDUCxDQUFDO1FBRUQsSUFBSSxDQUFDLGlCQUFpQixFQUFFLENBQUM7WUFDdkIsT0FBTyxDQUFDLEtBQUssQ0FDWCw4REFBOEQsQ0FDL0QsQ0FBQztZQUNGLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixPQUFPLEVBQ0wsb0VBQW9FO2FBQ3ZFLENBQUMsQ0FBQztRQUNQLENBQUM7UUFDRCwyR0FBMkc7UUFDM0csMkNBQTJDO1FBQzNDLElBQUksQ0FBQyxxQkFBcUIsRUFBRSxDQUFDO1lBQzNCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsa0VBQWtFLENBQ25FLENBQUM7WUFDRixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUM7Z0JBQ0osT0FBTyxFQUNMLHdFQUF3RTthQUMzRSxDQUFDLENBQUM7UUFDUCxDQUFDO1FBRUQsTUFBTSxZQUFZLEdBQUcsSUFBSSxNQUFNLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FDekMsaUJBQWlCLEVBQ2pCLHFCQUFxQixFQUNyQixXQUFXLENBQ1osQ0FBQztRQUVGLE1BQU0sZ0JBQWdCLEdBQUcsWUFBWSxDQUFDLGVBQWUsQ0FBQztZQUNwRCxXQUFXLEVBQUUsU0FBUyxFQUFFLDBCQUEwQjtZQUNsRCxLQUFLLEVBQUUsZUFBZTtZQUN0QixNQUFNLEVBQUUsU0FBUyxFQUFFLHNGQUFzRjtZQUN6Ryw0RkFBNEY7U0FDN0YsQ0FBQyxDQUFDO1FBRUgsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixnQkFBZ0IsRUFBRSxnQkFBZ0I7U0FDbkMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsT0FBTyxDQUFDLEtBQUssQ0FBQyxnQ0FBZ0MsRUFBRSxDQUFDLENBQUMsQ0FBQztRQUNuRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFDTCwwQ0FBMEM7Z0JBQzFDLENBQUMsQ0FBQyxDQUFDLE9BQU8sSUFBSSxlQUFlLENBQUM7U0FDakMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsT0FBTyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCB7IGdvb2dsZSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuLy8gQWRqdXN0IHRoZSBwYXRoIGJhc2VkIG9uIHRoZSBmaW5hbCBsb2NhdGlvbiBvZiBtY3Atc2VydmljZSByZWxhdGl2ZSB0byBnb29nbGUtYXBpLWF1dGhcbmltcG9ydCB7XG4gIGdvb2dsZUNsaWVudElkTWNwLFxuICBnb29nbGVDbGllbnRTZWNyZXRNY3AsXG4gIGdvb2dsZU1jcFJlZGlyZWN0VXJsLFxuICBnb29nbGVNY3BTY29wZXMsXG59IGZyb20gJy4uL2dvb2dsZS1hcGktYXV0aC9fbGlicy9jb25zdGFudHMnO1xuXG5pbnRlcmZhY2UgR2VuZXJhdGVNY3BBdXRoVXJsUmVxdWVzdEJvZHkge1xuICBzZXNzaW9uX3ZhcmlhYmxlczoge1xuICAgICd4LWhhc3VyYS11c2VyLWlkJzogc3RyaW5nO1xuICB9O1xuICBpbnB1dDoge1xuICAgIC8vIGNsaWVudFJlZGlyZWN0VXJpPzogc3RyaW5nOyAvLyBJZiB5b3UgbmVlZCB0byBzdXBwb3J0IG11bHRpcGxlIHJlZGlyZWN0IFVSSXMgZnJvbSBkaWZmZXJlbnQgY2xpZW50c1xuICB9O1xufVxuXG5jb25zdCBoYW5kbGVyID0gYXN5bmMgKFxuICByZXE6IFJlcXVlc3Q8e30sIHt9LCBHZW5lcmF0ZU1jcEF1dGhVcmxSZXF1ZXN0Qm9keT4sXG4gIHJlczogUmVzcG9uc2VcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIGNvbnN0IHVzZXJJZCA9IHJlcS5ib2R5LnNlc3Npb25fdmFyaWFibGVzWyd4LWhhc3VyYS11c2VyLWlkJ107XG5cbiAgICBjb25zdCByZWRpcmVjdFVyaSA9IGdvb2dsZU1jcFJlZGlyZWN0VXJsO1xuICAgIGlmICghcmVkaXJlY3RVcmkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICdHT09HTEVfTUNQX1JFRElSRUNUX1VSTCBlbnZpcm9ubWVudCB2YXJpYWJsZSBpcyBub3QgY29uZmlndXJlZC4nXG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAnU2VydmVyIGNvbmZpZ3VyYXRpb24gZXJyb3I6IE1pc3NpbmcgcmVkaXJlY3QgVVJMIGZvciBNY3AgaW50ZWdyYXRpb24uJyxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgaWYgKCFnb29nbGVDbGllbnRJZE1jcCkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0dPT0dMRV9DTElFTlRfSURfTUNQIGVudmlyb25tZW50IHZhcmlhYmxlIGlzIG5vdCBjb25maWd1cmVkLidcbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgICAuanNvbih7XG4gICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICdTZXJ2ZXIgY29uZmlndXJhdGlvbiBlcnJvcjogTWlzc2luZyBDbGllbnQgSUQgZm9yIE1jcCBpbnRlZ3JhdGlvbi4nLFxuICAgICAgICB9KTtcbiAgICB9XG4gICAgLy8gZ29vZ2xlQ2xpZW50U2VjcmV0TWNwIGlzIG5vdCBzdHJpY3RseSByZXF1aXJlZCB0byBnZW5lcmF0ZSB0aGUgYXV0aCBVUkwgYnV0IHRoZSBvYXV0aDJDbGllbnQgZXhwZWN0cyBpdC5cbiAgICAvLyBJdCB3aWxsIGJlIHVzZWQgaW4gdGhlIGNhbGxiYWNrIGhhbmRsZXIuXG4gICAgaWYgKCFnb29nbGVDbGllbnRTZWNyZXRNY3ApIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICdHT09HTEVfQ0xJRU5UX1NFQ1JFVF9NQ1AgZW52aXJvbm1lbnQgdmFyaWFibGUgaXMgbm90IGNvbmZpZ3VyZWQuJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgJ1NlcnZlciBjb25maWd1cmF0aW9uIGVycm9yOiBNaXNzaW5nIENsaWVudCBTZWNyZXQgZm9yIE1jcCBpbnRlZ3JhdGlvbi4nLFxuICAgICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zdCBvYXV0aDJDbGllbnQgPSBuZXcgZ29vZ2xlLmF1dGguT0F1dGgyKFxuICAgICAgZ29vZ2xlQ2xpZW50SWRNY3AsXG4gICAgICBnb29nbGVDbGllbnRTZWNyZXRNY3AsXG4gICAgICByZWRpcmVjdFVyaVxuICAgICk7XG5cbiAgICBjb25zdCBhdXRob3JpemF0aW9uVXJsID0gb2F1dGgyQ2xpZW50LmdlbmVyYXRlQXV0aFVybCh7XG4gICAgICBhY2Nlc3NfdHlwZTogJ29mZmxpbmUnLCAvLyBSZXF1ZXN0IGEgcmVmcmVzaCB0b2tlblxuICAgICAgc2NvcGU6IGdvb2dsZU1jcFNjb3BlcyxcbiAgICAgIHByb21wdDogJ2NvbnNlbnQnLCAvLyBJbXBvcnRhbnQgdG8gZW5zdXJlIHRoZSB1c2VyIGlzIHByb21wdGVkIGZvciBjb25zZW50IGFuZCBhIHJlZnJlc2ggdG9rZW4gaXMgaXNzdWVkLFxuICAgICAgLy8gZXNwZWNpYWxseSBpZiB0aGV5J3ZlIGF1dGhvcml6ZWQgYmVmb3JlIHdpdGggZmV3ZXIgc2NvcGVzIG9yIGZvciBhIGRpZmZlcmVudCBhcHAgdmVyc2lvbi5cbiAgICB9KTtcblxuICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7XG4gICAgICBhdXRob3JpemF0aW9uVXJsOiBhdXRob3JpemF0aW9uVXJsLFxuICAgIH0pO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBnZW5lcmF0aW5nIE1jcCBhdXRoIFVSTDonLCBlKTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg1MDApLmpzb24oe1xuICAgICAgbWVzc2FnZTpcbiAgICAgICAgJ0Vycm9yIGdlbmVyYXRpbmcgTWNwIGF1dGhvcml6YXRpb24gVVJMOiAnICtcbiAgICAgICAgKGUubWVzc2FnZSB8fCAnVW5rbm93biBlcnJvcicpLFxuICAgIH0pO1xuICB9XG59O1xuXG5leHBvcnQgZGVmYXVsdCBoYW5kbGVyO1xuIl19
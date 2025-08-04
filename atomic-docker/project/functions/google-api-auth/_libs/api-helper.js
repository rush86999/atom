import got from 'got';
import { google } from 'googleapis';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { googleAuthRedirectUri, googleClientIdAtomicWeb, googleClientIdIos, googleClientIdWeb, googleClientSecretAtomicWeb, googleClientSecretWeb, googleTokenUrl, } from './constants';
import { googleClientIdGmail, googleClientSecretGmail, googleClientIdMcp, googleClientSecretMcp, } from './constants'; // Added Mcp constants
dayjs.extend(utc);
dayjs.extend(timezone);
export const getGoogleTokenAndRefreshToken = async (code) => {
    try {
        const oauth2Client = new google.auth.OAuth2(googleClientIdWeb, googleClientSecretWeb, googleAuthRedirectUri);
        const { tokens } = await oauth2Client.getToken(code);
        return tokens;
    }
    catch (e) {
        console.log(e, ' unable to get google token and refresh token');
        throw e; // Re-throw the error to be handled by the caller
    }
};
// New function for Gmail token exchange
export const getGmailUserTokens = async (code, redirectUri) => {
    try {
        const oauth2Client = new google.auth.OAuth2(googleClientIdGmail, // Use Gmail specific client ID
        googleClientSecretGmail, // Use Gmail specific client secret
        redirectUri // Use the provided redirect URI for this specific flow
        );
        const { tokens } = await oauth2Client.getToken(code);
        if (!tokens) {
            throw new Error('Failed to retrieve tokens from Google.');
        }
        return tokens;
    }
    catch (e) {
        console.error('Error in getGmailUserTokens:', e);
        throw e; // Re-throw the error
    }
};
export const googleCalendarAtomicWebRefreshToken = async (refreshToken) => {
    try {
        const res = await got
            .post(googleTokenUrl, {
            form: {
                grant_type: 'refresh_token',
                refresh_token: refreshToken,
                client_id: googleClientIdAtomicWeb,
                client_secret: googleClientSecretAtomicWeb,
            },
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        })
            .json();
        console.log(res, ' refresh token success');
        return res;
    }
    catch (e) {
        console.log(e, ' unable to refresh token');
        throw e; // Re-throw
    }
};
// New function for Gmail token refresh
export const refreshGmailAccessToken = async (refreshToken) => {
    try {
        const res = await got
            .post(googleTokenUrl, {
            form: {
                grant_type: 'refresh_token',
                refresh_token: refreshToken,
                client_id: googleClientIdGmail, // Use Gmail specific client ID
                client_secret: googleClientSecretGmail, // Use Gmail specific client secret
            },
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        })
            .json();
        console.log(res, 'Gmail access token refresh success');
        return res;
    }
    catch (e) {
        console.error('Error in refreshGmailAccessToken:', e);
        throw e; // Re-throw
    }
};
export const googleCalendarWebRefreshToken = async (refreshToken) => {
    try {
        const res = await got
            .post(googleTokenUrl, {
            form: {
                grant_type: 'refresh_token',
                refresh_token: refreshToken,
                client_id: googleClientIdWeb,
                client_secret: googleClientSecretWeb,
            },
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        })
            .json();
        console.log(res, ' refresh token success');
        return res;
    }
    catch (e) {
        console.log(e, ' unable to refresh token');
    }
};
// New function for Mcp token exchange
export const getMcpUserTokens = async (code, redirectUri) => {
    try {
        const oauth2Client = new google.auth.OAuth2(googleClientIdMcp, // Use Mcp specific client ID
        googleClientSecretMcp, // Use Mcp specific client secret
        redirectUri // Use the provided redirect URI for this specific flow
        );
        const { tokens } = await oauth2Client.getToken(code);
        if (!tokens) {
            throw new Error('Failed to retrieve tokens from Google.');
        }
        return tokens;
    }
    catch (e) {
        console.error('Error in getMcpUserTokens:', e);
        throw e; // Re-throw the error
    }
};
// New function for Mcp token refresh
export const refreshMcpAccessToken = async (refreshToken) => {
    try {
        const res = await got
            .post(googleTokenUrl, {
            form: {
                grant_type: 'refresh_token',
                refresh_token: refreshToken,
                client_id: googleClientIdMcp, // Use Mcp specific client ID
                client_secret: googleClientSecretMcp, // Use Mcp specific client secret
            },
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        })
            .json();
        console.log(res, 'Mcp access token refresh success');
        return res;
    }
    catch (e) {
        console.error('Error in refreshMcpAccessToken:', e);
        throw e; // Re-throw
    }
};
export const googleCalendarIosRefreshToken = async (refreshToken) => {
    try {
        const res = await got
            .post(googleTokenUrl, {
            form: {
                grant_type: 'refresh_token',
                refresh_token: refreshToken,
                client_id: googleClientIdIos,
            },
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        })
            .json();
        console.log(res, ' refresh token success');
        return res;
    }
    catch (e) {
        console.log(e, ' unable to refresh token');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBRXRCLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxZQUFZLENBQUM7QUFFcEMsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBRTFCLE9BQU8sR0FBRyxNQUFNLGtCQUFrQixDQUFDO0FBQ25DLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sRUFDTCxxQkFBcUIsRUFDckIsdUJBQXVCLEVBQ3ZCLGlCQUFpQixFQUNqQixpQkFBaUIsRUFDakIsMkJBQTJCLEVBQzNCLHFCQUFxQixFQUNyQixjQUFjLEdBQ2YsTUFBTSxhQUFhLENBQUM7QUFHckIsT0FBTyxFQVFMLG1CQUFtQixFQUNuQix1QkFBdUIsRUFDdkIsaUJBQWlCLEVBQ2pCLHFCQUFxQixHQUN0QixNQUFNLGFBQWEsQ0FBQyxDQUFDLHNCQUFzQjtBQUM1QyxLQUFLLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDO0FBQ2xCLEtBQUssQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLENBQUM7QUFFdkIsTUFBTSxDQUFDLE1BQU0sNkJBQTZCLEdBQUcsS0FBSyxFQUFFLElBQVksRUFBRSxFQUFFO0lBQ2xFLElBQUksQ0FBQztRQUNILE1BQU0sWUFBWSxHQUFHLElBQUksTUFBTSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQ3pDLGlCQUFpQixFQUNqQixxQkFBcUIsRUFDckIscUJBQXFCLENBQ3RCLENBQUM7UUFFRixNQUFNLEVBQUUsTUFBTSxFQUFFLEdBQUcsTUFBTSxZQUFZLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxDQUFDO1FBRXJELE9BQU8sTUFBTSxDQUFDO0lBQ2hCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVB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Q0QsT0FBTyxFQUFFO2dCQUNQLGNBQWMsRUFBRSxtQ0FBbUM7YUFDcEQ7U0FDRixDQUFDO2FBQ0QsSUFBSSxFQUFFLENBQUM7UUFFVixPQUFPLENBQUMsR0FBRyxDQUFDLEdBQUcsRUFBRSx3QkFBd0IsQ0FBQyxDQUFDO1FBQzNDLE9BQU8sR0FBRyxDQUFDO0lBQ2IsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSwwQkFBMEIsQ0FBQyxDQUFDO0lBQzdDLENBQUM7QUFDSCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5cbmltcG9ydCB7IGdvb2dsZSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuXG5pbXBvcnQgZGF5anMgZnJvbSAnZGF5anMnO1xuXG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnO1xuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSc7XG5pbXBvcnQge1xuICBnb29nbGVBdXRoUmVkaXJlY3RVcmksXG4gIGdvb2dsZUNsaWVudElkQXRvbWljV2ViLFxuICBnb29nbGVDbGllbnRJZElvcyxcbiAgZ29vZ2xlQ2xpZW50SWRXZWIsXG4gIGdvb2dsZUNsaWVudFNlY3JldEF0b21pY1dlYixcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0V2ViLFxuICBnb29nbGVUb2tlblVybCxcbn0gZnJvbSAnLi9jb25zdGFudHMnO1xuaW1wb3J0IHsgUmVmcmVzaFRva2VuUmVzcG9uc2VCb2R5VHlwZSB9IGZyb20gJy4vdHlwZXMnO1xuXG5pbXBvcnQge1xuICBnb29nbGVBdXRoUmVkaXJlY3RVcmksXG4gIGdvb2dsZUNsaWVudElkQXRvbWljV2ViLFxuICBnb29nbGVDbGllbnRJZElvcyxcbiAgZ29vZ2xlQ2xpZW50SWRXZWIsXG4gIGdvb2dsZUNsaWVudFNlY3JldEF0b21pY1dlYixcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0V2ViLFxuICBnb29nbGVUb2tlblVybCxcbiAgZ29vZ2xlQ2xpZW50SWRHbWFpbCxcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0R21haWwsXG4gIGdvb2dsZUNsaWVudElkTWNwLFxuICBnb29nbGVDbGllbnRTZWNyZXRNY3AsXG59IGZyb20gJy4vY29uc3RhbnRzJzsgLy8gQWRkZWQgTWNwIGNvbnN0YW50c1xuZGF5anMuZXh0ZW5kKHV0Yyk7XG5kYXlqcy5leHRlbmQodGltZXpvbmUpO1xuXG5leHBvcnQgY29uc3QgZ2V0R29vZ2xlVG9rZW5BbmRSZWZyZXNoVG9rZW4gPSBhc3luYyAoY29kZTogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb2F1dGgyQ2xpZW50ID0gbmV3IGdvb2dsZS5hdXRoLk9BdXRoMihcbiAgICAgIGdvb2dsZUNsaWVudElkV2ViLFxuICAgICAgZ29vZ2xlQ2xpZW50U2VjcmV0V2ViLFxuICAgICAgZ29vZ2xlQXV0aFJlZGlyZWN0VXJpXG4gICAgKTtcblxuICAgIGNvbnN0IHsgdG9rZW5zIH0gPSBhd2FpdCBvYXV0aDJDbGllbnQuZ2V0VG9rZW4oY29kZSk7XG5cbiAgICByZXR1cm4gdG9rZW5zO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGdvb2dsZSB0b2tlbiBhbmQgcmVmcmVzaCB0b2tlbicpO1xuICAgIHRocm93IGU7IC8vIFJlLXRocm93IHRoZSBlcnJvciB0byBiZSBoYW5kbGVkIGJ5IHRoZSBjYWxsZXJcbiAgfVxufTtcblxuLy8gTmV3IGZ1bmN0aW9uIGZvciBHbWFpbCB0b2tlbiBleGNoYW5nZVxuZXhwb3J0IGNvbnN0IGdldEdtYWlsVXNlclRva2VucyA9IGFzeW5jIChcbiAgY29kZTogc3RyaW5nLFxuICByZWRpcmVjdFVyaTogc3RyaW5nXG4pOiBQcm9taXNlPGdvb2dsZS5hdXRoLkNyZWRlbnRpYWxzPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb2F1dGgyQ2xpZW50ID0gbmV3IGdvb2dsZS5hdXRoLk9BdXRoMihcbiAgICAgIGdvb2dsZUNsaWVudElkR21haWwsIC8vIFVzZSBHbWFpbCBzcGVjaWZpYyBjbGllbnQgSURcbiAgICAgIGdvb2dsZUNsaWVudFNlY3JldEdtYWlsLCAvLyBVc2UgR21haWwgc3BlY2lmaWMgY2xpZW50IHNlY3JldFxuICAgICAgcmVkaXJlY3RVcmkgLy8gVXNlIHRoZSBwcm92aWRlZCByZWRpcmVjdCBVUkkgZm9yIHRoaXMgc3BlY2lmaWMgZmxvd1xuICAgICk7XG5cbiAgICBjb25zdCB7IHRva2VucyB9ID0gYXdhaXQgb2F1dGgyQ2xpZW50LmdldFRva2VuKGNvZGUpO1xuICAgIGlmICghdG9rZW5zKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ0ZhaWxlZCB0byByZXRyaWV2ZSB0b2tlbnMgZnJvbSBHb29nbGUuJyk7XG4gICAgfVxuICAgIHJldHVybiB0b2tlbnM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBpbiBnZXRHbWFpbFVzZXJUb2tlbnM6JywgZSk7XG4gICAgdGhyb3cgZTsgLy8gUmUtdGhyb3cgdGhlIGVycm9yXG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnb29nbGVDYWxlbmRhckF0b21pY1dlYlJlZnJlc2hUb2tlbiA9IGFzeW5jIChcbiAgcmVmcmVzaFRva2VuOiBzdHJpbmdcbik6IFByb21pc2U8UmVmcmVzaFRva2VuUmVzcG9uc2VCb2R5VHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlczogUmVmcmVzaFRva2VuUmVzcG9uc2VCb2R5VHlwZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgZm9ybToge1xuICAgICAgICAgIGdyYW50X3R5cGU6ICdyZWZyZXNoX3Rva2VuJyxcbiAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgY2xpZW50X2lkOiBnb29nbGVDbGllbnRJZEF0b21pY1dlYixcbiAgICAgICAgICBjbGllbnRfc2VjcmV0OiBnb29nbGVDbGllbnRTZWNyZXRBdG9taWNXZWIsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL3gtd3d3LWZvcm0tdXJsZW5jb2RlZCcsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZWZyZXNoIHRva2VuIHN1Y2Nlc3MnKTtcbiAgICByZXR1cm4gcmVzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcmVmcmVzaCB0b2tlbicpO1xuICAgIHRocm93IGU7IC8vIFJlLXRocm93XG4gIH1cbn07XG5cbi8vIE5ldyBmdW5jdGlvbiBmb3IgR21haWwgdG9rZW4gcmVmcmVzaFxuZXhwb3J0IGNvbnN0IHJlZnJlc2hHbWFpbEFjY2Vzc1Rva2VuID0gYXN5bmMgKFxuICByZWZyZXNoVG9rZW46IHN0cmluZ1xuKTogUHJvbWlzZTxSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzOiBSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlID0gYXdhaXQgZ290XG4gICAgICAucG9zdChnb29nbGVUb2tlblVybCwge1xuICAgICAgICBmb3JtOiB7XG4gICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcbiAgICAgICAgICBjbGllbnRfaWQ6IGdvb2dsZUNsaWVudElkR21haWwsIC8vIFVzZSBHbWFpbCBzcGVjaWZpYyBjbGllbnQgSURcbiAgICAgICAgICBjbGllbnRfc2VjcmV0OiBnb29nbGVDbGllbnRTZWNyZXRHbWFpbCwgLy8gVXNlIEdtYWlsIHNwZWNpZmljIGNsaWVudCBzZWNyZXRcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnR21haWwgYWNjZXNzIHRva2VuIHJlZnJlc2ggc3VjY2VzcycpO1xuICAgIHJldHVybiByZXM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBpbiByZWZyZXNoR21haWxBY2Nlc3NUb2tlbjonLCBlKTtcbiAgICB0aHJvdyBlOyAvLyBSZS10aHJvd1xuICB9XG59O1xuZXhwb3J0IGNvbnN0IGdvb2dsZUNhbGVuZGFyV2ViUmVmcmVzaFRva2VuID0gYXN5bmMgKFxuICByZWZyZXNoVG9rZW46IHN0cmluZ1xuKTogUHJvbWlzZTxSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzOiBSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlID0gYXdhaXQgZ290XG4gICAgICAucG9zdChnb29nbGVUb2tlblVybCwge1xuICAgICAgICBmb3JtOiB7XG4gICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcbiAgICAgICAgICBjbGllbnRfaWQ6IGdvb2dsZUNsaWVudElkV2ViLFxuICAgICAgICAgIGNsaWVudF9zZWNyZXQ6IGdvb2dsZUNsaWVudFNlY3JldFdlYixcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlZnJlc2ggdG9rZW4gc3VjY2VzcycpO1xuICAgIHJldHVybiByZXM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZWZyZXNoIHRva2VuJyk7XG4gIH1cbn07XG5cbi8vIE5ldyBmdW5jdGlvbiBmb3IgTWNwIHRva2VuIGV4Y2hhbmdlXG5leHBvcnQgY29uc3QgZ2V0TWNwVXNlclRva2VucyA9IGFzeW5jIChcbiAgY29kZTogc3RyaW5nLFxuICByZWRpcmVjdFVyaTogc3RyaW5nXG4pOiBQcm9taXNlPGdvb2dsZS5hdXRoLkNyZWRlbnRpYWxzPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb2F1dGgyQ2xpZW50ID0gbmV3IGdvb2dsZS5hdXRoLk9BdXRoMihcbiAgICAgIGdvb2dsZUNsaWVudElkTWNwLCAvLyBVc2UgTWNwIHNwZWNpZmljIGNsaWVudCBJRFxuICAgICAgZ29vZ2xlQ2xpZW50U2VjcmV0TWNwLCAvLyBVc2UgTWNwIHNwZWNpZmljIGNsaWVudCBzZWNyZXRcbiAgICAgIHJlZGlyZWN0VXJpIC8vIFVzZSB0aGUgcHJvdmlkZWQgcmVkaXJlY3QgVVJJIGZvciB0aGlzIHNwZWNpZmljIGZsb3dcbiAgICApO1xuXG4gICAgY29uc3QgeyB0b2tlbnMgfSA9IGF3YWl0IG9hdXRoMkNsaWVudC5nZXRUb2tlbihjb2RlKTtcbiAgICBpZiAoIXRva2Vucykge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdGYWlsZWQgdG8gcmV0cmlldmUgdG9rZW5zIGZyb20gR29vZ2xlLicpO1xuICAgIH1cbiAgICByZXR1cm4gdG9rZW5zO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgaW4gZ2V0TWNwVXNlclRva2VuczonLCBlKTtcbiAgICB0aHJvdyBlOyAvLyBSZS10aHJvdyB0aGUgZXJyb3JcbiAgfVxufTtcblxuLy8gTmV3IGZ1bmN0aW9uIGZvciBNY3AgdG9rZW4gcmVmcmVzaFxuZXhwb3J0IGNvbnN0IHJlZnJlc2hNY3BBY2Nlc3NUb2tlbiA9IGFzeW5jIChcbiAgcmVmcmVzaFRva2VuOiBzdHJpbmdcbik6IFByb21pc2U8UmVmcmVzaFRva2VuUmVzcG9uc2VCb2R5VHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlczogUmVmcmVzaFRva2VuUmVzcG9uc2VCb2R5VHlwZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgZm9ybToge1xuICAgICAgICAgIGdyYW50X3R5cGU6ICdyZWZyZXNoX3Rva2VuJyxcbiAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgY2xpZW50X2lkOiBnb29nbGVDbGllbnRJZE1jcCwgLy8gVXNlIE1jcCBzcGVjaWZpYyBjbGllbnQgSURcbiAgICAgICAgICBjbGllbnRfc2VjcmV0OiBnb29nbGVDbGllbnRTZWNyZXRNY3AsIC8vIFVzZSBNY3Agc3BlY2lmaWMgY2xpZW50IHNlY3JldFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICdNY3AgYWNjZXNzIHRva2VuIHJlZnJlc2ggc3VjY2VzcycpO1xuICAgIHJldHVybiByZXM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBpbiByZWZyZXNoTWNwQWNjZXNzVG9rZW46JywgZSk7XG4gICAgdGhyb3cgZTsgLy8gUmUtdGhyb3dcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdvb2dsZUNhbGVuZGFySW9zUmVmcmVzaFRva2VuID0gYXN5bmMgKFxuICByZWZyZXNoVG9rZW46IHN0cmluZ1xuKTogUHJvbWlzZTxSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzOiBSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlID0gYXdhaXQgZ290XG4gICAgICAucG9zdChnb29nbGVUb2tlblVybCwge1xuICAgICAgICBmb3JtOiB7XG4gICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcbiAgICAgICAgICBjbGllbnRfaWQ6IGdvb2dsZUNsaWVudElkSW9zLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVmcmVzaCB0b2tlbiBzdWNjZXNzJyk7XG4gICAgcmV0dXJuIHJlcztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlZnJlc2ggdG9rZW4nKTtcbiAgfVxufTtcbiJdfQ==
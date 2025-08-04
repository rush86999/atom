"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const msal_node_1 = require("@azure/msal-node");
const nextjs_1 = require("supertokens-node/nextjs");
const express_1 = require("supertokens-node/recipe/session/framework/express");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../../../config/backendConfig"); // Adjusted path
const logger_1 = require("../../../../../../project/functions/_utils/logger");
// TODO: Move these to a central constants file and manage via environment variables
const MSTEAMS_CLIENT_ID = process.env.MSTEAMS_CLIENT_ID || 'YOUR_MSTEAMS_APP_CLIENT_ID';
const MSTEAMS_CLIENT_SECRET = process.env.MSTEAMS_CLIENT_SECRET || 'YOUR_MSTEAMS_APP_CLIENT_SECRET'; // Needed for token exchange in callback
const MSTEAMS_REDIRECT_URI = process.env.MSTEAMS_REDIRECT_URI ||
    'http://localhost:3000/api/atom/auth/msteams/callback';
const MSTEAMS_AUTHORITY = process.env.MSTEAMS_AUTHORITY || 'https://login.microsoftonline.com/common'; // Or your tenant ID
// Define the scopes required for reading chats and channel messages
const MSTEAMS_SCOPES = [
    'Chat.Read',
    'ChannelMessage.Read.All',
    'User.Read',
    'offline_access',
];
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
const msalConfig = {
    auth: {
        clientId: MSTEAMS_CLIENT_ID,
        authority: MSTEAMS_AUTHORITY,
        clientSecret: MSTEAMS_CLIENT_SECRET, // Required for confidential client flows like auth code
    },
    system: {
        loggerOptions: {
            loggerCallback(loglevel, message, containsPii) {
                // console.log(`MSAL Log (${LogLevel[loglevel]}): ${message}`);
            },
            piiLoggingEnabled: false,
            logLevel: msal_node_1.LogLevel.Warning,
        },
    },
};
async function handler(req, res) {
    await (0, nextjs_1.superTokensNextWrapper)(async (next) => (0, express_1.verifySession)()(req, res, next), req, res);
    const userId = req.session?.getUserId();
    if (!userId) {
        logger_1.logger.warn('[MSTeamsAuthInitiate] User not authenticated.');
        return res.status(401).json({ message: 'Authentication required.' });
    }
    if (!MSTEAMS_CLIENT_ID ||
        MSTEAMS_CLIENT_ID === 'YOUR_MSTEAMS_APP_CLIENT_ID') {
        logger_1.logger.error('[MSTeamsAuthInitiate] MS Teams Client ID not configured.');
        return res
            .status(500)
            .json({ message: 'MS Teams OAuth configuration error on server.' });
    }
    const pca = new msal_node_1.PublicClientApplication(msalConfig); // For auth code flow, server-side usually uses ConfidentialClientApplication
    // NOTE: For server-side confidential client flow (which is typical when you have a client secret),
    // you'd use ConfidentialClientApplication. However, the initial redirect can be constructed
    // similarly. The crucial part is handling the secret securely in the callback.
    // The msal-node library's examples often show PublicClientApplication for some flows,
    // but for web apps exchanging code for token with a secret, ConfidentialClientApplication is standard.
    // Let's proceed with constructing the URL, the PCA/CCA choice primarily affects token acquisition.
    const authCodeUrlParameters = {
        scopes: MSTEAMS_SCOPES,
        redirectUri: MSTEAMS_REDIRECT_URI,
        state: userId, // Using userId as state to verify in callback & link tokens
        prompt: 'select_account', // Can be 'login', 'consent', 'select_account', or 'none'
    };
    try {
        // If using ConfidentialClientApplication:
        // const cca = new ConfidentialClientApplication(msalConfig);
        // const authUrl = await cca.getAuthCodeUrl(authCodeUrlParameters);
        // For PublicClientApplication (less common for server-side confidential handling but works for URL gen):
        const authUrl = await pca.getAuthCodeUrl(authCodeUrlParameters);
        logger_1.logger.info(`[MSTeamsAuthInitiate] Redirecting user ${userId} to MS Teams auth URL.`);
        res.redirect(authUrl);
    }
    catch (error) {
        logger_1.logger.error('[MSTeamsAuthInitiate] Error generating MS Teams auth URL:', error);
        res
            .status(500)
            .json({ message: 'Failed to initiate MS Teams authentication.' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5pdGlhdGUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbml0aWF0ZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQW1EQSwwQkErREM7QUFqSEQsZ0RBSzBCO0FBQzFCLG9EQUFpRTtBQUNqRSwrRUFBa0Y7QUFDbEYsd0VBQTJDO0FBQzNDLHVFQUFvRSxDQUFDLGdCQUFnQjtBQUNyRiw4RUFBMkU7QUFFM0Usb0ZBQW9GO0FBQ3BGLE1BQU0saUJBQWlCLEdBQ3JCLE9BQU8sQ0FBQyxHQUFHLENBQUMsaUJBQWlCLElBQUksNEJBQTRCLENBQUM7QUFDaEUsTUFBTSxxQkFBcUIsR0FDekIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxxQkFBcUIsSUFBSSxnQ0FBZ0MsQ0FBQyxDQUFDLHdDQUF3QztBQUNqSCxNQUFNLG9CQUFvQixHQUN4QixPQUFPLENBQUMsR0FBRyxDQUFDLG9CQUFvQjtJQUNoQyxzREFBc0QsQ0FBQztBQUN6RCxNQUFNLGlCQUFpQixHQUNyQixPQUFPLENBQUMsR0FBRyxDQUFDLGlCQUFpQixJQUFJLDBDQUEwQyxDQUFDLENBQUMsb0JBQW9CO0FBRW5HLG9FQUFvRTtBQUNwRSxNQUFNLGNBQWMsR0FBRztJQUNyQixXQUFXO0lBQ1gseUJBQXlCO0lBQ3pCLFdBQVc7SUFDWCxnQkFBZ0I7Q0FDakIsQ0FBQztBQUVGLDBCQUFXLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUM7QUFFbEMsTUFBTSxVQUFVLEdBQWtCO0lBQ2hDLElBQUksRUFBRTtRQUNKLFFBQVEsRUFBRSxpQkFBaUI7UUFDM0IsU0FBUyxFQUFFLGlCQUFpQjtRQUM1QixZQUFZLEVBQUUscUJBQXFCLEVBQUUsd0RBQXdEO0tBQzlGO0lBQ0QsTUFBTSxFQUFFO1FBQ04sYUFBYSxFQUFFO1lBQ2IsY0FBYyxDQUFDLFFBQVEsRUFBRSxPQUFPLEVBQUUsV0FBVztnQkFDM0MsK0RBQStEO1lBQ2pFLENBQUM7WUFDRCxpQkFBaUIsRUFBRSxLQUFLO1lBQ3hCLFFBQVEsRUFBRSxvQkFBUSxDQUFDLE9BQU87U0FDM0I7S0FDRjtDQUNGLENBQUM7QUFFYSxLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUFvQjtJQUVwQixNQUFNLElBQUEsK0JBQXNCLEVBQzFCLEtBQUssRUFBRSxJQUFJLEVBQUUsRUFBRSxDQUFDLElBQUEsdUJBQWEsR0FBRSxDQUFDLEdBQVUsRUFBRSxHQUFVLEVBQUUsSUFBSSxDQUFDLEVBQzdELEdBQUcsRUFDSCxHQUFHLENBQ0osQ0FBQztJQUVGLE1BQU0sTUFBTSxHQUFHLEdBQUcsQ0FBQyxPQUFPLEVBQUUsU0FBUyxFQUFFLENBQUM7SUFDeEMsSUFBSSxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQ1osZUFBTSxDQUFDLElBQUksQ0FBQywrQ0FBK0MsQ0FBQyxDQUFDO1FBQzdELE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsMEJBQTBCLEVBQUUsQ0FBQyxDQUFDO0lBQ3ZFLENBQUM7SUFFRCxJQUNFLENBQUMsaUJBQWlCO1FBQ2xCLGlCQUFpQixLQUFLLDRCQUE0QixFQUNsRCxDQUFDO1FBQ0QsZUFBTSxDQUFDLEtBQUssQ0FBQywwREFBMEQsQ0FBQyxDQUFDO1FBQ3pFLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsK0NBQStDLEVBQUUsQ0FBQyxDQUFDO0lBQ3hFLENBQUM7SUFFRCxNQUFNLEdBQUcsR0FBRyxJQUFJLG1DQUF1QixDQUFDLFVBQVUsQ0FBQyxDQUFDLENBQUMsNkVBQTZFO0lBRWxJLG1HQUFtRztJQUNuRyw0RkFBNEY7SUFDNUYsK0VBQStFO0lBQy9FLHNGQUFzRjtJQUN0Rix1R0FBdUc7SUFDdkcsbUdBQW1HO0lBRW5HLE1BQU0scUJBQXFCLEdBQTRCO1FBQ3JELE1BQU0sRUFBRSxjQUFjO1FBQ3RCLFdBQVcsRUFBRSxvQkFBb0I7UUFDakMsS0FBSyxFQUFFLE1BQU0sRUFBRSw0REFBNEQ7UUFDM0UsTUFBTSxFQUFFLGdCQUFnQixFQUFFLHlEQUF5RDtLQUNwRixDQUFDO0lBRUYsSUFBSSxDQUFDO1FBQ0gsMENBQTBDO1FBQzFDLDZEQUE2RDtRQUM3RCxtRUFBbUU7UUFFbkUseUdBQXlHO1FBQ3pHLE1BQU0sT0FBTyxHQUFHLE1BQU0sR0FBRyxDQUFDLGNBQWMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDO1FBRWhFLGVBQU0sQ0FBQyxJQUFJLENBQ1QsMENBQTBDLE1BQU0sd0JBQXdCLENBQ3pFLENBQUM7UUFDRixHQUFHLENBQUMsUUFBUSxDQUFDLE9BQU8sQ0FBQyxDQUFDO0lBQ3hCLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsZUFBTSxDQUFDLEtBQUssQ0FDViwyREFBMkQsRUFDM0QsS0FBSyxDQUNOLENBQUM7UUFDRixHQUFHO2FBQ0EsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSw2Q0FBNkMsRUFBRSxDQUFDLENBQUM7SUFDdEUsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7XG4gIFB1YmxpY0NsaWVudEFwcGxpY2F0aW9uLFxuICBDb25maWd1cmF0aW9uLFxuICBMb2dMZXZlbCxcbiAgQXV0aG9yaXphdGlvblVybFJlcXVlc3QsXG59IGZyb20gJ0BhenVyZS9tc2FsLW5vZGUnO1xuaW1wb3J0IHsgc3VwZXJUb2tlbnNOZXh0V3JhcHBlciB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvbmV4dGpzJztcbmltcG9ydCB7IHZlcmlmeVNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uL2ZyYW1ld29yay9leHByZXNzJztcbmltcG9ydCBzdXBlcnRva2VucyBmcm9tICdzdXBlcnRva2Vucy1ub2RlJztcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi8uLi8uLi8uLi9jb25maWcvYmFja2VuZENvbmZpZyc7IC8vIEFkanVzdGVkIHBhdGhcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uLy4uLy4uLy4uLy4uL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9sb2dnZXInO1xuXG4vLyBUT0RPOiBNb3ZlIHRoZXNlIHRvIGEgY2VudHJhbCBjb25zdGFudHMgZmlsZSBhbmQgbWFuYWdlIHZpYSBlbnZpcm9ubWVudCB2YXJpYWJsZXNcbmNvbnN0IE1TVEVBTVNfQ0xJRU5UX0lEID1cbiAgcHJvY2Vzcy5lbnYuTVNURUFNU19DTElFTlRfSUQgfHwgJ1lPVVJfTVNURUFNU19BUFBfQ0xJRU5UX0lEJztcbmNvbnN0IE1TVEVBTVNfQ0xJRU5UX1NFQ1JFVCA9XG4gIHByb2Nlc3MuZW52Lk1TVEVBTVNfQ0xJRU5UX1NFQ1JFVCB8fCAnWU9VUl9NU1RFQU1TX0FQUF9DTElFTlRfU0VDUkVUJzsgLy8gTmVlZGVkIGZvciB0b2tlbiBleGNoYW5nZSBpbiBjYWxsYmFja1xuY29uc3QgTVNURUFNU19SRURJUkVDVF9VUkkgPVxuICBwcm9jZXNzLmVudi5NU1RFQU1TX1JFRElSRUNUX1VSSSB8fFxuICAnaHR0cDovL2xvY2FsaG9zdDozMDAwL2FwaS9hdG9tL2F1dGgvbXN0ZWFtcy9jYWxsYmFjayc7XG5jb25zdCBNU1RFQU1TX0FVVEhPUklUWSA9XG4gIHByb2Nlc3MuZW52Lk1TVEVBTVNfQVVUSE9SSVRZIHx8ICdodHRwczovL2xvZ2luLm1pY3Jvc29mdG9ubGluZS5jb20vY29tbW9uJzsgLy8gT3IgeW91ciB0ZW5hbnQgSURcblxuLy8gRGVmaW5lIHRoZSBzY29wZXMgcmVxdWlyZWQgZm9yIHJlYWRpbmcgY2hhdHMgYW5kIGNoYW5uZWwgbWVzc2FnZXNcbmNvbnN0IE1TVEVBTVNfU0NPUEVTID0gW1xuICAnQ2hhdC5SZWFkJyxcbiAgJ0NoYW5uZWxNZXNzYWdlLlJlYWQuQWxsJyxcbiAgJ1VzZXIuUmVhZCcsXG4gICdvZmZsaW5lX2FjY2VzcycsXG5dO1xuXG5zdXBlcnRva2Vucy5pbml0KGJhY2tlbmRDb25maWcoKSk7XG5cbmNvbnN0IG1zYWxDb25maWc6IENvbmZpZ3VyYXRpb24gPSB7XG4gIGF1dGg6IHtcbiAgICBjbGllbnRJZDogTVNURUFNU19DTElFTlRfSUQsXG4gICAgYXV0aG9yaXR5OiBNU1RFQU1TX0FVVEhPUklUWSxcbiAgICBjbGllbnRTZWNyZXQ6IE1TVEVBTVNfQ0xJRU5UX1NFQ1JFVCwgLy8gUmVxdWlyZWQgZm9yIGNvbmZpZGVudGlhbCBjbGllbnQgZmxvd3MgbGlrZSBhdXRoIGNvZGVcbiAgfSxcbiAgc3lzdGVtOiB7XG4gICAgbG9nZ2VyT3B0aW9uczoge1xuICAgICAgbG9nZ2VyQ2FsbGJhY2sobG9nbGV2ZWwsIG1lc3NhZ2UsIGNvbnRhaW5zUGlpKSB7XG4gICAgICAgIC8vIGNvbnNvbGUubG9nKGBNU0FMIExvZyAoJHtMb2dMZXZlbFtsb2dsZXZlbF19KTogJHttZXNzYWdlfWApO1xuICAgICAgfSxcbiAgICAgIHBpaUxvZ2dpbmdFbmFibGVkOiBmYWxzZSxcbiAgICAgIGxvZ0xldmVsOiBMb2dMZXZlbC5XYXJuaW5nLFxuICAgIH0sXG4gIH0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCBhc3luYyBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZVxuKSB7XG4gIGF3YWl0IHN1cGVyVG9rZW5zTmV4dFdyYXBwZXIoXG4gICAgYXN5bmMgKG5leHQpID0+IHZlcmlmeVNlc3Npb24oKShyZXEgYXMgYW55LCByZXMgYXMgYW55LCBuZXh0KSxcbiAgICByZXEsXG4gICAgcmVzXG4gICk7XG5cbiAgY29uc3QgdXNlcklkID0gcmVxLnNlc3Npb24/LmdldFVzZXJJZCgpO1xuICBpZiAoIXVzZXJJZCkge1xuICAgIGxvZ2dlci53YXJuKCdbTVNUZWFtc0F1dGhJbml0aWF0ZV0gVXNlciBub3QgYXV0aGVudGljYXRlZC4nKTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDEpLmpzb24oeyBtZXNzYWdlOiAnQXV0aGVudGljYXRpb24gcmVxdWlyZWQuJyB9KTtcbiAgfVxuXG4gIGlmIChcbiAgICAhTVNURUFNU19DTElFTlRfSUQgfHxcbiAgICBNU1RFQU1TX0NMSUVOVF9JRCA9PT0gJ1lPVVJfTVNURUFNU19BUFBfQ0xJRU5UX0lEJ1xuICApIHtcbiAgICBsb2dnZXIuZXJyb3IoJ1tNU1RlYW1zQXV0aEluaXRpYXRlXSBNUyBUZWFtcyBDbGllbnQgSUQgbm90IGNvbmZpZ3VyZWQuJyk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7IG1lc3NhZ2U6ICdNUyBUZWFtcyBPQXV0aCBjb25maWd1cmF0aW9uIGVycm9yIG9uIHNlcnZlci4nIH0pO1xuICB9XG5cbiAgY29uc3QgcGNhID0gbmV3IFB1YmxpY0NsaWVudEFwcGxpY2F0aW9uKG1zYWxDb25maWcpOyAvLyBGb3IgYXV0aCBjb2RlIGZsb3csIHNlcnZlci1zaWRlIHVzdWFsbHkgdXNlcyBDb25maWRlbnRpYWxDbGllbnRBcHBsaWNhdGlvblxuXG4gIC8vIE5PVEU6IEZvciBzZXJ2ZXItc2lkZSBjb25maWRlbnRpYWwgY2xpZW50IGZsb3cgKHdoaWNoIGlzIHR5cGljYWwgd2hlbiB5b3UgaGF2ZSBhIGNsaWVudCBzZWNyZXQpLFxuICAvLyB5b3UnZCB1c2UgQ29uZmlkZW50aWFsQ2xpZW50QXBwbGljYXRpb24uIEhvd2V2ZXIsIHRoZSBpbml0aWFsIHJlZGlyZWN0IGNhbiBiZSBjb25zdHJ1Y3RlZFxuICAvLyBzaW1pbGFybHkuIFRoZSBjcnVjaWFsIHBhcnQgaXMgaGFuZGxpbmcgdGhlIHNlY3JldCBzZWN1cmVseSBpbiB0aGUgY2FsbGJhY2suXG4gIC8vIFRoZSBtc2FsLW5vZGUgbGlicmFyeSdzIGV4YW1wbGVzIG9mdGVuIHNob3cgUHVibGljQ2xpZW50QXBwbGljYXRpb24gZm9yIHNvbWUgZmxvd3MsXG4gIC8vIGJ1dCBmb3Igd2ViIGFwcHMgZXhjaGFuZ2luZyBjb2RlIGZvciB0b2tlbiB3aXRoIGEgc2VjcmV0LCBDb25maWRlbnRpYWxDbGllbnRBcHBsaWNhdGlvbiBpcyBzdGFuZGFyZC5cbiAgLy8gTGV0J3MgcHJvY2VlZCB3aXRoIGNvbnN0cnVjdGluZyB0aGUgVVJMLCB0aGUgUENBL0NDQSBjaG9pY2UgcHJpbWFyaWx5IGFmZmVjdHMgdG9rZW4gYWNxdWlzaXRpb24uXG5cbiAgY29uc3QgYXV0aENvZGVVcmxQYXJhbWV0ZXJzOiBBdXRob3JpemF0aW9uVXJsUmVxdWVzdCA9IHtcbiAgICBzY29wZXM6IE1TVEVBTVNfU0NPUEVTLFxuICAgIHJlZGlyZWN0VXJpOiBNU1RFQU1TX1JFRElSRUNUX1VSSSxcbiAgICBzdGF0ZTogdXNlcklkLCAvLyBVc2luZyB1c2VySWQgYXMgc3RhdGUgdG8gdmVyaWZ5IGluIGNhbGxiYWNrICYgbGluayB0b2tlbnNcbiAgICBwcm9tcHQ6ICdzZWxlY3RfYWNjb3VudCcsIC8vIENhbiBiZSAnbG9naW4nLCAnY29uc2VudCcsICdzZWxlY3RfYWNjb3VudCcsIG9yICdub25lJ1xuICB9O1xuXG4gIHRyeSB7XG4gICAgLy8gSWYgdXNpbmcgQ29uZmlkZW50aWFsQ2xpZW50QXBwbGljYXRpb246XG4gICAgLy8gY29uc3QgY2NhID0gbmV3IENvbmZpZGVudGlhbENsaWVudEFwcGxpY2F0aW9uKG1zYWxDb25maWcpO1xuICAgIC8vIGNvbnN0IGF1dGhVcmwgPSBhd2FpdCBjY2EuZ2V0QXV0aENvZGVVcmwoYXV0aENvZGVVcmxQYXJhbWV0ZXJzKTtcblxuICAgIC8vIEZvciBQdWJsaWNDbGllbnRBcHBsaWNhdGlvbiAobGVzcyBjb21tb24gZm9yIHNlcnZlci1zaWRlIGNvbmZpZGVudGlhbCBoYW5kbGluZyBidXQgd29ya3MgZm9yIFVSTCBnZW4pOlxuICAgIGNvbnN0IGF1dGhVcmwgPSBhd2FpdCBwY2EuZ2V0QXV0aENvZGVVcmwoYXV0aENvZGVVcmxQYXJhbWV0ZXJzKTtcblxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtNU1RlYW1zQXV0aEluaXRpYXRlXSBSZWRpcmVjdGluZyB1c2VyICR7dXNlcklkfSB0byBNUyBUZWFtcyBhdXRoIFVSTC5gXG4gICAgKTtcbiAgICByZXMucmVkaXJlY3QoYXV0aFVybCk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgJ1tNU1RlYW1zQXV0aEluaXRpYXRlXSBFcnJvciBnZW5lcmF0aW5nIE1TIFRlYW1zIGF1dGggVVJMOicsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgbWVzc2FnZTogJ0ZhaWxlZCB0byBpbml0aWF0ZSBNUyBUZWFtcyBhdXRoZW50aWNhdGlvbi4nIH0pO1xuICB9XG59XG4iXX0=
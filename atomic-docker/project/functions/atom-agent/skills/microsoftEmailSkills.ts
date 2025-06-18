import got from 'got';
import {
  ATOM_MSGRAPH_CLIENT_ID,
  ATOM_MSGRAPH_CLIENT_SECRET,
  ATOM_MSGRAPH_TENANT_ID,
  MSGRAPH_OAUTH_AUTHORITY_BASE,
  MSGRAPH_API_SCOPES,
  ATOM_MSGRAPH_REDIRECT_URI,
} from '../_libs/constants';
import { getAtomMicrosoftGraphTokens, saveAtomMicrosoftGraphTokens, deleteAtomMicrosoftGraphTokens } from '../_libs/token-utils';
import { Email, EmailDetails, ReadEmailResponse, SendEmailResponse } from '../types'; // Assuming types are compatible

interface MicrosoftGraphTokenResponse {
    token_type: string;
    scope: string;
    expires_in: number; // Seconds
    access_token: string;
    refresh_token?: string;
}

// Internal helper function to refresh Microsoft Graph token
// This is duplicated from microsoftCalendarSkills.ts.
// TODO: Refactor this into a shared utility, possibly in token-utils.ts if it can be made generic enough
// or a new msal-token-utils.ts if using MSAL.js library directly.
async function refreshMicrosoftGraphToken(userId: string, refreshToken: string, existingAppEmail?: string | null): Promise<string | null> {
    if (!ATOM_MSGRAPH_CLIENT_ID || !ATOM_MSGRAPH_CLIENT_SECRET || !ATOM_MSGRAPH_TENANT_ID || !ATOM_MSGRAPH_REDIRECT_URI) {
        console.error('Microsoft Graph client credentials or tenant ID or redirect URI not configured for token refresh.');
        return null;
    }
    const tokenEndpoint = `${MSGRAPH_OAUTH_AUTHORITY_BASE}${ATOM_MSGRAPH_TENANT_ID}/oauth2/v2.0/token`;

    try {
        console.log(`Attempting to refresh Microsoft Graph token for userId (email skills): ${userId}`);
        const response = await got.post(tokenEndpoint, {
            form: {
                client_id: ATOM_MSGRAPH_CLIENT_ID,
                client_secret: ATOM_MSGRAPH_CLIENT_SECRET,
                scope: MSGRAPH_API_SCOPES.join(' '),
                refresh_token: refreshToken,
                grant_type: 'refresh_token',
                redirect_uri: ATOM_MSGRAPH_REDIRECT_URI,
            },
            responseType: 'json',
        });

        const newTokens = response.body as MicrosoftGraphTokenResponse;
        if (newTokens.access_token && newTokens.expires_in) {
            const expiryDate = Date.now() + (newTokens.expires_in * 1000);
            await saveAtomMicrosoftGraphTokens(userId, {
                access_token: newTokens.access_token,
                refresh_token: newTokens.refresh_token || refreshToken,
                expiry_date: expiryDate,
                scope: newTokens.scope,
                token_type: newTokens.token_type,
            }, existingAppEmail);

            console.log(`Successfully refreshed and saved Microsoft Graph token for userId (email skills): ${userId}`);
            return newTokens.access_token;
        } else {
            console.error('Microsoft Graph token refresh response missing access_token or expires_in (email skills):', newTokens);
            return null;
        }
    } catch (error: any) {
        console.error(`Error refreshing Microsoft Graph token for userId (email skills) ${userId}:`, error.message);
        if (error.response?.body) {
            console.error("MS Graph Refresh Token Error Response (email skills):", error.response.body);
            const bodyError = error.response.body as any;
            if (bodyError.error === 'invalid_grant') {
                console.error(`Refresh token invalid for userId (email skills) ${userId}. Deleting stored tokens.`);
                await deleteAtomMicrosoftGraphTokens(userId);
            }
        }
        return null;
    }
}

export async function listRecentEmailsMicrosoft(userId: string, limit: number = 10): Promise<Email[]> {
    console.log(`Attempting to list Microsoft Graph emails for userId: ${userId}`);
    let tokens = await getAtomMicrosoftGraphTokens(userId);

    if (!tokens?.access_token) {
        console.error(`No valid Microsoft Graph tokens for userId: ${userId}. User needs to authenticate.`);
        return [];
    }

    const callGraphApi = async (accessToken: string): Promise<Email[]> => {
        const listMessagesUrl = `https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$top=${limit}&$select=id,subject,from,toRecipients,receivedDateTime,bodyPreview,isRead&$orderby=receivedDateTime desc`;

        try {
            const response: any = await got.get(listMessagesUrl, {
                headers: { 'Authorization': `Bearer ${accessToken}` },
                responseType: 'json',
            });

            const graphMessages = response.body.value || [];
            return graphMessages.map((msg: any) => ({
                id: msg.id,
                summary: msg.subject || 'No Subject', // Not used in Email type directly, but good to have
                description: msg.bodyPreview || undefined, // For Email type, bodyPreview goes to body for list
                body: msg.bodyPreview || '', // For list view, snippet/bodyPreview is used
                sender: msg.from?.emailAddress?.address ? `${msg.from.emailAddress.name} <${msg.from.emailAddress.address}>` : 'Unknown Sender',
                recipient: msg.toRecipients?.map((r: any) => `${r.emailAddress.name} <${r.emailAddress.address}>`).join(', ') || '',
                subject: msg.subject || 'No Subject',
                timestamp: new Date(msg.receivedDateTime + 'Z').toISOString(), // Ensure ISO string
                read: msg.isRead !== null && msg.isRead !== undefined ? msg.isRead : true, // Assume read if isRead is not explicitly false
                htmlLink: msg.webLink || undefined, // Microsoft Graph provides webLink for messages
            }));
        } catch (error: any) {
            if (error.response?.statusCode === 401 && tokens?.refresh_token) {
                console.log(`MS Graph access token expired for userId ${userId} (list emails). Attempting refresh.`);
                const newAccessToken = await refreshMicrosoftGraphToken(userId, tokens.refresh_token, tokens.appEmail);
                if (newAccessToken) {
                    tokens.access_token = newAccessToken;
                    return callGraphApi(newAccessToken);
                } else {
                    console.error(`Failed to refresh MS Graph token for userId ${userId} (list emails).`);
                    return [];
                }
            }
            console.error(`Error fetching Microsoft Graph emails for userId ${userId}:`, error.message);
            if (error.response?.body) console.error("MS Graph API Error (list emails):", error.response.body);
            return [];
        }
    };
    return callGraphApi(tokens.access_token);
}

export async function readEmailMicrosoft(userId: string, emailId: string): Promise<ReadEmailResponse> {
    console.log(`Attempting to read Microsoft Graph emailId: ${emailId} for userId: ${userId}`);
    let tokens = await getAtomMicrosoftGraphTokens(userId);

    if (!tokens?.access_token) {
        return { success: false, message: 'Authentication required. Please connect your Microsoft Account.' };
    }

    const callGraphApi = async (accessToken: string): Promise<ReadEmailResponse> => {
        const messageUrl = `https://graph.microsoft.com/v1.0/me/messages/${emailId}?$select=id,subject,from,toRecipients,receivedDateTime,body,isRead,webLink`;
        try {
            const response: any = await got.get(messageUrl, {
                headers: { 'Authorization': `Bearer ${accessToken}` },
                responseType: 'json',
            });

            const msg = response.body;
            const email: Email = {
                id: msg.id,
                summary: msg.subject || 'No Subject',
                description: msg.bodyPreview || undefined,
                body: msg.body?.contentType === 'HTML' || msg.body?.contentType === 'text' ? msg.body.content : '', // Prioritize text if HTML
                sender: msg.from?.emailAddress?.address ? `${msg.from.emailAddress.name} <${msg.from.emailAddress.address}>` : 'Unknown Sender',
                recipient: msg.toRecipients?.map((r: any) => `${r.emailAddress.name} <${r.emailAddress.address}>`).join(', ') || '',
                subject: msg.subject || 'No Subject',
                timestamp: new Date(msg.receivedDateTime + 'Z').toISOString(),
                read: msg.isRead !== null && msg.isRead !== undefined ? msg.isRead : true,
                htmlLink: msg.webLink || undefined,
            };

            if (msg.isRead === false) {
                console.log(`Marking email ${emailId} as read for user ${userId}`);
                await got.patch(`https://graph.microsoft.com/v1.0/me/messages/${emailId}`, {
                    headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
                    json: { isRead: true },
                });
                email.read = true;
            }
            return { success: true, email };

        } catch (error: any) {
            if (error.response?.statusCode === 401 && tokens?.refresh_token) {
                console.log(`MS Graph access token expired for userId ${userId} (read email). Attempting refresh.`);
                const newAccessToken = await refreshMicrosoftGraphToken(userId, tokens.refresh_token, tokens.appEmail);
                if (newAccessToken) {
                    tokens.access_token = newAccessToken;
                    return callGraphApi(newAccessToken);
                } else {
                    return { success: false, message: 'Failed to refresh token. Please try re-authenticating.' };
                }
            }
            console.error(`Error reading Microsoft Graph email ${emailId} for userId ${userId}:`, error.message);
            if (error.response?.body) console.error("MS Graph API Error (read email):", error.response.body);
            return { success: false, message: `Failed to read email: ${error.message}` };
        }
    };
    return callGraphApi(tokens.access_token);
}

export async function sendEmailMicrosoft(userId: string, emailDetails: EmailDetails): Promise<SendEmailResponse> {
    console.log(`Attempting to send email via Microsoft Graph for userId: ${userId}`);
    let tokens = await getAtomMicrosoftGraphTokens(userId);

    if (!tokens?.access_token) {
        return { success: false, message: 'Authentication required. Please connect your Microsoft Account.' };
    }
    if (!emailDetails.to || !emailDetails.subject || !emailDetails.body) {
        return { success: false, message: 'Missing required email details (to, subject, body).' };
    }

    const callGraphApi = async (accessToken: string): Promise<SendEmailResponse> => {
        const message = {
            subject: emailDetails.subject,
            body: {
                contentType: "HTML", // Assuming HTML body, could be "Text"
                content: emailDetails.body
            },
            toRecipients: [{ emailAddress: { address: emailDetails.to } }],
            // ccRecipients and bccRecipients can be added similarly if needed
        };

        // Note: The "From" address is implicitly the authenticated user.
        // If `tokens.appEmail` is available and reliable, it could be added to `from` field if API allows overriding,
        // but usually not needed for /sendMail.

        try {
            // The sendMail action doesn't return the created message body, only a 202 Accepted.
            // No ID is returned directly by this specific endpoint.
            await got.post('https://graph.microsoft.com/v1.0/me/sendMail', {
                headers: { 'Authorization': `Bearer ${accessToken}` },
                json: { message: message, saveToSentItems: "true" }, // saveToSentItems is optional, defaults to true
                responseType: 'json', // Expecting no significant body on 202
            });

            // Since sendMail returns 202 Accepted and no message ID immediately,
            // we can't provide an emailId here.
            console.log(`Email sent successfully via Microsoft Graph for userId: ${userId} to: ${emailDetails.to}`);
            return { success: true, message: 'Email sent successfully via Microsoft Graph.' };

        } catch (error: any) {
            if (error.response?.statusCode === 401 && tokens?.refresh_token) {
                console.log(`MS Graph access token expired for userId ${userId} (send email). Attempting refresh.`);
                const newAccessToken = await refreshMicrosoftGraphToken(userId, tokens.refresh_token, tokens.appEmail);
                if (newAccessToken) {
                    tokens.access_token = newAccessToken;
                    return callGraphApi(newAccessToken);
                } else {
                    return { success: false, message: 'Failed to refresh token. Please try re-authenticating.' };
                }
            }
            console.error(`Error sending email via Microsoft Graph for userId ${userId}:`, error.message);
            if (error.response?.body) console.error("MS Graph API Error (send email):", error.response.body);
            return { success: false, message: `Failed to send email via Microsoft Graph: ${error.message}` };
        }
    };
    return callGraphApi(tokens.access_token);
}

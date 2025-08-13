import { google, gmail_v1 } from 'googleapis';
// Adjust paths as necessary
import { createAdminGraphQLClient } from '../_utils/dbService';
import {
  decrypt,
  encrypt,
} from '../gmail-integration/handle-gmail-auth-callback';
import { refreshGmailAccessToken } from '../google-api-auth/_libs/api-helper';
import {
  googleClientIdGmail,
  googleClientSecretGmail,
} from '../google-api-auth/_libs/constants';

const GET_GMAIL_TOKENS_QUERY = `
query GetUserGmailTokens($userId: uuid!) {
  user_gmail_tokens(where: {user_id: {_eq: $userId}}, limit: 1) {
    encrypted_access_token
    encrypted_refresh_token
    token_expiry_timestamp
  }
}
`;

const UPDATE_GMAIL_ACCESS_TOKEN_MUTATION = `
mutation UpdateUserGmailAccessTokenAfterRefresh($userId: uuid!, $newEncryptedAccessToken: String!, $newExpiryTimestamp: timestamptz!) {
  update_user_gmail_tokens(
    where: {user_id: {_eq: $userId}},
    _set: {
      encrypted_access_token: $newEncryptedAccessToken,
      token_expiry_timestamp: $newExpiryTimestamp,
      updated_at: "now()"
    }
  ) {
    affected_rows
  }
}
`;

/**
 * Retrieves a user's stored Gmail tokens, refreshes if necessary,
 * and returns an authenticated OAuth2 client configured for Gmail API.
 * @param userId The ID of the user.
 * @returns An authenticated google.auth.OAuth2 client or null if tokens are not found/valid.
 */
export async function getGmailClientForUser(
  userId: string
): Promise<google.auth.OAuth2 | null> {
  const adminGraphQLClient = createAdminGraphQLClient();

  try {
    const gqlResponse = await adminGraphQLClient.request(
      GET_GMAIL_TOKENS_QUERY,
      { userId }
    );
    const storedTokenRecord =
      gqlResponse.user_gmail_tokens && gqlResponse.user_gmail_tokens[0];

    if (!storedTokenRecord) {
      console.log(
        `No Gmail tokens found for user ${userId}. User needs to authorize.`
      );
      return null;
    }

    let {
      encrypted_access_token,
      encrypted_refresh_token,
      token_expiry_timestamp,
    } = storedTokenRecord;

    if (!encrypted_access_token && !encrypted_refresh_token) {
      console.log(
        `Neither access nor refresh token found for user ${userId}. Re-authorization needed.`
      );
      return null;
    }

    const oauth2Client = new google.auth.OAuth2(
      googleClientIdGmail,
      googleClientSecretGmail
      // No redirect URI needed here as we are not starting a new auth flow
    );

    let currentAccessToken = '';

    // Check if token is expired or about to expire (e.g., within next 5 minutes)
    const expiryDate = token_expiry_timestamp
      ? new Date(token_expiry_timestamp).getTime()
      : 0;
    const needsRefresh = Date.now() >= expiryDate - 5 * 60 * 1000;

    if (needsRefresh) {
      if (!encrypted_refresh_token) {
        console.error(
          `Token for user ${userId} needs refresh, but no refresh token is available. User must re-authorize.`
        );
        // Optionally, clear the invalid tokens from DB or mark them as needing re-auth
        return null;
      }
      console.log(
        `Gmail access token for user ${userId} requires refresh. Attempting...`
      );

      const decryptedRefreshToken = decrypt(encrypted_refresh_token);
      if (!decryptedRefreshToken) {
        console.error(`Failed to decrypt refresh token for user ${userId}.`);
        return null; // Cannot proceed without decrypted refresh token
      }

      const refreshedGoogleTokens = await refreshGmailAccessToken(
        decryptedRefreshToken
      );

      if (
        !refreshedGoogleTokens.access_token ||
        !refreshedGoogleTokens.expires_in
      ) {
        console.error(
          `Failed to refresh Gmail access token from Google for user ${userId}.`
        );
        // This could be due to revoked refresh token. User needs to re-authorize.
        // Optionally, clear the invalid tokens from DB or mark them as needing re-auth
        return null;
      }

      currentAccessToken = refreshedGoogleTokens.access_token;
      const newEncryptedAccessToken = encrypt(currentAccessToken);
      const newExpiry = new Date(
        Date.now() + refreshedGoogleTokens.expires_in * 1000
      ).toISOString();

      // Update the database with the new access token and expiry
      await adminGraphQLClient.request(UPDATE_GMAIL_ACCESS_TOKEN_MUTATION, {
        userId,
        newEncryptedAccessToken: newEncryptedAccessToken,
        newExpiryTimestamp: newExpiry,
      });
      console.log(
        `Gmail access token for user ${userId} refreshed and updated in DB.`
      );

      // If the original refresh token was also updated by Google (rare, but possible),
      // you would also update encrypted_refresh_token here.
      // For now, assuming refresh_token remains the same unless Google explicitly changes it.
    } else {
      if (!encrypted_access_token) {
        console.error(
          `Token for user ${userId} not expired, but access token is missing. This state should not occur.`
        );
        return null; // Should not happen if not expired and no refresh needed.
      }
      const decryptedAccessToken = decrypt(encrypted_access_token);
      if (!decryptedAccessToken) {
        console.error(`Failed to decrypt access token for user ${userId}.`);
        return null;
      }
      currentAccessToken = decryptedAccessToken;
    }

    oauth2Client.setCredentials({ access_token: currentAccessToken });
    // If Google returned a new refresh_token (rare for Google, but some providers do),
    // you'd set it here too: oauth2Client.setCredentials({ access_token: ..., refresh_token: ... });
    // And then re-encrypt and save the new refresh_token.

    return oauth2Client;
  } catch (error: any) {
    console.error(
      `Error in getGmailClientForUser for user ${userId}:`,
      error.message
    );
    if (error.response && error.response.body) {
      // Log Google API errors if available
      console.error('Google API error details:', error.response.body);
    }
    return null;
  }
}

/**
 * Placeholder for searching user's emails.
 * @param userId The ID of the user.
 * @param query The search query (e.g., "from:xyz@example.com subject:contract after:2023/01/01 before:2023/03/31").
 * @param maxResults Maximum number of results to return.
 * @returns A promise that resolves to an array of Gmail messages.
 */
export async function searchUserEmails(
  userId: string,
  query: string,
  maxResults: number = 10
): Promise<gmail_v1.Schema$Message[]> {
  console.log(
    `Gmail Service: Searching emails for user ${userId} with query "${query}", max ${maxResults}`
  );
  const authedClient = await getGmailClientForUser(userId);
  if (!authedClient) {
    // Detailed error already logged in getGmailClientForUser if it returns null due to auth issues
    throw new Error(
      'Failed to get authenticated Gmail client. User may need to authorize or re-authorize.'
    );
  }

  const gmail = google.gmail({ version: 'v1', auth: authedClient });

  try {
    const response = await gmail.users.messages.list({
      userId: 'me',
      q: query,
      maxResults: maxResults,
      // consider adding fields parameter to optimize, e.g. 'messages(id,threadId,snippet)'
    });

    // messages.list returns a list of Message resources, which should include id, threadId, and often snippet.
    // If more details like subject, from, date are needed for each item in search results *without* N+1 calls,
    // the query would need to be more complex (e.g. batch requests for messages.get with format: 'metadata')
    // or a different Gmail API endpoint. For now, this is a direct mapping.
    return response.data.messages || [];
  } catch (error: any) {
    console.error(
      `Error searching emails for user ${userId} (query: "${query}"):`,
      error.message
    );
    if (error.code === 401) {
      // Unauthorized, often due to token issues not caught by refresh
      throw new Error(
        'Gmail authentication failed (token might be revoked or insufficient permissions). Please re-authorize.'
      );
    }
    if (error.code === 403) {
      // Forbidden, e.g. Gmail API not enabled for project or usage limits
      throw new Error(
        'Access to Gmail API is forbidden. Please check API configuration or usage limits.'
      );
    }
    // Re-throw a generic error or a more specific one based on Google's error structure
    throw new Error(
      `Failed to search emails: ${error.message || 'Unknown Gmail API error'}`
    );
  }
}

export async function sendEmail(
  userId: string,
  to: string,
  subject: string,
  body: string
): Promise<any> {
  const authedClient = await getGmailClientForUser(userId);
  if (!authedClient) {
    throw new Error('Failed to get authenticated Gmail client.');
  }

  const gmail = google.gmail({ version: 'v1', auth: authedClient });

  // The 'From' header will be set automatically by the Gmail API to the user's primary email address
  // when using userId: 'me'. The 'To' and 'Subject' headers must be included.
  const rawMessage = [
    `To: ${to}`,
    `Subject: ${subject}`,
    'Content-Type: text/plain; charset=utf-8',
    '',
    body,
  ].join('\n');

  const encodedMessage = Buffer.from(rawMessage)
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');

  try {
    const response = await gmail.users.messages.send({
      userId: 'me',
      requestBody: {
        raw: encodedMessage,
      },
    });
    return response.data;
  } catch (error: any) {
    console.error(`Error sending email for user ${userId}:`, error.message);
    throw new Error(`Failed to send email: ${error.message || 'Unknown Gmail API error'}`);
  }
}

/**
 * Fetches the full content of a specific email.
 * @param userId The ID of the user.
 * @param emailId The ID of the email to fetch.
 * @returns A promise that resolves to the full Gmail message content.
 */
export async function getUserEmailContent(
  userId: string,
  emailId: string
): Promise<gmail_v1.Schema$Message | null> {
  console.log(
    `Gmail Service: Getting email content for user ${userId}, email ID "${emailId}"`
  );
  const authedClient = await getGmailClientForUser(userId);
  if (!authedClient) {
    throw new Error(
      'Failed to get authenticated Gmail client. User may need to authorize or re-authorize.'
    );
  }

  const gmail = google.gmail({ version: 'v1', auth: authedClient });

  try {
    const response = await gmail.users.messages.get({
      userId: 'me',
      id: emailId,
      format: 'full', // Fetches full email content, including headers, body, attachments etc.
      // Use 'metadata' for headers only, 'minimal' for id/threadId/labels.
    });
    return response.data;
  } catch (error: any) {
    console.error(
      `Error fetching email content for user ${userId}, email ID ${emailId}:`,
      error.message
    );
    if (error.code === 401) {
      throw new Error(
        'Gmail authentication failed (token might be revoked or insufficient permissions). Please re-authorize.'
      );
    }
    if (error.code === 403) {
      throw new Error(
        'Access to Gmail API is forbidden for this message or user. Please check API configuration or usage limits.'
      );
    }
    if (error.code === 404) {
      throw new Error(`Email with ID ${emailId} not found.`);
    }
    throw new Error(
      `Failed to fetch email content: ${error.message || 'Unknown Gmail API error'}`
    );
  }
}

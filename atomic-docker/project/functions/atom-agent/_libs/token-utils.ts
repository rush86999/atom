import got from 'got';
import {
  HASURA_GRAPHQL_URL,
  HASURA_ADMIN_SECRET,
  ATOM_CALENDAR_RESOURCE_NAME,
  ATOM_GMAIL_RESOURCE_NAME,
  ATOM_MSGRAPH_RESOURCE_NAME, // Added
  ATOM_CLIENT_TYPE,
  ATOM_TOKEN_ENCRYPTION_KEY,
  ATOM_TOKEN_ENCRYPTION_IV,
} from './constants';
import dayjs from 'dayjs';
import crypto from 'crypto';

export async function encryptToken(token: string): Promise<string | null> {
    if (!ATOM_TOKEN_ENCRYPTION_KEY || !ATOM_TOKEN_ENCRYPTION_IV) {
        console.error("Encryption key or IV is missing. Cannot encrypt token.");
        return null;
    }
    if (!token) return token;

    try {
        const key = Buffer.from(ATOM_TOKEN_ENCRYPTION_KEY, 'hex');
        const iv = Buffer.from(ATOM_TOKEN_ENCRYPTION_IV, 'hex');

        if (key.length !== 32 || iv.length !== 16) {
            console.error("Invalid key or IV length for AES-256-CBC. Key must be 32 bytes (64 hex chars), IV must be 16 bytes (32 hex chars).");
            return null;
        }

        const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
        let encrypted = cipher.update(token, 'utf8', 'base64');
        encrypted += cipher.final('base64');
        return encrypted;
    } catch (error) {
        console.error("Error during token encryption:", error);
        return null;
    }
}

export async function decryptToken(encryptedToken: string): Promise<string | null> {
    if (!ATOM_TOKEN_ENCRYPTION_KEY || !ATOM_TOKEN_ENCRYPTION_IV) {
        console.error("Encryption key or IV is missing. Cannot decrypt token.");
        return null;
    }
    if (!encryptedToken) return encryptedToken;

    try {
        const key = Buffer.from(ATOM_TOKEN_ENCRYPTION_KEY, 'hex');
        const iv = Buffer.from(ATOM_TOKEN_ENCRYPTION_IV, 'hex');

        if (key.length !== 32 || iv.length !== 16) {
            console.error("Invalid key or IV length for AES-256-CBC.");
            return null;
        }

        const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
        let decrypted = decipher.update(encryptedToken, 'base64', 'utf8');
        decrypted += decipher.final('utf8');
        return decrypted;
    } catch (error) {
        console.error("Error during token decryption:", error);
        return null;
    }
}

interface GoogleTokenSet {
    access_token: string;
    refresh_token?: string | null;
    expiry_date: number; // Expecting timestamp in milliseconds
    scope?: string | null;
    token_type?: string | null;
}

export async function saveAtomGoogleCalendarTokens(
    userId: string,
    tokens: GoogleTokenSet,
    appEmail?: string | null
): Promise<{ id: string; userId: string } | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot save tokens.');
        throw new Error('Server configuration error for saving tokens.');
    }
    if (!userId || !tokens.access_token || !tokens.expiry_date) {
        console.error('Missing required token information for saving.');
        throw new Error('Invalid token data provided for saving.');
    }

    const encryptedAccessToken = await encryptToken(tokens.access_token);
    // Ensure refresh token is only encrypted if it exists
    const encryptedRefreshToken = tokens.refresh_token ? await encryptToken(tokens.refresh_token) : null;

    if (!encryptedAccessToken || (tokens.refresh_token && !encryptedRefreshToken)) {
        console.error("Failed to encrypt tokens. Aborting save.");
        throw new Error("Token encryption failed. Cannot save tokens.");
    }

    // Convert expiry_date (timestamp in ms) to timestamptz string for Hasura
    const expiresAt = new Date(tokens.expiry_date).toISOString();

    const mutation = `
        mutation upsertAtomGoogleCalendarToken(
            $userId: uuid!,
            $accessToken: String!,
            $refreshToken: String,
            $expiresAt: timestamptz!,
            $scope: String,
            $tokenType: String,
            $resourceName: String!,
            $clientType: String!,
            $appEmail: String, // Added appEmail
            $enabled: Boolean!
        ) {
          insert_Calendar_Integration_one(object: {
            userId: $userId,
            token: $accessToken,       // Encrypted
            refreshToken: $refreshToken, // Encrypted
            expiresAt: $expiresAt,
            scope: $scope,
            token_type: $tokenType,
            resource: $resourceName,
            clientType: $clientType,
            name: $resourceName,
            appEmail: $appEmail,     // Added appEmail
            enabled: $enabled,
            syncEnabled: false
          }, on_conflict: {
            constraint: Calendar_Integration_userId_resource_clientType_key,
            update_columns: [token, refreshToken, expiresAt, scope, token_type, appEmail, enabled, updatedAt] // Added appEmail
          }) {
            id
            userId
          }
        }
    `;

    const variables = {
        userId: userId,
        accessToken: encryptedAccessToken,
        refreshToken: encryptedRefreshToken,
        expiresAt: expiresAt,
        scope: tokens.scope,
        tokenType: tokens.token_type,
        resourceName: ATOM_CALENDAR_RESOURCE_NAME,
        clientType: ATOM_CLIENT_TYPE,
        appEmail: appEmail, // Added appEmail
        enabled: true, // Enable the integration on save/update
    };

    try {
        console.log(`Saving/Updating Atom Google Calendar tokens for userId: ${userId}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: {
                query: mutation,
                variables: variables,
            },
            headers: {
                'x-hasura-admin-secret': HASURA_ADMIN_SECRET,
            },
        }).json();

        if (response.errors) {
            console.error('Error saving Atom Google Calendar tokens to Hasura:', response.errors);
            throw new Error(`Failed to save tokens: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }

        console.log('Successfully saved Atom Google Calendar tokens:', response.data.insert_Calendar_Integration_one);
        return response.data.insert_Calendar_Integration_one;
    } catch (error: any) {
        console.error('Exception while saving Atom Google Calendar tokens:', error.message);
        // Log the detailed error if available (e.g. network error, got specific error)
        if (error.response && error.response.body) {
            console.error("Detailed error from got:", error.response.body);
        }
        throw new Error(`An exception occurred while saving tokens: ${error.message}`);
    }
}


export async function getAtomGoogleCalendarTokens(userId: string): Promise<GoogleTokenSet | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot get tokens.');
        throw new Error('Server configuration error for getting tokens.');
    }

    const query = `
        query getAtomGoogleCalendarTokens($userId: uuid!, $resourceName: String!, $clientType: String!) {
          Calendar_Integration(where: {
            userId: {_eq: $userId},
            resource: {_eq: $resourceName},
            clientType: {_eq: $clientType}
          }, limit: 1) {
            id
            token # Encrypted access_token
            refreshToken # Encrypted refresh_token
            expiresAt
            scope
            token_type
            appEmail   # Added appEmail
          }
        }
    `;

    const variables = {
        userId: userId,
        resourceName: ATOM_CALENDAR_RESOURCE_NAME,
        clientType: ATOM_CLIENT_TYPE,
    };

    try {
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query, variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error fetching Atom Google Calendar tokens from Hasura:', response.errors);
            return null;
        }

        const integration = response.data.Calendar_Integration?.[0];
        if (!integration) {
            console.log(`No Atom Google Calendar tokens found for userId: ${userId}`);
            return null;
        }

        const accessToken = await decryptToken(integration.token);
        const refreshToken = integration.refreshToken ? await decryptToken(integration.refreshToken) : null;

        // If decryption fails for a critical token (access_token), treat as no valid token found.
        if (!accessToken) {
            console.error(`Failed to decrypt access token for userId: ${userId}. Returning null.`);
            return null;
        }
        if (integration.refreshToken && !refreshToken) {
            console.warn(`Failed to decrypt refresh token for userId: ${userId}. Proceeding without it.`);
        }

        return {
            access_token: accessToken,
            refresh_token: refreshToken || undefined, // Keep as undefined if null
            expiry_date: new Date(integration.expiresAt).getTime(),
            scope: integration.scope,
            token_type: integration.token_type,
            appEmail: integration.appEmail || null, // Add appEmail
        };

    } catch (error: any) {
        console.error('Exception while fetching Atom Google Calendar tokens:', error.message);
        return null;
    }
}


export async function deleteAtomGoogleCalendarTokens(userId: string): Promise<{ affected_rows: number }> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot delete tokens.');
        throw new Error('Server configuration error for deleting tokens.');
    }

    const mutation = `
        mutation deleteAtomGoogleCalendarToken($userId: uuid!, $resourceName: String!, $clientType: String!) {
          delete_Calendar_Integration(where: {
            userId: {_eq: $userId},
            resource: {_eq: $resourceName},
            clientType: {_eq: $clientType}
          }) {
            affected_rows
          }
        }
    `;

    const variables = {
        userId: userId,
        resourceName: ATOM_CALENDAR_RESOURCE_NAME,
        clientType: ATOM_CLIENT_TYPE,
    };

    try {
        console.log(`Deleting Atom Google Calendar tokens for userId: ${userId}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: {
                query: mutation,
                variables: variables,
            },
            headers: {
                'x-hasura-admin-secret': HASURA_ADMIN_SECRET,
            },
        }).json();

        if (response.errors) {
            console.error('Error deleting Atom Google Calendar tokens from Hasura:', response.errors);
            throw new Error(`Failed to delete tokens: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }

        console.log('Successfully deleted Atom Google Calendar tokens (or no tokens found to delete). Affected rows:', response.data.delete_Calendar_Integration.affected_rows);
        return response.data.delete_Calendar_Integration;

    } catch (error: any) {
        console.error('Exception while deleting Atom Google Calendar tokens:', error.message);
        throw new Error(`An exception occurred while deleting tokens: ${error.message}`);
    }
}

// --- Gmail Token Functions ---

export async function saveAtomGmailTokens(
    userId: string,
    tokens: GoogleTokenSet, // Reusing the same interface, ensure it's suitable or create a specific one
    appEmail?: string | null
): Promise<{ id: string; userId: string } | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot save Gmail tokens.');
        throw new Error('Server configuration error for saving Gmail tokens.');
    }
    if (!userId || !tokens.access_token || !tokens.expiry_date) {
        console.error('Missing required Gmail token information for saving.');
        throw new Error('Invalid Gmail token data provided for saving.');
    }

    const encryptedAccessToken = await encryptToken(tokens.access_token);
    const encryptedRefreshToken = tokens.refresh_token ? await encryptToken(tokens.refresh_token) : null;

    if (!encryptedAccessToken || (tokens.refresh_token && !encryptedRefreshToken)) {
        console.error("Failed to encrypt Gmail tokens. Aborting save.");
        throw new Error("Gmail token encryption failed. Cannot save tokens.");
    }

    const expiresAt = new Date(tokens.expiry_date).toISOString();

    // Using the same Calendar_Integration table and upsert mutation structure
    // Differentiated by resource and clientType (ATOM_GMAIL_RESOURCE_NAME, ATOM_CLIENT_TYPE)
    const mutation = `
        mutation upsertAtomGmailToken(
            $userId: uuid!,
            $accessToken: String!,
            $refreshToken: String,
            $expiresAt: timestamptz!,
            $scope: String,
            $tokenType: String,
            $resourceName: String!,
            $clientType: String!,
            $appEmail: String,
            $enabled: Boolean!
        ) {
          insert_Calendar_Integration_one(object: {
            userId: $userId,
            token: $accessToken,
            refreshToken: $refreshToken,
            expiresAt: $expiresAt,
            scope: $scope,
            token_type: $tokenType,
            resource: $resourceName,
            clientType: $clientType,
            name: $resourceName, // Or a more descriptive name like "Atom Gmail Connection"
            appEmail: $appEmail,
            enabled: $enabled,
            syncEnabled: false // Default for Atom integrations
          }, on_conflict: {
            constraint: Calendar_Integration_userId_resource_clientType_key,
            update_columns: [token, refreshToken, expiresAt, scope, token_type, appEmail, enabled, updatedAt]
          }) {
            id
            userId
          }
        }
    `;

    const variables = {
        userId: userId,
        accessToken: encryptedAccessToken,
        refreshToken: encryptedRefreshToken,
        expiresAt: expiresAt,
        scope: tokens.scope,
        tokenType: tokens.token_type,
        resourceName: ATOM_GMAIL_RESOURCE_NAME, // Specific for Gmail
        clientType: ATOM_CLIENT_TYPE,       // Shared client type for Atom
        appEmail: appEmail,
        enabled: true,
    };

    try {
        console.log(`Saving/Updating Atom Gmail tokens for userId: ${userId}, appEmail: ${appEmail}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query: mutation, variables: variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error saving Atom Gmail tokens to Hasura:', response.errors);
            throw new Error(`Failed to save Gmail tokens: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }

        console.log('Successfully saved Atom Gmail tokens:', response.data.insert_Calendar_Integration_one);
        return response.data.insert_Calendar_Integration_one;
    } catch (error: any) {
        console.error('Exception while saving Atom Gmail tokens:', error.message);
        if (error.response && error.response.body) {
            console.error("Detailed error from got (Gmail save):", error.response.body);
        }
        throw new Error(`An exception occurred while saving Gmail tokens: ${error.message}`);
    }
}

export async function getAtomGmailTokens(userId: string): Promise<(GoogleTokenSet & { appEmail?: string | null }) | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot get Gmail tokens.');
        throw new Error('Server configuration error for getting Gmail tokens.');
    }

    const query = `
        query getAtomGmailTokens($userId: uuid!, $resourceName: String!, $clientType: String!) {
          Calendar_Integration(where: {
            userId: {_eq: $userId},
            resource: {_eq: $resourceName},
            clientType: {_eq: $clientType}
          }, limit: 1) {
            id
            token
            refreshToken
            expiresAt
            scope
            token_type
            appEmail
          }
        }
    `;

    const variables = {
        userId: userId,
        resourceName: ATOM_GMAIL_RESOURCE_NAME, // Specific for Gmail
        clientType: ATOM_CLIENT_TYPE,       // Shared client type for Atom
    };

    try {
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query, variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error fetching Atom Gmail tokens from Hasura:', response.errors);
            return null;
        }

        const integration = response.data.Calendar_Integration?.[0];
        if (!integration) {
            console.log(`No Atom Gmail tokens found for userId: ${userId}`);
            return null;
        }

        const accessToken = await decryptToken(integration.token);
        const refreshToken = integration.refreshToken ? await decryptToken(integration.refreshToken) : null;

        if (!accessToken) {
            console.error(`Failed to decrypt Gmail access token for userId: ${userId}. Returning null.`);
            return null;
        }
        if (integration.refreshToken && !refreshToken) {
            console.warn(`Failed to decrypt Gmail refresh token for userId: ${userId}. Proceeding without it.`);
        }

        return {
            access_token: accessToken,
            refresh_token: refreshToken || undefined,
            expiry_date: new Date(integration.expiresAt).getTime(),
            scope: integration.scope,
            token_type: integration.token_type,
            appEmail: integration.appEmail || null,
        };

    } catch (error: any) {
        console.error('Exception while fetching Atom Gmail tokens:', error.message);
        return null;
    }
}

export async function deleteAtomGmailTokens(userId: string): Promise<{ affected_rows: number }> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot delete Gmail tokens.');
        throw new Error('Server configuration error for deleting Gmail tokens.');
    }

    const mutation = `
        mutation deleteAtomGmailToken($userId: uuid!, $resourceName: String!, $clientType: String!) {
          delete_Calendar_Integration(where: {
            userId: {_eq: $userId},
            resource: {_eq: $resourceName},
            clientType: {_eq: $clientType}
          }) {
            affected_rows
          }
        }
    `;

    const variables = {
        userId: userId,
        resourceName: ATOM_GMAIL_RESOURCE_NAME, // Specific for Gmail
        clientType: ATOM_CLIENT_TYPE,       // Shared client type for Atom
    };

    try {
        console.log(`Deleting Atom Gmail tokens for userId: ${userId}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query: mutation, variables: variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error deleting Atom Gmail tokens from Hasura:', response.errors);
            throw new Error(`Failed to delete Gmail tokens: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }

        console.log('Successfully deleted Atom Gmail tokens. Affected rows:', response.data.delete_Calendar_Integration.affected_rows);
        return response.data.delete_Calendar_Integration;

    } catch (error: any) {
        console.error('Exception while deleting Atom Gmail tokens:', error.message);
        throw new Error(`An exception occurred while deleting Gmail tokens: ${error.message}`);
    }
}

// --- Microsoft Graph Token Functions ---

export async function saveAtomMicrosoftGraphTokens(
    userId: string,
    tokens: GoogleTokenSet, // Reusing GoogleTokenSet; ensure fields like expiry_date (number), access_token, refresh_token align
    appEmail?: string | null
): Promise<{ id: string; userId: string } | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot save Microsoft Graph tokens.');
        throw new Error('Server configuration error for saving Microsoft Graph tokens.');
    }
    if (!userId || !tokens.access_token || !tokens.expiry_date) {
        console.error('Missing required Microsoft Graph token information for saving.');
        throw new Error('Invalid Microsoft Graph token data provided for saving.');
    }

    const encryptedAccessToken = await encryptToken(tokens.access_token);
    const encryptedRefreshToken = tokens.refresh_token ? await encryptToken(tokens.refresh_token) : null;

    if (!encryptedAccessToken || (tokens.refresh_token && !encryptedRefreshToken)) {
        console.error("Failed to encrypt Microsoft Graph tokens. Aborting save.");
        throw new Error("Microsoft Graph token encryption failed. Cannot save tokens.");
    }

    const expiresAt = new Date(tokens.expiry_date).toISOString(); // expiry_date is expected as number (ms)

    const mutation = `
        mutation upsertAtomMicrosoftGraphToken(
            $userId: uuid!,
            $accessToken: String!,
            $refreshToken: String,
            $expiresAt: timestamptz!,
            $scope: String,
            $tokenType: String,
            $resourceName: String!,
            $clientType: String!,
            $appEmail: String,
            $enabled: Boolean!
        ) {
          insert_Calendar_Integration_one(object: {
            userId: $userId,
            token: $accessToken,
            refreshToken: $refreshToken,
            expiresAt: $expiresAt,
            scope: $scope,
            token_type: $tokenType,
            resource: $resourceName,
            clientType: $clientType,
            name: $resourceName,
            appEmail: $appEmail,
            enabled: $enabled,
            syncEnabled: false
          }, on_conflict: {
            constraint: Calendar_Integration_userId_resource_clientType_key,
            update_columns: [token, refreshToken, expiresAt, scope, token_type, appEmail, enabled, updatedAt]
          }) {
            id
            userId
          }
        }
    `;

    const variables = {
        userId: userId,
        accessToken: encryptedAccessToken,
        refreshToken: encryptedRefreshToken,
        expiresAt: expiresAt,
        scope: tokens.scope,
        tokenType: tokens.token_type,
        resourceName: ATOM_MSGRAPH_RESOURCE_NAME, // Specific for Microsoft Graph
        clientType: ATOM_CLIENT_TYPE,           // Shared client type for Atom
        appEmail: appEmail,
        enabled: true,
    };

    try {
        console.log(`Saving/Updating Atom Microsoft Graph tokens for userId: ${userId}, appEmail: ${appEmail}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query: mutation, variables: variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error saving Atom Microsoft Graph tokens to Hasura:', response.errors);
            throw new Error(`Failed to save Microsoft Graph tokens: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }

        console.log('Successfully saved Atom Microsoft Graph tokens:', response.data.insert_Calendar_Integration_one);
        return response.data.insert_Calendar_Integration_one;
    } catch (error: any) {
        console.error('Exception while saving Atom Microsoft Graph tokens:', error.message);
        if (error.response && error.response.body) {
            console.error("Detailed error from got (Microsoft Graph save):", error.response.body);
        }
        throw new Error(`An exception occurred while saving Microsoft Graph tokens: ${error.message}`);
    }
}

export async function getAtomMicrosoftGraphTokens(userId: string): Promise<(GoogleTokenSet & { appEmail?: string | null }) | null> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot get Microsoft Graph tokens.');
        throw new Error('Server configuration error for getting Microsoft Graph tokens.');
    }

    const query = `
        query getAtomMicrosoftGraphTokens($userId: uuid!, $resourceName: String!, $clientType: String!) {
          Calendar_Integration(where: {
            userId: {_eq: $userId},
            resource: {_eq: $resourceName},
            clientType: {_eq: $clientType}
          }, limit: 1) {
            id
            token
            refreshToken
            expiresAt
            scope
            token_type
            appEmail
          }
        }
    `;

    const variables = {
        userId: userId,
        resourceName: ATOM_MSGRAPH_RESOURCE_NAME, // Specific for Microsoft Graph
        clientType: ATOM_CLIENT_TYPE,           // Shared client type for Atom
    };

    try {
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query, variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error fetching Atom Microsoft Graph tokens from Hasura:', response.errors);
            return null;
        }

        const integration = response.data.Calendar_Integration?.[0];
        if (!integration) {
            console.log(`No Atom Microsoft Graph tokens found for userId: ${userId}`);
            return null;
        }

        const accessToken = await decryptToken(integration.token);
        const refreshToken = integration.refreshToken ? await decryptToken(integration.refreshToken) : null;

        if (!accessToken) {
            console.error(`Failed to decrypt Microsoft Graph access token for userId: ${userId}. Returning null.`);
            return null;
        }
        if (integration.refreshToken && !refreshToken) {
            console.warn(`Failed to decrypt Microsoft Graph refresh token for userId: ${userId}. Proceeding without it.`);
        }

        return {
            access_token: accessToken,
            refresh_token: refreshToken || undefined,
            expiry_date: new Date(integration.expiresAt).getTime(),
            scope: integration.scope,
            token_type: integration.token_type,
            appEmail: integration.appEmail || null,
        };

    } catch (error: any) {
        console.error('Exception while fetching Atom Microsoft Graph tokens:', error.message);
        return null;
    }
}

export async function deleteAtomMicrosoftGraphTokens(userId: string): Promise<{ affected_rows: number }> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('Hasura URL or Admin Secret not configured. Cannot delete Microsoft Graph tokens.');
        throw new Error('Server configuration error for deleting Microsoft Graph tokens.');
    }

    const mutation = `
        mutation deleteAtomMicrosoftGraphToken($userId: uuid!, $resourceName: String!, $clientType: String!) {
          delete_Calendar_Integration(where: {
            userId: {_eq: $userId},
            resource: {_eq: $resourceName},
            clientType: {_eq: $clientType}
          }) {
            affected_rows
          }
        }
    `;

    const variables = {
        userId: userId,
        resourceName: ATOM_MSGRAPH_RESOURCE_NAME, // Specific for Microsoft Graph
        clientType: ATOM_CLIENT_TYPE,           // Shared client type for Atom
    };

    try {
        console.log(`Deleting Atom Microsoft Graph tokens for userId: ${userId}`);
        const response: any = await got.post(HASURA_GRAPHQL_URL, {
            json: { query: mutation, variables: variables },
            headers: { 'x-hasura-admin-secret': HASURA_ADMIN_SECRET },
        }).json();

        if (response.errors) {
            console.error('Error deleting Atom Microsoft Graph tokens from Hasura:', response.errors);
            throw new Error(`Failed to delete Microsoft Graph tokens: ${response.errors.map((e: any) => e.message).join(', ')}`);
        }

        console.log('Successfully deleted Atom Microsoft Graph tokens. Affected rows:', response.data.delete_Calendar_Integration.affected_rows);
        return response.data.delete_Calendar_Integration;

    } catch (error: any) {
        console.error('Exception while deleting Atom Microsoft Graph tokens:', error.message);
        throw new Error(`An exception occurred while deleting Microsoft Graph tokens: ${error.message}`);
    }
}

import got from 'got';
import {
  HASURA_GRAPHQL_URL,
  HASURA_ADMIN_SECRET,
  ATOM_CALENDAR_RESOURCE_NAME,
  ATOM_CLIENT_TYPE,
} from './constants';
import dayjs from 'dayjs'; // For handling expiry_date calculation

// Placeholder for actual encryption logic (e.g., using crypto module like Zoom example)
export async function encryptToken(token: string): Promise<string> {
    console.log("TODO: Implement actual token encryption for token:", token ? token.substring(0,5) + "..." : "null/undefined");
    if (!token) return token; // Return null/undefined as is
    return `encrypted_${token}`;
}

export async function decryptToken(encryptedToken: string): Promise<string> {
    console.log("TODO: Implement actual token decryption for token:", encryptedToken ? encryptedToken.substring(0,15) + "..." : "null/undefined");
    if (!encryptedToken) return encryptedToken; // Return null/undefined as is
    if (encryptedToken.startsWith('encrypted_')) {
        return encryptedToken.substring('encrypted_'.length);
    }
    return encryptedToken;
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
    tokens: GoogleTokenSet
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
    const encryptedRefreshToken = tokens.refresh_token ? await encryptToken(tokens.refresh_token) : null;

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
            enabled: $enabled,
            syncEnabled: false
          }, on_conflict: {
            constraint: Calendar_Integration_userId_resource_clientType_key,
            update_columns: [token, refreshToken, expiresAt, scope, token_type, enabled, updatedAt]
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

        return {
            access_token: accessToken,
            refresh_token: refreshToken || undefined,
            expiry_date: new Date(integration.expiresAt).getTime(),
            scope: integration.scope,
            token_type: integration.token_type,
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

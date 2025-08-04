/**
 * Retrieves a valid Google Drive access token for the given user.
 * Calls a secure backend endpoint that handles token storage and refresh logic.
 * @param userId The ID of the user for whom to retrieve the token.
 * @returns A promise that resolves to the access token string if successful, or null if not.
 */
declare function getGoogleDriveAccessToken(userId: string): Promise<string | null>;
/**
 * Constructs the URL to initiate the Google Drive OAuth flow.
 * This URL points to the backend endpoint that starts the OAuth dance with Google.
 * @param userId The Atom user ID to associate with the OAuth flow (will be passed in 'state').
 * @returns The URL string or null if configuration is missing.
 */
declare function getGoogleDriveAuthInitiateUrl(userId: string): string | null;
export declare const AuthService: {
    getGoogleDriveAccessToken: typeof getGoogleDriveAccessToken;
    getGoogleDriveAuthInitiateUrl: typeof getGoogleDriveAuthInitiateUrl;
};
export {};

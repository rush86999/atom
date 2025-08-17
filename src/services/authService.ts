// In a real application, these credentials would be fetched from a secure storage.
// For now, we will use mock credentials.

export async function getTwitterCredentials(userId: string): Promise<{ bearerToken: string } | null> {
    console.warn("Using mock Twitter credentials. Replace with real credentials in a production environment.");
    return {
        bearerToken: process.env.TWITTER_BEARER_TOKEN || "mock_twitter_bearer_token",
    };
}

export async function getLinkedInCredentials(userId: string): Promise<{ accessToken: string; personId: string } | null> {
    console.warn("Using mock LinkedIn credentials. Replace with real credentials in a production environment.");
    return {
        accessToken: process.env.LINKEDIN_ACCESS_TOKEN || "mock_linkedin_access_token",
        personId: process.env.LINKEDIN_PERSON_ID || "mock_linkedin_person_id",
    };
}

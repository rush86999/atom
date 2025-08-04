// File: atomic-docker/project/functions/_utils/aws-secrets-manager.ts
import { SecretsManagerClient, GetSecretValueCommand, } from '@aws-sdk/client-secrets-manager';
// Environment variables expected (for AWS SDK configuration, typically handled by Lambda execution environment):
// - AWS_REGION (implicitly used by SDK if not specified in client constructor)
const secretsManagerClient = new SecretsManagerClient({
    region: process.env.AWS_REGION || 'us-east-1', // Default to us-east-1 or your specific primary region
});
const secretCache = {};
const CACHE_DURATION_MS = 5 * 60 * 1000; // Cache secrets for 5 minutes by default
/**
 * Retrieves a secret string from AWS Secrets Manager.
 * Caches secrets in memory for a short duration to reduce API calls.
 *
 * @param secretId The ARN or name of the secret to retrieve.
 * @param versionId (Optional) Specifies the unique identifier of the version of the secret to retrieve.
 *                  If you specify this parameter then stage is ignored. Defaults to AWSCURRENT.
 * @param versionStage (Optional) Specifies the secret version stage that you want to retrieve.
 *                     If you specify this parameter then versionId is ignored. Defaults to AWSCURRENT.
 * @returns {Promise<string | undefined>} The secret string, or undefined if an error occurs or secret is not found.
 * @throws {Error} If fetching the secret fails and is not handled gracefully (e.g. access denied).
 */
export const getSecret = async (secretId, versionId, versionStage) => {
    const cacheKey = `${secretId}:${versionId || 'defaultVersionId'}:${versionStage || 'AWSCURRENT'}`;
    const cachedItem = secretCache[cacheKey];
    if (cachedItem && Date.now() - cachedItem.timestamp < CACHE_DURATION_MS) {
        console.log(`[SecretsManager] Returning cached secret for ID: ${secretId.split('/').pop()?.split('-')[0]}...`); // Log part of secret name
        return cachedItem.value;
    }
    console.log(`[SecretsManager] Fetching secret from AWS Secrets Manager for ID: ${secretId.split('/').pop()?.split('-')[0]}...`);
    const params = {
        SecretId: secretId,
    };
    if (versionId)
        params.VersionId = versionId;
    if (versionStage && !versionId)
        params.VersionStage = versionStage;
    try {
        const command = new GetSecretValueCommand(params);
        const data = await secretsManagerClient.send(command);
        let secretString;
        if (data.SecretString) {
            secretString = data.SecretString;
        }
        else if (data.SecretBinary) {
            // If secret is binary, decode it. For API keys, usually it's a string.
            // This example assumes SecretString is used. If binary, uncomment and adjust:
            // const buff = Buffer.from(data.SecretBinary); // For Node.js v14+ direct Buffer from Uint8Array
            // secretString = buff.toString('utf-8');
            console.warn(`[SecretsManager] Secret for ID ${secretId} is binary. This utility currently processes SecretString directly.`);
        }
        else {
            console.warn(`[SecretsManager] Secret for ID ${secretId} has no SecretString or SecretBinary content.`);
        }
        if (secretString) {
            secretCache[cacheKey] = { value: secretString, timestamp: Date.now() };
        }
        return secretString;
    }
    catch (error) {
        console.error(`[SecretsManager] Error retrieving secret for ID ${secretId}: ${error.name} - ${error.message}`);
        if (error.name === 'ResourceNotFoundException' ||
            error.name === 'InvalidParameterException') {
            return undefined; // Secret not found or bad identifier, return undefined gracefully.
        }
        // For other errors like AccessDeniedException, InternalServiceErrorException, etc., re-throw.
        throw error;
    }
};
/**
 * Clears a specific secret or the entire cache.
 * @param secretId (Optional) The ARN or name of the secret to clear from cache. If not provided, clears all cached secrets.
 */
export const clearSecretCache = (secretId) => {
    if (secretId) {
        // Clear all versions/stages for this secretId that might be cached
        Object.keys(secretCache).forEach((key) => {
            if (key.startsWith(secretId + ':')) {
                delete secretCache[key];
            }
        });
        console.log(`[SecretsManager] Cleared cache for secret ID: ${secretId}`);
    }
    else {
        Object.keys(secretCache).forEach((key) => delete secretCache[key]);
        console.log('[SecretsManager] All secrets cleared from cache.');
    }
};
// Example Usage:
/*
import { getSecret } from './aws-secrets-manager'; // Adjust path as necessary

export const exampleLambdaHandler = async () => {
    const myApiTokenArn = process.env.MY_API_TOKEN_SECRET_ARN;
    if (!myApiTokenArn) {
        console.error("MY_API_TOKEN_SECRET_ARN environment variable is not set.");
        return;
    }

    try {
        const apiToken = await getSecret(myApiTokenArn);
        if (apiToken) {
            console.log("Successfully retrieved API token (first few chars):", apiToken.substring(0, 5));
            // Use the apiToken...
        } else {
            console.log("API token not found or is empty.");
        }
    } catch (error) {
        console.error("Failed to process secret:", error);
    }
};
*/
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXdzLXNlY3JldHMtbWFuYWdlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImF3cy1zZWNyZXRzLW1hbmFnZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsc0VBQXNFO0FBRXRFLE9BQU8sRUFDTCxvQkFBb0IsRUFDcEIscUJBQXFCLEdBR3RCLE1BQU0saUNBQWlDLENBQUM7QUFFekMsaUhBQWlIO0FBQ2pILCtFQUErRTtBQUUvRSxNQUFNLG9CQUFvQixHQUFHLElBQUksb0JBQW9CLENBQUM7SUFDcEQsTUFBTSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxJQUFJLFdBQVcsRUFBRSx1REFBdUQ7Q0FDdkcsQ0FBQyxDQUFDO0FBTUgsTUFBTSxXQUFXLEdBQXFDLEVBQUUsQ0FBQztBQUN6RCxNQUFNLGlCQUFpQixHQUFHLENBQUMsR0FBRyxFQUFFLEdBQUcsSUFBSSxDQUFDLENBQUMseUNBQXlDO0FBRWxGOzs7Ozs7Ozs7OztHQVdHO0FBQ0gsTUFBTSxDQUFDLE1BQU0sU0FBUyxHQUFHLEtBQUssRUFDNUIsUUFBZ0IsRUFDaEIsU0FBa0IsRUFDbEIsWUFBcUIsRUFDUSxFQUFFO0lBQy9CLE1BQU0sUUFBUSxHQUFHLEdBQUcsUUFBUSxJQUFJLFNBQVMsSUFBSSxrQkFBa0IsSUFBSSxZQUFZLElBQUksWUFBWSxFQUFFLENBQUM7SUFDbEcsTUFBTSxVQUFVLEdBQUcsV0FBVyxDQUFDLFFBQVEsQ0FBQyxDQUFDO0lBRXpDLElBQUksVUFBVSxJQUFJLElBQUksQ0FBQyxHQUFHLEVBQUUsR0FBRyxVQUFVLENBQUMsU0FBUyxHQUFHLGlCQUFpQixFQUFFLENBQUM7UUFDeEUsT0FBTyxDQUFDLEdBQUcsQ0FDVCxvREFBb0QsUUFBUSxDQUFDLEtBQUssQ0FBQyxHQUFHLENBQUMsQ0FBQyxHQUFHLEVBQUUsRUFBRSxLQUFLLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDLEtBQUssQ0FDbEcsQ0FBQyxDQUFDLDBCQUEwQjtRQUM3QixP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Q0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGlCQUFpQjtBQUNqQjs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztFQXNCRSIsInNvdXJjZXNDb250ZW50IjpbIi8vIEZpbGU6IGF0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2F3cy1zZWNyZXRzLW1hbmFnZXIudHNcblxuaW1wb3J0IHtcbiAgU2VjcmV0c01hbmFnZXJDbGllbnQsXG4gIEdldFNlY3JldFZhbHVlQ29tbWFuZCxcbiAgR2V0U2VjcmV0VmFsdWVDb21tYW5kSW5wdXQsXG4gIEdldFNlY3JldFZhbHVlQ29tbWFuZE91dHB1dCxcbn0gZnJvbSAnQGF3cy1zZGsvY2xpZW50LXNlY3JldHMtbWFuYWdlcic7XG5cbi8vIEVudmlyb25tZW50IHZhcmlhYmxlcyBleHBlY3RlZCAoZm9yIEFXUyBTREsgY29uZmlndXJhdGlvbiwgdHlwaWNhbGx5IGhhbmRsZWQgYnkgTGFtYmRhIGV4ZWN1dGlvbiBlbnZpcm9ubWVudCk6XG4vLyAtIEFXU19SRUdJT04gKGltcGxpY2l0bHkgdXNlZCBieSBTREsgaWYgbm90IHNwZWNpZmllZCBpbiBjbGllbnQgY29uc3RydWN0b3IpXG5cbmNvbnN0IHNlY3JldHNNYW5hZ2VyQ2xpZW50ID0gbmV3IFNlY3JldHNNYW5hZ2VyQ2xpZW50KHtcbiAgcmVnaW9uOiBwcm9jZXNzLmVudi5BV1NfUkVHSU9OIHx8ICd1cy1lYXN0LTEnLCAvLyBEZWZhdWx0IHRvIHVzLWVhc3QtMSBvciB5b3VyIHNwZWNpZmljIHByaW1hcnkgcmVnaW9uXG59KTtcblxuaW50ZXJmYWNlIFNlY3JldENhY2hlRW50cnkge1xuICB2YWx1ZTogc3RyaW5nO1xuICB0aW1lc3RhbXA6IG51bWJlcjtcbn1cbmNvbnN0IHNlY3JldENhY2hlOiBSZWNvcmQ8c3RyaW5nLCBTZWNyZXRDYWNoZUVudHJ5PiA9IHt9O1xuY29uc3QgQ0FDSEVfRFVSQVRJT05fTVMgPSA1ICogNjAgKiAxMDAwOyAvLyBDYWNoZSBzZWNyZXRzIGZvciA1IG1pbnV0ZXMgYnkgZGVmYXVsdFxuXG4vKipcbiAqIFJldHJpZXZlcyBhIHNlY3JldCBzdHJpbmcgZnJvbSBBV1MgU2VjcmV0cyBNYW5hZ2VyLlxuICogQ2FjaGVzIHNlY3JldHMgaW4gbWVtb3J5IGZvciBhIHNob3J0IGR1cmF0aW9uIHRvIHJlZHVjZSBBUEkgY2FsbHMuXG4gKlxuICogQHBhcmFtIHNlY3JldElkIFRoZSBBUk4gb3IgbmFtZSBvZiB0aGUgc2VjcmV0IHRvIHJldHJpZXZlLlxuICogQHBhcmFtIHZlcnNpb25JZCAoT3B0aW9uYWwpIFNwZWNpZmllcyB0aGUgdW5pcXVlIGlkZW50aWZpZXIgb2YgdGhlIHZlcnNpb24gb2YgdGhlIHNlY3JldCB0byByZXRyaWV2ZS5cbiAqICAgICAgICAgICAgICAgICAgSWYgeW91IHNwZWNpZnkgdGhpcyBwYXJhbWV0ZXIgdGhlbiBzdGFnZSBpcyBpZ25vcmVkLiBEZWZhdWx0cyB0byBBV1NDVVJSRU5ULlxuICogQHBhcmFtIHZlcnNpb25TdGFnZSAoT3B0aW9uYWwpIFNwZWNpZmllcyB0aGUgc2VjcmV0IHZlcnNpb24gc3RhZ2UgdGhhdCB5b3Ugd2FudCB0byByZXRyaWV2ZS5cbiAqICAgICAgICAgICAgICAgICAgICAgSWYgeW91IHNwZWNpZnkgdGhpcyBwYXJhbWV0ZXIgdGhlbiB2ZXJzaW9uSWQgaXMgaWdub3JlZC4gRGVmYXVsdHMgdG8gQVdTQ1VSUkVOVC5cbiAqIEByZXR1cm5zIHtQcm9taXNlPHN0cmluZyB8IHVuZGVmaW5lZD59IFRoZSBzZWNyZXQgc3RyaW5nLCBvciB1bmRlZmluZWQgaWYgYW4gZXJyb3Igb2NjdXJzIG9yIHNlY3JldCBpcyBub3QgZm91bmQuXG4gKiBAdGhyb3dzIHtFcnJvcn0gSWYgZmV0Y2hpbmcgdGhlIHNlY3JldCBmYWlscyBhbmQgaXMgbm90IGhhbmRsZWQgZ3JhY2VmdWxseSAoZS5nLiBhY2Nlc3MgZGVuaWVkKS5cbiAqL1xuZXhwb3J0IGNvbnN0IGdldFNlY3JldCA9IGFzeW5jIChcbiAgc2VjcmV0SWQ6IHN0cmluZyxcbiAgdmVyc2lvbklkPzogc3RyaW5nLFxuICB2ZXJzaW9uU3RhZ2U/OiBzdHJpbmdcbik6IFByb21pc2U8c3RyaW5nIHwgdW5kZWZpbmVkPiA9PiB7XG4gIGNvbnN0IGNhY2hlS2V5ID0gYCR7c2VjcmV0SWR9OiR7dmVyc2lvbklkIHx8ICdkZWZhdWx0VmVyc2lvbklkJ306JHt2ZXJzaW9uU3RhZ2UgfHwgJ0FXU0NVUlJFTlQnfWA7XG4gIGNvbnN0IGNhY2hlZEl0ZW0gPSBzZWNyZXRDYWNoZVtjYWNoZUtleV07XG5cbiAgaWYgKGNhY2hlZEl0ZW0gJiYgRGF0ZS5ub3coKSAtIGNhY2hlZEl0ZW0udGltZXN0YW1wIDwgQ0FDSEVfRFVSQVRJT05fTVMpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbU2VjcmV0c01hbmFnZXJdIFJldHVybmluZyBjYWNoZWQgc2VjcmV0IGZvciBJRDogJHtzZWNyZXRJZC5zcGxpdCgnLycpLnBvcCgpPy5zcGxpdCgnLScpWzBdfS4uLmBcbiAgICApOyAvLyBMb2cgcGFydCBvZiBzZWNyZXQgbmFtZVxuICAgIHJldHVybiBjYWNoZWRJdGVtLnZhbHVlO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgYFtTZWNyZXRzTWFuYWdlcl0gRmV0Y2hpbmcgc2VjcmV0IGZyb20gQVdTIFNlY3JldHMgTWFuYWdlciBmb3IgSUQ6ICR7c2VjcmV0SWQuc3BsaXQoJy8nKS5wb3AoKT8uc3BsaXQoJy0nKVswXX0uLi5gXG4gICk7XG5cbiAgY29uc3QgcGFyYW1zOiBHZXRTZWNyZXRWYWx1ZUNvbW1hbmRJbnB1dCA9IHtcbiAgICBTZWNyZXRJZDogc2VjcmV0SWQsXG4gIH07XG4gIGlmICh2ZXJzaW9uSWQpIHBhcmFtcy5WZXJzaW9uSWQgPSB2ZXJzaW9uSWQ7XG4gIGlmICh2ZXJzaW9uU3RhZ2UgJiYgIXZlcnNpb25JZCkgcGFyYW1zLlZlcnNpb25TdGFnZSA9IHZlcnNpb25TdGFnZTtcblxuICB0cnkge1xuICAgIGNvbnN0IGNvbW1hbmQgPSBuZXcgR2V0U2VjcmV0VmFsdWVDb21tYW5kKHBhcmFtcyk7XG4gICAgY29uc3QgZGF0YTogR2V0U2VjcmV0VmFsdWVDb21tYW5kT3V0cHV0ID1cbiAgICAgIGF3YWl0IHNlY3JldHNNYW5hZ2VyQ2xpZW50LnNlbmQoY29tbWFuZCk7XG5cbiAgICBsZXQgc2VjcmV0U3RyaW5nOiBzdHJpbmcgfCB1bmRlZmluZWQ7XG4gICAgaWYgKGRhdGEuU2VjcmV0U3RyaW5nKSB7XG4gICAgICBzZWNyZXRTdHJpbmcgPSBkYXRhLlNlY3JldFN0cmluZztcbiAgICB9IGVsc2UgaWYgKGRhdGEuU2VjcmV0QmluYXJ5KSB7XG4gICAgICAvLyBJZiBzZWNyZXQgaXMgYmluYXJ5LCBkZWNvZGUgaXQuIEZvciBBUEkga2V5cywgdXN1YWxseSBpdCdzIGEgc3RyaW5nLlxuICAgICAgLy8gVGhpcyBleGFtcGxlIGFzc3VtZXMgU2VjcmV0U3RyaW5nIGlzIHVzZWQuIElmIGJpbmFyeSwgdW5jb21tZW50IGFuZCBhZGp1c3Q6XG4gICAgICAvLyBjb25zdCBidWZmID0gQnVmZmVyLmZyb20oZGF0YS5TZWNyZXRCaW5hcnkpOyAvLyBGb3IgTm9kZS5qcyB2MTQrIGRpcmVjdCBCdWZmZXIgZnJvbSBVaW50OEFycmF5XG4gICAgICAvLyBzZWNyZXRTdHJpbmcgPSBidWZmLnRvU3RyaW5nKCd1dGYtOCcpO1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgW1NlY3JldHNNYW5hZ2VyXSBTZWNyZXQgZm9yIElEICR7c2VjcmV0SWR9IGlzIGJpbmFyeS4gVGhpcyB1dGlsaXR5IGN1cnJlbnRseSBwcm9jZXNzZXMgU2VjcmV0U3RyaW5nIGRpcmVjdGx5LmBcbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYFtTZWNyZXRzTWFuYWdlcl0gU2VjcmV0IGZvciBJRCAke3NlY3JldElkfSBoYXMgbm8gU2VjcmV0U3RyaW5nIG9yIFNlY3JldEJpbmFyeSBjb250ZW50LmBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKHNlY3JldFN0cmluZykge1xuICAgICAgc2VjcmV0Q2FjaGVbY2FjaGVLZXldID0geyB2YWx1ZTogc2VjcmV0U3RyaW5nLCB0aW1lc3RhbXA6IERhdGUubm93KCkgfTtcbiAgICB9XG4gICAgcmV0dXJuIHNlY3JldFN0cmluZztcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgW1NlY3JldHNNYW5hZ2VyXSBFcnJvciByZXRyaWV2aW5nIHNlY3JldCBmb3IgSUQgJHtzZWNyZXRJZH06ICR7ZXJyb3IubmFtZX0gLSAke2Vycm9yLm1lc3NhZ2V9YFxuICAgICk7XG4gICAgaWYgKFxuICAgICAgZXJyb3IubmFtZSA9PT0gJ1Jlc291cmNlTm90Rm91bmRFeGNlcHRpb24nIHx8XG4gICAgICBlcnJvci5uYW1lID09PSAnSW52YWxpZFBhcmFtZXRlckV4Y2VwdGlvbidcbiAgICApIHtcbiAgICAgIHJldHVybiB1bmRlZmluZWQ7IC8vIFNlY3JldCBub3QgZm91bmQgb3IgYmFkIGlkZW50aWZpZXIsIHJldHVybiB1bmRlZmluZWQgZ3JhY2VmdWxseS5cbiAgICB9XG4gICAgLy8gRm9yIG90aGVyIGVycm9ycyBsaWtlIEFjY2Vzc0RlbmllZEV4Y2VwdGlvbiwgSW50ZXJuYWxTZXJ2aWNlRXJyb3JFeGNlcHRpb24sIGV0Yy4sIHJlLXRocm93LlxuICAgIHRocm93IGVycm9yO1xuICB9XG59O1xuXG4vKipcbiAqIENsZWFycyBhIHNwZWNpZmljIHNlY3JldCBvciB0aGUgZW50aXJlIGNhY2hlLlxuICogQHBhcmFtIHNlY3JldElkIChPcHRpb25hbCkgVGhlIEFSTiBvciBuYW1lIG9mIHRoZSBzZWNyZXQgdG8gY2xlYXIgZnJvbSBjYWNoZS4gSWYgbm90IHByb3ZpZGVkLCBjbGVhcnMgYWxsIGNhY2hlZCBzZWNyZXRzLlxuICovXG5leHBvcnQgY29uc3QgY2xlYXJTZWNyZXRDYWNoZSA9IChzZWNyZXRJZD86IHN0cmluZyk6IHZvaWQgPT4ge1xuICBpZiAoc2VjcmV0SWQpIHtcbiAgICAvLyBDbGVhciBhbGwgdmVyc2lvbnMvc3RhZ2VzIGZvciB0aGlzIHNlY3JldElkIHRoYXQgbWlnaHQgYmUgY2FjaGVkXG4gICAgT2JqZWN0LmtleXMoc2VjcmV0Q2FjaGUpLmZvckVhY2goKGtleSkgPT4ge1xuICAgICAgaWYgKGtleS5zdGFydHNXaXRoKHNlY3JldElkICsgJzonKSkge1xuICAgICAgICBkZWxldGUgc2VjcmV0Q2FjaGVba2V5XTtcbiAgICAgIH1cbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhgW1NlY3JldHNNYW5hZ2VyXSBDbGVhcmVkIGNhY2hlIGZvciBzZWNyZXQgSUQ6ICR7c2VjcmV0SWR9YCk7XG4gIH0gZWxzZSB7XG4gICAgT2JqZWN0LmtleXMoc2VjcmV0Q2FjaGUpLmZvckVhY2goKGtleSkgPT4gZGVsZXRlIHNlY3JldENhY2hlW2tleV0pO1xuICAgIGNvbnNvbGUubG9nKCdbU2VjcmV0c01hbmFnZXJdIEFsbCBzZWNyZXRzIGNsZWFyZWQgZnJvbSBjYWNoZS4nKTtcbiAgfVxufTtcblxuLy8gRXhhbXBsZSBVc2FnZTpcbi8qXG5pbXBvcnQgeyBnZXRTZWNyZXQgfSBmcm9tICcuL2F3cy1zZWNyZXRzLW1hbmFnZXInOyAvLyBBZGp1c3QgcGF0aCBhcyBuZWNlc3NhcnlcblxuZXhwb3J0IGNvbnN0IGV4YW1wbGVMYW1iZGFIYW5kbGVyID0gYXN5bmMgKCkgPT4ge1xuICAgIGNvbnN0IG15QXBpVG9rZW5Bcm4gPSBwcm9jZXNzLmVudi5NWV9BUElfVE9LRU5fU0VDUkVUX0FSTjtcbiAgICBpZiAoIW15QXBpVG9rZW5Bcm4pIHtcbiAgICAgICAgY29uc29sZS5lcnJvcihcIk1ZX0FQSV9UT0tFTl9TRUNSRVRfQVJOIGVudmlyb25tZW50IHZhcmlhYmxlIGlzIG5vdCBzZXQuXCIpO1xuICAgICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3QgYXBpVG9rZW4gPSBhd2FpdCBnZXRTZWNyZXQobXlBcGlUb2tlbkFybik7XG4gICAgICAgIGlmIChhcGlUb2tlbikge1xuICAgICAgICAgICAgY29uc29sZS5sb2coXCJTdWNjZXNzZnVsbHkgcmV0cmlldmVkIEFQSSB0b2tlbiAoZmlyc3QgZmV3IGNoYXJzKTpcIiwgYXBpVG9rZW4uc3Vic3RyaW5nKDAsIDUpKTtcbiAgICAgICAgICAgIC8vIFVzZSB0aGUgYXBpVG9rZW4uLi5cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiQVBJIHRva2VuIG5vdCBmb3VuZCBvciBpcyBlbXB0eS5cIik7XG4gICAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgICBjb25zb2xlLmVycm9yKFwiRmFpbGVkIHRvIHByb2Nlc3Mgc2VjcmV0OlwiLCBlcnJvcik7XG4gICAgfVxufTtcbiovXG4iXX0=
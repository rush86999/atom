// File: atomic-docker/project/functions/_utils/aws-secrets-manager.ts

import {
  SecretsManagerClient,
  GetSecretValueCommand,
  GetSecretValueCommandInput,
  GetSecretValueCommandOutput,
} from '@aws-sdk/client-secrets-manager';

// Environment variables expected (for AWS SDK configuration, typically handled by Lambda execution environment):
// - AWS_REGION (implicitly used by SDK if not specified in client constructor)

const secretsManagerClient = new SecretsManagerClient({
  region: process.env.AWS_REGION || 'us-east-1', // Default to us-east-1 or your specific primary region
});

interface SecretCacheEntry {
  value: string;
  timestamp: number;
}
const secretCache: Record<string, SecretCacheEntry> = {};
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
export const getSecret = async (
  secretId: string,
  versionId?: string,
  versionStage?: string
): Promise<string | undefined> => {
  const cacheKey = `${secretId}:${versionId || 'defaultVersionId'}:${versionStage || 'AWSCURRENT'}`;
  const cachedItem = secretCache[cacheKey];

  if (cachedItem && Date.now() - cachedItem.timestamp < CACHE_DURATION_MS) {
    console.log(
      `[SecretsManager] Returning cached secret for ID: ${secretId.split('/').pop()?.split('-')[0]}...`
    ); // Log part of secret name
    return cachedItem.value;
  }

  console.log(
    `[SecretsManager] Fetching secret from AWS Secrets Manager for ID: ${secretId.split('/').pop()?.split('-')[0]}...`
  );

  const params: GetSecretValueCommandInput = {
    SecretId: secretId,
  };
  if (versionId) params.VersionId = versionId;
  if (versionStage && !versionId) params.VersionStage = versionStage;

  try {
    const command = new GetSecretValueCommand(params);
    const data: GetSecretValueCommandOutput =
      await secretsManagerClient.send(command);

    let secretString: string | undefined;
    if (data.SecretString) {
      secretString = data.SecretString;
    } else if (data.SecretBinary) {
      // If secret is binary, decode it. For API keys, usually it's a string.
      // This example assumes SecretString is used. If binary, uncomment and adjust:
      // const buff = Buffer.from(data.SecretBinary); // For Node.js v14+ direct Buffer from Uint8Array
      // secretString = buff.toString('utf-8');
      console.warn(
        `[SecretsManager] Secret for ID ${secretId} is binary. This utility currently processes SecretString directly.`
      );
    } else {
      console.warn(
        `[SecretsManager] Secret for ID ${secretId} has no SecretString or SecretBinary content.`
      );
    }

    if (secretString) {
      secretCache[cacheKey] = { value: secretString, timestamp: Date.now() };
    }
    return secretString;
  } catch (error: any) {
    console.error(
      `[SecretsManager] Error retrieving secret for ID ${secretId}: ${error.name} - ${error.message}`
    );
    if (
      error.name === 'ResourceNotFoundException' ||
      error.name === 'InvalidParameterException'
    ) {
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
export const clearSecretCache = (secretId?: string): void => {
  if (secretId) {
    // Clear all versions/stages for this secretId that might be cached
    Object.keys(secretCache).forEach((key) => {
      if (key.startsWith(secretId + ':')) {
        delete secretCache[key];
      }
    });
    console.log(`[SecretsManager] Cleared cache for secret ID: ${secretId}`);
  } else {
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

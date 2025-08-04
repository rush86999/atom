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
export declare const getSecret: (secretId: string, versionId?: string, versionStage?: string) => Promise<string | undefined>;
/**
 * Clears a specific secret or the entire cache.
 * @param secretId (Optional) The ARN or name of the secret to clear from cache. If not provided, clears all cached secrets.
 */
export declare const clearSecretCache: (secretId?: string) => void;

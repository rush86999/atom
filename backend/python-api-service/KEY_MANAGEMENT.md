# Secure Key Management for GDrive OAuth

This document outlines the procedures for managing the `ATOM_OAUTH_ENCRYPTION_KEY` used for encrypting Google Drive OAuth tokens stored by the application.

## `ATOM_OAUTH_ENCRYPTION_KEY`

The `ATOM_OAUTH_ENCRYPTION_KEY` is critical for securing user OAuth tokens. It is used by `crypto_utils.py` with Fernet symmetric encryption.

### Key Format

*   The key **MUST** be a URL-safe base64-encoded string that represents 32 raw bytes.
*   A utility to generate a valid key is provided in `crypto_utils.py`. You can generate a new key by running:
    ```bash
    python atomic-docker/project/functions/python_api_service/crypto_utils.py
    ```
    Copy the "Example Generated Fernet Key" output.

### Secure Deployment

1.  **Environment Variable:**
    *   The primary method for providing this key to the application is through an environment variable named `ATOM_OAUTH_ENCRYPTION_KEY`.
    *   **Never hardcode this key into the source code or commit it to version control.**

2.  **Production Environment:**
    *   Use your deployment platform's mechanism for managing secret environment variables (e.g., AWS Secrets Manager, AWS Systems Manager Parameter Store, Google Cloud Secret Manager, Azure Key Vault, HashiCorp Vault, Docker secrets, Kubernetes Secrets).
    *   These services provide secure storage, access control, and often auditing for secrets.
    *   The application container/runtime should then securely load this environment variable from the secrets management service.

3.  **Development Environment:**
    *   For local development, you can use a `.env` file (make sure `.env` is in your `.gitignore`) to set the `ATOM_OAUTH_ENCRYPTION_KEY` environment variable.
    *   Alternatively, you can set it directly in your shell environment.

### Key Rotation

*   Regular key rotation is a good security practice. However, Fernet keys do not inherently support trivial rotation for already encrypted data.
*   If you need to rotate the `ATOM_OAUTH_ENCRYPTION_KEY`:
    1.  **Decrypt all existing OAuth tokens** in the database using the *old* key.
    2.  Generate a **new** `ATOM_OAUTH_ENCRYPTION_KEY`.
    3.  Deploy the application with the **new** key.
    4.  **Re-encrypt all the decrypted OAuth tokens** using the *new* key and store them back in the database.
    *   This process requires careful planning and execution, potentially involving a maintenance window or a more complex multi-key decryption setup during transition if zero downtime is required.
    *   Alternatively, forcing users to re-authenticate after a key rotation is a simpler approach if acceptable.

### Security Best Practices

*   **Limit Access:** Ensure that only necessary personnel and services have access to the `ATOM_OAUTH_ENCRYPTION_KEY`.
*   **Auditing:** If using a secrets management service, enable auditing to track access to the key.
*   **Backup:** While the key itself is derived (generated), ensure your method for storing and providing it to the application is reliable and backed up if it's part of a configuration file managed by a secrets service. The primary concern is the encrypted data; if the key is lost and not backed up, all encrypted tokens become unusable.

By following these guidelines, you can help ensure the secure deployment and management of the `ATOM_OAUTH_ENCRYPTION_KEY`.

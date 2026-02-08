#!/usr/bin/env ts-node
/**
 * OAuth Token Encryption Migration Script
 *
 * This script migrates existing plaintext OAuth tokens to encrypted format.
 * It should be run once to encrypt all tokens in the database.
 *
 * Usage:
 *   TOKEN_ENCRYPTION_KEY=<your-64-hex-char-key> \
 *   DATABASE_URL=postgresql://... \
 *   ts-node scripts/migrate-oauth-tokens.ts
 *
 * Dry run (no changes):
 *   DRY_RUN=true ts-node scripts/migrate-oauth-tokens.ts
 *
 * Environment Variables:
 *   - TOKEN_ENCRYPTION_KEY: 64-character hex string (required)
 *   - DATABASE_URL: PostgreSQL connection string (required)
 *   - DRY_RUN: Set to "true" to simulate migration without changes
 */

import { Pool, PoolClient } from 'pg';
import { encryptToken, getEncryptionService, TokenEncryptionService } from '@lib/tokenEncryption';

interface TokenRow {
  id: string;
  user_id: string;
  service_name: string;
  access_token: string;
  refresh_token: string | null;
  id_token: string | null;
  is_encrypted: boolean | null;
}

interface MigrationResult {
  totalTokens: number;
  alreadyEncrypted: number;
  encryptedCount: number;
  failedCount: number;
  errors: Array<{ token_id: string; error: string }>;
}

/**
 * Main migration function
 */
async function migrateOAuthTokens(): Promise<MigrationResult> {
  // Validate environment variables
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    throw new Error('DATABASE_URL environment variable is not set');
  }

  const dryRun = process.env.DRY_RUN === 'true';

  // Initialize encryption service
  let encryption: TokenEncryptionService;
  try {
    encryption = getEncryptionService();
    console.log('✅ Encryption service initialized');
  } catch (error) {
    console.error('❌ Failed to initialize encryption service:', error);
    throw error;
  }

  // Connect to database
  const pool = new Pool({ connectionString: databaseUrl });
  console.log('✅ Connected to database');

  const result: MigrationResult = {
    totalTokens: 0,
    alreadyEncrypted: 0,
    encryptedCount: 0,
    failedCount: 0,
    errors: [],
  };

  const client = await pool.connect();

  try {
    // Start transaction
    if (!dryRun) {
      await client.query('BEGIN');
    }

    // Check if is_encrypted column exists
    const columnCheck = await client.query(`
      SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'user_tokens'
        AND column_name = 'is_encrypted'
      );
    `);

    if (!columnCheck.rows[0].exists) {
      console.log('📋 Adding is_encrypted column to user_tokens table...');
      if (!dryRun) {
        await client.query(`
          ALTER TABLE user_tokens
          ADD COLUMN is_encrypted BOOLEAN DEFAULT FALSE;
        `);
      }
      console.log('✅ Added is_encrypted column');
    }

    // Fetch all tokens that are not encrypted
    const tokensResult = await client.query<TokenRow>(`
      SELECT
        id,
        user_id,
        service_name,
        access_token,
        refresh_token,
        id_token,
        COALESCE(is_encrypted, FALSE) as is_encrypted
      FROM user_tokens
      ORDER BY user_id, service_name;
    `);

    result.totalTokens = tokensResult.rows.length;
    console.log(`\n📊 Found ${result.totalTokens} tokens in database`);

    if (dryRun) {
      console.log('🔍 DRY RUN MODE - No changes will be made\n');
    }

    // Encrypt each token
    for (const token of tokensResult.rows) {
      try {
        // Skip if already encrypted
        if (token.is_encrypted) {
          result.alreadyEncrypted++;
          console.log(`⏭️  Skipping already encrypted token: ${token.id} (${token.service_name} for ${token.user_id})`);
          continue;
        }

        console.log(`\n🔐 Encrypting token: ${token.id} (${token.service_name} for ${token.user_id})`);

        // Encrypt access_token
        const encryptedAccessToken = encryption.encrypt(token.access_token);
        console.log(`   ✓ Encrypted access_token`);

        // Encrypt refresh_token if present
        let encryptedRefreshToken: string | null = null;
        if (token.refresh_token) {
          encryptedRefreshToken = encryption.encrypt(token.refresh_token);
          console.log(`   ✓ Encrypted refresh_token`);
        }

        // Encrypt id_token if present
        let encryptedIdToken: string | null = null;
        if (token.id_token) {
          encryptedIdToken = encryption.encrypt(token.id_token);
          console.log(`   ✓ Encrypted id_token`);
        }

        // Update database
        if (!dryRun) {
          await client.query(`
            UPDATE user_tokens
            SET
              access_token = $1,
              refresh_token = $2,
              id_token = $3,
              is_encrypted = TRUE,
              updated_at = NOW()
            WHERE id = $4;
          `, [encryptedAccessToken, encryptedRefreshToken, encryptedIdToken, token.id]);
        }

        result.encryptedCount++;
        console.log(`   ✅ Token ${token.id} encrypted successfully`);

      } catch (error) {
        result.failedCount++;
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        result.errors.push({ token_id: token.id, error: errorMessage });
        console.error(`   ❌ Failed to encrypt token ${token.id}:`, errorMessage);
      }
    }

    // Commit transaction
    if (!dryRun) {
      await client.query('COMMIT');
      console.log('\n✅ Migration committed successfully');
    } else {
      console.log('\n✅ Dry run completed successfully (no changes made)');
    }

    return result;

  } catch (error) {
    // Rollback on error
    if (!dryRun) {
      await client.query('ROLLBACK');
      console.error('\n❌ Migration failed, rolling back changes');
    }
    throw error;
  } finally {
    client.release();
    await pool.end();
    console.log('\n🔌 Database connection closed');
  }
}

/**
 * Main execution
 */
async function main() {
  console.log('🚀 OAuth Token Encryption Migration');
  console.log('=====================================\n');

  try {
    const result = await migrateOAuthTokens();

    // Print summary
    console.log('\n📊 Migration Summary:');
    console.log(`   Total tokens: ${result.totalTokens}`);
    console.log(`   Already encrypted: ${result.alreadyEncrypted}`);
    console.log(`   Newly encrypted: ${result.encryptedCount}`);
    console.log(`   Failed: ${result.failedCount}`);

    if (result.errors.length > 0) {
      console.log('\n❌ Errors:');
      result.errors.forEach(({ token_id, error }) => {
        console.log(`   - ${token_id}: ${error}`);
      });
    }

    if (result.failedCount > 0) {
      process.exit(1);
    }

  } catch (error) {
    console.error('\n💥 Migration failed:', error);
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  main();
}

export { migrateOAuthTokens };

import NextAuth, { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import GitHubProvider from "next-auth/providers/github";

export const authOptions: NextAuthOptions = {
  providers: [
    // Google OAuth Provider
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
    // GitHub OAuth Provider
    GitHubProvider({
      clientId: process.env.GITHUB_CLIENT_ID || "",
      clientSecret: process.env.GITHUB_CLIENT_SECRET || "",
    }),
    // Credentials provider for E2E testing and development - DISABLED IN PRODUCTION
    ...(process.env.NODE_ENV === "development" || process.env.ENABLE_TEST_CREDENTIALS === "true" ? [{
      ...CredentialsProvider({
        name: "Credentials",
        credentials: {
          email: { label: "Email", type: "email" },
          password: { label: "Password", type: "password" }
        },
        async authorize(credentials) {
          // Only allow test credentials in explicit test environments
          if (
            (process.env.NODE_ENV === "development" || process.env.ENABLE_TEST_CREDENTIALS === "true") &&
            credentials?.email === "test@example.com" &&
            credentials?.password === "testpassword"
          ) {
            console.warn("⚠️ Using test credentials - ensure this is only in development/test environments");
            return {
              id: "test-user-id",
              email: "test@example.com",
              name: "Test User",
              token: "test-token-for-e2e",
            };
          }

          if (!credentials?.email || !credentials?.password) {
            throw new Error("Email and password are required");
          }


          try {
            // Import query function for database access
            const { query } = await import('../../../lib/db');
            const bcrypt = await import('bcryptjs');

            // Check user in database
            const result = await query(
              'SELECT id, email, name, password_hash FROM users WHERE email = $1',
              [credentials.email]
            );

            if (result.rows.length === 0) {
              throw new Error("No user found with this email");
            }

            const user = result.rows[0];

            // Verify password
            const isValidPassword = await bcrypt.compare(
              credentials.password,
              user.password_hash
            );

            if (!isValidPassword) {
              throw new Error("Invalid password");
            }

            // Return user data
            return {
              id: user.id,
              email: user.email,
              name: user.name,
              token: "db-auth-token",
            };
          } catch (error) {
            // Log security events without leaking sensitive information
            console.error("Authentication attempt failed for:", credentials?.email || "unknown");
            if (error instanceof Error) {
              // Don't leak detailed error messages to potential attackers
              throw new Error("Invalid credentials");
            }
            throw new Error("Authentication failed");
          }
        },
      }),
    }] : []),
  ],
  callbacks: {
    async signIn({ user, account, profile }) {
      // Handle OAuth provider sign-ins (Google, GitHub)
      if (account && (account.provider === "google" || account.provider === "github")) {
        try {
          const { query } = await import('../../../lib/db');

          // Check if user exists by email
          const existingUser = await query(
            'SELECT id, email, name FROM users WHERE email = $1',
            [user.email]
          );

          let userId;

          if (existingUser.rows.length === 0) {
            // Create new user from OAuth
            const newUser = await query(
              'INSERT INTO users (email, name, email_verified, image, password_hash) VALUES ($1, $2, NOW(), $3, $4) RETURNING id',
              [user.email, user.name, user.image, ''] // Empty password_hash for OAuth users
            );
            userId = newUser.rows[0].id;
            console.log(`Created new user from ${account.provider}:`, user.email);
          } else {
            userId = existingUser.rows[0].id;
            // Update email_verified if not set (trust OAuth providers)
            await query(
              'UPDATE users SET email_verified = COALESCE(email_verified, NOW()), image = COALESCE(image, $1) WHERE email = $2',
              [user.image, user.email]
            );
            console.log(`Updated existing user from ${account.provider}:`, user.email);
          }

          // Store or update OAuth account info with encrypted tokens
          // NOTE: In production, implement proper encryption for OAuth tokens
          const crypto = await import('crypto');
          const algorithm = 'aes-256-gcm';
          const secretKey = process.env.OAUTH_TOKEN_ENCRYPTION_KEY || crypto.createHash('sha256').update(process.env.NEXTAUTH_SECRET || 'fallback-secret').digest();

          const encryptToken = (token: string | null): string | null => {
            if (!token) return null;
            try {
              const iv = crypto.randomBytes(16);
              const cipher = crypto.createCipher(algorithm, secretKey);
              cipher.setAAD(Buffer.from(account.provider, 'utf8'));
              let encrypted = cipher.update(token, 'utf8', 'hex');
              encrypted += cipher.final('hex');
              const authTag = cipher.getAuthTag();
              return iv.toString('hex') + ':' + authTag.toString('hex') + ':' + encrypted;
            } catch (error) {
              console.error('Failed to encrypt OAuth token:', error);
              return null;
            }
          };

          await query(
            `INSERT INTO user_accounts
              (user_id, provider, provider_account_id, access_token, refresh_token, expires_at, token_type, scope, id_token)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
             ON CONFLICT (user_id, provider)
             DO UPDATE SET
               provider_account_id = EXCLUDED.provider_account_id,
               access_token = EXCLUDED.access_token,
               refresh_token = EXCLUDED.refresh_token,
               expires_at = EXCLUDED.expires_at,
               token_type = EXCLUDED.token_type,
               scope = EXCLUDED.scope,
               id_token = EXCLUDED.id_token,
               updated_at = NOW()`,
            [
              userId,
              account.provider,
              account.providerAccountId,
              encryptToken(account.access_token) || null,
              encryptToken(account.refresh_token) || null,
              account.expires_at ? new Date(account.expires_at * 1000) : null,
              account.token_type || null,
              account.scope || null,
              encryptToken(account.id_token) || null,
            ]
          );

          console.log(`Stored ${account.provider} account for user:`, user.email);
        } catch (error) {
          console.error('Error in OAuth sign-in callback:', error);
          return false; // Deny sign-in on error
        }
      }
      return true; // Allow sign-in
    },
    async jwt({ token, user, account, trigger, session }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        // @ts-ignore
        token.backendToken = user.token || user.backendToken;

        // Record session in database
        try {
          const { query } = await import('../../../lib/db');
          // Use a hash of the token or a unique ID as session identifier
          // Since we don't have the actual session token here (it's generated later),
          // we'll use a combination of user ID and a timestamp/random string stored in the token
          // For now, we'll just update the last login time
          await query('UPDATE users SET last_login_at = NOW() WHERE id = $1', [user.id]);
        } catch (e) {
          console.error('Failed to update last login:', e);
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (token) {
        session.user.id = token.id as string;
        session.user.email = token.email as string;
        // @ts-ignore - backendToken added for internal use
        session.backendToken = token.backendToken as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/auth/signin",
    error: "/auth/error",
  },
  session: {
    strategy: "jwt" as const,
    maxAge: 24 * 60 * 60, // 1 day (reduced from 30 days for security)
    updateAge: 60 * 60, // Update session every hour
  },
  // Enhanced security configuration
  useSecureCookies: process.env.NODE_ENV === "production",
  cookies: {
    sessionToken: {
      name: process.env.NODE_ENV === "production" ? "__Secure-next-auth.session-token" : "next-auth.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
        domain: process.env.NEXTAUTH_URL ? new URL(process.env.NEXTAUTH_URL).hostname : undefined,
      },
    },
    callbackUrl: {
      name: process.env.NODE_ENV === "production" ? "__Secure-next-auth.callback-url" : "next-auth.callback-url",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
        domain: process.env.NEXTAUTH_URL ? new URL(process.env.NEXTAUTH_URL).hostname : undefined,
      },
    },
    csrfToken: {
      name: process.env.NODE_ENV === "production" ? "__Host-next-auth.csrf-token" : "next-auth.csrf-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
        domain: process.env.NEXTAUTH_URL ? new URL(process.env.NEXTAUTH_URL).hostname : undefined,
      },
    },
    pkceCodeVerifier: {
      name: process.env.NODE_ENV === "production" ? "__Secure-next-auth.pkce.code_verifier" : "next-auth.pkce.code_verifier",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
        domain: process.env.NEXTAUTH_URL ? new URL(process.env.NEXTAUTH_URL).hostname : undefined,
      },
    },
    state: {
      name: process.env.NODE_ENV === "production" ? "__Host-next-auth.state" : "next-auth.state",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
        domain: process.env.NEXTAUTH_URL ? new URL(process.env.NEXTAUTH_URL).hostname : undefined,
      },
    },
  },
  secret: process.env.NEXTAUTH_SECRET || (() => {
    throw new Error("NEXTAUTH_SECRET environment variable is required in production");
  })(),
};

export default NextAuth(authOptions);

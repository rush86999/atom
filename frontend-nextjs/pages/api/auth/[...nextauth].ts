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
          // Use Backend API for authentication (avoids direct DB access from frontend)
          try {
            const res = await fetch("http://127.0.0.1:8000/api/auth/login", {
              method: 'POST',
              headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
              },
              body: new URLSearchParams({
                username: credentials?.email || '',
                password: credentials?.password || ''
              })
            })

            const data = await res.json()

            if (res.ok && data.access_token) {
              // Get user details using the token
              // We could make another call to /api/auth/me here, but for now let's use the basic info
              return {
                id: "user-from-backend", // Ideally we'd decode the token or get ID from response if available
                email: credentials?.email,
                name: "Admin User", // Placeholder until we fetch profile
                token: data.access_token,
              }
            }

            return null
          } catch (error) {
            console.error("Login Check Error:", error)
            return null
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
              const key = typeof secretKey === 'string'
                ? Buffer.from(secretKey.slice(0, 32).padEnd(32, '0'))
                : secretKey;
              // @ts-ignore - Node crypto types compatibility
              const cipher = crypto.createCipheriv(algorithm, key, iv);
              let encrypted = cipher.update(token, 'utf8', 'hex');
              encrypted += cipher.final('hex');
              // @ts-ignore - getAuthTag exists on GCM ciphers
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
  secret: process.env.NEXTAUTH_SECRET || "development-fallback-secret-123",
};

export default NextAuth(authOptions);

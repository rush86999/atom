import NextAuth, { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { query } from './db';

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
        tenant_subdomain: { label: 'Tenant Subdomain', type: 'text' },
        totp_code: { label: '2FA Code', type: 'text' }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        // const db = new DatabaseService(); // REMOVED

        try {
          // Unified authentication flow: Always use backend API to ensure consistent JWT generation
          // This handles both admin and tenant users, and properly manages 2FA challenges

          let loginPayload = {
            username: credentials.email,
            password: credentials.password,
            totp_code: credentials.totp_code
          };

          // Call backend login endpoint
          const loginResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(loginPayload)
          });

          const loginData = await loginResponse.json();

          if (loginResponse.ok && loginData.access_token) {
            // Get rich user info from DB to populate session (keep existing rich session data)
            // Check admin_users first
            if (credentials.email.endsWith('@atom-saas.com') || credentials.email === 'admin@example.com') {
              const adminResult = await query(`
                SELECT au.*, ar.name as role_name, ar.permissions
                FROM admin_users au
                JOIN admin_roles ar ON au.role_id = ar.id
                WHERE au.email = $1 AND au.status = 'active'
              `, [credentials.email]);

              if (adminResult.rows.length > 0) {
                const admin = adminResult.rows[0];
                // Update last login
                await query('UPDATE admin_users SET last_login = NOW() WHERE id = $1', [admin.id]);

                return {
                  id: admin.id,
                  email: admin.email,
                  name: admin.name,
                  role: 'super_admin',
                  admin_role: admin.role_name,
                  permissions: admin.permissions,
                  tenant_id: null,
                  access_token: loginData.access_token // Use the backend token!
                };
              }
            }

            // Check standard users (including super_admins in main table)
            const userResult = await query(
              "SELECT * FROM users WHERE email = $1 AND status = 'active'",
              [credentials.email]
            );

            if (userResult.rows.length > 0) {
              const user = userResult.rows[0];

              // Determine tenant details if applicable
              let tenantSubdomain = null;
              let tenantName = null;
              let planType = null;

              if (user.tenant_id) {
                const tenantResult = await query('SELECT * FROM tenants WHERE id = $1', [user.tenant_id]);
                if (tenantResult.rows.length > 0) {
                  tenantSubdomain = tenantResult.rows[0].subdomain;
                  tenantName = tenantResult.rows[0].name;
                  planType = tenantResult.rows[0].plan_type;
                }
              }

              return {
                id: user.id,
                email: user.email,
                name: `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.name || user.email,
                role: user.role,
                admin_role: user.role === 'super_admin' ? 'super_admin' : undefined,
                permissions: user.role === 'super_admin' ? ['*'] : ['basic'],
                tenant_id: user.tenant_id,
                tenant_subdomain: tenantSubdomain,
                tenant_name: tenantName,
                plan_type: planType,
                access_token: loginData.access_token // Correctly pass the token
              };
            }
          } else if (loginResponse.status === 401 && loginData.detail === 'Invalid 2FA code') {
            throw new Error('INVALID_2FA_CODE');
          } else if (loginData.two_factor_required) {
            throw new Error("2FA_REQUIRED");
          }

          // Handle tenant user login
          const tenantSubdomain = credentials.tenant_subdomain || extractSubdomainFromRequest();

          if (tenantSubdomain) {
            // Get tenant by subdomain
            const tenantResult = await query(
              "SELECT * FROM tenants WHERE subdomain = $1 AND status = 'active'",
              [tenantSubdomain]
            );

            if (tenantResult.rows.length === 0) {
              return null;
            }

            const tenant = tenantResult.rows[0];

            // Set tenant context for database queries
            await query('SELECT set_tenant_context($1)', [tenant.id]);

            // Get user via backend login endpoint which now handles 2FA
            const loginResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/login`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                username: credentials.email,
                password: credentials.password,
                totp_code: credentials.totp_code
              })
            });

            const loginData = await loginResponse.json();

            if (loginResponse.ok && loginData.access_token) {
              // Get user info if token is returned
              const userResult = await query(
                "SELECT * FROM users WHERE email = $1 AND status = 'active'",
                [credentials.email]
              );

              if (userResult.rows.length > 0) {
                const user = userResult.rows[0];
                return {
                  id: user.id,
                  email: user.email,
                  name: user.name,
                  role: user.role,
                  tenant_id: user.tenant_id,
                  tenant_subdomain: tenant.subdomain,
                  tenant_name: tenant.name,
                  plan_type: tenant.plan_type,
                  permissions: ['basic'],
                  access_token: loginData.access_token // Pass token to session if needed
                };
              }
            } else if (loginResponse.status === 401 && loginData.detail === 'Invalid 2FA code') {
              throw new Error('INVALID_2FA_CODE');
            } else if (loginData.two_factor_required) {
              // Signal to frontend that 2FA is needed
              throw new Error("2FA_REQUIRED");
            }
          }

          return null;

        } catch (error: any) {
          if (error.message === '2FA_REQUIRED' || error.message === 'INVALID_2FA_CODE') {
            throw error;
          }
          console.error('Authentication error:', error);
          return null;
        }
      }
    }),
    // Add OAuth providers here for tenant users
    // GoogleProvider, MicrosoftProvider, etc.
  ],
  session: {
    strategy: 'jwt',
    maxAge: 24 * 60 * 60, // 24 hours
  },
  jwt: {
    secret: process.env.JWT_SECRET || process.env.NEXTAUTH_SECRET,
  },
  callbacks: {
    async jwt({ token, user }: { token: any, user?: any }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.name = user.name;
        token.role = user.role;
        token.tenant_id = user.tenant_id;
        token.tenant_subdomain = user.tenant_subdomain;
        token.tenant_name = user.tenant_name;
        token.plan_type = user.plan_type;
        token.admin_role = user.admin_role;
        token.permissions = user.permissions;
        token.backendToken = user.access_token;
      }
      return token;
    },
    async session({ session, token }: { session: any, token: any }) {
      session.user.id = token.id;
      session.user.email = token.email;
      session.user.name = token.name;
      session.user.role = token.role;
      session.user.tenant_id = token.tenant_id;
      session.user.tenant_subdomain = token.tenant_subdomain;
      session.user.tenant_name = token.tenant_name;
      session.user.plan_type = token.plan_type;
      session.user.admin_role = token.admin_role;
      session.user.permissions = token.permissions;
      session.backendToken = token.backendToken;
      return session;
    }
  },
  pages: {
    signIn: '/auth/signin',
    error: '/auth/error',
  }
};

function extractSubdomainFromRequest(): string | null {
  // This will be implemented in the middleware to extract from request hostname
  return null;
}

export default NextAuth(authOptions);
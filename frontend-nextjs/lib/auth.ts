import NextAuth, { NextAuthOptions } from 'next-auth';
import { createBackendSignOutEvent } from './backend-session-logout';
import CredentialsProvider from 'next-auth/providers/credentials';
import { createBackendCredentialsAuthorize } from './backend-credentials';

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
      authorize: createBackendCredentialsAuthorize(() => process.env.NEXT_PUBLIC_API_URL || process.env.API_BASE_URL || process.env.PYTHON_BACKEND_URL || ""),
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
  events: {
    signOut: createBackendSignOutEvent(() => process.env.NEXT_PUBLIC_API_URL || process.env.API_BASE_URL || process.env.PYTHON_BACKEND_URL || ""),
  },
  callbacks: {
    async jwt({ token, user }: { token: any, user?: any }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.name = user.name;
        token.role = user.role;
        token.workspace_id = user.workspace_id;
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
      session.user.workspace_id = token.workspace_id;
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
    signIn: "/auth/signin",
    error: '/auth/error',
  },
  secret: (() => {
    const s = process.env.NEXTAUTH_SECRET;
    if (!s) {
      if (process.env.NODE_ENV === "production") {
        throw new Error("CRITICAL: NEXTAUTH_SECRET is required in production");
      }
      console.warn("⚠️  NEXTAUTH_SECRET is not set. Using a temporary secret for development.");
      return "atom_development_only_secret_please_set_in_env";
    }
    return s;
  })(),
};

export default NextAuth(authOptions);
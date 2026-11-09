import NextAuth, { NextAuthOptions } from 'next-auth';
import { createBackendSignOutEvent } from './backend-session-logout';
import CredentialsProvider from 'next-auth/providers/credentials';
import { createBackendCredentialsAuthorize } from './backend-credentials';
import { projectCurrentBackendSession } from './backend-current-session';
import { resolveWebAuthSecret, resolveWebAuthBackend } from './web-auth-config';

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
      authorize: createBackendCredentialsAuthorize(resolveWebAuthBackend),
    }),
    // Add OAuth providers here for tenant users
    // GoogleProvider, MicrosoftProvider, etc.
  ],
  session: {
    strategy: 'jwt',
    maxAge: 24 * 60 * 60, // 24 hours
  },
  events: {
    signOut: createBackendSignOutEvent(resolveWebAuthBackend),
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
        if (typeof token.backendToken !== 'string' || !token.backendToken) throw new Error('BACKEND_SESSION_UNAVAILABLE');
      }
      return token;
    },
    async session({ session, token }) {
      return projectCurrentBackendSession(session, token, resolveWebAuthBackend);
    },
  },
  pages: {
    signIn: "/auth/signin",
    error: '/auth/error',
  },
  // Resolve at request time: a build must not bake a runtime signing key.
  get secret() { return resolveWebAuthSecret(); },
};

export default NextAuth(authOptions);
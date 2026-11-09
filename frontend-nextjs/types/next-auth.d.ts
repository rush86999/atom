import NextAuth, { DefaultSession } from "next-auth"
import { JWT } from "next-auth/jwt"

declare module "next-auth" {
    /**
     * Returned by `useSession`, `getSession` and received as a prop on the `SessionProvider` React Context
     */
    interface Session {
        user: {
            /** The user's postal address. */
            id: string
            /** Backend UserRole string (super_admin..guest) — set by the
             * canonical session callback, revalidated on every session read.
             * The API-first flow stores only the
             * backend token (role comes from lib/user-role.ts instead). */
            role?: string
            workspace_id?: string | null
            tenant_id?: string | null
            permissions?: string[]
        } & DefaultSession["user"]
        backendToken?: string
    }

    interface User {
        id: string
        token?: string
        backendToken?: string
        role?: string
        workspace_id?: string | null
        tenant_id?: string | null
        access_token?: string
    }
}

declare module "next-auth/jwt" {
    /** Returned by the `jwt` callback and `getToken`, when using JWT sessions */
    interface JWT {
        /** OpenID ID Token */
        idToken?: string
        id?: string
        role?: string
        workspace_id?: string | null
        tenant_id?: string | null
        permissions?: string[]
        backendToken?: string
    }
}

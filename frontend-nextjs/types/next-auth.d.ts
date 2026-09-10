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
             * jwt/session callbacks in lib/auth.ts. Only populated on the
             * NextAuth sign-in path; the API-first flow stores only the
             * backend token (role comes from lib/user-role.ts instead). */
            role?: string
            permissions?: string[]
        } & DefaultSession["user"]
        backendToken?: string
    }

    interface User {
        id: string
        token?: string
        backendToken?: string
    }
}

declare module "next-auth/jwt" {
    /** Returned by the `jwt` callback and `getToken`, when using JWT sessions */
    interface JWT {
        /** OpenID ID Token */
        idToken?: string
        id?: string
        role?: string
        permissions?: string[]
        backendToken?: string
    }
}

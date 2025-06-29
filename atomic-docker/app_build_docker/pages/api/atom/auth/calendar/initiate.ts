import type { NextApiRequest, NextApiResponse } from 'next'
import qs from 'qs'
import Cors from 'cors'
import { generateGoogleAuthUrl } from '@lib/api-backend-helper'

import { superTokensNextWrapper } from 'supertokens-node/nextjs'
import { verifySession } from 'supertokens-node/recipe/session/framework/express'
import supertokens from 'supertokens-node'
import { backendConfig } from '../../../../../config/backendConfig' // Adjusted path

supertokens.init(backendConfig())

// Initializing the cors middleware
const cors = Cors({
    methods: ['POST', 'GET', 'HEAD'],
    // Allow all origins for simplicity in dev, or specify your frontend URL
    // origin: process.env.NODE_ENV === 'production' ? ["https://atomiclife.app", /\.atomiclife\.app$/] : "*",
})

// Helper method to wait for a middleware to execute before continuing
function runMiddleware(
    req: NextApiRequest,
    res: NextApiResponse,
    fn: Function
) {
    return new Promise((resolve, reject) => {
        fn(req, res, (result: any) => {
            if (result instanceof Error) {
                return reject(result)
            }
            return resolve(result)
        })
    })
}


export default async function handler(req: NextApiRequest, res: NextApiResponse) { // Changed req: any, res: any to NextApiRequest, NextApiResponse
    try {
        await runMiddleware(req, res, cors)

        await superTokensNextWrapper(
            async (next) => {
              // Added type assertion for req and res as per SuperTokens examples for Next.js
              return await verifySession()(req as any, res as any, next)
            },
            req,
            res
        )

        const userId = req.session?.getUserId(); // Use optional chaining and get userId

        if (!userId) {
            // It's generally better to return a 401 Unauthorized status
            // or redirect to a login page if this is directly accessed by a user's browser.
            // For an API, 401 is more appropriate.
            return res.status(401).json({ message: "Authentication required." });
        }

        // Pass the userId as state to be used in the callback
        const authorizationUrl = generateGoogleAuthUrl(userId)

        return res.redirect(authorizationUrl)

    } catch (e: unknown) { // Changed type of e to unknown for better error handling
        console.error('Error in Google OAuth initiation:', e); // console.error for errors
        const errorMessage = e instanceof Error ? e.message : 'Internal server error during OAuth initiation.'
        // It's good practice to avoid sending detailed internal error messages to the client.
        return res.status(500).json({ statusCode: 500, message: 'Failed to initiate Google authentication.' })
    }
}

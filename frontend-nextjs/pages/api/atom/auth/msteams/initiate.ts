import type { NextApiRequest, NextApiResponse } from "next";
import {
  PublicClientApplication,
  Configuration,
  LogLevel,
  AuthorizationUrlRequest,
} from "@azure/msal-node";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../../auth/[...nextauth]";
import { logger } from "@lib/logger";

// TODO: Move these to a central constants file and manage via environment variables
const MSTEAMS_CLIENT_ID =
  process.env.MSTEAMS_CLIENT_ID || "YOUR_MSTEAMS_APP_CLIENT_ID";
const MSTEAMS_CLIENT_SECRET =
  process.env.MSTEAMS_CLIENT_SECRET || "YOUR_MSTEAMS_APP_CLIENT_SECRET"; // Needed for token exchange in callback
const MSTEAMS_REDIRECT_URI =
  process.env.MSTEAMS_REDIRECT_URI ||
  "http://localhost:3000/api/atom/auth/msteams/callback";
const MSTEAMS_AUTHORITY =
  process.env.MSTEAMS_AUTHORITY || "https://login.microsoftonline.com/common"; // Or your tenant ID

// Define the scopes required for reading chats and channel messages
const MSTEAMS_SCOPES = [
  "Chat.Read",
  "ChannelMessage.Read.All",
  "User.Read",
  "offline_access",
];

const msalConfig: Configuration = {
  auth: {
    clientId: MSTEAMS_CLIENT_ID,
    authority: MSTEAMS_AUTHORITY,
    clientSecret: MSTEAMS_CLIENT_SECRET, // Required for confidential client flows like auth code
  },
  system: {
    loggerOptions: {
      loggerCallback(loglevel, message, containsPii) {
        // console.log(`MSAL Log (${LogLevel[loglevel]}): ${message}`);
      },
      piiLoggingEnabled: false,
      logLevel: LogLevel.Warning,
    },
  },
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    logger.warn("[MSTeamsAuthInitiate] User not authenticated.");
    return res.status(401).json({ message: "Authentication required." });
  }

  const userId = session.user.id;

  if (
    !MSTEAMS_CLIENT_ID ||
    MSTEAMS_CLIENT_ID === "YOUR_MSTEAMS_APP_CLIENT_ID"
  ) {
    logger.error("[MSTeamsAuthInitiate] MS Teams Client ID not configured.");
    return res
      .status(500)
      .json({ message: "MS Teams OAuth configuration error on server." });
  }

  const pca = new PublicClientApplication(msalConfig); // For auth code flow, server-side usually uses ConfidentialClientApplication

  // NOTE: For server-side confidential client flow (which is typical when you have a client secret),
  // you'd use ConfidentialClientApplication. However, the initial redirect can be constructed
  // similarly. The crucial part is handling the secret securely in the callback.
  // The msal-node library's examples often show PublicClientApplication for some flows,
  // but for web apps exchanging code for token with a secret, ConfidentialClientApplication is standard.
  // Let's proceed with constructing the URL, the PCA/CCA choice primarily affects token acquisition.

  const authCodeUrlParameters: AuthorizationUrlRequest = {
    scopes: MSTEAMS_SCOPES,
    redirectUri: MSTEAMS_REDIRECT_URI,
    state: userId, // Using userId as state to verify in callback & link tokens
    prompt: "select_account", // Can be 'login', 'consent', 'select_account', or 'none'
  };

  try {
    // If using ConfidentialClientApplication:
    // const cca = new ConfidentialClientApplication(msalConfig);
    // const authUrl = await cca.getAuthCodeUrl(authCodeUrlParameters);

    // For PublicClientApplication (less common for server-side confidential handling but works for URL gen):
    const authUrl = await pca.getAuthCodeUrl(authCodeUrlParameters);

    logger.info(
      `[MSTeamsAuthInitiate] Redirecting user ${userId} to MS Teams auth URL.`,
    );
    res.redirect(authUrl);
  } catch (error) {
    logger.error(
      "[MSTeamsAuthInitiate] Error generating MS Teams auth URL:",
      error instanceof Error ? error.message : String(error),
    );
    res
      .status(500)
      .json({ message: "Failed to initiate MS Teams authentication." });
  }
}

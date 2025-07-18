
export const googleClientIdWeb = process.env.GOOGLE_CLIENT_ID_WEB
export const googleTokenUrl = 'https://oauth2.googleapis.com/token'
export const googleClientSecretWeb = process.env.GOOGLE_CLIENT_SECRET_WEB
export const googleAuthRedirectUri = process.env.GOOGLE_AUTH_REDIRECT_URL
export const googleClientIdIos = process.env.GOOGLE_ClIENT_ID_IOS

export const googleClientIdAtomicWeb = process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB
export const googleClientSecretAtomicWeb = process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB

// Gmail Integration Constants
export const googleClientIdGmail = process.env.GOOGLE_CLIENT_ID_GMAIL
export const googleClientSecretGmail = process.env.GOOGLE_CLIENT_SECRET_GMAIL
export const googleGmailRedirectUrl = process.env.GOOGLE_GMAIL_REDIRECT_URL
export const googleGmailScopes = [ // Array of scopes
    'https://www.googleapis.com/auth/gmail.readonly',
    // Add other Gmail scopes here if needed in the future, e.g., send, modify
].join(' '); // Google's library often expects scopes as a space-separated string

// MCP Integration Constants
export const googleClientIdMcp = process.env.GOOGLE_CLIENT_ID_MCP
export const googleClientSecretMcp = process.env.GOOGLE_CLIENT_SECRET_MCP
export const googleMcpRedirectUrl = process.env.GOOGLE_MCP_REDIRECT_URL
export const googleMcpScopes = [ // Array of scopes
    'https://www.googleapis.com/auth/drive.readonly',
    // Add other MCP scopes here if needed in the future
].join(' '); // Google's library often expects scopes as a space-separated string

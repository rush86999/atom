# Microsoft Teams Integration Guide for Atom Agent (Delegated Permissions)

This document outlines the setup, architecture, and usage of the Microsoft Teams integration feature within the Atom Agent, focusing on delegated permissions for accessing chat messages. This allows the agent to act on behalf of the user to search their Teams messages, retrieve content, and extract information.

## 1. Setup and Configuration (Delegated Permissions)

Proper setup is crucial for the Microsoft Teams integration with delegated permissions. This involves configuring an Azure AD Application, setting environment variables, and preparing for per-user token management.

### 1.1. Azure AD Application Registration

To enable Microsoft Graph API access with delegated permissions:

1.  **Register an Application:**
    *   Go to the [Azure portal](https://portal.azure.com/) > "Azure Active Directory" > "App registrations".
    *   Click "+ New registration".
    *   **Name:** Provide a name (e.g., "Atom Agent Teams Integration").
    *   **Supported account types:** Choose an appropriate option. For most scenarios allowing organizational accounts, "Accounts in this organizational directory only (Single tenant)" or "Accounts in any organizational directory (Any Azure AD directory - Multitenant)" would be suitable. "Accounts in any organizational directory ... and personal Microsoft accounts (e.g. Skype, Xbox)" could also be chosen if wider access is needed.
    *   **Redirect URI (Critical):**
        *   Select "Web" as the platform.
        *   Enter the redirect URI where Microsoft will send the authorization code after user consent. This URI must be handled by your backend. Example: `YOUR_APP_SERVICE_BASE_URL/auth/msteams/callback` (e.g., `http://localhost:YOUR_BACKEND_PORT/auth/msteams/callback` for local development, or your deployed backend callback URL). This will be configured via an environment variable like `MSGRAPH_DELEGATED_REDIRECT_URL`.
    *   Click "Register".

2.  **API Permissions (Delegated Permissions):**
    *   Navigate to "API permissions" for your newly registered app.
    *   Click "+ Add a permission" > "Microsoft Graph".
    *   Select "Delegated permissions".
    *   Add the following permissions:
        *   `Chat.Read`: Allows the app to read the signed-in user's 1:1 and group chat messages.
        *   `ChannelMessage.Read.All`: Allows the app to read messages in all channels the user can access.
        *   `User.Read`: Allows the app to sign in the user and read their basic profile (required for most delegated flows).
        *   `offline_access`: Allows the app to receive refresh tokens, enabling long-term access on behalf of the user without them being actively present.
        *   (Optional, consider if needed later) `Team.ReadBasic.All`: To read basic properties of teams the user is a member of (e.g., to list teams/channels).
    *   After adding permissions, an administrator might need to grant admin consent for these permissions on behalf of users in the organization, depending on tenant policies, especially for `ChannelMessage.Read.All`.

3.  **Certificates & Secrets:**
    *   Navigate to "Certificates & secrets".
    *   Click "+ New client secret".
    *   Provide a description and choose an expiry duration.
    *   **Important:** Copy the **Value** of the client secret immediately. It will not be visible again. This will be used as an environment variable.

4.  **Overview Tab:**
    *   Note down the "Application (client) ID" and "Directory (tenant) ID". These will be used in environment variables.

### 1.2. Environment Variables

The following environment variables must be set in your backend function's environment:

*   `MSGRAPH_DELEGATED_CLIENT_ID`: The Application (client) ID from your Azure AD app registration.
*   `MSGRAPH_DELEGATED_CLIENT_SECRET`: The client secret value you generated.
*   `MSGRAPH_DELEGATED_TENANT_ID`: The Directory (tenant) ID.
*   `MSGRAPH_DELEGATED_AUTHORITY`: The authority URL, typically `https://login.microsoftonline.com/{YOUR_TENANT_ID}`. Replace `{YOUR_TENANT_ID}` with your actual tenant ID or use `common` for multi-tenant apps (if configured that way).
*   `MSGRAPH_DELEGATED_REDIRECT_URL`: The exact redirect URI configured in your Azure AD app registration (e.g., `https://your-agent-backend.com/auth/msteams/callback`).
*   `MSGRAPH_DELEGATED_SCOPES`: A space-separated string of the delegated scopes you configured (e.g., `"Chat.Read ChannelMessage.Read.All User.Read offline_access"`).
*   `MSTEAMS_TOKEN_ENCRYPTION_KEY`: A **32-byte (64 hexadecimal characters)** secret key for AES-256-GCM encryption of stored user-specific OAuth tokens (similar to the Gmail key). **Generate a new, unique key for this.**
*   `ATOM_OPENAI_API_KEY`: Your OpenAI API key, required for LLM-powered query understanding and information extraction.
*   `ATOM_NLU_MODEL_NAME`: The OpenAI model to be used (e.g., `gpt-3.5-turbo`).
*   `POSTGRAPHILE_ENDPOINT`: The endpoint for your PostGraphile GraphQL API.
*   `FUNCTIONS_BASE_URL`: The base URL for your deployed backend functions.

### 1.3. Database Setup

A new table (e.g., `user_msteams_tokens`) will be required to store the encrypted OAuth tokens (access token, refresh token, and MSAL account information) for each authorizing user. This table should include:
*   `user_id` (uuid, foreign key to your users table, primary key)
*   `encrypted_access_token` (text)
*   `encrypted_refresh_token` (text)
*   `token_expiry_timestamp` (timestamptz)
*   `account_json_blob` (jsonb, to store the MSAL `AccountInfo` object)
*   `created_at`, `updated_at` (timestamptz)

Migrations for this table need to be created and applied.

### 1.4. Backend Function Deployment

The new and modified backend TypeScript functions need to be deployed:
*   The refactored service `atomic-docker/project/functions/msteams-service/service.ts`.
*   New agent skills in `atom-agent/skills/llm_msteams_query_understander.ts` and `atom-agent/skills/nlu_msteams_helper.ts`.
*   The new agent skills file `atom-agent/skills/msTeamsSkills.ts`.
*   The new command handler `atom-agent/command_handlers/msteams_command_handler.ts`.
*   New HTTP handlers (e.g., Express routes or serverless function endpoints) that expose functions from `msteams-service.ts`.

---

## 2. Token Management and Core Service (`msteams-service.ts`)

Located in `atomic-docker/project/functions/msteams-service/service.ts`. This service is responsible for all direct interactions with the Microsoft Graph API using delegated permissions.

### 2.1. OAuth 2.0 Authorization Code Flow
*   **`initializeConfidentialClientApp()`**: Initializes the MSAL `ConfidentialClientApplication` with delegated app credentials.
*   **`generateTeamsAuthUrl(userIdForContext: string, state?: string)`**: Generates the Microsoft authorization URL where the user will be redirected to grant consent. Includes scopes like `Chat.Read`, `ChannelMessage.Read.All`, `User.Read`, `offline_access`.
*   **`handleTeamsAuthCallback(userId: string, authorizationCode: string)`**:
    *   Called by your backend's redirect URI handler.
    *   Exchanges the `authorizationCode` for an access token and a refresh token using `clientApp.acquireTokenByCode()`.
    *   **Crucially, this function (and helper `storeUserMSTeamsTokens`) needs to be fully implemented to securely encrypt and store the obtained tokens (access token, refresh token, and MSAL `AccountInfo` object) in the `user_msteams_tokens` database table, associated with the `userId`.** (Currently placeholders).
*   **`getDelegatedMSGraphTokenForUser(userId: string)`**:
    *   **This function needs to be fully implemented to retrieve the stored, encrypted refresh token and `AccountInfo` for the given `userId` from the database.** (Currently placeholders).
    *   Decrypts the tokens.
    *   Uses `clientApp.acquireTokenSilent()` with the user's `AccountInfo` to get a valid access token. MSAL handles using the refresh token if the access token is expired.
    *   If tokens are refreshed, the new tokens (and potentially updated `AccountInfo`) must be re-encrypted and stored back in the database.
    *   Returns the valid access token.

### 2.2. Microsoft Graph API Interactions
*   **Meeting Functions (Updated):**
    *   `listMicrosoftTeamsMeetings(atomUserId: string, options)`: Fetches calendar events for the user using `/me/calendar/events`.
    *   `getMicrosoftTeamsMeetingDetails(atomUserId: string, eventId: string)`: Fetches specific event details using `/me/events/{id}`.
*   **New Chat Message Functions:**
    *   `searchTeamsMessages(atomUserId: string, searchQuery: string, maxResults: number)`: Uses the `/search/query` Graph API endpoint with `entityTypes: ['chatMessage']` to search messages based on a KQL query.
    *   `getTeamsChatMessageContent(atomUserId: string, chatId: string, messageId: string)`: Fetches a specific 1:1 or group chat message using `/me/chats/{chat-id}/messages/{message-id}`.
    *   `getTeamsChannelMessageContent(atomUserId: string, teamId: string, channelId: string, messageId: string)`: Fetches a specific channel message using `/teams/{team-id}/channels/{channel-id}/messages/{message-id}`.
    *   Note: Message permalinks (`webUrl`) are typically part of the message resource fetched by the content retrieval functions.

---

## 3. Agent Integration (`atom-agent/`)

These components enable the agent to understand and process MS Teams related commands.

### 3.1. MS Teams Skills (`skills/msTeamsSkills.ts` - New File)
This file contains agent-facing functions that usually call backend actions (which then trigger the `msteams-service.ts` functions).

*   **`searchMyMSTeamsMessages(userId: string, searchQuery: string, limit: number)`**: Calls the `searchUserMSTeamsMessages` backend action.
*   **`readMSTeamsMessage(userId: string, identifier: GetMSTeamsMessageDetailInput)`**: Calls the `getMSTeamsMessageDetail` backend action.
*   **`extractInformationFromMSTeamsMessage(messageContent: string, infoKeywords: string[])`**: Uses an LLM (OpenAI) with a specific prompt (`MSTEAMS_EXTRACTION_SYSTEM_PROMPT_TEMPLATE`) to extract information from message text.
*   **`getMSTeamsMessageWebUrl(userId: string, identifier: GetMSTeamsMessageWebUrlInput)`**: Calls the `getMSTeamsMessageWebUrl` backend action (which likely just extracts the `webUrl` from the full message detail fetched by the service).

### 3.2. NLU for Teams Search (`skills/llm_msteams_query_understander.ts` & `skills/nlu_msteams_helper.ts`)
1.  **`llm_msteams_query_understander.ts`**:
    *   Defines `StructuredMSTeamsQuery` interface.
    *   **`understandMSTeamsSearchQueryLLM(rawUserQuery: string)`**: Uses an LLM with `MSTEAMS_QUERY_UNDERSTANDING_SYSTEM_PROMPT` to parse natural language into a `StructuredMSTeamsQuery` object.
2.  **`nlu_msteams_helper.ts`**:
    *   **`buildMSTeamsSearchQuery(params: StructuredMSTeamsQuery)`**: Converts the `StructuredMSTeamsQuery` into a KQL string for the Graph Search API.

### 3.3. Agent Command Handler (`command_handlers/msteams_command_handler.ts`)
*   **`handleMSTeamsInquiry(request: ParsedNluMSTeamsRequest)`**:
    *   Orchestrates the flow: NLU parsing -> KQL query building -> calling `searchMyMSTeamsMessages` -> (optional) disambiguation -> calling `readMSTeamsMessage` -> performing actions like `extractInformationFromMSTeamsMessage` or `getMSTeamsMessageWebUrl`.
    *   Formats user-facing responses.

---

## 4. Backend Actions

These actions expose the backend service functions to the agent skills layer.

*   **OAuth Placeholders (to be implemented for user interaction):**
    *   `generateMSTeamsAuthUrl`
    *   `handleMSTeamsAuthCallback`
*   **Message Interaction Actions:**
    *   `searchUserMSTeamsMessages`
    *   `getMSTeamsMessageDetail`
    *   `getMSTeamsMessageWebUrl`

---

## 5. Frontend Overview

Interaction with these advanced MS Teams chat features is primarily via the agent's chat interface. Future frontend work could include:
*   A settings page section for connecting/disconnecting the MS Teams integration (initiating the OAuth flow and displaying connection status).
*   UI elements for displaying Teams message search results or details if desired outside the chat context.

---
This guide will be updated as the features evolve, particularly the token storage and frontend components.

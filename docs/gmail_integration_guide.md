# Gmail Integration Guide for Atom Agent

This document outlines the setup, architecture, and usage of the Gmail integration feature within the Atom Agent. This feature allows the agent to connect to a user's Gmail account to search emails and retrieve their content, forming a foundation for more advanced NLU-driven email processing tasks.

## 1. Setup and Configuration

Proper setup is crucial for the Gmail integration to function correctly. This involves configuration in Google Cloud Console, setting environment variables, and ensuring database and backend deployments are up to date.

### 1.1. Google Cloud Console Setup

To enable Gmail API access, you need to configure a project in the Google Cloud Console:

1.  **Create/Select a Project:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.

2.  **Enable Gmail API:**
    *   Navigate to "APIs & Services" > "Library".
    *   Search for "Gmail API" and enable it for your project.

3.  **Configure OAuth 2.0 Consent Screen:**
    *   Navigate to "APIs & Services" > "OAuth consent screen".
    *   Choose "User Type" (e.g., "External").
    *   Fill in app information:
        *   App name (e.g., "Atom Agent Email Integration")
        *   User support email
        *   Developer contact information
    *   **Scopes:** Add the necessary scopes. For the current implementation, `https://www.googleapis.com/auth/gmail.readonly` is used. If future features require sending or modifying emails, additional scopes like `https://www.googleapis.com/auth/gmail.send` or `https://www.googleapis.com/auth/gmail.modify` will be needed.
    *   Add test users during development if your app is not yet verified by Google.

4.  **Create OAuth 2.0 Credentials:**
    *   Navigate to "APIs & Services" > "Credentials".
    *   Click "+ CREATE CREDENTIALS" > "OAuth client ID".
    *   **Application type:** Select "Web application".
    *   **Name:** Give it a name (e.g., "Atom Agent Web Client").
    *   **Authorized JavaScript origins:** Add your frontend URL(s) (e.g., `http://localhost:3000` for local dev, and your deployed frontend URL).
    *   **Authorized redirect URIs:** This is critical. Add the URI where Google will redirect after user authentication. The backend is configured to expect this via the `GOOGLE_GMAIL_REDIRECT_URL` environment variable. A typical value would be `YOUR_FRONTEND_APP_URL/auth/gmail/callback` (e.g., `http://localhost:3000/auth/gmail/callback`).
    *   After creation, Google will provide a **Client ID** and **Client Secret**. Securely store these values; they will be used in environment variables.

### 1.2. Environment Variables

The following environment variables must be set in your backend function's environment:

*   `GOOGLE_CLIENT_ID_GMAIL`: The Client ID obtained from Google Cloud Console.
*   `GOOGLE_CLIENT_SECRET_GMAIL`: The Client Secret obtained from Google Cloud Console.
*   `GOOGLE_GMAIL_REDIRECT_URL`: The full URL that Google will redirect to after user authentication. This **must match exactly** one of the URIs configured in your Google Cloud Console credentials. Example: `https://yourapp.com/auth/gmail/callback` or `http://localhost:3000/auth/gmail/callback` for local development.
*   `GMAIL_TOKEN_ENCRYPTION_KEY`: A **32-byte (64 hexadecimal characters)** secret key used for AES-256-GCM encryption of the stored Gmail OAuth tokens. Generate a cryptographically strong random key for this (e.g., using `openssl rand -hex 32`). **Keep this key secure; its compromise would expose user tokens.**
*   `HASURA_GRAPHQL_ENDPOINT`: The endpoint for your Hasura GraphQL API (e.g., `http://localhost:8080/v1/graphql`).
*   `HASURA_ADMIN_SECRET`: (Optional) If agent skills call Hasura actions with admin rights. The `callHasuraActionGraphQL` helper in `emailSkills.ts` is set up to pass user role and ID, assuming user-permissioned actions.
*   `ATOM_OPENAI_API_KEY`: Your OpenAI API key, required for the LLM-powered query understanding and information extraction modules.
*   `ATOM_NLU_MODEL_NAME`: The OpenAI model to be used (e.g., `gpt-3.5-turbo`, `gpt-4`). This is used by `nluService.ts`, `llm_email_query_understander.ts`, and the LLM-based `extractInformationFromEmailBody`.

### 1.3. Hasura Setup

1.  **Apply Migrations:**
    *   The new database table `public.user_gmail_tokens` is defined in a migration file (e.g., `atomic-docker/project/metadata/databases/default/migrations/TIMESTAMP_add_user_gmail_tokens_table/up.sql`).
    *   Apply migrations using the Hasura CLI: `hasura migrate apply --database-name default` (or your database name).
2.  **Apply Metadata:**
    *   Changes to `actions.graphql`, `actions.yaml`, and table tracking YAML files (`public_user_gmail_tokens.yaml`, `tables.yaml`, `public_User.yaml`) are made.
    *   Apply metadata using the Hasura CLI: `hasura metadata apply`.

### 1.4. Backend Function Deployment

The new and modified backend TypeScript functions need to be deployed. These include:
*   Functions in `atomic-docker/project/functions/google-api-auth/_libs/`
*   Handlers in `atomic-docker/project/functions/gmail-integration/`
*   The `gmail-service/service.ts` file.
*   Agent skills in `atom-agent/skills/emailSkills.ts`.
*   LLM helpers `atom-agent/skills/llm_email_query_understander.ts` and `atom-agent/skills/nlu_email_helper.ts`.
*   Command handler `atom-agent/command_handlers/email_command_handler.ts`.
*   Updated `atom-agent/skills/nluService.ts`.

Ensure deployed function URLs match `actions.yaml` handlers.

---

## 2. Backend API and Services

This section details the backend components responsible for the Gmail integration, including Hasura Actions, core service logic, and how OAuth tokens are managed.

### 2.1. Hasura Actions

Handlers for these actions are located in `atomic-docker/project/functions/gmail-integration/`.

1.  **`generate_gmail_auth_url`**: Generates Google OAuth URL. (Returns `GenerateGmailAuthUrlOutput`)
2.  **`handle_gmail_auth_callback`**: Handles Google callback, exchanges code for tokens, encrypts and stores them. (Takes `HandleGmailAuthCallbackInput`, returns `HandleGmailAuthCallbackOutput`)
3.  **`refresh_user_gmail_token`**: Refreshes expired access token. (Returns `RefreshUserGmailTokenOutput`)
4.  **`search_user_gmail`**: Searches user's Gmail. (Takes `GmailSearchQueryInput`, returns `GmailSearchOutput`)
5.  **`get_user_gmail_content`**: Fetches specific email content. (Takes `GetUserGmailContentInput`, returns `GetUserGmailContentOutput`)
6.  **`get_gmail_connection_status`**: Checks if Gmail is connected. (Query action, returns `GmailConnectionStatusOutput`)
7.  **`disconnect_gmail_account`**: Deletes user's Gmail tokens. (Returns `DisconnectGmailAccountOutput`)

(Refer to `actions.graphql` for detailed input/output types of these actions.)

### 2.2. Core Gmail Service (`atomic-docker/project/functions/gmail-service/service.ts`)

*   **`getGmailClientForUser(userId: string)`**: Retrieves/refreshes tokens, returns authenticated `google.auth.OAuth2` client.
*   **`searchUserEmails(userId: string, query: string, maxResults: number)`**: Uses client to call `gmail.users.messages.list()`.
*   **`getUserEmailContent(userId: string, emailId: string)`**: Uses client to call `gmail.users.messages.get({format: 'full'})`.

### 2.3. Token Storage (`user_gmail_tokens` Table)

*   **Table:** `public.user_gmail_tokens`
*   **Purpose:** Securely stores encrypted OAuth 2.0 access and refresh tokens.
*   **Key Columns:** `user_id`, `encrypted_access_token`, `encrypted_refresh_token`, `token_expiry_timestamp`, `scopes`.
*   **Encryption:** AES-256-GCM via `GMAIL_TOKEN_ENCRYPTION_KEY`.

---

## 3. Agent Integration

Located under `atomic-docker/project/functions/atom-agent/`.

### 3.1. Email Skills (`skills/emailSkills.ts`)

*   **`searchMyEmails(userId: string, searchQuery: string, limit: number)`**: Calls `search_user_gmail` action, basic mapping to agent's `Email[]` type.
*   **`readEmail(userId: string, emailId: string)`**: Calls `get_user_gmail_content` action, maps to agent's `Email` type, includes body parsing via `extractReadableBody`.
*   **`extractReadableBody(part: any)`**: Helper to parse MIME parts, preferring `text/plain`, with basic HTML stripping fallback.
*   **`extractInformationFromEmailBody(emailBody: string, infoKeywords: string[])`**: LLM-powered extraction using `EXTRACTION_SYSTEM_PROMPT_TEMPLATE` to get specific info based on keywords.
*   **`sendEmail(...)`**: Unchanged by Gmail reading feature.

### 3.2. NLU Email Query Construction and Understanding

1.  **Main NLU Service (`skills/nluService.ts`)**
    *   **Intent `QueryEmails`:** `SYSTEM_PROMPT` updated to capture `raw_email_search_query`, `action_on_email`, and related keywords/questions. Basic date resolution for common terms (e.g., "yesterday", "last week") is performed here, adding `resolved_date_range` to entities.
2.  **LLM Email Query Understander (`skills/llm_email_query_understander.ts`)**
    *   **`understandEmailSearchQueryLLM(rawUserQuery: string)`**: Takes raw query, uses LLM with `QUERY_UNDERSTANDING_SYSTEM_PROMPT` (including `{{CURRENT_DATE}}` injection) to parse into `StructuredEmailQuery` (dates, sender, subject, etc.).
3.  **NLU Email Helper (`skills/nlu_email_helper.ts`)**
    *   **`buildGmailSearchQuery(params: StructuredEmailQuery)`**: Converts `StructuredEmailQuery` from LLM understander into Gmail API query string.

### 3.3. Agent Command Handler (`command_handlers/email_command_handler.ts`)

*   **`handleEmailInquiry(request: ParsedNluEmailRequest)`**:
    *   Receives `ParsedNluEmailRequest` (containing `userId`, `rawEmailSearchQuery`, `actionRequested`).
    *   Calls `understandEmailSearchQueryLLM` to get structured search parameters.
    *   Calls `buildGmailSearchQuery`.
    *   Calls `searchMyEmails`, then `readEmail`.
    *   Performs action based on `actionRequested.actionType` (e.g., calls LLM-powered `extractInformationFromEmailBody` for `FIND_SPECIFIC_INFO`).
    *   Formats response.

---

## 4. Frontend Overview

Located in `atomic-docker/app_build_docker/pages/`.

### 4.1. Connection Management (`Settings/UserViewCalendarAndContactIntegrations.tsx`)

*   **Functionality:**
    *   Fetches and displays Gmail connection status (`get_gmail_connection_status` query).
    *   Shows "Connected as: [email]" or "Gmail is not connected."
    *   Provides "Connect to Gmail" button (calls `generate_gmail_auth_url` action, redirects to Google).
    *   Provides "Disconnect Gmail" button (calls `disconnect_gmail_account` action).

### 4.2. OAuth Callback Page (`auth/gmail/callback.tsx`)
*   Handles redirect from Google, calls `handle_gmail_auth_callback` action, displays status, redirects to settings.

### 4.3. Proof-of-Concept Search UI (`Gmail/UserGmailSearch.tsx`)
*   Basic UI to test `search_user_gmail` action.

---

This concludes the main sections of the documentation.

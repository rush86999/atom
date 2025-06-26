# Slack Integration Guide for Atom Agent

This document outlines the setup, architecture, and usage of the enhanced Slack integration feature within the Atom Agent. This feature allows the agent to connect to a user's Slack workspace to search messages, retrieve their content, and extract information, leveraging NLU for advanced processing.

## 1. Setup and Configuration

Proper setup is crucial for the Slack integration to function correctly. This involves configuring a Slack App, setting environment variables, and ensuring backend deployments are up to date.

### 1.1. Slack App Configuration

To enable Slack API access, you need to create and configure a Slack App:

1.  **Create a Slack App:**
    *   Go to [api.slack.com/apps](https://api.slack.com/apps).
    *   Click "Create New App".
    *   Choose "From scratch", provide an App Name (e.g., "Atom Agent"), and select your development workspace.

2.  **Add Scopes (Bot Token Scopes):**
    *   Navigate to "OAuth & Permissions" in your app's settings.
    *   Scroll down to "Bot Token Scopes".
    *   Add the following scopes:
        *   `search:read` (to search messages and files)
        *   `channels:history` (to view messages in public channels)
        *   `groups:history` (to view messages in private channels)
        *   `im:history` (to view messages in direct messages)
        *   `mpim:history` (to view messages in group direct messages)
        *   `channels:read` (to view basic information about public channels)
        *   `groups:read` (to view basic information about private channels)
        *   `im:read` (to view basic information about direct messages)
        *   `mpim:read` (to view basic information about group direct messages)
        *   `users:read` (to view basic information about users, e.g., resolving user IDs to names)
        *   `chat:write` (to send messages as the app)
        *   `chat:get.permalink` (to retrieve permalinks for messages)

3.  **Install App to Workspace:**
    *   After adding scopes, install (or reinstall) your app to your workspace.
    *   This will generate a "Bot User OAuth Token".

4.  **Bot User OAuth Token:**
    *   Copy the "Bot User OAuth Token" (starts with `xoxb-`). This token will be used as an environment variable.

### 1.2. Environment Variables

The following environment variable must be set in your backend function's environment:

*   `ATOM_SLACK_BOT_TOKEN`: The Bot User OAuth Token obtained from your Slack App's "OAuth & Permissions" page. This token is used by the agent to interact with the Slack API.
*   `ATOM_OPENAI_API_KEY`: Your OpenAI API key, required for the LLM-powered query understanding and information extraction modules for Slack.
*   `ATOM_NLU_MODEL_NAME`: The OpenAI model to be used (e.g., `gpt-3.5-turbo`, `gpt-4`). This is used by `llm_slack_query_understander.ts` and `extractInformationFromSlackMessage`.
*   `HASURA_GRAPHQL_ENDPOINT`: The endpoint for your Hasura GraphQL API (e.g., `http://localhost:8080/v1/graphql` or `http://hasura:8080/v1/graphql` if running in Docker).
*   `FUNCTIONS_BASE_URL`: The base URL for your deployed backend functions that Hasura will call.

### 1.3. Hasura Setup

1.  **Apply Metadata:**
    *   The new Slack actions and their types are defined in `atomic-docker/project/metadata/actions.graphql` and `atomic-docker/project/metadata/actions.yaml`.
    *   Apply metadata using the Hasura CLI: `hasura metadata apply`. This will register the new actions with Hasura.
    *   Ensure your Hasura instance can reach the `FUNCTIONS_BASE_URL` where the action handlers will be deployed.

### 1.4. Backend Function Deployment

The new and modified backend TypeScript functions need to be deployed. These include:
*   The new service `atomic-docker/project/functions/slack-service/service.ts`.
*   New agent skills in `atom-agent/skills/llm_slack_query_understander.ts` and `atom-agent/skills/nlu_slack_helper.ts`.
*   Updated agent skills in `atom-agent/skills/slackSkills.ts`.
*   The new command handler `atom-agent/command_handlers/slack_command_handler.ts`.
*   New HTTP handlers (e.g., Express routes or serverless function endpoints) that expose the relevant functions from `slack-service.ts` (like `searchSlackMessages`, `getSlackMessageContent`, `getSlackPermalink`) to be callable by Hasura actions. The URLs for these handlers must match those defined in `actions.yaml`.

---

## 2. Backend API and Services

This section details the backend components responsible for the Slack integration.

### 2.1. Hasura Actions

Handlers for these actions are new HTTP endpoints that wrap functions from `slack-service/service.ts`.

1.  **`searchUserSlackMessages`**:
    *   GraphQL Action defined in `actions.graphql` and `actions.yaml`.
    *   Input: `SlackSearchQueryInput` (query, maxResults)
    *   Output: `SlackSearchOutput` (success, message, results: [SlackMessageObject])
    *   Handler URL (example): `{{FUNCTIONS_BASE_URL}}/search-user-slack-messages`
    *   Permissions: `user` role.
    *   Comment: "Searches messages in the user's connected Slack workspace."
2.  **`getSlackMessageDetail`**:
    *   GraphQL Action defined in `actions.graphql` and `actions.yaml`.
    *   Input: `SlackMessageIdentifierInput` (channelId, messageTs)
    *   Output: `SlackMessageOutput` (success, message, slackMessage: SlackMessageObject)
    *   Handler URL (example): `{{FUNCTIONS_BASE_URL}}/get-slack-message-detail`
    *   Permissions: `user` role.
    *   Comment: "Fetches the detailed content of a specific Slack message."
3.  **`getSlackMessagePermalink`**:
    *   GraphQL Action defined in `actions.graphql` and `actions.yaml`.
    *   Input: `SlackMessageIdentifierInput` (channelId, messageTs)
    *   Output: `SlackPermalinkOutput` (success, message, permalink)
    *   Handler URL (example): `{{FUNCTIONS_BASE_URL}}/get-slack-message-permalink`
    *   Permissions: `user` role.
    *   Comment: "Gets a permalink for a specific Slack message."

(Refer to `actions.graphql` for detailed input/output GraphQL type definitions like `SlackMessageObject`, `SlackMessageFileObject`, etc.)

### 2.2. Core Slack Service (`atomic-docker/project/functions/slack-service/service.ts`)

This service contains the core logic for interacting with the Slack API.

*   **`getSlackClientForUser(userId: string)`**: Returns an initialized Slack WebClient using the global `ATOM_SLACK_BOT_TOKEN`.
*   **`searchSlackMessages(userId: string, query: string, maxResults: number)`**: Uses `client.search.messages` to find messages based on a query string. Handles basic pagination and transforms results into `AgentSlackMessage[]`.
*   **`getSlackMessageContent(userId: string, channelId: string, messageTs: string)`**: Uses `client.conversations.history` to fetch a specific message's full content by its channel and timestamp. Returns an `AgentSlackMessage` or null.
*   **`getSlackPermalink(userId: string, channelId: string, messageTs: string)`**: Uses `client.chat.getPermalink` to get a direct link to a message. Returns a permalink string or null.

---

## 3. Agent Integration

Located under `atomic-docker/project/functions/atom-agent/`. These components enable the agent to understand Slack-related commands and use the Slack service.

### 3.1. Slack Skills (`skills/slackSkills.ts`)

This file contains functions that the agent's command handler can call. These skills typically wrap calls to Hasura actions, which then trigger the `slack-service`.

*   **Existing Skills (Updated):**
    *   `listSlackChannels`: Lists public/private channels, DMs, and MPIMs. Uses the Slack WebClient directly.
    *   `sendSlackMessage`: Sends a message to a channel or user. Uses the Slack WebClient directly. Includes improved channel/user ID resolution.
*   **New Skills (for AI-powered features):**
    *   `searchMySlackMessages(userId: string, searchQuery: string, limit: number)`: Calls the `searchUserSlackMessages` Hasura action. Transforms results from the action (which should be `SlackMessageObject[]`) into the agent's internal `SlackMessage[]` type (defined in `atom-agent/types.ts`).
    *   `readSlackMessage(userId: string, channelId: string, messageTs: string)`: Calls the `getSlackMessageDetail` Hasura action. Transforms the result into a `SlackMessage` object.
    *   `extractInformationFromSlackMessage(messageText: string, infoKeywords: string[])`: Uses an LLM (via OpenAI API) with a specific prompt (`SLACK_EXTRACTION_SYSTEM_PROMPT_TEMPLATE`) to extract desired pieces of information from a given Slack message's text content.
    *   `getSlackMessagePermalink(userId: string, channelId: string, messageTs: string)`: Calls the `getSlackMessagePermalink` Hasura action.

### 3.2. NLU Slack Query Construction and Understanding

These modules are responsible for interpreting natural language commands related to Slack searching.

1.  **LLM Slack Query Understander (`skills/llm_slack_query_understander.ts`)**
    *   Defines `StructuredSlackQuery` interface (fields like `fromUser`, `inChannel`, `textKeywords`, dates, `hasFile`, etc.).
    *   **`understandSlackSearchQueryLLM(rawUserQuery: string)`**: Takes a raw natural language query from the user. It uses an LLM (e.g., GPT model via OpenAI API) with the `SLACK_QUERY_UNDERSTANDING_SYSTEM_PROMPT`. This prompt is engineered to guide the LLM to parse the user's query and output a JSON object matching the `StructuredSlackQuery` interface. It handles relative date conversions (e.g., "yesterday", "last week") by injecting the `{{CURRENT_DATE}}` into the prompt.
2.  **NLU Slack Helper (`skills/nlu_slack_helper.ts`)**
    *   **`buildSlackSearchQuery(params: StructuredSlackQuery)`**: Takes the `StructuredSlackQuery` object (output from `understandSlackSearchQueryLLM`) and constructs a search query string compatible with the Slack API's `search.messages` endpoint (e.g., using operators like `from:`, `in:`, `has:`, `on:`, `before:`, `after:`).

### 3.3. Agent Command Handler (`command_handlers/slack_command_handler.ts`)

This new handler orchestrates the agent's response to Slack-related NLU intents.

*   **`handleSlackInquiry(request: ParsedNluSlackRequest): Promise<string>`**
    *   **Input:** `ParsedNluSlackRequest` which includes `userId`, `rawSlackSearchQuery` (the user's natural language input for searching), an `actionRequested` object (detailing what to do, e.g., `FIND_INFO_IN_SLACK_MESSAGE`), and optionally `targetChannelId`/`targetMessageTs` if the NLU directly identified a specific message.
    *   **Orchestration Flow:**
        1.  **Message Identification:**
            *   If a specific message is targeted by `targetChannelId` and `targetMessageTs`, it calls `readSlackMessage`.
            *   Otherwise (for new searches):
                *   It calls `understandSlackSearchQueryLLM` with the `rawSlackSearchQuery` to get a `StructuredSlackQuery`.
                *   It then calls `buildSlackSearchQuery` with this structured object to get the final Slack API-compatible query string.
                *   It calls the `searchMySlackMessages` skill to find relevant messages.
                *   **Disambiguation Logic:** If `searchMySlackMessages` returns multiple results, `handleSlackInquiry` formulates a message asking the user for clarification (e.g., listing snippets of the first few messages and asking to choose).
                *   If only one email is found (or after successful clarification), it proceeds to call `readSlackMessage` for the selected message to ensure full content is loaded.
        2.  **Action Execution:** Based on the `actionRequested.actionType`:
            *   `GET_SLACK_MESSAGE_CONTENT`: Provides a text preview of the message.
            *   `FIND_INFO_IN_SLACK_MESSAGE`: Calls `extractInformationFromSlackMessage` with the message text and specified keywords.
            *   `GET_SLACK_MESSAGE_LINK`: Calls `getSlackMessagePermalink`.
            *   `SUMMARIZE_SLACK_MESSAGE`: (Placeholder for future LLM-based summarization).
        3.  **Response Formatting:** Constructs a natural language response suitable for the user.

---

## 4. Frontend Overview

(This section can be updated if/when UI elements are added for managing or interacting with the enhanced Slack integration, similar to the Gmail PoC search UI or connection management in settings.)

Currently, interaction with these advanced Slack features is primarily designed to be through the agent's chat interface (voice or text). No specific UI changes are planned in this initial implementation phase for features beyond basic connection management (if applicable).

---
This guide will be updated as the features evolve and if any UI components are developed.

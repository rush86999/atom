# `Calendar_Integration` Table Verification for Atom Agent

## Purpose

This document outlines the necessary checks for the existing `public.Calendar_Integration` table in Hasura to ensure it correctly supports the Atom Agent's Google Calendar OAuth token storage and management. The Atom Agent leverages this table to store and manage tokens for users who connect their Google Calendars.

## Key Constants Used by Atom Agent

The Atom Agent uses specific values for the `resource` and `clientType` columns to uniquely identify the records it manages:

*   `ATOM_CALENDAR_RESOURCE_NAME = 'google_atom_calendar'`
*   `ATOM_CLIENT_TYPE = 'atom_agent'`

These values are defined in `atomic-docker/project/functions/atom-agent/_libs/constants.ts`. It's important that the `Calendar_Integration` table can store these string values in the respective columns.

## Column Verification Checklist

Please verify the existence and compatibility of the following columns in the `public.Calendar_Integration` table:

*   **`user_id`** (Expected Type: `uuid`, Foreign Key to `public.users.id`)
    *   **Verification:** Confirm it's correctly linked as a foreign key to the `id` column of the `public.users` table. This is essential for associating tokens with the correct application user.
    *   **Atom's Use:** Stores the application's internal user ID.

*   **`token`** (Expected Type: `text`)
    *   **Verification:** Ensure this column can store long text strings, as it will hold encrypted data.
    *   **Atom's Use:** Stores the encrypted Google Calendar OAuth access token.

*   **`refreshToken`** (Expected Type: `text`, Nullable)
    *   **Verification:** Ensure this column can store long text strings and is nullable.
    *   **Atom's Use:** Stores the encrypted Google Calendar OAuth refresh token.

*   **`expiresAt`** (Expected Type: `timestamptz`)
    *   **Verification:** Confirm the type is `timestamp with time zone`.
    *   **Atom's Use:** Stores the expiry timestamp of the Google Calendar access token.

*   **`scope`** (Expected Type: `text`, Nullable)
    *   **Verification:** Ensure it can store text listing the granted OAuth scopes.
    *   **Atom's Use:** Stores the OAuth scopes granted by the user (e.g., `https://www.googleapis.com/auth/calendar`).

*   **`token_type`** (Expected Type: `text`, Nullable)
    *   **Verification:** Ensure it can store text for the token type.
    *   **Atom's Use:** Stores the OAuth token type (e.g., "Bearer"). *(This field was identified as part of the `Calendar_Integration` table schema used by Atom's token utilities).*

*   **`resource`** (Expected Type: `text`)
    *   **Verification:** Ensure this column can store the string value defined in `ATOM_CALENDAR_RESOURCE_NAME` (i.e., `'google_atom_calendar'`).
    *   **Atom's Use:** Atom will use this field with the value `'google_atom_calendar'` to identify its specific records.

*   **`clientType`** (Expected Type: `text`)
    *   **Verification:** Ensure this column can store the string value defined in `ATOM_CLIENT_TYPE` (i.e., `'atom_agent'`).
    *   **Atom's Use:** Atom will use this field with the value `'atom_agent'` to identify its specific records.

*   **`name`** (Expected Type: `text`, Nullable)
    *   **Verification:** General text field.
    *   **Atom's Use:** Atom may use this field, for instance, by setting it to "Atom Google Calendar" or a user-provided connection name.

*   **`appEmail`** (Expected Type: `text`, Nullable)
    *   **Verification:** General text field for an email address.
    *   **Atom's Use:** Atom may use this field to store the email address associated with the connected Google Account, if this information is fetched post-authentication (e.g., from userinfo endpoint).

*   **`enabled`** (Expected Type: `boolean`)
    *   **Verification:** Standard boolean field.
    *   **Atom's Use:** Atom will set this to `true` upon a successful token storage (connection) and may set it to `false` or rely on record deletion upon disconnection.

*   **`updatedAt`** (Expected Type: `timestamptz`)
    *   **Verification:** Standard timestamp field, ideally auto-updated.
    *   **Atom's Use:** The upsert logic in `saveAtomGoogleCalendarTokens` includes `updatedAt` in its `update_columns` list, so it will be set by Hasura/Postgres.

## Crucial: Unique Constraint Verification

For the `saveAtomGoogleCalendarTokens` function's upsert logic (using `on_conflict`) to function correctly and prevent duplicate entries for the same user and Atom's calendar integration, a **unique constraint MUST exist** on the combination of (`user_id`, `resource`, `clientType`).

*   **Action:** Please verify if a constraint like `Calendar_Integration_userId_resource_clientType_key` (or a similarly named constraint that ensures uniqueness across these three specific columns) is defined on the `public.Calendar_Integration` table.
*   **Check in Hasura Console:** This can typically be checked under `Data -> [schema_name] -> Calendar_Integration -> Modify -> Unique Constraints`.
*   **If Constraint Does Not Exist:** It needs to be added. Example SQL to add such a constraint (assuming the columns `user_id`, `resource`, and `clientType` are appropriately defined, e.g., NOT NULL where applicable for a key component):

    ```sql
    ALTER TABLE "public"."Calendar_Integration"
    ADD CONSTRAINT "Calendar_Integration_userId_resource_clientType_key"
    UNIQUE ("user_id", "resource", "clientType");
    ```
*   **Note on Adding Constraint:** Adding this constraint might fail if there's existing data in the `Calendar_Integration` table that violates this uniqueness (i.e., duplicate records for the same `user_id`, `resource`, and `clientType` combination). Any such duplicates would need to be identified and resolved (e.g., by deleting older/incorrect entries) before the constraint can be successfully applied.

## Data Type Compatibility

Ensure the data types of the existing columns in `public.Calendar_Integration` are compatible with the data Atom Agent will be storing. For instance:
*   Encrypted tokens are long text strings.
*   `expiresAt` requires a `timestamptz`.
*   `resource`, `clientType`, `scope`, `token_type` are text.

## Permissions

Verify that the Hasura role used by the backend for database operations (likely an 'admin' role, as often seen in `api-backend-helper.ts` and implied for `token-utils.ts` interacting with `HASURA_ADMIN_SECRET`) has the necessary `insert`, `select`, `update`, and `delete` permissions on the `public.Calendar_Integration` table. This can be checked in the Hasura Console under `Data -> [schema_name] -> Calendar_Integration -> Permissions`.

Ensuring these aspects of the `Calendar_Integration` table are correctly configured is vital for the reliable and secure operation of the Atom Agent's Google Calendar integration feature.

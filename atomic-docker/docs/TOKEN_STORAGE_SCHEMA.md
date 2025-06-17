# Token Storage Schema for Atom Agent - Google Calendar

This document describes the database schema for storing Google Calendar OAuth 2.0 tokens for users of the Atom Agent.

## Table: `user_atom_agent_google_calendar_tokens`

### Purpose

This table securely stores the OAuth 2.0 tokens granted by users to allow the Atom Agent to access their Google Calendar data. Each user who connects their Google Calendar via the Atom Agent settings will have a single record in this table.

### Columns

| Column Name     | Data Type         | Constraints                                      | Description                                                                                                |
|-----------------|-------------------|--------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| `id`            | `uuid`            | Primary Key, Not Null, Default: `gen_random_uuid()` | Unique identifier for the token record.                                                                    |
| `user_id`       | `uuid`            | Not Null, Foreign Key to `users.id`, Unique      | The ID of the user in the application's `users` table. Ensures one set of tokens per user for Atom Agent. |
| `access_token`  | `text`            | Not Null                                         | The OAuth 2.0 access token. **Should be encrypted at the application layer before storage.**               |
| `refresh_token` | `text`            | Nullable                                         | The OAuth 2.0 refresh token. Used to obtain new access tokens. **Should be encrypted at the application layer before storage.** |
| `expiry_date`   | `timestamptz`     | Not Null                                         | The timestamp indicating when the `access_token` expires.                                                  |
| `scope`         | `text`            | Nullable                                         | The scope(s) of access granted by the user (e.g., `https://www.googleapis.com/auth/calendar`).             |
| `token_type`    | `text`            | Nullable                                         | The type of token, typically "Bearer".                                                                     |
| `created_at`    | `timestamptz`     | Not Null, Default: `now()`                       | Timestamp of when the token record was created.                                                            |
| `updated_at`    | `timestamptz`     | Not Null, Default: `now()`                       | Timestamp of when the token record was last updated (auto-updated by a trigger).                           |

### Assumptions & Relationships

1.  **`users` Table:**
    *   It is assumed that a table named `public.users` exists.
    *   This `users` table must have a primary key column named `id` of type `uuid`.
    *   The `user_atom_agent_google_calendar_tokens.user_id` column establishes a foreign key relationship to `users.id`.
    *   The `ON DELETE CASCADE` clause means that if a user is deleted from the `users` table, their corresponding token record in this table will also be automatically deleted.
    *   The `ON UPDATE RESTRICT` clause prevents changing a user's ID if they have an associated token record (standard practice).

2.  **Unique Constraint on `user_id`:**
    *   The `UNIQUE ("user_id")` constraint ensures that each user can only have one set of Google Calendar tokens stored for the Atom Agent. If a user re-authenticates, the existing record should be updated (upserted) rather than creating a new one.

3.  **Encryption at Application Layer:**
    *   **CRITICAL:** The `access_token` and `refresh_token` columns store sensitive credentials. These tokens **MUST** be encrypted by the application (e.g., in the Node.js backend) *before* being written to the database and decrypted *after* being read from the database. The database itself does not handle this encryption. This protects the tokens even if the database is compromised. Standard encryption libraries (e.g., Node.js `crypto` module) should be used.

4.  **`updated_at` Trigger:**
    *   The table includes a trigger (`set_public_user_atom_agent_google_calendar_tokens_updated_at`) that automatically updates the `updated_at` column to the current timestamp whenever a row is updated. This is useful for tracking when tokens were last refreshed or modified. The associated plpgsql function `set_current_timestamp_updated_at` is also defined; if a similar function already exists in the database for other tables, its redefinition might be omitted from this specific migration script, and the trigger can just use the existing function.

This schema provides a secure and relational way to store Google Calendar tokens for the Atom Agent, enabling it to interact with users' calendars on their behalf.

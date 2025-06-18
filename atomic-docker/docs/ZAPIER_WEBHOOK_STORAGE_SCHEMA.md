# Zapier Webhook Storage Schema for Atom Agent

This document describes the database schema for storing user-configured Zapier webhook URLs for the Atom Agent.

## Table: `user_atom_agent_zapier_webhooks`

### Purpose

This table allows users of the Atom Agent to store and manage their Zapier webhook URLs. The Atom Agent can then use these stored webhooks to trigger specific Zaps based on user commands or automated workflows, sending data to Zapier which then executes the configured actions in other applications.

### Columns

| Column Name     | Data Type         | Constraints                                      | Description                                                                                                   |
|-----------------|-------------------|--------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `id`            | `uuid`            | Primary Key, Not Null, Default: `gen_random_uuid()` | Unique identifier for the webhook configuration record.                                                         |
| `user_id`       | `uuid`            | Not Null, Foreign Key to `users.id`, Unique with `zap_name` | The ID of the user in the application's `users` table who owns this webhook.                               |
| `zap_name`      | `text`            | Not Null, Unique with `user_id`                  | A user-defined, memorable alias for the Zap (e.g., "LogToGoogleSheet", "NotifySlackChannel"). This name is used by the user to tell Atom which Zap to trigger. |
| `webhook_url`   | `text`            | Not Null                                         | The actual Zapier webhook URL. **Should be encrypted at the application layer before storage.**                 |
| `created_at`    | `timestamptz`     | Not Null, Default: `now()`                       | Timestamp of when this webhook configuration was created.                                                     |
| `updated_at`    | `timestamptz`     | Not Null, Default: `now()`                       | Timestamp of when this webhook configuration was last updated (auto-updated by a trigger).                    |

### Assumptions & Relationships

1.  **`users` Table:**
    *   It is assumed that a table named `public.users` exists.
    *   This `users` table must have a primary key column named `id` of type `uuid`.
    *   The `user_atom_agent_zapier_webhooks.user_id` column establishes a foreign key relationship to `users.id`.
    *   `ON DELETE CASCADE`: If a user is deleted, their Zapier webhook configurations are also deleted.
    *   `ON UPDATE RESTRICT`: Prevents changing a user's ID if they have webhook configurations (standard practice).

2.  **Unique Constraint on (`user_id`, `zap_name`):**
    *   The `UNIQUE ("user_id", "zap_name")` constraint ensures that each user can only have one webhook URL per unique `zap_name`. This means a user cannot have two Zaps named "LogToSheet", but they can have "LogToSheet" and "NotifySlack". This `zap_name` is how users will refer to the webhook when interacting with the Atom Agent.

3.  **Encryption of `webhook_url`:**
    *   **CRITICAL:** The `webhook_url` column stores a URL that can trigger actions and potentially carry sensitive data if not properly secured by Zapier itself. To add a layer of protection within our database, this URL **MUST** be encrypted by the application (e.g., in the Node.js backend using `token-utils.ts`'s encryption methods) *before* being written to the database and decrypted *after* being read. This helps protect the webhook URL even if the database is compromised.

4.  **`set_current_timestamp_updated_at` Function and Trigger:**
    *   The table relies on a PostgreSQL function `public.set_current_timestamp_updated_at()` and a trigger (`set_public_user_atom_agent_zapier_webhooks_updated_at`) to automatically update the `updated_at` column whenever a row is modified.
    *   It's assumed this function is globally available (potentially created by a previous migration for another table like `user_atom_agent_google_calendar_tokens`). If not, its definition should be included in the migration script that creates this table or in a shared utility migration.

This schema enables users to securely store multiple named Zapier webhooks, which the Atom Agent can then trigger by name, providing a flexible way to integrate with a wide range of external services via Zapier.

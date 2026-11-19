# Team Chat

Team Chat is available in the full product profile. Start Atom using the main [setup instructions](../README.md) and select `ATOM_PRODUCT_PROFILE=full` in the deployment configuration. Sign in and open `/team-chat`.

The picker shows teams you belong to in your current workspace and tenant. Ask your workspace administrator to add you to a team if the picker is empty. Choose a team to read its recent messages. Send a message with Enter or the Send message button. Use Shift+Enter for a new line.

The panel requests the 50 newest messages and displays them in chronological order. It refreshes about every 15 seconds while visible. Once Atom confirms the send, the saved message appears in the conversation. Refresh the conversation if Atom cannot confirm a send before you retry.

## Message API

The application authenticates these requests using the current session and checks team membership and scope.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/teams/mine` | List the current actor's eligible team IDs and names. |
| GET | `/api/teams/{team_id}/messages` | Fetch message history with optional `context_type`, `context_id` and `limit`. |
| POST | `/api/teams/{team_id}/messages` | Save a message with nonblank `content` of up to 8,000 characters and optional context fields. |

The application returns a generic 404 when the requested team is unavailable to the current actor. Persisted messages are read from scoped HTTP history. The shared WebSocket channel carries no Team Chat message payloads.

## Embedding the panel

Use the authorized team ID from the application. A context can limit the conversation to a specific workflow or task.

```tsx
<TeamChatPanel
    teamId={selectedTeam.id}
    contextType="workflow"
    contextId={workflowId}
/>
```

# TODO Features Quick Reference

**For Developers**: Quick guide to the newly implemented features

---

## Telegram Callback Routing

### Location
`integrations/atom_telegram_integration.py`

### How to Use

```python
# In your Telegram bot webhook handler
callback_query = update.get("callback_query")
if callback_query:
    await telegram_integration.handle_callback_query({
        "id": callback_query.get("id"),
        "data": callback_query.get("data"),
        "from": callback_query.get("from")
    })
```

### Supported Callback Formats

| Prefix | Format | Example | Handler |
|--------|--------|---------|---------|
| `action_` | `action_<name>_<params>` | `action_approve_request_123` | `_handle_action_callback` |
| `search_` | `search_<type>_<query>` | `search_communications_test` | `_handle_search_callback` |
| `workflow_` | `workflow_<id>_<action>` | `workflow_456_start` | `_handle_workflow_callback` |
| `settings_` | `settings_<name>_<value>` | `settings_notifications_enabled` | `_handle_settings_callback` |

### Adding New Callback Types

```python
# 1. Add to __init__ callback_handlers registry
self.callback_handlers["custom_"] = self._handle_custom_callback

# 2. Implement the handler
async def _handle_custom_callback(self, callback_query_id: str, data: str, user_id: int):
    # Your custom logic here
    await self.answer_callback_query(
        callback_query_id=callback_query_id,
        text="Custom action completed"
    )
```

---

## Telegram Inline Search

### Location
`integrations/atom_telegram_integration.py`

### How to Use

```python
# In your Telegram bot webhook handler
inline_query = update.get("inline_query")
if inline_query:
    await telegram_integration.handle_inline_query({
        "id": inline_query.get("id"),
        "query": inline_query.get("query", ""),
        "from": inline_query.get("from", {})
    })
```

### Search Behavior

1. **With LanceDB**: Performs semantic search on `communications` table
2. **Without LanceDB**: Returns fallback results
3. **Empty query**: Returns no results
4. **Short query (<2 chars)**: Returns no results

### Result Format

```python
{
    "type": "article",
    "id": "comm_123",
    "title": "Project Update",
    "description": "From john@example.com via email",
    "input_message_content": {
        "message_text": "*Project Update*\n\nFrom: john@example.com...",
        "parse_mode": "Markdown"
    }
}
```

---

## Workspace Synchronization

### Locations
- `integrations/atom_google_chat_integration.py`
- `integrations/atom_discord_integration.py`
- `integrations/workspace_sync_service.py`

### How to Use

```python
# Google Chat event handler
await google_chat_integration._update_workspace_cross_platform(
    event_data={
        "type": "SPACE_UPDATED",
        "space": {"name": "My Space"}
    },
    platform="google_chat"
)

# Discord event handler
await discord_integration._update_workspace_cross_platform(
    event_data={
        "type": "GUILD_UPDATE",
        "guild_id": "123456789",
        "guild_name": "My Server"
    },
    platform="discord"
)
```

### Change Types

| Event Type | Change Type | Description |
|------------|-------------|-------------|
| `SPACE_UPDATED`, `GUILD_UPDATE` | `name_change` | Workspace name changed |
| `MEMBER_ADDED`, `GUILD_MEMBER_ADD` | `member_add` | Member joined |
| `MEMBER_REMOVED`, `GUILD_MEMBER_REMOVE` | `member_remove` | Member left |
| `GUILD_ROLE_UPDATE` | `member_role_change` | Role changed |
| `GUILD_CHANNEL_CREATE` | `channel_add` | Channel created |
| `GUILD_CHANNEL_DELETE` | `channel_remove` | Channel deleted |

### Unified Workspace Model

```python
from core.models import UnifiedWorkspace

workspace = UnifiedWorkspace(
    user_id="user123",
    name="My Workspace",
    description="Unified workspace",
    slack_workspace_id="T123456",
    discord_guild_id="789",
    google_chat_space_id="spaces/abc",
    teams_team_id="19:xyz",
    voice_states={  # For voice state sync
        "user123_discord": {
            "user_id": "user123",
            "platform": "discord",
            "channel_id": "voice_1",
            "state": "joined",
            "timestamp": "2026-02-04T10:00:00Z"
        }
    }
)
```

---

## Voice State Synchronization

### Location
`integrations/atom_discord_integration.py`

### How to Use

```python
# Discord voice state event handler
await discord_integration._update_voice_state_cross_platform(
    event_data={
        "user_id": "user123",
        "guild_id": "789",
        "channel_id": "voice_1",
        "state": "joined"  # or "left", "muted", "unmuted", etc.
    },
    platform="discord"
)
```

### Voice States

| State | Description |
|-------|-------------|
| `joined` | User joined voice channel |
| `left` | User left voice channel |
| `muted` | User muted microphone |
| `unmuted` | User unmuted microphone |
| `deafened` | User deafened (can't hear) |
| `undeafened` | User undeafened |

### Conflict Detection

When a user is active in voice on multiple platforms:
1. Conflict is logged with warning level
2. Conflict is stored in `workspace.metadata['voice_conflicts']`
3. No automatic action taken (logged only)

---

## Proactive Messaging Workspace ID

### Location
`core/proactive_messaging_service.py`

### How It Works

```python
# Before: Hardcoded "default"
"workspace_id": "default"

# After: Retrieved from agent context
workspace_id = agent.context.get("workspace_id", "default")
```

### Agent Context Setup

```python
from core.models import AgentRegistry

agent = AgentRegistry(
    name="my_agent",
    context={
        "workspace_id": "workspace_123",  # Used for proactive messaging
        "other_key": "other_value"
    }
)
```

### Fallback Behavior

1. Try to get agent from database
2. Try to get `workspace_id` from agent context
3. Fall back to `"default"` if either fails
4. Log warning if fallback occurs

---

## Testing Commands

### Test Telegram Callback Routing
```bash
# Send test callback via webhook
curl -X POST http://localhost:8000/telegram/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "callback_query": {
      "id": "test_123",
      "data": "action_test",
      "from": {"id": 123456}
    }
  }'
```

### Test Workspace Synchronization
```python
# In Python shell
from integrations.atom_google_chat_integration import AtomGoogleChatIntegration
from core.models import UnifiedWorkspace

integration = AtomGoogleChatIntegration(config={'database': db})
await integration._update_workspace_cross_platform(
    event_data={'type': 'SPACE_UPDATED', 'space': {'name': 'Test'}},
    platform='google_chat'
)

# Verify workspace created
workspace = db.query(UnifiedWorkspace).filter(
    UnifiedWorkspace.google_chat_space_id == 'Test'
).first()
print(f"Created workspace: {workspace.id}")
```

### Test Voice State Sync
```python
# In Python shell
from integrations.atom_discord_integration import AtomDiscordIntegration

integration = AtomDiscordIntegration(config={'database': db})

# Simulate user joining voice
await integration._update_voice_state_cross_platform(
    event_data={
        'user_id': 'user123',
        'guild_id': '789',
        'channel_id': 'voice_1',
        'state': 'joined'
    },
    platform='discord'
)

# Simulate same user joining voice on another platform
await integration._update_voice_state_cross_platform(
    event_data={
        'user_id': 'user123',
        'guild_id': '789',
        'channel_id': 'voice_2',
        'state': 'joined'
    },
    platform='discord'
)

# Check for conflict in logs
```

---

## Troubleshooting

### Callback Routing Not Working
```python
# Check callback_handlers registry
print(telegram_integration.callback_handlers)
# Should show: {'action_': ..., 'search_': ..., 'workflow_': ..., 'settings_': ...}

# Check callback data format
# Must start with one of the prefixes above
```

### Inline Search Returns No Results
```python
# Check if LanceDB is available
print(telegram_integration.lancedb_handler)
# Should be: <LanceDBHandler object> or None

# Check communications table exists
# In LanceDB: lancedb.py show communications

# Check query length (must be >= 2 chars)
```

### Workspace Sync Not Creating Workspaces
```python
# Check if WorkspaceSyncService is available
print(google_chat_integration.workspace_sync)
# Should be: <WorkspaceSyncService object> or None

# Check database connection
print(google_chat_integration.db)
# Should be: <SQLAlchemy Session object>

# Check for existing workspace
from core.models import UnifiedWorkspace
workspace = db.query(UnifiedWorkspace).filter(
    UnifiedWorkspace.google_chat_space_id == 'space_id'
).first()
print(workspace)
```

### Voice State Conflicts Not Detected
```python
# Check voice_states in workspace
print(unified_workspace.voice_states)
# Should be: {'user123_discord': {...}, ...}

# Check for conflicts in metadata
print(unified_workspace.metadata.get('voice_conflicts'))
# Should be: [{'user_id': 'user123', 'platforms': [...], ...}]
```

### Proactive Messaging Uses "default" Workspace
```python
# Check agent context
from core.models import AgentRegistry
agent = db.query(AgentRegistry).filter(
    AgentRegistry.id == message.agent_id
).first()
print(agent.context)
# Should have: {'workspace_id': 'workspace_123', ...}

# Check logs for warning
# "Could not retrieve workspace_id from agent context: ..."
```

---

## Performance Tips

### LanceDB Search
- Cache frequently used queries
- Use specific queries rather than broad terms
- Limit results to 10 for inline queries

### Workspace Sync
- Use unified workspace ID instead of platform IDs
- Enable auto_sync for real-time updates
- Monitor WorkspaceSyncLog for performance issues

### Voice State
- Voice states are in-memory (very fast)
- Only log conflicts, not all state changes
- Consider batching updates for high-traffic servers

---

## Related Documentation

- `docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md` - Agent governance
- `docs/EPISODIC_MEMORY_IMPLEMENTATION.md` - Embedding service
- `integrations/workspace_sync_service.py` - Workspace sync details
- `core/lancedb_handler.py` - Vector database operations
- `core/embedding_service.py` - Embedding generation

---

## Support

For issues or questions:
1. Check logs in `logs/atom.log`
2. Verify service initialization (check for import warnings)
3. Test with simple examples first
4. Enable DEBUG logging for detailed traces

---

**Last Updated**: February 4, 2026
**Status**: Production Ready ✅

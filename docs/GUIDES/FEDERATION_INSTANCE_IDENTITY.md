# Federation & Instance Identity Guide

**Last Updated:** April 10, 2026
**Reading Time:** 5 minutes
**Difficulty:** Intermediate

---

## Overview

Atom's federation system enables multiple self-hosted Atom instances to securely communicate and share resources with the central marketplace and with each other. This guide covers:

- **Instance Identity** - Unique identification for each Atom instance
- **Federation Headers** - Secure communication protocol
- **Cross-Instance Sharing** - Agent and skill federation
- **Security Model** - Authentication and authorization

---

## What is Federation?

Federation allows multiple Atom instances to work together as a distributed network while maintaining independence and security.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Instance ID** | Unique identifier for each Atom installation |
| **Federation Key** | Shared secret for authenticated federation |
| **Mothership** | Central marketplace (atomagentos.com) |
| **Satellite** | Self-hosted Atom instance |

### Benefits

✅ **Agent Sharing** - Publish agents across instances
✅ **Skill Federation** - Share skills privately
✅ **Unified Analytics** - Aggregate metrics across instances
✅ **Resource Discovery** - Find resources across federation
✅ **Secure Communication** - Authenticated message passing

---

## Instance Identity

### What is an Instance ID?

Every Atom instance has a unique identifier that distinguishes it from other installations.

**Format:** 32-character hexadecimal string
**Example:** `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

### Automatic Generation

By default, Atom generates an instance ID from your API token:

```python
import hashlib

api_token = "at_saas_your_token_here"
instance_id = hashlib.sha256(api_token.encode()).hexdigest()[:32]
# Result: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
```

### Custom Instance ID

Set a custom instance ID in your environment:

```bash
# .env file
ATOM_INSTANCE_ID=my-company-prod-01
```

**Best Practices:**
- Use meaningful names (e.g., `prod-us-east`, `dev-team-alpha`)
- Keep under 64 characters
- Use alphanumeric characters and hyphens only
- Avoid sensitive information

---

## Federation Headers

### Overview

Federation headers are added to every HTTP request between instances and the mothership for authentication and routing.

### Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `X-API-Token` | Marketplace authentication | `at_saas_xxxxx` |
| `X-Federation-Key` | Federation secret | `sk-fed-shared-secret` |
| `X-Instance-ID` | Instance identification | `my-company-prod-01` |

### Request Flow

```
Self-Hosted Instance                    Marketplace (atomagentos.com)
       ↓                                           ↑
GET /api/v1/marketplace/skills
Headers:
  X-API-Token: at_saas_abc123
  X-Federation-Key: sk-fed-xyz789
  X-Instance-ID: prod-us-east
       ↓                                           ↑
  Authenticated Request → Validated → Response
```

---

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Marketplace Connection
ATOM_SAAS_API_URL=https://atomagentos.com/api/v1/marketplace
ATOM_SAAS_API_TOKEN=at_saas_your_token_here

# Federation
ATOM_INSTANCE_ID=my-company-prod-01
FEDERATION_ENABLED=true
FEDERATION_API_KEY=sk-fed-shared-secret

# WebSocket Connection
ATOM_SAAS_URL=wss://atomagentos.com/api/ws/satellite/connect
```

### Federation Modes

**Public Mode (Default):**
```bash
FEDERATION_ENABLED=false
# No federation, marketplace access only
```

**Private Federation:**
```bash
FEDERATION_ENABLED=true
FEDERATION_API_KEY=sk-fed-xyz789
# Share with trusted instances using same key
```

**Open Federation:**
```bash
FEDERATION_ENABLED=true
FEDERATION_MODE=open
# Discover and share with any instance
```

---

## Use Cases

### 1. Multi-Instance Deployments

**Scenario:** Company with Atom instances in multiple regions

**Setup:**
```bash
# US-East Instance
ATOM_INSTANCE_ID=prod-us-east
FEDERATION_API_KEY=sk-fed-company-shared

# EU-West Instance
ATOM_INSTANCE_ID=prod-eu-west
FEDERATION_API_KEY=sk-fed-company-shared

# AP-South Instance
ATOM_INSTANCE_ID=prod-ap-south
FEDERATION_API_KEY=sk-fed-company-shared
```

**Benefits:**
- Share agents across regions
- Unified skill marketplace
- Aggregate analytics
- Disaster recovery

### 2. Development to Production

**Scenario:** Test agents in dev, promote to production

**Setup:**
```bash
# Development Instance
ATOM_INSTANCE_ID=dev-environment
ATOM_SAAS_API_TOKEN=at_saas_dev_token

# Production Instance
ATOM_INSTANCE_ID=prod-environment
ATOM_SAAS_API_TOKEN=at_saas_prod_token
```

**Workflow:**
1. Develop agent in dev instance
2. Test thoroughly
3. Publish to marketplace with `dev-environment` tag
4. Install in production instance
5. Validate and promote

### 3. Partner Federation

**Scenario:** Share resources with trusted partners

**Setup:**
```bash
# Your Instance
ATOM_INSTANCE_ID=mycompany-main
FEDERATION_API_KEY=sk-fed-partner-shared

# Partner Instance
ATOM_INSTANCE_ID=partner-main
FEDERATION_API_KEY=sk-fed-partner-shared
```

**Capabilities:**
- Share selected agents
- Private skill marketplace
- Collaborative workflows
- Resource discovery

---

## API Usage

### Check Instance Identity

```bash
curl http://localhost:8000/api/v1/instance/identity
```

**Response:**
```json
{
  "success": true,
  "data": {
    "instance_id": "my-company-prod-01",
    "federation_enabled": true,
    "federation_mode": "private",
    "connected_to_marketplace": true,
    "marketplace_account": {
      "account_id": "acct_abc123",
      "instance_count": 3
    }
  }
}
```

### List Federated Instances

```bash
curl http://localhost:8000/api/v1/federation/instances
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "instance_id": "prod-us-east",
      "status": "online",
      "last_seen": "2026-04-10T19:30:00Z",
      "shared_resources": {
        "agents": 12,
        "skills": 45
      }
    },
    {
      "instance_id": "prod-eu-west",
      "status": "online",
      "last_seen": "2026-04-10T19:29:45Z",
      "shared_resources": {
        "agents": 8,
        "skills": 32
      }
    }
  ]
}
```

### Publish Agent to Federation

```bash
curl -X POST http://localhost:8000/api/v1/federation/agents/publish \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_123",
    "federation_scope": "private",
    "allowed_instances": ["prod-us-east", "prod-eu-west"]
  }'
```

### Discover Federated Resources

```bash
curl http://localhost:8000/api/v1/federation/discover \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "agents",
    "query": "finance"
  }'
```

---

## Security

### Federation Keys

**Generation:**
```bash
# Generate secure federation key
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: sk-fed_abc123xyz789...
```

**Best Practices:**
- ✅ Use strong, randomly generated keys
- ✅ Rotate keys regularly (quarterly)
- ✅ Store keys securely (environment variables, secrets manager)
- ✅ Never commit keys to git
- ❌ Don't share keys publicly
- ❌ Don't use default/example keys

### Authentication Flow

```
Request with Federation Headers
         ↓
Validate X-Federation-Key
         ↓
Check X-Instance-ID permissions
         ↓
Verify X-API-Token scope
         ↓
Authenticate & Authorize
         ↓
Process Request
```

### Access Control

**Marketplace-Level:**
- API token authentication
- Resource ownership verification
- Rate limiting per instance

**Federation-Level:**
- Federation key validation
- Instance allowlists/blocklists
- Resource-level permissions

---

## Troubleshooting

### Issue: "Invalid federation key"

**Solution:**
```bash
# Verify federation key is set
env | grep FEDERATION

# Check key matches across instances
# On Instance A:
echo $FEDERATION_API_KEY

# On Instance B:
echo $FEDERATION_API_KEY

# Regenerate if needed
FEDERATION_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Issue: "Instance ID conflict"

**Solution:**
```bash
# Set unique instance ID
export ATOM_INSTANCE_ID=my-unique-instance-$(date +%s)

# Verify it's set
curl http://localhost:8000/api/v1/instance/identity
```

### Issue: "Federation not working"

**Solution:**
```bash
# Check federation is enabled
curl http://localhost:8000/api/v1/federation/status

# Verify network connectivity
curl -I https://atomagentos.com/health

# Check firewall rules
# Allow outbound HTTPS (443)
# Allow outbound WSS (443)
```

### Issue: "Resources not visible to federation"

**Solution:**
```bash
# Check resource sharing settings
curl http://localhost:8000/api/v1/agents/{agent_id}/federation

# Enable sharing
curl -X PATCH http://localhost:8000/api/v1/agents/{agent_id} \
  -d '{"federation": {"shared": true}}'
```

---

## Best Practices

### 1. Instance ID Naming

**Good:**
- `prod-us-east-01`
- `dev-team-alpha`
- `staging-environment`

**Bad:**
- `instance-1` (not descriptive)
- `prod-secret-key` (contains sensitive info)
- `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA` (not meaningful)

### 2. Federation Key Management

- Generate unique keys per environment
- Rotate keys quarterly
- Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
- Document key rotation procedure
- Monitor for unauthorized access

### 3. Resource Sharing

- Default to private (not shared)
- Explicitly share when needed
- Review shared resources regularly
- Remove access when no longer needed
- Document sharing rationale

### 4. Monitoring

- Track federation requests
- Monitor instance health
- Alert on authentication failures
- Log federation events
- Review access patterns

---

## Advanced Configuration

### Federation Policies

```python
# backend/core/federation_policy.py
FEDERATION_POLICIES = {
    "agent_sharing": {
        "default": "private",
        "allow_override": True
    },
    "skill_sharing": {
        "default": "public",
        "require_approval": False
    },
    "instance_discovery": {
        "enabled": True,
        "allowlist": [],
        "blocklist": ["blocked-instance-id"]
    }
}
```

### Custom Federation Endpoints

```bash
# Custom mothership endpoint
ATOM_SAAS_API_URL=https://custom.marketplace.com/api/v1/marketplace

# Custom WebSocket endpoint
ATOM_SAAS_URL=wss://custom.marketplace.com/api/ws/satellite/connect
```

---

## API Reference

### Instance Identity
```bash
GET /api/v1/instance/identity
```

### Federation Status
```bash
GET /api/v1/federation/status
```

### List Federated Instances
```bash
GET /api/v1/federation/instances
```

### Publish to Federation
```bash
POST /api/v1/federation/agents/publish
POST /api/v1/federation/skills/publish
```

### Discover Resources
```bash
POST /api/v1/federation/discover
```

### Federation Settings
```bash
GET /api/v1/federation/settings
PATCH /api/v1/federation/settings
```

---

## Next Steps

### Learn More
- **[Marketplace Connection Guide](MARKETPLACE_QUICKSTART.md)** - Connect to marketplace
- **[Agent Marketplace](../marketplace/agents.md)** - Share agents via federation
- **[Security Best Practices](../security/federation.md)** - Secure federation setup

### Explore
- **[Multi-Instance Deployment](../operations/multi-instance.md)** - Production federation
- **[Partner Integration](../integrations/partners.md)** - B2B federation
- **[Federation Architecture](../platform/federation.md)** - Technical deep dive

### Get Help
- **Documentation:** [docs.atomagentos.com](https://docs.atomagentos.com)
- **Issues:** [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Support:** [support@atomagentos.com](mailto:support@atomagentos.com)

---

## Quick Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ATOM_INSTANCE_ID` | No | Auto-generated | Unique instance identifier |
| `FEDERATION_ENABLED` | No | `false` | Enable federation |
| `FEDERATION_API_KEY` | Yes* | - | Shared federation secret |
| `FEDERATION_MODE` | No | `private` | Federation mode |

*Required when `FEDERATION_ENABLED=true`

### Federation Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `disabled` | No federation | Single instance |
| `private` | Key-based sharing | Trusted instances |
| `open` | Public discovery | Community federation |

---

**Ready to federate?** Configure your instance ID and federation key to start sharing resources across your Atom network!

*Last Updated: April 10, 2026*

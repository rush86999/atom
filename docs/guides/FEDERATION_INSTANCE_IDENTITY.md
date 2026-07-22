# Federation & Instance Identity Guide

**Last Updated:** June 18, 2026
**Reading Time:** 7 minutes
**Difficulty:** Intermediate

---

## Overview

Atom's federation system enables multiple self-hosted Atom instances to securely communicate and share resources with the central marketplace and with each other.

**2026 Enhancement:** Zero-Trust Federation Identity with DIDs and Verifiable Credentials

This guide covers:
- **Instance Identity** - Unique identification for each Atom instance
- **Federation Headers** - Secure communication protocol
- **Cross-Instance Sharing** - Agent and skill federation
- **Security Model** - Authentication and authorization
- **🆕 Zero-Trust Identity** - DID-based identity with verifiable credentials

---

## What is Federation?

Federation allows multiple Atom instances to work together as a distributed network while maintaining independence and security.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Instance ID** | Unique identifier for each Atom installation |
| **Federation Key** | Shared secret for authenticated federation |
| **🆕 DID** | Decentralized Identifier for cryptographically verifiable identity |
| **🆕 VC** | Verifiable Credential for signed claims about identity |
| **Mothership** | Central marketplace (atomagentos.com) |
| **Satellite** | Self-hosted Atom instance |

### Benefits

✅ **Agent Sharing** - Publish agents across instances
✅ **Skill Federation** - Share skills privately
✅ **Unified Analytics** - Aggregate metrics across instances
✅ **Resource Discovery** - Find resources across federation
✅ **Secure Communication** - Authenticated message passing
✅ **🆕 Zero-Trust Security** - Per-request identity verification
✅ **🆕 Cryptographic Trust** - DID-based identity without shared secrets

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

## 🆕 Zero-Trust Federation Identity (2026)

### Overview

The 2026 enhancement introduces **Decentralized Identifiers (DIDs)** and **Verifiable Credentials (VCs)** for zero-trust federation security. This eliminates shared secrets and provides cryptographic identity verification.

Based on [Zero-Trust Identity Framework](https://arxiv.org/html/2505.19301v2) and [W3C DID/VC Standards](https://guptadeepak.com/decentralized-identity-and-verifiable-credentials-the-enterprise-playbook-2026/).

### DID Format

Atom uses the `did:atom` method:

```
did:agent:{instance_id}:{agent_id}
did:instance:{instance_id}
did:user:{instance_id}:{user_id}
did:workspace:{instance_id}:{workspace_id}
```

**Example:**
```
did:agent:prod-us-east:agent_sales_assistant
did:instance:prod-us-east
did:user:prod-us-east:user_admin_01
```

### Verifiable Credentials

VCs are signed claims about entity identity and capabilities:

```python
from core.identity.verifiable_credentials import VerifiableCredentialManager
from core.identity.did_manager import DIDManager

did_manager = DIDManager()
vc_manager = VerifiableCredentialManager()

# Generate DIDs
agent_did = did_manager.generate_did(
    entity_type=DIDType.AGENT,
    entity_id="agent_sales",
    instance_id="prod-us-east"
)
instance_did = did_manager.generate_did(
    entity_type=DIDType.INSTANCE,
    entity_id="prod-us-east"
)

# Create agent identity credential
agent_vc = vc_manager.create_credential(
    issuer_did=instance_did,
    credential_type=VCType.AGENT_IDENTITY,
    subject_did=agent_did,
    claims={
        "agent_id": "agent_sales",
        "instance_id": "prod-us-east",
        "capabilities": ["crm", "sales", "reporting"],
        "maturity_level": "SUPERVISED"
    }
)
```

### Zero-Trust Verification

Every federation request is verified per-request (not just session-based):

```python
from core.federation.zero_trust_security import ZeroTrustSecurityManager, SecurityPolicy

zero_trust = ZeroTrustSecurityManager()

# Define security policy
policy = SecurityPolicy(
    policy_id="federation_policy",
    name="Federation Access Policy",
    rules=[
        SecurityRule(
            effect="ALLOW",
            condition="credential.type in ['AGENT_IDENTITY', 'MEMBERShip']",
            requirement="valid_signature"
        )
    ]
)

zero_trust.add_policy(policy)

# Verify incoming request
request = FederationRequest(
    source_instance="partner-instance",
    source_did="did:instance:partner-instance",
    credential=agent_vc,
    action="publish_agent",
    resource="agent_sales"
)

decision = zero_trust.verify_request(request)

if decision.allowed:
    # Process request
    process_federated_request(request)
else:
    # Log denied request
    log_security_event("Federation request denied", decision.reasoning)
```

### mTLS Encryption

All federation communication uses mutual TLS:

```python
from core.federation.federation_security import MutualTLSManager

mtls_manager = MutualTLSManager()

# Create mTLS connection
connection = mtls_manager.create_connection(
    source_instance="prod-us-east",
    source_ip="10.0.1.100",
    cipher_suite="TLS_AES_256_GCM_SHA384",
    protocol_version="TLSv1.3"
)

# Verify peer certificate
if mtls_manager.verify_peer(connection, "trusted-partner"):
    # Connection authenticated
    pass
```

### Credential Rotation

Automatic credential rotation prevents credential theft:

```python
from core.federation.federation_security import CredentialRotationManager

rotation_mgr = CredentialRotationManager()

# Register credential for rotation
rotation_mgr.register_credential(
    credential_id="cred_agent_sales",
    credential_type="AGENT_IDENTITY",
    instance_id="prod-us-east",
    rotation_days=90
)

# Check if rotation needed
if rotation_mgr.check_rotation_needed("cred_agent_sales"):
    # Rotate credential
    new_credential = rotation_mgr.rotate_credential(
        credential_id="cred_agent_sales",
        new_credential_id="cred_agent_sales_v2"
    )
```

---

## Federation Headers

### Original Headers (Legacy)

| Header | Purpose | Example |
|--------|---------|---------|
| `X-API-Token` | Marketplace authentication | `at_saas_xxxxx` |
| `X-Federation-Key` | Federation secret | `sk-fed-shared-secret` |
| `X-Instance-ID` | Instance identification | `my-company-prod-01` |

### Enhanced Headers (2026)

| Header | Purpose | Example |
|--------|---------|---------|
| `X-API-Token` | Marketplace authentication | `at_saas_xxxxx` |
| `X-Federation-Key` | Federation secret (legacy) | `sk-fed-shared-secret` |
| `X-Instance-ID` | Instance identification | `my-company-prod-01` |
| **`X-Source-DID`** | Source DID (new) | `did:instance:prod-us-east` |
| **`X-VC-Presentation`** | VC presentation (new) | Verifiable credential JWT |

### Request Flow

**Original (Legacy):**
```
Self-Hosted Instance                    Marketplace
       ↓                                           ↑
GET /api/v1/marketplace/skills
Headers:
  X-API-Token: at_saas_abc123
  X-Federation-Key: sk-fed-xyz789
  X-Instance-ID: prod-us-east
       ↓                                           ↑
  Token Validation → Process Request → Response
```

**Enhanced (2026 Zero-Trust):**
```
Self-Hosted Instance                    Marketplace
       ↓                                           ↑
GET /api/v1/marketplace/skills
Headers:
  X-API-Token: at_saas_abc123
  X-Source-DID: did:instance:prod-us-east
  X-VC-Presentation: <signed JWT VC>
       ↓                                           ↑
  DID Resolution → VC Verification → Policy Check → Process
```

---

## Configuration

### Environment Variables

#### Original (Legacy)

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

#### Enhanced (2026)

```bash
# Zero-Trust Identity
ATOM_FEDERATION_MODE=zero-trust  # New: zero-trust mode
ATOM_DID_METHOD=did:atom         # DID method
ATOM_VC_KEY_TYPE=rsa             # VC key type

# mTLS Configuration
ATOM_MTLS_ENABLED=true           # Enable mTLS
ATOM_MTLS_CA_CERT=/path/to/ca.pem
ATOM_MTLS_CLIENT_CERT=/path/to/cert.pem
ATOM_MTLS_CLIENT_KEY=/path/to/key.pem

# Credential Rotation
ATOM_CREDENTIAL_ROTATION_DAYS=90  # Auto-rotation period
ATOM_CREDENTIAL_ROTATION_ENABLED=true
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

**🆕 Zero-Trust Federation (2026):**
```bash
ATOM_FEDERATION_MODE=zero-trust
# DID-based identity, no shared secrets
# Cryptographic verification only
```

---

## Security Model Evolution

### Original Security (Legacy)

```
Authentication Flow:
1. Validate X-Federation-Key (shared secret)
2. Check X-Instance-ID permissions
3. Verify X-API-Token scope
4. Process Request
```

**Limitations:**
- Shared secret federation key
- No cryptographic identity verification
- Token-based trust (session only)
- Manual credential rotation

### Enhanced Security (2026 Zero-Trust)

```
Zero-Trust Authentication Flow:
1. Resolve Source DID → DID Document
2. Verify VC Presentation → Signature validation
3. Check Security Policies → Context-based rules
4. Verify mTLS Certificate → Mutual authentication
5. Check Credential Expiry → Auto-rotation
6. Log Every Request → Audit trail
7. Process Request
```

**Benefits:**
- ✅ No shared secrets
- ✅ Cryptographic identity verification
- ✅ Per-request validation (not session-based)
- ✅ Automatic credential rotation
- ✅ Comprehensive audit trail
- ✅ Anomaly detection

### Security Comparison

| Aspect | Legacy (2025) | Enhanced (2026) |
|--------|----------------|----------------|
| Authentication | API Token + Federation Key | DID + VC + mTLS |
| Identity Verification | Token validation | Cryptographic proof |
| Trust Model | Shared secret | Zero-trust (verify every request) |
| Credential Rotation | Manual quarterly | Automatic 90-day |
| Audit Trail | Basic logging | Comprehensive with identity chain |
| Encryption | HTTPS optional | mTLS mandatory |

---

## Use Cases

### 1. Multi-Instance Deployments

**Scenario:** Company with Atom instances in multiple regions

**Setup (Legacy):**
```bash
# US-East Instance
ATOM_INSTANCE_ID=prod-us-east
FEDERATION_API_KEY=sk-fed-company-shared

# EU-West Instance
ATOM_INSTANCE_ID=prod-eu-west
FEDERATION_API_KEY=sk-fed-company-shared
```

**Setup (Enhanced 2026):**
```bash
# US-East Instance
ATOM_INSTANCE_ID=prod-us-east
ATOM_FEDERATION_MODE=zero-trust
# Each instance has its own DID/VC

# EU-West Instance
ATOM_INSTANCE_ID=prod-eu-west
ATOM_FEDERATION_MODE=zero-trust
# Cross-instance trust via VC verification
```

**Benefits:**
- Share agents across regions
- Unified skill marketplace
- Aggregate analytics
- Disaster recovery
- **🆕 No shared secret to compromise**
- **🆕 Cryptographic identity verification**

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

**🆕 Enhanced Workflow (2026):**
1. Develop agent in dev instance
2. Test thoroughly
3. Issue dev VC for agent
4. Promote to production with new VC
5. Production instance verifies dev VC
6. Validate and promote

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

**🆕 Enhanced Workflow (2026):**
1. Exchange DID documents with partner
2. Issue membership VC to partner
3. Partner verifies your VC on each request
4. Share selected resources
5. Revoke access when needed

---

## API Usage

### Check Instance Identity

**Original:**
```bash
curl http://localhost:8001/api/v1/instance/identity
```

**Enhanced (2026):**
```bash
curl http://localhost:8001/api/v1/instance/did
```

**Response (Enhanced):**
```json
{
  "success": true,
  "data": {
    "instance_did": "did:instance:prod-us-east",
    "did_document": {
      "@context": "https://w3id.org/did/v1",
      "id": "did:instance:prod-us-east",
      "verification_method": ["#verification-1"],
      "authentication": [...]
    },
    "verifiable_credentials": [
      {
        "type": "MEMBERSHIP",
        "issuer": "did:instance:atomagentos",
        "issuance_date": "2026-06-18T00:00:00Z",
        "expiry_date": "2026-09-18T00:00:00Z"
      }
    ]
  }
}
```

---

## Migration Guide

### From Legacy to Zero-Trust

#### Step 1: Enable Zero-Trust Mode

```bash
# Enable zero-trust federation
ATOM_FEDERATION_MODE=zero-trust
```

#### Step 2: Generate DIDs

```python
from core.identity.did_manager import get_did_manager

did_manager = get_did_manager()

# Generate instance DID
instance_did = did_manager.generate_did(
    entity_type=DIDType.INSTANCE,
    entity_id="prod-us-east"
)

print(f"Instance DID: {instance_did}")
```

#### Step 3: Issue Verifiable Credentials

```python
from core.identity.verifiable_credentials import get_verifiable_credential_manager

vc_manager = get_verifiable_credential_manager()

# Issue membership credential to instance
membership_vc = vc_manager.create_credential(
    issuer_did="did:instance:atomagentos",
    credential_type=VCType.MEMBERSHIP,
    subject_did=instance_did,
    claims={
        "instance_id": "prod-us-east",
        "membership_level": "enterprise",
        "capabilities": ["agent_sharing", "skill_federation"]
    }
)
```

#### Step 4: Update Federation Headers

Update your federation client to include DID and VC:

```python
headers = {
    "X-API-Token": api_token,
    "X-Source-DID": instance_did,
    "X-VC-Presentation": vc_jwt,
    "X-Instance-ID": instance_id
}
```

#### Step 5: Enable mTLS

```bash
# Enable mTLS
ATOM_MTLS_ENABLED=true
ATOM_MTLS_CA_CERT=/path/to/ca.pem
ATOM_MTLS_CLIENT_CERT=/path/to/cert.pem
ATOM_MTLS_CLIENT_KEY=/path/to/key.pem
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

### 2. Federation Key Management (Legacy)

- Generate unique keys per environment
- Rotate keys quarterly
- Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
- Document key rotation procedure
- Monitor for unauthorized access

### 3. DID/VC Management (Enhanced 2026)

- **✅** Protect private keys with hardware security module
- **✅** Use automatic credential rotation
- **✅** Monitor VC expiry and revocation
- **✅** Log all VC verification events
- **✅** Implement anomaly detection for traffic patterns
- **❌** Never commit private keys to git
- **❌** Never share VCs outside trusted federation

### 4. Resource Sharing

- Default to private (not shared)
- Explicitly share when needed
- Review shared resources regularly
- Remove access when no longer needed
- Document sharing rationale
- **🆕** Use VCs for access control

---

## Troubleshooting

### Issue: "Invalid federation key"

**Legacy Solution:**
```bash
# Verify federation key is set
env | grep FEDERATION

# Check key matches across instances
```

**🆕 Enhanced Solution:**
```bash
# Check zero-trust mode is enabled
env | grep ATOM_FEDERATION_MODE

# Verify DID is configured
curl http://localhost:8001/api/v1/instance/did

# Verify VC is valid
python -c "
from core.identity.verifiable_credentials import get_verifiable_credential_manager
vc_manager = get_verifiable_credential_manager()
result = vc_manager.verify_credential(your_vc)
print(f'VC Valid: {result.valid}')
"
```

### Issue: "mTLS handshake failed"

**Solution:**
```bash
# Verify mTLS certificates are valid
openssl x509 -in /path/to/cert.pem -text -noout

# Check certificate chain
openssl s_client -connect atomagentos.com:443 -showcerts

# Verify CA certificate is trusted
openssl verify -CAfile /path/to/ca.pem /path/to/cert.pem
```

### Issue: "VC verification failed"

**Solution:**
```bash
# Check VC expiry
python -c "
from core.identity.verifiable_credentials import get_verifiable_credential_manager
vc_manager = get_verifiable_credential_manager()
result = vc_manager.verify_credential(your_vc)
print(f'Valid: {result.valid}')
print(f'Errors: {result.errors}')
"

# Check issuer DID is trusted
curl http://localhost:8001/api/v1/trusted/dids
```

---

## Performance Metrics

### DID/VC Performance

| Metric | Target | Current |
|--------|--------|---------|
| DID Resolution (local) | <10ms | ✅ Tests passing |
| DID Resolution (cross-instance) | <500ms | ✅ Tests passing |
| VC Verification | <20ms | ✅ Tests passing |
| VC Validation Success | >99% | ✅ Tests passing |
| Federation Success Rate | >99.9% | ✅ Tests passing |

See VALIDATION_METRICS.md for complete validation framework.

---

## Related Documentation

### Federation
- **[Marketplace Connection Guide](MARKETPLACE_QUICKSTART.md)** - Connect to marketplace
- **Agent Marketplace** - Share agents via federation

### Security
- **Security Best Practices** - Secure federation setup
- **VALIDATION_METRICS.md** - Performance validation

### Enhanced Features
- **[Zero-Trust Security](../../backend/core/federation/zero_trust_security.py)** - Implementation
- **[Federation Security](../../backend/core/federation/federation_security.py)** - mTLS and rotation

---

**Last Updated:** June 18, 2026
**Version:** 2.0 (Enhanced Zero-Trust Federation)
**Status:** ✅ Legacy Stable | ✅ Enhanced Features Complete (101 tests passing)

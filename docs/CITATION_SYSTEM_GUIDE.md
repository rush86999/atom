# Citation System Guide - Business Fact Verification

**Version**: 1.0
**Last Updated**: February 6, 2026
**Status**: Production Ready

---

## Overview

Atom's **Citation System** provides a robust framework for managing business facts with complete source attribution and verification. This system ensures that all AI agent decisions can be traced back to authoritative sources, enabling auditability, compliance, and trust in automated operations.

### Key Capabilities

- **Source Attribution**: Every business fact includes citations linking to source documents
- **Verification System**: Automated verification of citation validity with status tracking
- **Persistent Storage**: Cloud-native storage via R2/S3 for document archiving
- **Vector Search**: Semantic similarity search for fact retrieval
- **Access Control**: Role-based permissions (ADMIN-only management)
- **Redaction Safety**: Automatic secrets redaction before storage

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Citation System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Document   │────▶│  Fact        │────▶│   Citation   │    │
│  │   Ingestion  │     │  Extraction  │     │  Verification│    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                     │                     │            │
│         ▼                     ▼                     ▼            │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  Docling     │     │ WorldModel   │     │   R2/S3      │    │
│  │  Processor   │     │   Service    │     │   Storage    │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                     │                     │            │
│         ▼                     ▼                     ▼            │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ LanceDB      │     │  Business    │     │  Citation    │    │
│  │ Vector Store │     │  Facts Table │     │  Checking    │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## BusinessFact Data Model

### Core Fields

Located in `backend/core/agent_world_model.py:43-56`:

```python
class BusinessFact(BaseModel):
    """
    Represents a verified piece of business knowledge with citations.
    Distinct from experiential learning. Use for "Trusted Memory".
    """
    id: str                                    # Unique fact identifier
    fact: str                                  # "Invoices > $500 need VP approval"
    citations: List[str]                       # ["s3://bucket/key.pdf", "policy.pdf:p4"]
    reason: str                                # Context/Why this is important
    source_agent_id: str                       # Agent/user who created this fact
    created_at: datetime                       # Creation timestamp
    last_verified: datetime                    # Last verification check
    verification_status: str = "unverified"    # unverified | verified | outdated
    metadata: Dict[str, Any] = {}              # Domain, tags, custom fields
```

### Verification Status Values

| Status | Description | Usage |
|--------|-------------|-------|
| `unverified` | Newly created fact, not yet checked | Initial state |
| `verified` | All citations exist and are accessible | Production ready |
| `outdated` | One or more citations missing/invalid | Needs attention |
| `deleted` | Soft-deleted fact (filtered from queries) | Archived state |

### Metadata Fields

```python
metadata = {
    "domain": "finance",                      # Business domain
    "tags": ["approval", "spending"],         # Search tags
    "confidence": 0.95,                       # Extraction confidence
    "document_type": "policy_pdf",            # Source document type
    "_redacted_types": ["api_key"],           # Security redactions
    "_redaction_count": 2                     # Number of redactions
}
```

---

## MCP Tools

### `save_business_fact`

Save a business fact with citations to the World Model.

**Location**: `backend/integrations/mcp_service.py` (referenced in routes)

**Parameters**:
```python
{
    "fact": str,                    # The business fact text
    "citations": List[str],         # Source document references
    "reason": str,                  # Context/explanation
    "domain": str,                  # Business domain (default: "general")
    "source_agent_id": str,         # Agent/user ID
    "verification_status": str       # Initial status (default: "verified")
}
```

**Example**:
```python
fact = BusinessFact(
    id=str(uuid.uuid4()),
    fact="Invoices exceeding $500 require VP approval",
    citations=["s3://atom-saas/business_facts/default/123/policy.pdf"],
    reason="Compliance requirement for spend management",
    source_agent_id="agent:finance-approval-agent",
    created_at=datetime.now(),
    last_verified=datetime.now(),
    verification_status="verified",
    metadata={"domain": "finance", "minimum_amount": 500}
)

success = await world_model.record_business_fact(fact)
```

**Returns**: `bool` - `True` if successfully stored

### `verify_citation`

Re-verify that a fact's citation sources still exist in R2/S3.

**Location**: `backend/api/admin/business_facts_routes.py:335-406`

**Parameters**:
```python
{
    "fact_id": str                  # Business fact ID to verify
}
```

**Response**:
```python
{
    "fact_id": str,
    "new_status": str,              # "verified" or "outdated"
    "citations": [
        {
            "citation": str,        # Original citation URL
            "exists": bool,         # Whether source still exists
            "source": str           # "R2" or "Local"
        }
    ]
}
```

**Example**:
```python
# Verify all citations for a fact
result = await wm.verify_citation(fact_id="abc-123")

# Returns:
# {
#     "fact_id": "abc-123",
#     "new_status": "verified",
#     "citations": [
#         {
#             "citation": "s3://atom-saas/business_facts/default/.../policy.pdf",
#             "exists": True,
#             "source": "R2"
#         }
#     ]
# }
```

---

## REST API Endpoints

All endpoints require `UserRole.ADMIN` permission.

**Base Path**: `/api/admin/governance/facts`

### List Facts

**GET** `/api/admin/governance/facts`

**Query Parameters**:
- `status` (optional): Filter by verification status
- `domain` (optional): Filter by business domain
- `limit` (optional): Max results (default: 100)

**Response**:
```python
[
    {
        "id": str,
        "fact": str,
        "citations": [str],
        "reason": str,
        "domain": str,
        "verification_status": str,
        "created_at": datetime
    }
]
```

**Example**:
```bash
curl -X GET "http://localhost:8000/api/admin/governance/facts?domain=finance&status=verified&limit=50"
```

### Get Fact

**GET** `/api/admin/governance/facts/{fact_id}`

**Response**: Single `FactResponse` object

### Create Fact

**POST** `/api/admin/governance/facts`

**Request Body**:
```python
{
    "fact": str,
    "citations": [str],
    "reason": str,
    "domain": str
}
```

**Response**: Created `FactResponse`

### Update Fact

**PUT** `/api/admin/governance/facts/{fact_id}`

**Request Body**:
```python
{
    "fact": str (optional),
    "citations": [str] (optional),
    "reason": str (optional),
    "domain": str (optional),
    "verification_status": str (optional)
}
```

**Response**: Updated `FactResponse`

### Delete Fact

**DELETE** `/api/admin/governance/facts/{fact_id}`

**Response**: `{"status": "deleted", "id": fact_id}`

### Upload and Extract

**POST** `/api/admin/governance/facts/upload`

**Parameters**:
- `file` (form-data): Document file
- `domain` (form-data): Business domain (default: "general")

**Response**:
```python
{
    "success": True,
    "facts_extracted": int,
    "facts": [FactResponse],
    "source_document": str,
    "extraction_time": float
}
```

**Supported Formats**:
- `.pdf`, `.docx`, `.doc`, `.txt`
- `.png`, `.tiff`, `.tif`, `.jpeg`, `.jpg` (OCR-enabled)

**Example**:
```bash
curl -X POST \
  http://localhost:8000/api/admin/governance/facts/upload?domain=finance \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@approval_policy.pdf"
```

### Verify Citation

**POST** `/api/admin/governance/facts/{fact_id}/verify-citation`

**Response**: Verification results (see MCP Tools section above)

---

## Citation Verification Flow

### Automatic Verification

```
┌────────────────┐
│  Fact Created  │
└────────┬───────┘
         │
         ▼
┌────────────────────────────────────────┐
│  Citations Parsed                      │
│  - s3:// URIs → R2/S3 check            │
│  - file:paths → Local filesystem check │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│  Storage Service Check                 │
│  storage.check_exists(key)             │
└────────┬───────────────────────────────┘
         │
         ├─▶ Exists → "verified"
         │
         └─▶ Missing → "outdated"
                    │
                    ▼
         ┌──────────────────────┐
         │  Log Warning         │
         │  Update Status       │
         │  Notify Admin (opt)  │
         └──────────────────────┘
```

### Manual Verification

```python
# 1. Trigger verification via API
POST /api/admin/governance/facts/{fact_id}/verify-citation

# 2. System checks all citations
for citation in fact.citations:
    if citation.startswith("s3://"):
        # Parse bucket/key
        bucket_name = storage.bucket
        key = citation.replace(f"s3://{bucket_name}/", "")
        exists = storage.check_exists(key)
    else:
        # Check local filesystem
        exists = os.path.exists(citation)

# 3. Update verification status
new_status = "verified" if all_valid else "outdated"
await wm.update_fact_verification(fact_id, new_status)
```

---

## Storage Architecture

### Hybrid Storage Model

```
┌──────────────────────────────────────────────────────────┐
│                    Storage Layers                        │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────┐      ┌─────────────────┐           │
│  │   PostgreSQL    │      │   LanceDB       │           │
│  │   (Hot Store)   │      │   (Warm Store)  │           │
│  │                 │      │                 │           │
│  │ • Active facts  │      │ • Vector search │           │
│  │ • Recent access │      │ • Semantic sim  │           │
│  │ • Sub-ms lookup │      │ • Embeddings    │           │
│  └─────────────────┘      └─────────────────┘           │
│           │                         │                    │
│           └────────────┬────────────┘                    │
│                        ▼                                 │
│           ┌─────────────────────────┐                    │
│           │   R2 / S3 (Cold Store)  │                    │
│           │                         │                    │
│           │ • Source documents      │                    │
│           │ • PDFs, images          │                    │
│           │ • Persistent archives   │                    │
│           │ • CDN-eligible          │                    │
│           └─────────────────────────┘                    │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### R2/S3 Storage Integration

**Location**: `backend/core/storage.py`

**Key Methods**:

```python
class StorageService:
    def upload_file(self, file_obj, key: str, content_type: str = None) -> str:
        """
        Upload file-like object to S3/R2

        Args:
            file_obj: BytesIO or file object
            key: S3 key path (e.g., "business_facts/workspace_id/doc_id/filename")
            content_type: MIME type (e.g., "application/pdf")

        Returns:
            s3://bucket/key URI string
        """
        self.s3.upload_fileobj(file_obj, self.bucket, key, ExtraArgs=extra_args)
        return f"s3://{self.bucket}/{key}"

    def check_exists(self, key: str) -> bool:
        """
        Check if file exists in S3/R2

        Args:
            key: S3 key path

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False
```

**Configuration**:

```bash
# Environment Variables
AWS_S3_BUCKET=atom-saas
S3_ENDPOINT=https://abc.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=auto
```

**File Organization**:

```
s3://atom-saas/
├── business_facts/
│   ├── default/
│   │   ├── {uuid4}/
│   │   │   ├── policy.pdf
│   │   │   ├── handbook.docx
│   │   │   └── scan.tiff
│   │   └── {uuid4}/
│   │       └── sop.pdf
```

### LanceDB Vector Storage

**Location**: `backend/core/lancedb_handler.py`

**Table Schema**:

```python
schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("workspace_id", pa.string()),
    pa.field("text", pa.string()),              # Fact + citations + reason
    pa.field("source", pa.string()),            # fact_agent_{agent_id}
    pa.field("metadata", pa.string()),          # JSON metadata
    pa.field("created_at", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384))  # Embedding
])
```

**Vector Search**:

```python
# Semantic search for relevant facts
results = db.search(
    table_name="business_facts",
    query="approval limits for invoices",
    limit=5
)

# Results ranked by similarity score
for result in results:
    print(f"Score: {result['score']}")
    print(f"Fact: {result['metadata']['fact']}")
    print(f"Citations: {result['metadata']['citations']}")
```

---

## Usage Examples for Agents

### 1. Recording a Business Fact

```python
from core.agent_world_model import WorldModelService, BusinessFact
from datetime import datetime

wm = WorldModelService(workspace_id="default")

fact = BusinessFact(
    id=str(uuid.uuid4()),
    fact="Remote work requires manager approval for requests > 3 days",
    citations=["s3://atom-saas/business_facts/default/abc/handbook.pdf"],
    reason="HR policy compliance for remote work requests",
    source_agent_id="agent:hr-automation",
    created_at=datetime.now(),
    last_verified=datetime.now(),
    verification_status="verified",
    metadata={"domain": "hr", "max_days": 3}
)

success = await wm.record_business_fact(fact)
```

### 2. Retrieving Relevant Facts

```python
# JIT fact retrieval for decision-making
facts = await wm.get_relevant_business_facts(
    query="approval requirements for remote work",
    limit=5
)

for fact in facts:
    print(f"Fact: {fact.fact}")
    print(f"Citations: {fact.citations}")
    print(f"Status: {fact.verification_status}")

    # Verify citations before using
    if fact.verification_status != "verified":
        logger.warning(f"Fact {fact.id} has outdated citations")
```

### 3. Verifying Citations

```python
# Periodic verification job
async def verify_all_facts():
    wm = WorldModelService(workspace_id="default")

    facts = await wm.list_all_facts(status="verified")
    for fact in facts:
        result = await wm.verify_citation(fact.id)

        if result["new_status"] == "outdated":
            # Send alert to admin
            await send_alert(
                subject=f"Citation verification failed for fact {fact.id}",
                details=result["citations"]
            )
```

### 4. Bulk Fact Recording

```python
# Extract and store multiple facts
business_facts = []

for extracted in extraction_result.facts:
    fact = BusinessFact(
        id=str(uuid.uuid4()),
        fact=extracted.fact,
        citations=[s3_uri],
        reason=f"Extracted from {filename}",
        source_agent_id=f"user:{user_id}",
        created_at=datetime.now(),
        last_verified=datetime.now(),
        verification_status="verified",
        metadata={"domain": extracted.domain or domain}
    )
    business_facts.append(fact)

# Bulk store
stored_count = await wm.bulk_record_facts(business_facts)
```

---

## Testing and Validation

### Unit Tests

```python
import pytest
from core.agent_world_model import WorldModelService, BusinessFact

@pytest.mark.asyncio
async def test_record_business_fact():
    wm = WorldModelService(workspace_id="test")

    fact = BusinessFact(
        id="test-123",
        fact="Test fact",
        citations=["test.pdf"],
        reason="Test",
        source_agent_id="test-agent",
        created_at=datetime.now(),
        last_verified=datetime.now(),
        verification_status="verified"
    )

    success = await wm.record_business_fact(fact)
    assert success is True

@pytest.mark.asyncio
async def test_get_relevant_facts():
    wm = WorldModelService(workspace_id="test")

    facts = await wm.get_relevant_business_facts(
        query="approval policy",
        limit=3
    )

    assert len(facts) <= 3
    assert all(isinstance(f, BusinessFact) for f in facts)
```

### Integration Tests

```bash
# Test citation verification
pytest tests/test_citation_system.py -v

# Test fact extraction from documents
pytest tests/test_fact_extraction.py -v

# Test R2/S3 storage integration
pytest tests/test_storage_integration.py -v
```

### Validation Checklist

- [ ] All citations are valid URIs or file paths
- [ ] Citations point to accessible storage locations
- [ ] Verification status updates correctly
- [ ] Vector search returns semantically similar facts
- [ ] Secrets redaction works before storage
- [ ] RBAC prevents unauthorized access
- [ ] Bulk operations handle failures gracefully

---

## Performance Benchmarks

| Operation | Target | Actual | Notes |
|-----------|--------|--------|-------|
| Fact creation | <100ms | ~50ms | Includes embedding generation |
| Citation verification | <500ms | ~200ms | Per citation (R2/S3 check) |
| Vector search (5 facts) | <100ms | ~50ms | Semantic similarity |
| Bulk fact recording (100) | <5s | ~3s | Parallel embeddings |
| Document upload & extraction | <30s | ~15s | Depends on document size |

---

## Security Considerations

### Secrets Redaction

```python
# Automatic redaction before storage
from core.secrets_redactor import get_secrets_redactor

redactor = get_secrets_redactor()
redaction_result = redactor.redact(text)

if redaction_result.has_secrets:
    logger.warning(f"Redacted {len(redaction_result.redactions)} secrets")
    text = redaction_result.redacted_text

# Add redaction metadata
metadata["_redacted_types"] = [r["type"] for r in redaction_result.redactions]
metadata["_redaction_count"] = len(redaction_result.redactions)
```

### RBAC Enforcement

```python
from core.security.rbac import require_role
from core.models import UserRole

@router.post("", response_model=FactResponse)
async def create_fact(
    request: FactCreateRequest,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))  # ADMIN only
):
    # Only ADMIN users can create facts
    ...
```

### Access Control

- **ADMIN**: Full CRUD operations, verification, bulk operations
- **USER**: Read-only access (future feature)
- **AGENT**: Read-only via WorldModelService queries

---

## Troubleshooting

### Common Issues

**Issue**: Citation verification fails for valid R2/S3 URLs

**Solution**:
```bash
# Check storage configuration
echo $AWS_S3_BUCKET
echo $S3_ENDPOINT

# Test connection manually
python -c "
from core.storage import get_storage_service
storage = get_storage_service()
print(storage.check_exists('business_facts/default/test/file.pdf'))
"
```

**Issue**: Vector search returns no results

**Solution**:
```python
# Check embedding generation
from core.lancedb_handler import get_lancedb_handler

handler = get_lancedb_handler()
embedding = handler.embed_text("test query")
print(f"Embedding dimension: {len(embedding)}")

# Verify table exists
print(handler.db.table_names())
```

**Issue**: Facts not extracted from uploaded documents

**Solution**:
```bash
# Check Docling availability
python -c "
from core.docling_processor import is_docling_available
print(f'Docling available: {is_docling_available()}')

# Verify file format is supported
processor = get_docling_processor()
print(processor.get_supported_formats())
"
```

---

## Related Documentation

- [JIT Fact Provision System](./JIT_FACT_PROVISION_SYSTEM.md) - Real-time fact retrieval
- [Document Processing Pipeline](./DOCUMENT_PROCESSING_PIPELINE.md) - Multi-format parsing
- [Architecture Diagrams](./ARCHITECTURE_DIAGRAMS.md) - Visual system overview
- [Agent World Model](../backend/core/agent_world_model.py) - Core implementation

---

## Changelog

### February 2026
- Initial citation system implementation
- R2/S3 storage integration
- Docling document processor
- Automatic secrets redaction
- Verification status tracking

### Future Enhancements
- [ ] Batch verification operations
- [ ] Citation confidence scoring
- [ ] Automatic re-extraction from updated documents
- [ ] Cross-reference detection between facts
- [ ] Fact versioning with change history

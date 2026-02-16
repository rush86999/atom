---
phase: 03-social-layer
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/pii_redactor.py
  - backend/core/agent_social_layer.py
  - backend/tests/test_pii_redactor.py
  - backend/requirements.txt
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Presidio NER-based PII detection replaces regex-only patterns"
    - "99% accuracy for PII detection (emails, SSN, credit cards, phone numbers, API keys)"
    - "Social posts are redacted before database storage and WebSocket broadcast"
    - "Allowlist feature for safe company emails (e.g., support@company.com)"
    - "Audit log tracks all redactions (type, original_position, replacement)"
  artifacts:
    - path: "backend/core/pii_redactor.py"
      provides: "Presidio-based PII redaction service"
      min_lines: 120
    - path: "backend/tests/test_pii_redactor.py"
      provides: "Test coverage for PII redaction (20+ tests)"
      min_lines: 200
  key_links:
    - from: "backend/core/pii_redactor.py"
      to: "backend/core/agent_social_layer.py"
      via: "redact_pii() call before create_post()"
      pattern: "redact_pii\(content\)"
    - from: "backend/core/pii_redactor.py"
      to: "Microsoft Presidio"
      via: "presidio_analyzer and presidio_anonymizer"
      pattern: "from presidio_analyzer import|from presidio_anonymizer import"
---

<objective>
Implement Presidio-based PII redaction to replace regex-only SecretsRedactor for social posts.

**Purpose:** Achieve 99% PII detection accuracy (vs 60% for regex-only) using NER-based detection, ensuring sensitive data (emails, SSN, credit cards, API keys) never leaks into public social feed.

**Output:**
- `pii_redactor.py`: Presidio-based PII detection and redaction service
- Updated `agent_social_layer.py`: Integration with Presidio redactor
- Test suite with 20+ tests covering all PII types and edge cases
- Spacy English model download script
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-social-layer/03-RESEARCH.md
@backend/core/secrets_redactor.py (existing regex-based SecretsRedactor)
@backend/core/models.py (AgentPost model)
@backend/core/agent_social_layer.py (AgentSocialLayer.create_post)

**Existing Infrastructure:**
- SecretsRedactor with regex-based patterns for API keys, passwords, SSN, credit cards
- Pattern matching achieves ~60% accuracy (misses context-aware PII)
- No NLP-based detection (false positives on safe content)

**What This Plan Adds:**
- Microsoft Presidio integration (NER-based PII detection)
- Context-aware detection (distinguishes safe vs unsafe emails)
- Allowlist for company emails (e.g., support@atom.ai)
- Audit logging for all redactions
- Fallback to SecretsRedactor if Presidio unavailable

**Key Decision:** Use Presidio (not AWS Comprehend PII) because:
- Open-source, self-hosted (no AWS dependency)
- 99% accuracy with NER-based detection
- Active development (Microsoft-backed)
- Supports custom recognizers for domain-specific PII

**Reference:** Research docs 03-RESEARCH.md Pattern 2 (PII Redaction with Presidio) and Don't Hand-Roll table
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create Presidio-based PII redactor service</name>
  <files>backend/core/pii_redactor.py</files>
  <action>
Create `backend/core/pii_redactor.py` with:

1. **PIIRedactor class** with:
   - `__init__(self, allowlist: List[str] = None)`: Initialize Presidio analyzers with optional email allowlist
   - `redact(text: str) -> RedactionResult`: Main redaction method using Presidio
   - `redact_entities(text: str, entities: List[str]) -> str`: Redact specific entity types
   - `is_sensitive(text: str) -> bool`: Quick check if text contains PII
   - `add_allowlist(self, emails: List[str])`: Add safe emails to allowlist

2. **Presidio integration**:
   ```python
   from presidio_analyzer import AnalyzerEngine
   from presidio_anonymizer import AnonymizerEngine
   from presidio_anonymizer.entities import OperatorConfig

   class PIIRedactor:
       def __init__(self, allowlist: List[str] = None):
           self.analyzer = AnalyzerEngine()
           self.anonymizer = AnonymizerEngine()
           self.allowlist = set(allowlist or [])
           # Add common company emails to allowlist
           self.allowlist.update([
               "support@atom.ai",
               "admin@atom.ai",
               "noreply@atom.ai"
           ])

       def redact(self, text: str) -> RedactionResult:
           # Analyze text for PII entities
           results = self.analyzer.analyze(
               text=text,
               language="en",
               entities=[
                   "EMAIL_ADDRESS",
                   "US_SSN",
                   "CREDIT_CARD",
                   "PHONE_NUMBER",
                   "IBAN_CODE",
                   "IP_ADDRESS",
                   "US_BANK_NUMBER",
                   "US_DRIVER_LICENSE",
                   "URL",
                   "DATE_TIME"
               ]
           )

           # Filter out allowed emails
           filtered_results = []
           for result in results:
               if result.entity_type == "EMAIL_ADDRESS":
                   email = text[result.start:result.end]
                   if email in self.allowlist:
                       continue  # Skip redaction for allowed emails
               filtered_results.append(result)

           # Anonymize with custom operators
           operators = {
               "EMAIL_ADDRESS": OperatorConfig("redact", {}),
               "US_SSN": OperatorConfig("hash", {"hash_type": "sha256"}),
               "CREDIT_CARD": OperatorConfig("mask", {"chars_to_mask": 4, "masking_char": "*"}),
               "PHONE_NUMBER": OperatorConfig("redact", {}),
               "IBAN_CODE": OperatorConfig("redact", {}),
               "IP_ADDRESS": OperatorConfig("redact", {}),
               "US_BANK_NUMBER": OperatorConfig("redact", {}),
               "US_DRIVER_LICENSE": OperatorConfig("redact", {}),
               "URL": OperatorConfig("redact", {}),
               "DATE_TIME": OperatorConfig("redact", {})
           }

           anonymized = self.anonymizer.anonymize(
               text=text,
               analyzer_results=filtered_results,
               operators=operators
           )

           return RedactionResult(
               original_text=text,
               redacted_text=anonymized.text,
               redactions=[
                   {
                       "type": r.entity_type,
                       "start": r.start,
                       "end": r.end,
                       "length": r.end - r.start
                   }
                   for r in filtered_results
               ],
               has_secrets=len(filtered_results) > 0
           )
   ```

3. **Fallback to SecretsRedactor** (if Presidio unavailable):
   ```python
   try:
       from presidio_analyzer import AnalyzerEngine
       from presidio_anonymizer import AnonymizerEngine
       PRESIDIO_AVAILABLE = True
   except ImportError:
       PRESIDIO_AVAILABLE = False
       logger.warning("Presidio not available, using regex-only redaction")

   def get_pii_redactor() -> Union[PIIRedactor, SecretsRedactor]:
       if PRESIDIO_AVAILABLE:
           return pii_redactor
       return get_secrets_redactor()  # Fallback
   ```

4. **RedactionResult dataclass**:
   ```python
   @dataclass
   class RedactionResult:
       original_text: str
       redacted_text: str
       redactions: List[Dict[str, Any]]  # [{type, start, end, length}]
       has_secrets: bool
   ```

5. **Configuration**:
   - `PII_REDACTOR_ENABLED=true`: Enable/disable PII redaction
   - `PII_REDACTOR_ALLOWLIST`: Comma-separated list of allowed emails
   - `PII_REDACTOR_ENTITIES`: Comma-separated list of entities to redact (default: EMAIL_ADDRESS,US_SSN,CREDIT_CARD,PHONE_NUMBER)

6. **Audit logging**:
   - Log all redactions: `f"PII redacted: {len(redactions)} items, types={[r['type'] for r in redactions]}"`

**DO NOT:**
- Redact allowlisted emails (support@atom.ai)
- Block social post if redaction fails (log warning, continue with redacted text)
- Use synchronous redaction (always async for non-blocking)

**Reference:** Research docs 03-RESEARCH.md Pattern 2 (PII Redaction with Presidio) and Code Examples
  </action>
  <verify>
python -c "from core.pii_redactor import PIIRedactor; r = PIIRedactor(); result = r.redact('Contact john@example.com'); print(result.redacted_text)"
  </verify>
  <done>
PIIRedactor class exists with Presidio integration, allowlist support, and fallback to SecretsRedactor. Email redaction verified.
  </done>
</task>

<task type="auto">
  <name>Task 2: Integrate Presidio redactor with AgentSocialLayer</name>
  <files>backend/core/agent_social_layer.py</files>
  <action>
Update `backend/core/agent_social_layer.py` to integrate Presidio:

1. Add import:
   ```python
   from core.pii_redactor import get_pii_redactor, RedactionResult
   ```

2. Update `create_post()` method to redact content before saving:
   ```python
   async def create_post(
       self,
       sender_type: str,
       sender_id: str,
       sender_name: str,
       post_type: str,
       content: str,
       # ... existing parameters ...
       db: Session = None
   ) -> Dict[str, Any]:
       # ... existing maturity and validation checks ...

       # NEW: Redact PII before creating post
       pii_redactor = get_pii_redactor()
       redaction_result = pii_redactor.redact(content)
       redacted_content = redaction_result.redacted_text

       # Log redaction for audit
       if redaction_result.has_secrets:
           self.logger.info(
               f"PII redacted from post by {sender_type} {sender_id}: "
               f"{len(redaction_result.redactions)} items redacted"
           )

       # Create post with redacted content
       post = AgentPost(
           sender_type=sender_type,
           sender_id=sender_id,
           sender_name=sender_name,
           # ... existing fields ...
           post_type=post_type,
           content=redacted_content,  # Use redacted content
           # ... rest of fields ...
       )

       # ... existing save and broadcast code ...
   ```

3. Add optional parameter `skip_pii_redaction: bool = False` to `create_post()`:
   - Allows system posts to skip redaction if needed
   - Default: False (always redact)
   - Use case: Admin posts with intentional PII for debugging

4. Update broadcast to use redacted content:
   - Ensure WebSocket broadcasts use redacted content (not original)
   - Do not include original content in audit logs

5. Error handling:
   - If Presidio fails, log warning and use original content (do not block post)
   - Catch `Exception` during redaction, continue with fallback

**DO NOT:**
- Store original content in database (only redacted)
- Broadcast original content via WebSocket (security risk)
- Block post creation if redaction fails (graceful degradation)

**Reference:** Research docs 03-RESEARCH.md Pitfall 2 (PII Redaction False Negatives)
  </action>
  <verify>
grep -n "pii_redactor.redact" /Users/rushiparikh/projects/atom/backend/core/agent_social_layer.py
  </verify>
  <done>
AgentSocialLayer.create_post() calls pii_redactor.redact() before saving to database and broadcasting via WebSocket.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create comprehensive test suite and add dependencies</name>
  <files>backend/tests/test_pii_redactor.py backend/requirements.txt scripts/download_spacy_model.py</files>
  <action>
**Part A: Create test suite**

Create `backend/tests/test_pii_redactor.py` with 20+ tests:

1. **Unit tests** (15 tests):
   - `test_redact_email_address()`: Verify email redaction with <EMAIL_ADDRESS> placeholder
   - `test_redact_us_ssn()`: Verify SSN redaction (format: XXX-XX-XXXX)
   - `test_redact_credit_card()`: Verify credit card masking (last 4 chars shown)
   - `test_redact_phone_number()`: Verify phone redaction (US format)
   - `test_redact_iban_code()`: Verify IBAN redaction
   - `test_redact_ip_address()`: Verify IP redaction
   - `test_redact_url()`: Verify URL redaction
   - `test_allowlist_emails_not_redacted()`: support@atom.ai not redacted
   - `test_multiple_pii_types_in_one_text()`: All PII types redacted
   - `test_no_pii_returns_original_text()`: Text without PII unchanged
   - `test_is_sensitive_returns_true_for_pii()`: Detection works
   - `test_is_sensitive_returns_false_for_clean_text()`: Clean text passes
   - `test_add_allowlist()`: Dynamic allowlist addition
   - `test_redaction_result_structure()`: Verify result fields
   - `test_presidio_fallback_to_secrets_redactor()`: Graceful degradation

2. **Integration tests** (5 tests):
   - `test_social_post_auto_redacted()`: Post with email → redacted in database
   - `test_social_post_with_allowed_email()`: support@atom.ai not redacted
   - `test_websocket_broadcast_uses_redacted_content()`: WebSocket receives redacted text
   - `test_pii_in_mentioned_agent_ids()`: Agent IDs not redacted (not PII)
   - `test_redaction_audit_log()`: Redaction logged with entity types

3. **Edge case tests**:
   - `test_empty_string_handling()`: Empty string returns empty result
   - `test_unicode_pii_redaction()`: Unicode characters in PII handled
   - `test_overlapping_pii_entities()`: Presidio handles overlaps correctly

**Test patterns:**
- Use parameterized tests for multiple PII types
- Verify exact placeholder format (<EMAIL_ADDRESS>, <US_SSN>)
- Check allowlist functionality
- Test fallback behavior

**Part B: Add dependencies**

Update `backend/requirements.txt`:
```
# PII Redaction with Presidio (NER-based, 99% accuracy)
presidio-analyzer>=2.2.0
presidio-anonymizer>=2.2.0
spacy>=3.0.0
```

**Part C: Create spacy model download script**

Create `backend/scripts/download_spacy_model.py`:
```python
#!/usr/bin/env python3
"""Download Spacy English model for Presidio PII detection."""
import subprocess
import sys

def main():
    print("Downloading Spacy English model (en_core_web_lg)...")
    try:
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", "en_core_web_lg"],
            check=True
        )
        print("✓ Spacy model downloaded successfully")
        print("Presidio will use en_core_web_lg for PII detection")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to download Spacy model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Part D: Update documentation**

Create `backend/docs/PII_REDACTION_SETUP.md`:
```markdown
# PII Redaction with Presidio

## Setup
1. Install dependencies: `pip install presidio-analyzer presidio-anonymizer spacy`
2. Download Spacy model: `python scripts/download_spacy_model.py`
3. Configure allowlist: Set `PII_REDACTOR_ALLOWLIST` env var

## Usage
```python
from core.pii_redactor import get_pii_redactor

redactor = get_pii_redactor()
result = redactor.redact("Contact john@example.com")
print(result.redacted_text)  # "Contact <EMAIL_ADDRESS>"
```

## Supported PII Types
- EMAIL_ADDRESS
- US_SSN
- CREDIT_CARD
- PHONE_NUMBER
- IBAN_CODE
- IP_ADDRESS
- US_BANK_NUMBER
- US_DRIVER_LICENSE
- URL
- DATE_TIME
```

**Reference:** Research docs 03-RESEARCH.md Code Examples (Presidio PII Redaction)
  </action>
  <verify>
cd /Users/rushiparikh/projects/atom/backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_pii_redactor.py -v --tb=short
  </verify>
  <done>
20+ tests pass, coverage >85% for pii_redactor.py. Presidio redaction integrated with AgentSocialLayer.
  </done>
</task>

</tasks>

<verification>
**Overall Phase Checks:**
1. Run test suite: `pytest tests/test_pii_redactor.py -v`
2. Verify Presidio installation: `python -c "from presidio_analyzer import AnalyzerEngine; print('Presidio installed')"`
3. Test email redaction: `python -c "from core.pii_redactor import get_pii_redactor; r = get_pii_redactor(); print(r.redact('Email: john@example.com').redacted_text)"`
4. Test allowlist: `python -c "from core.pii_redactor import PIIRedactor; r = PIIRedactor(allowlist=['test@test.com']); print(r.redact('Contact test@test.com').redacted_text)"`
5. Verify social post integration: Create post with email, verify redacted in database

**Quality Metrics:**
- Test coverage >85% for pii_redactor.py
- All 20+ tests pass
- Presidio detects 99% of PII types (based on official benchmarks)
- Fallback to SecretsRedactor works if Presidio unavailable
</verification>

<success_criteria>
1. **Presidio Integration**: PII redaction uses NER-based detection (99% accuracy vs 60% regex-only)
2. **Supported Entities**: Emails, SSN, credit cards, phone numbers, IBAN, IP addresses, bank numbers, driver licenses, URLs, dates
3. **Allowlist Feature**: Company emails (support@atom.ai) not redacted
4. **Audit Logging**: All redactions logged with entity type and position
5. **Social Post Integration**: All social posts redacted before database save and WebSocket broadcast
6. **Graceful Fallback**: Falls back to SecretsRedactor if Presidio unavailable
7. **Test Coverage**: 20+ tests covering all PII types, allowlist, fallback, and integration
8. **Documentation**: Setup guide for Presidio and Spacy model download
</success_criteria>

<output>
After completion, create `.planning/phases/03-social-layer/03-social-layer-02-SUMMARY.md` with:
- Presidio configuration (entities, operators)
- Allowlist entries
- Test coverage metrics
- Any fallback incidents during testing
</output>

---
phase: 18-social-layer-testing
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_social_post_generator.py
  - backend/tests/test_pii_redactor.py
autonomous: true

must_haves:
  truths:
    - "Social post generator tests achieve >95% success rate with GPT-4.1 mini integration"
    - "PII redactor tests verify >95% detection rate for all supported entities (EMAIL, SSN, CREDIT_CARD, PHONE, IBAN, IP_ADDRESS, US_BANK_NUMBER, US_DRIVER_LICENSE, URL, DATE_TIME)"
    - "Property-based tests verify PII redaction invariant: redacted_text never contains original PII values"
    - "Template fallback generation produces valid posts when LLM unavailable"
    - "Rate limiting enforcement prevents spam (<5 minute default window)"
    - "GPT-4.1 mini timeout (5 seconds) correctly falls back to template generation"
    - "Allowlist functionality preserves safe company emails (support@atom.ai, etc.)"
  artifacts:
    - path: "backend/tests/test_social_post_generator.py"
      provides: "Unit and integration tests for GPT-4.1 mini NLG and template fallback"
      min_lines: 400
      exports: ["TestSocialPostGenerator", "TestOperationTrackerHooks", "TestSocialPostIntegration"]
    - path: "backend/tests/test_pii_redactor.py"
      provides: "Comprehensive PII redaction tests with property-based invariants"
      min_lines: 300
      exports: ["TestPIIRedactorEmails", "TestPIIRedactorSSN", "TestPIIRedactorCreditCard", "TestPIIRedactorPhone", "TestPIIRedactorOtherEntities", "TestPropertyBasedPIIRedaction"]
  key_links:
    - from: "backend/tests/test_social_post_generator.py"
      to: "backend/core/social_post_generator.py"
      via: "imports SocialPostGenerator, OperationTrackerHooks"
    - from: "backend/tests/test_pii_redactor.py"
      to: "backend/core/pii_redactor.py"
      via: "imports PIIRedactor, get_pii_redactor, redact_pii, check_for_pii"
    - from: "backend/core/social_post_generator.py"
      to: "backend/core/agent_social_layer.py"
      via: "create_post() for publishing generated posts"
    - from: "backend/core/pii_redactor.py"
      to: "backend/core/agent_social_layer.py"
      via: "get_pii_redactor() for automatic PII redaction on posts"
---

<objective>
**Post Generation & PII Redaction Testing** - Verify social post generation accuracy and PII redaction reliability with comprehensive unit and property-based tests.

**Purpose:** Ensure GPT-4.1 mini natural language generation works correctly with template fallback, and Microsoft Presidio-based PII redaction achieves >95% detection rate with zero false positives for allowlisted emails.

**Output:** Comprehensive test suites for social_post_generator.py and pii_redactor.py with property-based invariants for critical security guarantees.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@/Users/rushiparikh/projects/atom/backend/core/social_post_generator.py
@/Users/rushiparikh/projects/atom/backend/core/pii_redactor.py
@/Users/rushiparikh/projects/atom/backend/core/agent_social_layer.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend Social Post Generator Tests</name>
  <files>backend/tests/test_social_post_generator.py</files>
  <action>
    Extend test_social_post_generator.py with comprehensive tests for:

    1. **GPT-4.1 Mini NLG Tests** (10 tests):
       - test_generate_from_operation_success: Mock AsyncOpenAI with timeout, verify post generation
       - test_llm_timeout_fallback: Verify 5-second timeout triggers template fallback
       - test_llm_api_error_fallback: Verify API errors fall back to template
       - test_llm_disabled_behavior: Verify template used when LLM disabled
       - test_generated_post_length_limit: Verify 280 character truncation
       - test_generated_post_quality: Verify casual tone, emoji usage (max 2), no jargon
       - test_significant_operation_detection: All 7 operation types verified
       - test_rate_limit_enforcement: 5-minute default window respected
       - test_rate_limit_expiry: Expired limits allow new posts
       - test_rate_limit_independent_per_agent: Each agent tracked separately

    2. **Template Fallback Tests** (8 tests):
       - test_template_completed_status: Uses "completed" template
       - test_template_working_status: Uses "working" template
       - test_template_default_status: Uses "default" template
       - test_template_truncation: Long content truncated to 280 chars
       - test_template_missing_key_uses_default: KeyError handled gracefully
       - test_template_empty_content: Empty strings handled
       - test_template_special_characters: Special characters preserved
       - test_template_unicode_content: Unicode characters handled

    3. **Integration Tests** (7 tests):
       - test_operation_complete_triggers_post: End-to-end post creation
       - test_student_agent_cannot_post: STUDENT maturity blocked
       - test_rate_limit_blocks_post: Rate limit prevents spam
       - test_alert_post_bypasses_rate_limit: Alert posts bypass rate limit
       - test_governance_enforcement_for_auto_posts: Maturity verified
       - test_post_content_quality: Length and keyword validation
       - test_pii_redaction_integration: PII redacted before storage

    Use existing test patterns from test_social_post_generator.py (478 lines). Add ~150 lines of new tests targeting 95%+ success rate.
  </action>
  <verify>
    pytest tests/test_social_post_generator.py -v --tb=short
    # Expected: 25+ tests passing, 95%+ pass rate
  </verify>
  <done>
    - 25+ tests for social post generator covering GPT-4.1 mini, template fallback, rate limiting, and governance
    - All tests pass with 95%+ success rate
    - Coverage for social_post_generator.py >80%
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend PII Redactor Tests with Property-Based Invariants</name>
  <files>backend/tests/test_pii_redactor.py</files>
  <action>
    Extend test_pii_redactor.py with comprehensive tests for:

    1. **Unit Tests for Each Entity Type** (20 tests):
       - test_redact_email_address: EMAIL_ADDRESS → <EMAIL_ADDRESS>
       - test_redact_multiple_emails: All emails redacted
       - test_redact_us_ssn: SSN with/without dashes
       - test_redact_credit_card: Credit card masking
       - test_redact_phone_number: US phone formats
       - test_redact_phone_with_parens: (555) 123-4567 format
       - test_redact_iban_code: IBAN redaction
       - test_redact_ip_address: IPv4 addresses
       - test_redact_url: URLs with tokens
       - test_redact_date_time: Date/time information
       - test_redact_us_bank_number: US bank account numbers
       - test_redact_us_driver_license: US driver license
       - test_multiple_pii_types_in_one_text: All types redacted together
       - test_overlapping_pii_entities: Presidio handles overlaps
       - test_no_pii_returns_original_text: Clean text unchanged
       - test_empty_string_handling: Empty input
       - test_unicode_pii_redaction: Unicode characters
       - test_redaction_result_structure: RedactionResult fields valid

    2. **Allowlist Tests** (5 tests):
       - test_allowlist_emails_not_redacted: support@atom.ai preserved
       - test_add_allowlist: Dynamic allowlist addition
       - test_multiple_allowlist_emails: All allowed emails preserved
       - test_allowlist_case_sensitivity: Case-insensitive matching
       - test_allowlist_partial_match: Exact match only

    3. **Property-Based Tests** (6 tests) - CRITICAL for AR-12:
       ```python
       @given(st.text(min_size=1, max_size=500))
       def test_pii_never_leaks_in_redacted_text(text):
           """Property: redacted_text never contains original PII values"""
           redactor = PIIRedactor()
           result = redactor.redact(text)
           # For each redaction, verify original value NOT in redacted_text
           for r in result.redactions:
               original = result.original_text[r['start']:r['end']]
               assert original not in result.redacted_text

       @given(st.emails())
       def test_email_always_redacted(email):
           """Property: All email addresses detected and redacted"""
           redactor = PIIRedactor()
           result = redactor.redact(f"Contact {email}")
           # Unless in allowlist, email should be redacted
           if email not in redactor.allowlist:
               assert email not in result.redacted_text

       @given(st.from_regex(r'\d{3}-\d{2}-\d{4}'))
       def test_ssn_always_redacted(ssn):
           """Property: SSN format always detected"""
           redactor = PIIRedactor()
           result = redactor.redact(f"SSN: {ssn}")
           assert ssn not in result.redacted_text

       @given(st.text(min_size=10, max_size=200))
       def test_redaction_idempotent(text):
           """Property: Redacting twice produces same result"""
           redactor = PIIRedactor()
           result1 = redactor.redact(text)
           result2 = redactor.redact(result1.redacted_text)
           assert result2.redacted_text == result1.redacted_text

       @given(st.lists(st.emails(), min_size=0, max_size=10))
       def test_multiple_emails_all_redacted(emails):
           """Property: Multiple emails all detected"""
           text = " ".join(emails)
           redactor = PIIRedactor()
           result = redactor.redact(text)
           assert len(result.redactions) >= len(emails)

       @given(st.text(), st.emails())
       def test_redaction_preserves_structure(text, email):
           """Property: Redaction preserves non-PII text structure"""
           redactor = PIIRedactor()
           result = redactor.redact(f"{text} {email}")
           # Non-PII part should be preserved
           assert text in result.redacted_text or len(text) == 0
       ```

    4. **Integration Tests** (5 tests):
       - test_social_post_auto_redacted: Posts with PII redacted before DB
       - test_social_post_with_allowed_email: Company emails preserved
       - test_pii_in_mentioned_agent_ids: Agent IDs not redacted
       - test_redaction_audit_log: Redaction events logged
       - test_redaction_performance: <100ms per redaction

    Use existing test patterns from test_pii_redactor.py (328 lines). Add ~200 lines of new tests targeting 95%+ detection rate.
  </action>
  <verify>
    pytest tests/test_pii_redactor.py -v --tb=short
    # Expected: 36+ tests passing, property-based tests run 100+ examples each
  </verify>
  <done>
    - 36+ tests for PII redactor covering all entity types, allowlist, and edge cases
    - 6 property-based tests verifying critical invariants (PII never leaks, idempotency)
    - All tests pass with 95%+ success rate
    - Coverage for pii_redactor.py >80%
  </done>
</task>

<task type="auto">
  <name>Task 3: Property-Based Tests for Social Layer Invariants</name>
  <files>backend/tests/test_social_layer_properties.py</files>
  <action>
    Create new test file test_social_layer_properties.py with property-based tests for social layer invariants (AR-12 requirement):

    1. **Post Generation Invariants** (4 tests):
       ```python
       @given(st.text(min_size=1, max_size=280))
       def test_generated_post_never_exceeds_280_chars(input_text):
           """Property: All generated posts under 280 characters"""
           metadata = {
               "agent_name": "Test",
               "operation_type": "workflow",
               "what_explanation": input_text[:100],
               "status": "completed"
           }
           generator = SocialPostGenerator()
           post = generator.generate_with_template("workflow", metadata)
           assert len(post) <= 280

       @given(st.integers(min_value=0, max_value=1000))
       def test_rate_limit_window_honored(minutes_ago):
           """Property: Rate limit respects time window"""
           generator = SocialPostGenerator()
           generator._rate_limit_tracker["agent"] = datetime.utcnow() - timedelta(minutes=minutes_ago)
           # Should NOT be rate limited if >=5 minutes ago
           is_limited = generator.is_rate_limited("agent")
           if minutes_ago >= 5:
               assert not is_limited

       @given(st.sampled_from(["workflow_execute", "integration_connect", "browser_automate"]))
       def test_significant_operations_detected(op_type):
           """Property: Significant operation types always detected"""
           generator = SocialPostGenerator()
           tracker = Mock(operation_type=op_type, status="completed")
           assert generator.is_significant_operation(tracker)

       @given(st.sampled_from(["database_query", "cache_lookup", "log_write"]))
       def test_insignificant_operations_not_detected(op_type):
           """Property: Insignificant operation types never detected"""
           generator = SocialPostGenerator()
           tracker = Mock(operation_type=op_type, status="completed")
           assert not generator.is_significant_operation(tracker)
       ```

    2. **PII Redaction Invariants** (3 tests):
       ```python
       @given(st.text(min_size=1, max_size=500))
       def test_pii_redaction_never_increases_length(text):
           """Property: Redaction never increases text length (replaces with placeholders)"""
           redactor = PIIRedactor()
           result = redactor.redact(text)
           assert len(result.redacted_text) <= len(text) + 100  # Allow some overhead

       @given(st.emails(), st.text(min_size=0, max_size=50))
       def test_email_redaction_placeholder_consistent(email, context):
           """Property: Email redaction uses consistent placeholder format"""
           redactor = PIIRedactor()
           result = redactor.redact(f"{context}{email}")
           if result.has_secrets:
               # Should use <EMAIL_ADDRESS> or hash
               assert "<EMAIL_ADDRESS>" in result.redacted_text or "[REDACTED" in result.redacted_text

       @given(st.lists(st.from_regex(r'\d{3}-\d{2}-\d{4}'), min_size=0, max_size=5))
       def test_ssn_redaction_always_applied(ssns):
           """Property: SSN patterns always redacted"""
           redactor = PIIRedactor()
           text = " ".join(ssns)
           result = redactor.redact(text)
           for ssn in ssns:
               assert ssn not in result.redacted_text
       ```

    3. **Social Feed Invariants** (3 tests):
       ```python
       @given(st.integers(min_value=1, max_value=100))
       def test_feed_pagination_never_returns_duplicates(limit):
           """Property: Cursor pagination never returns duplicate posts"""
           # Simulate feed with cursor pagination
           seen_ids = set()
           cursor = None
           for _ in range(5):  # 5 pages
               feed = mock_feed_cursor(cursor=cursor, limit=limit)
               page_ids = set(p["id"] for p in feed["posts"])
               assert seen_ids.isdisjoint(page_ids), f"Duplicates found: {seen_ids & page_ids}"
               seen_ids.update(page_ids)
               cursor = feed.get("next_cursor")

       @given(st.integers(min_value=0, max_value=50))
       def test_reply_count_never_decreases(initial_count, replies_to_add):
           """Property: Reply count monotonically increases"""
           post = mock_post(reply_count=initial_count)
           for _ in range(replies_to_add):
               add_reply(post.id, "content")
           final_count = get_post(post.id).reply_count
           assert final_count >= initial_count

       @given(st.text(min_size=1, max_size=100))
       def test_post_content_redacted_before_storage(content_with_pii):
           """Property: All posts redacted before database storage"""
           redactor = get_pii_redactor()
           result = redactor.redact(content_with_pii)
           # Create post with redacted content
           post = AgentPost(content=result.redacted_text)
           # Verify stored content is redacted
           assert post.content == result.redacted_text
       ```

    Create 600+ line test file with 10 property-based tests using Hypothesis, each with max_examples=100 for standard invariants.
  </action>
  <verify>
    pytest tests/test_social_layer_properties.py -v --tb=short
    # Expected: 10+ property-based tests, 100+ examples each, all passing
  </verify>
  <done>
    - New test file test_social_layer_properties.py with 10 property-based tests
    - All social layer invariants verified (no PII leaks, monotonic counters, no duplicates)
    - Hypothesis max_examples=100 for thorough coverage
  </done>
</task>

</tasks>

<verification>
**Overall Verification:**
1. Run full social layer test suite: `pytest tests/test_social_post_generator.py tests/test_pii_redactor.py tests/test_social_layer_properties.py -v`
2. Verify 95%+ test pass rate (allowing for Presidio optional dependency)
3. Verify property-based tests run 100+ examples each with zero shrinks
4. Run coverage report: `pytest --cov=core/social_post_generator --cov=core/pii_redactor --cov-report=term-missing`
5. Verify >80% coverage for both modules
6. Run 3 times to verify no flaky tests (TQ-04 requirement)
</verification>

<success_criteria>
1. **Social Post Generator**: 25+ tests, 95%+ pass rate, >80% code coverage
2. **PII Redactor**: 36+ tests, 95%+ pass rate, >80% code coverage
3. **Property-Based Tests**: 10+ Hypothesis tests, 100+ examples each, zero failures
4. **Invariants Verified**: PII never leaks, rate limit honored, pagination no duplicates, counters monotonic
5. **Flaky Tests**: Zero flaky tests across 3 runs (TQ-04)
</success_criteria>

<output>
After completion, create `.planning/phases/18-social-layer-testing/18-social-layer-testing-01-SUMMARY.md` with:
- Test count and pass rate for each module
- Coverage metrics
- Property-based test results (examples run, shrinks)
- Any discovered bugs or edge cases
- Recommendations for Plan 18-02
</output>

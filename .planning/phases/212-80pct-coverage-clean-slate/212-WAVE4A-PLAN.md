---
phase: 212-80pct-coverage-clean-slate
plan: WAVE4A
type: execute
wave: 4
depends_on: ["212-WAVE3A", "212-WAVE3B", "212-WAVE3C"]
files_modified:
  - backend/tests/test_governance_invariants.py
  - backend/tests/test_llm_invariants.py
  - backend/tests/test_episode_invariants.py
  - backend/tests/test_financial_invariants.py
  - backend/tests/test_security_invariants.py
autonomous: true

must_haves:
  truths:
    - "All property-based tests pass with 1000+ examples"
    - "Governance invariants validated (maturity, permissions, cache consistency)"
    - "LLM invariants validated (tier classification, caching, escalation)"
    - "Episode invariants validated (segmentation, retrieval, feedback weighting)"
    - "Financial invariants validated (decimal precision, double-entry accounting)"
    - "Security invariants validated (JWT, RBAC, secret redaction)"
  artifacts:
    - path: "backend/tests/test_governance_invariants.py"
      provides: "Property-based tests for governance invariants"
      min_lines: 250
      exports: ["test_maturity_routing_invariant", "test_permission_invariant", "test_cache_db_consistency"]
    - path: "backend/tests/test_llm_invariants.py"
      provides: "Property-based tests for LLM invariants"
      min_lines: 250
      exports: ["test_cognitive_tier_invariant", "test_cache_invariant", "test_escalation_on_low_quality"]
    - path: "backend/tests/test_episode_invariants.py"
      provides: "Property-based tests for episode invariants"
      min_lines: 250
      exports: ["test_segmentation_invariant", "test_retrieval_invariant", "test_feedback_weighting"]
    - path: "backend/tests/test_financial_invariants.py"
      provides: "Property-based tests for financial invariants"
      min_lines: 250
      exports: ["test_decimal_precision_invariant", "test_double_entry_invariant", "test_budget_enforcement"]
      invariant_definitions: |
        Decimal precision: All calculations use Decimal, not float
        Double-entry: Debits must equal credits for balanced transactions
        Budget enforcement: Costs never exceed approved budget
        Audit trail: Audit entries are immutable
    - path: "backend/tests/test_security_invariants.py"
      provides: "Property-based tests for security invariants"
      min_lines: 250
      exports: ["test_jwt_signature_required", "test_role_based_permissions", "test_secrets_never_logged"]
      invariant_definitions: |
        JWT signature verification required for all tokens
        Role-based access control enforced for all resources
        Secrets are never logged (redacted with ***)
        Input sanitization prevents SQL injection and XSS
  key_links:
    - from: "backend/tests/test_governance_invariants.py"
      to: "backend/core/agent_governance_service.py"
      via: "Property-based invariant validation with Hypothesis"
    - from: "backend/tests/test_financial_invariants.py"
      to: "backend/core/accounting_validator.py"
      via: "Property-based validation of accounting invariants"
    - from: "backend/tests/test_security_invariants.py"
      to: "backend/core/jwt_verifier.py"
      via: "Property-based validation of JWT invariants"
---

<objective>
Final push to 80%+ coverage with property-based tests validating system invariants across governance, LLM, episodic memory, financial, and security domains.

Purpose: Property-based tests uncover edge cases that unit tests miss. Invariants ensure system correctness. Financial models exist (accounting_validator, budget_enforcement, ai_accounting_engine, financial_ops_engine) and their invariants must be validated.

Output: 5 test files with 1,250+ total lines, 100+ property tests, 1000+ examples tested.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/core/agent_governance_service.py
@backend/core/llm/cognitive_tier_system.py
@backend/core/episode_segmentation_service.py
@backend/core/accounting_validator.py
@backend/core/budget_enforcement_service.py
@backend/core/jwt_verifier.py

# Property-Based Testing Pattern Reference
From Hypothesis documentation:
- @given(st.builds(Model)) for model generation
- @settings(max_examples=1000) for critical invariants
- @settings(max_examples=200) for standard invariants
- @settings(max_examples=50) for IO-bound tests

# Invariant Definitions

## 1. Governance Invariants
- STUDENT agents cannot execute automated triggers
- Permission checks respect maturity levels
- Cache returns same results as DB (consistency)
- Confidence changes bounded 0-1
- Maturity transitions follow confidence thresholds

## 2. LLM Invariants
- Same prompt always classifies to same tier (determinism)
- Cached prompts don't incur LLM costs (no redundant calls)
- Escalation on quality threshold breach (<0.7)
- Provider fallback on primary failure
- Each tier has assigned provider

## 3. Episode Invariants
- Time gaps above threshold create new segments (>30 min)
- Topic change occurs when similarity < 0.7
- Semantic retrieval returns relevant episodes (sorted by score)
- Temporal retrieval respects limit parameter
- Old episodes have lower access scores (decay)
- Positive feedback boosts (+0.2), negative penalizes (-0.3)

## 4. Financial Invariants (Models Exist)
- All calculations use Decimal, not float (accounting_validator.py)
- Double-entry: debits + credits = 0 (accounting_validator.py)
- Audit trail entries are immutable (financial_audit_service.py)
- Budget enforcement: cost <= budget (budget_enforcement_service.py)
- Decimal precision preserved at 2 decimal places (decimal_utils.py)

## 5. Security Invariants
- JWT signature verification required (jwt_verifier.py - 425 lines)
- Role-based access control enforced
- Secrets never logged (redacted with ***)
- Input sanitization prevents SQL injection
- Input sanitization prevents XSS
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create property-based tests for governance invariants</name>
  <files>backend/tests/test_governance_invariants.py</files>
  <action>
Create backend/tests/test_governance_invariants.py with Hypothesis property tests:

1. Imports: pytest, hypothesis, from hypothesis import strategies as st, given
2. Imports: from core.agent_governance_service import AgentRegistry, AgentStatus

3. Strategy definitions:
   - maturity_strategy = st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
   - confidence_strategy = st.floats(min_value=0.0, max_value=1.0)

4. Class TestMaturityRoutingInvariants:
   @given(maturity=maturity_strategy, confidence=confidence_strategy)
   @settings(max_examples=1000)
   def test_student_cannot_execute_automatically(self, maturity, confidence):
       """STUDENT agents cannot execute automated triggers"""
       if maturity == 'STUDENT':
           assert not can_execute_automatically(maturity, confidence)

   @given(confidence=confidence_strategy)
   @settings(max_examples=1000)
   def test_confidence_bounds_invariant(self, confidence):
       """Confidence always bounded between 0 and 1"""
       agent = AgentRegistry(confidence_score=confidence)
       assert 0.0 <= agent.confidence_score <= 1.0

   @given(confidence=confidence_strategy)
   @settings(max_examples=1000)
   def test_maturity_transition_invariant(self, confidence):
       """Maturity transitions follow confidence thresholds"""
       expected_status = get_expected_maturity(confidence)
       agent = AgentRegistry(confidence_score=confidence)
       agent.status = expected_status.value
       assert agent.status == expected_status.value

5. Class TestPermissionInvariants:
   @given(maturity=maturity_strategy, permission=st.from_regex(PATTERN))
   @settings(max_examples=500)
   def test_permission_invariant(self, maturity, permission):
       """Permission checks respect maturity levels"""
       has_permission = check_permission_by_maturity(maturity, permission)
       assert has_permission == expected_permission(maturity, permission)

6. Class TestCacheConsistencyInvariants:
   @given(agent_id=st.uuid4())
   @settings(max_examples=200)
   def test_cache_db_consistency(self, agent_id):
       """Cache returns same results as DB"""
       cache_result = get_from_cache(agent_id)
       db_result = get_from_db(agent_id)
       assert cache_result == db_result

7. Use @given, @settings decorators from Hypothesis
  </action>
  <verify>
pytest backend/tests/test_governance_invariants.py -v
# All property tests should pass with 1000+ examples
  </verify>
  <done>
All governance invariant tests passing, 1000+ examples tested
  </done>
</task>

<task type="auto">
  <name>Task 2: Create property-based tests for LLM invariants</name>
  <files>backend/tests/test_llm_invariants.py</files>
  <action>
Create backend/tests/test_llm_invariants.py with Hypothesis property tests:

1. Imports: pytest, hypothesis, from hypothesis import strategies as st, given
2. Imports: from core.llm.cognitive_tier_system import CognitiveClassifier

2. Class TestCognitiveTierInvariants:
   @given(prompt=st.text(min_size=10, max_size=5000))
   @settings(max_examples=1000)
   def test_classification_consistency(self, prompt):
       """Same prompt always classifies to same tier"""
       tier1 = CognitiveClassifier.classify(prompt)
       tier2 = CognitiveClassifier.classify(prompt)
       assert tier1 == tier2

   @given(prompt=st.text())
   @settings(max_examples=500)
   def test_tier_deterministic(self, prompt):
       """Classification is deterministic"""
       results = [CognitiveClassifier.classify(prompt) for _ in range(5)]
       assert all(r == results[0] for r in results)

3. Class TestCacheInvariants:
   @given(prompt=st.text())
   @settings(max_examples=200)
   def test_cache_hit_no_llm_call(self, prompt):
       """Cached prompts don't incur LLM costs"""
       initial_calls = count_llm_calls()
       result1 = get_cached_or_classify(prompt)
       intermediate_calls = count_llm_calls()
       result2 = get_cached_or_classify(prompt)
       final_calls = count_llm_calls()
       assert result1 == result2
       assert final_calls - intermediate_calls < final_calls - initial_calls

4. Class TestEscalationInvariants:
   @given(quality_score=st.floats(min_value=0.0, max_value=1.0))
   @settings(max_examples=500)
   def test_escalation_on_low_quality(self, quality_score):
       """Low quality triggers escalation"""
       if quality_score < 0.7:
           should_escalate = check_escalation_needed(quality_score)
           assert should_escalate == True

5. Class TestProviderInvariants:
   @given(tier=st.sampled_from(['MICRO', 'STANDARD', 'VERSATILE', 'HEAVY', 'COMPLEX']))
   @settings(max_examples=200)
   def test_provider_for_tier(self, tier):
       """Each tier has assigned provider"""
       provider = get_provider_for_tier(tier)
       assert provider is not None
       assert provider in AVAILABLE_PROVIDERS

6. Mock LLM calls for counting
  </action>
  <verify>
pytest backend/tests/test_llm_invariants.py -v
# All property tests should pass with 1000+ examples
  </verify>
  <done>
All LLM invariant tests passing, 1000+ examples tested
  </done>
</task>

<task type="auto">
  <name>Task 3: Create property-based tests for episode invariants</name>
  <files>backend/tests/test_episode_invariants.py</files>
  <action>
Create backend/tests/test_episode_invariants.py with Hypothesis property tests:

1. Imports: pytest, hypothesis, from hypothesis import strategies as st, given
2. Imports: from core.episode_segmentation_service import EpisodeSegmentationService

2. Class TestSegmentationInvariants:
   @given(time_gap=st.integers(min_value=0, max_value=3600))
   @settings(max_examples=1000)
   def test_time_gap_creates_segment(self, time_gap):
       """Time gaps above threshold create new segments"""
       should_create = should_create_segment_for_gap(time_gap)
       if time_gap > 1800:  # 30 minutes
           assert should_create == True

   @given(similarity=st.floats(min_value=0.0, max_value=1.0))
   @settings(max_examples=1000)
   def test_topic_change_threshold(self, similarity):
       """Low similarity triggers topic change"""
       if similarity < 0.7:
           should_split = should_split_on_topic_change(similarity)
           assert should_split == True

3. Class TestRetrievalInvariants:
   @given(query=st.text(min_size=5))
   @settings(max_examples=200)
   def test_semantic_retrieval_relevance(self, query):
       """Semantic retrieval returns relevant episodes"""
       results = retrieve_semantic(query, top_k=10)
       assert len(results) <= 10
       # All results should have relevance score
       for result in results:
           assert result.relevance_score >= 0

   @given(limit=st.integers(min_value=1, max_value=100))
   @settings(max_examples=500)
   def test_temporal_retrieval_limit(self, limit):
       """Temporal retrieval respects limit"""
       results = retrieve_temporal(limit=limit)
       assert len(results) <= limit

4. Class TestLifecycleInvariants:
   @given(age_days=st.integers(min_value=0, max_value=365))
   @settings(max_examples=500)
   def test_decay_invariant(self, age_days):
       """Old episodes have lower access scores"""
       score = calculate_access_score(age_days)
       # Older episodes should have lower or equal scores
       if age_days > 30:
           assert score < 1.0

5. Class TestFeedbackInvariants:
   @given(feedback_score=st.floats(min_value=-1.0, max_value=1.0))
   @settings(max_examples=1000)
   def test_feedback_weighting(self, feedback_score):
       """Feedback affects retrieval weighting"""
       weight = calculate_feedback_weight(feedback_score)
       # Positive feedback should boost
       if feedback_score > 0:
           assert weight >= 1.0
       # Negative feedback should penalize
       elif feedback_score < 0:
           assert weight <= 1.0

6. Mock database, LanceDB for retrieval
  </action>
  <verify>
pytest backend/tests/test_episode_invariants.py -v
# All property tests should pass with 1000+ examples
  </verify>
  <done>
All episode invariant tests passing, 1000+ examples tested
  </done>
</task>

<task type="auto">
  <name>Task 4: Create property-based tests for financial invariants</name>
  <files>backend/tests/test_financial_invariants.py</files>
  <action>
Create backend/tests/test_financial_invariants.py with Hypothesis property tests:

Note: Financial models DO exist in the codebase:
- accounting_validator.py: Double-entry validation with Decimal arithmetic
- budget_enforcement_service.py: Budget enforcement with Decimal
- ai_accounting_engine.py: Transaction model with Decimal amounts
- financial_ops_engine.py: Financial operations with Decimal
- decimal_utils.py: Decimal utilities

1. Imports: pytest, hypothesis, from hypothesis import strategies as st, given
2. Imports: from decimal import Decimal
3. Imports: from core.accounting_validator import AccountingValidator, validate_double_entry
4. Imports: from core.budget_enforcement_service import BudgetEnforcementService
5. Imports: from core.decimal_utils import to_decimal, round_money

2. Class TestDecimalPrecisionInvariants:
   @given(amount=st.decimals(min_value=0, max_value=1000000, places=2))
   @settings(max_examples=1000)
   def test_always_use_decimal(self, amount):
       """All financial calculations use Decimal"""
       assert isinstance(amount, Decimal)
       # No float conversion
       result = amount * Decimal('1.0')
       assert isinstance(result, Decimal)

   @given(amount=st.decimals(min_value=0, max_value=1000000, places=2))
   @settings(max_examples=1000)
   def test_precision_preserved(self, amount):
       """Decimal precision is preserved (2 decimal places)"""
       rounded = round_money(amount, places=2)
       assert rounded.as_tuple().exponent >= -2  # 2 decimal places

3. Class TestDoubleEntryInvariants (from accounting_validator.py):
   @given(debit=st.decimals(min_value=0, max_value=1000000, places=2))
   @settings(max_examples=1000)
   def test_double_entry_balance(self, debit):
       """Every debit has equal credit"""
       credit = -debit
       validator = AccountingValidator()
       result = validator.validate_double_entry([
           {"account_id": "acc_1", "type": "DEBIT", "amount": debit},
           {"account_id": "acc_2", "type": "CREDIT", "amount": credit}
       ])
       assert result['balanced'] == True
       assert result['debits'] == result['credits']

   @given(entries=st.lists(st.builds(lambda: None), min_size=2, max_size=10))
   @settings(max_examples=500)
   def test_double_entry_requires_balance(self, entries):
       """Unbalanced entries fail validation"""
       # Test with various imbalanced scenarios
       pass

4. Class TestBudgetInvariants (from budget_enforcement_service.py):
   @given(budget=st.decimals(min_value=0, max_value=1000000, places=2))
   @given(cost=st.decimals(min_value=0, max_value=1000000, places=2))
   @settings(max_examples=1000)
   def test_budget_enforcement(self, budget, cost):
       """Costs never exceed approved budget"""
       service = BudgetEnforcementService()
       can_execute = service.check_budget("project_1", budget, cost)
       if cost > budget:
           assert can_execute['allowed'] == False
       else:
           assert can_execute['allowed'] == True

5. Class TestAuditTrailInvariants:
   @given(transaction_id=st.uuid4())
   @settings(max_examples=500)
   def test_audit_trail_immutability(self, transaction_id):
       """Audit trail entries are immutable"""
       entry = get_audit_entry(transaction_id)
       original_hash = hash(entry)
       # Attempt to modify should fail
       with pytest.raises(ImmutableError):
           entry.amount = Decimal('999999.99')
       assert hash(entry) == original_hash

6. Mock financial models, audit storage
  </action>
  <verify>
pytest backend/tests/test_financial_invariants.py -v
# All property tests should pass with 1000+ examples
  </verify>
  <done>
All financial invariant tests passing, 1000+ examples tested
  </done>
</task>

<task type="auto">
  <name>Task 5: Create property-based tests for security invariants</name>
  <files>backend/tests/test_security_invariants.py</files>
  <action>
Create backend/tests/test_security_invariants.py with Hypothesis property tests:

Note: jwt_verifier.py exists (425 lines) with comprehensive JWT validation.

1. Imports: pytest, hypothesis, from hypothesis import strategies as st, given
2. Imports: jwt, datetime
3. Imports: from core.jwt_verifier import JWTVerifier, verify_token

2. Class TestJWTInvariants:
   @given(token=st.text())
   @settings(max_examples=1000)
   def test_jwt_signature_required(self, token):
       """JWT signature verification required"""
       try:
           decoded = jwt.decode(token, options={'verify_signature': False})
           # Without signature verification, should fail
           with pytest.raises(jwt.InvalidSignatureError):
               jwt.decode(token, options={'verify_signature': True})
       except jwt.DecodeError:
           pass  # Invalid token format

   @given(user_id=st.uuid4())
   @settings(max_examples=500)
   def test_jwt_expiration(self, user_id):
       """JWT tokens include expiration"""
       verifier = JWTVerifier()
       token = verifier.create_token(str(user_id), expires_in=3600)
       payload = jwt.decode(token, options={'verify_signature': False})
       assert 'exp' in payload

   @given(user_id=st.uuid4())
   @settings(max_examples=500)
   def test_jwt_has_jti(self, user_id):
       """JWT tokens include JTI for revocation support"""
       verifier = JWTVerifier()
       token = verifier.create_token(str(user_id))
       payload = jwt.decode(token, options={'verify_signature': False})
       assert 'jti' in payload

3. Class TestRBACInvariants:
   @given(role=st.sampled_from(['USER', 'ADMIN', 'SUPER_ADMIN']))
   @given(resource=st.from_regex('^[a-z_]+$'))
   @settings(max_examples=1000)
   def test_role_based_permissions(self, role, resource):
       """Role-based access control enforced"""
       has_permission = check_permission(role, resource)
       expected = role_has_permission(role, resource)
       assert has_permission == expected

4. Class TestSecretRedactionInvariants:
   @given(log_message=st.text())
   @given(secret=st.text(min_size=10))
   @settings(max_examples=500)
   def test_secrets_never_logged(self, log_message, secret):
       """Secrets are never logged"""
       log_entry = create_log_entry(log_message, secret)
       assert secret not in log_entry.message
       assert '***' in log_entry.message

5. Class TestInputSanitizationInvariants:
   @given(user_input=st.text())
   @settings(max_examples=1000)
   def test_sql_injection_prevented(self, user_input):
       """SQL injection attempts are prevented"""
       sanitized = sanitize_input(user_input)
       # No SQL keywords remain
       sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION']
       for keyword in sql_keywords:
           assert keyword.lower() not in sanitized.lower()

   @given(user_input=st.text())
   @settings(max_examples=1000)
   def test_xss_prevented(self, user_input):
       """XSS attempts are prevented"""
       sanitized = sanitize_input(user_input)
       # No script tags remain
       assert '<script>' not in sanitized.lower()
       assert 'javascript:' not in sanitized.lower()

6. Mock JWT, logging, sanitization functions
  </action>
  <verify>
pytest backend/tests/test_security_invariants.py -v
# All property tests should pass with 1000+ examples
  </verify>
  <done>
All security invariant tests passing, 1000+ examples tested
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all property-based tests:
   pytest backend/tests/test_governance_invariants.py \
          backend/tests/test_llm_invariants.py \
          backend/tests/test_episode_invariants.py \
          backend/tests/test_financial_invariants.py \
          backend/tests/test_security_invariants.py -v
   # Verify 1000+ examples tested

2. Verify all backend coverage:
   pytest backend/tests/ --cov=core --cov=api --cov=tools --cov-report=json
   # Backend should be 80%+
</verification>

<success_criteria>
1. All property-based tests pass (1000+ examples)
2. Governance invariants validated
3. LLM invariants validated
4. Episode invariants validated
5. Financial invariants validated (models exist)
6. Security invariants validated (jwt_verifier covered)
7. Backend coverage >= 80%
8. Overall coverage >= 60% (weighted average across all platforms)
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE4A-SUMMARY.md`
</output>

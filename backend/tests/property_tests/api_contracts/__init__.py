"""
API Contract Property-Based Tests

Tests API contract invariants using Hypothesis:
- Malformed JSON handling (returns 400/422, not 500)
- Oversized payload rejection (returns 413, not OOM/crash)
- Response schema validation (conforms to OpenAPI)
- API contract fuzzing for robustness

These tests prevent crashes from malformed input and ensure
API responses conform to contract specifications.
"""

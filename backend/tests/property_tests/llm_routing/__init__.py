"""
Property-based tests for LLM routing subsystem.

Tests validate invariants for:
- Cognitive tier system (token count → tier mapping)
- Cache-aware routing (cached prompts skip classification)
- Provider routing consistency (same prompt → same provider)

These tests ensure LLM routing is deterministic, cost-effective, and correct.
"""

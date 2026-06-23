"""
TDD regression tests for Round 26 - Memory/GraphRAG auth.

Critical: promote_agent, delete_memory, create_entity_type all unauthenticated.
"""

from __future__ import annotations

import inspect


def _has_auth(func) -> bool:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty: continue
        if hasattr(p.default, "dependency"):
            deps.append(getattr(p.default.dependency, "__name__", "") or "")
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    markers = ("get_current_user","verify_token","require_user","require_auth",
               "require_permission","require_governance","get_current_active_user","require_admin")
    return any(any(m in d for m in markers) for d in deps)


class TestMemoryRoutesRequireAuth:
    def _load(self):
        from api import memory_routes as mod; return mod

    def test_store_memory_requires_auth(self):
        assert _has_auth(self._load().store_memory), "store_memory has no auth"

    def test_delete_memory_requires_auth(self):
        assert _has_auth(self._load().delete_memory), "delete_memory has no auth — anyone can wipe memories"


class TestEpisodeRoutesRequireAuth:
    def _load(self):
        from api import episode_routes as mod; return mod

    def test_promote_agent_requires_auth(self):
        assert _has_auth(self._load().promote_agent), "promote_agent has no auth — privilege escalation"

    def test_list_episodes_requires_auth(self):
        assert _has_auth(self._load().list_episodes), "list_episodes has no auth — memory enumeration"


class TestGraphRagRoutesRequireAuth:
    def _load(self):
        from api import graphrag_routes as mod; return mod

    def test_add_entity_requires_auth(self):
        assert _has_auth(self._load().add_entity), "add_entity has no auth — graph poisoning"

    def test_ingest_document_requires_auth(self):
        assert _has_auth(self._load().ingest_document), "ingest_document has no auth"


class TestEntityTypeRoutesRequireAuth:
    def _load(self):
        from api import entity_type_routes as mod; return mod

    def test_create_entity_type_requires_auth(self):
        assert _has_auth(self._load().create_entity_type), "create_entity_type has no auth — schema injection"

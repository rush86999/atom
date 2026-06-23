"""
TDD regression tests for Round 21 bug hunt - Data ingestion & compliance.

Covers:
- BUG R21-1: accounting/export_service.py CSV injection (formulas not sanitized)
- BUG R21-2: document_ingestion_routes /parse has NO auth + no file size limit
- BUG R21-3: document_ingestion_routes /documents has NO auth (cross-tenant data)
- BUG R21-4: data_ingestion_routes /usage, /sync-status, /available-integrations NO auth
"""

from __future__ import annotations

import inspect


def _route_auth_dependencies(func) -> list[str]:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            name = getattr(p.default.dependency, "__name__", "") or p.default.dependency.__class__.__name__
            deps.append(name)
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    return deps


def _has_auth_dependency(func) -> bool:
    deps = _route_auth_dependencies(func)
    markers = ("get_current_user", "verify_token", "require_user", "require_auth",
               "get_current_active_user", "require_admin", "require_permission",
               "require_governance")
    return any(any(m in d for m in markers) for d in deps)


# ---------------------------------------------------------------------------
# BUG R21-1: CSV injection in export_service
# ---------------------------------------------------------------------------


class TestExportServiceCsvInjectionProtection:
    """Financial CSV export must sanitize formula-triggering characters."""

    def test_export_general_ledger_sanitizes_cells(self):
        from accounting import export_service as mod

        src = inspect.getsource(mod)
        # The buggy code writes entry.description / tx.description directly to CSV.
        # The fix must apply a sanitizer (prefix '= + - @' with a quote or tab).
        assert (
            "_sanitize_csv_cell" in src
            or "sanitize_csv" in src
            or "csv_injection" in src.lower()
            or "def _csv_safe" in src
        ), (
            "export_general_ledger_csv writes unsanitized user input to CSV — "
            "CSV injection via =cmd|... formulas executes code on accountant's workstation"
        )

    def test_sanitizer_handles_formula_prefix(self):
        from accounting import export_service as mod

        # If the sanitizer exists, it must neutralize = + - @ prefixes
        if hasattr(mod, "_sanitize_csv_cell"):
            f = mod._sanitize_csv_cell
            for payload in ("=cmd|' /C calc'!A0", "+1+1", "-1+1", "@SUM(A1)"):
                result = f(payload)
                assert not result.startswith(("=", "+", "-", "@")), (
                    f"CSV sanitizer failed to neutralize {payload!r} → {result!r}"
                )
        elif hasattr(mod, "_csv_safe"):
            f = mod._csv_safe
            for payload in ("=cmd|' /C calc'!A0", "+1+1", "-1+1", "@SUM(A1)"):
                result = f(payload)
                assert not result.startswith(("=", "+", "-", "@"))
        else:
            # If sanitizer not exposed as module function, skip (previous test guards existence)
            pass


# ---------------------------------------------------------------------------
# BUG R21-2: document_ingestion /parse — auth + size limit
# ---------------------------------------------------------------------------


class TestDocumentIngestionParseRequiresAuth:
    """/parse must require auth AND enforce a file size limit."""

    def test_parse_document_file_requires_auth(self):
        from api import document_ingestion_routes as mod

        assert _has_auth_dependency(mod.parse_document_file), (
            "POST /parse has no auth — unauthenticated document parsing / DoS"
        )

    def test_parse_document_file_enforces_size_limit(self):
        from api import document_ingestion_routes as mod

        src = inspect.getsource(mod.parse_document_file)
        # Must check file size before reading (MAX_FILE_SIZE / len(content) / file.size)
        assert (
            "MAX_FILE_SIZE" in src
            or "max_file_size" in src
            or "MAX_UPLOAD" in src
            or "file.size" in src
            or "content_size" in src
            or "len(content)" in src
        ), (
            "parse_document_file reads entire upload into memory with no size check — "
            "OOM denial of service via large file upload"
        )


# ---------------------------------------------------------------------------
# BUG R21-3: document_ingestion /documents — auth
# ---------------------------------------------------------------------------


class TestDocumentIngestionListRequiresAuth:
    """/documents must require auth (currently cross-tenant data exposure)."""

    def test_list_ingested_documents_requires_auth(self):
        from api import document_ingestion_routes as mod

        assert _has_auth_dependency(mod.list_ingested_documents), (
            "GET /documents has no auth — cross-tenant document enumeration"
        )


# ---------------------------------------------------------------------------
# BUG R21-4: data_ingestion_routes — auth
# ---------------------------------------------------------------------------


class TestDataIngestionRoutesRequireAuth:
    """data_ingestion_routes must require auth on info-disclosing endpoints."""

    def test_get_integration_usage_requires_auth(self):
        from api import data_ingestion_routes as mod

        assert _has_auth_dependency(mod.get_integration_usage), (
            "GET /usage has no auth — integration usage data leaked"
        )

    def test_get_sync_status_requires_auth(self):
        from api import data_ingestion_routes as mod

        assert _has_auth_dependency(mod.get_sync_status), (
            "GET /sync-status/{id} has no auth — sync status leaked"
        )

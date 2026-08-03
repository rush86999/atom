"""Data analysis package — dataset management + agent tools.

Provides DuckDB-backed dataset loading/caching/querying for agent-driven
data analysis. Datasets are loaded once, cached by name, and referenced
across agent turns without re-loading (avoids re-sending large files
through LLM context every turn).

Evidence: ExperiencedDevs consensus and n8n community both conclude LLMs
should orchestrate code against datasets, not ingest raw files into
context. DuckDB Lab's "DuckDB as agent brain" pattern: dataset referenced
by name across turns; DuckDB holds the connection.

DuckDB handles out-of-core datasets (larger than RAM) per codecentric
benchmarks. Falls back to pandas when DuckDB is unavailable.
"""
from __future__ import annotations

from core.data.dataset_manager import DatasetManager, get_dataset_manager

__all__ = ["DatasetManager", "get_dataset_manager"]

# Token Compression

Atom compresses terminal/tool output and deduplicates cross-turn content to reduce token usage — saving 15-95% on verbose build logs without touching structured business data.

## Evidence basis

These features were designed based on multiple independent research sources:

- **Observation compression is safe; prompt compression is dangerous.** [ICML 2025](https://arxiv.org/html/2505.19433v1) shows agentic tasks degrade sharply with lossy compression. [arXiv:2510.22963](https://arxiv.org/html/2510.22963v2) shows compression can drop critical tokens. [ACM LLMLingua-2 eval](https://dl.acm.org/doi/10.1145/3816713.3818806) shows compression "changes failure modes."
- **Exact-match dedup is categorically safe** — zero information loss. Semantic/Caveman compression is **excluded**.
- **Tool-output compression (RTK pattern)** is validated by [TACO (arXiv)](https://arxiv.org/html/2604.19572v2), [Morph Context Compaction](https://morphllm.com/context-compaction), [Compression Survey (preprints.org)](https://www.preprints.org/manuscript/202605.2065).

## The critical safety boundary: structured-data guard

Atom is a **business automation platform that also does coding**. Prompts carry financial records, CRM data, SQL results, and API responses. **Lossy compression of these would silently corrupt business workflows.**

The RTK engine detects structured data and **never compresses it**:
- JSON objects/arrays → skipped
- SQL queries → skipped
- XML documents → skipped
- Fenced code blocks (```...```) → skipped

Only **free-form log/terminal text** is compressed. This is verified by tests including a `test_financial_data_1_cent_difference_preserved` test that confirms a 1-cent difference in an invoice total is never deduped.

## RTK Engine (Run/Tool/Kit)

Compresses terminal/build/test log output via a composable pipeline:

| Engine | What it does |
|--------|-------------|
| ANSI stripping | Removes escape sequences and control characters |
| Repeated-line collapse | 3+ consecutive identical lines → `[N repeated lines]` |
| Test-runner detection | Jest/Vitest/Pytest/Cargo/Go/Docker — keeps failures/warnings/summaries, drops passing noise |
| Git-diff context collapse | Keeps `+`/`-` lines, collapses context |
| Length cap | Last-resort truncation with marker |

Measured **85% savings** on verbose build logs in smoke tests.

### Integration
- `byok_handler.generate_response`: compresses prompt before SDK call
- `generic_agent` ReAct loop: compresses observation before execution_history

### Configuration
| Env var | Default | Effect |
|---------|---------|--------|
| `ATOM_COMPRESSION_ENABLED` | `true` | Master gate |
| `COMPRESS_RTK_ENABLED` | `true` | RTK engine gate |
| `COMPRESS_RTK_MAX_SECTION_CHARS` | `8000` | Max chars per section before truncation |

## Session-Dedup (exact-match only)

Replaces byte-identical repeated text across turns with reference markers. Prevents re-sending unchanged context (system prompts, tool definitions, prior outputs).

**Exact-match only** (SHA-256 hash). No rewriting, no semantic compression. A 1-cent difference in a financial figure is preserved.

### Integration
- **Write-side:** `_update_session` indexes each turn's content hashes
- **Read-side:** history window deduped before building messages

### Configuration
| Env var | Default | Effect |
|---------|---------|--------|
| `COMPRESS_SESSION_DEDUP_ENABLED` | `true` | Session-dedup gate |
| `COMPRESS_DEDUP_MIN_CHUNK` | `200` | Minimum chunk size (chars) to index |
| `COMPRESS_DEDUP_MAX_INDEX` | `500` | Max entries per session (LRU eviction) |

## What's NOT included (evidence-based exclusions)

- **Caveman/semantic prose compression** — lossy, changes failure modes (ICML 2025)
- **LLMLingua-2 ONNX classifier** — requires ML dependency; RTK covers the high-value case
- **CCR content-addressed references** — complex, lower priority

# Data Analysis & Predictive Modeling

Atom agents can load datasets, run analysis code in the sandbox, query/summarize data, and build predictive models — all without ingesting raw data into LLM context. The agent generates code; the sandbox executes it safely; results flow back structured.

## Evidence basis

- [DABstep benchmark (arXiv 2506.23719)](https://arxiv.org/html/2506.23719v1): code-interpreter is the SOTA pattern for multi-step data analysis (450+ tasks).
- [DS-STAR (Google Research)](https://research.google/blog/ds-star-a-state-of-the-art-versatile-data-science-agent/): code execution + self-debugging raises accuracy from 41%→45%.
- [DuckDB vs Pandas (codecentric)](https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-dataframe-libraries): DuckDB outperforms pandas on large analytical workloads, handles larger-than-RAM datasets.
- [ExperiencedDevs consensus](https://www.reddit.com/r/ExperiencedDevs/comments/1lvlvw3/): LLMs should orchestrate code, not ingest raw files.
- [IBM Developer](https://developer.ibm.com/articles/agentic-ml-tasks/): classical ML via tool-calling, not raw LLM forecasting.
- [DeepLearning.AI community](https://community.deeplearning.ai/t/use-of-llm-for-any-forecasting-scenarios/690668): LLMs predict tokens, not numbers — must use classical ML.

## Architecture

```
Agent (LLM) generates code
  → DatasetManager provides cached DataFrame as 'df'
    → Sandbox runtime (Docker/E2B/Firecracker) executes code
      → AST tripwires + egress proxy + resource caps enforce safety
        → Results (JSON) flow back to agent
```

### Dataset Manager (`core/data/dataset_manager.py`)
- Loads CSV/Excel/JSON/Parquet + inline JSON
- Caches by name, **session-scoped** (isolation between sessions)
- DuckDB backend when available (out-of-core, larger-than-RAM datasets)
- Pandas fallback when DuckDB is not installed
- `query()`, `head()`, `describe()`, `list_datasets()`, `clear_session()`

### Agent Tools

| Tool | Maturity | Description |
|------|----------|-------------|
| `load_dataset` | INTERN | Load CSV/Excel/JSON/Parquet, cache by name |
| `analyze_data` | INTERN | Run Python code in sandbox against cached dataset |
| `query_data` | INTERN | SQL or pandas expression against cached dataset |
| `describe_data` | INTERN | Summary statistics (pandas describe) |
| `list_datasets` | INTERN | List loaded datasets in session |
| `forecast` | **SUPERVISED** | Time-series forecasting (linear/MA/exponential) |
| `run_model` | **SUPERVISED** | Regression/classification (sklearn) |

### Predictive Modeling (governed)

Forecasting and modeling tools require **SUPERVISED** maturity and include a governance notice in results: *"Review before using for business decisions."*

Methods:
- **Forecast**: linear regression, moving average, exponential smoothing (statsmodels when available)
- **Model**: LinearRegression (regression), RandomForestClassifier (classification)

Returns: model metrics (R², MSE, MAE, accuracy, feature importance, coefficients), not raw predictions alone.

## Security

All code execution goes through the existing sandbox runtime:
- **AST tripwires**: blocks `os`/`subprocess`/`socket` imports, `eval`/`exec`, `__subclasses__` traversal
- **Egress proxy**: blocks non-allowlisted network access (prevents data exfiltration)
- **Resource caps**: memory, CPU, timeout (30s for data analysis)
- **Network isolation**: `--network none` in Docker
- **Filesystem scope**: read/write only within designated roots

Evidence: [Modal](https://modal.com/resources/run-untrusted-code-safely), [Trend Micro](https://www.trendmicro.com/vinfo/us/security/news/cybercrime-and-digital-threats/unveiling-ai-agent-vulnerabilities-code-execution), [arXiv 2504.00018](https://arxiv.org/html/2504.00018v1).

## Why not native LLM forecasting?

[DeepLearning.AI community consensus](https://community.deeplearning.ai/t/use-of-llm-for-any-forecasting-scenarios/690668): LLMs are language models that predict the next token, not numerical outcomes. They excel at *orchestrating* classical ML tools (generating sklearn code, interpreting results) but should not be used as native forecasters. Atom's `forecast` and `run_model` tools use sklearn/statsmodels — the LLM generates the code, the sandbox runs it.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Sandbox timeout | 30s | Max execution time for data analysis code |
| DuckDB | auto-detected | Used when available for out-of-core datasets |
| Dataset scope | per-session | Datasets cleared on session end |

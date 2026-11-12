# COMPAT-01 — main CI quickstart install/run (2026-11-12)

Bounded evidence for the documented CPython 3.11–3.13 quickstart path on
Linux. It does not qualify Python 3.14, non-Linux platforms, or full-app
behavior.

## Run identity

| Field | Value |
|---|---|
| Workflow | [`CI`](https://github.com/rush86999/atom/actions/runs/43155871096) (`.github/workflows/ci.yml`) |
| Run | `43155871096`, run 2797, attempt 1 |
| Event | `push` to `main` |
| Head | `d1be5e816a83c095bbf7894471797bbf3c241d20` |
| Tree | `37bdfe2d2a490c2d2da23d0bbafebf497758c457` |
| Window | 2026-11-12 04:36:07–06:06:33 UTC |
| Result | `success`; all 11 jobs passed |

The `quickstart-install (3.11)`, `(3.12)` and `(3.13)` matrix jobs, the
aggregate `quickstart` job, and the separate `full-app-boots` job all
succeeded. The other jobs (`backend-core`, `backend-oracle`, `backend-tests`,
`e2e-journey`, `frontend-typecheck`, `syntax-gate`) also succeeded.

## What each matrix leg proved

Each Python matrix job ran on `ubuntu-latest` with Node 20:

1. **Fresh installation directories:** `backend/venv` and
   `frontend-nextjs/node_modules` were absent before setup.
2. **`make setup`:** the real `scripts/quickstart.sh` bootstrap completed,
   creating the backend virtualenv, installing backend and frontend
   dependencies, generating `backend/.env`, and generating
   `frontend-nextjs/.env.local`.
3. **Installed-storage binary smoke:** with `HF_HUB_OFFLINE=1` and
   `TRANSFORMERS_OFFLINE=1`, the newly installed venv imported NumPy,
   PyArrow, LanceDB and FastEmbed, then wrote and read one synthetic vector
   row in a temporary LanceDB store. No application database, embedding model,
   provider or user data was used.
4. **Setup artifacts:** `backend/venv`, `backend/.env` containing
   `SECRET_KEY=`, `frontend-nextjs/node_modules` and
   `frontend-nextjs/.env.local` all existed.
5. **Boot from the generated environment:** the job activated the new venv
   and started `main_api_app` with uvicorn; `/alive` returned HTTP success
   within the 60-second polling window.

The aggregate `quickstart` job requires the whole matrix result to be
`success`. The separate `full-app-boots` job also passed on Python 3.11, using
requirements-installed dependencies rather than the generated quickstart env.

## Boundaries

- **Linux CI only.** Matrix coverage is `ubuntu-latest`; Windows, macOS, ARM,
  Docker, non-CI hosts and alternate package indexes were not exercised.
- **Documented Python range only.** The matrix is 3.11, 3.12 and 3.13. Python
  3.14 and later are outside the documented range; `scripts/quickstart.sh`
  explicitly rejects 3.14 with the `torch<3` wheel message. "Python 3.11+" in
  the claim name must not be read as 3.14 support.
- **Backend boot probe only.** `/alive` proves the app imports and serves a
  health response from the generated env; it does not prove browser login,
  onboarding, workflows, application data, or a full user journey.
- **No persistence or external services.** No process restart, PostgreSQL,
  live provider/model, send, spend or deployment action was part of this run.
- **Storage smoke, not a full ABI matrix.** The storage step imports the
  installed stack and performs one LanceDB write/read; it does not construct
  an embedding model or test every storage path.

The historical 2026-11-07 requirement audit, its COMPAT-01 guard-only finding,
the 143 claim records, the 18 goal-map rows and all historical scores remain
unchanged. This packet is current bounded evidence, not a rewrite of that
snapshot.

## Source binding at `d1be5e816`

| File | Git blob | SHA-256 |
|---|---|---|
| `.github/workflows/ci.yml` | `498757bfcc905cdec4b07a67c7ee457615246d51` | `3530efc99cab0ed17598e459cd7bd69a5c50783533fade98001048c1e06b7ef9` |
| `scripts/quickstart.sh` | `3c700558a1fb3502a7adcf41da459665de32a239` | `3bf727ac031a8c42f971b8fb0ee12c414e29fe62a3919ece3f0b537d041cda71` |
| `scripts/ci/verify_quickstart_storage.py` | `b4db9aa6dbace05b88536da8a46b6ee28c690b7b` | `58a6b58db56c5cd8ac67e20cd527b40af7e395148bdd61880ed61a336bb29f67` |
| `Makefile` | `7cb186d7e42ae83afc988a641453f27ac36af647` | `18ca140069290ed8ac1c1df43537c3945b6a3b2912233454fe49f914a67c65b2` |

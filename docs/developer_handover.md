# Developer Handover & Status Report

**Date:** November 19, 2025
**Project:** Atom (Advanced Task Orchestration & Management)

## 1. Project Overview
Atom is an AI-powered automation platform featuring a Next.js frontend (wrapped in Tauri for desktop) and a Python FastAPI backend. It integrates with various services (Asana, Slack, etc.) and uses local/remote LLMs (DeepSeek, OpenAI, etc.) for natural language understanding and workflow generation.

## 2. Current Status

2.  **Frontend:**
    ```bash
    cd atom/frontend-nextjs
    npm run dev
    ```
    Runs on `http://localhost:3000`.

3.  **Desktop (Tauri):**
    ```bash
    cd atom
    npm run tauri dev
    ```

## 6. Known Issues
- **Git Divergence:** Local `main` is ahead/diverged from remote. Needs careful sync.
- **Routing:** Some backend endpoints might be shadowed by others if mounted with same prefix.

## 7. Documentation
- `task.md`: Detailed task tracking.
- `app_readiness_plan.md`: Specific plan for current phase.
- `implementation_plan.md`: Technical design docs.

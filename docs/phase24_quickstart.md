# Phase 24 Quick Start Guide

## What Was Implemented

### 1. Chat-Based Workflow Creation
Use natural language to create workflows through the chat interface.

**Example Commands:**
```
"Create a workflow to send daily reports"
"Create a workflow to notify Slack when a new lead arrives"
"List my workflows"
```

**Backend Endpoint:** `POST /api/workflow-agent/chat`

### 2. Visual Workflow Scheduling
Schedule workflows using a visual interface with three modes:

- **Interval**: Run every X days/hours/minutes
- **Cron**: Advanced scheduling (presets or custom expressions)
- **Date**: One-time execution at specific date/time

**Location:** Workflow Editor → Schedule Tab (4th tab)

## How to Test

### Start Backend Server
```bash
cd /home/developer/projects/atom/backend
python main_api_app.py
# Server runs on http://localhost:8000
```

### Start Frontend
```bash
cd /home/developer/projects/atom/frontend-nextjs
npm run dev
# Frontend runs on http://localhost:3000
```

### Test Workflow Creation via Chat
```bash
# Test the chat endpoint directly
curl -X POST http://localhost:8000/api/workflow-agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a workflow to send an email to alerts@company.com every hour",
    "user_id": "test_user",
    "session_id": "test_session",
    "conversation_history": []
  }'
```

### Test Scheduling UI
1. Open frontend at `http://localhost:3000`
2. Navigate to Workflow Editor (Automations section)
3. Create or open a workflow
4. Click the "Schedule" tab
5. Try each scheduling mode:
   - Interval: Set to run every 30 minutes
   - Cron: Use preset "Daily at 9 AM" or custom expression
   - Date: Schedule for tomorrow at a specific time

### Verify Scheduled Jobs
```bash
# Check all scheduled jobs
curl http://localhost:8000/api/v1/scheduler/jobs

# Or view in UI: Workflow Editor → Schedule tab → Scheduled Jobs table
```

## Key Files

### Backend
- `backend/core/workflow_agent_endpoints.py` - Chat endpoint with AI workflow creation
- `backend/ai/workflow_scheduler.py` - Scheduler engine (fixed imports)
- `backend/core/workflow_endpoints.py` - Workflow CRUD + scheduling APIs

### Frontend
- `frontend-nextjs/components/Automations/WorkflowScheduler.tsx` - Scheduling UI (NEW)
- `frontend-nextjs/components/Automations/WorkflowEditor.tsx` - Main editor with Schedule tab

### Test Scripts
- `backend/verify_scheduler.py` - Tests scheduler execution
- `backend/test_chat_endpoint.py` - Tests chat workflow creation
- `backend/test_engine_deep.py` - Tests AutomationEngine

## Git Status

**Commits Pushed:**
- `6082b110` - feat: Complete Phase 24 - Chat-based Workflow Management & Scheduling UI
- `2b104483` - chore: Remove corrupt token.json file

**Remote:** `origin/main` (updated)

## What's Next?

### Immediate Testing Priority
1. Verify chat creates valid workflows
2. Test each scheduling mode (interval, cron, date)
3. Confirm scheduled workflows execute on time
4. Check execution history shows scheduled runs

### Potential Phase 25 Features
- **Chat-based Scheduling**: "Schedule this workflow daily at 9am" via chat
- **Workflow Templates**: Pre-built workflows for common tasks
- **Analytics Dashboard**: Metrics on workflow execution, success rate, time savings
- **Advanced Conditionals**: If/else logic in workflows
- **Workflow Versioning**: Track and rollback workflow changes

## Known Items

### Untracked Files (Can be ignored or added to .gitignore)
- `backend/reproduce_issue.py` - Test script
- `backend/verify_scheduler.py` - Test script
- `executions.json` - Runtime execution data
- `jobs.sqlite` - Scheduler persistence

### Configuration Required
- Ensure AI provider API keys are set (DEEPSEEK_API_KEY, etc.)
- OAuth tokens needed for Gmail/Slack integrations
- See `docs/missing_credentials_guide.md` for details

## Support

**Documentation:**
- `docs/developer_handover.md` - Complete project status
- `docs/missing_credentials_guide.md` - Credential setup
- Walkthrough artifact - Detailed implementation notes

**Questions?** Check the developer handover doc or review the implementation plan artifact.

# Mobile Workflow API Usage Guide

## Overview

The Mobile Workflow API provides optimized endpoints for mobile devices to interact with workflows. All endpoints are prefixed with `/api/mobile/workflows`.

## Key Features

1. **Synchronous & Asynchronous Execution**
   - Execute workflows synchronously (wait for completion) or asynchronously (background)
   - Real-time progress tracking

2. **Step-Level Execution Tracking**
   - Monitor individual step status
   - View execution timing and errors

3. **Workflow Cancellation**
   - Cancel running workflows
   - Proper cleanup and status updates

4. **Execution Logging**
   - Query execution logs
   - Filter by log level

## API Endpoints

### 1. List Workflows (Mobile Optimized)
```http
GET /api/mobile/workflows?status=active&limit=20&offset=0
```

**Response:**
```json
[
  {
    "id": "workflow_123",
    "name": "Daily Report Generator",
    "description": "Generates daily reports",
    "category": "automation",
    "status": "active",
    "created_at": "2026-02-01T10:00:00Z",
    "last_execution": "2026-02-01T15:30:00Z",
    "execution_count": 45,
    "success_rate": 95.5,
    "tags": ["reports", "automation"]
  }
]
```

### 2. Get Workflow Details
```http
GET /api/mobile/workflows/{workflow_id}
```

### 3. Trigger Workflow Execution

#### Asynchronous (Non-blocking)
```http
POST /api/mobile/workflows/trigger?user_id=user_123
Content-Type: application/json

{
  "workflow_id": "workflow_123",
  "synchronous": false,
  "parameters": {
    "report_type": "daily",
    "recipients": ["admin@example.com"]
  }
}
```

**Response:**
```json
{
  "execution_id": "exec_20260201_153000_123456",
  "status": "started",
  "message": "Workflow execution started",
  "workflow_id": "workflow_123"
}
```

#### Synchronous (Wait for completion)
```http
POST /api/mobile/workflows/trigger?user_id=user_123
Content-Type: application/json

{
  "workflow_id": "workflow_123",
  "synchronous": true,
  "parameters": {
    "report_type": "daily"
  }
}
```

**Response (after completion):**
```json
{
  "execution_id": "exec_20260201_153000_123456",
  "status": "completed",
  "message": "Workflow completed",
  "workflow_id": "workflow_123"
}
```

### 4. Get Execution Details
```http
GET /api/mobile/workflows/executions/{execution_id}
```

**Response:**
```json
{
  "id": "exec_20260201_153000_123456",
  "workflow_id": "workflow_123",
  "workflow_name": "Daily Report Generator",
  "status": "running",
  "started_at": "2026-02-01T15:30:00Z",
  "completed_at": null,
  "duration_seconds": null,
  "triggered_by": "user_123",
  "current_step": 2,
  "total_steps": 5,
  "progress_percentage": 40,
  "error_message": null,
  "recent_logs": [
    {
      "id": "log_123",
      "level": "INFO",
      "message": "Step 2 completed successfully",
      "timestamp": "2026-02-01T15:31:00Z",
      "step_id": "step_2"
    }
  ]
}
```

### 5. Get Execution Steps
```http
GET /api/mobile/workflows/{workflow_id}/executions/{execution_id}/steps
```

**Response:**
```json
{
  "execution_id": "exec_20260201_153000_123456",
  "current_step": 2,
  "total_steps": 5,
  "progress_percentage": 40,
  "steps": [
    {
      "step_id": "step_1",
      "step_name": "Validate Input",
      "step_type": "action",
      "sequence_order": 1,
      "status": "completed",
      "started_at": "2026-02-01T15:30:00Z",
      "completed_at": "2026-02-01T15:30:05Z",
      "duration_ms": 5000,
      "error_message": null
    },
    {
      "step_id": "step_2",
      "step_name": "Generate Report",
      "step_type": "action",
      "sequence_order": 2,
      "status": "running",
      "started_at": "2026-02-01T15:30:05Z",
      "completed_at": null,
      "duration_ms": null,
      "error_message": null
    }
  ]
}
```

### 6. Cancel Execution
```http
POST /api/mobile/workflows/executions/{execution_id}/cancel?user_id=user_123
```

**Response:**
```json
{
  "message": "Execution cancelled successfully",
  "execution_id": "exec_20260201_153000_123456"
}
```

### 7. Get Execution Logs
```http
GET /api/mobile/workflows/{workflow_id}/executions/{execution_id}/logs?level=ERROR&limit=50
```

### 8. Search Workflows
```http
GET /api/mobile/workflows/search?query=report&limit=20
```

## Step Status Values

- `pending` - Step is waiting to execute
- `running` - Step is currently executing
- `completed` - Step completed successfully
- `failed` - Step failed with error
- `skipped` - Step was skipped (condition not met)

## Execution Status Values

- `PENDING` - Waiting to start
- `RUNNING` - Currently executing
- `COMPLETED` - Finished successfully
- `FAILED` - Failed with error
- `PAUSED` - Paused (missing input)
- `CANCELLED` - Cancelled by user

## Best Practices

1. **Use Asynchronous Execution for Long Workflows**
   - Set `synchronous: false` for workflows that take > 30 seconds
   - Poll the execution status endpoint for updates

2. **Use Synchronous Execution for Quick Workflows**
   - Set `synchronous: true` for workflows that complete in < 30 seconds
   - Get immediate result without polling

3. **Monitor Progress**
   - Use the steps endpoint to track individual step progress
   - Calculate progress percentage from completed/total steps

4. **Handle Timeouts**
   - Synchronous execution has a 5-minute timeout
   - Request will return with status "timeout" if exceeded

5. **Error Handling**
   - Check `error_message` field in execution details
   - Check `error_message` field in individual steps
   - Query logs with `level=ERROR` for detailed error information

## Mobile UI Considerations

1. **Show Progress Indicators**
   - Display progress percentage from execution details
   - Show current step number (e.g., "Step 2 of 5")

2. **Refresh Status Periodically**
   - Poll every 2-5 seconds for running executions
   - Stop polling when status is completed/failed/cancelled

3. **Provide Cancellation Option**
   - Show cancel button only for running executions
   - Verify user is the one who triggered the execution

4. **Display Step Errors**
   - Highlight failed steps in red
   - Show error message for troubleshooting

## Example Implementation Flow

```python
# 1. Trigger workflow asynchronously
response = await client.post(
    "/api/mobile/workflows/trigger?user_id=user_123",
    json={
        "workflow_id": "daily_report",
        "synchronous": False,
        "parameters": {"report_type": "daily"}
    }
)
execution_id = response.json()["execution_id"]

# 2. Poll for status (every 3 seconds)
while True:
    response = await client.get(
        f"/api/mobile/workflows/executions/{execution_id}"
    )
    data = response.json()

    # Update UI with progress
    print(f"Progress: {data['progress_percentage']}%")

    # Check if complete
    if data["status"] in ["completed", "failed", "cancelled"]:
        break

    await asyncio.sleep(3)

# 3. Get detailed steps
response = await client.get(
    f"/api/mobile/workflows/daily_report/executions/{execution_id}/steps"
)
steps = response.json()["steps"]

# 4. Display results
for step in steps:
    print(f"{step['step_name']}: {step['status']}")
```

## Testing

Run the test suite:
```bash
pytest tests/test_mobile_workflows_simple.py -v
```

Expected output:
```
6 passed in 0.38s
```

# Atom API Documentation

## Overview

The Atom API provides a comprehensive RESTful interface for managing all aspects of the personal assistant platform. This documentation covers all available endpoints, authentication methods, and usage examples.

## Base URL

```
https://localhost/api
```

## Authentication

### OAuth 2.0 with SuperTokens

All API endpoints require authentication using OAuth 2.0 tokens managed by SuperTokens.

**Headers:**
```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Token Refresh

```http
POST /auth/session/refresh
Content-Type: application/json

{
  "refreshToken": "your-refresh-token"
}
```

**Response:**
```json
{
  "status": "OK",
  "accessToken": {
    "token": "new-access-token",
    "expiresAt": 1234567890
  },
  "refreshToken": {
    "token": "new-refresh-token",
    "expiresAt": 1234567890
  }
}
```

## Error Handling

### Standard Error Response

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      "field": "additional error details"
    }
  }
}
```

### Common Error Codes

- `AUTH_REQUIRED` - Authentication required
- `INVALID_TOKEN` - Invalid or expired token
- `PERMISSION_DENIED` - Insufficient permissions
- `VALIDATION_ERROR` - Request validation failed
- `NOT_FOUND` - Resource not found
- `RATE_LIMITED` - Rate limit exceeded
- `SERVICE_UNAVAILABLE` - External service unavailable

## Rate Limiting

- **General endpoints**: 1000 requests per hour
- **Authentication endpoints**: 10 requests per minute
- **AI endpoints**: 100 requests per hour
- **Webhook endpoints**: 5000 requests per hour

## Core Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "external_apis": "healthy"
  }
}
```

### User Profile

#### Get User Profile

```http
GET /users/me
```

**Response:**
```json
{
  "id": "user-123",
  "email": "user@example.com",
  "name": "John Doe",
  "preferences": {
    "timezone": "America/New_York",
    "language": "en",
    "notifications": {
      "email": true,
      "push": true
    }
  },
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T00:00:00Z"
}
```

#### Update User Profile

```http
PATCH /users/me
Content-Type: application/json

{
  "name": "John Smith",
  "preferences": {
    "timezone": "Europe/London"
  }
}
```

## Calendar Management

### List Calendar Events

```http
GET /calendar/events
Query Parameters:
  start_date: 2024-01-01
  end_date: 2024-01-31
  calendar_id: optional
```

**Response:**
```json
{
  "events": [
    {
      "id": "event-123",
      "title": "Team Meeting",
      "description": "Weekly team sync",
      "start_time": "2024-01-15T10:00:00Z",
      "end_time": "2024-01-15T11:00:00Z",
      "location": "Conference Room A",
      "status": "confirmed",
      "calendar_id": "calendar-123",
      "attendees": [
        {
          "email": "user1@example.com",
          "name": "User One",
          "response": "accepted"
        }
      ],
      "reminders": [
        {
          "minutes": 15,
          "method": "popup"
        }
      ]
    }
  ],
  "pagination": {
    "total": 50,
    "page": 1,
    "per_page": 20
  }
}
```

### Create Calendar Event

```http
POST /calendar/events
Content-Type: application/json

{
  "title": "New Meeting",
  "description": "Meeting description",
  "start_time": "2024-01-15T14:00:00Z",
  "end_time": "2024-01-15T15:00:00Z",
  "location": "Online",
  "attendees": ["user1@example.com", "user2@example.com"],
  "reminders": [
    {
      "minutes": 10,
      "method": "email"
    }
  ]
}
```

### Update Calendar Event

```http
PUT /calendar/events/{event_id}
Content-Type: application/json

{
  "title": "Updated Meeting Title",
  "description": "Updated description"
}
```

### Delete Calendar Event

```http
DELETE /calendar/events/{event_id}
```

## Task Management

### List Tasks

```http
GET /tasks
Query Parameters:
  status: pending|in_progress|completed
  project_id: optional
  priority: low|medium|high|critical
  due_date: 2024-01-31
```

**Response:**
```json
{
  "tasks": [
    {
      "id": "task-123",
      "title": "Complete project proposal",
      "description": "Draft and review project proposal document",
      "status": "in_progress",
      "priority": "high",
      "due_date": "2024-01-20T23:59:59Z",
      "project_id": "project-123",
      "assignee": "user-123",
      "tags": ["work", "urgent"],
      "dependencies": ["task-122"],
      "estimated_duration": 120,
      "time_spent": 45,
      "created_at": "2024-01-10T09:00:00Z",
      "updated_at": "2024-01-15T14:30:00Z"
    }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "per_page": 20
  }
}
```

### Create Task

```http
POST /tasks
Content-Type: application/json

{
  "title": "New Task",
  "description": "Task description",
  "priority": "medium",
  "due_date": "2024-01-31T23:59:59Z",
  "project_id": "project-123",
  "tags": ["work"],
  "estimated_duration": 60
}
```

### Update Task Status

```http
PATCH /tasks/{task_id}
Content-Type: application/json

{
  "status": "completed",
  "time_spent": 120
}
```

## Communication

### List Messages

```http
GET /messages
Query Parameters:
  platform: gmail|slack|teams|discord
  unread: true|false
  limit: 50
```

**Response:**
```json
{
  "messages": [
    {
      "id": "message-123",
      "platform": "gmail",
      "from": {
        "email": "sender@example.com",
        "name": "Sender Name"
      },
      "to": ["user@example.com"],
      "subject": "Important Update",
      "preview": "This is a preview of the message content...",
      "body": "Full message content...",
      "timestamp": "2024-01-15T14:30:00Z",
      "unread": true,
      "labels": ["INBOX", "IMPORTANT"],
      "attachments": [
        {
          "filename": "document.pdf",
          "size": 1024000,
          "mime_type": "application/pdf"
        }
      ]
    }
  ]
}
```

### Send Message

```http
POST /messages/send
Content-Type: application/json

{
  "platform": "gmail",
  "to": ["recipient@example.com"],
  "subject": "Test Message",
  "body": "This is a test message",
  "cc": ["cc@example.com"],
  "bcc": ["bcc@example.com"]
}
```

## Financial Data

### List Transactions

```http
GET /finance/transactions
Query Parameters:
  account_id: optional
  start_date: 2024-01-01
  end_date: 2024-01-31
  category: food|transport|entertainment
```

**Response:**
```json
{
  "transactions": [
    {
      "id": "transaction-123",
      "account_id": "account-123",
      "amount": -45.50,
      "currency": "USD",
      "description": "Grocery Store",
      "category": "food",
      "date": "2024-01-15T10:30:00Z",
      "merchant": {
        "name": "Local Grocery",
        "category": "Groceries"
      },
      "pending": false,
      "transaction_id": "bank-transaction-123"
    }
  ],
  "summary": {
    "total_income": 5000.00,
    "total_expenses": 3200.50,
    "net_flow": 1799.50
  }
}
```

### Get Financial Summary

```http
GET /finance/summary
Query Parameters:
  period: month|quarter|year
  start_date: 2024-01-01
  end_date: 2024-01-31
```

**Response:**
```json
{
  "period": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "income": 5000.00,
  "expenses": 3200.50,
  "savings": 1799.50,
  "by_category": {
    "food": 450.00,
    "transport": 200.00,
    "entertainment": 150.50
  },
  "budget_vs_actual": {
    "food": {
      "budget": 400.00,
      "actual": 450.00,
      "variance": -50.00
    }
  }
}
```

## Agent System

### List Agents

```http
GET /agents
```

**Response:**
```json
{
  "agents": [
    {
      "id": "agent-123",
      "name": "Research Assistant",
      "role": "research_agent",
      "status": "active",
      "capabilities": ["web_search", "document_analysis"],
      "performance": {
        "tasks_completed": 45,
        "success_rate": 92.5,
        "avg_response_time": 1200
      },
      "config": {
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": "You are a research assistant..."
      },
      "last_active": "2024-01-15T14:30:00Z"
    }
  ]
}
```

### Create Agent

```http
POST /agents
Content-Type: application/json

{
  "name": "New Agent",
  "role": "personal_assistant",
  "capabilities": ["calendar_management", "task_management"],
  "config": {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

### Start/Stop Agent

```http
POST /agents/{agent_id}/start
POST /agents/{agent_id}/stop
```

## Workflow Automation

### List Workflows

```http
GET /workflows
```

**Response:**
```json
{
  "workflows": [
    {
      "id": "workflow-123",
      "name": "Email to Task",
      "description": "Convert important emails to tasks",
      "version": "1.0.0",
      "enabled": true,
      "triggers": [
        {
          "type": "email_received",
          "config": {
            "labels": ["IMPORTANT"],
            "senders": ["boss@company.com"]
          }
        }
      ],
      "actions": [
        {
          "type": "create_task",
          "config": {
            "project_id": "project-123",
            "priority": "high"
          }
        }
      ],
      "execution_count": 45,
      "last_executed": "2024-01-15T10:30:00Z",
      "success_rate": 95.6
    }
  ]
}
```

### Create Workflow

```http
POST /workflows
Content-Type: application/json

{
  "name": "New Workflow",
  "description": "Workflow description",
  "triggers": [
    {
      "type": "calendar_event",
      "config": {
        "event_type": "meeting",
        "minutes_before": 15
      }
    }
  ],
  "actions": [
    {
      "type": "send_notification",
      "config": {
        "platform": "slack",
        "message": "Meeting starting soon"
      }
    }
  ]
}
```

### Execute Workflow

```http
POST /workflows/{workflow_id}/execute
Content-Type: application/json

{
  "trigger_data": {
    "event_id": "event-123",
    "event_type": "meeting"
  }
}
```

## AI Chat Interface

### Create Chat Session

```http
POST /ai/sessions
Content-Type: application/json

{
  "title": "Project Discussion",
  "model": "gpt-4",
  "system_prompt": "You are a helpful assistant..."
}
```

**Response:**
```json
{
  "id": "session-123",
  "title": "Project Discussion",
  "messages": [],
  "model": "gpt-4",
  "created_at": "2024-01-15T14:30:00Z",
  "updated_at": "2024-01-15T14:30:00Z"
}
```

### Send Message to AI

```http
POST /ai/sessions/{session_id}/messages
Content-Type: application/json

{
  "content": "Hello, how can you help me?",
  "role": "user"
}
```

**Response:**
```json
{
  "id": "message-123",
  "role": "assistant",
  "content": "I can help you with various tasks including calendar management, task tracking, and information retrieval. What would you like me to help you with?",
  "timestamp": "2024-01-15T14:31:00Z",
  "model": "gpt-4",
  "tokens": 25
}
```

### List Chat Sessions

```http
GET /ai/sessions
```

## Voice Commands

### List Voice Commands

```http
GET /voice/commands
```

**Response:**
```json
{
  "commands": [
    {
      "id": "command-123",
      "phrase": "open calendar",
      "action": "navigate",
      "description": "Open the calendar view",
      "enabled": true,
      "confidence_threshold": 0.7,
      "parameters": {
        "route": "/calendar"
      },
      "usage_count": 45,
      "last_used": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Process Voice Command

```http
POST /voice/process
Content-Type: application/json

{
  "audio_data": "base64-encoded-audio",
  "transcript": "open calendar"
}
```

**Response:**
```json
{
  "success": true,
  "action": "navigate",
  "parameters": {
    "route": "/calendar"
  },
  "confidence": 0.85
}
```

## Service Integrations

### List Connected Services

```http
GET /integrations
```

**Response:**
```json
{
  "integrations": [
    {
      "id": "integration-123",
      "service_type": "gmail",
      "display_name": "Gmail",
      "connected": true,
      "last_sync": "2024-01-15T14:00:00Z",
      "sync_status": "success",
      "config": {
        "email": "user@example.com",
        "labels_enabled": ["INBOX", "SENT"]
      }
    }
  ]
}
```

### Connect Service

```http
POST /integrations/connect
Content-Type: application/json

{
  "service_type": "gmail",
  "config": {
    "scopes": ["email", "calendar"]
  }
}
```

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "random-state-string"
}
```

### Disconnect Service

```http
DELETE /integrations/{integration_id}
```

## Webhooks

### Register Webhook

```http
POST /webhooks
Content-Type: application/json

{
  "url": "https://your-server.com/webhooks/atom",
  "events": ["calendar.event_created", "task.completed"],
  "secret": "webhook-secret"
}
```

**Response:**
```json
{
  "id": "webhook-123",
  "url": "https://your-server.com/webhooks/atom",
  "events": ["calendar.event_created", "task.completed"],
  "created_at": "2024-01-15T14:30:00Z",
  "active": true
}
```

### Webhook Payload Example

```json
{
  "event": "calendar.event_created",
  "timestamp": "2024-01-15T14:30:00Z",
  "data": {
    "event_id": "event-123",
    "title": "Team Meeting",
    "start_time": "2024-01-16T10:00:00Z",
    "end_time": "2024-01-16T11:00:00Z"
  }
}
```

## Real-time Features

### WebSocket Connection

Connect to WebSocket endpoint for real-time updates:

```javascript
const ws = new WebSocket('wss://localhost/ws');

ws.onopen = () => {
  console.log('Connected to Atom WebSocket');
  // Subscribe to events
  ws.send(JSON.stringify({
    type: 'subscribe',
    events: ['calendar.updates', 'task.updates', 'message.received']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received update:', data);
  
  switch(data.type) {
    case 'calendar.event_created':
      // Handle new calendar event
      break;
    case 'task.completed':
      // Handle task completion
      break;
    case 'message.received':
      // Handle new message
      break;
  }
};

ws.onclose = () => {
  console.log('Disconnected from Atom WebSocket');
};
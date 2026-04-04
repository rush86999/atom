# Frontend to Backend API Documentation

## Overview

This document describes the backend API endpoints created for the migration from direct database access in the Next.js frontend to a centralized FastAPI backend architecture.

**Migration Date**: February 2, 2026
**API Version**: 1.0.0
**Base URL**: `http://localhost:8000` (development)

---

## Table of Contents

- [Authentication](#authentication)
- [User Management](#user-management)
- [Email Verification](#email-verification)
- [Tenants](#tenants)
- [Admin](#admin)
- [Meetings](#meetings)
- [Financial](#financial)
- [Error Responses](#error-responses)
- [Rate Limiting](#rate-limiting)

---

## Authentication

All API endpoints require authentication using a JWT Bearer token.

### Headers

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Token Format

Tokens are issued by `/api/auth/login` and include:
- `sub`: User ID
- `exp`: Expiration timestamp
- `role`: User role

### Example

```bash
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## User Management

Base path: `/api/users`

### Get Current User Details

Get detailed information about the currently authenticated user.

**Endpoint**: `GET /api/users/me`

**Authentication**: Required

**Response**:
```json
{
  "id": "user-123",
  "email": "user@example.com",
  "name": "John Doe",
  "first_name": "John",
  "last_name": "Doe",
  "role": "member",
  "status": "active",
  "email_verified": true,
  "tenant_id": "tenant-456",
  "created_at": "2026-02-01T00:00:00Z",
  "last_login": "2026-02-02T12:34:56Z"
}
```

**Status Codes**:
- `200 OK`: Success
- `401 Unauthorized`: Invalid or missing token

---

### List User Sessions

List all active sessions for the current user.

**Endpoint**: `GET /api/users/sessions`

**Authentication**: Required

**Response**:
```json
[
  {
    "id": "session-789",
    "device_type": "desktop",
    "browser": "Chrome",
    "os": "macOS",
    "ip_address": "192.168.1.100",
    "last_active_at": "2026-02-02T12:34:56Z",
    "created_at": "2026-02-01T00:00:00Z",
    "is_active": true,
    "is_current": false
  }
]
```

---

### Revoke Session

Revoke a specific session (sign out from a device).

**Endpoint**: `DELETE /api/users/sessions/{session_id}`

**Authentication**: Required

**Parameters**:
- `session_id` (path): Session ID

**Response**:
```json
{
  "message": "Session revoked successfully"
}
```

**Status Codes**:
- `200 OK`: Session revoked
- `404 Not Found`: Session not found or doesn't belong to user

---

### Revoke All Sessions

Revoke all sessions except the current one.

**Endpoint**: `DELETE /api/users/sessions`

**Authentication**: Required

**Response**:
```json
{
  "message": "All sessions revoked successfully"
}
```

---

## Email Verification

Base path: `/api/email-verification`

### Verify Email

Verify email with a 6-digit code.

**Endpoint**: `POST /api/email-verification/verify`

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**Validation**:
- `email`: Valid email address (required)
- `code`: Exactly 6 digits (required)

**Response**:
```json
{
  "message": "Email verified successfully"
}
```

**Status Codes**:
- `200 OK`: Email verified successfully
- `400 Bad Request`: Invalid or expired code
- `404 Not Found`: User not found

---

### Send Verification Email

Send a 6-digit verification code via email.

**Endpoint**: `POST /api/email-verification/send`

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response**:
```json
{
  "message": "Verification email sent"
}
```

**Behavior**:
- Generates a 6-digit code
- Code expires in 24 hours
- Old codes are replaced with new ones
- Returns success even if user doesn't exist (prevents email enumeration)

---

## Tenants

Base path: `/api/tenants`

### Get Tenant by Subdomain

Get tenant information by subdomain.

**Endpoint**: `GET /api/tenants/by-subdomain/{subdomain}`

**Authentication**: Not required

**Parameters**:
- `subdomain` (path): Tenant subdomain

**Response**:
```json
{
  "id": "tenant-456",
  "name": "Acme Corporation",
  "subdomain": "acme",
  "plan_type": "premium",
  "status": "active"
}
```

**Status Codes**:
- `200 OK`: Tenant found
- `404 Not Found`: Tenant not found

---

### Get Tenant Context

Get the current user's tenant context.

**Endpoint**: `GET /api/tenants/context`

**Authentication**: Required

**Response**:
```json
{
  "tenant": {
    "id": "tenant-456",
    "name": "Acme Corporation",
    "subdomain": "acme",
    "plan_type": "premium"
  },
  "user_role": "member"
}
```

---

## Admin

Base path: `/api/admin`

### List Admin Users

List all admin users with their roles and permissions.

**Endpoint**: `GET /api/admin/users`

**Authentication**: Required (super_admin role)

**Response**:
```json
[
  {
    "id": "admin-123",
    "email": "admin@example.com",
    "name": "System Administrator",
    "role_id": "role-456",
    "role_name": "super_admin",
    "permissions": {
      "users": true,
      "workflows": true,
      "security": true
    },
    "status": "active",
    "last_login": "2026-02-02T12:34:56Z"
  }
]
```

**Status Codes**:
- `200 OK`: Success
- `403 Forbidden`: User is not a super_admin

---

### Update Admin Last Login

Update an admin user's last login timestamp.

**Endpoint**: `PATCH /api/admin/users/{admin_id}/last-login`

**Authentication**: Required

**Parameters**:
- `admin_id` (path): Admin user ID

**Response**:
```json
{
  "message": "Last login updated"
}
```

---

## Meetings

Base path: `/api/meetings`

### Get Meeting Attendance

Get meeting attendance status for a task.

**Endpoint**: `GET /api/meetings/attendance/{task_id}`

**Authentication**: Required

**Parameters**:
- `task_id` (path): Task ID

**Response**:
```json
{
  "task_id": "task-789",
  "user_id": "user-123",
  "platform": "zoom",
  "meeting_identifier": "123456789",
  "status_timestamp": "2026-02-02T12:34:56Z",
  "current_status_message": "In progress",
  "final_notion_page_url": "https://notion.so/page-abc123",
  "error_details": null
}
```

**Status Codes**:
- `200 OK`: Meeting attendance found
- `404 Not Found`: Meeting attendance not found

---

## Financial

Base path: `/api/financial`

### Get Net Worth Summary

Get user's net worth summary (latest snapshot).

**Endpoint**: `GET /api/financial/net-worth/summary`

**Authentication**: Required

**Response**:
```json
{
  "user_id": "user-123",
  "snapshot_date": "2026-02-01",
  "net_worth": "50000.00",
  "assets": "75000.00",
  "liabilities": "25000.00"
}
```

---

### List Financial Accounts

List all financial accounts for the current user.

**Endpoint**: `GET /api/financial/accounts`

**Authentication**: Required

**Response**:
```json
[
  {
    "id": "account-123",
    "account_type": "checking",
    "provider": "Chase Bank",
    "name": "Main Checking",
    "balance": "5000.00",
    "currency": "USD"
  }
]
```

---

## Error Responses

All endpoints may return these standard error responses:

### 400 Bad Request

Invalid request parameters.

```json
{
  "detail": "Invalid or expired verification code"
}
```

### 401 Unauthorized

Authentication failed or token missing.

```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden

Insufficient permissions.

```json
{
  "detail": "Admin access required"
}
```

### 404 Not Found

Resource not found.

```json
{
  "detail": "User not found"
}
```

### 500 Internal Server Error

Server error.

```json
{
  "detail": "Internal server error",
  "error": "Detailed error message"
}
```

---

## Rate Limiting

To prevent abuse, the following endpoints have rate limiting:

- `POST /api/email-verification/verify`: 10 requests per minute
- `POST /api/email-verification/send`: 3 requests per hour
- `POST /api/auth/login`: 5 requests per minute

**Rate Limit Response**:
```json
{
  "detail": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Migration from Direct DB Access

This API replaces the following direct database queries previously made by the frontend:

### User Queries
```sql
-- OLD: Direct DB query
SELECT * FROM users WHERE email = $1
-- NEW: API endpoint
GET /api/users/me
```

### Email Verification
```sql
-- OLD: Direct DB query
SELECT * FROM email_verification_tokens WHERE user_id = $1 AND token = $2
-- NEW: API endpoint
POST /api/email-verification/verify
```

### Tenant Queries
```sql
-- OLD: Direct DB query
SELECT * FROM tenants WHERE subdomain = $1
-- NEW: API endpoint
GET /api/tenants/by-subdomain/{subdomain}
```

### Admin Queries
```sql
-- OLD: Direct DB query
SELECT au.*, ar.name as role_name FROM admin_users au JOIN admin_roles ar ON au.role_id = ar.id
-- NEW: API endpoint
GET /api/admin/users
```

---

## Client Libraries

### TypeScript (Frontend)

```typescript
import { apiClient, USE_BACKEND_API } from './lib/api';

// Get current user
const user = await apiClient.getCurrentUser();

// Verify email
await apiClient.verifyEmail('user@example.com', '123456');
```

See `frontend-nextjs/lib/api.ts` for complete API client implementation.

---

## Version History

- **1.0.0** (2026-02-02): Initial release with migration endpoints
  - User management endpoints
  - Email verification endpoints
  - Tenant management endpoints
  - Admin user endpoints
  - Meeting tracking endpoints
  - Financial data endpoints

---

## Support

For issues or questions:
- Backend logs: Check server console output
- Frontend logs: Check Next.js console output
- API Docs: http://localhost:8000/docs (Swagger UI)
- Architecture: See `docs/ARCHITECTURE.md`

---

**Generated**: February 2, 2026
**Last Updated**: February 2, 2026

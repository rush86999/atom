# Frontend Security Audit — Round 38

**Date**: June 22, 2026
**Scope**: `frontend-nextjs/` — XSS, token storage, API client security

## Findings

### HIGH-1: XSS via `dangerouslySetInnerHTML` in chat components

**Files affected**:
- `components/chat/canvas-host.tsx:344` — renders `htmlContent` directly
- `components/chat/MessageList.tsx:51` — renders message content
- `components/chat/CanvasHost.tsx:92` — renders `marked.parse(data)` output

**Risk**: Agent output and user messages may contain `<script>` tags or event
handlers (`onerror=`, `onload=`). `marked.parse()` does **not** sanitize HTML
by default — inline HTML passes through. If an attacker can control agent
output (e.g., via prompt injection that causes the LLM to emit malicious HTML),
they achieve XSS in every viewer's browser.

**Recommended fix**:
```bash
npm install dompurify @types/dompurify
```
```typescript
import DOMPurify from 'dompurify';
const cleanHtml = DOMPurify.sanitize(marked.parse(content));
```

Apply to ALL three `dangerouslySetInnerHTML` sites.

### MEDIUM-2: Auth token stored in `localStorage`

**Files affected**:
- `hooks/useWebSocket.ts:41`
- `lib/api.ts:33`
- `lib/api-admin.ts:52,321`
- `pages/login.tsx` (writes the token)

**Risk**: `localStorage` is accessible to any JavaScript on the page. Combined
with HIGH-1 (XSS), an attacker who achieves script execution can exfiltrate
the auth token via `localStorage.getItem("auth_token")` → full account takeover.

**Recommended fix**: Migrate to `httpOnly` + `Secure` + `SameSite=Strict` cookies
set by the backend. This makes tokens inaccessible to client-side JS, neutralizing
the XSS→token-theft chain. Requires backend changes to `/api/auth/login` (set
Set-Cookie header instead of returning token in body).

### LOW-3: `mermaid` SVG injection

**File**: `components/ReasoningChainViewer.tsx:88-90`

Mermaid renders SVG via `innerHTML`. Mermaid has had XSS advisories in the past.
Ensure `mermaid` is pinned to the latest patched version.

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| HIGH (XSS) | 3 sites | Needs DOMPurify fix |
| MEDIUM (token storage) | 5 files | Needs httpOnly cookie migration |
| LOW (mermaid) | 1 file | Keep dependency updated |

**No code changes applied in this round** — frontend changes require careful
E2E regression testing and were out of scope for the backend-focused bug hunt.
These findings should be addressed in a dedicated frontend security sprint.

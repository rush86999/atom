# Phase 0 — Fix the Email Ingestion Basics

> This document is part of the bigger plan: "Ingestion → Agent Training".
> Phase 0 is the first step. It only fixes 3 small problems in the email
> pipeline. We do these first because the later phases need a working email
> pipeline.

> **Status (2026-09-01): all 3 tasks implemented + tested.**
> Task 1 (poller token), Task 2 (poll interval env), Task 3 (email secrets
> redaction) are done. Evidence: `tests/test_email_api_ingestion.py` 24 passed
> (19 existing + 5 new), `tests/test_ingestion_status_routes.py` 25 passed.

---


## What is this phase about

The app reads Outlook emails in the background (this is called **polling**).
Right now the email pipeline has 3 problems:

1. **The email poller cannot get the user's login token.** So it never
   actually reads any email.
2. **The poll time is fixed in the code.** We cannot change how often the app
   checks for new email without changing code.
3. **Email bodies are saved as-is.** If an email contains a secret (like an
   API key or a password), the secret is stored in the database and later
   shown to agents.

This phase fixes these 3 problems. Nothing else changes.

---

## Task 1 — Fix the email poller token bug

### The problem

The email poller is a background loop that checks Outlook for new mail every
few seconds. To read mail, it needs the user's access token (a key that
Microsoft gives when the user connects Outlook).

But the code asks for the token like this:

```python
access_token = await outlook_service._get_access_token(user_id=None)
```

It passes `user_id=None` (no user).

The token function has a safety rule: **never use another user's token** (no
cross-user fallback). So when there is no user id, it returns `None` — on
purpose.

Result: the poller never gets a token, so it never fetches any email. It
just logs a warning:

```
No Microsoft OAuth token found for Outlook polling (IntegrationToken)
```

Files (evidence):

- `backend/integrations/atom_communication_ingestion_pipeline.py` line 2284
  — the call with `user_id=None`
- `backend/integrations/outlook_service.py` lines 182-224 — returns `None`
  when there is no user id

### The fix

When the user connects Outlook (the OAuth login step), we know who the user
is. We pass that user's id to the poller:

- `backend/api/oauth_routes.py` line 384 — change the poller start to send
  the user id: `start_outlook_poller(user_id=<the user>)`
- `backend/integrations/atom_communication_ingestion_pipeline.py` — the
  poller saves the user id in its config. The mail-fetch step
  (`_fetch_outlook_messages`) uses that user id to get the token.

Rules we keep:

- **No cross-user fallback.** The poller only uses the token of the user who
  connected. This is a security rule — we do not change it.
- If there is no user id, the poller skips (same as today) and logs a clear
  reason.

### Test

Write a unit test:

1. Save an `IntegrationToken` for user X (encrypted, as the OAuth flow does).
2. Run the mail fetch with user X's id.
3. Check that the fetch uses user X's token and returns the messages.
4. Also test the empty case: no token → returns empty list, no crash.

---

## Task 2 — Make the poll time a setting

### The problem

The poll time (how often the app checks Outlook for new email) is a number
fixed in the code: 60 seconds. To change it, someone has to edit code.

### The fix

Add a new environment variable:

```
ATOM_OUTLOOK_POLL_SECONDS
```

- Default: `60` (same as today)
- Minimum: `15` (the code has a floor of 15 — keep it)

Where:

- `backend/integrations/atom_communication_ingestion_pipeline.py` line 930
  (`start_outlook_poller`) — read the env variable as the default value.
- Document the new variable in `CLAUDE.md` and
  `docs/reference/ENVIRONMENT_VARIABLES.md`.

### Test

Unit test:

1. Set `ATOM_OUTLOOK_POLL_SECONDS=45`.
2. Check the poller config shows 45.
3. Set it to `10` — check the value becomes 15 (the floor works).

---

## Task 3 — Clean secrets from email bodies

### The problem

When the app reads an email, it stores the full body in the database
(LanceDB, table `atom_communications`, column `content`). The body is saved
as-is — nothing is removed.

If an email contains something sensitive — an API key, a password, a secret
token — that secret is stored and later shown to agents when they recall the
email.

Document files already get this cleaning (a **secrets redactor**). Email
bodies do not. This is the gap.

### The fix

Reuse the same secrets redactor that documents already use:

- `backend/core/secrets_redactor.py` — `SecretsRedactor.redact()`

Apply it to the email body before storing it. Secrets become placeholders
like `[REDACTED_API_KEY]` instead of the real value.

Where:

- `backend/integrations/atom_communication_ingestion_pipeline.py` — at the
  point where the body is cleaned and stored (around lines 2388-2417, before
  the write to LanceDB).

Notes:

- This only cleans **new** emails. Old emails already in the database stay
  as they are. Cleaning old rows is a follow-up, not part of Phase 0.

### Test

Unit test:

1. Make an email body that contains a fake API key and a fake password.
2. Run the ingest step.
3. Check that the stored content has `[REDACTED_...]` placeholders and does
   not contain the raw secret.

---

## What does NOT change in Phase 0

- No changes to the webhook, subscription, or delta-query work (that is
  Phase 4).
- No changes to Drive ingestion (that is Phase 2).
- No changes to the frontend.
- No changes to how agents are governed (maturity, HITL).
- No changes to the database schema.

---

## Files changed in Phase 0 (summary)

| File | Why |
|---|---|
| `backend/api/oauth_routes.py` | Send the user id when starting the poller |
| `backend/integrations/atom_communication_ingestion_pipeline.py` | Use the user id for the token; read the poll interval from env; redact email bodies |
| `backend/integrations/outlook_service.py` | (maybe) small helper to read the poller's user id — only if needed |
| `CLAUDE.md`, `docs/reference/ENVIRONMENT_VARIABLES.md` | Document `ATOM_OUTLOOK_POLL_INTERVAL_SECONDS` |
| `backend/tests/test_email_api_ingestion.py` | New tests added to the existing email suite:
  `test_fetch_outlook_messages_uses_configured_user_token`, `test_start_outlook_poller_stores_user_id` |

## How we work (repo rules)

- Every fix starts with a failing test (TDD). Red → Green → Refactor.
- After each fix, add a row to `docs/testing/TESTED_FILES_TRACKER.md`.
- Flag behavior changes in `notes/AGENT_COORDINATION.md` before starting.
  Task 1 changes behavior for every email-ingestion caller (it was silently
  failing before).

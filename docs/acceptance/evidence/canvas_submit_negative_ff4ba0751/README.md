# Canvas submit — reproduced negative on remote main

Runtime main b550fd728, test checkpoint ff4ba0751. Real mounted POST /api/canvas/submit + fresh scratch SQLite:3fail1pass. Commit failure still returns200success, successful write lacks exact verifiable operation/audit receipt, foreign-tenant/workspace canvas accepts a submit audit. Same-scope non-owner shared-form submission passes and must stay supported; submit is an event, not authorship/gallery access.

Only a commit fault is injected; authority/model/router/session persistence paths are real in this slice. TESTING1 and an explicit scratch DATABASE_URL keep the live dev DB untouched. No app server/model/device/account actions. No repair accepted yet; configured Flash proposal is four existing files, reusing accepted canvas actor/scope/CAS helpers, existing CanvasAudit ledger and registered oracle. Accepted save/restore/delete evidence remains unchanged. No extra approval prompt or scope broadening is authorized.

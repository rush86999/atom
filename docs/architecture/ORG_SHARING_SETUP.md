# Org Ingestion Sharing — Setup & Operations Runbook

> **Audience:** the person standing up org-wide ingestion sharing for a team where
> each member runs Atom locally (Personal Edition). Feature reference:
> [ORG_INGESTION_SHARING_PLAN.md](ORG_INGESTION_SHARING_PLAN.md).
> Everything below is behind `ATOM_ORG_SHARING_ENABLED` (default **off**) — enabling
> it changes nothing until you export/import or configure a hub.

---

## Topology

```
                ┌────────────────────────────┐
                │  HUB (one always-on        │   owns org-source connections
                │  instance: server or a     │   (org service account, NOT
                │  designated member machine)│   personal OAuth)
                └─────────────┬──────────────┘
        signed delta pulls     │      signed profiles/bundles
        (ATOM_ORG_HUB_URL)     │      (file transfer, any channel)
   ┌──────────┬───────────────┼──────────────┬───────────┐
   │ Member A │  Member B     │  Member C    │  ...      │
   │ (local)  │  (local)      │  (local)     │           │
   │ personal │  personal     │  personal    │           │
   │ sources  │  sources      │  sources     │           │
   └──────────┴───────────────┴──────────────┴───────────┘
```

Personal sources and credentials never leave a member's instance. Episodic
memory, chat, and turn facts are **never shared** (they drive per-agent
graduation; sharing would corrupt the trust model).

## 0. Prerequisites (both hub and members)

- Atom backend with migration `20260816_org_ingestion_sharing` applied
  (`alembic upgrade head`; the migration is guarded and idempotent).
- `ATOM_ORG_SHARING_ENABLED=true` in the instance `.env`.
- Run `GET /api/data-ingestion/org-key` once — it generates the instance
  Ed25519 keypair (`./data/org_sharing_key`, 0600) and registers the public
  key. **Back this file up** (losing it means re-registering your identity).

## 1. Hub setup

The hub is an ordinary Atom instance (the same `docker-compose-personal.yml`
works) plus:

```bash
ATOM_ORG_SHARING_ENABLED=true
ATOM_ORG_HUB_ENABLED=true                 # serves GET /api/data-ingestion/hub/bundles
# Egress policy — a member request can never exceed these:
ATOM_ORG_HUB_MAX_SENSITIVITY=internal     # public|internal|confidential|restricted
ATOM_ORG_HUB_SOURCE_ALLOWLIST=salesforce,slack,gmail   # unset = no restriction
```

**Set the allowlist.** Without it, a member pulling with `sources=` empty is
served *every* integration on the hub — including anything personal connected
to it. With it, requests are intersected with the allowlist (mixed requests
fail closed with a 400 naming the denied source) and empty requests get the
allowlist.

**Member pull keys.** Members authenticate with `atom_sk_*` gateway keys (the
LLM-gateway mechanism, `api/gateway_key_routes.py`). Mint one per member on
the hub, distribute over a secure channel, and revoke there if a member
leaves. Hub access is read-only egress; the key grants no write surface.

Connect org sources on the hub with an **org service account** (not a
member's personal OAuth), then verify: `POST /api/data-ingestion/sync/{id}`
succeeds and `GET /api/data-ingestion/usage` shows records.

## 2. Key ceremony (one-time, per member ↔ hub pair)

1. Hub runs `GET /api/data-ingestion/org-key` → public key + fingerprint.
2. Member runs the same. Exchange public keys out-of-band (any channel — they
   are public values; verify fingerprints verbally/through a second channel).
3. Each side: `POST /api/data-ingestion/org-key/register`
   `{"public_key": "<b64>", "label": "hub" | "member-alice"}`.
4. Validate: export a bundle on one side, import on the other — signature
   must verify. A `signature verification failed` error means step 2/3 was
   skipped or mistyped.

Members importing hub pulls must register the **hub's** public key. The hub
itself needs no member keys (it signs; members verify).

## 3. Member setup

```bash
ATOM_ORG_SHARING_ENABLED=true
ATOM_ORG_HUB_URL=https://hub.internal.example.com   # enables the scheduled pull loop
ATOM_ORG_HUB_API_KEY=atom_sk_...                    # member's gateway key on the hub
ATOM_ORG_HUB_SOURCES=salesforce,slack               # what to pull
ATOM_ORG_HUB_SENSITIVITY_CEILING=internal           # what to accept
ATOM_ORG_HUB_PULL_INTERVAL_MIN=15                   # default 15
```

- The pull loop starts with the app, pulls signed **delta** bundles (only
  records newer than the member's cursor), verifies the signature, and
  applies via the Phase 2 import path (dedup, re-embedding, audit).
- Cursor state survives restarts. `GET /api/data-ingestion/hub/status` shows
  the cursor per source and the last five import results — the first thing to
  check when data looks stale.
- One-off/manual pull: `POST /api/data-ingestion/hub/pull`
  `{"hub_url", "api_key", "sources", "sensitivity_ceiling"}`.

Config-only sharing (no hub): export/import **ingestion profiles**
(`GET/POST /api/data-ingestion/profile/{export,import}`) and one-shot
**bundles** (`POST /api/data-ingestion/bundle/{export,import}`) as files over
any channel.

## 4. Sensitivity policy

Records are classified `public < internal < confidential < restricted` (P4
data-taint; GraphRAG nodes inherit the most restrictive source document).

- Exports exclude confidential/restricted **by default**. Raising the ceiling
  (`sensitivity_ceiling=confidential`) creates a scoped sub-bundle for a named
  audience (`destination="finance-team"` — recorded in the audit row).
- On the hub, `ATOM_ORG_HUB_MAX_SENSITIVITY` caps what any member can pull,
  regardless of what they request. The response reports
  `ceiling_clamped_to` when a request was clamped.
- Imports never lower a local record's classification; merges take the max.

## 5. Operating procedures

| Situation | Procedure |
|---|---|
| Rotate a member's signing key | Member: delete `./data/org_sharing_key`, `GET /org-key` (new key), re-register on the hub; hub: `DELETE /api/data-ingestion/org-key/{old_id}` (`GET /org-key/list` shows ids) |
| Remove a departed member | Hub: revoke their `atom_sk_*` gateway key; members: revoke their old public key |
| Hub down | No action — members run on stale local data; the loop retries each interval |
| Hub replaced/re-hosted | Same key file restored → members keep verifying; new key file → repeat the key ceremony |
| Data looks stale on a member | `GET /api/data-ingestion/hub/status` → check `recent_imports` for errors and `cursor_sources` |
| Suspected bad bundle | Refuse-by-design: tampered/unsigned/oversized bundles are rejected before parsing and audited in `bundle_imports` |

## 6. Validation checklist (before production)

- [ ] Migration applied on hub and all members; `GET /health/ready` green.
- [ ] Hub allowlist set; `MAX_SENSITIVITY` deliberately chosen and recorded.
- [ ] Key ceremony done both directions where applicable; a profile round-trip
      imports with `signature_valid: true`.
- [ ] A delta pull on a member lands records that appear in memory search;
      re-pull is a no-op (`records_skipped` grows, `records_ingested` = 0).
- [ ] A restricted row on the hub does **not** appear in a default pull.
- [ ] Killing the hub: member stays functional, logs a pull error, recovers
      when the hub returns.
- [ ] `bundle_exports` / `bundle_imports` audit rows exist for every operation
      with expected counts.

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `403 Permission denied: org ingestion sharing` | `ATOM_ORG_SHARING_ENABLED` not set on the serving instance |
| `403` on `/hub/bundles` | `ATOM_ORG_HUB_ENABLED` not set on the hub |
| `401` on pull | Gateway key wrong/revoked on the hub |
| `400 signature verification failed` | Signer's public key not registered (key ceremony step 3) |
| `400 Payload hash mismatch` | Bundle was modified in transit — do not trust it; re-export |
| `400 Sources not on the hub allowlist` | Request includes non-allowlisted sources; fix member `ATOM_ORG_HUB_SOURCES` |
| `records_ingested: 0` on every pull | Expected after first sync (dedup) — check `records_skipped`; if both are 0, check hub source ids match member `ATOM_ORG_HUB_SOURCES` |
| Import works but search finds nothing | Member-side re-embedding runs through the LanceDB path; check the instance's embedding provider is configured (BYOK key or fastembed) |

## 8. Security properties (what the design guarantees)

1. Credentials never travel: every export path runs `strip_credentials` and
   fails closed if anything survives.
2. Embeddings never travel: members re-embed locally (BYOK providers differ).
3. Restricted/confidential data cannot leave by default; hub-side clamps
   override member requests.
4. Signature verified **before** parsing; tampered/unsigned bundles are
   rejected and audited.
5. Imports are untrusted input: they re-enter through governed ingestion
   paths and can never lower a sensitivity classification.
6. Episodic memory, chat, and turn facts are architecturally excluded.

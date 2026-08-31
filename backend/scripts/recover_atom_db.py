"""One-shot recovery: rebuild data/atom.db from sqlite3 .recover output.

Context (Aug 30 incident): a backend restart under system Python 3.14 at
22:58 dropped the domain tables; .recover preserved the rows in
lost_and_found (keyed by original root page + field count). This script
recreates the schema from the ORM and lifts the identifiable rows back
into their tables, then recreates the 4 fleet agents whose small pages
were overwritten before the process was stopped.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RECOVERED_SQL = "/tmp/recovered.sql"
TARGET_DB = "/tmp/atom_rebuilt.db"

# ── 1. schema ────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, text  # noqa: E402
from core.database import Base  # noqa: E402
import core.models  # noqa: F401,E402
from core.models import AgentRegistry  # noqa: E402
import core.models_registration  # noqa: F401,E402

if os.path.exists(TARGET_DB):
    os.remove(TARGET_DB)
eng = create_engine(f"sqlite:///{TARGET_DB}")
Base.metadata.create_all(eng)
print("schema created")

# ── 2. parse lost_and_found ──────────────────────────────────────────────
LINE = re.compile(r"^INSERT INTO lost_and_found VALUES\((\d+), (\d+), (\d+), (.*)\);\s*$")


def parse_values(s):
    out, i, n = [], 0, len(s)
    while i < n:
        while i < n and s[i] in " ,":
            i += 1
        if i >= n:
            break
        if s.startswith("NULL", i):
            out.append(None)
            i += 4
        elif s[i] == "'":
            i += 1
            buf = []
            while i < n:
                if s[i] == "'":
                    if i + 1 < n and s[i + 1] == "'":
                        buf.append("'")
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    buf.append(s[i])
                    i += 1
            out.append("".join(buf))
        else:
            j = i
            while j < n and s[j] != ",":
                j += 1
            tok = s[i:j].strip()
            try:
                out.append(int(tok))
            except ValueError:
                try:
                    out.append(float(tok))
                except ValueError:
                    out.append(tok)
            i = j
    return out


# Multi-line values (canvas email bodies!) break line-by-line matching, so
# split on statement starts and take everything up to the next INSERT/EOF.
rows = []
content = open(RECOVERED_SQL, errors="replace").read()
chunks = content.split("INSERT INTO lost_and_found VALUES(")[1:]
for chunk in chunks:
    header, rest = chunk.split(",", 1)  # first number only
    pgno_s, nfield_s, rest = rest.split(",", 2)
    body = rest[: rest.rfind(");")]
    rows.append((int(pgno_s.split(",")[0] if "," in pgno_s else pgno_s), int(nfield_s), parse_values(body)))
print("lost_and_found rows parsed:", len(rows))


def isuuid(x):
    return isinstance(x, str) and re.fullmatch(r"[0-9a-f-]{36}", x) is not None


def table_cols(nfield, v):
    """Recovered rows are (rowid, c0..c{nfield-1}, NULL-padding...). The
    header's nfield is the authoritative column count."""
    return v[1:1 + nfield]


conn = eng.connect()
counts = {}


def insert_many(table, columns, value_rows):
    ph = ",".join(f":c{i}" for i in range(len(columns)))
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({ph})"
    for vr in value_rows:
        conn.execute(text(sql), {f"c{i}": v for i, v in enumerate(vr)})
    counts[table] = len(value_rows)


# users — 19 recovered fields, model uses the first 14
USER_COLS = ["id", "tenant_id", "email", "hashed_password", "first_name", "last_name",
             "role", "status", "workspace_id", "is_active", "created_at", "updated_at",
             "last_login", "notification_preferences"]
users = []
for (_r, n, v) in rows:
    vv = table_cols(n, v)
    if (n == 19 and isuuid(vv[0]) and isinstance(vv[2], str) and "@" in vv[2]
            and str(vv[3]).startswith("$2b$")):
        users.append(vv[:14])
insert_many("users", USER_COLS, users)

# tenants — 22 fields, model uses first 15
TENANT_COLS = ["id", "name", "subdomain", "domain", "plan_type", "edition",
               "segregated_namespaces", "is_active", "billing_email", "budget_limit_usd",
               "metadata_json", "current_spend_usd", "total_spend_usd", "created_at", "updated_at"]
tenants = []
for (_r, n, v) in rows:
    vv = table_cols(n, v)
    if n == 22 and vv[1:2] == ["Default Tenant"]:
        tenants.append(vv[:15])
insert_many("tenants", TENANT_COLS, tenants)

# canvases — 18 fields, exact model order
CANVAS_COLS = ["id", "tenant_id", "workspace_id", "created_by", "name", "description",
               "canvas_type", "content", "style", "is_collaborative", "is_public",
               "share_token", "status", "mini_app_id", "created_at", "updated_at",
               "last_edited_by", "last_edited_at"]
canvases = []
for (_r, n, v) in rows:
    vv = table_cols(n, v)
    if n == 18 and isuuid(vv[0]) and isinstance(vv[4], str) and vv[1] in ("default", None):
        canvases.append(vv)
insert_many("canvases", CANVAS_COLS, canvases)

# canvas_audit — 11 fields, exact model order
AUDIT_COLS = ["id", "canvas_id", "tenant_id", "session_id", "action_type", "user_id",
              "agent_id", "episode_id", "canvas_type", "details_json", "created_at"]
audit = []
for (_r, n, v) in rows:
    vv = table_cols(n, v)
    if (n == 11 and isuuid(vv[0]) and isuuid(vv[1])
            and vv[4] in ("create", "update", "present", "close", "delete", "fork")):
        audit.append(vv)
insert_many("canvas_audit", AUDIT_COLS, audit)

# chat_messages — 8 fields, exact model order
CHAT_COLS = ["id", "conversation_id", "tenant_id", "role", "content", "created_at",
             "agent_id", "metadata_json"]
chats = []
for (_r, n, v) in rows:
    vv = table_cols(n, v)
    if n == 8 and isinstance(vv[3], str) and vv[3] in ("user", "assistant", "system"):
        chats.append(vv)
insert_many("chat_messages", CHAT_COLS, chats)

# agent_reasoning_steps — 21 fields, exact model order (id..resolved_model)
STEP_COLS = ["id", "tenant_id", "execution_id", "step_number", "step_type", "thought",
             "action", "observation", "confidence", "duration_ms", "verified",
             "verification_evidence", "feedback_score", "feedback_text", "match_level",
             "match_confidence_provenance", "match_confidence_score", "external_validated_at",
             "timestamp", "requested_model", "resolved_model"]
steps = []
for (_r, n, v) in rows:
    vv = table_cols(n, v)
    if n == 21 and isuuid(vv[0]) and isinstance(vv[4], str) and vv[4] in (
            "thought", "observation", "final_answer", "action", "reflection"):
        steps.append(vv)
insert_many("agent_reasoning_steps", STEP_COLS, steps)

# ── 3. recreate the fleet agents (their pages were overwritten) ─────────
AGENTS = [
    # (id, name, description, status, confidence, role)
    ("atom_main", "Atom", "Main orchestrator agent — mentor and governance anchor", "autonomous", 0.9, "orchestrator"),
    ("a458ff79-4a13-4abc-9118-7de34a7d8813", "SDR Hire", "Sales development hire", "autonomous", 0.6, "sdr"),
    ("9837ec71-4f1b-41db-b014-119862362d44", "Sales Assistant",
     "Sales Assistant. Employee goal: sales agent", "student", 0.5, "sales_assistant"),
    ("b38f2c3d-7432-48e8-a049-92e75c0d967b", "Demo Assistant", "Demo assistant", "student", 0.5, "assistant"),
]
agent_rows = []
for aid, name, desc, status, conf, arole in AGENTS:
    cfg = ('{"system_prompt": "You are ' + name + '.'
            + (' Employee goal: sales agent", "role": "sales_assistant"}' if "Sales Assistant" in name else '"}'))
    agent_rows.append([
        aid,               # id
        name,              # name
        name,              # display_name
        None,              # handle
        desc,              # description
        "generic",         # category
        arole,             # role
        "generic",         # type
        "{}",              # capabilities
        "GenericAgent",    # module_class
        "core.generic_agent",  # module_path
        "GenericAgent",    # class_name
        None,              # user_id
        "default",         # workspace_id
        "default",         # tenant_id
        status,            # status
        conf,              # confidence_score
        None,              # required_role_for_autonomy
        0,                 # self_healed_count
        aid == "atom_main",  # is_system_agent
        1,                 # enabled
        None,              # diversity_profile
        None,              # division_id
        None,              # parent_agent_id
        None,              # specialty
        None,              # version
        "2026-08-28 21:27:53",  # created_at
        None,              # updated_at
        cfg,               # configuration
        None,              # schedule_config
        None,              # training_period_days
        None,              # training_started_at
        None,              # training_ends_at
        None,              # training_config
        None,              # last_promotion_at
        0,                 # promotion_count
        None,              # last_exam_id
        None,              # exam_eligible_at
        0,                 # daily_requests_count
        None,              # last_request_date
    ])
AGENT_COLS_ORDER = [c.name for c in AgentRegistry.__table__.columns]
insert_many("agent_registry", AGENT_COLS_ORDER, agent_rows)

conn.commit()
print("inserted:", counts)

# sanity: the key entities
for q in [
    "SELECT COUNT(*) FROM users WHERE id='8cce0c47-1471-4c3f-bf5f-6a01da01095f'",
    "SELECT COUNT(*) FROM canvases WHERE id='e7249cf9-ca81-4647-9bca-d94fbfb2998e'",
    "SELECT COUNT(*) FROM canvas_audit WHERE canvas_id='e7249cf9-ca81-4647-9bca-d94fbfb2998e'",
    "SELECT COUNT(*) FROM agent_registry",
    "SELECT COUNT(*) FROM chat_messages",
]:
    print(q, "->", conn.execute(text(q)).scalar())
conn.close()
print("rebuilt db at", TARGET_DB)

"""Source-contract tests for the WA-075 signed-in settings acceptance.

These tests launch nothing: no world, no browser, no model, no provider and
no database. They pin the harness guardrails (which checks must exist, which
origins/credentials must never appear, which cleanup paths must run) and the
preflight's pure refusal functions.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT = REPO / "scripts" / "acceptance" / "browser_settings_preflight.py"
DRIVER = REPO / "scripts" / "acceptance" / "browser_settings_acceptance.mjs"
CORE_SURFACE = REPO / "scripts" / "acceptance" / "browser_core_surface.mjs"
SHARED_LIB = REPO / "scripts" / "acceptance" / "lib" / "core_surface_session.mjs"

REQUIRED_CHECKS = {
    "session.signed_in_token",
    "run.no_foreign_api_origin",
    "account.page_loads",
    "account.profile_readback",
    "account.two_factor_surface",
    "account.password_change_saved",
    "account.password_reload",
    "account.password_restored",
    "ai.page_loads",
    "ai.policy_loads",
    "ai.policy_saved",
    "ai.policy_persisted_reload",
    "ai.policy_restored",
    "sessions.page_loads",
    "sessions.disposable_secondary_session",
    "sessions.list_reflects_live_sessions",
    "sessions.revoke_disposable",
    "routing.page_loads",
    "routing.metrics_loaded_from_backend",
    "routing.rendered_matches_payload",
    "routing.refresh_refetches",
    "routing.honest_telemetry_state",
    "local_models.page_loads",
    "local_models.register_saved",
    "local_models.persisted_after_reload",
    "local_models.delete_removed",
    "local_models.no_provider_contact",
}

BANNED_EXTERNAL_HOSTS = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "openrouter.ai",
    "api.deepseek.com",
    "api.groq.com",
    "ollama.com",
    "127.0.0.1:8001",
    "localhost:8000",
    "127.0.0.1:3000",
)


def _load_preflight():
    spec = importlib.util.spec_from_file_location(
        "browser_settings_preflight", PREFLIGHT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def preflight():
    return _load_preflight()


@pytest.fixture(scope="module")
def driver_source() -> str:
    return DRIVER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------------

def test_every_wa075_check_is_explicit(driver_source: str):
    missing = sorted(cid for cid in REQUIRED_CHECKS if f'"{cid}"' not in driver_source)
    assert not missing, f"driver does not record these checks: {missing}"


def test_driver_uses_the_core_surface_world_contract(driver_source: str):
    assert "lib/core_surface_session.mjs" in driver_source
    assert "ATOM_FRONTEND_URL" in driver_source
    assert "ATOM_BACKEND_URL" in driver_source
    assert "ATOM_SCOPE_PASSWORD" in driver_source
    assert "channel: \"chrome\"" in driver_source
    assert "ATOM_CHROME_EXECUTABLE" in driver_source
    assert "frontend-nextjs/node_modules/playwright/index.mjs" in driver_source
    # The original harness must keep working through the extracted helpers.
    core = CORE_SURFACE.read_text(encoding="utf-8")
    assert "./lib/core_surface_session.mjs" in core
    assert "coreLoginToken" in core
    assert SHARED_LIB.is_file()


def test_no_live_or_external_endpoint_is_hardcoded(driver_source: str):
    for banned in BANNED_EXTERNAL_HOSTS:
        assert banned not in driver_source, f"driver names live/external host {banned}"
    # The only provider host the driver may name is the RFC 2606 fixture.
    assert "wa075-disposable.invalid" in driver_source


def test_driver_never_reads_provider_credentials(driver_source: str):
    for name in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
        "OPENCODE_API_KEY", "MISTRAL_API_KEY", "XAI_API_KEY",
    ):
        assert name not in driver_source, f"driver reads credential variable {name}"
    assert "password_value_recorded: false" in driver_source
    assert "secret_recorded: false" in driver_source


def test_driver_installs_nothing_and_child_processes_nothing(driver_source: str):
    for banned in ("child_process", "execSync", "spawnSync", "npm install", "playwright install"):
        assert banned not in driver_source


def test_driver_has_bounded_cleanup_for_every_mutation(driver_source: str):
    # API policy baseline is re-asserted after the checks.
    assert "evidence.ai_cleanup" in driver_source
    assert "ensureOriginalPassword" in driver_source
    assert "local_models_cleanup" in driver_source
    assert "secondary.close()" in driver_source


def test_primary_prefers_the_real_login_form_and_records_the_fallback(driver_source: str):
    assert "await formLogin(formPage)" in driver_source
    assert 'mechanism: "real login form' in driver_source
    assert 'web_session: false' in driver_source
    assert "the real login form did not establish a session" in driver_source


def test_missing_capabilities_are_distinct_from_failures(driver_source: str):
    assert 'status: "missing"' in driver_source
    assert 'status: "skipped"' in driver_source
    # Required skips are incomplete, not a pass: nonzero exit 4 and an
    # explicit `incomplete` status.
    assert 'incomplete ? "incomplete" : "pass"' in driver_source
    assert '(incomplete ? 4 : 0)' in driver_source
    assert "a required check was skipped; WA-075 is not complete" in driver_source
    assert "required_skipped_ids" in driver_source
    assert 'completeness: status === "pass" ? "complete" : "incomplete"' in driver_source


def test_evidence_is_allowlisted_and_auth_bodies_are_never_persisted(driver_source: str):
    assert "BODY_EVIDENCE_ALLOWLIST" in driver_source
    assert "auth_response_bodies_persisted: false" in driver_source
    assert "setup_body_sample:" not in driver_source
    assert "setup_body_persisted: false" in driver_source
    assert "sanitizeEvidence" in driver_source
    assert "refusing to write evidence" in driver_source
    # The body allowlist must not include any auth endpoint.
    allowlist = driver_source.split("BODY_EVIDENCE_ALLOWLIST = new Set([", 1)[1].split("]);", 1)[0]
    assert "/api/auth" not in allowlist
    for path in (
        '"/api/chat/routing-stats"', '"/api/ai/provider-policy"',
        '"/api/ai/providers"', '"/api/local-models"',
    ):
        assert path in allowlist


def test_scratch_origins_are_pinned_and_identity_precedes_login(driver_source: str):
    assert "LOOPBACK_HOSTS" in driver_source
    assert "NON_SCRATCH_PORTS" in driver_source
    assert "verifyScratchIdentity" in driver_source
    assert "ATOM_WA075_WORLD" in driver_source
    # The identity check must be invoked before the login token is minted.
    assert driver_source.index("await verifyScratchIdentity()") < \
        driver_source.index("await loginToken(")
    assert "backend database" in driver_source
    assert "nothing was changed" in driver_source


def test_blocking_dialogs_and_abandoned_waits_cannot_kill_the_run(driver_source: str):
    # A fresh scratch admin gets the onboarding modal; it must be dismissed
    # through the UI and recorded, never hidden via localStorage.
    assert "dismissOnboardingDialog" in driver_source
    assert "Welcome to Atom" in driver_source
    assert "onboarding_dismissals" in driver_source
    # An abandoned waitForResponse must fail one check, not crash Node.
    assert "__wait_error" in driver_source


def test_driver_uses_the_pure_settings_contract_module(driver_source: str):
    assert "./lib/settings_contract.mjs" in driver_source
    assert "totpCode" in driver_source
    contract = (REPO / "scripts" / "acceptance" / "lib" / "settings_contract.mjs").read_text(
        encoding="utf-8")
    for name in ("normalizePolicy", "policyMode", "samePolicy", "routingStatsFrom",
                 "toNumber", "totpCode", "totpStepAtMs", "freshTotpStepDelayMs"):
        assert f"export function {name}" in contract


def test_sessions_revoke_targets_the_secondarys_own_session(driver_source: str):
    """Regression: a bootstrap login is a session row too.

    The old check required exactly one non-current row and clicked the first
    Revoke button. A scratch run registers the bootstrap API bearer as a
    session, so the primary page has two non-current rows; the check failed
    before acting, and clicking the first control would have revoked the
    wrong session.
    """
    section = driver_source.split('id: "sessions.revoke_disposable"', 1)[1] \
        .split('id: "account.page_loads"', 1)[0]
    assert "./lib/session_selection.mjs" in driver_source
    assert "selectDisposableSession({ secondaryRows, primaryRows })" in section
    assert "secondaryLogin.token" in section
    assert "revokeButtons.nth(selection.controlIndex).click()" in section
    assert "revokeButtons.first().click()" not in section
    assert "expected exactly one revocable" not in section
    # The primary must still be authenticated and still own a listed row.
    assert "primaryMe.status === 200" in section
    assert "primary_row_present_after" in section


def test_session_selection_ignores_the_bootstrap_row(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    script = (
        'import { ownCurrentSession, revocableRows, selectDisposableSession } '
        'from "./scripts/acceptance/lib/session_selection.mjs";'
        'const secondaryRows = ['
        '  {id:"bootstrap", is_current:false},'
        '  {id:"primary", is_current:false},'
        '  {id:"disposable", is_current:true},'
        '];'
        'const primaryRows = ['
        '  {id:"bootstrap", is_current:false},'
        '  {id:"primary", is_current:true},'
        '  {id:"disposable", is_current:false},'
        '];'
        'const picked = selectDisposableSession({secondaryRows, primaryRows});'
        'const ambiguous = selectDisposableSession({'
        '  secondaryRows:[{id:"a",is_current:true},{id:"b",is_current:true}],'
        '  primaryRows});'
        'console.log(JSON.stringify({'
        'picked, own: ownCurrentSession(secondaryRows),'
        'revocable: revocableRows(primaryRows).map((r) => r.id), ambiguous,'
        '}));'
    )
    proc = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=str(REPO), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["own"]["id"] == "disposable"
    assert payload["revocable"] == ["bootstrap", "disposable"]
    assert payload["picked"]["ok"] is True
    assert payload["picked"]["id"] == "disposable"
    # The bootstrap row is first among the revocable controls; the disposable
    # row must be addressed by its exact index, not by position alone.
    assert payload["picked"]["controlIndex"] == 1
    assert payload["ambiguous"]["ok"] is False


def test_totp_matches_rfc6238_vectors():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    # The RFC 6238 SHA-1 seed is the ASCII string "12345678901234567890";
    # derive its RFC 4648 base32 form at runtime instead of hardcoding a
    # credential-shaped literal.
    seed = base64.b32encode(b"12345678901234567890").decode("ascii")
    script = (
        'import { totpCode } from "./scripts/acceptance/lib/settings_contract.mjs";'
        f'const s = "{seed}";'
        'console.log(totpCode(s, 59 * 1000), totpCode(s, 1111111109 * 1000));'
    )
    proc = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=str(REPO), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    # RFC 6238 SHA-1 vectors 94287082 / 07081804 truncated to six digits.
    assert proc.stdout.strip() == "287082 081804"


def test_fresh_totp_step_delay_waits_out_the_consumed_step():
    """Regression: enable burns a TOTP step; disable must spend the next one.

    The backend refuses a second use of the same step (409). The harness waits
    for the clock instead of computing a future-step code, which pyotp would
    reject against the server's current step. The clock is injected here so
    the boundary cases are deterministic and no real time passes.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    # GitGuardian hygiene: never commit a credential-shaped literal; the
    # fixture secret is derived at runtime (RFC 4648 base32, pyotp's default
    # 16-char length). It is deterministic so the enable/next code comparison
    # below cannot collide by chance.
    secret = base64.b32encode(b"wa075-fixt").decode("ascii")
    script = (
        'import { freshTotpStepDelayMs, totpCode, totpStepAtMs } '
        'from "./scripts/acceptance/lib/settings_contract.mjs";'
        f'const secret = "{secret}";'
        'const consumed = 1200 * 1000;'
        'const same = freshTotpStepDelayMs(consumed, {nowMs: consumed});'
        'const near = freshTotpStepDelayMs(consumed, {nowMs: consumed + 29900});'
        'const late = freshTotpStepDelayMs(consumed, {nowMs: consumed + 30100});'
        'const margin = freshTotpStepDelayMs(consumed,'
        '  {nowMs: consumed, marginMs: 250});'
        'const skewed = freshTotpStepDelayMs(consumed, {nowMs: consumed - 5000});'
        'const next = consumed + same;'
        'console.log(JSON.stringify({same,near,late,margin,skewed,'
        'enable:totpCode(secret,consumed),next:totpCode(secret,next),'
        'before:totpStepAtMs(consumed),after:totpStepAtMs(next)}));'
    )
    proc = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=str(REPO), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    # A code spent at the start of a step needs the whole period to expire.
    assert payload["same"] == 30_000
    # The wait ends at the next boundary, never before it.
    assert payload["near"] == 100
    assert payload["margin"] == 30_250
    # Already past the boundary: no extra sleep, but the step did advance.
    assert payload["late"] == 0
    assert payload["skewed"] == 35_000
    assert payload["after"] == payload["before"] + 1
    # The fresh code is for the later step, not a precomputed future value.
    assert payload["next"] != payload["enable"]


def test_routing_and_policy_normalizers_are_exact():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    script = (
        'import { normalizePolicy, policyMode, samePolicy, routingStatsFrom, toNumber } '
        'from "./scripts/acceptance/lib/settings_contract.mjs";'
        'const p = normalizePolicy({mode:"selected",allowed_providers:["b","a"],preferred:null});'
        'const r = routingStatsFrom({enabled:false,ema_enabled:false,'
        'stats:{feedback_samples:3,model_success_rates:{x:1}}});'
        'console.log(JSON.stringify({p,same:samePolicy({mode:"automatic"},'
        '{mode:"automatic",allowed_providers:[]}),'
        'unsetEqualsAutomatic:samePolicy({mode:"unset"},{mode:"automatic"}),'
        'unsetMode:policyMode("unset"),r,n:toNumber("1,234")}));'
    )
    proc = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=str(REPO), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["p"]["allowed_providers"] == ["a", "b"]
    assert payload["same"] is True
    assert payload["unsetEqualsAutomatic"] is True
    assert payload["unsetMode"] == "automatic"
    assert payload["r"]["feedback_samples"] == 3
    assert payload["r"]["enabled"] is False
    assert payload["n"] == 1234


# ---------------------------------------------------------------------------
# 2FA setup response interpretation
# ---------------------------------------------------------------------------

def _extract_js_function(source: str, name: str) -> str:
    """Return one top-level `function name(...) { ... }` block from the driver.

    The driver is a script: importing it would start a browser run. The pure
    2FA parser is therefore copied out verbatim and executed in a throwaway
    module, so the regression is proven against the real implementation
    without launching anything.
    """
    start = source.index(f"function {name}(")
    end = source.index("\n}\n", start) + len("\n}\n")
    return source[start:end]


def test_two_factor_reversible_waits_for_a_fresh_step_after_enable(driver_source: str):
    """Regression: enable and disable must not spend the same TOTP step.

    The old driver computed all three codes with `totpCode(secret)`, so a run
    whose enable/disable fell inside one 30-second window got the backend's
    409 and cascaded into the password checks. Each later request now waits
    for a step after every step already consumed.
    """
    section = driver_source.split('id: "account.two_factor_reversible"', 1)[1] \
        .split("if (SKIP_PASSWORD)", 1)[0]
    assert "totpCode(secret)" not in section
    assert "totpCode(secret, enableAtMs)" in section
    assert "totpCode(secret, disableAtMs)" in section
    assert "totpCode(secret, cleanupAtMs)" in section
    assert "freshTotpStepDelayMs(enableCompletedAtMs" in section
    assert "Math.max(enableCompletedAtMs, disableCompletedAtMs)" in section
    # Each wait must be computed from the response that spent the step and
    # must happen before the next code is spent.
    assert section.index("freshTotpStepDelayMs(enableCompletedAtMs") \
        < section.index("totpCode(secret, disableAtMs)")
    assert section.index("Math.max(enableCompletedAtMs, disableCompletedAtMs)") \
        < section.index("totpCode(secret, cleanupAtMs)")
    # Never bypass the backend guard by sending a future-step code.
    assert "totpCode(secret, Date.now() +" not in section
    assert "totp_step_waits_ms" in section


def test_two_factor_setup_parses_the_full_body_before_judging_it(driver_source: str):
    """Regression: the live setup body does not fit in a 300-byte sample.

    POST /api/auth/2fa/setup answers 200 with a secret, an otpauth:// URL and
    the write-service receipt. Slicing that text to 300 chars before
    JSON.parse() made every successful setup look like a non-JSON answer, and
    the check then explained it with a routing claim that was no longer true.
    """
    section = driver_source.split('id: "account.two_factor_surface"', 1)[1] \
        .split('id: "account.two_factor_reversible"', 1)[0]
    assert "interpretTwoFactorSetup(" in section
    # The body is parsed whole; truncation for display is not allowed to feed
    # the parse or the reachability decision.
    assert ".slice(0, 300)" not in section
    assert "JSON.parse" in _extract_js_function(driver_source, "interpretTwoFactorSetup")
    # Diagnose from the captured status/parse outcome, not a fixed story.
    assert "the tab's 2FA setup call is not routed" not in driver_source
    assert "fall into the NextAuth catch-all" not in driver_source
    # No part of the auth response body may be persisted.
    assert "setup_body_persisted: false" in section
    for raw in ("setup_body_sample:", "setup_raw:", "setup_full_text:",
                "response_body:", "setup_text:"):
        assert raw not in section


def test_two_factor_setup_interpretation_reports_the_real_outcome(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    source = DRIVER.read_text(encoding="utf-8")
    helpers = "\n\n".join(
        _extract_js_function(source, name)
        for name in ("interpretTwoFactorSetup", "describeTwoFactorSetup"))
    module = tmp_path / "two_factor_setup.mjs"
    module.write_text(
        f"{helpers}\n\nexport {{ describeTwoFactorSetup, interpretTwoFactorSetup }};\n",
        encoding="utf-8")

    # GitGuardian hygiene: never commit a credential-shaped literal; the
    # fixture secret is generated at runtime (RFC 4648 base32, pyotp's
    # default 16-char length).
    secret = base64.b32encode(secrets.token_bytes(10)).decode("ascii")
    live_payload = {
        "secret": secret,
        "otpauth_url": (
            f"otpauth://totp/Atom:admin@example.com?secret={secret}"
            "&issuer=Atom&algorithm=SHA1&digits=6&period=30&padding="
            + "p" * 120
        ),
        "operation_id": "op-" + "0" * 40,
        "status": "committed",
        "verification": {"status": "verified", "checks": ["a", "b", "c"]},
    }
    cases = {
        "live_200": {
            "status": 200, "contentType": "application/json",
            "text": json.dumps(live_payload),
        },
        "json_without_secret": {
            "status": 200, "contentType": "application/json",
            "text": json.dumps({"detail": "2FA is already enabled"}),
        },
        "html_200": {
            "status": 200, "contentType": "text/html; charset=utf-8",
            "text": "<!DOCTYPE html><html><body>Sign in to continue</body></html>",
        },
        "refused_409": {
            "status": 409, "contentType": "application/json",
            "text": json.dumps({"detail": "2FA setup is not pending"}),
        },
    }
    # The fixture must actually reproduce the old failure: a 300-char prefix
    # of the live body is not parseable JSON.
    assert len(cases["live_200"]["text"].encode()) > 300
    with pytest.raises(json.JSONDecodeError):
        json.loads(cases["live_200"]["text"][:300])

    script = (
        "import { interpretTwoFactorSetup, describeTwoFactorSetup } from "
        f"{json.dumps(module.as_uri())};"
        f"const cases = {json.dumps(cases)};"
        "const out = {};"
        "for (const [key, value] of Object.entries(cases)) {"
        "  const r = interpretTwoFactorSetup(value);"
        "  out[key] = {http: r.http, bytes: r.body_bytes, parsed: r.json_parsed,"
        "    secret: r.secret, returned: r.secret_returned,"
        "    persisted: r.body_persisted, detail: r.error_detail_present,"
        "    reason: describeTwoFactorSetup(r)};"
        "}"
        "console.log(JSON.stringify(out));"
    )
    proc = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)

    live = out["live_200"]
    assert live["parsed"] is True
    assert live["returned"] is True
    assert live["bytes"] > 300
    assert live["secret"] == secret
    assert live["reason"] is None
    assert live["persisted"] is False

    no_secret = out["json_without_secret"]
    assert no_secret["parsed"] is True
    assert no_secret["returned"] is False
    assert "carried no secret" in no_secret["reason"]

    html = out["html_200"]
    assert html["parsed"] is False
    assert html["returned"] is False
    assert "HTTP 200" in html["reason"]
    assert "not JSON" in html["reason"]
    assert "not routed" not in html["reason"]

    refused = out["refused_409"]
    assert refused["http"] == 409
    assert "HTTP 409" in refused["reason"]
    assert refused["detail"] is True
    assert refused["returned"] is False

    # `secret` is returned only so the caller can register it for redaction;
    # everything that can be persisted (the diagnostics and derived facts)
    # must be free of both the secret and the provisioning URL.
    for name, payload in out.items():
        facts = {k: v for k, v in payload.items() if k != "secret"}
        assert secret not in json.dumps(facts), f"{name} leaked the setup secret"
        assert "otpauth" not in json.dumps(facts), f"{name} leaked the otpauth URL"


# ---------------------------------------------------------------------------
# Preflight pure refusals
# ---------------------------------------------------------------------------

def _scratch_world(preflight_module, tmp_path: Path) -> Path:
    root = preflight_module.configured_worlds_root(REPO)
    return root / f"pytest-wa075-{tmp_path.name}"


def test_world_layout_accepts_a_scratch_world_under_the_configured_root(preflight, tmp_path):
    world = _scratch_world(preflight, tmp_path)
    result = preflight.check_world_layout(world, REPO)
    assert result["ok"] is True, result
    assert result["database"] == str(world.resolve() / "atom.db")
    assert result["database_is_live_dev_db"] is False


def test_world_layout_refuses_the_live_data_tree(preflight):
    result = preflight.check_world_layout(REPO / "backend" / "data", REPO)
    assert result["ok"] is False
    assert result["problems"]


def test_world_layout_refuses_the_repository_root(preflight):
    result = preflight.check_world_layout(REPO, REPO)
    assert result["ok"] is False


def test_world_layout_refuses_a_path_outside_the_worlds_root(preflight, tmp_path):
    result = preflight.check_world_layout(tmp_path / "outside-world", REPO)
    assert result["ok"] is False
    assert any("worlds root" in p for p in result["problems"])


def test_database_isolation_refuses_the_live_sqlite_db(preflight):
    url = f"sqlite:///{REPO / 'backend' / 'data' / 'atom.db'}"
    result = preflight.check_database_isolation(url, REPO)
    assert result["ok"] is False


def test_database_isolation_accepts_a_scratch_sqlite_file(preflight, tmp_path):
    result = preflight.check_database_isolation(f"sqlite:///{tmp_path / 'atom.db'}", REPO)
    assert result["ok"] is True
    assert result["source"] == "sqlite"


def test_database_isolation_accepts_unset(preflight):
    assert preflight.check_database_isolation(None, REPO)["ok"] is True


def test_storage_guard_bypass_is_never_accepted(preflight, monkeypatch):
    monkeypatch.setenv("ATOM_WORLD_STORAGE_BYPASS", "1")
    result = preflight._guard_check()
    assert result["ok"] is False
    assert "BYPASS" in result["reason"]


def test_storage_root_honours_the_guard_relocation_env(
        preflight, monkeypatch, tmp_path):
    """The preflight must resolve the SAME config the guard will read.

    Regression: reading only backend/config/world_storage.json while
    ATOM_WORLD_STORAGE_PATHS pointed the guard at a relocated config let the
    guard accept a root the preflight then refused.
    """
    config_dir = tmp_path / "isolated-config"
    config_dir.mkdir()
    worlds_root = tmp_path / "isolated-worlds"
    (config_dir / "world_storage.json").write_text(json.dumps({
        "enabled": True,
        "layout": "local",
        "worlds": {"root": str(worlds_root)},
    }), encoding="utf-8")
    monkeypatch.setenv("ATOM_WORLD_STORAGE_PATHS", str(config_dir))

    source = preflight.storage_config_source(REPO)
    assert source["relocated_by_env"] is True
    assert source["config_path"] == str(config_dir / "world_storage.json")
    assert preflight.configured_worlds_root(REPO) == worlds_root.resolve()

    world = worlds_root / "wa075-relocated"
    layout = preflight.check_world_layout(world, REPO)
    assert layout["ok"] is True, layout
    assert layout["configured_worlds_root"] == str(worlds_root.resolve())


def test_storage_root_without_the_env_stays_the_checkout_config(preflight, monkeypatch):
    monkeypatch.delenv("ATOM_WORLD_STORAGE_PATHS", raising=False)
    source = preflight.storage_config_source(REPO)
    assert source["relocated_by_env"] is False
    assert source["config_path"] == str(REPO / "backend" / "config" / "world_storage.json")
    assert preflight.configured_worlds_root(REPO) == \
        (REPO / "backend" / "data" / "acceptance_worlds").resolve()


def test_capability_report_blocks_every_tab_without_a_frontend(preflight):
    deps = {
        "frontend_node_modules": False, "playwright_module": False,
        "frontend_build_id": False, "chrome_app": True, "node": "/usr/bin/node",
    }
    caps = preflight._capability_report(
        deps, {"ok": True}, {"ok": True}, stack_running=False)
    assert {v["status"] for v in caps.values()} == {"blocked"}
    assert set(caps) == set(preflight.TAB_CHECKS)


def test_capability_report_marks_env_managed_policy_as_blocked(
        preflight, monkeypatch):
    monkeypatch.setenv("ATOM_LLM_PROVIDER_POLICY", "selected:ollama")
    deps = {
        "frontend_node_modules": True, "playwright_module": True,
        "frontend_build_id": True, "chrome_app": True, "node": "/usr/bin/node",
    }
    caps = preflight._capability_report(
        deps, {"ok": True}, {"ok": True}, stack_running=False)
    assert caps["ai"]["status"] == "blocked"
    assert "ATOM_LLM_PROVIDER_POLICY" in caps["ai"]["reason"]
    assert caps["account"]["status"] == "ready"
    assert caps["local_models"]["status"] == "ready"


def test_preflight_report_never_records_the_password_value(
        preflight, monkeypatch, tmp_path):
    # Runtime-random so the assertion holds for any value the file contains,
    # and so no scratch credential ever appears as a literal in this source.
    secret = secrets.token_urlsafe(24)
    pw_file = tmp_path / "admin_password"
    pw_file.write_text(secret + "\n", encoding="utf-8")
    pw_file.chmod(0o600)

    monkeypatch.setattr(preflight, "_guard_check", lambda: {"ok": True, "returncode": 0})
    monkeypatch.setattr(preflight, "_port_free", lambda port: True)
    monkeypatch.setattr(preflight, "dependency_report", lambda frontend: {
        "python": "test", "python_modules": {}, "node": "/usr/bin/node",
        "chrome_app": True, "frontend_dir": str(frontend),
        "frontend_node_modules": True, "playwright_module": True,
        "frontend_build_id": True, "frontend_env_local": False,
        "nextauth_secret_env": False,
    })
    world = _scratch_world(preflight, tmp_path)

    import argparse
    args = argparse.Namespace(
        world=str(world), frontend_dir=str(REPO / "frontend-nextjs"),
        backend_port=8105, frontend_port=3001, min_free_mb=1,
        admin_password_file=str(pw_file), stack_running=False, report=None,
    )
    report = preflight.build_report(args)
    blob = json.dumps(report)
    assert secret not in blob
    assert report["admin_password"]["value_recorded"] is False
    assert report["admin_password"]["mode"] == "0o600"
    assert report["ok"] is True, report["blockers"]


def test_preflight_never_writes_without_report(preflight, tmp_path):
    """build_report is pure: no directories are created for the world."""
    world = _scratch_world(preflight, tmp_path)
    before = sorted(p.name for p in preflight.configured_worlds_root(REPO).iterdir()) \
        if preflight.configured_worlds_root(REPO).is_dir() else []
    import argparse
    args = argparse.Namespace(
        world=str(world), frontend_dir=str(REPO / "frontend-nextjs"),
        backend_port=8105, frontend_port=3001, min_free_mb=1,
        admin_password_file=None, stack_running=False, report=None,
    )
    preflight.build_report(args)
    after = sorted(p.name for p in preflight.configured_worlds_root(REPO).iterdir()) \
        if preflight.configured_worlds_root(REPO).is_dir() else []
    assert world.name not in after
    assert before == after


def test_preflight_requires_an_explicit_world(preflight):
    with pytest.raises(SystemExit):
        preflight.main([])


# ---------------------------------------------------------------------------
# Scratch password recovery guard (used when a rotation is interrupted)
# ---------------------------------------------------------------------------

def _load_scratch_password():
    path = REPO / "scripts" / "acceptance" / "scratch_admin_password.py"
    spec = importlib.util.spec_from_file_location("scratch_admin_password", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_scratch_password_refuses_the_live_database():
    module = _load_scratch_password()
    allowed, reason = module.authorized_world_database(
        f"sqlite:///{REPO / 'backend' / 'data' / 'atom.db'}")
    assert allowed is False
    assert "live dev database" in reason


def test_scratch_password_refuses_non_sqlite_and_unknown_paths():
    module = _load_scratch_password()
    assert module.authorized_world_database("postgresql://host/db")[0] is False
    assert module.authorized_world_database(
        f"sqlite:///{REPO / 'tmp' / 'elsewhere' / 'atom.db'}")[0] is False


def test_scratch_password_allows_a_configured_scratch_world(tmp_path):
    module = _load_scratch_password()
    world = module._configured_worlds_root(REPO) / f"pytest-recovery-{tmp_path.name}"
    allowed, reason = module.authorized_world_database(
        f"sqlite:///{world / 'atom.db'}")
    assert allowed is True, reason

    # A database directly in the worlds root is not a world.
    assert module.authorized_world_database(
        f"sqlite:///{module._configured_worlds_root(REPO) / 'atom.db'}")[0] is False
    # A different filename inside a world is not the world database.
    assert module.authorized_world_database(
        f"sqlite:///{world / 'other.db'}")[0] is False


def test_scratch_password_honours_the_relocation_env(tmp_path, monkeypatch):
    module = _load_scratch_password()
    config_dir = tmp_path / "recovery-config"
    config_dir.mkdir()
    worlds_root = tmp_path / "recovery-worlds"
    (config_dir / "world_storage.json").write_text(json.dumps({
        "enabled": True, "layout": "local",
        "worlds": {"root": str(worlds_root)},
    }), encoding="utf-8")
    monkeypatch.setenv("ATOM_WORLD_STORAGE_PATHS", str(config_dir))

    world = worlds_root / "recovery-world"
    assert module._configured_worlds_root(REPO) == worlds_root.resolve()
    allowed, reason = module.authorized_world_database(
        f"sqlite:///{world / 'atom.db'}")
    assert allowed is True, reason
    assert module.authorized_world_database(
        f"sqlite:///{REPO / 'backend' / 'data' / 'acceptance_worlds' / 'w' / 'atom.db'}"
    )[0] is False

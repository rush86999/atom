"""
Round 21 TDD bug hunt — BUG-091: `/enable` and `/disable` 2FA endpoints lack rate limiting.

The module docstring in `api/auth_2fa_routes.py` states the rate limiter exists for
"2FA code verification endpoints — prevents brute-forcing TOTP codes (6 digits = 1M
combinations in a 30s window)". However `totp_rate_limit` was only wired onto
`verify_action_2fa`. The `/enable` and `/disable` endpoints BOTH call
`pyotp.TOTP.verify(...)` (a TOTP brute-force surface) with no lockout:

- `/disable` is the critical one: an attacker with a stolen session can guess the
  TOTP code to DISABLE the victim's 2FA, with unlimited attempts.
- `/enable` verifies a code against the just-generated secret, also unthrottled.

TDD: write the failing assertion first (red), then wire `totp_rate_limit` onto both
endpoints (green). Mirrors the existing `verify_action_2fa` rate-limit test in
`tests/test_round16_fixes.py`.
"""
import inspect


def _rate_limited_dep_names(func) -> list:
    """Return names of FastAPI dependencies whose callable contains 'rate_limit'."""
    deps = [
        p.default
        for p in inspect.signature(func).parameters.values()
        if p.default is not inspect.Parameter.empty
        and hasattr(p.default, "dependency")
    ]
    return [
        getattr(getattr(d, "dependency", None), "__name__", "")
        for d in deps
    ]


class Test2FAEnableDisableRateLimited:
    """TOTP-verifying 2FA endpoints must be rate-limited (anti-brute-force)."""

    def test_enable_2fa_has_rate_limit(self):
        from api import auth_2fa_routes

        dep_names = _rate_limited_dep_names(auth_2fa_routes.enable_2fa)
        assert any("rate_limit" in n for n in dep_names), (
            f"enable_2fa has no rate limit; deps: {dep_names}"
        )

    def test_disable_2fa_has_rate_limit(self):
        from api import auth_2fa_routes

        dep_names = _rate_limited_dep_names(auth_2fa_routes.disable_2fa)
        assert any("rate_limit" in n for n in dep_names), (
            f"disable_2fa has no rate limit; deps: {dep_names}"
        )

    def test_rate_limiter_is_the_totp_limiter(self):
        """The wired dependency must be the TOTP-specific limiter (5/min)."""
        from api import auth_2fa_routes

        for endpoint in (auth_2fa_routes.enable_2fa, auth_2fa_routes.disable_2fa):
            dep_names = _rate_limited_dep_names(endpoint)
            matching = [n for n in dep_names if "rate_limit" in n]
            assert matching, f"{endpoint.__name__} is not rate-limited"
            # Resolve the dependency callable and confirm it is totp_rate_limit.
            resolved = getattr(
                endpoint, "__depends__", None
            )
            # The default object holds the dependency; compare its __name__.
            assert matching[0] == "totp_rate_limit", (
                f"{endpoint.__name__} wired {matching[0]}, expected totp_rate_limit"
            )

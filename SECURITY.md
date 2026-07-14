# Security Policy

## Supported Versions

Atom is under active development. Security fixes are applied to the latest
`main` branch and included in the next release.

| Version | Supported |
|---------|-----------|
| latest main | ✅ |
| older releases | ❌ |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please report security issues responsibly:

1. Email **security@atomagentos.com** with a description of the vulnerability
2. Include steps to reproduce (proof of concept if possible)
3. We will acknowledge within 48 hours
4. We will investigate and provide a fix timeline within 7 days
5. Once fixed, we will credit you (unless you prefer to remain anonymous)

## Security Features

Atom includes several security layers:

- **BYOK (Bring Your Own Key)**: API keys are Fernet-encrypted at rest
- **Agent Governance**: 4-tier maturity system (Student → Autonomous) with
  human-in-the-loop approval for dangerous actions
- **Execution Sandbox**: 5-phase isolation (policy, filesystem scope,
  tripwires, resource caps, provenance tagging)
- **Auth**: JWT with refresh-token rotation, rate limiting on auth endpoints
- **CSRF Protection**: Middleware with bypass gated to test environment only
- **Input Validation**: Message length limits, SQL injection prevention

## Disclosure Timeline

1. You report the vulnerability privately
2. We confirm and develop a fix
3. Fix is released
4. Public disclosure (after fix is available, typically 30-90 days)

Thank you for helping keep Atom secure.

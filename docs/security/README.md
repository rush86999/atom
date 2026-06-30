# Security Documentation

Security best practices, compliance, and package security.

## 📚 Quick Navigation

### Core Security
- **[Security Overview](SECURITY_OVERVIEW.md)** - Security architecture overview
- **[Authentication](AUTHENTICATION.md)** - OAuth 2.0 and session management
- **[Data Protection](DATA_PROTECTION.md)** - Encryption and secrets management
- **[Compliance](COMPLIANCE.md)** - GDPR, SOC2, HIPAA considerations

### Agent Runtime Security
- **[Trust Tier ≠ Security Boundary](TRUST_VS_SANDBOX.md)** ⚠️ — Why the
  maturity graduation system is a *routing* decision, not a *security*
  decision. Read this before treating `AUTONOMOUS` as a safety claim.
- **[Prompt Injection Defense Plan](PROMPT_INJECTION_DEFENSE_PLAN.md)** ✅ —
  Engineering plan for the deterministic sandbox layer (filesystem scope,
  tool whitelist, egress allowlist, resource caps, tripwires) required to
  bound agent blast radius. **Implemented Rounds 43-47** — see the shipped
  design at [../architecture/SANDBOX_LAYER.md](../architecture/SANDBOX_LAYER.md).
- **[Execution Sandbox Layer](../architecture/SANDBOX_LAYER.md)** ✨ —
  Authoritative design doc for the five-phase blast-radius layer (Phases
  A-E). Ships in shadow mode by default; covers Firecracker microVM
  isolation, dual-proxy egress, tripwire registry, KillRun state machine,
  provenance tagging, and LLM ActionJudge.

### Package Security
- **[Packages](packages.md)** - Package security overview
- **[Python Packages](python-packages-guide.md)** - Python package support (350K+ packages)
- **[npm Packages](npm-packages.md)** - npm package support (2M+ packages)
- **[Package Governance](package-governance.md)** - Maturity-based access control

### Integration Security
- **[Webhook Verification](WEBHOOK_VERIFICATION.md)** - Slack, Teams, Gmail webhook security

### Security Advisories
- **[Security Advisory 2025-03-23](SECURITY_ADVISORY_2025-03-23.md)** - Security updates

## 🔒 Security Features

### Authentication & Authorization
- **OAuth 2.0**: Secure third-party authentication
- **Session Management**: Secure session handling
- **Agent Maturity Routing**: 4-tier graduation (STUDENT → AUTONOMOUS) routes
  work to appropriate approval workflows. **Routing only — not a security
  boundary.** See [TRUST_VS_SANDBOX.md](TRUST_VS_SANDBOX.md).
- **API Security**: Bearer token authentication

### Data Protection
- **Encryption**: Fernet encryption for sensitive data
- **Secrets Management**: Secure credential storage
- **PII Redaction**: Automatic redaction of personal information
- **Audit Logs**: Complete audit trail

### Package Security
- **Vulnerability Scanning**: pip-audit + Safety for Python
- **Supply Chain Protection**: Dependency confusion prevention
- **Maturity Gates**: STUDENT blocked, INTERN requires approval
- **Container Security**: Network disabled, read-only filesystem

### Webhook Security
- **Signature Verification**: HMAC-based webhook validation
- **Timestamp Checks**: Replay attack prevention
- **Payload Validation**: Request validation

## 🛡️ Security Best Practices

### Development
- Never commit secrets to repository
- Use environment variables for configuration
- Enable security headers in production
- Regular dependency updates

### Deployment
- Enable HTTPS in production
- Configure firewall rules
- Use secrets management service
- Enable audit logging

### Operations
- Regular security audits
- Monitor for suspicious activity
- Keep dependencies updated
- Review access logs

## 📖 Related Documentation

- **[Operations](../operations/README.md)** - Security operations
- **[Package Governance](package-governance.md)** - Package access control
- **[Compliance](COMPLIANCE.md)** - Regulatory compliance

## 🔗 Security Resources

- **Report Vulnerabilities**: [GitHub Security Advisories](https://github.com/rush86999/atom/security/advisories)
- **Security Policy**: See SECURITY.md

---

*Last Updated: April 12, 2026*

# Contributing to Atom

Thank you for your interest in contributing to Atom, the AI-powered business automation platform!

## Getting Started

### Development Setup

See [docs/development/DEVELOPMENT_SETUP.md](docs/development/DEVELOPMENT_SETUP.md) for complete development setup instructions, including:
- Security requirements
- Testing procedures
- Deployment guidelines
- Background task queue setup

### Quick Start

```bash
# Clone the repository
git clone https://github.com/rush86999/atom.git
cd atom

# Backend deps in a venv
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure (every var has a default; set SECRET_KEY + one LLM key)
cp .env.example .env
# Full reference: docs/reference/ENVIRONMENT_VARIABLES.md

# Run tests
pytest tests/ -v

# Start the FULL backend (main_api_app:app, all 80+ routers) — from repo root
cd ..
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
```

> The canonical entrypoint is `main_api_app:app` (in `backend/main_api_app.py`).
> `minimal_app:app` is a ~125-route smoke subset only — do not use it for
> feature work. Run from the **repo root** with `PYTHONPATH=$PWD:$PWD/backend`
> so both bare and `backend.*` imports resolve.

## Security Guidelines

### NEVER Commit These Files

**CRITICAL**: The following files and directories contain sensitive information and must NEVER be committed to the repository:

- **`.claude/`** - Contains Claude Code API keys and sensitive configuration
- **`.env` files** - All environment variables with API keys, secrets, and credentials
- **`secrets.json`** - Any secret keys or tokens
- **`*.pem`, `*.key`** - SSL/TLS certificates and private keys
- **`credentials.json`** - OAuth credentials and API keys
- **`backend/token.json`** - Authentication tokens

These are already in `.gitignore`, but always verify with `git status` before committing.

### If You Accidentally Commit Secrets

If you accidentally commit sensitive information:

1. **Immediately rotate the compromised keys** - Change API keys, passwords, tokens
2. **Remove from git history** - Use `git filter-repo` or BFG Repo-Cleaner (NOT just `git rm`)
3. **Force push carefully** - Only after confirming history is clean
4. **Notify maintainers** - Inform the team immediately

Example cleanup command (use with caution):
```bash
# Remove file from history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .claude/settings.local.json" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (ONLY after confirming)
git push origin --force --all
```

### Code Security

- Never hardcode API keys, credentials, or secrets
- Use environment variables for all sensitive configuration
- Follow OWASP security guidelines
- Validate and sanitize all user inputs
- Keep dependencies updated and scan for vulnerabilities

## Contribution Guidelines

### Making Changes

1. **Fork the repository** and create your feature branch
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our code standards
   - Follow existing code style and patterns
   - Add tests for new functionality
   - Update documentation as needed

3. **Test thoroughly**
```bash
# Run all backend tests (from backend/, using the venv)
cd backend && ../backend/venv/bin/python -m pytest tests/ -v

# Run specific test files
./backend/venv/bin/python -m pytest tests/test_governance_streaming.py -v
```

4. **Commit your changes** with clear, descriptive messages
   ```bash
   git add .
   git commit -m "feat: add description of your changes"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Code Standards

- **Python**: Follow PEP 8 guidelines
- **TypeScript/React**: Follow existing patterns in `frontend-nextjs/`
- **Tests**: Maintain test coverage above 80%
- **Documentation**: Update relevant docs in `docs/` directory

#### Conventions learned from past bugs

These come from real defects found by the user-journey suite (full stories in
[`docs/architecture/BUGS_FOUND_AND_FIXED.md`](docs/architecture/BUGS_FOUND_AND_FIXED.md)).
Following them prevents the most common regressions:

- **Never `include_router(...)` with a prefix the router already declares.**
  If a router has `APIRouter(prefix="/api/foo")`, include it bare — otherwise
  the path doubles (`/api/v1/foo/api/foo/...`) and every endpoint 404s.
- **Backend response shape is `{success, data, ...}`** (the `BaseAPIRouter`
  wrapper). Frontend code that expects a bare array/object must unwrap `.data`.
- **`async` methods must be awaited.** A sync caller of an `async` scanner/LLM
  call gets a coroutine object and fails far from the call site
  (`'coroutine' object is not subscriptable`).
- **New roles added to `UserRole` must be added to
  `_get_role_permissions()`** in `core/rbac_service.py` — otherwise they get
  an empty permission set (worse than guest). A regression guard enforces this.
- **E2E `is_loaded()` checks should use `wait_for(state="attached")` or
  `wait_for_selector`, not bare `is_visible()`.** SSR content is in the DOM
  before hydration; visibility can lag and produce false negatives.
- **Don't guess the DB path from tests.** Use the backend's own
  `core.database.SessionLocal`, and in CI use an absolute `DATABASE_URL`.

### Areas Where We Need Help

- **Core Features**: Agent governance, episodic memory, canvas system
- **Integrations**: New service integrations (see [backend/docs/CONTRIBUTING_INTEGRATIONS.md](backend/docs/CONTRIBUTING_INTEGRATIONS.md))
- **Testing**: Test coverage and edge cases
- **Documentation**: Guides, examples, and API documentation
- **Mobile**: React Native implementation (see [mobile/docs/REACT_NATIVE_ARCHITECTURE.md](mobile/docs/REACT_NATIVE_ARCHITECTURE.md))

## Project Structure

```
atom/
├── backend/           # Python FastAPI backend
│   ├── core/         # Core services and models
│   ├── api/          # API endpoints
│   ├── tools/        # Agent tools
│   └── tests/        # Backend tests
├── frontend-nextjs/  # Next.js frontend
├── mobile/           # React Native mobile app
├── docs/             # Documentation
└── tests/            # Integration tests
```

## Documentation

- **[docs/INDEX.md](docs/INDEX.md)** - Complete documentation index
- **[docs/development/DEVELOPMENT_SETUP.md](docs/development/DEVELOPMENT_SETUP.md)** - Development setup guide
- **[backend/docs/CONTRIBUTING_INTEGRATIONS.md](backend/docs/CONTRIBUTING_INTEGRATIONS.md)** - Integration contribution guide
- **[CLAUDE.md](CLAUDE.md)** - Project architecture and context

## Code of Conduct

### Our Pledge

We are committed to making participation in our community a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**
- Being respectful and inclusive
- Welcoming new contributors
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Harassment or discriminatory language
- Personal attacks or insulting comments
- Public or private harassment
- Publishing others' private information without permission
- Unprofessional conduct

## Getting Help

### Resources

- **Documentation**: [docs/INDEX.md](docs/INDEX.md)
- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Architecture**: See [CLAUDE.md](CLAUDE.md) for project context

### Asking Questions

1. Check existing documentation first
2. Search existing GitHub issues
3. Create a new issue with:
   - Clear description of the question
   - Relevant code snippets
   - Steps already tried

## Pull Request Process

1. **Update documentation** if you've changed functionality
2. **Add tests** for new features or bug fixes
3. **Ensure all tests pass** before submitting
4. **Request review** from maintainers

### PR Checklist

- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages follow conventions
- [ ] PR description clearly explains changes

## License

By contributing to Atom, you agree that your contributions will be licensed under the same license as the project.

## Acknowledgments

Thank you for contributing to Atom! Every contribution helps make the platform better for everyone.

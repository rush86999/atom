# Scripts Directory

This directory contains utility scripts for development, testing, deployment, and maintenance of the Atom platform.

## Directory Structure

```
scripts/
├── dev/              # Development, testing, and debugging scripts
├── production/       # Production deployment and maintenance scripts
├── legacy/           # Obsolete or archived scripts (kept for reference)
├── README.md         # This file
└── [scripts]         # General utility scripts (to be categorized)
```

## Script Categories

### Development Scripts (`dev/`)

Scripts used during development for testing, debugging, and feature development:

- **Test Scripts**: `test_*.py`, `*_test.py`, `e2e_*.py`
- **Demo Scripts**: `demo_*.py`, `showcase_*.py`
- **Debug Scripts**: `debug_*.py`, `diagnose_*.py`
- **Feature Development**: `*_implementation.py`, `*_phase*.py`
- **Utilities**: Development helpers, data generators, mock data creators

**Examples**:
- `test_workspace_permissions.py` - Run permission tests
- `debug_governance.py` - Debug governance system
- `demo_canvas_features.py` - Showcase canvas capabilities

### Production Scripts (`production/`)

Scripts used in production environments for deployment and maintenance:

- **Deployment**: `deploy_*.py`, `production_*.py`
- **Database**: Migrations, seeders, backups
- **Monitoring**: Health checks, metrics collection
- **Maintenance**: Cleanup, optimization, verification

**Examples**:
- `deploy_production.py` - Deploy to production
- `seed_admin_user.py` - Create initial admin user
- `verify_integrations.py` - Check integration health

### Legacy Scripts (`legacy/`)

Obsolete or deprecated scripts kept for reference:

- **Old Implementations**: Superseded by new code
- **Deprecated Features**: Features no longer supported
- **Historical Reference**: For understanding past implementations

**Note**: Scripts in `legacy/` should NOT be used in production. They are kept only for reference.

## General Guidelines

### Adding New Scripts

1. **Choose the right category**:
   - Development/debugging → `dev/`
   - Production deployment → `production/`
   - Utility scripts → Root (to be categorized later)

2. **Name descriptively**:
   - ✅ `deploy_production.py`
   - ✅ `test_governance_permissions.py`
   - ❌ `script1.py`
   - ❌ `temp.py`

3. **Add docstring**:
   ```python
   """
   Script description.

   Usage:
       python script_name.py [args]

   Args:
       arg1: Description

   Examples:
       python script_name.py --arg1 value
   """
   ```

4. **Make executable** (if needed):
   ```bash
   chmod +x scripts/production/deploy.sh
   ```

### Removing Scripts

Before deleting a script, verify:

1. ✅ Not referenced in production code
2. ✅ Not used in CI/CD pipelines
3. ✅ Not documented in user guides
4. ✅ No active GitHub issues reference it

If unsure, move to `legacy/` instead of deleting.

## Migration Status

**Total Scripts**: 284
- ✅ Categorized: 0 (just started)
- 🔄 To categorize: ~280
- ❌ Obsolete: ~50 (estimated)

## Common Operations

### List all scripts
```bash
ls scripts/
```

### Find test scripts
```bash
ls scripts/dev/test_*.py
```

### Run a production deployment
```bash
python scripts/production/deploy.py --env production
```

### Search for scripts by keyword
```bash
ls scripts/ | grep -i oauth
```

## Maintenance

### Weekly Tasks
- [ ] Review root directory for uncategorized scripts
- [ ] Move completed feature scripts to `dev/`
- [ ] Archive obsolete scripts to `legacy/`

### Monthly Tasks
- [ ] Audit `legacy/` for scripts safe to delete
- [ ] Update README with new scripts
- [ ] Test production deployment scripts

## Related Documentation

- `docs/DEPLOYMENT.md` - Deployment procedures
- `docs/DEVELOPMENT.md` - Development setup
- `IMPLEMENTATION_COMPLETION_REPORT.md` - Recent changes

---

**Last Updated**: February 1, 2026
**Status**: Reorganization in progress

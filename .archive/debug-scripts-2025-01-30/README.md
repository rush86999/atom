# Archived: Debug and Test Scripts

**Archived Date**: 2025-01-30
**Reason**: Root directory cleanup to keep project structure minimal

## Files Archived

### Debug Scripts
- `debug_login.py` - Debug script for login functionality
- `debug_nlp.py` - Debug script for NLP features
- `debug_run_golden.py` - Debug script for golden path testing

### Utility Scripts
- `check_schema.py` - Database schema verification
- `convert_log.py` - Log file conversion utility
- `migrate_db.py` - Database migration script
- `verify_implementation.sh` - Implementation verification

### Test Outputs
- `bad_trace_simulation.json` - Test trace simulation data
- `results.json` - Test results output

## Why These Were Archived

These files were temporary debugging/testing scripts that:
1. Were used during development but not part of production code
2. Cluttered the root directory
3. Should be in `backend/scripts/` or `tests/` if needed
4. Can be restored from git history if necessary

## Keeping the Root Minimal

The root directory should only contain:
- Configuration files (.gitignore, docker-compose.yml, etc.)
- Documentation (README.md, CLAUDE.md, etc.)
- Main directories (backend/, frontend-nextjs/, scripts/, etc.)
- CI/CD configuration (.github/)

## Restoration

If you need any of these files:
```bash
# Find the commit before archival
git log --oneline --all | grep "archive.*debug"

# Restore specific file
git checkout <commit-before-archive> -- debug_login.py

# Or restore all archived files
mv .archive/debug-scripts-2025-01-30/* .
```

## Better Locations

If you need these scripts, consider:
- Debug scripts → `backend/scripts/debug/`
- Test scripts → `tests/` or `backend/tests/`
- Migration scripts → `backend/scripts/migrations/`
- Utilities → `backend/scripts/utils/`

## Git History

All files are preserved in git history. To see the original content:
```bash
git show <commit-hash>:debug_login.py
```

## Keep Until

**2025-07-30** (6 months from archival date)

After this date, if these scripts haven't been needed, the archive can be deleted.

---

**Archive Commit**: See git log for commit details
**Cleanup Commit**: See git log for commit details

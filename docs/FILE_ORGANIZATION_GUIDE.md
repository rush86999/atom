# File Organization Guide

## Overview

The ATOM project uses an automated file organization system to maintain a clean and consistent project structure. This system automatically categorizes files into appropriate directories based on predefined rules.

## Quick Start

### 1. Validate Current Structure
```bash
python scripts/organize-files.py --validate
```

This command checks if your current file structure complies with the organization rules and reports any violations.

### 2. Organize Files Automatically
```bash
python scripts/organize-files.py --organize
```

This command automatically moves files to their correct locations based on the rules defined in `.file-organization-rules.json`.

### 3. Preview Changes (Dry Run)
```bash
python scripts/organize-files.py --organize --dry-run
```

Use this to see what changes would be made without actually moving any files.

## File Organization Rules

### Core Categories

| Category | Description | File Patterns |
|----------|-------------|---------------|
| `docs/` | Documentation | `*.md`, `*.txt` |
| `scripts/` | Shell scripts | `*.sh` |
| `tests/` | Test files | `test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*` |
| `backups/` | Backup directories | `backup_*` |
| `logs/` | Log files | `*.log` |
| `temp/` | Temporary files | `*.pid`, cache directories |
| `deployment/` | Deployment config | `docker-compose.*` |
| `integration-tests/` | Test results | `*_test_results.json` |
| `config/` | Configuration | `*.json`, `*.env*` |
| `data/` | Database schemas | `*.sql` |

### Protected Files & Directories

The following are protected from automatic organization:

**Protected Files:**
- `README.md`
- `package.json`
- `tsconfig.json`
- `yarn.lock`
- `Pipfile.lock`
- `fly.toml`
- `.gitignore`, `.gitattributes`, `.gitmodules`
- `LICENSE.md`

**Protected Directories:**
- `.github`, `.git`, `.vscode`
- `node_modules`, `venv`, `.venv`
- `__pycache__`, `dist`, `build`, `target`
- `coverage`, `public`, `assets`
- `src`, `src-tauri`, `desktop`, `desktop-tauri`
- `frontend-nextjs`, `backend`
- All organization directories (docs, scripts, tests, etc.)

## Git Integration

### Set up Pre-commit Hook

```bash
python scripts/organize-files.py --create-hook
```

This creates a git pre-commit hook that automatically validates and organizes files before each commit.

### Manual Git Workflow

1. **Before committing changes:**
   ```bash
   python scripts/organize-files.py --validate
   ```

2. **If violations are found:**
   ```bash
   python scripts/organize-files.py --organize
   git add .
   git commit -m "Your commit message"
   ```

## Development Workflow

### Adding New Files

When creating new files, place them in the appropriate directory:

- **Python backend code**: `backend/`
- **TypeScript/React components**: `frontend-nextjs/` or `src/ui-shared/`
- **Documentation**: `docs/`
- **Scripts**: `scripts/`
- **Tests**: `tests/`

### If Files End Up in Root

If files accidentally end up in the root directory, the organization system will automatically move them:

```bash
# Check for misplaced files
python scripts/organize-files.py --validate

# Auto-organize them
python scripts/organize-files.py --organize
```

## Customizing Rules

### Modify Organization Rules

Edit `.file-organization-rules.json` to add, modify, or remove rules:

```json
{
  "pattern": "*.your-pattern",
  "target_directory": "your-directory",
  "description": "Your description",
  "priority": 1,
  "exceptions": ["exception-pattern"]
}
```

### Rule Priority

Rules are processed by priority (higher number = higher priority). The first matching rule is applied.

## Troubleshooting

### Common Issues

1. **"File already exists in target location"**
   - The organization script will not overwrite existing files
   - Manually resolve conflicts before running organization

2. **"Permission denied"**
   - Ensure you have write permissions for the files and directories
   - Run with appropriate privileges if needed

3. **Files not being organized**
   - Check if the file matches any rule patterns
   - Verify the file isn't protected
   - Check rule priorities and exceptions

### Debug Mode

For detailed logging:

```bash
python scripts/organize-files.py --organize 2>&1 | grep -i "debug"
```

## Best Practices

1. **Run validation regularly** during development
2. **Use the pre-commit hook** for automated organization
3. **Add new file patterns** to the rules as your project evolves
4. **Keep the rules file** in version control
5. **Document custom rules** for team members

## Integration with CI/CD

Add organization validation to your CI pipeline:

```yaml
# Example GitHub Actions
- name: Validate file organization
  run: python scripts/organize-files.py --validate
```

This ensures all contributions maintain the project's organized structure.

## Support

For questions or issues with the file organization system:
- Check this guide first
- Review `.file-organization-rules.json` for current rules
- Run with `--dry-run` to preview changes
- Contact the development team if problems persist
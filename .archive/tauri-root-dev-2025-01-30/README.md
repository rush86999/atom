# Archived: Root Development Tauri Configuration

**Archived Date**: 2025-01-30
**Reason**: Consolidated to single Tauri project at `frontend-nextjs/src-tauri/`

## Why This Was Archived

This directory was the **development configuration** for Tauri, separate from the production configuration. The split was:

- **Root `src-tauri/`** (this archive):
  - Used for local development
  - Configured for dev mode (`.next` output, `cargo tauri dev`)
  - Simpler codebase (430 lines in main.rs)
  - Used by shell scripts like `start_desktop.sh`

- **`frontend-nextjs/src-tauri/`** (now consolidated):
  - Used for production builds
  - Configured for production (`out` static export, `cargo tauri build`)
  - More feature-complete (770 lines, system tray, skill runner, file watching)
  - Used by CI/CD workflows

## Consolidation Changes

To reduce confusion and maintenance burden, the two configurations have been consolidated into a single Tauri project at `frontend-nextjs/src-tauri/` that supports both development and production modes through configuration.

The consolidated `tauri.conf.json` now includes:
- `beforeDevCommand`: Runs Next.js dev server for development
- `devUrl`: Points to localhost:3000 for dev mode
- `frontendDist`: Points to `../out` for production builds

## Rollback Instructions

If needed, restore this configuration:

```bash
# From repository root
mv .archive/tauri-root-dev-2025-01-30/* .
rmdir .archive/tauri-root-dev-2025-01-30

# Then revert the shell script changes in scripts/start_desktop.sh and others
git checkout HEAD -- scripts/*.sh
```

## Keep Until

**2025-07-30** (6 months from archival date)

After this date, if consolidation is working well, this archive can be safely deleted.

## Files in This Archive

### Root Tauri Files
- `Cargo.toml` - Dependencies for dev build
- `Cargo.lock` - Locked dependency versions
- `tauri.conf.json` - Development configuration (uses `.next` output)
- `build.rs` - Rust build script

### Source Code
- `src/` - Rust source code directory
- `src/main.rs` - Development Rust code (430 lines, fewer features)
- `src/atom_agent_commands.rs` - Tauri commands

### Resources
- `icons/` - Tauri app icons
- `capabilities/` - Tauri v2 capability definitions
- `gen/` - Generated files

### Build Artifacts
- `target/` - Rust build artifacts
- `atom_verifier.pkl` - Build verification file
- `build_errors.txt`, `build_output.txt`, `build_stdout.txt` - Build logs

### Other
- `lux/` - Additional utilities
- `build.rs` - Build script

## References

See git commit for consolidation changes:
```bash
git show --stat HEAD
```

For questions, refer to:
- `frontend-nextjs/src-tauri/tauri.conf.json` - Consolidated configuration
- `scripts/start_desktop.sh` - Updated to use consolidated location
- `CLAUDE.md` - Updated documentation

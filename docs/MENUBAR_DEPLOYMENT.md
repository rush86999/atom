# Menu Bar Deployment Guide

## Overview

This guide covers building, signing, and distributing the Atom Menu Bar application for macOS and Windows.

## Prerequisites

### macOS
- macOS 14+ (Sonoma) for building
- Xcode 15+ with Command Line Tools
- Apple Developer Account ($99/year) for distribution
- Rust stable toolchain
- Node.js 18+

### Windows
- Windows 10/11 for building
- Visual Studio 2022 with C++ build tools
- Rust stable toolchain
- Node.js 18+
- Code signing certificate (optional but recommended)

### Common
- GitHub account for releases
- Homebrew tap (for macOS distribution)

## Project Setup

### 1. Install Dependencies

```bash
cd menubar
npm install
```

### 2. Install Tauri CLI

```bash
npm install -g @tauri-apps/cli
```

### 3. Verify Environment

```bash
# Check Rust installation
rustc --version

# Check Node.js
node --version

# Check Tauri CLI
tauri --version
```

## macOS Deployment

### Step 1: Apple Developer Setup

1. Go to [Developer Portal](https://developer.apple.com)
2. Create an App ID:
   - Bundle ID: `com.atomplatform.menubar`
   - Capabilities:
     - App Sandbox
     - Network Client
     - File Access (User Selected Files)
     - Notifications (optional)

### Step 2: Code Signing

#### Development Signing

For local development, you can use your development certificate:

```bash
# Build for development
npm run tauri build
```

#### Production Signing

1. Create a Developer ID certificate:
   ```bash
   # In Keychain Access:
   # Certificate Assistant > Request a Certificate From a Certificate Authority
   # Save to disk as "CertificateSigningRequest.certSigningRequest"
   ```

2. Upload CSR to Apple Developer Portal and download the certificate

3. Install certificate in Keychain Access > Login

4. Update `menubar/src-tauri/tauri.conf.json`:
   ```json
   {
     "tauri": {
       "bundle": {
         "macOS": {
           "signingIdentity": "Developer ID Application: Your Name (TEAM_ID)",
           "entitlements": "entitlements.plist",
           "provisioningProfile": null
         }
       }
     }
   }
   ```

### Step 3: Notarization

Apple requires notarization for distribution outside the App Store.

1. Create an app-specific password in [Apple ID settings](https://appleid.apple.com)

2. Add environment variables:
   ```bash
   export APPLE_ID="your-apple-id@example.com"
   export APPLE_PASSWORD="your-app-specific-password"
   export APPLE_TEAM_ID="your-team-id"
   ```

3. Update `tauri.conf.json`:
   ```json
   {
     "tauri": {
       "bundle": {
         "macOS": {
           "notarize": true
         }
       }
     }
   }
   ```

4. Build and notarize:
   ```bash
   npm run tauri build
   ```

Tauri will automatically notarize the app using your Apple credentials.

### Step 4: Build for Distribution

#### Intel (x86_64)

```bash
npm run tauri build -- --target x86_64-apple-darwin
```

#### Apple Silicon (aarch64)

```bash
npm run tauri build -- --target aarch64-apple-darwin
```

#### Universal Binary

Create a universal binary that supports both architectures:

```bash
# Build for both architectures
npm run tauri build -- --target x86_64-apple-darwin
npm run tauri build -- --target aarch64-apple-darwin

# Combine into universal binary
./scripts/create-universal-app.sh
```

### Step 5: Homebrew Distribution

#### Create a Tap

A tap is a Homebrew repository for your formula:

```bash
# Create the tap repository
mkdir homebrew-tap
cd homebrew-tap
git init
# Create Formula/atom-menubar.rb (see below)
git add .
git commit -m "Add Atom Menu Bar formula"
git remote add origin git@github.com:rush86999/homebrew-tap.git
git push -u origin main
```

#### Formula File

The formula is already created at `menubar/Formula/atom-menubar.rb`. Copy it to your tap:

```bash
cp menubar/Formula/atom-menubar.rb homebrew-tap/Formula/
cd homebrew-tap
git add Formula/atom-menubar.rb
git commit -m "Update atom-menubar to v1.0.0"
git push
```

#### Update SHA256

After building, update the SHA256 in the formula:

```bash
# Generate SHA256 for the release artifact
shasum -a 256 src-tauri/target/release/bundle/dmg/Atom_Menu_Bar_1.0.0_aarch64.dmg

# Update the SHA256 in Formula/atom-menubar.rb
# Then commit and push the update
```

#### Users Install via Homebrew

```bash
# Add the tap
brew tap rush86999/homebrew-tap

# Install Atom Menu Bar
brew install atom-menubar

# Upgrade to latest version
brew upgrade atom-menubar
```

### Step 6: GitHub Release

1. Create a new release on GitHub:
   - Tag: `v1.0.0`
   - Title: `Atom Menu Bar v1.0.0`
   - Description: Release notes

2. Upload build artifacts:
   - `Atom_Menu_Bar_1.0.0_x64.dmg` (Intel)
   - `Atom_Menu_Bar_1.0.0_aarch64.dmg` (Apple Silicon)
   - `Atom_Menu_Bar_1.0.0_universal.dmg` (Universal, if created)

3. Update Homebrew formula with new version and SHA256

## Windows Deployment

### Step 1: Code Signing (Optional but Recommended)

#### Get a Code Signing Certificate

1. Purchase a code signing certificate from a trusted CA:
   - DigiCert
   - Sectigo
   - GlobalSign

2. Install the certificate in Windows Certificate Manager

3. Update `tauri.conf.json`:
   ```json
   {
     "tauri": {
       "bundle": {
         "windows": {
           "certificateThumbprint": "YOUR_CERTIFICATE_THUMBPRINT",
           "digestAlgorithm": "sha256"
         }
       }
     }
   }
   ```

### Step 2: Build for Windows

```bash
# Build NSIS installer
npm run tauri build

# Output: src-tauri/target/release/bundle/nsis/Atom Menu Bar_1.0.0_x64-setup.exe
```

### Step 3: Windows SmartScreen

Without code signing, Windows will show a SmartScreen warning. Users can:
1. Click "More info"
2. Click "Run anyway"

With code signing, the installer will run without warnings.

### Step 4: Distribute

Upload the installer to your website or GitHub Releases:
- `Atom Menu Bar_1.0.0_x64-setup.exe`

## Auto-Update Configuration

Atom Menu Bar supports automatic updates via Tauri's built-in updater.

### Update Server

1. Create a simple JSON endpoint for updates:

```json
{
  "version": "1.0.1",
  "notes": "Bug fixes and improvements",
  "pub_date": "2026-02-20T00:00:00Z",
  "platforms": {
    "darwin-aarch64": {
      "signature": "...",
      "url": "https://github.com/rush86999/atom/releases/download/v1.0.1/Atom_Menu_Bar_1.0.1_aarch64.dmg"
    },
    "darwin-x86_64": {
      "signature": "...",
      "url": "https://github.com/rush86999/atom/releases/download/v1.0.1/Atom_Menu_Bar_1.0.1_x64.dmg"
    },
    "windows-x86_64": {
      "signature": "...",
      "url": "https://github.com/rush86999/atom/releases/download/v1.0.1/Atom_Menu_Bar_1.0.1_x64-setup.exe"
    }
  }
}
```

2. Configure updater in `tauri.conf.json`:
   ```json
   {
     "tauri": {
       "updater": {
         "active": true,
         "endpoints": [
           "https://updates.atom-platform.com/atom-menubar/{{target}}/{{current_version}}"
         ],
         "dialog": true,
         "pubkey": "YOUR_PUBLIC_KEY"
       }
     }
   }
   ```

3. Generate keys:
   ```bash
   # Generate key pair
   npm run tauri signer generate

   # Add public key to tauri.conf.json
   # Keep private key secure for signing updates
   ```

4. Sign updates:
   ```bash
   # Sign the update artifacts
   npm run tauri signer sign ./path/to/Atom_Menu_Bar_1.0.1_aarch64.dmg
   ```

## Release Process

### Automated Release (CI/CD)

The `.github/workflows/menubar-ci.yml` workflow automates releases:

1. **On push to main**: Builds and uploads artifacts
2. **On tag (v*)**: Creates GitHub release and uploads assets

To trigger a release:

```bash
# Tag the release
git tag v1.0.0
git push origin v1.0.0

# Or manually trigger from GitHub Actions
# Go to Actions > Menu Bar CI/CD Pipeline > Run workflow
```

### Manual Release

1. **Build the app**:
   ```bash
   npm run tauri build
   ```

2. **Test the build**:
   ```bash
   # macOS
   open src-tauri/target/release/bundle/dmg/Atom\ Menu\ Bar.app

   # Windows
   ./src-tauri/target/release/bundle/nsis/Atom\ Menu\ Bar_1.0.0_x64-setup.exe
   ```

3. **Create GitHub release**:
   - Go to Releases > Draft a new release
   - Tag: `v1.0.0`
   - Upload build artifacts
   - Publish release

4. **Update Homebrew formula**:
   - Bump version
   - Update SHA256
   - Commit to tap repository

## Verification Checklist

Before releasing, verify:

- [ ] App launches without crashes
- [ ] All features work correctly
- [ ] Code signature is valid (macOS: `codesign -v -d "Atom Menu Bar.app"`)
- [ ] Notarization succeeded (macOS: `xcrun notarytool info <submission-id>`)
- [ ] Installer works on clean system
- [ ] Auto-update works (test by upgrading from previous version)
- [ ] Homebrew formula installs correctly
- [ ] Release notes are complete
- [ ] Screenshots are updated (for major releases)

## Troubleshooting

### macOS: Code Signing Failed

**Error**: "code signing is required"

**Solution**:
1. Check certificate is installed: `security find-identity -v -p codesigning`
2. Update `tauri.conf.json` with correct signing identity
3. Ensure Xcode Command Line Tools are installed

### macOS: Notarization Failed

**Error**: "Unable to notarize"

**Solution**:
1. Verify Apple ID and app-specific password are correct
2. Check team ID matches your developer account
3. Ensure you have a stable internet connection
4. Check notarization status: `xcrun notarytool history`

### Windows: SmartScreen Warning

**Error**: "Windows Defender SmartScreen prevented an unrecognized app"

**Solution**:
1. Get a code signing certificate
2. Sign the installer before distribution
3. Users can click "More info" > "Run anyway"

### Homebrew: SHA256 Mismatch

**Error**: "SHA256 mismatch"

**Solution**:
1. Rebuild the app
2. Generate new SHA256: `shasum -a 256 Atom_Menu_Bar_1.0.0_aarch64.dmg`
3. Update formula with correct SHA256

### Auto-Update Not Working

**Error**: "No updates available" when update exists

**Solution**:
1. Check updater endpoint is accessible
2. Verify JSON format is correct
3. Ensure version comparison works (semantic versioning)
4. Check public key matches signing key

## Security Considerations

### macOS
- Use Developer ID certificate for distribution
- Enable App Sandbox to limit system access
- Notarize all builds for macOS 10.15+
- Keep certificates secure (don't commit to repo)

### Windows
- Use code signing certificate from trusted CA
- Sign all installers and executables
- Enable SmartScreen reputation by signing builds

### Updates
- Sign all update packages
- Use HTTPS for update endpoints
- Validate signatures before applying updates
- Keep private keys secure

## Performance Optimization

### Build Time

- Use `cargo` caching to speed up Rust compilation
- Parallelize builds for multiple architectures
- Use GitHub Actions cache for dependencies

### App Size

- Enable upx compression (optional)
- Strip debug symbols from release builds
- Use dynamic linking for common libraries

### Startup Time

- Lazy load dependencies
- Use async initialization
- Minimize main thread work

## Additional Resources

- [Tauri Documentation](https://tauri.app/v1/guides/)
- [Apple Notarization Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Windows Code Signing](https://docs.microsoft.com/en-us/windows/win32/seccrypto/cryptography-tools)

## Support

For deployment issues:
1. Check the [Tauri Discord](https://discord.gg/tauri)
2. Search existing [GitHub Issues](https://github.com/tauri-apps/tauri/issues)
3. Create a new issue with detailed logs

## Appendix

### Example CI/CD Workflow

See `.github/workflows/menubar-ci.yml` for the complete automated workflow.

### Release Notes Template

See `docs/RELEASE_NOTES_TEMPLATE.md` for a template to use with each release.

### Environment Variables

Required environment variables for CI/CD:

- `APPLE_ID`: Your Apple ID email
- `APPLE_PASSWORD`: App-specific password
- `APPLE_TEAM_ID`: Your developer team ID
- `CERTIFICATE_MACOS_DEVELOPER_ID`: Base64-encoded certificate (for CI)
- `WINDOWS_CERTIFICATE_THUMBPRINT`: Windows certificate thumbprint

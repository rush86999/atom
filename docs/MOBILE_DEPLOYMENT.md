# Mobile Deployment Guide

## Overview

This guide covers deploying the Atom Mobile app to the iOS App Store and Google Play Store.

## Prerequisites

### iOS
- Apple Developer Account ($99/year)
- Xcode 15+ with Command Line Tools
- CocoaPods installed
- Mac with macOS 14+

### Android
- Google Play Developer Account ($25 one-time)
- Android Studio
- Java JDK 17+
- Android SDK 33+

## Project Setup

### 1. Install Dependencies

```bash
cd mobile
npm install
```

### 2. Configure EAS

```bash
npm install -g eas-cli
eas build:configure
```

### 3. Link Project

Link your project to your Expo account:

```bash
eas login
eas project:init
```

## iOS Deployment

### Step 1: App Store Connect Setup

1. Go to [App Store Connect](https://appstoreconnect.apple.com)
2. Create a new app:
   - Platform: iOS
   - Name: Atom AI
   - Bundle ID: com.atomplatform.ai
   - SKU: ATOM-MOBILE-001

### Step 2: Provisioning Profiles

1. Go to [Developer Portal](https://developer.apple.com)
2. Create App ID with bundle identifier `com.atomplatform.ai`
3. Enable capabilities:
   - Push Notifications
   - Location (When in Use)
   - Camera Usage
   - Face ID
4. Create Distribution Certificate
5. Create Provisioning Profile

### Step 3: Configure app.json

Ensure `app.json` has correct iOS config:

```json
{
  "expo": {
    "ios": {
      "bundleIdentifier": "com.atomplatform.ai",
      "buildNumber": "1"
    }
  }
}
```

### Step 4: Configure eas.json

```json
{
  "submit": {
    "production": {
      "ios": {
        "appleId": "your-apple-id@example.com",
        "ascAppId": "YOUR_APP_STORE_CONNECT_APP_ID",
        "appleTeamId": "YOUR_APPLE_TEAM_ID"
      }
    }
  }
}
```

### Step 5: Build

#### Development Build

```bash
eas build --platform ios --profile development
```

#### TestFlight Build

```bash
eas build --platform ios --profile preview
```

#### Production Build

```bash
eas build --platform ios --profile production
```

### Step 6: Submit to App Store

```bash
eas submit --platform ios --profile production
```

### Step 7: App Store Review

1. Upload screenshots (required sizes)
2. Provide app description
3. Set age rating
4. Submit for review
5. Wait for approval (typically 1-3 days)

## Android Deployment

### Step 1: Google Play Console Setup

1. Go to [Google Play Console](https://play.google.com/console)
2. Create a new app:
   - App name: Atom AI
   - Package name: com.atomplatform.ai
   - Free or Paid: Free
   - App ads: No

### Step 2: Generate Keystore

```bash
keytool -genkeypair -v -storetype PKCS12 -keystore atom-keystore.jks -alias atom-key-alias -keyalg RSA -keysize 2048 -validity 10000
```

Store the keystore securely and **never commit it to git**.

Add to `.gitignore`:

```
*.jks
*.keystore
keystore.properties
```

### Step 3: Create keystore.properties

Create `android/keystore.properties`:

```properties
KEYSTORE_FILE=atom-keystore.jks
KEYSTORE_PASSWORD=your-keystore-password
KEY_ALIAS=atom-key-alias
KEY_PASSWORD=your-key-password
```

### Step 4: Configure app.json

Ensure `app.json` has correct Android config:

```json
{
  "expo": {
    "android": {
      "package": "com.atomplatform.ai",
      "versionCode": 1
    }
  }
}
```

### Step 5: Configure eas.json

```json
{
  "build": {
    "production": {
      "android": {
        "keystorePath": "./atom-keystore.jks"
      }
    }
  }
}
```

### Step 6: Build

#### Development Build

```bash
eas build --platform android --profile development
```

#### Testing Build (APK)

```bash
eas build --platform android --profile preview --output ./app.apk
```

#### Production Build (AAB)

```bash
eas build --platform android --profile production
```

### Step 7: Submit to Play Store

1. Download the AAB file from EAS
2. Go to Google Play Console
3. Create new release:
   - Upload AAB file
   - Add release notes
   - Set rollout percentage (start with internal testing)
4. Submit for review
5. Wait for approval (typically 1-2 days)

## Continuous Deployment

### Automated Builds

Set up GitHub Actions for automatic builds:

```yaml
name: EAS Build

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: expo/expo-github-action@v7
        with:
          eas-version: latest
          command: eas build --platform all --profile production
```

### OTA Updates

Use EAS Update for over-the-air updates:

```bash
# Create update branch
eas branch:create production

# Publish update
eas update --branch production --message "Bug fixes"
```

## Store Listing

### App Store (iOS)

**Required Assets**:
- App icon (1024x1024 PNG)
- Screenshots:
  - 6.7" Display (1290x2796)
  - 6.5" Display (1242x2688)
  - 5.5" Display (1242x2208)

**Description**:
```
Atom AI - Automation at your fingertips

Chat with AI agents, view canvases, and automate workflows from anywhere.

Features:
• Real-time streaming chat with AI agents
• Episode context from past conversations
• View and interact with canvases
• Offline mode with automatic sync
• Push notifications for agent events
• Device capabilities (camera, location)

Your entire AI automation platform, now in your pocket.
```

### Play Store (Android)

**Required Assets**:
- App icon (512x512 PNG)
- Feature graphic (1024x500 PNG)
- Screenshots (phone, 7-inch tablet, 10-inch tablet)

**Description**:
```
Atom AI - Automation at your fingertips

Chat with AI agents, view canvases, and automate workflows from anywhere.

Features:
✦ Real-time streaming chat with AI agents
✦ Episode context from past conversations
✦ View and interact with canvases
✦ Offline mode with automatic sync
✦ Push notifications for agent events
✦ Device capabilities (camera, location)

Your entire AI automation platform, now in your pocket.
```

## Versioning

Follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features
- **PATCH**: Bug fixes

Example:
- `1.0.0` - Initial release
- `1.1.0` - Add new feature
- `1.1.1` - Bug fix
- `2.0.0` - Breaking changes

## Monitoring

### Crash Reporting

Set up Sentry:

```bash
npm install @sentry/react-native
```

Initialize in `App.tsx`:

```typescript
import * as Sentry from '@sentry/react-native';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  tracesSampleRate: 1.0,
});
```

### Analytics

Set up analytics:

```typescript
import { Analytics } from '@segment/analytics-react-native';

const analytics = new Analytics('WRITE_KEY');

analytics.track('App Launched');
```

## Troubleshooting

### Build Fails

1. Check EAS build logs
2. Verify all credentials are correct
3. Ensure bundle ID/package name match
4. Clear cache: `eas build --clear-cache`

### App Rejected

Common rejection reasons:
- **Missing permissions**: Explain why each permission is needed in review notes
- **Guideline 2.1**: Ensure app provides real value
- **Guideline 4.0**: Design must be minimum quality
- **Guideline 5.1.1**: Data collection must be disclosed

### Update Issues

If OTA updates don't work:

```bash
# Check update status
eas update:list

# View update details
eas update:view <update-id>
```

## Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Security audit completed
- [ ] Performance benchmarks met
- [ ] Accessibility tested
- [ ] Internationalization complete

### iOS
- [ ] App Store Connect app created
- [ ] Provisioning profiles configured
- [ ] Screenshots uploaded
- [ ] App description written
- [ ] Age rating set
- [ ] Export compliance documented
- [ ] Build uploaded
- [ ] TestFlight tested
- [ ] Ready for App Store submission

### Android
- [ ] Play Console app created
- [ ] Keystore generated and secured
- [ ] Screenshots uploaded
- [ ] Store listing complete
- [ ] Content rating completed
- [ ] Privacy policy URL provided
- [ ] Build uploaded (AAB)
- [ ] Internal testing complete
- [ ] Ready for production release

## Support

For deployment issues:
- EAS Documentation: https://docs.expo.dev/eas
- App Store Connect: https://apple.co/asc-support
- Google Play Console: https://support.google.com/googleplay/android-developer

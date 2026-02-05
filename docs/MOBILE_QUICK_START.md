# Mobile App Quick Start Guide

## Overview

Atom Mobile is a React Native app that brings AI-powered automation to your iOS and Android devices. This guide will help you get started with development, testing, and deployment.

## Prerequisites

- Node.js 18+ and npm
- Expo CLI: `npm install -g expo-cli`
- EAS CLI: `npm install -g eas-cli`
- iOS: Xcode 15+ and CocoaPods
- Android: Android Studio and SDK 33+

## Installation

```bash
cd mobile
npm install
```

## Development

### Start Development Server

```bash
npm start
```

Scan the QR code with Expo Go (iOS) or Expo app (Android).

### Run on iOS Simulator

```bash
npm run ios
```

### Run on Android Emulator

```bash
npm run android
```

## Environment Variables

Create `.env` file:

```bash
API_BASE_URL=http://localhost:8000
WEBSOCKET_URL=ws://localhost:8000
ENVIRONMENT=development
SENTRY_DSN=your-sentry-dsn
ANALYTICS_KEY=your-analytics-key
```

## Key Features

### 1. Agent Chat

- Stream real-time responses from AI agents
- View episode context from past conversations
- See governance badges (maturity, confidence)
- Reference canvases and past episodes

### 2. Agent List

- Filter agents by maturity level
- Search by name, description, capability
- Sort by name, created date, last execution
- View confidence scores and status

### 3. Canvas Viewer

- View canvases on mobile
- Interactive forms with validation
- Charts and data visualizations
- Zoom controls for detailed viewing

### 4. Offline Mode

- Queue actions when offline
- Automatic sync when connection restored
- Conflict resolution (last_write_wins, manual)
- Retry failed actions

### 5. Device Capabilities

- Camera: Capture images for AI analysis
- Location: Location-aware automation
- Notifications: Push notifications for agent events

## Testing

### Run Tests

```bash
npm test
```

### Run with Coverage

```bash
npm run test:coverage
```

### Watch Mode

```bash
npm run test:watch
```

## Building for Production

### iOS

```bash
# Configure EAS
eas build:configure

# Build for TestFlight
eas build --platform ios --profile preview

# Build for App Store
eas build --platform ios --profile production
```

### Android

```bash
# Build APK for testing
eas build --platform android --profile preview --output ./app.apk

# Build for Play Store
eas build --platform android --profile production
```

## Deployment

### TestFlight (iOS)

1. Build with `eas build --platform ios --profile preview`
2. Download IPA file
3. Upload to App Store Connect
4. Add to TestFlight
5. Invite testers

### Play Store (Android)

1. Build with `eas build --platform android --profile production`
2. Download AAB file
3. Upload to Google Play Console
4. Complete store listing
5. Submit for review

### Over-the-Air Updates

```bash
# Publish update
eas update --branch production --message "Bug fixes and improvements"
```

## Troubleshooting

### Metro Bundler Issues

```bash
npm start -- --reset-cache
```

### iOS Build Errors

```bash
cd ios
pod install
cd ..
npm run ios
```

### Android Build Errors

```bash
cd android
./gradlew clean
cd ..
npm run android
```

## Performance Tips

1. **Enable Hermes**: Improves JS performance significantly
2. **Use React.memo**: Prevent unnecessary re-renders
3. **Code Splitting**: Load components on demand
4. **Optimize Images**: Compress assets before bundling
5. **Minimize Re-renders**: Use useCallback and useMemo

## Next Steps

- Read [Mobile Deployment Guide](./MOBILE_DEPLOYMENT.md)
- Check [Architecture Overview](./REACT_NATIVE_ARCHITECTURE.md)
- Review [API Documentation](../backend/README.md)

## Support

For issues and questions:
- GitHub: https://github.com/rush86999/atom/issues
- Documentation: https://docs.atom-platform.com
- Discord: https://discord.gg/atom-platform

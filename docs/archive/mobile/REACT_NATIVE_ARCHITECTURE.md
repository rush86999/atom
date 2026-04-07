# Atom Mobile App - React Native Architecture

**Version**: 1.0
**Date**: February 1, 2026
**Platform**: React Native 0.73+ (iOS & Android)

---

## Overview

The Atom mobile app provides cross-platform access to the Atom AI automation platform with real-time agent interactions, canvas presentations, and device-native capabilities.

### Key Features

- ✅ Real-time agent chat with streaming responses
- ✅ Interactive canvas presentations on mobile
- ✅ Device-native capabilities (camera, location, notifications)
- ✅ Offline mode with data synchronization
- ✅ Biometric authentication (Face ID / Touch ID)
- ✅ Push notifications for agent responses
- ✅ Governance integration with audit trails
- ✅ Multi-agent collaboration support

---

## Architecture

### Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Mobile App Layer                     │
├─────────────────────────────────────────────────────────┤
│  React Native 0.73+ │ iOS 13+ │ Android 8+ (API 26+)    │
├─────────────────────────────────────────────────────────┤
│  Navigation    │  React Navigation 6.x                  │
│  State         │  Zustand 4.x (lightweight)              │
│  Networking    │  Axios + Socket.io-client              │
│  Storage       │  AsyncStorage + MMKV (fast KV)         │
│  UI            │  React Native Paper / NativeBase       │
│  Animations    │  React Native Reanimated 3.x           │
│  Charts        │  Victory Native                        │
│  WebView       │  React Native WebView (canvas embed)   │
│  Notifications │  React Native Push Notifications        │
│  Auth          │  React Native Keychain (secure tokens) │
│  Camera        │  React Native Vision Camera            │
│  Location      │  React Native Geolocation Service      │
└─────────────────────────────────────────────────────────┘
```

### Project Structure

```
mobile/
├── src/
│   ├── components/          # Reusable components
│   │   ├── chat/           # Chat-specific components
│   │   ├── canvas/         # Canvas rendering components
│   │   ├── agents/         # Agent selection/management
│   │   └── common/         # Shared UI components
│   ├── screens/            # Screen components
│   │   ├── auth/           # Login, register, forgot password
│   │   ├── chat/           # Chat screen with streaming
│   │   ├── canvas/         # Canvas gallery and detail
│   │   ├── agents/         # Agent management
│   │   └── settings/       # User settings and profile
│   ├── navigation/         # Navigation configuration
│   │   ├── AppNavigator.tsx
│   │   ├── AuthNavigator.tsx
│   │   └── MainNavigator.tsx
│   ├── services/           # API and business logic
│   │   ├── api/            # REST API clients
│   │   ├── websocket/      # WebSocket service
│   │   ├── auth/           # Authentication service
│   │   └── storage/        # Local storage service
│   ├── store/              # State management (Zustand)
│   │   ├── authStore.ts
│   │   ├── chatStore.ts
│   │   ├── canvasStore.ts
│   │   └── agentStore.ts
│   ├── hooks/              # Custom React hooks
│   │   ├── useAgentStream.ts
│   │   ├── useCanvasUpdates.ts
│   │   └── useBiometricAuth.ts
│   ├── utils/              # Helper functions
│   │   ├── logger.ts       # Logging utility
│   │   ├── validation.ts   # Input validation
│   │   └── constants.ts    # App constants
│   ├── types/              # TypeScript types
│   │   ├── agent.ts
│   │   ├── canvas.ts
│   │   └── api.ts
│   └── assets/             # Images, fonts, etc.
├── android/                # Android native code
├── ios/                    # iOS native code
├── App.tsx                 # Root component
├── package.json
└── tsconfig.json
```

---

## Core Features Implementation

### 1. Authentication

#### Biometric Authentication

```typescript
// services/auth/BiometricAuth.ts
import * as LocalAuthentication from 'expo-local-authentication';

export class BiometricAuthService {
  async authenticate(): Promise<boolean> {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) return false;

    const isEnrolled = await LocalAuthentication.isEnrolledAsync();
    if (!isEnrolled) return false;

    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to access Atom',
        fallbackLabel: 'Use password',
      });
      return result.success;
    } catch (error) {
      return false;
    }
  }
}
```

### 2. Real-time Agent Chat

#### WebSocket Service

```typescript
// services/websocket/AgentStreamService.ts
import { io, Socket } from 'socket.io-client';

export class AgentStreamService {
  private socket: Socket | null = null;

  connect(userId: string, token: string): void {
    this.socket = io('ws://localhost:8000', {
      auth: { token },
      transports: ['websocket'],
      reconnection: true,
    });

    this.socket.on('agent_chunk', (data: AgentChunkData) => {
      useChatStore.getState().appendChunk(data);
    });

    this.socket.on('agent_complete', (data: AgentCompleteData) => {
      useChatStore.getState().completeMessage(data);
    });
  }

  sendMessage(agentId: string, message: string, sessionId: string): void {
    this.socket?.emit('agent_message', {
      agent_id: agentId,
      message,
      session_id: sessionId,
      platform: 'mobile',
    });
  }
}
```

### 3. Canvas Presentations

#### Canvas WebView Component

```typescript
// components/canvas/CanvasWebView.tsx
import React from 'react';
import { WebView } from 'react-native-webview';
import { View, ActivityIndicator } from 'react-native';

interface CanvasWebViewProps {
  canvasId: string;
  sessionId: string;
  onDataUpdate?: (data: any) => void;
}

export const CanvasWebView: React.FC<CanvasWebViewProps> = ({
  canvasId,
  sessionId,
  onDataUpdate,
}) => {
  const canvasUrl = `http://localhost:8000/canvas/${canvasId}?session_id=${sessionId}&platform=mobile`;

  const handleMessage = (event: any) => {
    const data = JSON.parse(event.nativeEvent.data);

    switch (data.type) {
      case 'data_update':
        onDataUpdate?.(data.payload);
        break;
      case 'form_submit':
        handleFormSubmit(data.payload);
        break;
    }
  };

  return (
    <WebView
      source={{ uri: canvasUrl }}
      onMessage={handleMessage}
      javaScriptEnabled={true}
      domStorageEnabled={true}
    />
  );
};
```

---

## Governance Integration

All mobile agent actions are tracked with device-specific governance:

```typescript
// services/governance/MobileGovernanceService.ts
interface AgentAction {
  agent_id: string;
  action_type: string;
  platform: 'mobile';
  device_id: string;
  session_id: string;
  metadata: {
    device_model: string;
    os_version: string;
    app_version: string;
  };
}

export class MobileGovernanceService {
  async trackAction(action: AgentAction): Promise<void> {
    await api.post('/governance/track', {
      ...action,
      platform: 'mobile',
      device_id: await this.getDeviceId(),
    });
  }

  async checkAgentPermission(
    agentId: string,
    action: string
  ): Promise<boolean> {
    const response = await api.get('/governance/check', {
      agent_id: agentId,
      action,
      platform: 'mobile',
    });

    return response.data.allowed;
  }
}
```

---

## Next Steps for Full Implementation

1. **Phase 1**: Project setup and authentication
2. **Phase 2**: Chat interface with WebSocket streaming
3. **Phase 3**: Canvas rendering and gallery
4. **Phase 4**: Device-native features (camera, location, notifications)
5. **Phase 5**: Offline mode and performance optimization
6. **Phase 6**: Testing and deployment

---

## References

- [React Native Documentation](https://reactnative.dev/)
- [React Navigation](https://reactnavigation.org/)
- [Zustand](https://zustand-demo.pmnd.rs/)
- [Expo](https://docs.expo.dev/)
- [Socket.io Client](https://socket.io/docs/v4/client-api/)

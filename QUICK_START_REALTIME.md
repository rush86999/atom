# Quick Start: Advanced Real-Time Views

## 🚀 Getting Started in 5 Minutes

### 1. Import the Views

```typescript
import {
  AdvancedRealtimeHub,
  CollaborativeEditor,
  PerformanceMonitor,
  LiveDataSync,
} from './views';
```

### 2. Add to Your Router

```typescript
const viewRoutes = [
  {
    path: '/hub',
    element: <AdvancedRealtimeHub />,
    icon: '🚀',
    label: 'Real-Time Hub',
  },
  {
    path: '/editor',
    element: <CollaborativeEditor />,
    icon: '📝',
    label: 'Collaborative Editor',
  },
  {
    path: '/performance',
    element: <PerformanceMonitor />,
    icon: '🎯',
    label: 'Performance',
  },
  {
    path: '/sync',
    element: <LiveDataSync />,
    icon: '⚡',
    label: 'Data Sync',
  },
];
```

### 3. Enable WebSocket

```typescript
// In your main App component
import { useWebSocket, useRealtimeSync } from './hooks/useWebSocket';

function App() {
  // Initialize real-time connection
  const { isConnected } = useWebSocket({ enabled: true });
  useRealtimeSync();

  return (
    <div className="app">
      {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
      {/* Your routes */}
    </div>
  );
}
```

### 4. Import Styles

```typescript
// In your main CSS or SCSS file
@import './views/advanced-realtime-styles.css';
```

### 5. That's It! 🎉

Visit the new routes to see the real-time features in action:

- `/hub` - Monitor real-time collaboration
- `/editor` - Start editing with others in real-time
- `/performance` - Track system performance
- `/sync` - Monitor data synchronization

---

## 📋 View Overview

### Advanced Realtime Hub

**Path**: `/hub`
**Best For**: Monitoring overall system health and team activity

- 📊 Real-time metrics (users, messages, latency, throughput)
- 👥 Active sessions with live cursor tracking
- 🌐 Network health status
- 📍 Collaboration event timeline
- 📈 Current statistics

### Collaborative Editor

**Path**: `/editor`
**Best For**: Multi-user document editing with full version control

- ✏️ Real-time text synchronization
- 👆 Multi-user cursor tracking
- 📜 Version history with revert capability
- 🔒 Document locking mechanism
- 💾 Auto-save and manual save
- 📥 Export to Markdown

### Performance Monitor

**Path**: `/performance`
**Best For**: Identifying and fixing performance bottlenecks

- 📈 CPU, memory, network monitoring
- ⏱️ Render time and API latency tracking
- 🚨 Automatic alerts for degradation
- 📊 Real-time charts with historical data
- ⏰ Page load waterfall analysis
- 💡 Smart optimization recommendations

### Live Data Sync

**Path**: `/sync`
**Best For**: Managing data consistency across clients

- 🔄 Sync status per data type (tasks, messages, notes, workflows)
- ⚠️ Conflict detection and resolution
- 📋 Complete sync activity log
- 📡 Bandwidth usage monitoring
- 📈 Sync statistics and success rates
- ⏱️ Auto and manual sync modes

---

## 🔗 WebSocket Connection

### Auto-Connect (Recommended)

```typescript
const { isConnected } = useWebSocket({
  enabled: true, // Auto-connects
});
```

### Manual Control

```typescript
const { connect, disconnect, isConnected } = useWebSocket({
  enabled: false, // Start disconnected
});

// When ready
connect();

// When done
disconnect();
```

### With Options

```typescript
const { emit, subscribe } = useWebSocket({
  url: process.env.REACT_APP_WS_URL || 'ws://localhost:3001',
  enabled: true,
  reconnectAttempts: 5,
  enablePresence: true,
  enableLiveCursors: true,
  enableOfflineQueue: true,
});
```

---

## 📡 Common Events

### Listening to Events

```typescript
const { subscribe, unsubscribe } = useWebSocket({ enabled: true });

// Subscribe to real-time updates
subscribe('user:joined', (data) => {
  console.log(`${data.username} joined`);
});

subscribe('collaboration:event', (data) => {
  console.log(`${data.user} ${data.action}`);
});

// Don't forget to unsubscribe on unmount
return () => {
  unsubscribe('user:joined');
  unsubscribe('collaboration:event');
};
```

### Sending Events

```typescript
const { emit } = useWebSocket({ enabled: true });

// Broadcast a message
emit('broadcast:message', {
  from: 'You',
  content: 'Hello everyone!',
  timestamp: Date.now(),
});

// Request data sync
emit('sync:request', {
  dataTypes: ['tasks', 'messages'],
  timestamp: Date.now(),
});

// Send a health check
emit('health:check', {
  timestamp: Date.now(),
});
```

---

## 🎨 Styling

All components are pre-styled with:

- 📱 Responsive design (mobile, tablet, desktop)
- 🌙 Dark mode support (via existing theme system)
- ♿ WCAG 2.1 AA accessibility compliance
- 🎭 Smooth animations and transitions

### Custom Styling

Override specific components:

```css
/* Custom metric card colors */
.metric-card {
  background: linear-gradient(135deg, #your-color-1 0%, #your-color-2 100%);
  border-left-color: #your-accent;
}

/* Custom editor background */
.editor-textarea {
  background: #your-dark-bg;
  color: #your-light-text;
}
```

---

## 🔧 Configuration

### WebSocket Configuration

```typescript
// In your environment or config file
const config = {
  WS_URL: process.env.REACT_APP_WS_URL || 'ws://localhost:3001',
  WS_RECONNECT_ATTEMPTS: 5,
  WS_RECONNECT_INTERVAL: 1000,
  WS_HEARTBEAT_INTERVAL: 30000,
  SYNC_INTERVAL: 30000, // 30 seconds
  SYNC_MODE: 'auto', // or 'manual'
};
```

### Performance Monitor Settings

```typescript
// Customize alert thresholds
const ALERT_THRESHOLDS = {
  CPU: 75,
  MEMORY: 80,
  LATENCY: 200,
  RENDER_TIME: 16, // 60 FPS = 16ms
  API_LATENCY: 500,
};
```

### Sync Configuration

```typescript
// Configure sync behavior
const SYNC_CONFIG = {
  autoSync: true,
  syncInterval: 30000,
  conflictStrategy: 'last-write-wins', // or 'merge', 'server', 'client'
  compressionEnabled: true,
  offlineQueueEnabled: true,
  maxQueueSize: 100,
};
```

---

## 🐛 Common Issues & Solutions

### WebSocket Won't Connect

```typescript
// ❌ Wrong
useWebSocket({ enabled: true }); // No return used

// ✅ Correct
const { isConnected } = useWebSocket({ enabled: true });
console.log(isConnected); // Use the returned value
```

### Changes Not Syncing

```typescript
// ✅ Always check connection first
const { emit, isConnected } = useWebSocket({ enabled: true });

if (isConnected) {
  emit('document:edit', change);
} else {
  // Queue for later or show offline message
}
```

### Performance Monitor Shows 0 Values

```typescript
// ✅ Ensure hook is being used
const { isConnected } = useRealtimeSync();

// ✅ Wait for initial data before rendering
const [metrics, setMetrics] = useState([]);

useEffect(() => {
  if (metrics.length > 0) {
    // Render charts
  }
}, [metrics]);
```

### Editor Lagging with Large Documents

```typescript
// ✅ Use useMemo for expensive operations
const renderedContent = useMemo(() => {
  return content.split('\n').map(renderLine);
}, [content]);

// ✅ Debounce frequent updates
const debouncedSave = useCallback(
  debounce((content) => {
    emit('document:save', { content });
  }, 1000),
  []
);
```

---

## 📊 Real-Time Data Examples

### Collaborative Editing

```typescript
// When user types
const handleChange = (e) => {
  const newContent = e.target.value;
  setContent(newContent);

  // Calculate change
  const change = {
    id: `change-${Date.now()}`,
    type: 'insert',
    position: oldContent.length,
    content: newText,
    author: currentUser,
    timestamp: Date.now(),
  };

  // Emit to other users
  emit('document:edit', change);
};
```

### Performance Metrics

```typescript
// Metrics update every 3 seconds
useEffect(() => {
  const interval = setInterval(() => {
    const newMetric = {
      timestamp: Date.now(),
      cpu: performance.cpu, // Your measurement
      memory: performance.memory,
      network: performance.network,
      renderTime: performance.renderTime,
      apiLatency: performance.apiLatency,
    };

    setMetrics((prev) => [...prev, newMetric]);
  }, 3000);

  return () => clearInterval(interval);
}, []);
```

### Conflict Resolution

```typescript
// When conflict detected
const handleResolveConflict = (conflictId, resolution) => {
  // resolution: 'local' | 'remote'

  if (resolution === 'local') {
    // Keep local version
    emit('conflict:resolve', { conflictId, resolution: 'local' });
  } else {
    // Use remote version
    const remoteData = conflicts.find((c) => c.id === conflictId).remote;
    setContent(remoteData);
    emit('conflict:resolve', { conflictId, resolution: 'remote' });
  }
};
```

---

## 🎓 Learning Resources

### Understanding Real-Time Sync

- WebSocket basics: https://socket.io/docs/
- Operational Transformation: https://en.wikipedia.org/wiki/Operational_transformation
- CRDT alternatives: https://crdt.tech/

### Performance Best Practices

- React performance: https://react.dev/reference/react/useMemo
- Network optimization: https://web.dev/performance/
- Browser DevTools: https://developer.chrome.com/docs/devtools/

### Security Considerations

- WebSocket security: https://owasp.org/www-community/attacks/websocket
- Data validation: https://www.npmjs.com/package/joi
- Encryption: https://www.npmjs.com/package/crypto-js

---

## 📞 Support

### Debug Mode

```typescript
// Enable verbose logging
const { isConnected } = useWebSocket({
  enabled: true,
  onConnect: () => console.log('✅ Connected'),
  onDisconnect: () => console.log('❌ Disconnected'),
  onError: (error) => console.error('⚠️ Error:', error),
});
```

### Check Network Activity

```typescript
// In browser DevTools:
// 1. Open Network tab
// 2. Filter for WS (WebSocket)
// 3. Click on connection
// 4. Check Messages tab
```

### View Real-Time Logs

```typescript
// Monitor sync operations
const [syncLogs, setSyncLogs] = useState([]);

subscribe('sync:completed', (log) => {
  setSyncLogs((prev) => [log, ...prev]);
  console.log('Sync completed:', log);
});
```

---

## 🎉 Next Steps

1. ✅ Import the views in your app
2. ✅ Add routes to your router
3. ✅ Enable WebSocket connection
4. ✅ Import CSS styles
5. ✅ Test each view by visiting the routes
6. ✅ Customize configuration as needed
7. ✅ Read detailed documentation for advanced usage
8. ✅ Deploy with confidence!

---

**Congratulations!** 🎊

You now have a fully functional real-time collaboration platform with performance monitoring and data synchronization. Start using these features to enhance your application's real-time capabilities!

For detailed information, see: `ADVANCED_REALTIME_FEATURES.md`

**Last Updated**: November 18, 2025  
**Version**: 1.0.0  
**Status**: Production Ready ✅

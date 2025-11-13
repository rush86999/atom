# TODO: Fix useWebSocket Tests

## Current Issues

- Initial connection state mismatch: tests expect 'disconnected' but hook auto-connects with default enabled=true
- Disconnect notifications not shown for server disconnects
- Event listeners not set up in useRealtimeSync when not connected
- Cleanup verification failing due to listeners not being set

## Plan

1. Change default `enabled` to `false` in `useWebSocket` hook
2. Update disconnect logic to always show notification, attempt reconnect for specific reasons
3. Remove `isConnected` check from `useRealtimeSync` useEffect to set up listeners regardless
4. Add more comprehensive tests for edge cases
5. Improve error handling and connection management

## Tasks

- [x] Update useWebSocket default options
- [x] Fix disconnect notification logic
- [x] Modify useRealtimeSync listener setup
- [x] Run tests to verify fixes
- [ ] Add additional test cases for better coverage
- [ ] Enhance WebSocket implementation with better error handling

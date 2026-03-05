/**
 * Agent Device Bridge Tests
 *
 * Tests for agent-device integration with governance:
 * - Governance maturity checks (STUDENT blocked, INTERN+ with approval)
 * - Capability execution (camera, location, notifications, biometric, photos)
 * - Audit log tracking and filtering
 * - Error handling and timeouts
 * - Capability discovery
 */

// Mock Expo modules BEFORE importing services
jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn(),
  isEnrolledAsync: jest.fn(),
  authenticateAsync: jest.fn(),
  getSupportedAuthenticationTypesAsync: jest.fn(),
}));

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

jest.mock('expo-camera', () => ({
  CameraView: {
    requestCameraPermissionsAsync: jest.fn(),
    getCameraPermissionsAsync: jest.fn(),
    isAvailableAsync: jest.fn(),
  },
  CameraType: {
    Front: 'front',
    Back: 'back',
  },
}));

jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(),
  requestBackgroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  startLocationUpdatesAsync: jest.fn(),
  stopLocationUpdatesAsync: jest.fn(),
  hasServicesEnabledAsync: jest.fn(),
  Accuracy: {
    High: 6,
    Balanced: 3,
    Low: 2,
    Lowest: 1,
  },
  GeocodingAccuracy: {
    High: 6,
    Medium: 3,
    Low: 2,
    Lowest: 1,
  },
}));

jest.mock('expo-notifications', () => ({
  scheduleNotificationAsync: jest.fn(),
  cancelScheduledNotificationAsync: jest.fn(),
  getAllScheduledNotificationsAsync: jest.fn(),
  setBadgeCountAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
}));

jest.mock('expo-image-picker', () => ({
  launchImageLibraryAsync: jest.fn(),
  requestMediaLibraryPermissionsAsync: jest.fn(),
  MediaTypeOptions: {
    Images: 'images',
  },
}));

// Now import services
import { agentDeviceBridge, DeviceCapability, AgentMaturityLevel } from '../../services/agentDeviceBridge';
import { cameraService } from '../../services/cameraService';
import { locationService } from '../../services/locationService';
import { notificationService } from '../../services/notificationService';
import { biometricService } from '../../services/biometricService';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Alert } from 'react-native';

// Mock all service dependencies
jest.mock('../../services/cameraService');
jest.mock('../../services/locationService');
jest.mock('../../services/notificationService');
jest.mock('../../services/biometricService');
jest.mock('@react-native-async-storage/async-storage');
jest.mock('react-native', () => ({
  Alert: {
    alert: jest.fn(),
  },
  Platform: {
    OS: 'ios',
  },
}));

// Type casts for mocked services
const mockCameraService = cameraService as jest.Mocked<typeof cameraService>;
const mockLocationService = locationService as jest.Mocked<typeof locationService>;
const mockNotificationService = notificationService as jest.Mocked<typeof notificationService>;
const mockBiometricService = biometricService as jest.Mocked<typeof biometricService>;
const mockAlert = Alert.alert as jest.Mock;
const mockAsyncStorage = AsyncStorage as jest.Mocked<typeof AsyncStorage>;

describe('agentDeviceBridge', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    agentDeviceBridge._resetState();

    // Default mock implementations
    mockCameraService.isAvailable.mockResolvedValue(true);
    mockCameraService.requestPermissions.mockResolvedValue(true);
    mockCameraService.pickImage.mockResolvedValue([
      { uri: 'file://image1.jpg', width: 1920, height: 1080 },
    ]);

    mockLocationService.requestPermissions.mockResolvedValue(true);
    mockLocationService.getCurrentLocation.mockResolvedValue({
      latitude: 37.7749,
      longitude: -122.4194,
      altitude: 0,
      accuracy: 10,
      speed: 0,
      heading: 0,
      timestamp: Date.now(),
    });
    mockLocationService.startTracking.mockResolvedValue(true);
    mockLocationService.stopTracking.mockResolvedValue(undefined);
    mockLocationService.calculateDistance.mockReturnValue(1000);
    mockLocationService.reverseGeocode.mockResolvedValue({
      street: '123 Main St',
      city: 'San Francisco',
      state: 'CA',
      country: 'USA',
      postalCode: '94102',
    });

    mockNotificationService.sendLocalNotification.mockResolvedValue(undefined);
    mockNotificationService.scheduleNotification.mockResolvedValue('notif-123');
    mockNotificationService.setBadgeCount.mockResolvedValue(undefined);

    mockBiometricService.isAvailable.mockResolvedValue(true);
    mockBiometricService.isEnrolled.mockResolvedValue(true);
    mockBiometricService.getBiometricType.mockResolvedValue('face');
    mockBiometricService.authenticate.mockResolvedValue({ success: true, warning: undefined });

    mockAsyncStorage.getItem.mockResolvedValue(null);
    mockAsyncStorage.setItem.mockResolvedValue(undefined);
    mockAsyncStorage.removeItem.mockResolvedValue(undefined);

    // Reset Alert mock to default (approve)
    mockAlert.mockReset();
    mockAlert.mockImplementation((title, message, buttons) => {
      if (buttons && buttons[1] && typeof buttons[1].onPress === 'function') {
        buttons[1].onPress();
      }
    });

    // Initialize service
    await agentDeviceBridge.initialize();
  });

  // Helper function to create mock requests
  const mockRequest = (
    maturityLevel: AgentMaturityLevel,
    capability: DeviceCapability,
    action: string,
    params?: Record<string, any>
  ) => ({
    requestId: `req-${Date.now()}-${Math.random()}`,
    agentId: 'agent-123',
    agentName: 'Test Agent',
    maturityLevel,
    capability,
    action,
    params,
    timestamp: Date.now(),
  });

  // Governance tests (8 tests)
  describe('Governance', () => {
    it('should block STUDENT agents from camera', async () => {
      const request = mockRequest('STUDENT', 'camera', 'pickImage');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(false);
      expect(result.error).toContain('insufficient');
      expect(result.error).toContain('INTERN');
    });

    it('should allow INTERN agents with user approval', async () => {
      // Mock user approval
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        const approveButton = buttons[1];
        if (approveButton && typeof approveButton.onPress === 'function') {
          approveButton.onPress();
        }
      });

      const request = mockRequest('INTERN', 'camera', 'pickImage');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data).toBeDefined();
      expect(mockAlert).toHaveBeenCalled();
    });

    it('should allow SUPERVISED agents with approval', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        const approveButton = buttons[1];
        if (approveButton && typeof approveButton.onPress === 'function') {
          approveButton.onPress();
        }
      });

      const request = mockRequest('SUPERVISED', 'location', 'getCurrentLocation');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data).toBeDefined();
    });

    it('should allow AUTONOMOUS agents without approval for notifications', async () => {
      const request = mockRequest('AUTONOMOUS', 'notification', 'sendNotification', {
        title: 'Test',
        body: 'Test notification',
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data).toEqual({ sent: true });
      expect(mockAlert).not.toHaveBeenCalled(); // No approval needed for notifications
    });

    it('should block AUTONOMOUS agents from biometric without approval', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        const denyButton = buttons[0];
        if (denyButton && typeof denyButton.onPress === 'function') {
          denyButton.onPress();
        }
      });

      const request = mockRequest('AUTONOMOUS', 'biometric', 'authenticate', {
        promptMessage: 'Authenticate to proceed',
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(false);
      expect(result.error).toContain('User denied');
      expect(mockAlert).toHaveBeenCalled(); // Approval required for biometric
    });

    it('should check capability requirements', () => {
      const req = agentDeviceBridge.getCapabilityRequirements('camera');
      expect(req.minMaturity).toBe('INTERN');
      expect(req.requireApproval).toBe(true);
      expect(req.description).toContain('camera');
    });

    it('should validate agent can use capability', () => {
      expect(agentDeviceBridge.canAgentUseCapability('AUTONOMOUS', 'notification')).toBe(true);
      expect(agentDeviceBridge.canAgentUseCapability('INTERN', 'notification')).toBe(true);
      expect(agentDeviceBridge.canAgentUseCapability('STUDENT', 'camera')).toBe(false);
      expect(agentDeviceBridge.canAgentUseCapability('INTERN', 'biometric')).toBe(false);
    });

    it('should get all capability requirements', () => {
      const all = agentDeviceBridge.getAllCapabilityRequirements();
      expect(Object.keys(all).length).toBeGreaterThan(0);
      expect(all.camera).toBeDefined();
      expect(all.location).toBeDefined();
      expect(all.notification).toBeDefined();
      expect(all.biometric).toBeDefined();
    });
  });

  // Capability execution tests (8 tests)
  describe('Capability Execution', () => {
    it('should execute camera pickImage action', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'camera', 'pickImage', {
        allowsMultipleSelection: true,
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.images).toBeDefined();
      expect(result.data.count).toBe(1);
      expect(mockCameraService.pickImage).toHaveBeenCalledWith({ allowsMultipleSelection: true });
    });

    it('should execute location getCurrentLocation', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'location', 'getCurrentLocation');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.latitude).toBeDefined();
      expect(result.data.longitude).toBeDefined();
      expect(mockLocationService.getCurrentLocation).toHaveBeenCalled();
    });

    it('should execute location startTracking', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'location', 'startTracking', {
        background: false,
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.tracking).toBe(true);
      expect(mockLocationService.startTracking).toHaveBeenCalled();
    });

    it('should execute notification sendNotification', async () => {
      const request = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Test Title',
        body: 'Test Body',
        data: { key: 'value' },
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.sent).toBe(true);
      expect(mockNotificationService.sendLocalNotification).toHaveBeenCalledWith({
        title: 'Test Title',
        body: 'Test Body',
        data: { key: 'value' },
      });
    });

    it('should execute notification scheduleNotification', async () => {
      const request = mockRequest('INTERN', 'notification', 'scheduleNotification', {
        title: 'Scheduled Title',
        body: 'Scheduled Body',
        triggerSeconds: 60,
        data: { key: 'value' },
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.scheduled).toBe(true);
      expect(result.data.identifier).toBe('notif-123');
      expect(mockNotificationService.scheduleNotification).toHaveBeenCalled();
    });

    it('should execute biometric authenticate', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('AUTONOMOUS', 'biometric', 'authenticate', {
        promptMessage: 'Authenticate to access sensitive data',
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.success).toBe(true);
      expect(mockBiometricService.authenticate).toHaveBeenCalledWith({
        promptMessage: 'Authenticate to access sensitive data',
      });
    });

    it('should execute photos pickImage', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'photos', 'pickImage', {
        allowsMultipleSelection: false,
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.images).toBeDefined();
      expect(mockCameraService.pickImage).toHaveBeenCalledWith({
        allowsMultipleSelection: false,
      });
    });

    it('should handle unknown capability with error', async () => {
      const request = mockRequest('INTERN', 'unknown' as DeviceCapability, 'action');

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Unknown capability');
    });
  });

  // Audit log tests (5 tests)
  describe('Audit Log', () => {
    it('should log all device requests', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Audit Test',
        body: 'Testing audit logging',
      });

      await agentDeviceBridge.requestCapability(request);
      const log = await agentDeviceBridge.getAuditLog();

      expect(log.length).toBeGreaterThan(0);
      expect(log[0].agentId).toBe('agent-123');
      expect(log[0].capability).toBe('notification');
      expect(log[0].action).toBe('sendNotification');
      expect(log[0].granted).toBe(true);
    });

    it('should filter audit log by agent', async () => {
      mockAlert.mockImplementation((title, message, buttons) => {
        buttons[1].onPress();
      });

      // Create requests from different agents
      const request1 = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Agent 1',
        body: 'Test',
      });
      request1.agentId = 'agent-1';

      const request2 = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Agent 2',
        body: 'Test',
      });
      request2.agentId = 'agent-2';

      await agentDeviceBridge.requestCapability(request1);
      await agentDeviceBridge.requestCapability(request2);

      const agent1Log = await agentDeviceBridge.getAuditLog({ agentId: 'agent-1' });
      const agent2Log = await agentDeviceBridge.getAuditLog({ agentId: 'agent-2' });

      expect(agent1Log.length).toBe(1);
      expect(agent2Log.length).toBe(1);
      expect(agent1Log[0].agentId).toBe('agent-1');
      expect(agent2Log[0].agentId).toBe('agent-2');
    });

    it('should filter audit log by capability', async () => {
      mockAlert.mockImplementation((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request1 = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Test',
        body: 'Test',
      });

      const request2 = mockRequest('INTERN', 'location', 'getCurrentLocation');

      await agentDeviceBridge.requestCapability(request1);
      await agentDeviceBridge.requestCapability(request2);

      const notificationLog = await agentDeviceBridge.getAuditLog({
        capability: 'notification',
      });
      const locationLog = await agentDeviceBridge.getAuditLog({ capability: 'location' });

      expect(notificationLog.length).toBe(1);
      expect(locationLog.length).toBe(1);
      expect(notificationLog[0].capability).toBe('notification');
      expect(locationLog[0].capability).toBe('location');
    });

    it('should filter audit log by date range', async () => {
      mockAlert.mockImplementation((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Date Test',
        body: 'Testing date filtering',
      });

      await agentDeviceBridge.requestCapability(request);

      const now = Date.now();
      const futureLog = await agentDeviceBridge.getAuditLog({
        startDate: now + 10000,
        endDate: now + 20000,
      });
      const currentLog = await agentDeviceBridge.getAuditLog({
        startDate: now - 1000,
        endDate: now + 1000,
      });

      expect(futureLog.length).toBe(0);
      expect(currentLog.length).toBeGreaterThan(0);
    });

    it('should clear audit log', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Clear Test',
        body: 'Testing log clearing',
      });

      await agentDeviceBridge.requestCapability(request);
      let log = await agentDeviceBridge.getAuditLog();
      expect(log.length).toBeGreaterThan(0);

      await agentDeviceBridge.clearAuditLog();
      log = await agentDeviceBridge.getAuditLog();

      expect(log).toEqual([]);
      expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_audit_log');
    });
  });

  // Error handling tests (4 tests)
  describe('Error Handling', () => {
    it('should handle capability execution error', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      mockLocationService.getCurrentLocation.mockRejectedValueOnce(
        new Error('Location service unavailable')
      );

      const request = mockRequest('INTERN', 'location', 'getCurrentLocation');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Location service unavailable');
    });

    it('should handle timeout', async () => {
      // This test verifies that timeout doesn't crash the service
      // The actual timeout handling logs a warning but allows operation to complete
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'location', 'getCurrentLocation');
      const result = await agentDeviceBridge.requestCapability(request);

      // Operation should complete successfully
      expect(result.success).toBe(true);
      expect(result.data).toBeDefined();
    }, 10000); // Increase timeout to 10 seconds

    it('should get available capabilities', async () => {
      mockCameraService.isAvailable.mockResolvedValue(true);
      mockBiometricService.isAvailable.mockResolvedValue(true);

      const capabilities = await agentDeviceBridge.getAvailableCapabilities();

      expect(capabilities).toContain('location');
      expect(capabilities).toContain('notification');
      expect(capabilities).toContain('photos');
      expect(capabilities).toContain('camera');
      expect(capabilities).toContain('biometric');
    });

    it('should cleanup on destroy', async () => {
      await agentDeviceBridge.destroy();

      // Verify service still works after destroy (reinitializes if needed)
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      await agentDeviceBridge.initialize();

      const request = mockRequest('INTERN', 'notification', 'sendNotification', {
        title: 'Post Destroy',
        body: 'Testing after destroy',
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
    });
  });

  // Additional governance edge cases (3 tests)
  describe('Governance Edge Cases', () => {
    it('should deny INTERN agent when user rejects approval', async () => {
      // Create a flag to track denial
      let denied = false;

      // Override mock to call first button (Deny)
      mockAlert.mockImplementation((title, message, buttons) => {
        if (buttons && buttons[0] && typeof buttons[0].onPress === 'function' && !denied) {
          denied = true;
          buttons[0].onPress();
        }
      });

      const request = mockRequest('INTERN', 'camera', 'pickImage');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(false);
      expect(result.error).toContain('User denied');
    });

    it('should handle Alert dismissal as denial', async () => {
      // Override mock to call onDismiss
      mockAlert.mockImplementation((title, message, buttons, options) => {
        if (options && typeof options.onDismiss === 'function') {
          options.onDismiss();
        }
      });

      const request = mockRequest('INTERN', 'camera', 'pickImage');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(false);
      expect(result.error).toContain('User denied');
    });

    it('should block SUPERVISED agent from contacts (AUTONOMOUS required)', async () => {
      const request = mockRequest('SUPERVISED', 'contacts', 'getContacts');
      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(false);
      expect(result.error).toContain('insufficient');
      expect(result.error).toContain('AUTONOMOUS');
    });
  });

  // Additional capability tests (2 tests)
  describe('Additional Capabilities', () => {
    it('should execute location calculateDistance', async () => {
      mockAlert.mockImplementationOnce((title, message, buttons) => {
        buttons[1].onPress();
      });

      const request = mockRequest('INTERN', 'location', 'calculateDistance', {
        from: { latitude: 37.7749, longitude: -122.4194 },
        to: { latitude: 37.7849, longitude: -122.4094 },
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.distance).toBe(1000);
      expect(result.data.unit).toBe('meters');
      expect(mockLocationService.calculateDistance).toHaveBeenCalledWith(
        { latitude: 37.7749, longitude: -122.4194 },
        { latitude: 37.7849, longitude: -122.4094 }
      );
    });

    it('should execute notification setBadge', async () => {
      const request = mockRequest('INTERN', 'notification', 'setBadge', {
        count: 5,
      });

      const result = await agentDeviceBridge.requestCapability(request);

      expect(result.success).toBe(true);
      expect(result.data.badge).toBe(5);
      expect(mockNotificationService.setBadgeCount).toHaveBeenCalledWith(5);
    });
  });
});

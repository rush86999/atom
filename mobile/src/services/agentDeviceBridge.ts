/**
 * Agent Device Bridge
 *
 * Enables AI agents to request and use device capabilities through governance-controlled API.
 *
 * Features:
 * - Agent device request API
 * - Governance check before permission grant
 * - User approval prompts for sensitive actions
 * - Capability result return to agent
 * - Audit logging for device usage
 * - Capability timeout handling
 * - Error handling for denials
 * - Device capability discovery API
 *
 * Security:
 * - All device requests require governance check
 * - Sensitive actions require user approval
 * - All operations logged for audit
 * - Automatic timeout for pending requests
 */

import { Platform, Alert } from 'react-native';
import { cameraService, CameraMode } from './cameraService';
import { locationService } from './locationService';
import { notificationService } from './notificationService';
import { biometricService } from './biometricService';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Types
export type DeviceCapability =
  | 'camera'
  | 'location'
  | 'notification'
  | 'biometric'
  | 'microphone'
  | 'contacts'
  | 'photos';

export type AgentMaturityLevel = 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS';

export interface DeviceRequest {
  requestId: string;
  agentId: string;
  agentName: string;
  maturityLevel: AgentMaturityLevel;
  capability: DeviceCapability;
  action: string;
  params?: Record<string, any>;
  timestamp: number;
  timeout?: number;
}

export interface DeviceResponse {
  requestId: string;
  success: boolean;
  data?: any;
  error?: string;
  timestamp: number;
}

export interface DeviceAuditLog {
  requestId: string;
  agentId: string;
  agentName: string;
  maturityLevel: AgentMaturityLevel;
  capability: DeviceCapability;
  action: string;
  granted: boolean;
  userApproved: boolean;
  reason?: string;
  timestamp: number;
}

// Configuration
const AUDIT_LOG_KEY = 'atom_device_audit_log';
const MAX_AUDIT_LOG_ENTRIES = 5000;
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const PENDING_REQUESTS_KEY = 'atom_pending_device_requests';

// Capability maturity requirements
const CAPABILITY_REQUIREMENTS: Record<
  DeviceCapability,
  { minMaturity: AgentMaturityLevel; requireApproval: boolean; description: string }
> = {
  camera: {
    minMaturity: 'INTERN',
    requireApproval: true,
    description: 'Access camera to capture photos or scan documents',
  },
  location: {
    minMaturity: 'INTERN',
    requireApproval: true,
    description: 'Access your current location',
  },
  notification: {
    minMaturity: 'INTERN',
    requireApproval: false,
    description: 'Send notifications to your device',
  },
  biometric: {
    minMaturity: 'AUTONOMOUS',
    requireApproval: true,
    description: 'Authenticate using biometric (Face ID/Touch ID)',
  },
  microphone: {
    minMaturity: 'SUPERVISED',
    requireApproval: true,
    description: 'Access microphone to record audio',
  },
  contacts: {
    minMaturity: 'AUTONOMOUS',
    requireApproval: true,
    description: 'Access your contacts',
  },
  photos: {
    minMaturity: 'INTERN',
    requireApproval: true,
    description: 'Access your photo library',
  },
};

// Maturity level hierarchy (higher index = more mature)
const MATURITY_HIERARCHY: Record<AgentMaturityLevel, number> = {
  STUDENT: 0,
  INTERN: 1,
  SUPERVISED: 2,
  AUTONOMOUS: 3,
};

/**
 * Agent Device Bridge Service
 */
class AgentDeviceBridgeService {
  private auditLog: DeviceAuditLog[] = [];
  private pendingRequests: Map<string, NodeJS.Timeout> = new Map();

  /**
   * Initialize the service
   */
  async initialize(): Promise<void> {
    try {
      await this.loadAuditLog();
      await this.cleanPendingRequests();
      console.log('AgentDeviceBridge: Initialized');
    } catch (error) {
      console.error('AgentDeviceBridge: Failed to initialize:', error);
    }
  }

  /**
   * Get available device capabilities
   */
  async getAvailableCapabilities(): Promise<DeviceCapability[]> {
    const capabilities: DeviceCapability[] = [];

    // Check camera
    const cameraAvailable = await cameraService.isAvailable();
    if (cameraAvailable) {
      capabilities.push('camera');
    }

    // Check location (always available on mobile)
    capabilities.push('location');

    // Check notifications
    capabilities.push('notification');

    // Check biometric
    const biometricAvailable = await biometricService.isAvailable();
    if (biometricAvailable) {
      capabilities.push('biometric');
    }

    // Photos (always available)
    capabilities.push('photos');

    return capabilities;
  }

  /**
   * Request device capability from agent
   */
  async requestCapability(request: DeviceRequest): Promise<DeviceResponse> {
    const startTime = Date.now();

    try {
      // Check if capability exists
      const requirement = CAPABILITY_REQUIREMENTS[request.capability];
      if (!requirement) {
        const error = `Unknown capability: ${request.capability}`;
        await this.logAudit(request, false, false, error);
        return this.createErrorResponse(request.requestId, error);
      }

      // Governance check: maturity level
      const agentMaturityLevel = MATURITY_HIERARCHY[request.maturityLevel];
      const requiredMaturityLevel = MATURITY_HIERARCHY[requirement.minMaturity];

      if (agentMaturityLevel < requiredMaturityLevel) {
        const error = `Agent maturity level (${request.maturityLevel}) insufficient for ${request.capability}. Requires ${requirement.minMaturity} or higher.`;
        await this.logAudit(request, false, false, error);
        return this.createErrorResponse(request.requestId, error);
      }

      // Governance check: user approval for sensitive actions
      if (requirement.requireApproval) {
        const approved = await this.requestUserApproval(request, requirement.description);
        if (!approved) {
          const error = 'User denied permission request';
          await this.logAudit(request, false, true, error);
          return this.createErrorResponse(request.requestId, error);
        }
      }

      // Set timeout for long-running operations
      const timeout = request.timeout || DEFAULT_TIMEOUT;
      const timeoutId = setTimeout(() => {
        this.handleTimeout(request.requestId);
      }, timeout);

      this.pendingRequests.set(request.requestId, timeoutId);

      // Execute the capability request
      const result = await this.executeCapability(request);

      // Clear timeout
      clearTimeout(timeoutId);
      this.pendingRequests.delete(request.requestId);

      // Log success
      await this.logAudit(request, true, requirement.requireApproval);

      return {
        requestId: request.requestId,
        success: true,
        data: result,
        timestamp: Date.now(),
      };
    } catch (error: any) {
      // Log failure
      await this.logAudit(request, false, false, error.message);

      return this.createErrorResponse(request.requestId, error.message);
    }
  }

  /**
   * Request user approval for capability
   */
  private async requestUserApproval(request: DeviceRequest, description: string): Promise<boolean> {
    return new Promise((resolve) => {
      Alert.alert(
        `${request.agentName} Requesting Permission`,
        `${request.agentName} wants to:\n\n${description}\n\nDo you approve this request?`,
        [
          {
            text: 'Deny',
            onPress: () => resolve(false),
            style: 'cancel',
          },
          {
            text: 'Approve',
            onPress: () => resolve(true),
          },
        ],
        { cancelable: true, onDismiss: () => resolve(false) }
      );
    });
  }

  /**
   * Execute the capability request
   */
  private async executeCapability(request: DeviceRequest): Promise<any> {
    switch (request.capability) {
      case 'camera':
        return await this.executeCameraAction(request);

      case 'location':
        return await this.executeLocationAction(request);

      case 'notification':
        return await this.executeNotificationAction(request);

      case 'biometric':
        return await this.executeBiometricAction(request);

      case 'photos':
        return await this.executePhotosAction(request);

      case 'microphone':
        throw new Error('Microphone capability not yet implemented');

      case 'contacts':
        throw new Error('Contacts capability not yet implemented');

      default:
        throw new Error(`Unknown capability: ${request.capability}`);
    }
  }

  /**
   * Execute camera action
   */
  private async executeCameraAction(request: DeviceRequest): Promise<any> {
    const action = request.action;
    const params = request.params || {};

    switch (action) {
      case 'takePhoto': {
        await cameraService.requestPermissions();
        const cameraRef = params.cameraRef;
        if (!cameraRef) {
          throw new Error('Camera ref is required for takePhoto');
        }
        // Note: This requires a valid camera ref from the UI
        throw new Error('takePhoto requires camera UI component');
      }

      case 'pickImage': {
        const images = await cameraService.pickImage(params);
        return { images, count: images.length };
      }

      case 'scanBarcode': {
        // Note: This requires active camera scanning session
        throw new Error('scanBarcode requires active camera scanning session');
      }

      default:
        throw new Error(`Unknown camera action: ${action}`);
    }
  }

  /**
   * Execute location action
   */
  private async executeLocationAction(request: DeviceRequest): Promise<any> {
    const action = request.action;
    const params = request.params || {};

    switch (action) {
      case 'getCurrentLocation': {
        await locationService.requestPermissions();
        const location = await locationService.getCurrentLocation();
        return location;
      }

      case 'startTracking': {
        await locationService.requestPermissions(false, params.background || false);
        const started = await locationService.startTracking();
        return { tracking: started };
      }

      case 'stopTracking': {
        await locationService.stopTracking();
        return { tracking: false };
      }

      case 'calculateDistance': {
        const { from, to } = params;
        if (!from || !to) {
          throw new Error('from and to coordinates are required');
        }
        const distance = locationService.calculateDistance(from, to);
        return { distance, unit: 'meters' };
      }

      case 'reverseGeocode': {
        const { coordinates } = params;
        if (!coordinates) {
          throw new Error('coordinates are required');
        }
        const address = await locationService.reverseGeocode(coordinates);
        return { address };
      }

      default:
        throw new Error(`Unknown location action: ${action}`);
    }
  }

  /**
   * Execute notification action
   */
  private async executeNotificationAction(request: DeviceRequest): Promise<any> {
    const action = request.action;
    const params = request.params || {};

    switch (action) {
      case 'sendNotification': {
        const { title, body, data } = params;
        if (!title || !body) {
          throw new Error('title and body are required');
        }
        await notificationService.sendLocalNotification({ title, body, data });
        return { sent: true };
      }

      case 'scheduleNotification': {
        const { title, body, triggerSeconds, data } = params;
        if (!title || !body || !triggerSeconds) {
          throw new Error('title, body, and triggerSeconds are required');
        }
        const identifier = await notificationService.scheduleNotification(
          { title, body, data },
          triggerSeconds
        );
        return { scheduled: true, identifier };
      }

      case 'setBadge': {
        const { count } = params;
        if (typeof count !== 'number') {
          throw new Error('count is required');
        }
        await notificationService.setBadgeCount(count);
        return { badge: count };
      }

      default:
        throw new Error(`Unknown notification action: ${action}`);
    }
  }

  /**
   * Execute biometric action
   */
  private async executeBiometricAction(request: DeviceRequest): Promise<any> {
    const action = request.action;
    const params = request.params || {};

    switch (action) {
      case 'authenticate': {
        const result = await biometricService.authenticate({
          promptMessage: params.promptMessage || `${request.agentName} requires authentication`,
        });
        return result;
      }

      case 'checkAvailability': {
        const available = await biometricService.isAvailable();
        const enrolled = await biometricService.isEnrolled();
        const type = await biometricService.getBiometricType();
        return { available, enrolled, type };
      }

      default:
        throw new Error(`Unknown biometric action: ${action}`);
    }
  }

  /**
   * Execute photos action
   */
  private async executePhotosAction(request: DeviceRequest): Promise<any> {
    const action = request.action;
    const params = request.params || {};

    switch (action) {
      case 'pickImage': {
        const images = await cameraService.pickImage(params);
        return { images, count: images.length };
      }

      default:
        throw new Error(`Unknown photos action: ${action}`);
    }
  }

  /**
   * Handle request timeout
   */
  private handleTimeout(requestId: string): void {
    console.warn('AgentDeviceBridge: Request timed out', requestId);
    this.pendingRequests.delete(requestId);
  }

  /**
   * Create error response
   */
  private createErrorResponse(requestId: string, error: string): DeviceResponse {
    return {
      requestId,
      success: false,
      error,
      timestamp: Date.now(),
    };
  }

  /**
   * Log device usage for audit
   */
  private async logAudit(
    request: DeviceRequest,
    granted: boolean,
    userApproved: boolean,
    reason?: string
  ): Promise<void> {
    const logEntry: DeviceAuditLog = {
      requestId: request.requestId,
      agentId: request.agentId,
      agentName: request.agentName,
      maturityLevel: request.maturityLevel,
      capability: request.capability,
      action: request.action,
      granted,
      userApproved,
      reason,
      timestamp: Date.now(),
    };

    this.auditLog.push(logEntry);

    // Limit log size
    if (this.auditLog.length > MAX_AUDIT_LOG_ENTRIES) {
      this.auditLog = this.auditLog.slice(-MAX_AUDIT_LOG_ENTRIES);
    }

    await this.saveAuditLog();
  }

  /**
   * Get audit log
   */
  async getAuditLog(filters?: {
    agentId?: string;
    capability?: DeviceCapability;
    startDate?: number;
    endDate?: number;
    limit?: number;
  }): Promise<DeviceAuditLog[]> {
    let log = [...this.auditLog];

    // Apply filters
    if (filters?.agentId) {
      log = log.filter((entry) => entry.agentId === filters.agentId);
    }

    if (filters?.capability) {
      log = log.filter((entry) => entry.capability === filters.capability);
    }

    if (filters?.startDate) {
      log = log.filter((entry) => entry.timestamp >= filters.startDate!);
    }

    if (filters?.endDate) {
      log = log.filter((entry) => entry.timestamp <= filters.endDate!);
    }

    // Sort by timestamp (newest first)
    log.sort((a, b) => b.timestamp - a.timestamp);

    // Apply limit
    if (filters?.limit) {
      log = log.slice(0, filters.limit);
    }

    return log;
  }

  /**
   * Clear audit log
   */
  async clearAuditLog(): Promise<void> {
    this.auditLog = [];
    await AsyncStorage.removeItem(AUDIT_LOG_KEY);
    console.log('AgentDeviceBridge: Audit log cleared');
  }

  /**
   * Save audit log to storage
   */
  private async saveAuditLog(): Promise<void> {
    try {
      await AsyncStorage.setItem(AUDIT_LOG_KEY, JSON.stringify(this.auditLog));
    } catch (error) {
      console.error('AgentDeviceBridge: Failed to save audit log:', error);
    }
  }

  /**
   * Load audit log from storage
   */
  private async loadAuditLog(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem(AUDIT_LOG_KEY);
      if (data) {
        this.auditLog = JSON.parse(data);
        console.log('AgentDeviceBridge: Audit log loaded', this.auditLog.length, 'entries');
      }
    } catch (error) {
      console.error('AgentDeviceBridge: Failed to load audit log:', error);
    }
  }

  /**
   * Clean up pending requests on service restart
   */
  private async cleanPendingRequests(): Promise<void> {
    // Clear any pending timeouts
    this.pendingRequests.forEach((timeoutId) => {
      clearTimeout(timeoutId);
    });
    this.pendingRequests.clear();
  }

  /**
   * Get capability requirements
   */
  getCapabilityRequirements(capability: DeviceCapability) {
    return CAPABILITY_REQUIREMENTS[capability];
  }

  /**
   * Get all capability requirements
   */
  getAllCapabilityRequirements() {
    return CAPABILITY_REQUIREMENTS;
  }

  /**
   * Check if agent can use capability
   */
  canAgentUseCapability(agentMaturityLevel: AgentMaturityLevel, capability: DeviceCapability): boolean {
    const requirement = CAPABILITY_REQUIREMENTS[capability];
    if (!requirement) {
      return false;
    }

    const agentLevel = MATURITY_HIERARCHY[agentMaturityLevel];
    const requiredLevel = MATURITY_HIERARCHY[requirement.minMaturity];

    return agentLevel >= requiredLevel;
  }

  /**
   * Cleanup
   */
  async destroy(): Promise<void> {
    // Clear all pending timeouts
    this.pendingRequests.forEach((timeoutId) => {
      clearTimeout(timeoutId);
    });
    this.pendingRequests.clear();
  }

  /**
   * Reset service state (for testing)
   */
  _resetState(): void {
    this.auditLog = [];
    this.pendingRequests.forEach((timeoutId) => {
      clearTimeout(timeoutId);
    });
    this.pendingRequests.clear();
  }
}

// Export singleton instance
export const agentDeviceBridge = new AgentDeviceBridgeService();

export default agentDeviceBridge;

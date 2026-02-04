/**
 * Device WebSocket Service
 *
 * Handles real-time bidirectional communication with the Atom backend.
 * Processes device commands (camera, location, notifications, etc.) and returns results.
 *
 * Architecture:
 * - Mobile App <--Socket.IO--> Backend (FastAPI + WebSocket)
 * - App registers device on connect
 * - Backend sends commands, app executes and returns results
 * - Heartbeat keep-alive every 30 seconds
 */

import { io, Socket } from 'socket.io-client';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import * as Camera from 'expo-camera';
import * as Location from 'expo-location';
import * as Notifications from 'expo-notifications';
import FileSystem from 'expo-file-system';

// Types
export interface DeviceInfo {
  device_node_id: string;
  name: string;
  node_type: string;
  platform: string;
  platform_version: string;
  architecture: string;
  capabilities: string[];
  capabilities_detailed: Record<string, any>;
  hardware_info: Record<string, any>;
}

export interface CommandMessage {
  type: 'command';
  command_id: string;
  command: string;
  params: Record<string, any>;
  timestamp: string;
}

export interface ResultMessage {
  type: 'result';
  command_id: string;
  success: boolean;
  data?: Record<string, any>;
  file_path?: string;
  error?: string;
  timestamp: string;
}

export interface ErrorMessage {
  type: 'error';
  error: string;
  timestamp: string;
}

// Service singleton
class DeviceSocketService {
  private socket: Socket | null = null;
  private deviceInfo: DeviceInfo | null = null;
  private isConnected = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private heartbeatInterval: NodeJS.Timeout | null = null;

  // Event handlers
  private commandHandlers: Map<string, (command: CommandMessage) => Promise<ResultMessage>> = new Map();

  constructor() {
    // Configure notification handler
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });
  }

  /**
   * Connect to the backend WebSocket server
   */
  async connect(): Promise<boolean> {
    try {
      // Get auth token
      const token = await AsyncStorage.getItem('auth_token');
      if (!token) {
        console.error('[DeviceSocket] No auth token found');
        return false;
      }

      // Get or create device ID
      let deviceId = await AsyncStorage.getItem('device_node_id');
      if (!deviceId) {
        deviceId = this.generateDeviceId();
        await AsyncStorage.setItem('device_node_id', deviceId);
      }

      // Build device info
      this.deviceInfo = await this.buildDeviceInfo(deviceId);

      // WebSocket server URL
      const wsUrl = __DEV__
        ? 'http://localhost:8000'
        : 'https://api.atom-platform.com';

      // Connect with Socket.IO
      this.socket = io(wsUrl, {
        query: { token },
        transports: ['websocket'],
        reconnection: true,
        reconnectionAttempts: this.maxReconnectAttempts,
        reconnectionDelay: this.reconnectDelay,
      });

      // Setup event handlers
      this.setupEventHandlers();

      return true;
    } catch (error: any) {
      console.error('[DeviceSocket] Connection error:', error.message);
      return false;
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }

    this.isConnected = false;
    console.log('[DeviceSocket] Disconnected');
  }

  /**
   * Setup Socket.IO event handlers
   */
  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('[DeviceSocket] Connected to server');
      this.isConnected = true;
      this.reconnectAttempts = 0;

      // Register device
      this.registerDevice();
    });

    this.socket.on('connect_error', (error: any) => {
      console.error('[DeviceSocket] Connection error:', error.message);
      this.reconnectAttempts++;

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('[DeviceSocket] Max reconnection attempts reached');
        this.disconnect();
      }
    });

    this.socket.on('disconnect', (reason: string) => {
      console.log('[DeviceSocket] Disconnected:', reason);
      this.isConnected = false;

      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
    });

    this.socket.on('message', async (message: any) => {
      await this.handleMessage(message);
    });

    this.socket.on('registered', (data: any) => {
      console.log('[DeviceSocket] Device registered:', data.device_node_id);

      // Start heartbeat
      this.startHeartbeat();
    });

    this.socket.on('heartbeat_ack', (data: any) => {
      // Heartbeat acknowledged
    });

    this.socket.on('heartbeat_probe', async (data: any) => {
      // Respond to heartbeat probe
      this.sendHeartbeat();
    });
  }

  /**
   * Register device with the server
   */
  private registerDevice(): void {
    if (!this.socket || !this.deviceInfo) return;

    const registerMessage = {
      type: 'register',
      device_node_id: this.deviceInfo.device_node_id,
      device_info: this.deviceInfo,
    };

    this.socket.emit('message', registerMessage);
    console.log('[DeviceSocket] Registering device...');
  }

  /**
   * Start heartbeat interval
   */
  private startHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, 30000); // Every 30 seconds

    console.log('[DeviceSocket] Heartbeat started');
  }

  /**
   * Send heartbeat message
   */
  private sendHeartbeat(): void {
    if (!this.socket || !this.isConnected) return;

    this.socket.emit('message', {
      type: 'heartbeat',
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Handle incoming message from server
   */
  private async handleMessage(message: any): Promise<void> {
    const msgType = message.type;

    switch (msgType) {
      case 'command':
        await this.handleCommand(message as CommandMessage);
        break;

      case 'connected':
        console.log('[DeviceSocket] Server welcome message:', message);
        break;

      default:
        console.warn('[DeviceSocket] Unknown message type:', msgType);
    }
  }

  /**
   * Handle command from server
   */
  private async handleCommand(command: CommandMessage): Promise<void> {
    console.log('[DeviceSocket] Received command:', command.command);

    try {
      let result: ResultMessage;

      switch (command.command) {
        case 'camera_snap':
          result = await this.handleCameraSnap(command);
          break;

        case 'screen_record_start':
          result = await this.handleScreenRecordStart(command);
          break;

        case 'screen_record_stop':
          result = await this.handleScreenRecordStop(command);
          break;

        case 'get_location':
          result = await this.handleGetLocation(command);
          break;

        case 'send_notification':
          result = await this.handleSendNotification(command);
          break;

        case 'execute_command':
          result = await this.handleExecuteCommand(command);
          break;

        default:
          result = {
            type: 'result',
            command_id: command.command_id,
            success: false,
            error: `Unknown command: ${command.command}`,
            timestamp: new Date().toISOString(),
          };
      }

      // Send result back to server
      this.sendResult(result);

    } catch (error: any) {
      console.error('[DeviceSocket] Command error:', error);

      const errorResult: ResultMessage = {
        type: 'result',
        command_id: command.command_id,
        success: false,
        error: error.message || 'Command failed',
        timestamp: new Date().toISOString(),
      };

      this.sendResult(errorResult);
    }
  }

  /**
   * Handle camera snap command
   */
  private async handleCameraSnap(command: CommandMessage): Promise<ResultMessage> {
    try {
      // Request camera permissions
      const { status } = await Camera.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        return {
          type: 'result',
          command_id: command.command_id,
          success: false,
          error: 'Camera permission not granted',
          timestamp: new Date().toISOString(),
        };
      }

      // Take a picture
      const result = await Camera.takePictureAsync({
        quality: command.params.quality || 0.8,
        base64: true,
        exif: true,
      });

      const savePath = command.params.save_path || `${FileSystem.cacheDirectory}camera_${command.command_id}.jpg`;

      // If save_path is provided, save the file
      if (command.params.save_path) {
        await FileSystem.copyAsync({
          from: result.uri,
          to: savePath,
        });
      }

      return {
        type: 'result',
        command_id: command.command_id,
        success: true,
        data: {
          base64_data: result.base64,
          width: result.width,
          height: result.height,
        },
        file_path: savePath,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      return {
        type: 'result',
        command_id: command.command_id,
        success: false,
        error: error instanceof Error ? error.message : 'Failed to capture photo',
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Handle screen record start command
   * NOTE: Screen recording on mobile requires platform-specific solutions:
   * - iOS: ReplayKit (requires native module)
   * - Android: MediaProjection API (requires native module)
   * Consider using: react-native-recording-screen-lib or similar
   */
  private async handleScreenRecordStart(command: CommandMessage): Promise<ResultMessage> {
    // Screen recording not implemented - requires native module
    // Recommended package: react-native-recording-screen-lib
    return {
      type: 'result',
      command_id: command.command_id,
      success: false,
      error: 'Screen recording requires native module (react-native-recording-screen-lib recommended)',
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Handle screen record stop command
   * NOTE: Screen recording on mobile requires platform-specific solutions
   */
  private async handleScreenRecordStop(command: CommandMessage): Promise<ResultMessage> {
    return {
      type: 'result',
      command_id: command.command_id,
      success: false,
      error: 'Screen recording requires native module (react-native-recording-screen-lib recommended)',
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Handle get location command
   */
  private async handleGetLocation(command: CommandMessage): Promise<ResultMessage> {
    try {
      // Request location permissions
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        return {
          type: 'result',
          command_id: command.command_id,
          success: false,
          error: 'Location permission not granted',
          timestamp: new Date().toISOString(),
        };
      }

      // Get current location
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      return {
        type: 'result',
        command_id: command.command_id,
        success: true,
        data: {
          latitude: location.coords.latitude,
          longitude: location.coords.longitude,
          altitude: location.coords.altitude,
          accuracy: location.coords.accuracy,
          heading: location.coords.heading,
          speed: location.coords.speed,
          timestamp: new Date().toISOString(),
        },
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      return {
        type: 'result',
        command_id: command.command_id,
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get location',
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Handle send notification command
   */
  private async handleSendNotification(command: CommandMessage): Promise<ResultMessage> {
    try {
      // Request notification permissions
      const { status } = await Notifications.requestPermissionsAsync();
      if (status !== 'granted') {
        return {
          type: 'result',
          command_id: command.command_id,
          success: false,
          error: 'Notification permission not granted',
          timestamp: new Date().toISOString(),
        };
      }

      // Send notification
      await Notifications.scheduleNotificationAsync({
        content: {
          title: command.params.title || 'Atom Notification',
          body: command.params.body || '',
          data: command.params.data || {},
          sound: command.params.sound || 'default',
          priority: Notifications.AndroidNotificationPriority.HIGH,
        },
        trigger: null, // Show immediately
      });

      return {
        type: 'result',
        command_id: command.command_id,
        success: true,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      return {
        type: 'result',
        command_id: command.command_id,
        success: false,
        error: error instanceof Error ? error.message : 'Failed to send notification',
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Handle execute command command
   */
  private async handleExecuteCommand(command: CommandMessage): Promise<ResultMessage> {
    // SECURITY: Command execution is NOT available on mobile
    // This is only for desktop devices
    return {
      type: 'result',
      command_id: command.command_id,
      success: false,
      error: 'Command execution not supported on mobile devices',
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Send result message back to server
   */
  private sendResult(result: ResultMessage): void {
    if (!this.socket || !this.isConnected) {
      console.error('[DeviceSocket] Cannot send result: not connected');
      return;
    }

    this.socket.emit('message', result);
    console.log('[DeviceSocket] Sent result for command:', result.command_id);
  }

  /**
   * Build device info object
   */
  private async buildDeviceInfo(deviceId: string): Promise<DeviceInfo> {
    return {
      device_node_id: deviceId,
      name: `${Device.deviceName} (${Device.modelId})`,
      node_type: 'mobile',
      platform: Platform.OS,
      platform_version: Platform.Version as string,
      architecture: await this.getArchitecture(),
      capabilities: await this.getCapabilities(),
      capabilities_detailed: {},
      hardware_info: {
        brand: Device.brand,
        manufacturer: Device.manufacturer,
        model_name: Device.modelName,
        design_name: Device.designName,
        product_name: Device.deviceName,
        year_class: Device.deviceYearClass,
        total_memory: Device.totalMemory,
      },
    };
  }

  /**
   * Get device architecture
   */
  private async getArchitecture(): Promise<string> {
    // Get actual device architecture
    return Platform.OS === 'ios' ? 'arm64' : 'arm64-v8a';
  }

  /**
   * Get device capabilities
   */
  private async getCapabilities(): Promise<string[]> {
    const capabilities: string[] = [];

    // Check camera permission
    const cameraStatus = await Camera.getCameraPermissionsAsync();
    if (cameraStatus.status === 'granted') {
      capabilities.push('camera');
    }

    // Check location permission
    const locationStatus = await Location.getForegroundPermissionsAsync();
    if (locationStatus.status === 'granted') {
      capabilities.push('location');
    }

    // Check notification permission
    const notificationStatus = await Notifications.getPermissionsAsync();
    if (notificationStatus.status === 'granted') {
      capabilities.push('notification');
    }

    // Screen recording is platform-dependent but requires native module
    // Not included until native module is implemented

    return capabilities;
  }

  /**
   * Generate a unique device ID
   */
  private generateDeviceId(): string {
    return `mobile_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
  }

  /**
   * Check if connected
   */
  connected(): boolean {
    return this.isConnected;
  }
}

// Export singleton instance
export const deviceSocketService = new DeviceSocketService();
export default deviceSocketService;

// Google Real-time Notifications Service
import { invoke } from '@tauri-apps/api/tauri';
import type { 
  GoogleEmail, 
  GoogleCalendarEvent, 
  GoogleDriveFile,
  GoogleConnectionStatus 
} from '../types/googleTypes';

interface NotificationConfig {
  emailEnabled: boolean;
  calendarEnabled: boolean;
  driveEnabled: boolean;
  realTimeUpdates: boolean;
  webhookUrl: string;
  pushNotifications: boolean;
  notificationThreshold: number;
}

interface NotificationEvent {
  id: string;
  type: 'email' | 'calendar' | 'drive' | 'connection';
  timestamp: number;
  userId: string;
  data: any;
  metadata: {
    service: string;
    action: string;
    severity: 'info' | 'warning' | 'error';
  };
}

interface Subscription {
  id: string;
  userId: string;
  service: string;
  resource: string;
  channel: string;
  webhookId?: string;
  resourceId?: string;
  expirationTime: number;
  active: boolean;
}

interface NotificationCallback {
  (event: NotificationEvent): void;
}

export class GoogleNotificationService {
  private static instance: GoogleNotificationService;
  private userId: string = '';
  private config: NotificationConfig;
  private subscriptions: Map<string, Subscription> = new Map();
  private callbacks: Map<string, NotificationCallback[]> = new Map();
  private eventQueue: NotificationEvent[] = [];
  private isProcessing: boolean = false;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private lastHeartbeat: number = 0;

  private constructor() {
    this.config = {
      emailEnabled: true,
      calendarEnabled: true,
      driveEnabled: true,
      realTimeUpdates: true,
      webhookUrl: '',
      pushNotifications: true,
      notificationThreshold: 100
    };
  }

  static getInstance(): GoogleNotificationService {
    if (!GoogleNotificationService.instance) {
      GoogleNotificationService.instance = new GoogleNotificationService();
    }
    return GoogleNotificationService.instance;
  }

  // Initialize notification service
  async initialize(userId: string): Promise<{ success: boolean; error?: string }> {
    try {
      this.userId = userId;
      
      // Initialize WebSocket connection
      await this.initializeWebSocket();
      
      // Start heartbeat
      this.startHeartbeat();
      
      // Resume existing subscriptions
      await this.resumeSubscriptions();
      
      // Start processing queue
      this.startEventProcessing();
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  // Initialize WebSocket connection
  private async initializeWebSocket(): Promise<void> {
    try {
      await invoke('google_start_websocket', {
        userId: this.userId,
        config: this.config
      });
    } catch (error) {
      console.error('Failed to initialize WebSocket:', error);
      throw error;
    }
  }

  // Subscribe to Gmail notifications
  async subscribeToGmail(
    labelIds?: string[],
    webhookUrl?: string
  ): Promise<{ success: boolean; subscription?: string; error?: string }> {
    try {
      const response = await invoke('google_subscribe_gmail', {
        userId: this.userId,
        labelIds: labelIds || ['INBOX'],
        webhookUrl: webhookUrl || this.config.webhookUrl
      });

      const subscription = response as Subscription;
      
      if (subscription.active) {
        this.subscriptions.set(subscription.id, subscription);
        return { 
          success: true, 
          subscription: subscription.id 
        };
      } else {
        return { 
          success: false, 
          error: 'Failed to activate Gmail subscription' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  // Subscribe to Calendar notifications
  async subscribeToCalendar(
    calendarId: string = 'primary',
    webhookUrl?: string
  ): Promise<{ success: boolean; subscription?: string; error?: string }> {
    try {
      const response = await invoke('google_subscribe_calendar', {
        userId: this.userId,
        calendarId,
        webhookUrl: webhookUrl || this.config.webhookUrl
      });

      const subscription = response as Subscription;
      
      if (subscription.active) {
        this.subscriptions.set(subscription.id, subscription);
        return { 
          success: true, 
          subscription: subscription.id 
        };
      } else {
        return { 
          success: false, 
          error: 'Failed to activate Calendar subscription' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  // Subscribe to Drive notifications
  async subscribeToDrive(
    fileId?: string,
    webhookUrl?: string
  ): Promise<{ success: boolean; subscription?: string; error?: string }> {
    try {
      const response = await invoke('google_subscribe_drive', {
        userId: this.userId,
        fileId,
        webhookUrl: webhookUrl || this.config.webhookUrl
      });

      const subscription = response as Subscription;
      
      if (subscription.active) {
        this.subscriptions.set(subscription.id, subscription);
        return { 
          success: true, 
          subscription: subscription.id 
        };
      } else {
        return { 
          success: false, 
          error: 'Failed to activate Drive subscription' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  // Unsubscribe from notifications
  async unsubscribe(subscriptionId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const subscription = this.subscriptions.get(subscriptionId);
      
      if (!subscription) {
        return { 
          success: false, 
          error: 'Subscription not found' 
        };
      }

      await invoke('google_unsubscribe', {
        userId: this.userId,
        subscriptionId,
        channelId: subscription.channel,
        resourceId: subscription.resourceId
      });

      this.subscriptions.delete(subscriptionId);
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  // Unsubscribe from all notifications
  async unsubscribeAll(): Promise<{ success: boolean; error?: string }> {
    try {
      const unsubscribePromises = Array.from(this.subscriptions.keys())
        .map(id => this.unsubscribe(id));
      
      await Promise.all(unsubscribePromises);
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  }

  // Register notification callback
  onNotification(eventType: string, callback: NotificationCallback): void {
    if (!this.callbacks.has(eventType)) {
      this.callbacks.set(eventType, []);
    }
    
    this.callbacks.get(eventType)!.push(callback);
  }

  // Remove notification callback
  offNotification(eventType: string, callback: NotificationCallback): void {
    const callbacks = this.callbacks.get(eventType);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  // Handle incoming notification event
  async handleNotificationEvent(event: NotificationEvent): Promise<void> {
    // Add to queue
    this.eventQueue.push(event);
    
    // Limit queue size
    if (this.eventQueue.length > this.config.notificationThreshold) {
      this.eventQueue.shift(); // Remove oldest event
    }
    
    // Start processing if not already running
    if (!this.isProcessing) {
      this.processEvents();
    }
  }

  // Process events from queue
  private async processEvents(): Promise<void> {
    if (this.isProcessing || this.eventQueue.length === 0) {
      return;
    }

    this.isProcessing = true;

    while (this.eventQueue.length > 0) {
      const event = this.eventQueue.shift()!;
      
      try {
        // Call relevant callbacks
        await this.triggerCallbacks(event);
        
        // Handle specific event types
        await this.handleSpecificEvent(event);
        
      } catch (error) {
        console.error('Error processing notification event:', error);
      }
    }

    this.isProcessing = false;
  }

  // Trigger relevant callbacks
  private async triggerCallbacks(event: NotificationEvent): Promise<void> {
    const callbacks = this.callbacks.get(event.type);
    if (callbacks) {
      for (const callback of callbacks) {
        try {
          await callback(event);
        } catch (error) {
          console.error('Error in notification callback:', error);
        }
      }
    }
  }

  // Handle specific event types
  private async handleSpecificEvent(event: NotificationEvent): Promise<void> {
    switch (event.type) {
      case 'email':
        await this.handleEmailNotification(event);
        break;
      case 'calendar':
        await this.handleCalendarNotification(event);
        break;
      case 'drive':
        await this.handleDriveNotification(event);
        break;
      case 'connection':
        await this.handleConnectionNotification(event);
        break;
    }
  }

  // Handle email notifications
  private async handleEmailNotification(event: NotificationEvent): Promise<void> {
    if (!this.config.emailEnabled) return;

    const emailData = event.data as GoogleEmail;
    
    // Update cache if needed
    if (emailData.id) {
      // Invalidate relevant cache entries
      // await googleCache.invalidate(this.userId, 'list_emails');
    }
    
    // Show desktop notification if enabled
    if (this.config.pushNotifications && !emailData.isRead) {
      await this.showDesktopNotification({
        title: `New email from ${emailData.from}`,
        body: emailData.subject,
        icon: '📧'
      });
    }
  }

  // Handle calendar notifications
  private async handleCalendarNotification(event: NotificationEvent): Promise<void> {
    if (!this.config.calendarEnabled) return;

    const eventData = event.data as GoogleCalendarEvent;
    
    // Update cache if needed
    if (eventData.id) {
      // await googleCache.invalidate(this.userId, 'list_events');
    }
    
    // Show desktop notification if enabled
    if (this.config.pushNotifications) {
      await this.showDesktopNotification({
        title: `Calendar: ${eventData.summary}`,
        body: `Starts at ${eventData.startTime}`,
        icon: '📅'
      });
    }
  }

  // Handle drive notifications
  private async handleDriveNotification(event: NotificationEvent): Promise<void> {
    if (!this.config.driveEnabled) return;

    const fileData = event.data as GoogleDriveFile;
    
    // Update cache if needed
    if (fileData.id) {
      // await googleCache.invalidate(this.userId, 'list_files');
    }
    
    // Show desktop notification if enabled
    if (this.config.pushNotifications) {
      await this.showDesktopNotification({
        title: `Drive: ${fileData.name}`,
        body: `Modified at ${fileData.modifiedTime}`,
        icon: '📁'
      });
    }
  }

  // Handle connection notifications
  private async handleConnectionNotification(event: NotificationEvent): Promise<void> {
    const connectionData = event.data as GoogleConnectionStatus;
    
    if (!connectionData.connected) {
      // Schedule reconnection
      this.scheduleReconnection();
      
      await this.showDesktopNotification({
        title: 'Google Connection Lost',
        body: 'Attempting to reconnect...',
        icon: '⚠️'
      });
    } else {
      // Cancel reconnection timer
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    }
  }

  // Show desktop notification
  private async showDesktopNotification(notification: {
    title: string;
    body: string;
    icon: string;
  }): Promise<void> {
    try {
      await invoke('show_notification', {
        title: notification.title,
        body: notification.body,
        icon: notification.icon
      });
    } catch (error) {
      console.error('Failed to show desktop notification:', error);
    }
  }

  // Schedule reconnection
  private scheduleReconnection(): void {
    if (this.reconnectTimer) return;

    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.initializeWebSocket();
        await this.resumeSubscriptions();
      } catch (error) {
        console.error('Reconnection failed:', error);
        // Schedule another attempt
        this.scheduleReconnection();
      }
    }, 5000); // Reconnect after 5 seconds
  }

  // Resume existing subscriptions
  private async resumeSubscriptions(): Promise<void> {
    try {
      const existingSubscriptions = await invoke('google_get_subscriptions', {
        userId: this.userId
      }) as Subscription[];

      for (const subscription of existingSubscriptions) {
        if (subscription.active && Date.now() < subscription.expirationTime) {
          this.subscriptions.set(subscription.id, subscription);
        }
      }
    } catch (error) {
      console.error('Failed to resume subscriptions:', error);
    }
  }

  // Start heartbeat
  private startHeartbeat(): void {
    setInterval(() => {
      this.lastHeartbeat = Date.now();
      
      // Check connection health
      this.checkConnectionHealth();
    }, 30000); // 30 seconds
  }

  // Check connection health
  private async checkConnectionHealth(): Promise<void> {
    try {
      const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat;
      
      if (timeSinceLastHeartbeat > 60000) { // 1 minute
        // Connection seems unhealthy
        await this.handleNotificationEvent({
          id: 'health_check',
          type: 'connection',
          timestamp: Date.now(),
          userId: this.userId,
          data: { connected: false },
          metadata: {
            service: 'notifications',
            action: 'health_check',
            severity: 'warning'
          }
        });
      }
    } catch (error) {
      console.error('Health check failed:', error);
    }
  }

  // Start event processing
  private startEventProcessing(): void {
    // Event processing is already handled by handleNotificationEvent
    // This is just a placeholder for any additional setup
  }

  // Get subscription status
  getSubscriptionStatus(): {
    totalSubscriptions: number;
    activeSubscriptions: number;
    services: string[];
  } {
    const subscriptions = Array.from(this.subscriptions.values());
    const activeSubscriptions = subscriptions.filter(sub => sub.active);
    const services = [...new Set(subscriptions.map(sub => sub.service))];

    return {
      totalSubscriptions: subscriptions.length,
      activeSubscriptions: activeSubscriptions.length,
      services
    };
  }

  // Update configuration
  updateConfig(config: Partial<NotificationConfig>): void {
    this.config = { ...this.config, ...config };
  }

  // Get current configuration
  getConfig(): NotificationConfig {
    return { ...this.config };
  }

  // Cleanup
  async cleanup(): Promise<void> {
    try {
      // Unsubscribe from all notifications
      await this.unsubscribeAll();
      
      // Clear callbacks
      this.callbacks.clear();
      
      // Clear event queue
      this.eventQueue.length = 0;
      
      // Clear reconnection timer
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    } catch (error) {
      console.error('Cleanup failed:', error);
    }
  }
}

// Export singleton instance
export const googleNotifications = GoogleNotificationService.getInstance();

// Export types
export type { 
  NotificationConfig, 
  NotificationEvent, 
  Subscription, 
  NotificationCallback 
};
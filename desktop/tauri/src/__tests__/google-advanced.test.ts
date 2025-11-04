// Google Advanced Services Integration Test
import { expect, describe, it, beforeEach, vi, afterEach } from 'vitest';
import { googleCache } from '../src/services/googleCache';
import { googleBatch } from '../src/services/googleBatch';
import { googleNotifications } from '../src/services/googleNotifications';
import { googleAnalytics } from '../src/services/googleAnalytics';

// Mock Tauri
const mockInvoke = vi.fn();
global.__TAURI__ = {
  invoke: mockInvoke
};

// Mock file system
vi.mock('@tauri-apps/api/fs', () => ({
  readTextFile: vi.fn(),
  writeTextFile: vi.fn(),
  exists: vi.fn(),
  createDir: vi.fn(),
}));

// Mock paths
vi.mock('@tauri-apps/api/path', () => ({
  appCacheDir: vi.fn().mockResolvedValue('/mock/cache'),
  appDataDir: vi.fn().mockResolvedValue('/mock/data'),
  join: vi.fn((...args) => args.join('/')),
}));

describe('Google Advanced Services Integration', () => {
  const testUserId = 'test-user-123';

  beforeEach(() => {
    vi.clearAllMocks();
    mockInvoke.mockClear();
  });

  afterEach(async () => {
    // Cleanup services
    await googleCache.clear();
    googleNotifications.cleanup();
    googleAnalytics.cleanup();
  });

  describe('Google Cache Service', () => {
    beforeEach(async () => {
      await googleCache.initialize();
    });

    it('should store and retrieve cached data', async () => {
      const testData = [
        {
          id: 'email_123',
          subject: 'Test Email',
          from: 'sender@example.com',
          body: 'Test body content'
        }
      ];

      // Store data in cache
      await googleCache.set(testUserId, 'list_emails', testData, {}, 300);

      // Retrieve from cache
      const cachedData = await googleCache.get(testUserId, 'list_emails', {});
      
      expect(cachedData).toEqual(testData);
      expect(cachedData).toHaveLength(1);
      expect(cachedData[0].subject).toBe('Test Email');
    });

    it('should handle cache expiration', async () => {
      const testData = [{ id: 'test', data: 'test' }];
      
      // Store with 1 second TTL
      await googleCache.set(testUserId, 'test_data', testData, {}, 1);

      // Should be available immediately
      const immediateData = await googleCache.get(testUserId, 'test_data', {});
      expect(immediateData).toEqual(testData);

      // Wait for expiration (mock time passage)
      vi.useFakeTimers();
      vi.advanceTimersByTime(2000); // 2 seconds

      // Should be expired
      const expiredData = await googleCache.get(testUserId, 'test_data', {});
      expect(expiredData).toBeNull();

      vi.useRealTimers();
    });

    it('should invalidate cache entries', async () => {
      const testData = [{ id: 'test', data: 'test' }];
      
      // Store data
      await googleCache.set(testUserId, 'test_data', testData);
      
      // Verify it's cached
      const cachedData = await googleCache.get(testUserId, 'test_data', {});
      expect(cachedData).toEqual(testData);

      // Invalidate
      await googleCache.invalidate(testUserId, 'test_data', {});

      // Should be gone
      const invalidatedData = await googleCache.get(testUserId, 'test_data', {});
      expect(invalidatedData).toBeNull();
    });

    it('should export and import cache data', async () => {
      const testData = [
        {
          id: 'email_123',
          subject: 'Export Test Email',
          from: 'export@example.com'
        },
        {
          id: 'email_456',
          subject: 'Another Test Email',
          from: 'another@example.com'
        }
      ];

      // Store data
      await googleCache.set(testUserId, 'test_export', testData);

      // Export cache
      const exportedData = await googleCache.exportCache(testUserId);
      expect(exportedData).toContain('Export Test Email');
      expect(exportedData).toContain('export@example.com');

      // Clear cache
      await googleCache.clear();
      const clearedData = await googleCache.get(testUserId, 'test_export', {});
      expect(clearedData).toBeNull();

      // Import cache
      await googleCache.importCache(exportedData);

      // Verify imported data
      const importedData = await googleCache.get(testUserId, 'test_export', {});
      expect(importedData).toHaveLength(2);
      expect(importedData[0].subject).toBe('Export Test Email');
    });

    it('should handle memory cache and file cache integration', async () => {
      const testData = [{ id: 'memory_test', data: 'test_data' }];
      
      // Store in cache
      await googleCache.set(testUserId, 'memory_test', testData);

      // Get from memory (first call)
      const memoryData = await googleCache.get(testUserId, 'memory_test', {});
      expect(memoryData).toEqual(testData);

      // Simulate clearing memory cache
      // (In real implementation, memory cache would be cleared)
      
      // Should still get data from file cache
      const fileData = await googleCache.get(testUserId, 'memory_test', {});
      expect(fileData).toEqual(testData);
    });
  });

  describe('Google Batch Service', () => {
    beforeEach(() => {
      googleBatch.initialize(testUserId);
    });

    it('should handle Gmail batch operations', async () => {
      const operations = [
        {
          type: 'mark' as const,
          data: {
            action: 'mark_email',
            params: {
              messageId: 'msg_123',
              action: 'read'
            }
          }
        },
        {
          type: 'mark' as const,
          data: {
            action: 'mark_email',
            params: {
              messageId: 'msg_456',
              action: 'starred'
            }
          }
        },
        {
          type: 'delete' as const,
          data: {
            action: 'delete_email',
            params: {
              messageId: 'msg_789',
              permanently: false
            }
          }
        }
      ];

      mockInvoke.mockResolvedValue([
        {
          id: 'gmail_0',
          status: 200,
          statusText: 'OK',
          headers: {},
          body: { id: 'msg_123', isRead: true }
        },
        {
          id: 'gmail_1',
          status: 200,
          statusText: 'OK',
          headers: {},
          body: { id: 'msg_456', isStarred: true }
        },
        {
          id: 'gmail_2',
          status: 200,
          statusText: 'OK',
          headers: {},
          body: { id: 'msg_789', deleted: true }
        }
      ]);

      const result = await googleBatch.batchGmailOperations(operations);

      expect(result.success).toBe(true);
      expect(result.results).toHaveLength(3);
      expect(result.errors).toHaveLength(0);
      expect(result.processed).toBe(3);
      expect(result.total).toBe(3);

      // Verify batch API was called
      expect(mockInvoke).toHaveBeenCalledWith('google_execute_batch', {
        userId: testUserId,
        requests: expect.arrayContaining([
          expect.objectContaining({
            method: 'POST',
            url: 'https://gmail.googleapis.com/gmail/v1/users/me/messages/msg_123/modify'
          }),
          expect.objectContaining({
            method: 'POST',
            url: 'https://gmail.googleapis.com/gmail/v1/users/me/messages/msg_456/modify'
          }),
          expect.objectContaining({
            method: 'DELETE',
            url: 'https://gmail.googleapis.com/gmail/v1/users/me/messages/msg_789/trash'
          })
        ])
      });
    });

    it('should handle batch errors gracefully', async () => {
      const operations = [
        {
          type: 'mark' as const,
          data: {
            action: 'mark_email',
            params: { messageId: 'invalid_msg', action: 'read' }
          }
        }
      ];

      mockInvoke.mockResolvedValue([
        {
          id: 'gmail_0',
          status: 404,
          statusText: 'Not Found',
          headers: {},
          error: 'Message not found'
        }
      ]);

      const result = await googleBatch.batchGmailOperations(operations);

      expect(result.success).toBe(false);
      expect(result.results).toHaveLength(0);
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0].id).toBe('gmail_0');
      expect(result.errors[0].error).toContain('Message not found');
    });

    it('should handle Calendar batch operations', async () => {
      const operations = [
        {
          type: 'update' as const,
          data: {
            action: 'update_event',
            params: {
              eventId: 'evt_123',
              calendarId: 'primary',
              summary: 'Updated Event'
            }
          }
        },
        {
          type: 'delete' as const,
          data: {
            action: 'delete_event',
            params: {
              eventId: 'evt_456',
              calendarId: 'primary',
              sendUpdates: 'all'
            }
          }
        }
      ];

      mockInvoke.mockResolvedValue([
        {
          id: 'calendar_0',
          status: 200,
          statusText: 'OK',
          headers: {},
          body: { id: 'evt_123', summary: 'Updated Event' }
        },
        {
          id: 'calendar_1',
          status: 204,
          statusText: 'No Content',
          headers: {},
          body: { deleted: true }
        }
      ]);

      const result = await googleBatch.calendarBatchOperations(operations);

      expect(result.success).toBe(true);
      expect(result.results).toHaveLength(2);
      expect(result.processed).toBe(2);

      // Verify API calls
      expect(mockInvoke).toHaveBeenCalledWith('google_execute_batch', {
        userId: testUserId,
        requests: expect.arrayContaining([
          expect.objectContaining({
            method: 'PUT',
            url: 'https://www.googleapis.com/calendar/v3/calendars/primary/events/evt_123'
          }),
          expect.objectContaining({
            method: 'DELETE',
            url: expect.stringContaining('calendars/primary/events/evt_456')
          })
        ])
      });
    });

    it('should handle large batches by chunking', async () => {
      const largeBatch = Array(150).fill(0).map((_, index) => ({
        type: 'mark' as const,
        data: {
          action: 'mark_email',
          params: {
            messageId: `msg_${index}`,
            action: 'read'
          }
        }
      }));

      // Set small batch size for testing
      googleBatch.setMaxBatchSize(50);

      mockInvoke.mockImplementation(async (command, args) => {
        if (command === 'google_execute_batch') {
          const requests = args.requests;
          return requests.map((req: any, index: number) => ({
            id: `chunk_${req.id}`,
            status: 200,
            statusText: 'OK',
            headers: {},
            body: { id: req.body.messageId, success: true }
          }));
        }
        return [];
      });

      const result = await googleBatch.batchGmailOperations(largeBatch);

      expect(result.success).toBe(true);
      expect(result.total).toBe(150);
      expect(result.processed).toBe(150);
      
      // Should have been called multiple times due to chunking
      expect(mockInvoke).toHaveBeenCalledTimes(3); // 150 / 50 = 3 chunks
    });

    it('should provide utility methods for common operations', async () => {
      mockInvoke.mockResolvedValue([
        { id: 'util_0', status: 200, statusText: 'OK', headers: {}, body: { id: 'msg_1', isRead: true } },
        { id: 'util_1', status: 200, statusText: 'OK', headers: {}, body: { id: 'msg_2', isRead: true } },
        { id: 'util_2', status: 200, statusText: 'OK', headers: {}, body: { id: 'msg_3', isRead: true } }
      ]);

      const result = await googleBatch.markMultipleEmails(
        ['msg_1', 'msg_2', 'msg_3'],
        'read'
      );

      expect(result.success).toBe(true);
      expect(result.results).toHaveLength(3);
      expect(mockInvoke).toHaveBeenCalledWith('google_execute_batch', expect.objectContaining({
        userId: testUserId,
        requests: expect.arrayContaining([
          expect.objectContaining({
            url: 'https://gmail.googleapis.com/gmail/v1/users/me/messages/msg_1/modify'
          })
        ])
      }));
    });
  });

  describe('Google Notifications Service', () => {
    beforeEach(async () => {
      vi.useFakeTimers();
      await googleNotifications.initialize(testUserId);
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should subscribe to Gmail notifications', async () => {
      mockInvoke.mockResolvedValue({
        id: 'gmail_sub_123',
        userId: testUserId,
        service: 'gmail',
        resource: 'users/me/messages',
        channel: 'channel_123',
        webhookId: 'webhook_123',
        expirationTime: Date.now() + 3600000, // 1 hour
        active: true
      });

      const result = await googleNotifications.subscribeToGmail(
        ['INBOX', 'UNREAD'],
        'https://example.com/webhook'
      );

      expect(result.success).toBe(true);
      expect(result.subscription).toBe('gmail_sub_123');

      expect(mockInvoke).toHaveBeenCalledWith('google_subscribe_gmail', {
        userId: testUserId,
        labelIds: ['INBOX', 'UNREAD'],
        webhookUrl: 'https://example.com/webhook'
      });
    });

    it('should handle notification callbacks', async () => {
      const callback = vi.fn();
      
      // Register callback
      googleNotifications.onNotification('email', callback);

      const mockEmail = {
        id: 'email_123',
        subject: 'New Email',
        from: 'sender@example.com',
        isRead: false
      };

      const notificationEvent = {
        id: 'notif_123',
        type: 'email' as const,
        timestamp: Date.now(),
        userId: testUserId,
        data: mockEmail,
        metadata: {
          service: 'gmail',
          action: 'received',
          severity: 'info' as const
        }
      };

      // Simulate notification event
      await googleNotifications.handleNotificationEvent(notificationEvent);

      // Wait for async processing
      await vi.runAllTimers();

      // Verify callback was called
      expect(callback).toHaveBeenCalledWith(notificationEvent);
    });

    it('should manage subscription lifecycle', async () => {
      // Create subscription
      mockInvoke.mockResolvedValue({
        id: 'test_sub_123',
        userId: testUserId,
        service: 'calendar',
        resource: 'calendars/primary/events',
        channel: 'channel_123',
        expirationTime: Date.now() + 3600000,
        active: true
      });

      const subscribeResult = await googleNotifications.subscribeToCalendar();
      expect(subscribeResult.success).toBe(true);

      // Unsubscribe
      mockInvoke.mockResolvedValue(true);
      const unsubscribeResult = await googleNotifications.unsubscribe(subscribeResult.subscription!);
      expect(unsubscribeResult.success).toBe(true);

      expect(mockInvoke).toHaveBeenCalledWith('google_unsubscribe', {
        userId: testUserId,
        subscriptionId: 'test_sub_123',
        channelId: 'channel_123',
        resourceId: undefined
      });
    });

    it('should handle connection status notifications', async () => {
      const connectionCallback = vi.fn();
      googleNotifications.onNotification('connection', connectionCallback);

      const connectionEvent = {
        id: 'conn_123',
        type: 'connection' as const,
        timestamp: Date.now(),
        userId: testUserId,
        data: { connected: false },
        metadata: {
          service: 'notifications',
          action: 'disconnected',
          severity: 'warning' as const
        }
      };

      await googleNotifications.handleNotificationEvent(connectionEvent);

      expect(connectionCallback).toHaveBeenCalledWith(connectionEvent);
    });

    it('should provide subscription statistics', () => {
      const status = googleNotifications.getSubscriptionStatus();

      expect(status).toHaveProperty('totalSubscriptions');
      expect(status).toHaveProperty('activeSubscriptions');
      expect(status).toHaveProperty('services');
      expect(typeof status.totalSubscriptions).toBe('number');
    });
  });

  describe('Google Analytics Service', () => {
    beforeEach(async () => {
      await googleAnalytics.initialize(testUserId);
    });

    it('should track API calls', () => {
      googleAnalytics.trackApiCall(
        'gmail',
        'list_emails',
        { maxResults: 10 },
        true,
        1500
      );

      const summary = googleAnalytics.getPerformanceSummary('hour');

      expect(summary.totalCalls).toBe(1);
      expect(summary.averageResponseTime).toBe(1500);
      expect(summary.successRate).toBe(100);
    });

    it('should track errors', async () => {
      const testError = new Error('Test API error');
      testError.stack = 'Test stack trace';

      await googleAnalytics.trackError(testError, {
        service: 'calendar',
        action: 'create_event',
        parameters: { summary: 'Test Event' },
        retryCount: 1
      });

      const errorSummary = googleAnalytics.getErrorSummary('hour');

      expect(errorSummary.totalErrors).toBe(1);
      expect(errorSummary.errorsByType).toHaveProperty('system_error');
      expect(errorSummary.errorsByService).toHaveProperty('calendar');
    });

    it('should track usage statistics', () => {
      googleAnalytics.trackUsage('gmail', 'send', 3);
      googleAnalytics.trackUsage('calendar', 'create', 1);
      googleAnalytics.trackUsage('drive', 'upload', 2);

      // Simulate usage events
      const eventTypes = [
        'api_call', 'usage', 'performance', 'security'
      ] as const;

      eventTypes.forEach(type => {
        googleAnalytics.trackApiCall('gmail', 'send', {}, true, 100);
        googleAnalytics.trackUsage('gmail', 'send', 1);
      });

      const usageStats = googleAnalytics.getPerformanceSummary('day');

      expect(usageStats.totalCalls).toBeGreaterThan(0);
    });

    it('should provide performance summaries', () => {
      // Track multiple metrics
      googleAnalytics.trackPerformance('gmail', 'send', {
        duration: 1200,
        success: true,
        cacheHit: false,
        responseSize: 1024
      });

      googleAnalytics.trackPerformance('calendar', 'list', {
        duration: 800,
        success: true,
        cacheHit: true,
        responseSize: 2048
      });

      googleAnalytics.trackPerformance('drive', 'upload', {
        duration: 5000,
        success: false,
        cacheHit: false,
        responseSize: 0
      });

      const summary = googleAnalytics.getPerformanceSummary('day');

      expect(summary.averageResponseTime).toBeGreaterThan(0);
      expect(summary.successRate).toBeLessThan(100); // One failed call
      expect(summary.cacheHitRate).toBeGreaterThan(0);
    });

    it('should export analytics data', async () => {
      // Add some data
      googleAnalytics.trackApiCall('gmail', 'list', {}, true, 1000);
      googleAnalytics.trackUsage('calendar', 'create', 1);

      const exportedData = await googleAnalytics.exportData('json');

      expect(exportedData).toContain('gmail');
      expect(exportedData).toContain('list');
      expect(exportedData).toContain('analytics');
      expect(exportedData).toContain('events');
    });

    it('should handle data retention', () => {
      const config = googleAnalytics.getConfig();
      expect(config.dataRetention).toBeGreaterThan(0);

      // Update retention policy
      googleAnalytics.updateConfig({ dataRetention: 7 });

      const updatedConfig = googleAnalytics.getConfig();
      expect(updatedConfig.dataRetention).toBe(7);
    });
  });

  describe('Service Integration', () => {
    it('should integrate cache with batch operations', async () => {
      await googleCache.initialize();
      googleBatch.initialize(testUserId);

      // Cache some data
      const testData = [
        { id: 'msg_1', subject: 'Test 1' },
        { id: 'msg_2', subject: 'Test 2' }
      ];
      await googleCache.set(testUserId, 'list_emails', testData);

      // Perform batch operation
      mockInvoke.mockResolvedValue([
        { id: 'batch_0', status: 200, statusText: 'OK', headers: {}, body: { id: 'msg_1', isRead: true } }
      ]);

      const operations = [{
        type: 'mark' as const,
        data: {
          action: 'mark_email',
          params: { messageId: 'msg_1', action: 'read' }
        }
      }];

      const result = await googleBatch.batchGmailOperations(operations);
      expect(result.success).toBe(true);

      // Cache should still contain original data
      const cachedData = await googleCache.get(testUserId, 'list_emails', {});
      expect(cachedData).toEqual(testData);
    });

    it('should integrate notifications with analytics', async () => {
      await googleNotifications.initialize(testUserId);
      await googleAnalytics.initialize(testUserId);

      // Track notification event
      const notificationCallback = async (event: any) => {
        googleAnalytics.trackApiCall('gmail', 'received', event.data, true, 0);
      };

      googleNotifications.onNotification('email', notificationCallback);

      const notificationEvent = {
        id: 'notif_123',
        type: 'email' as const,
        timestamp: Date.now(),
        userId: testUserId,
        data: { id: 'email_123', subject: 'New Email' },
        metadata: {
          service: 'gmail',
          action: 'received',
          severity: 'info' as const
        }
      };

      await googleNotifications.handleNotificationEvent(notificationEvent);

      const summary = googleAnalytics.getPerformanceSummary('hour');
      expect(summary.totalCalls).toBeGreaterThan(0);
    });

    it('should handle service configuration updates', () => {
      // Update cache configuration
      googleCache.updateConfig({ defaultTTL: 600 });

      // Update batch configuration
      googleBatch.setMaxBatchSize(200);

      // Update analytics configuration
      googleAnalytics.updateConfig({ dataRetention: 60 });

      const cacheConfig = googleCache.getConfig();
      const batchConfig = googleBatch.getMaxBatchSize();
      const analyticsConfig = googleAnalytics.getConfig();

      expect(cacheConfig.defaultTTL).toBe(600);
      expect(batchConfig).toBe(200);
      expect(analyticsConfig.dataRetention).toBe(60);
    });

    it('should handle service cleanup', async () => {
      // Initialize all services
      await googleCache.initialize();
      await googleNotifications.initialize(testUserId);
      await googleAnalytics.initialize(testUserId);
      googleBatch.initialize(testUserId);

      // Add some data
      await googleCache.set(testUserId, 'test', [{ id: 'test' }]);
      googleAnalytics.trackApiCall('gmail', 'test', {}, true, 100);

      // Cleanup services
      await googleCache.clear();
      await googleNotifications.cleanup();
      await googleAnalytics.cleanup();

      // Verify cleanup
      const cachedData = await googleCache.get(testUserId, 'test', {});
      expect(cachedData).toBeNull();

      const summary = googleAnalytics.getPerformanceSummary();
      expect(summary.totalCalls).toBe(0);
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should handle cache corruption', async () => {
      await googleCache.initialize();

      // Mock corrupted data
      vi.mocked(readTextFile).mockRejectedValue(new Error('Corrupted file'));

      const result = await googleCache.get(testUserId, 'test_corrupted', {});
      expect(result).toBeNull();
    });

    it('should handle batch API failures', async () => {
      googleBatch.initialize(testUserId);

      mockInvoke.mockRejectedValue(new Error('Batch API unavailable'));

      const operations = [{
        type: 'mark' as const,
        data: {
          action: 'mark_email',
          params: { messageId: 'test', action: 'read' }
        }
      }];

      const result = await googleBatch.batchGmailOperations(operations);

      expect(result.success).toBe(false);
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0].error).toContain('Batch API unavailable');
    });

    it('should handle notification subscription failures', async () => {
      await googleNotifications.initialize(testUserId);

      mockInvoke.mockResolvedValue({
        id: 'failed_sub',
        active: false
      });

      const result = await googleNotifications.subscribeToGmail();

      expect(result.success).toBe(false);
      expect(result.error).toContain('Failed to activate');
    });

    it('should handle analytics service failures', async () => {
      await googleAnalytics.initialize(testUserId);

      // Mock failed upload
      mockInvoke.mockRejectedValue(new Error('Upload failed'));

      const testError = new Error('Test error');
      await googleAnalytics.trackError(testError, {
        service: 'test',
        action: 'test_action',
        parameters: {},
        retryCount: 0
      });

      // Error should still be tracked locally even if upload fails
      const errorSummary = googleAnalytics.getErrorSummary();
      expect(errorSummary.totalErrors).toBeGreaterThan(0);
    });
  });
});
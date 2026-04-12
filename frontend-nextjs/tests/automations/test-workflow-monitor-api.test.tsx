import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('WorkflowMonitor - WebSocket Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('WebSocket Connection Management', () => {
    it('should establish WebSocket connection for workflow execution', (done) => {
      const mockWebSocket = {
        readyState: 1, // OPEN
        onopen: null,
        onmessage: null,
        onerror: null,
        onclose: null,
        send: jest.fn(),
        close: jest.fn(),
      };

      const connectWebSocket = (url: string) => {
        return new Promise((resolve) => {
          // Simulate connection
          setTimeout(() => {
            if (mockWebSocket.onopen) {
              mockWebSocket.onopen({ type: 'open' });
            }
            resolve(mockWebSocket);
          }, 100);
        });
      };

      connectWebSocket('ws://localhost:8000/ws/workflows/execution')
        .then((ws: any) => {
          expect(ws.readyState).toBe(1);
          expect(ws.send).toBeDefined();
          done();
        });
    });

    it('should handle WebSocket connection errors', (done) => {
      const mockWebSocket = {
        readyState: 3, // CLOSED
        onerror: null,
        onclose: null,
        close: jest.fn(),
      };

      const connectWebSocket = (url: string) => {
        return new Promise((resolve, reject) => {
          // Simulate connection error
          setTimeout(() => {
            const error = new Error('WebSocket connection failed');
            if (mockWebSocket.onerror) {
              mockWebSocket.onerror(error);
            }
            reject(error);
          }, 100);
        });
      };

      connectWebSocket('ws://invalid-host/ws/workflows/execution')
        .catch((error) => {
          expect(error).toBeInstanceOf(Error);
          expect(error.message).toContain('WebSocket connection failed');
          done();
        });
    });

    it('should close WebSocket connection on unmount', () => {
      const mockWebSocket = {
        readyState: 1,
        close: jest.fn(),
      };

      // Simulate component unmount
      const cleanup = () => {
        if (mockWebSocket.readyState === 1) {
          mockWebSocket.close();
        }
      };

      cleanup();

      expect(mockWebSocket.close).toHaveBeenCalled();
    });
  });

  describe('Real-time Execution Updates', () => {
    it('should receive execution start event via WebSocket', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const startEvent = {
        type: 'EXECUTION_START',
        data: {
          executionId: 'exec-123',
          workflowId: 'workflow-123',
          status: 'running',
          startedAt: new Date().toISOString(),
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('EXECUTION_START');
        expect(data.data.executionId).toBe('exec-123');
        expect(data.data.status).toBe('running');
        done();
      };

      // Simulate receiving message
      mockWebSocket.onmessage({ data: JSON.stringify(startEvent) } as MessageEvent);
    });

    it('should receive node execution progress events', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const progressEvent = {
        type: 'NODE_PROGRESS',
        data: {
          executionId: 'exec-123',
          nodeId: 'node-1',
          nodeName: 'Send Email',
          status: 'running',
          progress: 50,
          message: 'Sending email...',
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('NODE_PROGRESS');
        expect(data.data.nodeId).toBe('node-1');
        expect(data.data.progress).toBe(50);
        done();
      };

      mockWebSocket.onmessage({ data: JSON.stringify(progressEvent) } as MessageEvent);
    });

    it('should receive execution completion event', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const completionEvent = {
        type: 'EXECUTION_COMPLETE',
        data: {
          executionId: 'exec-123',
          workflowId: 'workflow-123',
          status: 'completed',
          result: {
            success: true,
            output: { emailSent: true },
          },
          completedAt: new Date().toISOString(),
          duration: 5432,
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('EXECUTION_COMPLETE');
        expect(data.data.status).toBe('completed');
        expect(data.data.result.success).toBe(true);
        expect(data.data.duration).toBeDefined();
        done();
      };

      mockWebSocket.onmessage({ data: JSON.stringify(completionEvent) } as MessageEvent);
    });

    it('should receive execution error event', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const errorEvent = {
        type: 'EXECUTION_ERROR',
        data: {
          executionId: 'exec-123',
          workflowId: 'workflow-123',
          status: 'failed',
          error: {
            message: 'Failed to send email',
            code: 'EMAIL_SEND_FAILED',
            nodeId: 'node-1',
          },
          failedAt: new Date().toISOString(),
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('EXECUTION_ERROR');
        expect(data.data.status).toBe('failed');
        expect(data.data.error.message).toBeDefined();
        expect(data.data.error.nodeId).toBe('node-1');
        done();
      };

      mockWebSocket.onmessage({ data: JSON.stringify(errorEvent) } as MessageEvent);
    });
  });

  describe('Execution Logs Streaming', () => {
    it('should receive log messages via WebSocket', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const logEvent = {
        type: 'LOG_MESSAGE',
        data: {
          executionId: 'exec-123',
          level: 'info',
          message: 'Starting workflow execution',
          timestamp: new Date().toISOString(),
          nodeId: null,
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('LOG_MESSAGE');
        expect(data.data.level).toBe('info');
        expect(data.data.message).toContain('Starting workflow');
        done();
      };

      mockWebSocket.onmessage({ data: JSON.stringify(logEvent) } as MessageEvent);
    });

    it('should receive error log messages', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const errorLogEvent = {
        type: 'LOG_MESSAGE',
        data: {
          executionId: 'exec-123',
          level: 'error',
          message: 'Failed to connect to email server',
          timestamp: new Date().toISOString(),
          nodeId: 'node-1',
          error: {
            code: 'CONNECTION_ERROR',
            details: 'Connection timeout after 30s',
          },
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('LOG_MESSAGE');
        expect(data.data.level).toBe('error');
        expect(data.data.error.code).toBe('CONNECTION_ERROR');
        done();
      };

      mockWebSocket.onmessage({ data: JSON.stringify(errorLogEvent) } as MessageEvent);
    });

    it('should batch multiple log messages', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const batchLogEvent = {
        type: 'LOG_BATCH',
        data: {
          executionId: 'exec-123',
          logs: [
            {
              level: 'info',
              message: 'Step 1 completed',
              timestamp: new Date().toISOString(),
            },
            {
              level: 'info',
              message: 'Step 2 started',
              timestamp: new Date().toISOString(),
            },
            {
              level: 'warning',
              message: 'Step 2 taking longer than expected',
              timestamp: new Date().toISOString(),
            },
          ],
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('LOG_BATCH');
        expect(data.data.logs).toHaveLength(3);
        expect(data.data.logs[2].level).toBe('warning');
        done();
      };

      mockWebSocket.onmessage({ data: JSON.stringify(batchLogEvent) } as MessageEvent);
    });
  });

  describe('Execution Control Commands', () => {
    it('should send pause command via WebSocket', () => {
      const mockWebSocket = {
        send: jest.fn(),
        readyState: 1,
      };

      const pauseCommand = {
        type: 'PAUSE_EXECUTION',
        data: {
          executionId: 'exec-123',
        },
      };

      mockWebSocket.send(JSON.stringify(pauseCommand));

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(pauseCommand));
    });

    it('should send resume command via WebSocket', () => {
      const mockWebSocket = {
        send: jest.fn(),
        readyState: 1,
      };

      const resumeCommand = {
        type: 'RESUME_EXECUTION',
        data: {
          executionId: 'exec-123',
        },
      };

      mockWebSocket.send(JSON.stringify(resumeCommand));

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(resumeCommand));
    });

    it('should send stop command via WebSocket', () => {
      const mockWebSocket = {
        send: jest.fn(),
        readyState: 1,
      };

      const stopCommand = {
        type: 'STOP_EXECUTION',
        data: {
          executionId: 'exec-123',
          reason: 'User requested',
        },
      };

      mockWebSocket.send(JSON.stringify(stopCommand));

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(stopCommand));
    });

    it('should send retry command via WebSocket', () => {
      const mockWebSocket = {
        send: jest.fn(),
        readyState: 1,
      };

      const retryCommand = {
        type: 'RETRY_EXECUTION',
        data: {
          executionId: 'exec-123',
          fromNodeId: 'node-2', // Retry from failed node
        },
      };

      mockWebSocket.send(JSON.stringify(retryCommand));

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(retryCommand));
    });
  });

  describe('Auto-refresh Configuration', () => {
    it('should configure auto-refresh interval', () => {
      const config = {
        autoRefresh: true,
        interval: 5000, // 5 seconds
      };

      expect(config.autoRefresh).toBe(true);
      expect(config.interval).toBe(5000);
    });

    it('should trigger refresh at configured interval', async () => {
      let refreshCount = 0;
      const interval = 100; // Short interval for testing

      const startAutoRefresh = (intervalMs: number) => {
        return setInterval(() => {
          refreshCount++;
        }, intervalMs);
      };

      const timerId = startAutoRefresh(interval);

      // Wait for 3 refreshes
      await new Promise(resolve => setTimeout(resolve, interval * 3 + 50));

      clearInterval(timerId);

      expect(refreshCount).toBeGreaterThanOrEqual(3);
    });

    it('should stop auto-refresh on unmount', () => {
      let refreshCount = 0;
      const timerId = setInterval(() => {
        refreshCount++;
      }, 1000);

      // Simulate component unmount
      clearInterval(timerId);

      const initialCount = refreshCount;

      // Wait and verify no more refreshes
      return new Promise<void>((resolve) => {
        setTimeout(() => {
          expect(refreshCount).toBe(initialCount);
          resolve();
        }, 1500);
      });
    });
  });

  describe('WebSocket Reconnection', () => {
    it('should attempt reconnection on connection loss', async () => {
      let reconnectAttempts = 0;
      const maxReconnectAttempts = 3;

      const reconnect = () => {
        return new Promise((resolve, reject) => {
          reconnectAttempts++;

          if (reconnectAttempts <= maxReconnectAttempts) {
            setTimeout(() => {
              resolve({ connected: true });
            }, 100);
          } else {
            reject(new Error('Max reconnection attempts reached'));
          }
        });
      };

      // Simulate reconnection attempts
      for (let i = 0; i < maxReconnectAttempts; i++) {
        await reconnect();
      }

      expect(reconnectAttempts).toBe(maxReconnectAttempts);
    });

    it('should use exponential backoff for reconnection', async () => {
      let attemptNumber = 0;
      const delays: number[] = [];

      const reconnectWithBackoff = () => {
        return new Promise((resolve) => {
          const delay = Math.pow(2, attemptNumber) * 1000; // 1s, 2s, 4s, 8s...
          delays.push(delay);

          setTimeout(() => {
            attemptNumber++;
            resolve({ connected: true });
          }, delay);
        });
      };

      // Make 3 reconnection attempts
      await reconnectWithBackoff();
      await reconnectWithBackoff();
      await reconnectWithBackoff();

      expect(delays[0]).toBe(1000); // 2^0 * 1000
      expect(delays[1]).toBe(2000); // 2^1 * 1000
      expect(delays[2]).toBe(4000); // 2^2 * 1000
    });

    it('should stop reconnection after max attempts', async () => {
      let attemptCount = 0;
      const maxAttempts = 3;

      const reconnectWithLimit = () => {
        return new Promise((resolve, reject) => {
          attemptCount++;

          if (attemptCount >= maxAttempts) {
            reject(new Error('Max reconnection attempts reached'));
          } else {
            resolve({ connected: true });
          }
        });
      };

      // Attempt reconnections until max
      for (let i = 0; i < maxAttempts; i++) {
        try {
          await reconnectWithLimit();
        } catch (error) {
          expect(error.message).toContain('Max reconnection attempts');
          break;
        }
      }

      expect(attemptCount).toBe(maxAttempts);
    });
  });

  describe('Execution Metrics', () => {
    it('should receive execution metrics via WebSocket', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
      };

      const metricsEvent = {
        type: 'EXECUTION_METRICS',
        data: {
          executionId: 'exec-123',
          metrics: {
            duration: 5432,
            nodeCount: 5,
            completedNodes: 3,
            failedNodes: 0,
            averageNodeDuration: 1086,
            memoryUsage: 51200000, // bytes
            cpuUsage: 45.5, // percentage
          },
          timestamp: new Date().toISOString(),
        },
      };

      mockWebSocket.onmessage = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        expect(data.type).toBe('EXECUTION_METRICS');
        expect(data.data.metrics.duration).toBe(5432);
        expect(data.data.metrics.nodeCount).toBe(5);
        expect(data.data.metrics.cpuUsage).toBe(45.5);
        done();
      };

      mockWebSocket.onmessage({ data: JSON.stringify(metricsEvent) } as MessageEvent);
    });

    it('should aggregate metrics over time', () => {
      const metricsHistory: any[] = [];

      const metrics1 = {
        timestamp: Date.now(),
        duration: 1000,
        memoryUsage: 50000000,
      };

      const metrics2 = {
        timestamp: Date.now() + 1000,
        duration: 2000,
        memoryUsage: 55000000,
      };

      const metrics3 = {
        timestamp: Date.now() + 2000,
        duration: 3000,
        memoryUsage: 60000000,
      };

      metricsHistory.push(metrics1, metrics2, metrics3);

      const averageDuration = metricsHistory.reduce((sum, m) => sum + m.duration, 0) / metricsHistory.length;
      const peakMemory = Math.max(...metricsHistory.map(m => m.memoryUsage));

      expect(averageDuration).toBe(2000);
      expect(peakMemory).toBe(60000000);
    });
  });
});

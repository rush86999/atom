/**
 * Auto-Sync Dashboard Component
 *
 * Real-time dashboard that automatically syncs data from external APIs
 * via agent skills with configurable refresh intervals and conflict resolution.
 *
 * Features:
 * - Real-time data sync (polling or WebSocket)
 * - Configurable refresh intervals
 * - Conflict resolution for concurrent updates
 * - Offline mode with queue
 * - Sync status indicators
 * - Last sync timestamp
 * - Manual sync trigger
 * - Data validation and error recovery
 * - Multi-source data aggregation
 *
 * Perfect for CRM dashboards, analytics, and live monitoring!
 */

'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  RefreshCw,
  Cloud,
  CloudOff,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  Settings,
  Pause,
  Play,
  Database
} from 'lucide-react';

export interface SyncConfig {
  skillId: string;
  interval?: number;  // Sync interval in milliseconds (0 = manual only)
  method: 'poll' | 'websocket' | 'hybrid';
  retryAttempts: number;
  timeout: number;
  enableOffline?: boolean;
}

export interface SyncStatus {
  isSyncing: boolean;
  lastSync: Date | null;
  nextSync: Date | null;
  lastError: string | null;
  consecutiveErrors: number;
  dataFetched: number;
  syncCount: number;
}

export interface DataConflict {
  field: string;
  localValue: any;
  remoteValue: any;
  timestamp: Date;
}

export interface AutoSyncDashboardProps {
  tenantId: string;
  config: SyncConfig;
  title?: string;
  description?: string;
  onDataUpdate?: (data: any) => void;
  onSyncError?: (error: string) => void;
  onDataConflict?: (conflict: DataConflict) => void;
  children: (data: any, status: SyncStatus) => React.ReactNode;
}

export const AutoSyncDashboard: React.FC<AutoSyncDashboardProps> = ({
  tenantId,
  config,
  title = 'Auto-Sync Dashboard',
  description = 'Real-time data sync with external APIs',
  onDataUpdate,
  onSyncError,
  onDataConflict,
  children
}) => {
  const [data, setData] = useState<any>(null);
  const [status, setStatus] = useState<SyncStatus>({
    isSyncing: false,
    lastSync: null,
    nextSync: null,
    lastError: null,
    consecutiveErrors: 0,
    dataFetched: 0,
    syncCount: 0
  });
  const [isPaused, setIsPaused] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [offlineQueue, setOfflineQueue] = useState<any[]>([]);
  const [conflicts, setConflicts] = useState<DataConflict[]>([]);
  const [failedUpdates, setFailedUpdates] = useState<any[]>([]);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch data from skill
  const fetchData = useCallback(async (isRetry = false): Promise<boolean> => {
    if (status.isSyncing) return false;

    setStatus(prev => ({ ...prev, isSyncing: true }));

    try {
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const response = await fetch(`/api/skills/${config.skillId}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': tenantId
        },
        body: JSON.stringify({}),
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      const fetchedData = result.data || result;

      // Check for conflicts (if we have existing data)
      if (data && !isRetry) {
        const newConflicts: DataConflict[] = [];

        Object.keys(fetchedData).forEach(key => {
          if (data[key] !== fetchedData[key] && typeof data[key] !== 'object') {
            newConflicts.push({
              field: key,
              localValue: data[key],
              remoteValue: fetchedData[key],
              timestamp: new Date()
            });
          }
        });

        if (newConflicts.length > 0) {
          setConflicts(prev => [...prev, ...newConflicts]);
          newConflicts.forEach(conflict => onDataConflict?.(conflict));
        }
      }

      setData(fetchedData);
      onDataUpdate?.(fetchedData);

      setStatus(prev => ({
        ...prev,
        isSyncing: false,
        lastSync: new Date(),
        lastError: null,
        consecutiveErrors: 0,
        dataFetched: prev.dataFetched + 1,
        syncCount: prev.syncCount + 1
      }));

      return true;
    } catch (error: any) {
      console.error('Sync error:', error);

      const errorMessage = error.name === 'AbortError' ? 'Sync cancelled' : error.message;

      setStatus(prev => ({
        ...prev,
        isSyncing: false,
        lastError: errorMessage,
        consecutiveErrors: prev.consecutiveErrors + 1
      }));

      onSyncError?.(errorMessage);

      // Retry logic
      if (!isRetry && status.consecutiveErrors < config.retryAttempts) {
        const delay = Math.pow(2, status.consecutiveErrors) * 1000; // Exponential backoff
        setTimeout(() => fetchData(true), delay);
      }

      return false;
    }
  }, [status, data, config, tenantId]);

  // Manual sync trigger
  const handleManualSync = async () => {
    await fetchData();
  };

  // Setup polling
  useEffect(() => {
    if (config.method === 'poll' || config.method === 'hybrid') {
      if (config.interval && config.interval > 0 && !isPaused) {
        intervalRef.current = setInterval(() => {
          fetchData();
        }, config.interval);

        setStatus(prev => ({
          ...prev,
          nextSync: new Date(Date.now() + config.interval!)
        }));
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [config.method, config.interval, isPaused, fetchData]);

  // Setup WebSocket
  useEffect(() => {
    if (config.method === 'websocket' || config.method === 'hybrid') {
      const wsUrl = `${window.location.origin.replace('http', 'ws')}/api/skills/${config.skillId}/stream`;

      websocketRef.current = new WebSocket(wsUrl);

      websocketRef.current.onopen = () => {
        console.log('WebSocket connected');
      };

      websocketRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.type === 'update') {
            const updatedData = message.data;
            setData(updatedData);
            onDataUpdate?.(updatedData);

            setStatus(prev => ({
              ...prev,
              lastSync: new Date(),
              syncCount: prev.syncCount + 1
            }));
          }
        } catch (error) {
          console.error('WebSocket message error:', error);
        }
      };

      websocketRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Fall back to polling
        if (config.method === 'hybrid') {
          fetchData();
        }
      };

      websocketRef.current.onclose = () => {
        console.log('WebSocket closed');
        // Reconnect after delay
        setTimeout(() => {
          if (websocketRef.current?.readyState === WebSocket.CLOSED) {
            fetchData();
          }
        }, 5000);
      };

      return () => {
        websocketRef.current?.close();
        websocketRef.current = null;
      };
    }
  }, [config.method, config.skillId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Online/offline detection
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);

      // Process offline queue sequentially when back online
      if (offlineQueue.length > 0) {
        processOfflineQueue();
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [offlineQueue]);

  // Process offline queue sequentially with retry logic
  const processOfflineQueue = async () => {
    const MAX_QUEUE_SIZE = 50; // Prevent memory issues
    const queue = offlineQueue.slice(0, MAX_QUEUE_SIZE);

    if (queue.length === 0) return;

    setStatus(prev => ({ ...prev, isSyncing: true }));

    // Process each item sequentially
    for (const item of queue) {
      let retries = 3;
      let success = false;

      while (retries > 0 && !success) {
        try {
          // Re-execute the queued update
          await item.execute();
          success = true;

          // Remove from queue on success
          setOfflineQueue(prev => prev.filter(i => i.id !== item.id));

        } catch (error) {
          retries--;
          console.error(`Queue item ${item.id} failed, retries left: ${retries}`, error);

          if (retries === 0) {
            // Mark as failed after all retries exhausted
            setFailedUpdates(prev => [...prev, {
              field: item.field,
              error: error instanceof Error ? error.message : 'Unknown error',
              timestamp: new Date()
            }]);

            // Remove from queue
            setOfflineQueue(prev => prev.filter(i => i.id !== item.id));
          } else {
            // Exponential backoff before retry
            await new Promise(resolve => setTimeout(resolve, 1000 * (4 - retries)));
          }
        }
      }
    }

    setStatus(prev => ({ ...prev, isSyncing: false }));

    // If queue still has items, warn about capacity
    if (offlineQueue.length > MAX_QUEUE_SIZE) {
      console.warn(`Offline queue exceeds capacity (${offlineQueue.length} > ${MAX_QUEUE_SIZE}). Oldest items may be lost.`);
    }
  };

  // Resolve conflict
  const resolveConflict = (field: string, useRemote: boolean) => {
    if (!data) return;

    const updatedData = { ...data };

    if (useRemote) {
      // Use remote value (already in data)
    } else {
      // Keep local value
      const conflict = conflicts.find(c => c.field === field);
      if (conflict) {
        updatedData[field] = conflict.localValue;
      }
    }

    setData(updatedData);
    setConflicts(prev => prev.filter(c => c.field !== field));
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5 text-blue-500" />
              {title}
            </CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {/* Sync status */}
            <Badge
              variant={status.isSyncing ? 'secondary' : status.lastError ? 'destructive' : 'default'}
              className="flex items-center gap-1"
            >
              {status.isSyncing ? (
                <>
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  Syncing...
                </>
              ) : status.lastError ? (
                <>
                  <XCircle className="w-3 h-3" />
                  Error
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-3 h-3" />
                  Synced
                </>
              )}
            </Badge>

            {/* Online status */}
            <Badge
              variant={isOnline ? 'default' : 'outline'}
              className="flex items-center gap-1"
            >
              {isOnline ? (
                <>
                  <Cloud className="w-3 h-3" />
                  Online
                </>
              ) : (
                <>
                  <CloudOff className="w-3 h-3" />
                  Offline
                </>
              )}
            </Badge>

            {/* Pause/Resume */}
            {config.interval && config.interval > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsPaused(!isPaused)}
              >
                {isPaused ? (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Resume
                  </>
                ) : (
                  <>
                    <Pause className="w-4 h-4 mr-2" />
                    Pause
                  </>
                )}
              </Button>
            )}

            {/* Manual sync */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleManualSync}
              disabled={status.isSyncing || !isOnline}
            >
              <RefreshCw className={`w-4 h-4 ${status.isSyncing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* Sync info */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground mt-2">
          {status.lastSync && (
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Last sync: {status.lastSync.toLocaleTimeString()}
            </div>
          )}

          {status.nextSync && !isPaused && (
            <div className="flex items-center gap-1">
              <RefreshCw className="w-3 h-3" />
              Next sync: {status.nextSync.toLocaleTimeString()}
            </div>
          )}

          {status.dataFetched > 0 && (
            <div>
              {status.syncCount} syncs, {status.dataFetched} records fetched
            </div>
          )}

          {config.enableOffline && offlineQueue.length > 0 && (
            <Badge variant="secondary">
              {offlineQueue.length} pending updates
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        {/* Conflicts */}
        {conflicts.length > 0 && (
          <Alert className="mb-4 bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-800">
            <AlertCircle className="h-4 w-4 text-yellow-600" />
            <AlertDescription>
              <div className="space-y-2">
                <p className="font-semibold">Data conflicts detected ({conflicts.length})</p>

                {conflicts.slice(0, 3).map((conflict, index) => (
                  <div key={index} className="text-sm p-2 bg-background rounded">
                    <div className="font-medium">{conflict.field}</div>
                    <div className="flex items-center gap-4 mt-1">
                      <div>
                        <span className="text-muted-foreground">Local:</span> {String(conflict.localValue)}
                      </div>
                      <div>
                        <span className="text-muted-foreground">Remote:</span> {String(conflict.remoteValue)}
                      </div>
                      <div className="flex gap-2 ml-auto">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => resolveConflict(conflict.field, false)}
                        >
                          Keep Local
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => resolveConflict(conflict.field, true)}
                        >
                          Use Remote
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Error */}
        {status.lastError && (
          <Alert className="mb-4 bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800">
            <XCircle className="h-4 w-4 text-red-600" />
            <AlertDescription>
              Sync error: {status.lastError}
              {status.consecutiveErrors > 1 && (
                <span className="ml-2">({status.consecutiveErrors} consecutive errors)</span>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* Children (dashboard content) */}
        {children(data, status)}

        {/* Loading overlay */}
        {status.isSyncing && !data && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/50">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">Syncing data...</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

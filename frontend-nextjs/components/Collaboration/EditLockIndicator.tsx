/**
 * Edit Lock Indicator Component
 * Shows which users have locks on which resources
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Lock, Unlock, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/components/ui/use-toast';

interface EditLockInfo {
  lock_id: string;
  resource_type: string;
  resource_id: string;
  locked_by: string;
  locked_by_name?: string;
  locked_at: string;
  expires_at?: string;
  lock_reason?: string;
}

interface EditLockIndicatorProps {
  workflowId: string;
  currentUserId?: string;
  onLockAcquired?: () => void;
  onLockReleased?: () => void;
}

export const EditLockIndicator: React.FC<EditLockIndicatorProps> = ({
  workflowId,
  currentUserId,
  onLockAcquired,
  onLockReleased,
}) => {
  const { toast } = useToast();
  const [locks, setLocks] = useState<EditLockInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch active locks
  const fetchLocks = useCallback(async () => {
    try {
      const response = await fetch(`/api/collaboration/locks/${workflowId}`);
      if (!response.ok) throw new Error('Failed to fetch locks');

      const data = await response.json();
      setLocks(data.locks || []);
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching locks:', error);
      setIsLoading(false);
    }
  }, [workflowId]);

  // Initial load
  useEffect(() => {
    fetchLocks();
  }, [fetchLocks]);

  // Poll for updates
  useEffect(() => {
    const interval = setInterval(fetchLocks, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, [fetchLocks]);

  // Get lock icon
  const getLockIcon = (resourceType: string) => {
    switch (resourceType) {
      case 'workflow':
        return '📄';
      case 'node':
        return '🔷';
      case 'edge':
        return '🔗';
      default:
        return '🔒';
    }
  };

  // Check if current user has lock
  const hasMyLocks = locks.some(lock => lock.locked_by === currentUserId);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active Locks</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-2">
            <div className="h-2 w-2 bg-gray-200 rounded-full animate-pulse mr-2" />
            <div className="h-2 w-16 bg-gray-200 rounded-full animate-pulse" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Lock className="h-4 w-4" />
          Active Locks ({locks.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        {locks.length === 0 ? (
          <div className="flex items-center justify-center py-4 text-muted-foreground">
            <Unlock className="h-8 w-8 mr-2 opacity-50" />
            <p className="text-sm">No active locks</p>
          </div>
        ) : (
          <div className="space-y-2">
            {locks.map((lock) => (
              <div
                key={lock.lock_id}
                className="flex items-center justify-between p-3 bg-muted rounded-lg"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {/* Lock Icon */}
                  <span className="text-xl">{getLockIcon(lock.resource_type)}</span>

                  {/* Lock Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium">
                        {lock.resource_type === 'workflow'
                          ? 'Entire workflow'
                          : `${lock.resource_type}: ${lock.resource_id}`}
                      </p>
                      {lock.locked_by === currentUserId ? (
                        <Badge variant="default" className="text-xs">
                          You
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs">
                          <User className="h-3 w-3 inline mr-1" />
                          {lock.locked_by_name || lock.locked_by}
                        </Badge>
                      )}
                    </div>

                    {lock.lock_reason && (
                      <p className="text-xs text-muted-foreground truncate">
                        {lock.lock_reason}
                      </p>
                    )}

                    <p className="text-xs text-muted-foreground">
                      {lock.expires_at
                        ? `Expires ${new Date(lock.expires_at).toLocaleTimeString()}`
                        : 'No expiry'}
                    </p>
                  </div>
                </div>

                {/* Lock Status */}
                <div className="flex items-center gap-1 text-green-600">
                  <Lock className="h-3 w-3" fill="currentColor" />
                  <span className="text-xs">Locked</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info Text */}
        <div className="mt-4 pt-4 border-t">
          <p className="text-xs text-muted-foreground">
            💡 Locks prevent conflicting edits when multiple users are editing.
            {hasMyLocks
              ? ' You have active locks.'
              : ' Other users have locked resources.'}
          </p>
        </div>
      </CardContent>
    </Card>
  );
};

export default EditLockIndicator;

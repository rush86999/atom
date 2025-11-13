import { useState, useCallback, useRef } from 'react';
import { useAppStore } from '../store';

interface OptimisticUpdateOptions<T> {
  onRevert?: (error: Error, originalData: T) => void;
  onSuccess?: (data: T) => void;
  rollbackOnError?: boolean;
}

export const useOptimisticUpdate = <T>(
  key: string,
  updateFn: (data: T) => Promise<T>,
  options: OptimisticUpdateOptions<T> = {}
) => {
  const { rollbackOnError = true, onRevert, onSuccess } = options;

  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const originalDataRef = useRef<T | null>(null);

  const { setTasks, setMessages, setCalendarEvents, setIntegrations } = useAppStore();

  const optimisticUpdate = useCallback(async (newData: T, optimisticData?: T) => {
    setIsUpdating(true);
    setError(null);

    // Store original data for potential rollback
    originalDataRef.current = newData;

    // Apply optimistic update
    const optimisticUpdateData = optimisticData || newData;

    // Update the store optimistically based on key
    switch (key) {
      case 'tasks':
        setTasks(optimisticUpdateData as any);
        break;
      case 'messages':
        setMessages(optimisticUpdateData as any);
        break;
      case 'calendarEvents':
        setCalendarEvents(optimisticUpdateData as any);
        break;
      case 'integrations':
        setIntegrations(optimisticUpdateData as any);
        break;
      default:
        console.warn(`Optimistic update not implemented for key: ${key}`);
    }

    try {
      // Perform the actual update
      const result = await updateFn(newData);

      // Update with server response
      switch (key) {
        case 'tasks':
          setTasks(result as any);
          break;
        case 'messages':
          setMessages(result as any);
          break;
        case 'calendarEvents':
          setCalendarEvents(result as any);
          break;
        case 'integrations':
          setIntegrations(result as any);
          break;
      }

      onSuccess?.(result);
      setIsUpdating(false);
      return result;
    } catch (err) {
      const error = err as Error;
      setError(error);

      // Rollback on error if enabled
      if (rollbackOnError && originalDataRef.current) {
        switch (key) {
          case 'tasks':
            setTasks(originalDataRef.current as any);
            break;
          case 'messages':
            setMessages(originalDataRef.current as any);
            break;
          case 'calendarEvents':
            setCalendarEvents(originalDataRef.current as any);
            break;
          case 'integrations':
            setIntegrations(originalDataRef.current as any);
            break;
        }

        onRevert?.(error, originalDataRef.current);
      }

      setIsUpdating(false);
      throw error;
    }
  }, [key, updateFn, rollbackOnError, onRevert, onSuccess, setTasks, setMessages, setCalendarEvents, setIntegrations]);

  const rollback = useCallback(() => {
    if (originalDataRef.current) {
      switch (key) {
        case 'tasks':
          setTasks(originalDataRef.current as any);
          break;
        case 'messages':
          setMessages(originalDataRef.current as any);
          break;
        case 'calendarEvents':
          setCalendarEvents(originalDataRef.current as any);
          break;
        case 'integrations':
          setIntegrations(originalDataRef.current as any);
          break;
      }
    }
  }, [key, setTasks, setMessages, setCalendarEvents, setIntegrations]);

  return {
    optimisticUpdate,
    rollback,
    isUpdating,
    error,
  };
};

// Higher-order component for optimistic updates
export const withOptimisticUpdate = <P extends object>(
  Component: React.ComponentType<P>,
  updateKey: string,
  updateFn: (data: any) => Promise<any>,
  options?: OptimisticUpdateOptions<any>
) => {
  return React.forwardRef<any, P>((props, ref) => {
    const { optimisticUpdate, rollback, isUpdating, error } = useOptimisticUpdate(
      updateKey,
      updateFn,
      options
    );

    return (
      <Component
        {...props}
        ref={ref}
        optimisticUpdate={optimisticUpdate}
        rollback={rollback}
        isUpdating={isUpdating}
        updateError={error}
      />
    );
  });
};

// Optimistic update queue for batch operations
export class OptimisticUpdateQueue {
  private queue: Array<{
    id: string;
    update: () => Promise<void>;
    rollback: () => void;
  }> = [];

  private isProcessing = false;

  enqueue(id: string, update: () => Promise<void>, rollback: () => void) {
    this.queue.push({ id, update, rollback });
    this.processQueue();
  }

  private async processQueue() {
    if (this.isProcessing || this.queue.length === 0) return;

    this.isProcessing = true;

    while (this.queue.length > 0) {
      const { id, update, rollback } = this.queue.shift()!;

      try {
        await update();
      } catch (error) {
        console.error(`Optimistic update failed for ${id}:`, error);
        rollback();
      }
    }

    this.isProcessing = false;
  }

  clear() {
    this.queue.forEach(({ rollback }) => rollback());
    this.queue = [];
  }
}

// Global optimistic update queue
export const optimisticUpdateQueue = new OptimisticUpdateQueue();

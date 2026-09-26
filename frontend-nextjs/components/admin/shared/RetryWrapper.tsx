import React, { useCallback } from "react";

interface RetryOptions {
  maxRetries?: number;
  delayMs?: number;
  backoffMultiplier?: number;
}

/**
 * Retry Hook
 *
 * Provides retry logic with exponential backoff for failed operations.
 */
export const useRetry = () => {
  const retry = useCallback(
    async <T,>(
      fn: () => Promise<T>,
      options: RetryOptions = {}
    ): Promise<T> => {
      const {
        maxRetries = 3,
        delayMs = 1000,
        backoffMultiplier = 2,
      } = options;

      let lastError: Error | null = null;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          return await fn();
        } catch (error) {
          lastError = error as Error;

          if (attempt < maxRetries) {
            const delay = delayMs * Math.pow(backoffMultiplier, attempt);
            console.log(`[Retry] Attempt ${attempt + 1}/${maxRetries + 1} failed, retrying in ${delay}ms...`);
            await new Promise((resolve) => setTimeout(resolve, delay));
          }
        }
      }

      throw lastError;
    },
    []
  );

  return { retry };
};

/**
 * Retry Wrapper Component
 *
 * Wraps async operations with automatic retry logic.
 */
export const RetryWrapper: React.FC<{
  children: (
    retry: <T>(fn: () => Promise<T>, options?: RetryOptions) => Promise<T>
  ) => React.ReactNode;
}> = ({ children }) => {
  const { retry } = useRetry();
  return <>{children(retry)}</>;
};

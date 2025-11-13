import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import axios, { AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { useAppStore } from '../store';

interface ApiState {
  isOnline: boolean;
  pendingRequests: number;
  lastRequestTime: Date | null;
  error: string | null;
}

interface ApiContextType extends ApiState {
  get: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  patch: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<AxiosResponse<T>>;
  setBaseURL: (url: string) => void;
  setAuthToken: (token: string | null) => void;
  clearError: () => void;
}

const ApiContext = createContext<ApiContextType | undefined>(undefined);

interface ApiProviderProps {
  children: ReactNode;
  baseURL?: string;
}

export const ApiProvider: React.FC<ApiProviderProps> = ({
  children,
  baseURL = process.env.REACT_APP_API_URL || 'http://localhost:3001/api'
}) => {
  const [apiState, setApiState] = useState<ApiState>({
    isOnline: navigator.onLine,
    pendingRequests: 0,
    lastRequestTime: null,
    error: null,
  });

  const { addNotification } = useAppStore();

  // Configure axios instance
  const api = axios.create({
    baseURL,
    timeout: 10000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor
  api.interceptors.request.use(
    (config) => {
      setApiState(prev => ({
        ...prev,
        pendingRequests: prev.pendingRequests + 1,
        lastRequestTime: new Date(),
      }));

      // Add auth token if available
      const token = localStorage.getItem('authToken');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      return config;
    },
    (error) => {
      setApiState(prev => ({
        ...prev,
        pendingRequests: Math.max(0, prev.pendingRequests - 1),
      }));
      return Promise.reject(error);
    }
  );

  // Response interceptor
  api.interceptors.response.use(
    (response) => {
      setApiState(prev => ({
        ...prev,
        pendingRequests: Math.max(0, prev.pendingRequests - 1),
        error: null,
      }));
      return response;
    },
    (error: AxiosError) => {
      setApiState(prev => ({
        ...prev,
        pendingRequests: Math.max(0, prev.pendingRequests - 1),
        error: error.message || 'API request failed',
      }));

      // Handle specific error types
      if (error.response?.status === 401) {
        // Unauthorized - token might be expired
        localStorage.removeItem('authToken');
        addNotification({
          type: 'error',
          title: 'Authentication Error',
          message: 'Your session has expired. Please sign in again.',
        });
      } else if (error.response?.status >= 500) {
        // Server error
        addNotification({
          type: 'error',
          title: 'Server Error',
          message: 'Something went wrong on our end. Please try again later.',
        });
      } else if (error.code === 'NETWORK_ERROR' || !navigator.onLine) {
        // Network error
        setApiState(prev => ({ ...prev, isOnline: false }));
        addNotification({
          type: 'warning',
          title: 'Connection Error',
          message: 'Please check your internet connection.',
        });
      }

      return Promise.reject(error);
    }
  );

  // Online/offline detection
  React.useEffect(() => {
    const handleOnline = () => {
      setApiState(prev => ({ ...prev, isOnline: true }));
      addNotification({
        type: 'success',
        title: 'Connection Restored',
        message: 'You are back online.',
      });
    };

    const handleOffline = () => {
      setApiState(prev => ({ ...prev, isOnline: false }));
      addNotification({
        type: 'warning',
        title: 'Connection Lost',
        message: 'You are currently offline.',
      });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [addNotification]);

  const setBaseURL = useCallback((url: string) => {
    api.defaults.baseURL = url;
  }, []);

  const setAuthToken = useCallback((token: string | null) => {
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete api.defaults.headers.common['Authorization'];
    }
  }, []);

  const clearError = useCallback(() => {
    setApiState(prev => ({ ...prev, error: null }));
  }, []);

  // HTTP method wrappers
  const get = useCallback(<T = any>(url: string, config?: AxiosRequestConfig) =>
    api.get<T>(url, config), []);

  const post = useCallback(<T = any>(url: string, data?: any, config?: AxiosRequestConfig) =>
    api.post<T>(url, data, config), []);

  const put = useCallback(<T = any>(url: string, data?: any, config?: AxiosRequestConfig) =>
    api.put<T>(url, data, config), []);

  const patch = useCallback(<T = any>(url: string, data?: any, config?: AxiosRequestConfig) =>
    api.patch<T>(url, data, config), []);

  const deleteMethod = useCallback(<T = any>(url: string, config?: AxiosRequestConfig) =>
    api.delete<T>(url, config), []);

  const value: ApiContextType = {
    ...apiState,
    get,
    post,
    put,
    patch,
    delete: deleteMethod,
    setBaseURL,
    setAuthToken,
    clearError,
  };

  return (
    <ApiContext.Provider value={value}>
      {children}
    </ApiContext.Provider>
  );
};

export const useApi = () => {
  const context = useContext(ApiContext);
  if (context === undefined) {
    throw new Error('useApi must be used within an ApiProvider');
  }
  return context;
};

// API status indicator component
export const ApiStatusIndicator: React.FC = () => {
  const { isOnline, pendingRequests, error } = useApi();

  if (isOnline && pendingRequests === 0 && !error) {
    return null; // Don't show anything when everything is fine
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <div className={`px-3 py-2 rounded-lg shadow-lg text-sm font-medium ${
        !isOnline
          ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
          : error
          ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
          : pendingRequests > 0
          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
          : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      }`}>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${
            !isOnline ? 'bg-red-500' :
            error ? 'bg-yellow-500' :
            pendingRequests > 0 ? 'bg-blue-500 animate-pulse' :
            'bg-green-500'
          }`} />
          <span>
            {!isOnline ? 'Offline' :
             error ? 'API Error' :
             pendingRequests > 0 ? `Loading (${pendingRequests})` :
             'Online'}
          </span>
        </div>
      </div>
    </div>
  );
};

// Retry hook for failed requests
export const useRetry = (maxRetries = 3, delay = 1000) => {
  const [retryCount, setRetryCount] = useState(0);

  const retry = useCallback(async <T>(
    fn: () => Promise<T>,
    currentRetry = 0
  ): Promise<T> => {
    try {
      const result = await fn();
      setRetryCount(0); // Reset on success
      return result;
    } catch (error) {
      if (currentRetry < maxRetries) {
        setRetryCount(currentRetry + 1);
        await new Promise(resolve => setTimeout(resolve, delay * (currentRetry + 1)));
        return retry(fn, currentRetry + 1);
      }
      throw error;
    }
  }, [maxRetries, delay]);

  return { retry, retryCount };
};

// Request deduplication hook
export const useRequestDedup = () => {
  const pendingRequests = React.useRef(new Map<string, Promise<any>>());

  const dedupedRequest = useCallback(async <T>(
    key: string,
    requestFn: () => Promise<T>
  ): Promise<T> => {
    if (pendingRequests.current.has(key)) {
      return pendingRequests.current.get(key)!;
    }

    const request = requestFn().finally(() => {
      pendingRequests.current.delete(key);
    });

    pendingRequests.current.set(key, request);
    return request;
  }, []);

  return { dedupedRequest };
};

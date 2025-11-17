import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios, { AxiosError } from 'axios';
import { io } from 'socket.io-client';
import { useAppStore } from '../store';
import type { Task, Workflow } from '../types';

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'http://localhost:3001/api';
axios.defaults.timeout = 10000;

// Request interceptor for auth
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
axios.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API hooks for different data types
export const useTasks = () => {
  const { setTasks, setLoading, setError } = useAppStore();

  return useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      setLoading('tasks', true);
      try {
        const response = await axios.get('/tasks');
        setTasks(response.data);
        setError('tasks', null);
        return response.data;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to fetch tasks';
        setError('tasks', message);
        throw error;
      } finally {
        setLoading('tasks', false);
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 3,
  });
};

export const useCreateTask = () => {
  const queryClient = useQueryClient();
  const { addTask, addNotification } = useAppStore();

  return useMutation({
    mutationFn: async (task: Omit<Task, 'id'>) => {
      const response = await axios.post('/tasks', task);
      return response.data;
    },
    onSuccess: (newTask) => {
      addTask(newTask);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      addNotification({
        type: 'success',
        title: 'Task Created',
        message: `Task "${newTask.title}" has been created successfully.`,
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Failed to Create Task',
        message: error instanceof Error ? error.message : 'An error occurred while creating the task.',
      });
    },
  });
};

export const useUpdateTask = () => {
  const queryClient = useQueryClient();
  const { updateTask, addNotification } = useAppStore();

  return useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<Task> }) => {
      const response = await axios.patch(`/tasks/${id}`, updates);
      return response.data;
    },
    onSuccess: (updatedTask) => {
      updateTask(updatedTask.id, updatedTask);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      addNotification({
        type: 'success',
        title: 'Task Updated',
        message: `Task "${updatedTask.title}" has been updated.`,
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Failed to Update Task',
        message: error instanceof Error ? error.message : 'An error occurred while updating the task.',
      });
    },
  });
};

export const useDeleteTask = () => {
  const queryClient = useQueryClient();
  const { deleteTask, addNotification } = useAppStore();

  return useMutation({
    mutationFn: async (id: string) => {
      await axios.delete(`/tasks/${id}`);
      return id;
    },
    onSuccess: (id) => {
      deleteTask(id);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      addNotification({
        type: 'success',
        title: 'Task Deleted',
        message: 'Task has been deleted successfully.',
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Failed to Delete Task',
        message: error instanceof Error ? error.message : 'An error occurred while deleting the task.',
      });
    },
  });
};

export const useCalendarEvents = (year: number, month: number) => {
  const { setCalendarEvents, setLoading, setError } = useAppStore();

  return useQuery({
    queryKey: ['calendar-events', year, month],
    queryFn: async () => {
      setLoading('calendar', true);
      try {
        const response = await axios.get(`/calendar/events`, {
          params: { year, month }
        });
        setCalendarEvents(response.data);
        setError('calendar', null);
        return response.data;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to fetch calendar events';
        setError('calendar', message);
        throw error;
      } finally {
        setLoading('calendar', false);
      }
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};

export const useMessages = () => {
  const { setMessages, setLoading, setError } = useAppStore();

  return useQuery({
    queryKey: ['messages'],
    queryFn: async () => {
      setLoading('messages', true);
      try {
        const response = await axios.get('/messages');
        setMessages(response.data);
        setError('messages', null);
        return response.data;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to fetch messages';
        setError('messages', message);
        throw error;
      } finally {
        setLoading('messages', false);
      }
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 30 * 1000, // Refetch every 30 seconds
  });
};

export const useIntegrations = () => {
  const { setIntegrations, setLoading, setError } = useAppStore();

  return useQuery({
    queryKey: ['integrations'],
    queryFn: async () => {
      setLoading('integrations', true);
      try {
        const response = await axios.get('/integrations');
        setIntegrations(response.data);
        setError('integrations', null);
        return response.data;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to fetch integrations';
        setError('integrations', message);
        throw error;
      } finally {
        setLoading('integrations', false);
      }
    },
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
};

export const useConnectIntegration = () => {
  const queryClient = useQueryClient();
  const { updateIntegration, addNotification } = useAppStore();

  return useMutation({
    mutationFn: async ({ id, config }: { id: string; config: Record<string, any> }) => {
      const response = await axios.post(`/integrations/${id}/connect`, config);
      return response.data;
    },
    onSuccess: (integration) => {
      updateIntegration(integration.id, integration);
      queryClient.invalidateQueries({ queryKey: ['integrations'] });
      addNotification({
        type: 'success',
        title: 'Integration Connected',
        message: `${integration.displayName} has been connected successfully.`,
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Connection Failed',
        message: error instanceof Error ? error.message : 'Failed to connect integration.',
      });
    },
  });
};

export const useWorkflows = () => {
  const { setWorkflows, setLoading, setError } = useAppStore();

  return useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      setLoading('workflows', true);
      try {
        const response = await axios.get('/workflows');
        setWorkflows(response.data);
        setError('workflows', null);
        return response.data;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to fetch workflows';
        setError('workflows', message);
        throw error;
      } finally {
        setLoading('workflows', false);
      }
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};

export const useCreateWorkflow = () => {
  const queryClient = useQueryClient();
  const { addWorkflow, addNotification } = useAppStore();

  return useMutation({
    mutationFn: async (workflow: Omit<Workflow, 'id' | 'executionCount' | 'lastExecuted'>) => {
      const response = await axios.post('/workflows', workflow);
      return response.data;
    },
    onSuccess: (newWorkflow) => {
      addWorkflow(newWorkflow);
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      addNotification({
        type: 'success',
        title: 'Workflow Created',
        message: `Workflow "${newWorkflow.name}" has been created successfully.`,
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Failed to Create Workflow',
        message: error instanceof Error ? error.message : 'An error occurred while creating the workflow.',
      });
    },
  });
};

export const useWeather = () => {
  return useQuery({
    queryKey: ['weather'],
    queryFn: async () => {
      const response = await axios.get('/weather/current');
      return response.data;
    },
    staleTime: 30 * 60 * 1000, // 30 minutes
    retry: 2,
  });
};

export const useNews = () => {
  return useQuery({
    queryKey: ['news'],
    queryFn: async () => {
      const response = await axios.get('/news');
      return response.data;
    },
    staleTime: 60 * 60 * 1000, // 1 hour
  });
};

export const useHealthMetrics = () => {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await axios.get('/health/metrics');
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 60 * 1000, // Refetch every minute
  });
};

// Real-time subscriptions using WebSocket
export const useRealtimeUpdates = () => {
  const { setConnected, addNotification } = useAppStore();
  const queryClient = useQueryClient();

  React.useEffect(() => {
    const socket = io();

    socket.on('connect', () => {
      setConnected(true);
      console.log('Connected to real-time updates');
    });

    socket.on('disconnect', () => {
      setConnected(false);
      console.log('Disconnected from real-time updates');
    });

    socket.on('task:updated', (task) => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      addNotification({
        type: 'info',
        title: 'Task Updated',
        message: `Task "${task.title}" has been updated.`,
      });
    });

    socket.on('message:new', (message) => {
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      addNotification({
        type: 'info',
        title: 'New Message',
        message: `New message from ${message.from.name}`,
      });
    });

    socket.on('calendar:event', (event) => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] });
      addNotification({
        type: 'info',
        title: 'Calendar Update',
        message: `New event: ${event.title}`,
      });
    });

    return () => {
      socket.disconnect();
    };
  }, [queryClient, setConnected, addNotification]);
};

// Utility hooks
export const useDebounce = (value: string, delay: number) => {
  const [debouncedValue, setDebouncedValue] = React.useState(value);

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

export const useLocalStorage = <T>(key: string, initialValue: T) => {
  const [storedValue, setStoredValue] = React.useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = React.useCallback((value: T | ((val: T) => T)) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  }, [key, storedValue]);

  return [storedValue, setValue] as const;
};

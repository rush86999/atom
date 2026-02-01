/**
 * Common Mobile Types
 * Shared TypeScript definitions for the mobile app
 */

import { ReactNode } from 'react';

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export type NavigationProp<T extends Record<string, object>> = import('@react-navigation/native').NavigationProp<T>;

export type RouteProp<T extends Record<string, object> = any> = import('@react-navigation/native').RouteProp<T, keyof T>;

export interface ScreenComponent {
  name: string;
  component: React.ComponentType<any>;
  options?: any;
}

export interface TabScreenConfig {
  name: string;
  component: React.ComponentType<any>;
  options: {
    tabBarLabel: string;
    tabBarIcon?: ({ focused, color, size }: any) => ReactNode;
    headerShown?: boolean;
  };
}

export interface LoadingState {
  isLoading: boolean;
  isRefreshing: boolean;
  error?: string;
}

export interface RootState {
  auth: {
    isAuthenticated: boolean;
    user: any;
    token: string | null;
  };
  workflows: {
    items: any[];
    filters: any;
    loading: boolean;
    error: string | null;
  };
  executions: {
    active: any[];
    history: any[];
    loading: boolean;
  };
  analytics: {
    kpis: any;
    timeline: any[];
    loading: boolean;
  };
}

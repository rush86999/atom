/**
 * Mobile API Service
 * Handles all HTTP requests to the backend API
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
// #6 fix: removed dead `import { AsyncStorage } from 'react-native'`
// (RN core dropped AsyncStorage in 0.59). The secureTokenStorage helpers
// use @react-native-async-storage/async-storage internally.
import {
  secureSet,
  secureGet,
  clearAuthSession,
  readAccessTokenSnapshot,
  invalidateAccessToken,
  isAccessTokenSnapshotCurrent,
  AccessTokenSnapshot,
} from '../storage/secureTokenStorage';
import { ApiResponse } from '../types/common';

// API base URL - configure for your environment
const API_BASE_URL = __DEV__
  ? 'http://localhost:8000'
  : 'https://api.atom-platform.com';

const EXPECTED_SNAPSHOT_KEY = 'expectedAccessTokenSnapshot';

/**
 * Opt-in request config for callers that must bind a request to the exact
 * access-token generation they observed. The request interceptor removes this
 * local-only property before the request reaches an adapter or transport.
 */
export interface ApiRequestConfig extends AxiosRequestConfig {
  expectedAccessTokenSnapshot?: AccessTokenSnapshot;
}

type UnknownRecord = { [key: string]: unknown };

function isUnknownRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isValidAccessTokenSnapshot(value: unknown): value is AccessTokenSnapshot {
  if (!isUnknownRecord(value)) return false;
  const token = value.token;
  const generation = value.generation;
  return (
    typeof token === 'string' &&
    token.length > 0 &&
    typeof generation === 'number' &&
    Number.isFinite(generation)
  );
}

/** Validate before Axios normalization can discard explicit undefined. */
function validateExpectedSnapshot(config: AxiosRequestConfig | undefined): void {
  if (!config || !Object.prototype.hasOwnProperty.call(config, EXPECTED_SNAPSHOT_KEY)) return;
  const expected = isUnknownRecord(config) ? config[EXPECTED_SNAPSHOT_KEY] : undefined;
  if (!isValidAccessTokenSnapshot(expected)) {
    throw new Error('Access token snapshot for this request is invalid');
  }
}

class ApiService {
  private client: AxiosInstance;
  private readonly requestSessions = new WeakMap<object, AccessTokenSnapshot>();

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      async (config) => {
        const session = await readAccessTokenSnapshot();
        const expectedProvided = Object.prototype.hasOwnProperty.call(
          config,
          EXPECTED_SNAPSHOT_KEY
        );

        if (expectedProvided) {
          const expected = isUnknownRecord(config)
            ? config[EXPECTED_SNAPSHOT_KEY]
            : undefined;

          if (!isValidAccessTokenSnapshot(expected)) {
            throw new Error('Access token snapshot for this request is invalid');
          }
          if (
            expected.generation !== session.generation ||
            expected.token !== session.token ||
            !isAccessTokenSnapshotCurrent(session) ||
            !isAccessTokenSnapshotCurrent(expected)
          ) {
            throw new Error('Access token snapshot for this request is not current');
          }
          if (!Reflect.deleteProperty(config, EXPECTED_SNAPSHOT_KEY)) {
            throw new Error('Access token snapshot for this request could not be cleared');
          }
        }

        this.requestSessions.set(config, session);
        if (session.token) {
          config.headers.Authorization = `Bearer ${session.token}`;
        } else {
          delete config.headers.Authorization;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          const session = error.config && this.requestSessions.get(error.config);
          // Only the exact request that used this session may invalidate it.
          if (session) await invalidateAccessToken(session);
        }
        return Promise.reject(error);
      }
    );
  }

  /**
   * Set authentication token
   */
  async setToken(token: string): Promise<void> {
    // #6 fix: use the same key AuthContext uses ('atom_access_token'),
    // not 'auth_token' which was never written by anything.
    await secureSet('atom_access_token', token);
  }

  /**
   * Get authentication token
   */
  async getToken(): Promise<string | null> {
    return secureGet('atom_access_token');
  }

  /**
   * Clear authentication token
   */
  async clearToken(): Promise<void> {
    await clearAuthSession();
  }

  /**
   * Generic GET request
   */
  async get<T>(url: string, config?: ApiRequestConfig): Promise<ApiResponse<T>> {
    try {
      validateExpectedSnapshot(config);
      const response: AxiosResponse<T> = await this.client.get(url, config);
      return { success: true, data: response.data };
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.detail || error.message || 'Request failed',
      };
    }
  }

  /**
   * Generic POST request
   */
  async post<T>(url: string, data?: any, config?: ApiRequestConfig): Promise<ApiResponse<T>> {
    try {
      validateExpectedSnapshot(config);
      const response: AxiosResponse<T> = await this.client.post(url, data, config);
      return { success: true, data: response.data };
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.detail || error.message || 'Request failed',
      };
    }
  }

  /**
   * Generic PUT request
   */
  async put<T>(url: string, data?: any, config?: ApiRequestConfig): Promise<ApiResponse<T>> {
    try {
      validateExpectedSnapshot(config);
      const response: AxiosResponse<T> = await this.client.put(url, data, config);
      return { success: true, data: response.data };
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.detail || error.message || 'Request failed',
      };
    }
  }

  /**
   * Generic DELETE request
   */
  async delete<T>(url: string, config?: ApiRequestConfig): Promise<ApiResponse<T>> {
    try {
      validateExpectedSnapshot(config);
      const response: AxiosResponse<T> = await this.client.delete(url, config);
      return { success: true, data: response.data };
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.detail || error.message || 'Request failed',
      };
    }
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;

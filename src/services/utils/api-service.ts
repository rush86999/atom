/**
 * Basic API Service - Test connection to backend
 */

import axios from 'axios';
import { PYTHON_API_SERVICE_BASE_URL } from '@shared-utils/constants';
import { logger } from '@shared-utils/logger';
import { SkillResponse } from '@shared-services/types/skill-response';

class ApiService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || PYTHON_API_SERVICE_BASE_URL;
  }

  async healthCheck(): Promise<SkillResponse<{ status: string }>> {
    try {
      logger.info('[ApiService] Checking backend health...', { baseUrl: this.baseUrl });
      
      const response = await axios.get(`${this.baseUrl}/healthz`, {
        timeout: 5000,
      });

      return {
        ok: true,
        data: {
          status: response.data.status || 'healthy',
        },
        metadata: {
          timestamp: new Date().toISOString(),
          executionTime: Date.now(),
          version: '1.0.0',
        },
      };
    } catch (error: any) {
      logger.error('[ApiService] Health check failed', error);
      return {
        ok: false,
        error: {
          code: 'HEALTH_CHECK_FAILED',
          message: error.message || 'Failed to connect to backend',
          details: error,
        },
      };
    }
  }

  async testIntegration(serviceName: string): Promise<SkillResponse<any>> {
    try {
      logger.info(`[ApiService] Testing ${serviceName} integration...`);
      
      const response = await axios.get(`${this.baseUrl}/api/${serviceName}/health`, {
        timeout: 10000,
      });

      return {
        ok: true,
        data: response.data,
      };
    } catch (error: any) {
      logger.error(`[ApiService] ${serviceName} integration test failed`, error);
      return {
        ok: false,
        error: {
          code: 'INTEGRATION_TEST_FAILED',
          message: `Failed to test ${serviceName} integration`,
          details: error,
        },
      };
    }
  }
}

export const apiService = new ApiService();
export default ApiService;
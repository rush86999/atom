/**
 * useApiService Hook - Test API connectivity in React components
 */

import { useState, useEffect } from 'react';
import { apiService } from '@shared-utils/api-service';
import { SkillResponse } from '@shared-services/types/skill-response';

interface UseApiServiceResult {
  health: SkillResponse<{ status: string }>;
  loading: boolean;
  testIntegration: (service: string) => Promise<SkillResponse<any>>;
  refetch: () => void;
}

export const useApiService = (): UseApiServiceResult => {
  const [health, setHealth] = useState<SkillResponse<{ status: string }>>({
    ok: false,
    error: {
      code: 'NOT_CHECKED',
      message: 'Health check not performed',
    },
  });
  const [loading, setLoading] = useState(true);

  const checkHealth = async () => {
    setLoading(true);
    try {
      const result = await apiService.healthCheck();
      setHealth(result);
    } catch (error) {
      setHealth({
        ok: false,
        error: {
          code: 'HEALTH_CHECK_ERROR',
          message: 'Failed to perform health check',
        },
      });
    } finally {
      setLoading(false);
    }
  };

  const testIntegration = async (service: string): Promise<SkillResponse<any>> => {
    return await apiService.testIntegration(service);
  };

  const refetch = () => {
    checkHealth();
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return {
    health,
    loading,
    testIntegration,
    refetch,
  };
};
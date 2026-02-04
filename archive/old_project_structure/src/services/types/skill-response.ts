/**
 * Skill Response Type Definitions
 * Unified response format for all skill services
 */

export interface SkillResponse<T = any> {
  ok: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  metadata?: {
    timestamp: string;
    executionTime: number;
    version: string;
  };
}

export interface SkillRequest {
  userId: string;
  action: string;
  parameters?: Record<string, any>;
  context?: Record<string, any>;
}

export interface SkillMetadata {
  name: string;
  version: string;
  description: string;
  category: string;
  requiredParams: string[];
  optionalParams: string[];
}
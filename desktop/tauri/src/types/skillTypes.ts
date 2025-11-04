/**
 * Types for Skills and Execution Context
 */

export interface Skill {
  execute(params: any, context: SkillExecutionContext): Promise<any>;
}

export interface SkillExecutionContext {
  userId: string;
  sessionId: string;
  timestamp: string;
  intent?: string;
  entities?: any[];
  confidence?: number;
  metadata?: Record<string, any>;
}

export interface SkillResult {
  success: boolean;
  data?: any;
  error?: string;
  metadata?: Record<string, any>;
  timestamp: string;
}

export interface SkillRegistry {
  registerSkill(name: string, skill: Skill): void;
  getSkill(name: string): Skill | null;
  listSkills(): string[];
}

export interface SkillConfig {
  name: string;
  description: string;
  category: string;
  parameters: SkillParameter[];
  enabled: boolean;
  requiredPermissions?: string[];
}

export interface SkillParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  description: string;
  defaultValue?: any;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
  };
}
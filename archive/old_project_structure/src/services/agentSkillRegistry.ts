/**
 * Agent Skill Registry
 *
 * Central registry for managing and executing agent skills across the ATOM platform.
 * Provides skill discovery, registration, execution, and lifecycle management.
 */

export interface SkillDefinition {
  id: string;
  name: string;
  description: string;
  category: string;
  icon?: string;
  parameters: SkillParameters;
  handler: SkillHandler;
  dependencies?: string[];
  version: string;
  enabled: boolean;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface SkillParameters {
  type: 'object';
  properties: Record<string, SkillParameter>;
  required?: string[];
}

export interface SkillParameter {
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  description: string;
  enum?: string[];
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  default?: any;
  items?: SkillParameter;
  properties?: Record<string, SkillParameter>;
}

export interface SkillHandler {
  (userId: string, parameters: Record<string, any>, context?: SkillContext): Promise<SkillResponse<any>>;
}

export interface SkillContext {
  sessionId?: string;
  workspaceId?: string;
  environment?: 'development' | 'staging' | 'production';
  metadata?: Record<string, any>;
}

export interface SkillResponse<T = any> {
  ok: boolean;
  data?: T;
  error?: SkillError;
  metadata?: {
    executionTime: number;
    resourceUsage?: ResourceUsage;
    warnings?: string[];
  };
}

export interface SkillError {
  code: string;
  message: string;
  details?: any;
  retryable?: boolean;
}

export interface ResourceUsage {
  apiCalls: number;
  computeTime: number;
  memoryUsage: number;
  storageUsage: number;
}

export interface SkillExecutionResult {
  skillId: string;
  success: boolean;
  result: SkillResponse;
  executionTime: number;
  timestamp: Date;
}

export interface SkillRegistryConfig {
  autoRegister: boolean;
  validateParameters: boolean;
  enableCaching: boolean;
  cacheTTL: number;
  maxConcurrentExecutions: number;
  timeout: number;
}

export class AgentSkillRegistry {
  private skills: Map<string, SkillDefinition> = new Map();
  private executionHistory: Map<string, SkillExecutionResult[]> = new Map();
  private config: SkillRegistryConfig;
  private isInitialized: boolean = false;

  constructor(config: Partial<SkillRegistryConfig> = {}) {
    this.config = {
      autoRegister: true,
      validateParameters: true,
      enableCaching: false,
      cacheTTL: 300000, // 5 minutes
      maxConcurrentExecutions: 10,
      timeout: 30000, // 30 seconds
      ...config
    };
  }

  /**
   * Initialize the skill registry
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    console.log('🔧 Initializing Agent Skill Registry...');

    // Register core skills
    await this.registerCoreSkills();

    this.isInitialized = true;
    console.log('✅ Agent Skill Registry initialized successfully');
  }

  /**
   * Register a new skill
   */
  async registerSkill(skill: SkillDefinition): Promise<boolean> {
    try {
      // Validate skill definition
      if (!this.validateSkillDefinition(skill)) {
        console.error(`❌ Invalid skill definition for: ${skill.name}`);
        return false;
      }

      // Check for duplicates
      if (this.skills.has(skill.id)) {
        console.warn(`⚠️ Skill already registered: ${skill.id}`);
        return false;
      }

      // Register the skill
      this.skills.set(skill.id, skill);

      console.log(`✅ Registered skill: ${skill.name} (${skill.id})`);
      return true;

    } catch (error) {
      console.error(`❌ Failed to register skill ${skill.name}:`, error);
      return false;
    }
  }

  /**
   * Execute a skill
   */
  async executeSkill(
    skillId: string,
    userId: string,
    parameters: Record<string, any> = {},
    context: SkillContext = {}
  ): Promise<SkillResponse> {
    const startTime = Date.now();

    try {
      // Get skill definition
      const skill = this.skills.get(skillId);
      if (!skill) {
        return {
          ok: false,
          error: {
            code: 'SKILL_NOT_FOUND',
            message: `Skill not found: ${skillId}`
          }
        };
      }

      // Check if skill is enabled
      if (!skill.enabled) {
        return {
          ok: false,
          error: {
            code: 'SKILL_DISABLED',
            message: `Skill is disabled: ${skill.name}`
          }
        };
      }

      // Validate parameters if enabled
      if (this.config.validateParameters) {
        const validationResult = this.validateParameters(skill.parameters, parameters);
        if (!validationResult.valid) {
          return {
            ok: false,
            error: {
              code: 'INVALID_PARAMETERS',
              message: `Invalid parameters: ${validationResult.errors.join(', ')}`
            }
          };
        }
      }

      // Execute the skill
      console.log(`🚀 Executing skill: ${skill.name} for user ${userId}`);

      const result = await Promise.race([
        skill.handler(userId, parameters, context),
        new Promise<SkillResponse>((_, reject) =>
          setTimeout(() => reject(new Error('Skill execution timeout')), this.config.timeout)
        )
      ]);

      const executionTime = Date.now() - startTime;

      // Record execution history
      this.recordExecution(skillId, {
        skillId,
        success: result.ok,
        result,
        executionTime,
        timestamp: new Date()
      });

      // Add execution metadata
      result.metadata = {
        executionTime,
        resourceUsage: {
          apiCalls: 1,
          computeTime: executionTime,
          memoryUsage: 0,
          storageUsage: 0
        },
        warnings: result.metadata?.warnings || []
      };

      console.log(`✅ Skill execution completed: ${skill.name} (${executionTime}ms)`);
      return result;

    } catch (error) {
      const executionTime = Date.now() - startTime;

      const errorResult: SkillResponse = {
        ok: false,
        error: {
          code: 'EXECUTION_ERROR',
          message: error instanceof Error ? error.message : 'Unknown execution error',
          retryable: true
        }
      };

      this.recordExecution(skillId, {
        skillId,
        success: false,
        result: errorResult,
        executionTime,
        timestamp: new Date()
      });

      console.error(`❌ Skill execution failed: ${skillId}`, error);
      return errorResult;
    }
  }

  /**
   * Get all registered skills
   */
  getSkills(): SkillDefinition[] {
    return Array.from(this.skills.values());
  }

  /**
   * Get skills by category
   */
  getSkillsByCategory(category: string): SkillDefinition[] {
    return this.getSkills().filter(skill => skill.category === category);
  }

  /**
   * Get skill by ID
   */
  getSkill(skillId: string): SkillDefinition | undefined {
    return this.skills.get(skillId);
  }

  /**
   * Enable/disable a skill
   */
  setSkillEnabled(skillId: string, enabled: boolean): boolean {
    const skill = this.skills.get(skillId);
    if (!skill) {
      return false;
    }

    skill.enabled = enabled;
    console.log(`🔧 Skill ${skill.name} ${enabled ? 'enabled' : 'disabled'}`);
    return true;
  }

  /**
   * Get execution history for a skill
   */
  getExecutionHistory(skillId: string, limit: number = 50): SkillExecutionResult[] {
    const history = this.executionHistory.get(skillId) || [];
    return history.slice(-limit);
  }

  /**
   * Get skill execution statistics
   */
  getSkillStatistics(skillId: string): {
    totalExecutions: number;
    successfulExecutions: number;
    failureRate: number;
    averageExecutionTime: number;
  } {
    const history = this.getExecutionHistory(skillId);
    const totalExecutions = history.length;
    const successfulExecutions = history.filter(exec => exec.success).length;
    const totalExecutionTime = history.reduce((sum, exec) => sum + exec.executionTime, 0);

    return {
      totalExecutions,
      successfulExecutions,
      failureRate: totalExecutions > 0 ? (totalExecutions - successfulExecutions) / totalExecutions : 0,
      averageExecutionTime: totalExecutions > 0 ? totalExecutionTime / totalExecutions : 0
    };
  }

  /**
   * Search skills by name, description, or tags
   */
  searchSkills(query: string): SkillDefinition[] {
    const lowerQuery = query.toLowerCase();
    return this.getSkills().filter(skill =>
      skill.name.toLowerCase().includes(lowerQuery) ||
      skill.description.toLowerCase().includes(lowerQuery) ||
      skill.tags?.some(tag => tag.toLowerCase().includes(lowerQuery)) ||
      false
    );
  }

  /**
   * Validate skill definition
   */
  private validateSkillDefinition(skill: SkillDefinition): boolean {
    if (!skill.id || !skill.name || !skill.description || !skill.category) {
      return false;
    }

    if (!skill.parameters || !skill.handler) {
      return false;
    }

    if (typeof skill.handler !== 'function') {
      return false;
    }

    return true;
  }

  /**
   * Validate parameters against schema
   */
  private validateParameters(
    schema: SkillParameters,
    parameters: Record<string, any>
  ): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Check required parameters
    if (schema.required) {
      for (const requiredParam of schema.required) {
        if (!(requiredParam in parameters)) {
          errors.push(`Missing required parameter: ${requiredParam}`);
        }
      }
    }

    // Validate each parameter
    for (const [paramName, paramValue] of Object.entries(parameters)) {
      const paramSchema = schema.properties[paramName];
      if (!paramSchema) {
        errors.push(`Unknown parameter: ${paramName}`);
        continue;
      }

      const paramError = this.validateParameter(paramName, paramValue, paramSchema);
      if (paramError) {
        errors.push(paramError);
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Validate individual parameter
   */
  private validateParameter(
    paramName: string,
    value: any,
    schema: SkillParameter
  ): string | null {
    // Type validation
    if (schema.type === 'string' && typeof value !== 'string') {
      return `Parameter ${paramName} must be a string`;
    }

    if (schema.type === 'number' && typeof value !== 'number') {
      return `Parameter ${paramName} must be a number`;
    }

    if (schema.type === 'boolean' && typeof value !== 'boolean') {
      return `Parameter ${paramName} must be a boolean`;
    }

    if (schema.type === 'array' && !Array.isArray(value)) {
      return `Parameter ${paramName} must be an array`;
    }

    if (schema.type === 'object' && (typeof value !== 'object' || Array.isArray(value))) {
      return `Parameter ${paramName} must be an object`;
    }

    // String length validation
    if (schema.type === 'string') {
      if (schema.minLength && value.length < schema.minLength) {
        return `Parameter ${paramName} must be at least ${schema.minLength} characters`;
      }
      if (schema.maxLength && value.length > schema.maxLength) {
        return `Parameter ${paramName} must be at most ${schema.maxLength} characters`;
      }
    }

    // Number range validation
    if (schema.type === 'number') {
      if (schema.minimum !== undefined && value < schema.minimum) {
        return `Parameter ${paramName} must be at least ${schema.minimum}`;
      }
      if (schema.maximum !== undefined && value > schema.maximum) {
        return `Parameter ${paramName} must be at most ${schema.maximum}`;
      }
    }

    // Enum validation
    if (schema.enum && !schema.enum.includes(value)) {
      return `Parameter ${paramName} must be one of: ${schema.enum.join(', ')}`;
    }

    // Array item validation
    if (schema.type === 'array' && schema.items) {
      for (let i = 0; i < value.length; i++) {
        const itemError = this.validateParameter(`${paramName}[${i}]`, value[i], schema.items);
        if (itemError) {
          return itemError;
        }
      }
    }

    // Object property validation
    if (schema.type === 'object' && schema.properties) {
      for (const [propName, propSchema] of Object.entries(schema.properties)) {
        if (value[propName] !== undefined) {
          const propError = this.validateParameter(
            `${paramName}.${propName}`,
            value[propName],
            propSchema
          );
          if (propError) {
            return propError;
          }
        }
      }
    }

    return null;
  }

  /**
   * Record skill execution
   */
  private recordExecution(skillId: string, result: SkillExecutionResult): void {
    const history = this.executionHistory.get(skillId) || [];
    history.push(result);
    this.executionHistory.set(skillId, history);
  }

  /**
   * Register core skills
   */
  private async registerCoreSkills(): Promise<void> {
    // This would register built-in skills
    // For now, it's a placeholder for future core skill registration
    console.log('📋 No core skills to register yet');
  }

  /**
   * Get registry status
   */
  getStatus(): {
    totalSkills: number;
    enabledSkills: number;
    totalExecutions: number;
    isInitialized: boolean;
  } {
    const skills = this.getSkills();
    const totalExecutions = Array.from(this.executionHistory.values())
      .reduce((sum, history) => sum + history.length, 0);

    return {
      totalSkills: skills.length,
      enabledSkills: skills.filter(skill => skill.enabled).length,
      totalExecutions,
      isInitialized: this.isInitialized
    };
  }
}

// Export singleton instance
export const agentSkillRegistry = new AgentSkillRegistry();

// Export convenience functions
export async function registerSkill(skill: SkillDefinition): Promise<boolean> {
  return agentSkillRegistry.registerSkill(skill);
}

export async function executeSkill(
  skillId: string,
  userId: string,
  parameters: Record<string, any> = {},
  context: SkillContext = {}
): Promise<SkillResponse> {
  return agentSkillRegistry.executeSkill(skillId, userId, parameters, context);
}

export function getSkills(): SkillDefinition[] {
  return agentSkillRegistry.getSkills();
}

export function getSkill(skillId: string): SkillDefinition | undefined {
  return agentSkillRegistry.getSkill(skillId);
}

// Auto-initialize on import
agentSkillRegistry.initialize().catch(console.error);

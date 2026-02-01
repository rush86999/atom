import { EventEmitter } from "events";

export interface Skill {
  name: string;
  description: string;
  parameters: Record<string, ParameterDefinition>;
  requiredParameters: string[];
  category: string;
  version: string;
}

export interface ParameterDefinition {
  type: "string" | "number" | "boolean" | "array" | "object";
  required: boolean;
  description?: string;
  defaultValue?: any;
  validation?: {
    min?: number;
    max?: number;
    minLength?: number;
    maxLength?: number;
    pattern?: string;
    enum?: any[];
  };
}

export interface SkillExecution {
  id: string;
  skillName: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  parameters: Record<string, any>;
  result?: any;
  error?: Error;
  startTime: Date;
  endTime?: Date;
  duration?: number;
}

export interface SkillStats {
  totalExecutions: number;
  successfulExecutions: number;
  failedExecutions: number;
  averageExecutionTime: number;
  lastExecutionTime?: Date;
}

export class SkillService extends EventEmitter {
  private availableSkills: Skill[];
  private executions: Map<string, SkillExecution>;
  private stats: Map<string, SkillStats>;

  constructor() {
    super();
    this.availableSkills = [];
    this.executions = new Map();
    this.stats = new Map();
    this.initializeDefaultSkills();
  }

  private initializeDefaultSkills(): void {
    this.availableSkills = [
      {
        name: "calendar_create_event",
        description: "Create calendar events and meetings",
        parameters: {
          title: { type: "string", required: true, description: "Event title" },
          time: { type: "string", required: true, description: "Event time" },
          duration: {
            type: "number",
            required: false,
            description: "Duration in minutes",
          },
          participants: {
            type: "array",
            required: false,
            description: "List of participants",
          },
        },
        requiredParameters: ["title", "time"],
        category: "calendar",
        version: "1.0.0",
      },
      {
        name: "analyze_financial_data",
        description: "Analyze financial reports and data",
        parameters: {
          report_type: {
            type: "string",
            required: true,
            description: "Type of financial report",
          },
          time_period: {
            type: "string",
            required: true,
            description: "Time period for analysis",
          },
          metrics: {
            type: "array",
            required: false,
            description: "Specific metrics to analyze",
          },
        },
        requiredParameters: ["report_type", "time_period"],
        category: "finance",
        version: "1.0.0",
      },
      {
        name: "generate_report",
        description: "Generate reports from analyzed data",
        parameters: {
          format: {
            type: "string",
            required: true,
            description: "Report format (pdf, html, etc.)",
          },
          data: {
            type: "object",
            required: true,
            description: "Data to include in report",
          },
          template: {
            type: "string",
            required: false,
            description: "Template to use",
          },
        },
        requiredParameters: ["format", "data"],
        category: "document",
        version: "1.0.0",
      },
      {
        name: "extract_text",
        description: "Extract text from documents",
        parameters: {
          document_type: {
            type: "string",
            required: true,
            description: "Type of document",
          },
          file_path: {
            type: "string",
            required: true,
            description: "Path to document file",
          },
          language: {
            type: "string",
            required: false,
            description: "Document language",
          },
        },
        requiredParameters: ["document_type", "file_path"],
        category: "document",
        version: "1.0.0",
      },
      {
        name: "analyze_content",
        description: "Analyze extracted text content",
        parameters: {
          content: {
            type: "string",
            required: true,
            description: "Text content to analyze",
          },
          analysis_type: {
            type: "string",
            required: true,
            description: "Type of analysis to perform",
          },
          depth: {
            type: "number",
            required: false,
            description: "Analysis depth level",
          },
        },
        requiredParameters: ["content", "analysis_type"],
        category: "analysis",
        version: "1.0.0",
      },
    ];
  }

  async executeSkill(
    skillName: string,
    parameters: Record<string, any> = {},
  ): Promise<any> {
    const skill = this.availableSkills.find((s) => s.name === skillName);
    if (!skill) {
      throw new Error(`Skill "${skillName}" not found`);
    }

    // Validate parameters
    const validation = await this.validateSkillParameters(skill, parameters);
    if (!validation.valid) {
      throw new Error(
        `Missing required parameters: ${validation.missing.join(", ")}`,
      );
    }

    const executionId = this.generateExecutionId();
    const execution: SkillExecution = {
      id: executionId,
      skillName,
      status: "pending",
      parameters,
      startTime: new Date(),
    };

    this.executions.set(executionId, execution);
    this.emit("executionStarted", execution);

    try {
      execution.status = "running";
      const result = await this.executeSkillLogic(skill, parameters);

      execution.status = "completed";
      execution.result = result;
      execution.endTime = new Date();
      execution.duration =
        execution.endTime.getTime() - execution.startTime.getTime();

      this.updateStats(
        skillName,
        true,
        execution.startTime,
        execution.endTime!,
      );
      this.emit("executionCompleted", execution);

      return result;
    } catch (error) {
      execution.status = "failed";
      execution.error = error as Error;
      execution.endTime = new Date();
      execution.duration =
        execution.endTime.getTime() - execution.startTime.getTime();

      this.updateStats(
        skillName,
        false,
        execution.startTime,
        execution.endTime!,
      );
      this.emit("executionFailed", execution);

      throw error;
    }
  }

  async getAvailableSkills(): Promise<string[]> {
    return this.availableSkills.map((skill) => skill.name);
  }

  async getSkillDetails(skillName: string): Promise<Skill | null> {
    return this.availableSkills.find((s) => s.name === skillName) || null;
  }

  async validateSkillParameters(
    skill: Skill,
    parameters: Record<string, any>,
  ): Promise<{ valid: boolean; missing: string[] }> {
    const missingParams = skill.requiredParameters.filter(
      (param) =>
        !(param in parameters) &&
        parameters[param] !== false &&
        parameters[param] !== 0,
    );

    return {
      valid: missingParams.length === 0,
      missing: missingParams,
    };
  }

  async registerSkill(skill: Skill): Promise<boolean> {
    if (this.availableSkills.some((s) => s.name === skill.name)) {
      return false;
    }
    this.availableSkills.push(skill);
    return true;
  }

  async unregisterSkill(skillName: string): Promise<boolean> {
    const index = this.availableSkills.findIndex((s) => s.name === skillName);
    if (index === -1) {
      return false;
    }
    this.availableSkills.splice(index, 1);
    return true;
  }

  async listSkills(): Promise<Skill[]> {
    return [...this.availableSkills];
  }

  async skillExists(skillName: string): Promise<boolean> {
    return this.availableSkills.some((s) => s.name === skillName);
  }

  async getExecution(executionId: string): Promise<SkillExecution | null> {
    return this.executions.get(executionId) || null;
  }

  async getStats(skillName: string): Promise<SkillStats | null> {
    return this.stats.get(skillName) || null;
  }

  async getAllStats(): Promise<Map<string, SkillStats>> {
    return new Map(this.stats);
  }

  private async executeSkillLogic(
    skill: Skill,
    parameters: Record<string, any>,
  ): Promise<any> {
    // Simulate skill execution delay
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Mock implementation - in real scenario, this would call actual skill logic
    switch (skill.name) {
      case "calendar_create_event":
        return {
          success: true,
          event_id: `event_${Date.now()}`,
          title: parameters.title,
          time: parameters.time,
          created_at: new Date().toISOString(),
        };

      case "analyze_financial_data":
        return {
          success: true,
          analysis_id: `analysis_${Date.now()}`,
          report_type: parameters.report_type,
          metrics: ["revenue", "expenses", "profit"],
          summary: "Financial analysis completed successfully",
        };

      case "generate_report":
        return {
          success: true,
          report_id: `report_${Date.now()}`,
          format: parameters.format,
          generated_at: new Date().toISOString(),
          download_url: `/reports/${Date.now()}.${parameters.format}`,
        };

      case "extract_text":
        return {
          success: true,
          extraction_id: `extract_${Date.now()}`,
          document_type: parameters.document_type,
          content: "This is extracted text content from the document.",
          word_count: 42,
          extracted_at: new Date().toISOString(),
        };

      case "analyze_content":
        return {
          success: true,
          analysis_id: `content_${Date.now()}`,
          analysis_type: parameters.analysis_type,
          sentiment: "positive",
          key_topics: ["technology", "business", "innovation"],
          summary: "Content analysis completed successfully",
        };

      default:
        return {
          success: true,
          skill: skill.name,
          parameters,
          executed_at: new Date().toISOString(),
          message: "Skill executed successfully",
        };
    }
  }

  private generateExecutionId(): string {
    return `skill_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private updateStats(
    skillName: string,
    success: boolean,
    startTime: Date,
    endTime: Date,
  ): void {
    const executionTime = endTime.getTime() - startTime.getTime();
    let stats = this.stats.get(skillName);

    if (!stats) {
      stats = {
        totalExecutions: 0,
        successfulExecutions: 0,
        failedExecutions: 0,
        averageExecutionTime: 0,
      };
    }

    stats.totalExecutions++;
    if (success) {
      stats.successfulExecutions++;
    } else {
      stats.failedExecutions++;
    }

    // Update average execution time
    stats.averageExecutionTime =
      (stats.averageExecutionTime * (stats.totalExecutions - 1) +
        executionTime) /
      stats.totalExecutions;

    stats.lastExecutionTime = new Date();
    this.stats.set(skillName, stats);
  }

  async clearExecutions(): Promise<void> {
    this.executions.clear();
  }

  async clearStats(): Promise<void> {
    this.stats.clear();
  }
}

// Export singleton instance
export const skillService = new SkillService();

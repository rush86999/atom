import { NLUHybridIntegrationService } from "./nluHybridIntegrationService";

// Mock the NLU service with a simple implementation
class MockNLUService {
  async understandMessage(message: string, context?: any): Promise<any> {
    // Simple mock implementation for testing
    if (message.toLowerCase().includes("hello")) {
      return {
        intent: "greeting",
        confidence: 0.9,
        entities: {},
        action: "respond",
        parameters: {},
        workflow: undefined,
        requiresConfirmation: false,
        suggestedResponses: ["Hello! How can I help you?"],
        context: undefined,
      };
    } else if (message.toLowerCase().includes("schedule")) {
      return {
        intent: "schedule_meeting",
        confidence: 0.85,
        entities: { participant: "default", time: "default" },
        action: "execute_skill",
        parameters: { participant: "default", time: "default" },
        workflow: "calendar_scheduling",
        requiresConfirmation: true,
        suggestedResponses: ["Should I schedule this meeting?"],
        context: undefined,
      };
    }
    throw new Error("Mock NLU service error");
  }
}

// Mock other services with minimal implementations
class MockOpenAIService {
  async analyzeMessage(message: string, options?: any): Promise<any> {
    return {
      intent: "ai_analysis",
      confidence: 0.8,
      entities: {},
      action: "respond",
      parameters: {},
      requiresConfirmation: false,
      suggestedResponses: ["AI analysis completed"],
      context: undefined,
    };
  }
}

class MockWorkflowService {
  async executeWorkflow(
    workflowName: string,
    parameters: Record<string, any>,
  ): Promise<any> {
    return { success: true, workflow: workflowName, parameters };
  }
  async getAvailableWorkflows(): Promise<string[]> {
    return ["calendar_scheduling", "financial_analysis"];
  }
}

class MockSkillService {
  async executeSkill(
    skillName: string,
    parameters: Record<string, any>,
  ): Promise<any> {
    return { success: true, skill: skillName, parameters };
  }
  async getAvailableSkills(): Promise<string[]> {
    return ["calendar_create_event", "analyze_financial_data"];
  }
}

describe("NLUHybridIntegrationService - Simple Test", () => {
  let hybridService: NLUHybridIntegrationService;
  let mockNLUService: MockNLUService;
  let mockOpenAIService: MockOpenAIService;
  let mockWorkflowService: MockWorkflowService;
  let mockSkillService: MockSkillService;

  beforeEach(() => {
    mockNLUService = new MockNLUService();
    mockOpenAIService = new MockOpenAIService();
    mockWorkflowService = new MockWorkflowService();
    mockSkillService = new MockSkillService();

    hybridService = new NLUHybridIntegrationService(
      mockNLUService as any,
      mockOpenAIService as any,
      mockWorkflowService as any,
      mockSkillService as any,
    );
  });

  test("should be instantiated correctly", () => {
    expect(hybridService).toBeInstanceOf(NLUHybridIntegrationService);
  });

  test("should handle simple messages with rules-based approach", async () => {
    const simpleMessage = "hello there";
    const result = await hybridService.understandMessage(simpleMessage);

    expect(result.intent).toBe("greeting");
    expect(result.confidence).toBe(0.9);
    expect(result.providerUsed).toBe("rules");
    expect(result.processingTime).toBeGreaterThan(0);
  });

  test("should handle medium complexity messages with hybrid approach", async () => {
    const mediumMessage = "schedule a meeting with John tomorrow at 2pm";
    const result = await hybridService.understandMessage(mediumMessage);

    expect(result.intent).toBe("schedule_meeting");
    expect(result.confidence).toBeGreaterThan(0.85); // AI enhancement increases confidence
    expect(result.providerUsed).toBe("hybrid");
    expect(result.processingTime).toBeGreaterThan(0);
  });

  test("should allow configuration updates", () => {
    const initialConfig = hybridService.getConfig();
    expect(initialConfig.enableHybridMode).toBe(true);

    hybridService.updateConfig({
      enableHybridMode: false,
      complexityThreshold: 0.8,
    });

    const updatedConfig = hybridService.getConfig();
    expect(updatedConfig.enableHybridMode).toBe(false);
    expect(updatedConfig.complexityThreshold).toBe(0.8);
  });

  test("should process batch messages", async () => {
    const messages = ["hello", "schedule meeting"];
    const results = await hybridService.batchProcess(messages);

    expect(results).toHaveLength(2);
    expect(results[0].intent).toBe("greeting");
    expect(results[1].intent).toBe("schedule_meeting");
  });

  test("should integrate with workflow service", async () => {
    const workflowName = "calendar_scheduling";
    const parameters = { meeting_time: "2pm", participant: "John" };

    const result = await hybridService.executeWorkflow(
      workflowName,
      parameters,
    );

    expect(result.success).toBe(true);
    expect(result.workflow).toBe(workflowName);
  });

  test("should integrate with skill service", async () => {
    const skillName = "calendar_create_event";
    const parameters = { title: "Meeting", time: "2pm" };

    const result = await hybridService.executeSkill(skillName, parameters);

    expect(result.success).toBe(true);
    expect(result.skill).toBe(skillName);
  });

  test("should get available workflows", async () => {
    const workflows = await hybridService.getAvailableWorkflows();
    expect(workflows).toContain("calendar_scheduling");
    expect(workflows).toContain("financial_analysis");
  });

  test("should get available skills", async () => {
    const skills = await hybridService.getAvailableSkills();
    expect(skills).toContain("calendar_create_event");
    expect(skills).toContain("analyze_financial_data");
  });

  test("should handle message complexity calculation", () => {
    const simpleMessage = "hi";
    const complexMessage =
      "schedule a meeting with John tomorrow at 2pm about quarterly financial reports";

    const simpleComplexity = (hybridService as any).calculateMessageComplexity(
      simpleMessage,
    );
    const complexComplexity = (hybridService as any).calculateMessageComplexity(
      complexMessage,
    );

    expect(simpleComplexity).toBeLessThan(0.5);
    expect(complexComplexity).toBeGreaterThan(0.5);
  });
});

const { describe, it, expect, beforeEach } = require("@jest/globals");
const jest = require("@jest/globals").jest;

// Mock the required services
jest.mock("../src/services/openaiService", () => {
  return {
    OpenAIService: jest.fn().mockImplementation(() => ({
      chatCompletion: jest.fn().mockResolvedValue({
        content: JSON.stringify({
          intent: "test_intent",
          confidence: 0.9,
          entities: { test: "value" },
          action: "test_action",
          parameters: { test: "value" },
        }),
        usage: { total_tokens: 100, prompt_tokens: 80, completion_tokens: 20 },
        model: "gpt-4",
        finish_reason: "stop",
      }),
    })),
  };
});

jest.mock("../src/services/workflowService", () => {
  return {
    WorkflowService: jest.fn().mockImplementation(() => ({
      getWorkflowInfo: jest.fn().mockResolvedValue({
        name: "test_workflow",
        description: "Test workflow",
        parameters: {},
      }),
    })),
  };
});

jest.mock("../src/services/skillService", () => {
  return {
    SkillService: jest.fn().mockImplementation(() => ({
      getSkillInfo: jest.fn().mockResolvedValue({
        name: "test_skill",
        description: "Test skill",
      }),
    })),
  };
});

// Mock other dependencies
jest.mock("../src/nlu_agents/nlu_lead_agent", () => {
  return {
    NLULeadAgent: jest.fn().mockImplementation(() => ({
      analyzeIntent: jest.fn().mockResolvedValue({
        primaryGoal: "analyze_data",
        primaryGoalConfidence: 0.92,
        extractedParameters: { data_type: "sales" },
        suggestedNextAction: {
          actionType: "invoke_skill",
          skillId: "data_analysis",
        },
      }),
    })),
  };
});

jest.mock("../src/lib/llmUtils", () => {
  return {
    RealLLMService: jest.fn().mockImplementation(() => ({
      generate: jest.fn().mockResolvedValue("Mock LLM response"),
    })),
  };
});

// Mock fs and path
jest.mock("fs", () => ({
  existsSync: jest.fn().mockReturnValue(true),
  readFileSync: jest.fn().mockReturnValue(
    JSON.stringify({
      intents: [
        {
          name: "create_task",
          description: "Create a new task",
          patterns: ["create task", "add task", "new task"],
          examples: ["create a task for tomorrow", "add a new task"],
          entities: ["task_name", "due_date"],
          action: "execute_skill",
          parameters: { skill: "task_creation" },
        },
        {
          name: "schedule_meeting",
          description: "Schedule a meeting",
          patterns: ["schedule meeting", "set up meeting", "book meeting"],
          examples: ["schedule meeting with team", "set up a meeting tomorrow"],
          entities: ["participants", "time", "date"],
          action: "execute_skill",
          parameters: { skill: "calendar_scheduling" },
        },
      ],
    }),
  ),
  writeFileSync: jest.fn(),
}));

jest.mock("path", () => ({
  join: jest.fn().mockReturnValue("/mock/path/to/config.json"),
  dirname: jest.fn().mockReturnValue("/mock/path/to"),
}));

describe("NLU Simple Integration Tests", () => {
  let NLUService;
  let NLUHybridIntegrationService;
  let nluService;
  let hybridService;

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();

    // Import services after mocks are set up
    NLUService = require("../src/services/nluService").NLUService;
    NLUHybridIntegrationService =
      require("../src/services/nluHybridIntegrationService").NLUHybridIntegrationService;

    // Create service instances
    nluService = new NLUService();
    hybridService = new NLUHybridIntegrationService(nluService);
  });

  describe("NLU Service Basic Functionality", () => {
    it("should initialize successfully", () => {
      expect(nluService).toBeInstanceOf(NLUService);
      expect(nluService.openaiService).toBeDefined();
      expect(nluService.workflowService).toBeDefined();
      expect(nluService.skillService).toBeDefined();
    });

    it("should process simple messages with rules-based approach", async () => {
      const message = "create a task for tomorrow";
      const context = {
        userId: "test-user",
        sessionId: "test-session",
        previousIntents: [],
        entities: {},
        timestamp: new Date(),
      };

      const response = await nluService.understandMessage(message, context, {
        service: "rules",
      });

      expect(response).toBeDefined();
      expect(response.intent).toBeDefined();
      expect(response.confidence).toBeGreaterThanOrEqual(0);
      expect(response.confidence).toBeLessThanOrEqual(1);
      expect(response.entities).toBeDefined();
    });

    it("should extract entities from messages", async () => {
      const message = 'create a task called "Finish report" due tomorrow';
      const context = {
        userId: "test-user",
        sessionId: "test-session",
        previousIntents: [],
        entities: {},
        timestamp: new Date(),
      };

      const response = await nluService.understandMessage(message, context, {
        service: "rules",
      });

      expect(response.entities).toBeDefined();
      expect(response.entities.task_name).toBeDefined();
      expect(response.entities.due_date).toBeDefined();
    });
  });

  describe("Hybrid Integration Service", () => {
    it("should initialize successfully", () => {
      expect(hybridService).toBeInstanceOf(NLUHybridIntegrationService);
      expect(hybridService.nluService).toBe(nluService);
    });

    it("should route simple messages to rules-based processing", async () => {
      const message = "hello there";
      const response = await hybridService.understandMessage(message);

      expect(response.providerUsed).toBe("rules");
      expect(response.complexityScore).toBeLessThan(0.3);
    });

    it("should route complex messages to AI processing", async () => {
      const message =
        "analyze sales data from last quarter and create a comprehensive report with recommendations";
      const response = await hybridService.understandMessage(message);

      expect(response.complexityScore).toBeGreaterThan(0.6);
      expect(response.intent).toBeDefined();
    });

    it("should handle batch processing", async () => {
      const messages = [
        "hello",
        "create a task",
        "analyze sales data and create report",
      ];

      const responses = await hybridService.batchProcess(messages);

      expect(responses).toHaveLength(3);
      expect(responses[0].complexityScore).toBeLessThan(0.3);
      expect(responses[2].complexityScore).toBeGreaterThan(0.6);
    });
  });

  describe("Error Handling", () => {
    it("should handle OpenAI service failures gracefully", async () => {
      // Mock OpenAI service to fail
      nluService.openaiService.chatCompletion.mockRejectedValueOnce(
        new Error("API timeout"),
      );

      const response = await nluService.understandMessage(
        "test message",
        undefined,
        {
          service: "openai",
        },
      );

      expect(response.intent).toBe("unknown");
      expect(response.confidence).toBeLessThan(0.5);
    });

    it("should fallback to rules when hybrid processing fails", async () => {
      // Mock the hybrid processing to fail
      jest
        .spyOn(nluService, "understandMessage")
        .mockRejectedValueOnce(new Error("Hybrid processing failed"));

      const message = "schedule meeting";
      const response = await hybridService.understandMessage(message);

      expect(response).toBeDefined();
      expect(response.providerUsed).toBe("rules_fallback");
    });
  });

  describe("Performance Metrics", () => {
    it("should track processing time", async () => {
      const message = "test message";
      const response = await hybridService.understandMessage(message);

      expect(response.processingTime).toBeGreaterThan(0);
      expect(response.processingTime).toBeLessThan(1000); // Should be reasonable
    });

    it("should handle concurrent requests", async () => {
      const messages = Array(5).fill("test message");

      const responses = await Promise.all(
        messages.map((msg) => hybridService.understandMessage(msg)),
      );

      expect(responses).toHaveLength(5);
      responses.forEach((response) => {
        expect(response).toBeDefined();
        expect(response.intent).toBeDefined();
      });
    });
  });
});

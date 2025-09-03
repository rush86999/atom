const { NLUService } = require("../src/services/nluService");
const {
  NLUHybridIntegrationService,
} = require("../src/services/nluHybridIntegrationService");

// Mock the required services
const mockOpenAIService = {
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
};

const mockWorkflowService = {
  getWorkflowInfo: jest.fn().mockResolvedValue({
    name: "test_workflow",
    description: "Test workflow",
    parameters: {},
  }),
};

const mockSkillService = {
  getSkillInfo: jest.fn().mockResolvedValue({
    name: "test_skill",
    description: "Test skill",
  }),
};

// Mock the constructors
jest.mock("../src/services/openaiService", () => {
  return {
    OpenAIService: jest.fn().mockImplementation(() => mockOpenAIService),
  };
});

jest.mock("../src/services/workflowService", () => {
  return {
    WorkflowService: jest.fn().mockImplementation(() => mockWorkflowService),
  };
});

jest.mock("../src/services/skillService", () => {
  return {
    SkillService: jest.fn().mockImplementation(() => mockSkillService),
  };
});

describe("NLU Minimal Integration Test", () => {
  let nluService;
  let hybridService;

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();

    // Create service instances
    nluService = new NLUService();
    hybridService = new NLUHybridIntegrationService(nluService);
  });

  test("NLU Service should be created successfully", () => {
    expect(nluService).toBeInstanceOf(NLUService);
    expect(hybridService).toBeInstanceOf(NLUHybridIntegrationService);
  });

  test("Should process simple message with rules-based approach", async () => {
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
  });

  test("Hybrid Service should route messages based on complexity", async () => {
    const simpleMessage = "hello there";
    const complexMessage = "analyze sales data and create comprehensive report";

    const simpleResponse = await hybridService.understandMessage(simpleMessage);
    const complexResponse =
      await hybridService.understandMessage(complexMessage);

    expect(simpleResponse.providerUsed).toBe("rules");
    expect(simpleResponse.complexityScore).toBeLessThan(0.3);
    expect(complexResponse.complexityScore).toBeGreaterThan(0.6);
  });

  test("Should handle batch processing", async () => {
    const messages = ["hello", "create a task", "analyze data"];

    const responses = await hybridService.batchProcess(messages);

    expect(responses).toHaveLength(3);
    responses.forEach((response) => {
      expect(response.intent).toBeDefined();
    });
  });

  test("Should handle service failures gracefully", async () => {
    // Mock OpenAI service to fail
    mockOpenAIService.chatCompletion.mockRejectedValueOnce(
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

  test("Should extract entities from messages", async () => {
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
    expect(Object.keys(response.entities).length).toBeGreaterThan(0);
  });
});

// Run the tests if this file is executed directly
if (require.main === module) {
  const jest = require("jest");
  jest.run(["--testPathPattern", __filename]);
}

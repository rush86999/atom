import {
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  jest,
} from "@jest/globals";
import { NLUService } from "../src/services/nluService";
import { NLUHybridIntegrationService } from "../src/services/nluHybridIntegrationService";
import { NLUOrchestrationIntegrationService } from "../src/services/nluOrchestrationIntegration";
import { OpenAIService } from "../src/services/openaiService";
import { WorkflowService } from "../src/services/workflowService";
import { SkillService } from "../src/services/skillService";

// Mock dependencies
jest.mock("../src/services/openaiService");
jest.mock("../src/services/workflowService");
jest.mock("../src/services/skillService");

describe("NLU System Integration Tests", () => {
  let nluService: NLUService;
  let hybridService: NLUHybridIntegrationService;
  let orchestrationService: NLUOrchestrationIntegrationService;
  let mockOpenAIService: jest.Mocked<OpenAIService>;
  let mockWorkflowService: jest.Mocked<WorkflowService>;
  let mockSkillService: jest.Mocked<SkillService>;

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();

    // Setup mock implementations
    mockOpenAIService = {
      chatCompletion: jest.fn().mockResolvedValue(
        JSON.stringify({
          intent: "test_intent",
          confidence: 0.9,
          entities: { test: "value" },
          action: "test_action",
          parameters: { test: "value" },
        }),
      ),
    } as any;

    mockWorkflowService = {
      getWorkflowInfo: jest.fn().mockResolvedValue({
        name: "test_workflow",
        description: "Test workflow",
        parameters: {},
      }),
    } as any;

    mockSkillService = {
      getSkillInfo: jest.fn().mockResolvedValue({
        name: "test_skill",
        description: "Test skill",
      }),
    } as any;

    // Mock the constructors
    (OpenAIService as jest.Mock).mockImplementation(() => mockOpenAIService);
    (WorkflowService as jest.Mock).mockImplementation(
      () => mockWorkflowService,
    );
    (SkillService as jest.Mock).mockImplementation(() => mockSkillService);

    // Create service instances
    nluService = new NLUService();
    hybridService = new NLUHybridIntegrationService(nluService);
    orchestrationService = new NLUOrchestrationIntegrationService(
      hybridService,
    );
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe("NLU Service Integration", () => {
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

    it("should process complex messages with AI service", async () => {
      const message =
        "analyze sales data from last quarter and create a report";
      const context = {
        userId: "test-user",
        sessionId: "test-session",
        previousIntents: [],
        entities: {},
        timestamp: new Date(),
      };

      const response = await nluService.understandMessage(message, context, {
        service: "openai",
      });

      expect(response).toBeDefined();
      expect(response.intent).toBe("test_intent");
      expect(response.confidence).toBe(0.9);
      expect(mockOpenAIService.chatCompletion).toHaveBeenCalled();
    });

    it("should extract entities correctly", async () => {
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
    it("should route simple messages to rules-based processing", async () => {
      const message = "hello there";

      const response = await hybridService.understandMessage(message);

      expect(response.providerUsed).toBe("rules");
      expect(response.complexityScore).toBeLessThan(0.3);
    });

    it("should route medium complexity messages to hybrid processing", async () => {
      const message = "schedule meeting with team tomorrow at 3pm";

      const response = await hybridService.understandMessage(message);

      expect(response.providerUsed).toBe("hybrid");
      expect(response.complexityScore).toBeGreaterThanOrEqual(0.3);
      expect(response.complexityScore).toBeLessThan(0.6);
    });

    it("should handle batch processing correctly", async () => {
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

  describe("Error Handling and Recovery", () => {
    it("should handle OpenAI service failures gracefully", async () => {
      mockOpenAIService.chatCompletion.mockRejectedValueOnce(
        new Error("API timeout"),
      );

      const message = "analyze complex data";
      const response = await nluService.understandMessage(message, undefined, {
        service: "openai",
      });

      expect(response).toBeDefined();
      expect(response.intent).toBe("unknown");
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

  describe("Performance and Metrics", () => {
    it("should track processing time metrics", async () => {
      const message = "test message";

      const response = await hybridService.understandMessage(message);

      expect(response.processingTime).toBeGreaterThan(0);
      expect(response.processingTime).toBeLessThan(1000); // Should be reasonable
    });

    it("should handle concurrent requests", async () => {
      const messages = Array(10).fill("test message");

      const responses = await Promise.all(
        messages.map((msg) => hybridService.understandMessage(msg)),
      );

      expect(responses).toHaveLength(10);
      responses.forEach((response) => {
        expect(response).toBeDefined();
        expect(response.intent).toBeDefined();
      });
    });
  });
});

import { NLUHybridIntegrationService } from "./nluHybridIntegrationService";
import { NLUService } from "./nluService";
import { hybridLLMService } from "./hybridLLMService";
import { jest } from "@jest/globals";

// Mock dependencies
jest.mock("./nluService");
jest.mock("./hybridLLMService");
jest.mock("./openaiService");
jest.mock("./workflowService");
jest.mock("./skillService");

describe("NLU Llama.cpp Integration", () => {
  let nluHybridService: NLUHybridIntegrationService;
  let mockNLUService: jest.Mocked<NLUService>;
  let mockHybridLLMService: jest.Mocked<typeof hybridLLMService>;

  beforeEach(() => {
    jest.clearAllMocks();

    mockNLUService = {
      understandMessage: jest.fn(),
    } as any;

    mockHybridLLMService = {
      generate: jest.fn(),
      getStatus: jest.fn(),
      stop: jest.fn(),
      clearCache: jest.fn(),
      on: jest.fn(),
      off: jest.fn(),
    } as any;

    (hybridLLMService as any) = mockHybridLLMService;

    nluHybridService = new NLUHybridIntegrationService(mockNLUService);
  });

  describe("Llama.cpp Integration", () => {
    it("should use llama.cpp for medium complexity messages", async () => {
      // Mock rules-based NLU result
      mockNLUService.understandMessage.mockResolvedValue({
        intent: "greeting",
        confidence: 0.8,
        entities: {},
        action: "respond",
        parameters: {},
        requiresConfirmation: false,
        suggestedResponses: ["Hello!"],
      });

      // Mock llama.cpp enhancement
      mockHybridLLMService.generate.mockResolvedValue({
        content: JSON.stringify({
          intent: "greeting",
          confidence: 0.9,
          entities: { name: "User" },
          action: "respond_with_welcome",
          requiresConfirmation: false,
          suggestedResponses: ["Hello! How can I help you today?"],
        }),
        tokens: { input: 50, output: 30 },
        cost: 0,
        model: "llama-3-8b-instruct",
        provider: "llama.cpp-local",
      });

      const result = await nluHybridService.understandMessage(
        "Hello there, my name is John and I need help with my project",
        { userId: "test-user" },
      );

      expect(result.providerUsed).toBe("llama-hybrid");
      expect(result.confidence).toBeGreaterThan(0.8);
      expect(mockHybridLLMService.generate).toHaveBeenCalled();
    });

    it("should fallback to llama.cpp when rules-based processing fails", async () => {
      mockNLUService.understandMessage.mockRejectedValue(
        new Error("Rules-based processing failed"),
      );

      mockHybridLLMService.generate.mockResolvedValue({
        content: JSON.stringify({
          intent: "help_request",
          confidence: 0.7,
          entities: { topic: "project" },
          action: "provide_assistance",
          requiresConfirmation: false,
          suggestedResponses: ["I can help you with your project."],
        }),
        tokens: { input: 40, output: 25 },
        cost: 0,
        model: "llama-3-8b-instruct",
        provider: "llama.cpp-local",
      });

      const result = await nluHybridService.understandMessage(
        "I need help with my coding project",
        { userId: "test-user" },
      );

      expect(result.providerUsed).toBe("llama");
      expect(result.intent).toBe("help_request");
      expect(mockHybridLLMService.generate).toHaveBeenCalled();
    });

    it("should handle llama.cpp JSON parsing errors gracefully", async () => {
      mockNLUService.understandMessage.mockRejectedValue(
        new Error("Rules-based processing failed"),
      );

      mockHybridLLMService.generate.mockResolvedValue({
        content: "Invalid JSON response",
        tokens: { input: 40, output: 25 },
        cost: 0,
        model: "llama-3-8b-instruct",
        provider: "llama.cpp-local",
      });

      const mockOpenAIService = { generate: jest.fn() };
      (nluHybridService as any).openaiService = mockOpenAIService;
      mockOpenAIService.generate.mockResolvedValue({
        intent: "help_request",
        confidence: 0.7,
        entities: {},
        action: "respond",
        parameters: {},
        requiresConfirmation: false,
        suggestedResponses: ["I can help you."],
      });

      const result = await nluHybridService.understandMessage(
        "I need help with my project",
      );

      expect(result.providerUsed).toBe("ai");
    });

    it("should respect useLlamaCPP configuration", async () => {
      nluHybridService.updateConfig({ useLlamaCPP: false });

      mockNLUService.understandMessage.mockResolvedValue({
        intent: "greeting",
        confidence: 0.8,
        entities: {},
        action: "respond",
        parameters: {},
        requiresConfirmation: false,
        suggestedResponses: ["Hello!"],
      });

      await nluHybridService.understandMessage(
        "Hello there, this should use AI enhancement instead of llama.cpp",
      );

      expect(mockHybridLLMService.generate).not.toHaveBeenCalled();
    });

    it("should use appropriate temperature for llama.cpp NLU tasks", async () => {
      mockNLUService.understandMessage.mockResolvedValue({
        intent: "greeting",
        confidence: 0.8,
        entities: {},
        action: "respond",
        parameters: {},
        requiresConfirmation: false,
        suggestedResponses: ["Hello!"],
      });

      mockHybridLLMService.generate.mockResolvedValue({
        content: JSON.stringify({
          intent: "greeting",
          confidence: 0.9,
          entities: {},
          action: "respond",
          requiresConfirmation: false,
          suggestedResponses: ["Hello!"],
        }),
        tokens: { input: 50, output: 30 },
        cost: 0,
        model: "llama-3-8b-instruct",
        provider: "llama.cpp-local",
      });

      await nluHybridService.understandMessage("Hello there");

      const generateCall = mockHybridLLMService.generate.mock.calls[0];
      const options = generateCall[2];
      expect(options?.temperature).toBe(0.3);
    });
  });

  describe("Complexity-based Routing", () => {
    it("should route simple messages to rules-based processing", async () => {
      const simpleMessage = "Hello";

      mockNLUService.understandMessage.mockResolvedValue({
        intent: "greeting",
        confidence: 0.9,
        entities: {},
        action: "respond",
        parameters: {},
        requiresConfirmation: false,
        suggestedResponses: ["Hi!"],
      });

      const result = await nluHybridService.understandMessage(simpleMessage);

      expect(result.providerUsed).toBe("rules");
      expect(mockHybridLLMService.generate).not.toHaveBeenCalled();
    });

    it("should route very complex messages to cloud AI instead of llama.cpp", async () => {
      const complexMessage =
        "Analyze my Q3 financial reports and compare them with last year's performance, then create a summary presentation with recommendations for next quarter";

      mockNLUService.understandMessage.mockResolvedValue({
        intent: "financial_analysis",
        confidence: 0.6,
        entities: { period: "Q3", comparison: "last year" },
        action: "analyze",
        parameters: {},
        requiresConfirmation: true,
        suggestedResponses: ["I can help analyze your financial reports."],
      });

      const mockOpenAIService = { generate: jest.fn() };
      (nluHybridService as any).openaiService = mockOpenAIService;
      mockOpenAIService.generate.mockResolvedValue({
        intent: "financial_analysis",
        confidence: 0.8,
        entities: {
          period: "Q3",
          comparison: "last year",
          action: "create_summary",
          output: "presentation",
        },
        action: "analyze_and_summarize",
        parameters: {},
        requiresConfirmation: true,
        suggestedResponses: [
          "I'll analyze your Q3 reports and create a comparison presentation.",
        ],
      });

      const result = await nluHybridService.understandMessage(complexMessage);

      expect(result.providerUsed).toBe("hybrid");
      expect(result.confidence).toBeGreaterThan(0.6);
    });
  });

  describe("Configuration", () => {
    it("should adjust llamaCPPThreshold configuration", async () => {
      nluHybridService.updateConfig({ llamaCPPThreshold: 0.7 });

      mockNLUService.understandMessage.mockResolvedValue({
        intent: "greeting",
        confidence: 0.8,
        entities: {},
        action: "respond",
        parameters: {},
        requiresConfirmation: false,
        suggestedResponses: ["Hello!"],
      });

      mockHybridLLMService.generate.mockResolvedValue({
        content: JSON.stringify({
          intent: "greeting",
          confidence: 0.9,
          entities: {},
          action: "respond",
          requiresConfirmation: false,
          suggestedResponses: ["Hello!"],
        }),
        tokens: { input: 50, output: 30 },
        cost: 0,
        model: "llama-3-8b-instruct",
        provider: "llama.cpp-local",
      });

      await nluHybridService.understandMessage(
        "Hello there, this is a moderately complex message",
      );

      expect(mockHybridLLMService.generate).toHaveBeenCalled();
    });
  });
});

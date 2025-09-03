const { NLUService } = require("../src/services/nluService");
const {
  NLUHybridIntegrationService,
} = require("../src/services/nluHybridIntegrationService");
const {
  NLUOrchestrationIntegrationService,
} = require("../src/services/nluOrchestrationIntegration");

class NLUIntegrationRunner {
  constructor() {
    this.tests = [];
    this.passed = 0;
    this.failed = 0;
    this.startTime = Date.now();
  }

  addTest(name, testFunction) {
    this.tests.push({ name, testFunction });
  }

  async runTests() {
    console.log("🚀 Starting NLU Integration Tests\n");
    console.log("═".repeat(50));

    // Initialize services
    const nluService = new NLUService();
    const hybridService = new NLUHybridIntegrationService(nluService);
    const orchestrationService = new NLUOrchestrationIntegrationService(
      hybridService,
    );

    for (const test of this.tests) {
      try {
        console.log(`🧪 Running: ${test.name}`);
        await test.testFunction(
          nluService,
          hybridService,
          orchestrationService,
        );
        console.log("✅ PASSED\n");
        this.passed++;
      } catch (error) {
        console.log("❌ FAILED");
        console.log(`   Error: ${error.message}\n`);
        this.failed++;
      }
    }

    this.printSummary();
  }

  printSummary() {
    const duration = Date.now() - this.startTime;
    console.log("═".repeat(50));
    console.log("📊 Test Summary:");
    console.log(`✅ Passed: ${this.passed}`);
    console.log(`❌ Failed: ${this.failed}`);
    console.log(`📈 Total: ${this.tests.length}`);
    console.log(`⏱️  Duration: ${duration}ms`);
    console.log("═".repeat(50));

    if (this.failed === 0) {
      console.log("🎉 All tests passed!");
    } else {
      console.log("💥 Some tests failed. Check the errors above.");
      process.exit(1);
    }
  }
}

// Create test runner
const runner = new NLUIntegrationRunner();

// Add tests
runner.addTest(
  "NLU Service - Simple Message Processing",
  async (nluService) => {
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

    if (!response) throw new Error("No response received");
    if (!response.intent) throw new Error("No intent detected");
    if (typeof response.confidence !== "number")
      throw new Error("Invalid confidence score");
  },
);

runner.addTest(
  "Hybrid Service - Message Routing",
  async (nluService, hybridService) => {
    const simpleMessage = "hello there";
    const complexMessage = "analyze sales data and create comprehensive report";

    const simpleResponse = await hybridService.understandMessage(simpleMessage);
    const complexResponse =
      await hybridService.understandMessage(complexMessage);

    if (simpleResponse.complexityScore >= 0.3) {
      throw new Error("Simple message should have low complexity");
    }
    if (complexResponse.complexityScore <= 0.6) {
      throw new Error("Complex message should have high complexity");
    }
  },
);

runner.addTest("Error Handling - Service Failures", async (nluService) => {
  // Mock OpenAI service failure
  const originalChatCompletion = nluService.openaiService.chatCompletion;
  nluService.openaiService.chatCompletion = async () => {
    throw new Error("API timeout");
  };

  try {
    const response = await nluService.understandMessage(
      "test message",
      undefined,
      {
        service: "openai",
      },
    );

    if (response.intent !== "unknown") {
      throw new Error("Should fallback to unknown intent on failure");
    }
  } finally {
    // Restore original method
    nluService.openaiService.chatCompletion = originalChatCompletion;
  }
});

runner.addTest("Batch Processing", async (nluService, hybridService) => {
  const messages = [
    "hello",
    "create a task",
    "analyze sales data and create report",
  ];

  const responses = await hybridService.batchProcess(messages);

  if (responses.length !== 3) {
    throw new Error(`Expected 3 responses, got ${responses.length}`);
  }

  responses.forEach((response, index) => {
    if (!response.intent) {
      throw new Error(`Response ${index} has no intent`);
    }
  });
});

runner.addTest("Entity Extraction", async (nluService) => {
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

  if (!response.entities || Object.keys(response.entities).length === 0) {
    throw new Error("No entities extracted");
  }
});

// Run tests
runner.runTests().catch((error) => {
  console.error("💥 Test runner failed:", error);
  process.exit(1);
});

module.exports = NLUIntegrationRunner;

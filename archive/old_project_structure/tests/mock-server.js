/**
 * Mock Server for Atom AI Integration Testing
 * Provides mock endpoints for all required API routes
 * Simulates real backend behavior for comprehensive testing
 */

const express = require("express");
const cors = require("cors");
const path = require("path");

class MockServer {
  constructor(port = 3000) {
    this.port = port;
    this.app = express();
    this.server = null;
    this.setupMiddleware();
    this.setupRoutes();
  }

  setupMiddleware() {
    this.app.use(cors());
    this.app.use(express.json());
    this.app.use(express.static(path.join(__dirname, "..", "public")));
  }

  setupRoutes() {
    // Health endpoints
    this.app.get("/api/health", (req, res) => {
      res.json({
        status: "healthy",
        timestamp: new Date().toISOString(),
        version: "1.0.0",
        services: ["auth", "database", "workflows", "budgets"],
      });
    });

    this.app.get("/api/health/db", (req, res) => {
      res.json({
        connected: true,
        database: "postgresql",
        version: "14.5",
        timestamp: new Date().toISOString(),
      });
    });

    this.app.post("/api/health/db", (req, res) => {
      res.json({
        connected: true,
        database: "postgresql",
        version: "14.5",
        timestamp: new Date().toISOString(),
      });
    });

    this.app.get("/api/auth/health", (req, res) => {
      res.json({
        status: "ok",
        providers: ["google", "linkedin"],
        authenticated: false,
      });
    });

    // Authentication endpoints
    this.app.post("/api/auth/signup", (req, res) => {
      const { email, password, name, persona } = req.body;

      if (!email || !password || !name || !persona) {
        return res.status(400).json({
          error: {
            message: "Missing required fields: email, password, name, persona",
            code: "VALIDATION_ERROR",
          },
        });
      }

      res.json({
        success: true,
        userId: `user-${Date.now()}`,
        token: `mock-jwt-token-${Date.now()}`,
        user: {
          email,
          name,
          persona,
          createdAt: new Date().toISOString(),
        },
      });
    });

    this.app.post("/api/auth/login", (req, res) => {
      const { email, password } = req.body;

      if (!email || !password) {
        return res.status(400).json({
          error: {
            message: "Email and password are required",
            code: "VALIDATION_ERROR",
          },
        });
      }

      res.json({
        success: true,
        token: `mock-jwt-token-${Date.now()}`,
        user: {
          email,
          name: email.split("@")[0],
          persona: "alex",
          createdAt: new Date().toISOString(),
        },
      });
    });

    // Onboarding endpoints
    this.app.post("/api/onboarding", (req, res) => {
      const { jobTitle, companySize, goals } = req.body;

      res.json({
        completed: true,
        profile: {
          jobTitle: jobTitle || "Software Engineer",
          companySize: companySize || "medium",
          goals: goals || ["productivity", "automation"],
          completedAt: new Date().toISOString(),
        },
      });
    });

    this.app.post("/api/financial-setup", (req, res) => {
      const { monthlyIncome, monthlyExpenses, savingsGoal, riskTolerance } =
        req.body;

      res.json({
        planCreated: true,
        financialPlan: {
          monthlyIncome: monthlyIncome || 8000,
          monthlyExpenses: monthlyExpenses || 4000,
          savingsGoal: savingsGoal || "emergency-fund",
          riskTolerance: riskTolerance || "moderate",
          recommendedBudget: 3000,
          createdAt: new Date().toISOString(),
        },
      });
    });

    this.app.post("/api/business-setup", (req, res) => {
      const { businessName, businessType, revenue, clients, automationNeeds } =
        req.body;

      res.json({
        setupComplete: true,
        businessProfile: {
          businessName: businessName || "TechStartup LLC",
          businessType: businessType || "technology",
          revenue: revenue || 120000,
          clients: clients || 5,
          automationNeeds: automationNeeds || [
            "client-communication",
            "project-management",
          ],
          createdAt: new Date().toISOString(),
        },
      });
    });

    // Workflow endpoints
    this.app.post("/api/workflows", (req, res) => {
      const { name, description, triggers, actions, type } = req.body;

      if (!name) {
        return res.status(400).json({
          error: {
            message: "Workflow name is required",
            code: "VALIDATION_ERROR",
          },
        });
      }

      res.json({
        success: true,
        workflowId: `workflow-${Date.now()}`,
        workflow: {
          id: `workflow-${Date.now()}`,
          name,
          description: description || "Automated workflow",
          triggers: triggers || ["daily"],
          actions: actions || ["create-task"],
          type: type || "productivity",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });
    });

    this.app.get("/api/workflows", (req, res) => {
      res.json({
        success: true,
        workflows: [
          {
            id: "workflow-1",
            name: "Daily Productivity",
            description: "Automates daily tasks and reminders",
            triggers: ["daily-9am"],
            actions: ["check-calendar", "create-tasks"],
            type: "productivity",
            createdAt: "2024-01-01T00:00:00Z",
          },
          {
            id: "workflow-2",
            name: "Budget Tracking",
            description: "Tracks monthly expenses and savings",
            triggers: ["monthly-1st"],
            actions: ["analyze-spending", "update-budget"],
            type: "financial",
            createdAt: "2024-01-02T00:00:00Z",
          },
        ],
      });
    });

    this.app.get("/api/workflows/:id", (req, res) => {
      const { id } = req.params;

      res.json({
        success: true,
        workflow: {
          id,
          name: "Sample Workflow",
          description: "A sample workflow for testing",
          triggers: ["manual"],
          actions: ["test-action"],
          type: "test",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      });
    });

    // Budget endpoints
    this.app.post("/api/budgets", (req, res) => {
      const { name, amount, categories, alerts, alertThreshold } = req.body;

      if (!name || !amount) {
        return res.status(400).json({
          error: {
            message: "Budget name and amount are required",
            code: "VALIDATION_ERROR",
          },
        });
      }

      res.json({
        success: true,
        budgetId: `budget-${Date.now()}`,
        budget: {
          id: `budget-${Date.now()}`,
          name,
          amount,
          categories: categories || ["general"],
          alerts: alerts !== undefined ? alerts : true,
          alertThreshold: alertThreshold || 0.8,
          createdAt: new Date().toISOString(),
        },
      });
    });

    this.app.get("/api/budgets", (req, res) => {
      res.json({
        success: true,
        budgets: [
          {
            id: "budget-1",
            name: "Monthly Essentials",
            amount: 3000,
            categories: ["food", "transport", "utilities"],
            alerts: true,
            alertThreshold: 0.8,
            createdAt: "2024-01-01T00:00:00Z",
          },
        ],
      });
    });

    // Automation endpoints
    this.app.post("/api/automation/workflows", (req, res) => {
      const { name, description, triggers, actions, conditions } = req.body;

      res.json({
        success: true,
        workflowId: `automation-${Date.now()}`,
        workflow: {
          id: `automation-${Date.now()}`,
          name,
          description: description || "Business automation workflow",
          triggers: triggers || ["new-client"],
          actions: actions || ["send-email"],
          conditions: conditions || [],
          createdAt: new Date().toISOString(),
        },
      });
    });

    // Analytics endpoints
    this.app.get("/api/analytics/workflows", (req, res) => {
      res.json({
        workflows: [
          {
            id: "workflow-1",
            name: "Daily Productivity",
            runs: 45,
            successRate: 95,
            lastRun: "2024-01-15T10:30:00Z",
            averageDuration: "2.5s",
          },
          {
            id: "workflow-2",
            name: "Budget Tracking",
            runs: 12,
            successRate: 100,
            lastRun: "2024-01-14T09:15:00Z",
            averageDuration: "1.8s",
          },
        ],
      });
    });

    this.app.post("/api/analytics/spending", (req, res) => {
      const { month, categories, amount } = req.body;

      res.json({
        analysis: {
          month: month || "2024-01",
          totalSpent: amount || 1500,
          categories: categories || ["dining", "entertainment"],
          recommendations: [
            "Reduce dining expenses by 20%",
            "Consider meal planning to save on food costs",
            "Set up automatic savings transfers",
          ],
          comparison: {
            previousMonth: 1400,
            average: 1600,
            trend: "stable",
          },
        },
      });
    });

    // Meeting preparation endpoint
    this.app.post("/api/meetings/prep", (req, res) => {
      const { title, attendees, duration, autoPrep } = req.body;

      res.json({
        prepared: true,
        meeting: {
          title: title || "Team Meeting",
          attendees: attendees || 5,
          duration: duration || 60,
          autoPrep: autoPrep !== undefined ? autoPrep : true,
          agenda: [
            "Project updates",
            "Blockers discussion",
            "Action items review",
          ],
          preparedAt: new Date().toISOString(),
        },
      });
    });

    // Goals endpoints
    this.app.post("/api/goals/savings", (req, res) => {
      const { emergencyFund, retirement, shortTermGoals, monthlyContribution } =
        req.body;

      res.json({
        goalsSet: true,
        savingsPlan: {
          emergencyFund: emergencyFund || 10000,
          retirement: retirement || 500000,
          shortTermGoals: shortTermGoals || ["vacation", "new-laptop"],
          monthlyContribution: monthlyContribution || 1000,
          timeline: "5 years",
          confidence: "high",
          createdAt: new Date().toISOString(),
        },
      });
    });

    // Project endpoints
    this.app.post("/api/projects/timeline", (req, res) => {
      const { name, deadline, milestones, client } = req.body;

      res.json({
        timelineCreated: true,
        project: {
          name: name || "Website Redesign",
          deadline: deadline || "2024-03-15",
          milestones: milestones || [
            { name: "Design Approval", date: "2024-02-15" },
            { name: "Development Complete", date: "2024-03-01" },
          ],
          client: client || "Acme Corp",
          status: "planned",
          createdAt: new Date().toISOString(),
        },
      });
    });

    // Reports endpoint
    this.app.post("/api/reports/business", (req, res) => {
      const { period, metrics, format } = req.body;

      res.json({
        report: {
          period: period || "last-quarter",
          metrics: metrics || ["revenue", "clients", "projects"],
          format: format || "detailed",
          summary: {
            revenue: 45000,
            clients: 8,
            projects: 12,
            profitability: 35,
            growth: 15,
          },
          generatedAt: new Date().toISOString(),
        },
      });
    });

    // Catch-all for undefined routes
    this.app.all("*", (req, res) => {
      res.status(404).json({
        error: {
          message: `Endpoint ${req.method} ${req.path} not found`,
          code: "ENDPOINT_NOT_FOUND",
        },
      });
    });
  }

  start() {
    return new Promise((resolve, reject) => {
      this.server = this.app.listen(this.port, (err) => {
        if (err) {
          reject(err);
        } else {
          console.log(`🚀 Mock server running on port ${this.port}`);
          console.log(
            `📊 Health check: http://localhost:${this.port}/api/health`,
          );
          resolve();
        }
      });
    });
  }

  stop() {
    return new Promise((resolve, reject) => {
      if (this.server) {
        this.server.close((err) => {
          if (err) {
            reject(err);
          } else {
            console.log("🛑 Mock server stopped");
            resolve();
          }
        });
      } else {
        resolve();
      }
    });
  }
}

// Export for use in tests
module.exports = MockServer;

// Start server if run directly
if (require.main === module) {
  const server = new MockServer();
  server.start().catch(console.error);

  // Graceful shutdown
  process.on("SIGINT", async () => {
    console.log("\n🛑 Shutting down mock server...");
    await server.stop();
    process.exit(0);
  });
}

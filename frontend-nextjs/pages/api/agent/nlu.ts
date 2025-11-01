import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../../lib/auth";

// Mock NLU service - replace with actual NLU service integration
async function understandMessage(
  message: string,
  context?: any,
  options?: any,
): Promise<any> {
  // Simple intent detection for demo purposes
  const intents = {
    workflow: ["create workflow", "automate", "when", "if", "schedule"],
    search: ["search", "find", "look for", "where is"],
    task: ["create task", "todo", "remind me", "task"],
    calendar: ["schedule", "meeting", "event", "calendar"],
    communication: ["message", "email", "send", "notify"],
  };

  const messageLower = message.toLowerCase();

  // Detect primary intent
  let primaryIntent = "general";
  let confidence = 0.3;

  for (const [intent, phrases] of Object.entries(intents)) {
    if (phrases.some((phrase) => messageLower.includes(phrase))) {
      primaryIntent = intent;
      confidence = 0.8;
      break;
    }
  }

  // Extract basic entities
  const entities = {
    service: extractService(messageLower),
    action: extractAction(messageLower),
    time: extractTime(messageLower),
    subject: extractSubject(message),
  };

  return {
    primaryGoal: primaryIntent,
    primaryGoalConfidence: confidence,
    extractedParameters: entities,
    rawSubAgentResponses: {
      workflow: {
        isWorkflowRequest: primaryIntent === "workflow",
        trigger:
          primaryIntent === "workflow"
            ? {
                service: entities.service,
                event: "user_request",
              }
            : null,
        actions:
          primaryIntent === "workflow"
            ? [
                {
                  service: entities.service,
                  action: entities.action,
                  parameters: entities,
                },
              ]
            : [],
      },
    },
    confidence: confidence,
    timestamp: new Date().toISOString(),
  };
}

// Helper functions for entity extraction
function extractService(text: string): string {
  const services = [
    "gmail",
    "email",
    "outlook",
    "notion",
    "asana",
    "trello",
    "calendar",
    "google calendar",
    "outlook calendar",
    "slack",
    "teams",
    "discord",
    "drive",
    "dropbox",
    "github",
  ];

  const found = services.find((service) => text.includes(service));
  return found || "general";
}

function extractAction(text: string): string {
  if (text.includes("create") || text.includes("make")) return "create";
  if (text.includes("send")) return "send";
  if (text.includes("search") || text.includes("find")) return "search";
  if (text.includes("schedule")) return "schedule";
  if (text.includes("update")) return "update";
  if (text.includes("delete") || text.includes("remove")) return "delete";
  return "process";
}

function extractTime(text: string): string | null {
  const timePatterns = [
    /\b(\d{1,2}:\d{2}\s*(?:am|pm)?)\b/i,
    /\b(today|tomorrow|yesterday)\b/i,
    /\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i,
    /\b(\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4}?)\b/i,
  ];

  for (const pattern of timePatterns) {
    const match = text.match(pattern);
    if (match) return match[1];
  }
  return null;
}

function extractSubject(text: string): string {
  // Simple subject extraction - in production, use proper NLP
  const words = text.split(" ").slice(0, 5).join(" ");
  return words.length > 20 ? words.substring(0, 20) + "..." : words;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Check authentication using NextAuth
  const session = await getServerSession(req, res, authOptions);

  if (!session) {
    return res.status(401).json({ message: "Unauthorized - Please sign in" });
  }

  if (req.method === "POST") {
    const { message } = req.body;

    if (!message || typeof message !== "string") {
      return res.status(400).json({
        message: "Message is required and must be a string",
        user: session.user.email,
      });
    }

    try {
      // Process the message with NLU service
      const nluResponse = await understandMessage(
        message,
        { userId: session.user.id, email: session.user.email },
        { service: "demo", apiKey: "demo-key" },
      );

      // Add user context to response
      const responseWithContext = {
        ...nluResponse,
        userContext: {
          userId: session.user.id,
          email: session.user.email,
          timestamp: new Date().toISOString(),
        },
      };

      return res.status(200).json(responseWithContext);
    } catch (error) {
      console.error("Error in NLU service:", error);
      return res.status(500).json({
        message: "Failed to process message with NLU service",
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  } else {
    res.setHeader("Allow", ["POST"]);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}

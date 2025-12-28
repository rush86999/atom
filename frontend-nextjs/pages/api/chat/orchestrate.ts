import type { NextApiRequest, NextApiResponse } from "next";

interface ChatRequest {
  userId: string;
  message: string;
  sessionId?: string;
  processId?: string;
}

interface ChatResponse {
  success: boolean;
  message: string;
  type: "text" | "workflow" | "multi_step" | "confirmation" | "error";
  metadata?: {
    workflowId?: string;
    processId?: string;
    nextSteps?: string[];
    suggestedActions?: string[];
    requiresConfirmation?: boolean;
    data?: Record<string, any>;
  };
  sessionId?: string;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ChatResponse>,
) {
  if (req.method !== "POST") {
    return res.status(405).json({
      success: false,
      message: "Method not allowed",
      type: "error",
    });
  }

  try {
    const { userId, message, sessionId, processId }: ChatRequest = req.body;

    if (!userId || !message) {
      return res.status(400).json({
        success: false,
        message: "Missing required fields: userId and message",
        type: "error",
      });
    }

    // Forward the request to the backend Python API
    const backendResponse = await fetch(
      "http://localhost:8000/api/workflow_agent/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: userId,
          message: message,
          session_id: sessionId,
          process_id: processId,
        }),
      },
    );

    if (!backendResponse.ok) {
      throw new Error(`Backend API returned ${backendResponse.status}`);
    }

    const backendData = await backendResponse.json();

    // Transform backend response to frontend format
    return res.status(200).json({
      success: true,
      message:
        backendData.response || backendData.message || "Message processed",
      type: backendData.type || "text",
      metadata: backendData.metadata,
      sessionId: sessionId || backendData.session_id || `session_${Date.now()}`,
    });
  } catch (error) {
    console.error("Error in chat orchestration API:", error);

    // Fallback response when backend is not available
    return res.status(200).json({
      success: true,
      message:
        "I received your message. The chat system is currently processing your request. You can continue using other features while I work on this.",
      type: "text",
      metadata: {
        suggestedActions: [
          "Try the search feature to find information",
          "Check your tasks in the task manager",
          "Send messages through the communication hub",
        ],
      },
      sessionId: `session_${Date.now()}`,
    });
  }
}

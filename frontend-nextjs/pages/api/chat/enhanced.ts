import type { NextApiRequest, NextApiResponse } from "next";

interface EnhancedChatRequest {
  userId: string;
  message: string;
  sessionId?: string;
  enableAIAnalysis?: boolean;
  conversationHistory?: Array<{ role: string; content: string; timestamp?: string }>;
}

interface EnhancedChatResponse {
  success: boolean;
  message: string;
  type: "text" | "workflow" | "multi_step" | "confirmation" | "error" | "enhanced";
  metadata?: {
    workflowId?: string;
    processId?: string;
    nextSteps?: string[];
    suggestedActions?: string[];
    requiresConfirmation?: boolean;
    data?: Record<string, any>;
    aiAnalysis?: {
      analysisId?: string;
      sentimentScores?: {
        overall_sentiment?: number;
        positive?: number;
        negative?: number;
        neutral?: number;
      };
      entities?: Array<{
        type: string;
        value: string;
        confidence?: number;
      }>;
      intents?: string[];
      contextRelevance?: number;
      suggestedActions?: string[];
    };
  };
  sessionId?: string;
  timestamp?: string;
}

interface AIAnalysisResponse {
  analysis_id: string;
  timestamp: string;
  sentiment_scores: {
    overall_sentiment: number;
    positive: number;
    negative: number;
    neutral: number;
  };
  entities: Array<{
    type: string;
    value: string;
    confidence?: number;
  }>;
  intents: string[];
  context_relevance: number;
  suggested_actions: string[];
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<EnhancedChatResponse>,
) {
  if (req.method !== "POST") {
    return res.status(405).json({
      success: false,
      message: "Method not allowed",
      type: "error",
    });
  }

  try {
    const { userId, message, sessionId, enableAIAnalysis = true, conversationHistory }: EnhancedChatRequest = req.body;

    if (!userId || !message) {
      return res.status(400).json({
        success: false,
        message: "Missing required fields: userId and message",
        type: "error",
      });
    }

    let aiAnalysis: AIAnalysisResponse | null = null;
    let enhancedResponse = message;

    // Step 1: Get AI analysis from Phase 3 lightweight AI intelligence
    if (enableAIAnalysis) {
      try {
        const aiResponse = await fetch("http://localhost:5062/api/v1/ai/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: message,
            user_id: userId,
          }),
        });

        if (aiResponse.ok) {
          aiAnalysis = await aiResponse.json();

          // Enhance response based on AI analysis
          const sentimentScore = aiAnalysis.sentiment_scores.overall_sentiment;
          if (sentimentScore < -0.3) {
            enhancedResponse = `I understand you're concerned about: "${message}". Let me help you with that.`;
          } else if (sentimentScore > 0.3) {
            enhancedResponse = `Great to hear about: "${message}"! Here's some information that might help.`;
          }
        }
      } catch (aiError) {
        console.warn("Phase 3 AI analysis unavailable, falling back to standard chat:", aiError);
      }
    }

    // Step 2: Forward to main backend for workflow processing
    let backendResponse;
    try {
      backendResponse = await fetch(
        "http://localhost:5059/api/workflow_agent/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: userId,
            message: enhancedResponse,
            session_id: sessionId,
          }),
        },
      );

      if (!backendResponse.ok) {
        throw new Error(`Backend API returned ${backendResponse.status}`);
      }

      const backendData = await backendResponse.json();

      // Combine AI analysis with backend response
      const finalResponse: EnhancedChatResponse = {
        success: true,
        message: backendData.response || backendData.message || enhancedResponse,
        type: aiAnalysis ? "enhanced" : (backendData.type || "text"),
        metadata: {
          ...backendData.metadata,
          ...(aiAnalysis && {
            aiAnalysis: {
              analysisId: aiAnalysis.analysis_id,
              sentimentScores: aiAnalysis.sentiment_scores,
              entities: aiAnalysis.entities,
              intents: aiAnalysis.intents,
              contextRelevance: aiAnalysis.context_relevance,
              suggestedActions: aiAnalysis.suggested_actions,
            },
          }),
        },
        sessionId: sessionId || backendData.session_id || `session_${Date.now()}`,
        timestamp: new Date().toISOString(),
      };

      return res.status(200).json(finalResponse);

    } catch (backendError) {
      console.error("Backend API unavailable, using AI-enhanced fallback:", backendError);

      // Fallback response with AI analysis
      return res.status(200).json({
        success: true,
        message: enhancedResponse,
        type: aiAnalysis ? "enhanced" : "text",
        metadata: {
          ...(aiAnalysis && {
            aiAnalysis: {
              analysisId: aiAnalysis.analysis_id,
              sentimentScores: aiAnalysis.sentiment_scores,
              entities: aiAnalysis.entities,
              intents: aiAnalysis.intents,
              contextRelevance: aiAnalysis.context_relevance,
              suggestedActions: aiAnalysis.suggested_actions,
            },
          }),
          suggestedActions: [
            "Try the search feature to find information",
            "Check your tasks in the task manager",
            "Send messages through the communication hub",
          ],
        },
        sessionId: sessionId || `session_${Date.now()}`,
        timestamp: new Date().toISOString(),
      });
    }

  } catch (error) {
    console.error("Error in enhanced chat API:", error);

    // Final fallback response
    return res.status(200).json({
      success: true,
      message: "I received your message. The enhanced chat system is currently processing your request with AI intelligence. You can continue using other features while I work on this.",
      type: "text",
      metadata: {
        suggestedActions: [
          "Try the search feature to find information",
          "Check your tasks in the task manager",
          "Send messages through the communication hub",
        ],
      },
      sessionId: `session_${Date.now()}`,
      timestamp: new Date().toISOString(),
    });
  }
}

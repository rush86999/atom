import type { NextApiRequest, NextApiResponse } from 'next';
import { chatOrchestrationService } from '../../../../../src/services/ChatOrchestrationService';

interface ChatRequest {
  userId: string;
  message: string;
  sessionId?: string;
  processId?: string;
}

interface ChatResponse {
  success: boolean;
  message: string;
  type: 'text' | 'workflow' | 'multi_step' | 'confirmation' | 'error';
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
  res: NextApiResponse<ChatResponse>
) {
  if (req.method !== 'POST') {
    return res.status(405).json({
      success: false,
      message: 'Method not allowed',
      type: 'error'
    });
  }

  try {
    const { userId, message, sessionId, processId }: ChatRequest = req.body;

    if (!userId || !message) {
      return res.status(400).json({
        success: false,
        message: 'Missing required fields: userId and message',
        type: 'error'
      });
    }

    // Initialize service if not already done
    if (!chatOrchestrationService) {
      return res.status(500).json({
        success: false,
        message: 'Chat orchestration service not available',
        type: 'error'
      });
    }

    // Process the chat message
    const response = await chatOrchestrationService.processMessage(userId, message);

    // Return the response
    res.status(200).json({
      success: true,
      message: response.message,
      type: response.type,
      metadata: response.metadata,
      sessionId: sessionId || `session_${Date.now()}`
    });

  } catch (error) {
    console.error('Error in chat orchestration API:', error);
    res.status(500).json({
      success: false,
      message: 'Internal server error processing your request',
      type: 'error'
    });
  }
}

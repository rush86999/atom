import type { NextApiRequest, NextApiResponse } from "next";

interface Phase3HealthResponse {
  status: "healthy" | "degraded" | "unavailable";
  version: string;
  timestamp: string;
  services: {
    phase3_ai_intelligence: {
      status: "available" | "unavailable";
      port: number;
      response_time?: number;
      features: {
        sentiment_analysis: boolean;
        entity_extraction: boolean;
        intent_detection: boolean;
        context_aware_responses: boolean;
      };
    };
    main_chat_api: {
      status: "available" | "unavailable";
      port: number;
      response_time?: number;
    };
    websocket_server: {
      status: "available" | "unavailable";
      port: number;
      response_time?: number;
    };
  };
  overall_health: {
    ai_intelligence_available: boolean;
    chat_api_available: boolean;
    websocket_available: boolean;
    enhanced_chat_ready: boolean;
  };
  recommendations?: string[];
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Phase3HealthResponse>,
) {
  if (req.method !== "GET") {
    return res.status(405).json({
      status: "unavailable",
      version: "1.0.0",
      timestamp: new Date().toISOString(),
      services: {
        phase3_ai_intelligence: {
          status: "unavailable",
          port: 5062,
          features: {
            sentiment_analysis: false,
            entity_extraction: false,
            intent_detection: false,
            context_aware_responses: false,
          },
        },
        main_chat_api: {
          status: "unavailable",
          port: 8000,
        },
        websocket_server: {
          status: "unavailable",
          port: 5060,
        },
      },
      overall_health: {
        ai_intelligence_available: false,
        chat_api_available: false,
        websocket_available: false,
        enhanced_chat_ready: false,
      },
      recommendations: ["Use GET method for health check"],
    });
  }

  try {
    const healthChecks = {
      phase3_ai_intelligence: await checkPhase3Service(),
      main_chat_api: await checkMainChatAPI(),
      websocket_server: await checkWebSocketServer(),
    };

    const overallStatus = calculateOverallStatus(healthChecks);
    const recommendations = generateRecommendations(healthChecks);

    const response: Phase3HealthResponse = {
      status: overallStatus,
      version: "1.0.0",
      timestamp: new Date().toISOString(),
      services: healthChecks,
      overall_health: {
        ai_intelligence_available: healthChecks.phase3_ai_intelligence.status === "available",
        chat_api_available: healthChecks.main_chat_api.status === "available",
        websocket_available: healthChecks.websocket_server.status === "available",
        enhanced_chat_ready:
          healthChecks.phase3_ai_intelligence.status === "available" &&
          healthChecks.main_chat_api.status === "available",
      },
      ...(recommendations.length > 0 && { recommendations }),
    };

    return res.status(200).json(response);
  } catch (error) {
    console.error("Error in Phase 3 health check:", error);

    return res.status(200).json({
      status: "unavailable",
      version: "1.0.0",
      timestamp: new Date().toISOString(),
      services: {
        phase3_ai_intelligence: {
          status: "unavailable",
          port: 5062,
          features: {
            sentiment_analysis: false,
            entity_extraction: false,
            intent_detection: false,
            context_aware_responses: false,
          },
        },
        main_chat_api: {
          status: "unavailable",
          port: 8000,
        },
        websocket_server: {
          status: "unavailable",
          port: 5060,
        },
      },
      overall_health: {
        ai_intelligence_available: false,
        chat_api_available: false,
        websocket_available: false,
        enhanced_chat_ready: false,
      },
      recommendations: ["System health check failed - check backend services"],
    });
  }
}

async function checkPhase3Service(): Promise<any> {
  const startTime = Date.now();
  try {
    const response = await fetch("http://localhost:5062/health", {
      method: "GET",
      timeout: 5000,
    } as any);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const responseTime = Date.now() - startTime;

    return {
      status: "available",
      port: 5062,
      response_time: responseTime,
      features: {
        sentiment_analysis: data.features?.sentiment_analysis || false,
        entity_extraction: data.features?.entity_extraction || false,
        intent_detection: data.features?.intent_detection || false,
        context_aware_responses: data.features?.phase3_enhanced_chat || false,
      },
    };
  } catch (error) {
    return {
      status: "unavailable",
      port: 5062,
      features: {
        sentiment_analysis: false,
        entity_extraction: false,
        intent_detection: false,
        context_aware_responses: false,
      },
    };
  }
}

async function checkMainChatAPI(): Promise<any> {
  const startTime = Date.now();
  try {
    const response = await fetch("http://localhost:8000/health", {
      method: "GET",
      timeout: 5000,
    } as any);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const responseTime = Date.now() - startTime;

    return {
      status: "available",
      port: 8000,
      response_time: responseTime,
    };
  } catch (error) {
    return {
      status: "unavailable",
      port: 8000,
    };
  }
}

async function checkWebSocketServer(): Promise<any> {
  const startTime = Date.now();
  try {
    const response = await fetch("http://localhost:5060/health", {
      method: "GET",
      timeout: 5000,
    } as any);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const responseTime = Date.now() - startTime;

    return {
      status: "available",
      port: 5060,
      response_time: responseTime,
    };
  } catch (error) {
    return {
      status: "unavailable",
      port: 5060,
    };
  }
}

function calculateOverallStatus(healthChecks: any): "healthy" | "degraded" | "unavailable" {
  const availableServices = Object.values(healthChecks).filter(
    (service: any) => service.status === "available"
  ).length;

  const totalServices = Object.keys(healthChecks).length;

  if (availableServices === totalServices) {
    return "healthy";
  } else if (availableServices >= 1) {
    return "degraded";
  } else {
    return "unavailable";
  }
}

function generateRecommendations(healthChecks: any): string[] {
  const recommendations: string[] = [];

  if (healthChecks.phase3_ai_intelligence.status === "unavailable") {
    recommendations.push("Start Phase 3 AI intelligence service on port 5062");
  }

  if (healthChecks.main_chat_api.status === "unavailable") {
    recommendations.push("Start main chat API service on port 8000");
  }

  if (healthChecks.websocket_server.status === "unavailable") {
    recommendations.push("Start WebSocket server on port 5060");
  }

  if (healthChecks.phase3_ai_intelligence.status === "available" &&
      healthChecks.main_chat_api.status === "available") {
    recommendations.push("Enhanced chat with AI intelligence is ready for use");
  }

  return recommendations;
}

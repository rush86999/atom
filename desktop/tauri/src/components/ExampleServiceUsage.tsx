import React, { useState, useEffect } from "react";
import { chatOrchestrationService } from "@shared-ai/ChatOrchestrationService";
import { AuthService } from "@shared-integrations/authService";
import { WorkflowService } from "@shared-workflows/workflowService";
import { nluService } from "@shared-ai/nluService";

/**
 * Example component demonstrating how to use shared services in the desktop app
 */
const ExampleServiceUsage: React.FC = () => {
  const [chatResponse, setChatResponse] = useState<string>("");
  const [authStatus, setAuthStatus] = useState<string>("");
  const [workflowStatus, setWorkflowStatus] = useState<string>("");
  const [nluAnalysis, setNluAnalysis] = useState<string>("");
  const [desktopFeatures, setDesktopFeatures] = useState<string>("");

  useEffect(() => {
    // Example: Initialize services on component mount
    initializeServices();
  }, []);

  const initializeServices = async () => {
    try {
      // Example: Check authentication status with desktop-specific context
      const authResult =
        await AuthService.getGoogleDriveAccessToken("desktop-user");
      setAuthStatus(
        authResult ? "Authenticated (Desktop)" : "Not authenticated",
      );

      // Example: Initialize workflow service for desktop
      const workflowService = new WorkflowService();
      const workflowResult =
        await workflowService.initializeWorkflow("desktop-workflow");
      setWorkflowStatus(
        workflowResult ? "Desktop workflow ready" : "Workflow failed",
      );

      // Desktop-specific features
      setDesktopFeatures(
        "Local storage, Audio processing, Wake word detection",
      );
    } catch (error) {
      console.error("Error initializing services:", error);
      setAuthStatus("Authentication error");
      setWorkflowStatus("Workflow initialization error");
    }
  };

  const handleChatMessage = async (message: string) => {
    try {
      const response = await chatOrchestrationService.processMessage({
        message,
        userId: "desktop-user",
        context: "desktop-app",
        // Desktop-specific context
        platform: "desktop",
        hasLocalStorage: true,
        canProcessAudio: true,
      });
      setChatResponse(response.content);
    } catch (error) {
      console.error("Chat error:", error);
      setChatResponse("Error processing message");
    }
  };

  const analyzeText = async (text: string) => {
    try {
      const analysis = await nluService.analyzeText(text, {
        userId: "desktop-user",
        language: "en",
        // Desktop-specific analysis options
        useLocalModels: true,
        offlineCapable: true,
      });
      setNluAnalysis(JSON.stringify(analysis, null, 2));
    } catch (error) {
      console.error("NLU analysis error:", error);
      setNluAnalysis("Analysis failed");
    }
  };

  const triggerDesktopWorkflow = async () => {
    try {
      const workflowService = new WorkflowService();
      const result = await workflowService.startWorkflow("desktop-automation", {
        userId: "desktop-user",
        platform: "desktop",
        // Desktop-specific workflow parameters
        useLocalStorage: true,
        enableVoiceCommands: true,
        offlineMode: true,
      });
      setWorkflowStatus(`Workflow triggered: ${result.status}`);
    } catch (error) {
      console.error("Workflow error:", error);
      setWorkflowStatus("Workflow failed");
    }
  };

  return (
    <div className="example-service-usage">
      <h2>Shared Services Example - Desktop App</h2>

      <div className="desktop-features">
        <h3>Desktop-Specific Features</h3>
        <p>{desktopFeatures}</p>
      </div>

      <div className="service-section">
        <h3>Authentication Service</h3>
        <p>Status: {authStatus}</p>
        <button onClick={() => initializeServices()}>
          Check Desktop Auth Status
        </button>
      </div>

      <div className="service-section">
        <h3>Chat Service (Desktop Context)</h3>
        <input
          type="text"
          placeholder="Enter a message for desktop context..."
          onKeyPress={(e) => {
            if (e.key === "Enter") {
              handleChatMessage(e.currentTarget.value);
              e.currentTarget.value = "";
            }
          }}
        />
        <p>Response: {chatResponse}</p>
      </div>

      <div className="service-section">
        <h3>Workflow Service (Desktop Automation)</h3>
        <p>Status: {workflowStatus}</p>
        <button onClick={triggerDesktopWorkflow}>Start Desktop Workflow</button>
      </div>

      <div className="service-section">
        <h3>NLU Service (Offline Capable)</h3>
        <input
          type="text"
          placeholder="Enter text to analyze offline..."
          onKeyPress={(e) => {
            if (e.key === "Enter") {
              analyzeText(e.currentTarget.value);
              e.currentTarget.value = "";
            }
          }}
        />
        <pre>{nluAnalysis}</pre>
      </div>

      <style>{`
        .example-service-usage {
          padding: 20px;
          max-width: 800px;
          margin: 0 auto;
          background-color: #f8f9fa;
          border-radius: 12px;
        }

        .desktop-features {
          background-color: #e3f2fd;
          padding: 15px;
          border-radius: 8px;
          margin-bottom: 20px;
          border-left: 4px solid #2196f3;
        }

        .service-section {
          margin-bottom: 25px;
          padding: 20px;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          background-color: white;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        h2 {
          color: #1a237e;
          margin-bottom: 20px;
          text-align: center;
        }

        h3 {
          color: #3949ab;
          margin-bottom: 10px;
          font-size: 1.1em;
        }

        input {
          padding: 10px;
          margin-right: 10px;
          border: 1px solid #bdbdbd;
          border-radius: 6px;
          width: 250px;
          font-size: 14px;
        }

        button {
          padding: 10px 20px;
          background-color: #3949ab;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
          transition: background-color 0.2s;
        }

        button:hover {
          background-color: #283593;
        }

        pre {
          background-color: #f5f5f5;
          padding: 12px;
          border-radius: 6px;
          overflow-x: auto;
          border: 1px solid #e0e0e0;
          font-size: 12px;
        }

        p {
          margin: 8px 0;
          color: #424242;
        }
      `}</style>
    </div>
  );
};

export default ExampleServiceUsage;

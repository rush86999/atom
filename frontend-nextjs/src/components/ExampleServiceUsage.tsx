import React, { useState, useEffect } from 'react';
import { ChatOrchestrationService } from '@shared-ai/ChatOrchestrationService';
import { authService } from '@shared-integrations/authService';
import { workflowService } from '@shared-workflows/workflowService';
import { nluService } from '@shared-ai/nluService';

/**
 * Example component demonstrating how to use shared services in the web app
 */
const ExampleServiceUsage: React.FC = () => {
  const [chatResponse, setChatResponse] = useState<string>('');
  const [authStatus, setAuthStatus] = useState<string>('');
  const [workflowStatus, setWorkflowStatus] = useState<string>('');
  const [nluAnalysis, setNluAnalysis] = useState<string>('');

  useEffect(() => {
    // Example: Initialize services on component mount
    initializeServices();
  }, []);

  const initializeServices = async () => {
    try {
      // Example: Check authentication status
      const authResult = await authService.getGoogleDriveAccessToken('user123');
      setAuthStatus(authResult ? 'Authenticated' : 'Not authenticated');

      // Example: Initialize workflow service
      const workflowResult = await workflowService.initializeWorkflow('example-workflow');
      setWorkflowStatus(workflowResult ? 'Workflow ready' : 'Workflow failed');

    } catch (error) {
      console.error('Error initializing services:', error);
      setAuthStatus('Authentication error');
      setWorkflowStatus('Workflow initialization error');
    }
  };

  const handleChatMessage = async (message: string) => {
    try {
      const response = await ChatOrchestrationService.processMessage({
        message,
        userId: 'user123',
        context: 'web-app'
      });
      setChatResponse(response.content);
    } catch (error) {
      console.error('Chat error:', error);
      setChatResponse('Error processing message');
    }
  };

  const analyzeText = async (text: string) => {
    try {
      const analysis = await nluService.analyzeText(text, {
        userId: 'user123',
        language: 'en'
      });
      setNluAnalysis(JSON.stringify(analysis, null, 2));
    } catch (error) {
      console.error('NLU analysis error:', error);
      setNluAnalysis('Analysis failed');
    }
  };

  return (
    <div className="example-service-usage">
      <h2>Shared Services Example - Web App</h2>

      <div className="service-section">
        <h3>Authentication Service</h3>
        <p>Status: {authStatus}</p>
        <button onClick={() => initializeServices()}>
          Check Auth Status
        </button>
      </div>

      <div className="service-section">
        <h3>Chat Service</h3>
        <input
          type="text"
          placeholder="Enter a message..."
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              handleChatMessage(e.currentTarget.value);
              e.currentTarget.value = '';
            }
          }}
        />
        <p>Response: {chatResponse}</p>
      </div>

      <div className="service-section">
        <h3>Workflow Service</h3>
        <p>Status: {workflowStatus}</p>
        <button onClick={() => workflowService.startWorkflow('example-workflow')}>
          Start Workflow
        </button>
      </div>

      <div className="service-section">
        <h3>NLU Service</h3>
        <input
          type="text"
          placeholder="Enter text to analyze..."
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              analyzeText(e.currentTarget.value);
              e.currentTarget.value = '';
            }
          }}
        />
        <pre>{nluAnalysis}</pre>
      </div>

      <style jsx>{`
        .example-service-usage {
          padding: 20px;
          max-width: 800px;
          margin: 0 auto;
        }

        .service-section {
          margin-bottom: 30px;
          padding: 15px;
          border: 1px solid #ddd;
          border-radius: 8px;
        }

        h2 {
          color: #333;
          margin-bottom: 20px;
        }

        h3 {
          color: #555;
          margin-bottom: 10px;
        }

        input {
          padding: 8px;
          margin-right: 10px;
          border: 1px solid #ccc;
          border-radius: 4px;
          width: 200px;
        }

        button {
          padding: 8px 16px;
          background-color: #0070f3;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }

        button:hover {
          background-color: #0051a8;
        }

        pre {
          background-color: #f5f5f5;
          padding: 10px;
          border-radius: 4px;
          overflow-x: auto;
        }
      `}</style>
    </div>
  );
};

export default ExampleServiceUsage;

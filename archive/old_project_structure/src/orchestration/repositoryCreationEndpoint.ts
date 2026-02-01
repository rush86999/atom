// atom/src/orchestration/repositoryCreationEndpoint.ts
import { Express } from 'express';
import { WebAppRepositoryOrchestrator } from './webAppRepositoryOrchestrator';
import { OrchestrationEngine } from './OrchestrationEngine';
import { verifyToken } from '../auth/auth-middleware';

interface RepositoryRequest {
  prompt: string;
  projectName?: string;
  templateType?: string;
  isPrivate?: boolean;
  userId: string;
}

interface RepositoryResponse {
  success: boolean;
  repository?: {
    name: string;
    url: string;
    cloneUrl: string;
  };
  message?: string;
  nextSteps?: string[];
  error?: string;
}

export function setupRepositoryCreationEndpoint(app: Express) {
  const orchestrator = new WebAppRepositoryOrchestrator(new OrchestrationEngine());

  app.post('/api/orchestration/create-web-app', verifyToken, async (req, res) => {
    try {
      const { prompt, projectName, templateType, isPrivate, userId }: RepositoryRequest = req.body;

      if (!prompt && !projectName) {
        return res.status(400).json({
          success: false,
          error: 'Either prompt or projectName is required'
        });
      }

      // Parse request
      let finalProjectName = projectName;
      let finalTemplate = templateType || 'nextjs-basic';

      if (!finalProjectName) {
        // Extract from prompt
        const nameMatch = prompt.match(/(?:create|build|start|make)\s+(?:project|app|website)\s+(?:called|named)?\s*"?([^"\s]+)"?/i);
        finalProjectName = nameMatch ? nameMatch[1].toLowerCase().replace(/[^a-z0-9-]/g, '-') : 'atom-generated-app';
      }

      if (!templateType) {
        // Infer from prompt
        if (prompt.includes('fullstack') || prompt.includes('full-stack')) finalTemplate = 'nextjs-fullstack';
        else if (prompt.includes('react')) finalTemplate = 'react-vite';
        else if (prompt.includes('node') || prompt.includes('express')) finalTemplate = 'node-express';
        else if (prompt.includes('vanilla') || prompt.includes('plain')) finalTemplate = 'vanilla-js';
      }

      const result = await orchestrator.createWebAppRepository({
        userId,
        projectName: finalProjectName,
        templateType: finalTemplate as any,
        isPrivate,
        description: prompt || `Generated via ATOM AI: ${finalProjectName}`
      });

      if (!result.success) {
        return res.status(400).json({
          success: false,
          error: result.error
        });
      }

      const response: RepositoryResponse = {
        success: true,
        repository: {
          name: result.repoName!,
          url: result.repoUrl!,
          cloneUrl: result.cloneUrl!
        },
        message: result.message,
        nextSteps: result.nextSteps
      };

      res.json(response);

    } catch (error) {
      console.error('Repository creation endpoint error:', error);
      res.status(500).json({
        success: false,
        error: 'Internal server error'
      });
    }
  });

  // ATOM Agent trigger - simpler endpoint for direct agent calls
  app.post('/api/agent/create-repository', async (req, res) => {
    try {
      // Check for ATOM agent signature
      const agentSecret = req.headers['x-atom-secret'];
      if (agentSecret !== process.env.ATOM_AGENT_SECRET) {
        return res.status(401).json({ success: false, error: 'Unauthorized' });
      }

      const { userId, intent, parameters } = req.body;

      if (!userId || !intent || intent !== 'create-web-app') {
        return res.status(400).json({
+          success: false,
++          error: 'Invalid request format'
++        });
++      }
++
++      const result = await orchestrator.createWebAppRepository({
++        userId,
++        projectName: parameters.projectName || 'atom-project',
++        templateType: parameters.templateType || 'nextjs-basic',
++        isPrivate: parameters.isPrivate,
++        description: parameters.description || 'ATOM AI generated project'
++      });
++
++      res.json({ success: true, ...result });
++    } catch (error) {
++      console.error('Agent repository creation error:', error);
++      res.status(500).json({ success: false, error: 'Internal error' });
++    }
++  });
++
++  // Status endpoint for checking creation status
++  app.get('/api/orchestration/repository-status/:userId', verifyToken, async (req, res) => {
++    try {
++      const user

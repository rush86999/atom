import { OrchestrationEngine } from './OrchestrationEngine';
import { createGithubRepo } from '../skills/githubSkills';
import { SkillResponse } from '../types';

interface WebAppRequest {
  userId: string;
  projectName: string;
  templateType: 'nextjs-basic' | 'nextjs-fullstack' | 'react-vite' | 'vanilla-js' | 'node-express';
  isPrivate?: boolean;
  description?: string;
}

interface RepositoryResult {
  success: boolean;
  repoUrl?: string;
  repoName?: string;
  cloneUrl?: string;
  message?: string;
  error?: string;
  nextSteps?: string[];
}

export class WebAppRepositoryOrchestrator {
  private engine: OrchestrationEngine;
  private templates = {
    'nextjs-basic': 'Next.js 14 with TypeScript and Tailwind CSS',
    'nextjs-fullstack': 'Next.js 14 + API routes + Prisma + Auth',
    'react-vite': 'React + Vite (client-only)',
    'vanilla-js': 'Plain HTML/CSS/JS',
    'node-express': 'Node.js + Express.js API'
  };

  constructor(engine: OrchestrationEngine) {
    this.engine = engine;
  }

  async createWebAppRepository(request: WebAppRequest): Promise<RepositoryResult> {
    try {
      console.log(`[WebAppRepositoryOrchestrator] Creating repo for ${request.userId}: ${request.projectName}`);

      // Validate and normalize inputs
      if (!request.userId || !request.projectName) {
        throw new Error('User ID and project name are required');
      }

      // Create repository via GitHub API
      const repoResponse = await createGithubRepo(request.userId, {
        name: request.projectName,
        description: request.description || `ATOM-generated ${request.projectName} - built via AI conversation`,
        private: request.isPrivate || false,
        template: request.templateType,
        auto_init: true
      });

      if (!repoResponse.ok || !repoResponse.data) {
        return {
          success: false,
          error: repoResponse.error?.message || 'Failed to create repository'
        };
      }

      const repoData = repoResponse.data;

      // Provide contextual next steps
      const nextSteps = this.generateNextSteps(request.templateType, repoData.full_url);

      return {
        success: true,
        repoUrl: repoData.full_url,
        repoName: repoData.name,
        cloneUrl: repoData.clone_url,
        message: `Successfully created repository: ${repoData.name}`,
        nextSteps
      };

    } catch (error: any) {
      console.error('[WebAppRepositoryOrchestrator] Error creating repository:', error);
      return {
        success: false,
        error: error.message || 'Repository creation failed'
      };
    }
  }

  private generateNextSteps(templateType: string, repoUrl: string): string[] {
    const steps = [
      `Clone your new repository: git clone ${repoUrl}`,
      `Navigate to the project: cd $(basename ${repoUrl} .git)`
    ];

    const templateSteps: Record<string, string[]> = {
      'nextjs-basic': [
        'Install dependencies: npm install',
        'Start development: npm run dev',
        'Build for production: npm run build'
      ],
      'nextjs-fullstack': [
        'Install dependencies: npm install',
        'Setup database: npm run db:setup',
        'Start development: npm run dev',
        'Deploy to production: git push origin main'
      ],
      'react-vite': [
        'Install dependencies: npm install',
        'Start development: npm run dev',
        'Build for production: npm run build'
      ],
      'vanilla-js': [
        'Open index.html in your browser',
        'Edit directly in the files',
        'Commit changes: git add . && git commit -m "Initial commit"'
      ],
      'node-express': [
        'Install dependencies: npm install',
        'Start development server: npm run dev',
        'Test your API: npm test'
      ]
    };

    return [...steps, ...(templateSteps[templateType] || [])];
  }

  async validateProjectName(projectName: string): Promise<boolean> {
    const validPattern = /^[a-zA-Z0-9-]+$/;
    return validPattern.test(projectName) && projectName.length <= 100;
  }

  return this.templates;
}
}

// Atom agent integration hooks
export const webAppRepositoryAgent = {
name: 'webAppRepositoryCreator',
description: 'Creates new GitHub repositories for web app development projects',

async handle(userId: string, context: any): Promise<RepositoryResult> {
  const orchestrator = new WebAppRepositoryOrchestrator(new OrchestrationEngine());

  const request: WebAppRequest = {
    userId,
    projectName: context.projectName,
    templateType: context.templateType || 'nextjs-basic',
    isPrivate: context.isPrivate,
    description: context.description
  };

  return orchestrator.createWebAppRepository(request);
},

parseConversation(text: string): WebAppRequest | null {
  // Parse natural language to extract repo creation intent
  const createMatch = text.match(/create.*project|build.*app|start.*website|make.*web/i);
  const projectMatch = text.match(/project[\s:]+"?([^"\s]+)"?|call[\s:]+"?([^"\s]+)"?|named[\s:]+"?([^"\s]+)"?/i);
  const templateMatch = text.match(/nextjs|react|vanilla|node|express/i);

  if (createMatch && projectMatch) {
    const projectName = (projectMatch[1] || projectMatch[2] || projectMatch[3] || 'my-app').toLowerCase().replace(/[^a-z0-9-]/g, '-');

    let templateType: WebAppRequest['templateType'] = 'nextjs-basic';
    if (templateMatch) {
      const match = templateMatch[0].toLowerCase();
      if (match.includes('fullstack')) templateType = 'nextjs-fullstack';
      else if (match.includes('react')) templateType = 'react-vite';
+        else if (match.includes('node')) templateType = 'node-express';
+        else if (match.includes('vanilla')) templateType = 'vanilla-js';
+      }
+
+      return {
+        userId: 'current-user',
+        projectName,
+        templateType,
+        description: `Generated via ATOM AI conversation: ${text.substring(0, 100)}...`
+      };
+    }
+
+    return null;
+  }
+};

+export function registerWithOrchestration(engine: OrchestrationEngine) {
+  engine.registerAgent({
+    id: 'web-app-repository-creator',
+    name: 'WebAppRepositoryCreator',
+    type: 'autonomous',
+    skills: ['github-repository-creation', 'web-project-initiation'],
+    onTask: async (task: any) => {
+      const request = webAppRepositoryAgent.parseConversation(task.payload.text || task.payload.message);
+      if (request) {
+        return webAppRepositoryAgent.handle(task.userId, {
+          ...request,
+          userId: task.userId
+        });
+      }
+      return null;
+    }
+  });
+}

// Atom agent integration hooks
export const webAppRepositoryAgent = {
  name: 'webAppRepositoryCreator',
  description: 'Creates new GitHub repositories for web app development projects',

  async handle(userId: string, context: any): Promise<RepositoryResult> {
    const orchestrator = new WebAppRepositoryOrc

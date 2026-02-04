// atom/src/orchestration/AgentRepositoryIntegration.ts
import { WebAppRepositoryOrchestrator } from './webAppRepositoryOrchestrator';
import { OrchestrationEngine } from './OrchestrationEngine';

export interface AgentConversationRequest {
  userId: string;
  conversationId: string;
  message: string;
  context?: {
    previousMessages?: string[];
    userPreferences?: Record<string, any>;
  };
}

export interface AgentRepositoryResponse {
  success: boolean;
  repositoryCreated: boolean;
  repositoryUrl?: string;
  repositoryName?: string;
  stepByStep?: string[];
  chatResponse?: string;
  error?: string;
}

export class AgentRepositoryIntegration {
  private orchestrator: WebAppRepositoryOrchestrator;
  private engine: OrchestrationEngine;

  constructor() {
    this.engine = new OrchestrationEngine();
    this.orchestrator = new WebAppRepositoryOrchestrator(this.engine);
  }

  async handleConversation(request: AgentConversationRequest): Promise<AgentRepositoryResponse> {
    try {
      const parsed = this.parseRepositoryIntent(request.message);

      if (!parsed.hasIntent) {
        return {
          success: true,
          repositoryCreated: false,
          chatResponse: 'I can help you create a new repository for web development! Try saying something like: "create a nextjs project called my-blog" or "build a react website named portfolio"'
        };
      }

      const response = await this.orchestrator.createWebAppRepository({
        userId: request.userId,
        projectName: parsed.projectName,
        templateType: parsed.template as any,
        isPrivate: parsed.isPrivate,
        description: `${parsed.projectName} - created via ATOM AI conversation`
      });

      if (!response.success) {
        return {
          success: false,
          repositoryCreated: false,
          error: response.error,
          chatResponse: `Sorry, I couldn't create the repository: ${response.error}`
        };
      }

      const chatResponse = this.generateFriendlyResponse({
        projectName: response.repoName!,
        repositoryUrl: response.repoUrl!,
        templateType: parsed.template,
        nextSteps: response.nextSteps
      });

      return {
        success: true,
        repositoryCreated: true,
        repositoryUrl: response.repoUrl,
        repositoryName: response.repoName,
        stepByStep: response.nextSteps,
        chatResponse
      };

    } catch (error) {
      console.error('[AgentRepositoryIntegration] Error:', error);
      return {
        success: false,
        repositoryCreated: false,
        error: 'Failed to process repository creation request',
        chatResponse: "I encountered an error while creating your repository. Please try again or contact support."
      };
    }
  }

  private parseRepositoryIntent(message: string): {
    hasIntent: boolean;
    projectName: string;
    template: string;
    isPrivate: boolean;
  } {
    const lower = message.toLowerCase();

    // Check if user wants to create a repository
    const creationTriggers = [
      /create.*project/i,
      /build.*web/i,
      /start.*website/i,
      /make.*app/i,
      /new.*repository/i,
      /repo.*create/i
    ];

    const hasIntent = creationTriggers.some(trigger => trigger.test(lower));

    // Extract project name
    const namePatterns = [
+      /(?:called|named|title):?\s*["']?([^"'\s]+)["']?/i,
+      /project:?\s*["']?([^"'\s]+)["']?/i,
+      /(?:name the repo|name it):?\s*["']?([^"'\s]+)["']?/i
+    ];
+
+    let projectName = 'atom-project';
+    for (const pattern of namePatterns) {
+      const match = message.match(pattern);
+      if (match) {
+        projectName = match[1].replace(/[^a-zA-Z0-9-]/g, '-').toLowerCase();
+        break;
+      }
+    }
+
+    // Add timestamp to ensure uniqueness
+    const timestamp = Date.now().toString().slice(-6);
+    projectName = `${projectName}-${timestamp}`;
+
+    // Detect template
+    let template = 'nextjs-basic';
+    if (lower.includes('fullstack') || lower.includes('full-stack')) template = 'nextjs-fullstack';
+    else if (lower.includes('react')) template = 'react-vite';
+    else if (lower.includes('node')) template = 'node-express';
+    else if (lower.includes('vanilla')) template = 'vanilla-js';
+
+    // Check for privacy
+    const isPrivate = lower.includes('private') || false;
+
return { hasIntent, projectName, template, isPrivate };
}

private generateFriendlyResponse(args: {
projectName: string;
repositoryUrl: string;
templateType: string;
nextSteps?: string[];
}): string {
return `🎉 **Your new web app has been created!**

I've successfully created **${args.projectName}** for you.

🔗 **Repository**: ${args.repositoryUrl}
📁 **Template**: ${this.formatTemplateName(args.templateType)}

🚀 **Next steps**:
+${args.nextSteps?.map(step => `   ${step}`).join('\n') || '   Clone and start development!'}

Your repository is ready for development! The project includes:
+- Modern build tools and setup
+- GitHub Actions for automatic deployment
+- Example code and structure
+- Development scripts

You can start coding immediately by cloning the repository and following the setup instructions in the README. Happy coding! 💻`;
}

private formatTemplateName(template: string): string {
const names: Record<string, string> = {
  'nextjs-basic': 'Next.js (Basic)',
  'nextjs-fullstack': 'Next.js (Full-stack)',
  'react-vite': 'React + Vite',
  'vanilla-js': 'Vanilla JavaScript',
  'node-express': 'Node.js + Express'
};
return names[template] || template;
}

// Registration function for the ATOM orchestration system
static register(engine: OrchestrationEngine) {
const integration = new AgentRepositoryIntegration();

engine.registerAgent({
+      id: 'web-app-repository-creator',
+      name: 'Repository Creator Agent',
+      type: 'autonomous',
+      skills: ['repository-creation', 'web-development-setup'],
+      capabilities: ['create-github-repository', 'setup-web-project', 'generate-nextsteps'],
+      onTask: async (task: any) => {
+        if (task.type === 'create-web-app-repository') {
+          return integrated.handleConversation({
+            userId: task.userId,
+            conversationId: task.id,
+            message: task.message || task.prompt
+          });
+        }
+        return null;
+      }
+    });
+
+    console.log('🎯 Repository Creator Agent registered with ATOM');
+  }
}

// Singleton instance export
+export const repositoryAgent = new AgentRepositoryIntegration();
+

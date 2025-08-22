// ATOM Desktop Web Development Service
// Integrates Next.js development with cloud deployment pipeline
// No direct local build dependencies - works through cloud services

import { invoke } from "@tauri-apps/api/tauri";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/api/shell";

export interface WebDevProject {
  id: string;
  name: string;
  githubRepo: string;
  cloudProvider: "vercel" | "netlify" | "render";
  status: "idle" | "building" | "ready" | "failed";
  liveUrl: string;
  previewUrl?: string;
  lastBuildTime?: number;
  score?: PerformanceScore;
  error?: string;
}

export interface PerformanceScore {
  performance: number;
  accessibility: number;
  bestPractices: number;
  seo: number;
}

export interface BuildCommand {
  instruction: string;
  type: "create" | "modify" | "deploy" | "optimize";
  details: Record<string, any>;
}

export interface DevelopmentSession {
  id: string;
  project: WebDevProject;
  startTime: Date;
  messages: BuildMessage[];
  isActive: boolean;
}

export interface BuildMessage {
  id: string;
  timestamp: Date;
  content: string;
  status: "info" | "success" | "error" | "building";
  url?: string;
}

export class WebDevService {
  private session: DevelopmentSession | null = null;
  private subscriptions: Array<() => void> = [];
  private messageHandlers: Array<(message: BuildMessage) => void> = [];

  constructor() {
    this.setupEventListeners();
  }

  private setupEventListeners(): void {
    // Setup event listeners for Tauri events
    listen("web-dev-project-update", (event) => {
      const project = event.payload as WebDevProject;
      this.emit("project-update", project);
    }).then((unsubscribe) => {
      this.subscriptions.push(unsubscribe);
    });

    listen("web-dev-build-message", (event) => {
      const message = event.payload as BuildMessage;
      this.emit("message", message);
    }).then((unsubscribe) => {
      this.subscriptions.push(unsubscribe);
    });
  }

  private emit(event: string, data: any): void {
    // Emit events to registered handlers
    if (event === "message") {
      this.messageHandlers.forEach((handler) => handler(data as BuildMessage));
    }
    // Add other event types as needed
  }

  onMessage(handler: (message: BuildMessage) => void): () => void {
    this.messageHandlers.push(handler);
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== handler);
    };
  }

  async startNewProject(config: {
    name: string;
    githubRepo?: string;
    template?: "nextjs" | "react" | "vue" | "templates/saas";
    provider?: "vercel" | "netlify" | "render";
  }): Promise<WebDevProject> {
    const project: WebDevProject = {
      id: `project-${Date.now()}`,
      name: config.name,
      githubRepo: config.githubRepo || `atom-dev/${config.name}`,
      cloudProvider: config.provider || "vercel",
      status: "idle",
      liveUrl: "",
    };

    const session: DevelopmentSession = {
      id: `session-${Date.now()}`,
      project,
      startTime: new Date(),
      messages: [],
      isActive: true,
    };

    this.session = session;

    // Notify cloud service
    await this.initializeCloudProject(project);

    this.addMessage({
      content: `Started development session for ${project.name}`,
      status: "info",
    });

    return project;
  }

  async buildViaConversation(instruction: string): Promise<void> {
    if (!this.session) {
      throw new Error("No active development session");
    }

    this.addMessage({
      content: `Processing: ${instruction}`,
      status: "building",
    });

    try {
      const result = await invoke("process_web_dev_instruction", {
        projectId: this.session.project.id,
        instruction,
        sessionId: this.session.id,
      });

      const buildResult = result as {
        status: string;
        url: string;
        performance: PerformanceScore;
      };

      this.session.project.status = buildResult.status as any;
      this.session.project.liveUrl = buildResult.url;
      this.session.project.score = buildResult.performance;
      this.session.project.lastBuildTime = Date.now();

      this.addMessage({
        content: `Build complete! ${instruction}`,
        status: "success",
        url: buildResult.url,
      });

      // Auto-open in browser
      if (buildResult.status === "ready") {
        await open(buildResult.url);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Build failed";

      this.addMessage({
        content: `Build error: ${errorMessage}`,
        status: "error",
      });
    }
  }

  async getProjectHistory(): Promise<WebDevProject[]> {
    const history = await invoke("get_project_history");
    return history as WebDevProject[];
  }

  async getPerformanceReport(): Promise<PerformanceScore | null> {
    if (!this.session) return null;

    const report = await invoke("get_performance_report", {
      projectId: this.session.project.id,
    });

    return report as PerformanceScore;
  }

  private async initializeCloudProject(project: WebDevProject): Promise<void> {
    await invoke("init_cloud_project", { project });
  }

  private addMessage(message: Omit<BuildMessage, "id" | "timestamp">): void {
    if (this.session) {
      const buildMessage: BuildMessage = {
        id: `msg-${Date.now()}`,
        timestamp: new Date(),
        ...message,
      };

      this.session.messages.push(buildMessage);
      this.emit("message", buildMessage);
    }
  }

  // Cleanup method to remove all event listeners
  destroy(): void {
    this.subscriptions.forEach((unsubscribe) => unsubscribe());
    this.subscriptions = [];
    this.messageHandlers = [];
  }
}

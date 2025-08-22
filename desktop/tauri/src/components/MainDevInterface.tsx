import React, { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/tauri";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/api/shell";
import { writeText } from "@tauri-apps/api/clipboard";
import { message as showDialog } from "@tauri-apps/api/dialog";

interface DevelopmentProject {
  id: string;
  name: string;
  githubRepo: string;
  cloudProvider: string;
  status: "initializing" | "building" | "ready" | "failed" | "updating";
  liveUrl: string;
  previewUrl: string;
  lastBuildTime?: number;
  performance?: {
    performance: number;
    accessibility: number;
    bestPractices: number;
    seo: number;
  };
  changes: number;
}

interface BuildMessage {
  id: string;
  timestamp: Date;
  content: string;
  status: "info" | "building" | "success" | "error";
  visible: boolean;
}

interface WebDevAgentConversation {
  id: string;
  instruction: string;
  response: string;
  timestamp: Date;
  status: "pending" | "processing" | "complete" | "error";
  urls?: string[];
}

const MainDevInterface: React.FC = () => {
  const [activeProject, setActiveProject] = useState<DevelopmentProject | null>(
    null,
  );
  const [messages, setMessages] = useState<BuildMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [projectHistory, setProjectHistory] = useState<DevelopmentProject[]>(
    [],
  );
  const [conversationHistory, setConversationHistory] = useState<
    WebDevAgentConversation[]
  >([]);

  useEffect(() => {
    setupWebSocketConnection();
    loadProjectHistory();
    setupEventListeners();
  }, []);

  const setupWebSocketConnection = useCallback(() => {
    const wsUrl = "wss://atom-cloud.webhook.app/dev-updates";
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      updateDeploymentStatus(data);
    };

    ws.onerror = (error) => {
      addMessage("WebSocket connection failed", "error");
    };
  }, []);

  const setupEventListeners = useCallback(async () => {
    await listen("cloud-deployment-ready", (event) => {
      const data = event.payload as DevelopmentProject;
      setActiveProject(data);
      addMessage("✅ Deployment ready! URL copied to clipboard", "success");

      if (data.liveUrl) {
        writeText(data.liveUrl);
      }
    });

    await listen("build-started", () => {
      setIsProcessing(true);
      addMessage("🔄 Starting cloud build...", "building");
    });

    await listen("build-failed", (event) => {
      const error = event.payload as string;
      setIsProcessing(false);
      addMessage(`❌ Build failed: ${error}`, "error");
      showDialog(error, { title: "Build Error", type: "error" });
    });
  }, []);

  const createNewProject = async (name: string, instruction: string) => {
    setIsProcessing(true);

    const project: Omit<DevelopmentProject, "id"> = {
      name,
      githubRepo: `atom-dev/${name}`,
      cloudProvider: "vercel",
      status: "initializing",
      liveUrl: "",
      previewUrl: "",
      changes: 0,
    };

    const newProject = await invoke("create_cloud_project", {
      project,
      instruction,
    });
    setActiveProject(newProject as DevelopmentProject);

    const conversation: WebDevAgentConversation = {
      id: `conv-${Date.now()}`,
      instruction,
      response: "Creating project in cloud...",
      timestamp: new Date(),
      status: "processing",
    };

    setConversationHistory((prev) => [conversation, ...prev]);
    addMessage(`🚀 Creating ${name} via cloud build...`, "building");
  };

  const processInstruction = async (instruction: string) => {
    if (!activeProject) {
      const projectName = prompt("Project name?");
      if (projectName) {
        await createNewProject(projectName, instruction);
      }
      return;
    }

    setIsProcessing(true);
    addMessage(`💭 Processing: ${instruction}`, "info");

    try {
      const result = await invoke("process_dev_instruction", {
        projectId: activeProject.id,
        instruction,
      });

      const conversation: WebDevAgentConversation = {
        id: `conv-${Date.now()}`,
        instruction,
        response: result as string,
        timestamp: new Date(),
        status: "complete",
      };

      setConversationHistory((prev) => [conversation, ...prev]);
      addMessage("✅ Instruction processed successfully", "success");
    } catch (error) {
      addMessage(`❌ Error processing instruction: ${error}`, "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const loadProjectHistory = async () => {
    try {
      const history = await invoke("get_project_history");
      setProjectHistory(history as DevelopmentProject[]);
    } catch (error) {
      console.error("Failed to load project history:", error);
    }
  };

  const updateDeploymentStatus = (data: any) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        timestamp: new Date(),
        content: data.message,
        status: data.status || "info",
        visible: true,
      },
    ]);
  };

  const addMessage = (content: string, status: BuildMessage["status"]) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        timestamp: new Date(),
        content,
        status,
        visible: true,
      },
    ]);
  };

  const handleChatSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (chatInput.trim() && !isProcessing) {
      processInstruction(chatInput.trim());
      setChatInput("");
    }
  };

  return (
    <div className="dev-interface">
      <div className="project-section">
        <h2>Active Project</h2>
        {activeProject ? (
          <div className="project-card">
            <h3>{activeProject.name}</h3>
            <p>Status: {activeProject.status}</p>
            {activeProject.liveUrl && (
              <button onClick={() => open(activeProject.liveUrl)}>
                Open Live Site
              </button>
            )}
          </div>
        ) : (
          <p>No active project. Start by describing what you want to build.</p>
        )}
      </div>

      <div className="chat-section">
        <h2>Development Assistant</h2>
        <form onSubmit={handleChatSubmit}>
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Describe what you want to build..."
            disabled={isProcessing}
          />
          <button type="submit" disabled={isProcessing}>
            {isProcessing ? "Processing..." : "Build"}
          </button>
        </form>

        <div className="messages">
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.status}`}>
              <span className="timestamp">
                {msg.timestamp.toLocaleTimeString()}
              </span>
              <span className="content">{msg.content}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="history-section">
        <h2>Project History</h2>
        {projectHistory.map((project) => (
          <div key={project.id} className="project-item">
            <h4>{project.name}</h4>
            <p>{project.status}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MainDevInterface;

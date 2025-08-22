import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/tauri";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/api/shell";
import { writeText } from "@tauri-apps/api/clipboard";

interface CloudDeployment {
  id: string;
  url: string;
  status: "building" | "ready" | "failed";
  timestamp: string;
  branch: string;
  commit: string;
  provider: "vercel" | "netlify" | "render";
  metrics: {
    buildTime: number;
    bundleSize: number;
    lighthouseScore: number;
  };
}

interface RepositoryInfo {
  name: string;
  branch: string;
  lastCommit: string;
  isClean: boolean;
}

interface DevelopmentSession {
  active: boolean;
  startTime: string;
  changes: number;
  previewUrl?: string;
}

const DevDashboard: React.FC = () => {
  const [deployments, setDeployments] = useState<CloudDeployment[]>([]);
  const [repoInfo, setRepoInfo] = useState<RepositoryInfo>({
    name: "atom-web-dev",
    branch: "main",
    lastCommit: "Loading...",
    isClean: true,
  });
  const [devSession, setDevSession] = useState<DevelopmentSession>({
    active: false,
    startTime: "",
    changes: 0,
  });
  const [atomStatus, setAtomStatus] = useState<string>("idle");
  const [buildPopup, setBuildPopup] = useState<CloudDeployment | null>(null);

  useEffect(() => {
    // Initialize Git connection
    checkRepoStatus();

    // Start WebSocket connection to cloud services
    connectToCloud();

    // Setup event listeners
    const cleanup = setupEventListeners();

    return cleanup;
  }, []);

  const checkRepoStatus = async () => {
    try {
      const status = await invoke("get_repo_status");
      setRepoInfo(status as RepositoryInfo);
    } catch (error) {
      console.error("Failed to get repo status:", error);
    }
  };

  const connectToCloud = async () => {
    // Connect to deployment WebSocket
    const unlisten1 = await listen<CloudDeployment>(
      "deployment-update",
      (event) => {
        setDeployments((prev) => [event.payload, ...prev].slice(0, 5));

        // Show popup for new deployments
        if (event.payload.status === "ready") {
          setBuildPopup(event.payload);
          setTimeout(() => setBuildPopup(null), 5000);
        }
      },
    );

    // Listen for AI agent updates
    const unlisten2 = await listen<string>("atom-status", (event) => {
      setAtomStatus(event.payload);
    });

    return () => {
      unlisten1();
      unlisten2();
    };
  };

  const setupEventListeners = () => {
    // File watcher for live reload
    const interval = setInterval(async () => {
      try {
        const changes = await invoke("get_uncommited_changes");
        const changeCount = (changes as string[]).length;

        if (changeCount > 0 && !devSession.active) {
          startDevelopmentSession();
        }

        setDevSession((prev) => ({ ...prev, changes: changeCount }));
      } catch (error) {
        console.error("Failed to check changes:", error);
      }
    }, 10000);

    return () => clearInterval(interval);
  };

  const startDevelopmentSession = () => {
    setDevSession({
      active: true,
      startTime: new Date().toISOString(),
      changes: 0,
    });
  };

  const previewDeployment = async (deployment: CloudDeployment) => {
    await open(deployment.url);
  };

  const copyPreviewUrl = async (url: string) => {
    await writeText(url);
  };

  const triggerBuild = async () => {
    try {
      await invoke("trigger_cloud_build");
      setAtomStatus("building");
    } catch (error) {
      console.error("Failed to trigger build:", error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ready":
        return "text-green-600";
      case "building":
        return "text-yellow-600";
      case "failed":
        return "text-red-600";
      default:
        return "text-gray-600";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ready":
        return "✅";
      case "building":
        return "🔄";
      case "failed":
        return "❌";
      default:
        return "⏳";
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div className="dev-dashboard p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="header mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
          Atom Development Dashboard
        </h1>
        <div className="status-bar flex items-center mt-2">
          <span
            className={`status-indicator mr-2 ${getStatusColor(atomStatus)}`}
          >
            {getStatusIcon(atomStatus)}
          </span>
          <span className="text-sm text-gray-600">Status: {atomStatus}</span>
        </div>
      </div>

      {/* Repository Info */}
      <div className="repo-card bg-white p-4 rounded-lg shadow mb-6">
        <h2 className="text-lg font-semibold mb-2">Repository</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-sm text-gray-500">Name:</span>
            <p className="font-medium">{repoInfo.name}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Branch:</span>
            <p className="font-medium">{repoInfo.branch}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Last Commit:</span>
            <p className="font-medium text-sm">{repoInfo.lastCommit}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Status:</span>
            <p
              className={`font-medium ${repoInfo.isClean ? "text-green-600" : "text-yellow-600"}`}
            >
              {repoInfo.isClean ? "Clean" : "Uncommitted Changes"}
            </p>
          </div>
        </div>
      </div>

      {/* Development Session */}
      <div className="session-card bg-white p-4 rounded-lg shadow mb-6">
        <h2 className="text-lg font-semibold mb-2">Development Session</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <span className="text-sm text-gray-500">Active:</span>
            <p
              className={`font-medium ${devSession.active ? "text-green-600" : "text-gray-600"}`}
            >
              {devSession.active ? "Yes" : "No"}
            </p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Changes:</span>
            <p className="font-medium">{devSession.changes}</p>
          </div>
          <div>
            <span className="text-sm text-gray-500">Duration:</span>
            <p className="font-medium">
              {devSession.startTime
                ? new Date(devSession.startTime).toLocaleTimeString()
                : "N/A"}
            </p>
          </div>
        </div>
      </div>

      {/* Build Controls */}
      <div className="build-controls mb-6">
        <button
          onClick={triggerBuild}
          disabled={atomStatus === "building"}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
        >
          {atomStatus === "building" ? "Building..." : "Trigger Build"}
        </button>
      </div>

      {/* Recent Deployments */}
      <div className="deployments-section">
        <h2 className="text-lg font-semibold mb-4">Recent Deployments</h2>
        {deployments.length === 0 ? (
          <p className="text-gray-500">No deployments yet</p>
        ) : (
          <div className="grid gap-4">
            {deployments.map((deployment) => (
              <div
                key={deployment.id}
                className="deployment-card bg-white p-4 rounded-lg shadow"
              >
                <div className="flex justify-between items-center mb-2">
                  <span
                    className={`font-medium ${getStatusColor(deployment.status)}`}
                  >
                    {getStatusIcon(deployment.status)} {deployment.status}
                  </span>
                  <span className="text-sm text-gray-500">
                    {formatTime(deployment.timestamp)}
                  </span>
                </div>
                <div className="mb-2">
                  <span className="text-sm text-gray-500">Branch:</span>
                  <p className="font-medium">{deployment.branch}</p>
                </div>
                <div className="mb-2">
                  <span className="text-sm text-gray-500">Provider:</span>
                  <p className="font-medium">{deployment.provider}</p>
                </div>
                {deployment.url && (
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => previewDeployment(deployment)}
                      className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700"
                    >
                      Preview
                    </button>
                    <button
                      onClick={() => copyPreviewUrl(deployment.url)}
                      className="bg-gray-600 text-white px-3 py-1 rounded text-sm hover:bg-gray-700"
                    >
                      Copy URL
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Build Popup */}
      {buildPopup && (
        <div className="fixed bottom-4 right-4 bg-green-600 text-white p-4 rounded-lg shadow-lg">
          <div className="flex items-center">
            <span className="mr-2">✅</span>
            <span>Deployment ready!</span>
          </div>
          <p className="text-sm mt-1">{buildPopup.url}</p>
        </div>
      )}
    </div>
  );
};

export default DevDashboard;

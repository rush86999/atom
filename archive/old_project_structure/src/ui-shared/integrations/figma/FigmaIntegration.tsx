import React, { useState, useEffect } from "react";

interface FigmaFile {
  id: string;
  name: string;
  key: string;
  thumbnail_url?: string;
  last_modified: string;
  editor_type: string;
  description?: string;
  url: string;
  team_id?: string;
  project_id?: string;
}

interface FigmaTeam {
  id: string;
  name: string;
  member_count: number;
  project_count: number;
  web_url: string;
}

interface FigmaComponent {
  id: string;
  name: string;
  description?: string;
  key: string;
  file_key: string;
  thumbnail_url?: string;
  created_at: string;
  updated_at: string;
}

interface FigmaIntegrationProps {
  userId: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  isConnected?: boolean;
}

export const FigmaIntegration: React.FC<FigmaIntegrationProps> = ({
  userId,
  onConnect,
  onDisconnect,
  isConnected = false,
}) => {
  const [activeTab, setActiveTab] = useState("files");
  const [files, setFiles] = useState<FigmaFile[]>([]);
  const [teams, setTeams] = useState<FigmaTeam[]>([]);
  const [components, setComponents] = useState<FigmaComponent[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "connected" | "disconnected" | "connecting"
  >(isConnected ? "connected" : "disconnected");

  // Mock data for demonstration
  const mockFiles: FigmaFile[] = [
    {
      id: "file-1",
      name: "Mobile App Design",
      key: "ABC123XYZ",
      thumbnail_url: "https://via.placeholder.com/200x150",
      last_modified: "2024-01-15T10:30:00Z",
      editor_type: "figma",
      description: "Complete mobile application design system",
      url: "https://figma.com/file/ABC123XYZ",
      team_id: "team-1",
    },
    {
      id: "file-2",
      name: "Website Redesign",
      key: "DEF456UVW",
      thumbnail_url: "https://via.placeholder.com/200x150",
      last_modified: "2024-01-14T15:45:00Z",
      editor_type: "figma",
      description: "Corporate website redesign project",
      url: "https://figma.com/file/DEF456UVW",
      team_id: "team-1",
    },
    {
      id: "file-3",
      name: "Dashboard UI Kit",
      key: "GHI789RST",
      thumbnail_url: "https://via.placeholder.com/200x150",
      last_modified: "2024-01-13T09:15:00Z",
      editor_type: "figma",
      description: "Reusable dashboard components library",
      url: "https://figma.com/file/GHI789RST",
      team_id: "team-2",
    },
  ];

  const mockTeams: FigmaTeam[] = [
    {
      id: "team-1",
      name: "Design Team",
      member_count: 8,
      project_count: 12,
      web_url: "https://figma.com/team/team-1",
    },
    {
      id: "team-2",
      name: "Product Team",
      member_count: 15,
      project_count: 25,
      web_url: "https://figma.com/team/team-2",
    },
  ];

  const mockComponents: FigmaComponent[] = [
    {
      id: "comp-1",
      name: "Primary Button",
      description: "Main call-to-action button",
      key: "1:23",
      file_key: "ABC123XYZ",
      thumbnail_url: "https://via.placeholder.com/100x80",
      created_at: "2024-01-10T14:20:00Z",
      updated_at: "2024-01-15T11:30:00Z",
    },
    {
      id: "comp-2",
      name: "Navigation Bar",
      description: "Main application navigation",
      key: "2:45",
      file_key: "ABC123XYZ",
      thumbnail_url: "https://via.placeholder.com/100x80",
      created_at: "2024-01-08T09:15:00Z",
      updated_at: "2024-01-14T16:45:00Z",
    },
    {
      id: "comp-3",
      name: "Input Field",
      description: "Text input component with validation",
      key: "3:67",
      file_key: "DEF456UVW",
      thumbnail_url: "https://via.placeholder.com/100x80",
      created_at: "2024-01-12T13:30:00Z",
      updated_at: "2024-01-13T10:20:00Z",
    },
  ];

  useEffect(() => {
    if (connectionStatus === "connected") {
      loadInitialData();
    }
  }, [connectionStatus]);

  const loadInitialData = async () => {
    setIsLoading(true);
    try {
      // Simulate API calls
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setFiles(mockFiles);
      setTeams(mockTeams);
      setComponents(mockComponents);
    } catch (error) {
      console.error("Failed to load Figma data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    setConnectionStatus("connecting");
    try {
      // Simulate OAuth connection
      await new Promise((resolve) => setTimeout(resolve, 2000));
      setConnectionStatus("connected");
      onConnect?.();
    } catch (error) {
      setConnectionStatus("disconnected");
      console.error("Failed to connect to Figma:", error);
    }
  };

  const handleDisconnect = async () => {
    try {
      setConnectionStatus("disconnected");
      setFiles([]);
      setTeams([]);
      setComponents([]);
      onDisconnect?.();
    } catch (error) {
      console.error("Failed to disconnect from Figma:", error);
    }
  };

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (query.trim()) {
      // Simulate search API call
      setIsLoading(true);
      await new Promise((resolve) => setTimeout(resolve, 500));
      const filteredFiles = mockFiles.filter(
        (file) =>
          file.name.toLowerCase().includes(query.toLowerCase()) ||
          file.description?.toLowerCase().includes(query.toLowerCase()),
      );
      setFiles(filteredFiles);
      setIsLoading(false);
    } else {
      setFiles(mockFiles);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (connectionStatus === "disconnected") {
    return (
      <div className="w-full p-6 border rounded-lg">
        <div className="mb-4">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center">
              📐
            </div>
            Figma Integration
          </h2>
          <p className="text-gray-600">
            Connect your Figma account to manage design files, teams, and
            components directly from ATOM.
          </p>
        </div>
        <div className="bg-gray-100 p-4 rounded-lg mb-4">
          <h4 className="font-semibold mb-2">Features</h4>
          <ul className="space-y-1 text-sm text-gray-600">
            <li>• Browse and search design files</li>
            <li>• Manage team projects and members</li>
            <li>• Access component libraries</li>
            <li>• Real-time collaboration tools</li>
            <li>• Version history tracking</li>
          </ul>
        </div>
        <button
          onClick={handleConnect}
          className="w-full bg-purple-600 hover:bg-purple-700 text-white py-3 px-4 rounded-lg font-medium"
        >
          📐 Connect Figma Account
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-6 border rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-500 rounded-lg flex items-center justify-center">
              📐
            </div>
            <div>
              <h2 className="text-xl font-bold">Figma Design Platform</h2>
              <p className="text-gray-600">
                Design collaboration and file management
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                connectionStatus === "connected"
                  ? "bg-green-100 text-green-800"
                  : "bg-yellow-100 text-yellow-800"
              }`}
            >
              {connectionStatus === "connected"
                ? "✅ Connected"
                : "🔄 Connecting..."}
            </span>
            <button
              className="border border-gray-300 px-3 py-1 rounded text-sm hover:bg-gray-50"
              onClick={handleDisconnect}
            >
              Disconnect
            </button>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="p-6 border rounded-lg">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder="Search files, components, teams..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>
          <button className="border border-gray-300 px-4 py-2 rounded-lg hover:bg-gray-50">
            🔍 Filter
          </button>
          <button className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700">
            ➕ New File
          </button>
        </div>
      </div>

      {/* Main Content Tabs */}
      <div className="space-y-4">
        <div className="grid grid-cols-4 gap-2 border-b">
          <button
            onClick={() => setActiveTab("files")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "files"
                ? "border-purple-500 text-purple-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            📄 Files
            <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
              {files.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("teams")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "teams"
                ? "border-purple-500 text-purple-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            👥 Teams
            <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
              {teams.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("components")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "components"
                ? "border-purple-500 text-purple-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            🧩 Components
            <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
              {components.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "analytics"
                ? "border-purple-500 text-purple-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            📊 Analytics
          </button>
        </div>

        {/* Files Tab */}
        {activeTab === "files" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Design Files</h3>
                <p className="text-gray-600">
                  Browse and manage your Figma design files
                </p>
              </div>
              <div>
                {isLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <span className="animate-spin mr-2">🔄</span>
                    Loading files...
                  </div>
                ) : files.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <div className="text-4xl mb-4">📄</div>
                    <p>No files found</p>
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {files.map((file) => (
                      <div
                        key={file.id}
                        className="border rounded-lg overflow-hidden"
                      >
                        <div className="aspect-video bg-gray-100 relative">
                          {file.thumbnail_url ? (
                            <img
                              src={file.thumbnail_url}
                              alt={file.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <span className="text-2xl">📄</span>
                            </div>
                          )}
                        </div>
                        <div className="p-4">
                          <div className="flex items-start justify-between mb-2">
                            <h3 className="font-semibold text-sm line-clamp-2 flex-1">
                              {file.name}
                            </h3>
                            <a
                              href={file.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-gray-500 hover:text-gray-700"
                            >
                              ↗️
                            </a>
                          </div>
                          {file.description && (
                            <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                              {file.description}
                            </p>
                          )}
                          <div className="flex items-center justify-between text-xs text-gray-500">
                            <span>
                              Modified {formatDate(file.last_modified)}
                            </span>
                            <span className="border border-gray-300 px-2 py-1 rounded text-xs">
                              {file.editor_type}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Teams Tab */}
        {activeTab === "teams" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Teams & Projects</h3>
                <p className="text-gray-600">
                  Manage your design teams and collaborative projects
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 font-medium">Team Name</th>
                      <th className="text-left py-2 font-medium">Members</th>
                      <th className="text-left py-2 font-medium">Projects</th>
                      <th className="text-left py-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teams.map((team) => (
                      <tr key={team.id} className="border-b">
                        <td className="py-3 font-medium">{team.name}</td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <span>👥</span>
                            {team.member_count} members
                          </div>
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <span>📄</span>
                            {team.project_count} projects
                          </div>
                        </td>
                        <td className="py-3">
                          <a
                            href={team.web_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="border border-gray-300 px-3 py-1 rounded text-sm hover:bg-gray-50 inline-flex items-center gap-1"
                          >
                            ↗️ View Team
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Components Tab */}
        {activeTab === "components" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Component Library</h3>
                <p className="text-gray-600">
                  Browse and manage reusable design components
                </p>
              </div>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {components.map((component) => (
                  <div
                    key={component.id}
                    className="border rounded-lg overflow-hidden"
                  >
                    <div className="aspect-square bg-gray-100 relative">
                      {component.thumbnail_url ? (
                        <img
                          src={component.thumbnail_url}
                          alt={component.name}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <span className="text-2xl">🧩</span>
                        </div>
                      )}
                    </div>
                    <div className="p-4">
                      <h4 className="font-semibold text-sm mb-1">
                        {component.name}
                      </h4>
                      {component.description && (
                        <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                          {component.description}
                        </p>
                      )}
                      <div className="text-xs text-gray-500">
                        <div>Created: {formatDate(component.created_at)}</div>
                        <div>Updated: {formatDate(component.updated_at)}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === "analytics" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Design Analytics</h3>
                <p className="text-gray-600">
                  View usage statistics and design metrics
                </p>
              </div>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">
                    {files.length}
                  </div>
                  <div className="text-sm text-blue-600">Design Files</div>
                </div>
                <div className="bg-green-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {teams.length}
                  </div>
                  <div className="text-sm text-green-600">Teams</div>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">
                    {components.length}
                  </div>
                  <div className="text-sm text-purple-600">Components</div>
                </div>
              </div>
              <div className="mt-6">
                <h4 className="font-semibold mb-3">Recent Activity</h4>
                <div className="space-y-2">
                  {files.slice(0, 5).map((file) => (
                    <div
                      key={file.id}
                      className="flex items-center justify-between py-2 border-b"
                    >
                      <span className="text-sm">{file.name}</span>
                      <span className="text-xs text-gray-500">
                        Modified {formatDate(file.last_modified)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

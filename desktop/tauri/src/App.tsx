import React, { useState } from "react";
import Chat from "./Chat";
import Sales from "./Sales";
import Projects from "./Projects";
import Support from "./Support";
import UserRole, { Role } from "./UserRole";
import FeatureViewGuard from "./components/FeatureViewGuard";
import ProjectHealth from './ProjectHealth';
import CompetitorAnalysis from './CompetitorAnalysis';
import LearningAssistant from './LearningAssistant';
import Finance from './Finance';
import "./App.css";

// Define the roles available in the desktop application.
const AVAILABLE_ROLES: Role[] = [
  "sales",
  "support",
  "developer",
  "project_manager",
  "financial_analyst",
];

/**
 * The main application component for the desktop app.
 * It handles navigation between different views (Chat, Sales, Settings)
 * and manages role-based access to features.
 */
function App() {
  // State to manage the currently displayed view. Defaults to 'chat'.
  const [activeView, setActiveView] = useState<
    "chat" | "sales" | "projects" | "support" | "settings" | "project-health" | "competitor-analysis" | "learning-assistant" | "finance"
  >("chat");
  // State to track which roles the user has activated.
  const [activeRoles, setActiveRoles] = useState<Role[]>([]);

  /**
   * Toggles a role's active status.
   * If the role is already active, it's removed. Otherwise, it's added.
   * @param {Role} role - The role to toggle.
   */
  const handleToggleRole = (role: Role) => {
    setActiveRoles((prevRoles) =>
      prevRoles.includes(role)
        ? prevRoles.filter((r) => r !== role)
        : [...prevRoles, role],
    );
  };

  const renderContent = () => {
    switch (activeView) {
      case "chat":
        return <Chat />;
      case "sales":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="sales"
            roleName="Sales"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Sales />
          </FeatureViewGuard>
        );
      case "projects":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="project_manager"
            roleName="Project Manager"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Projects />
          </FeatureViewGuard>
        );
      case "support":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="support"
            roleName="Support"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Support />
          </FeatureViewGuard>
        );
      case "settings":
        return (
          <UserRole
            activeRoles={activeRoles}
            availableRoles={AVAILABLE_ROLES}
            onToggleRole={handleToggleRole}
          />
        );
      case "project-health":
        return <ProjectHealth />;
      case "competitor-analysis":
        return <CompetitorAnalysis />;
      case "learning-assistant":
        return <LearningAssistant />;
      case "finance":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="financial_analyst"
            roleName="Financial Analyst"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Finance />
          </FeatureViewGuard>
        );
      default:
        return <Chat />;
    }
  };

  return (
    <div className="App">
      <nav className="app-nav">
        <button
          onClick={() => setActiveView("chat")}
          className={activeView === "chat" ? "active" : ""}
        >
          Chat
        </button>
        <button
          onClick={() => setActiveView("sales")}
          className={activeView === "sales" ? "active" : ""}
        >
          Sales
        </button>
        <button
          onClick={() => setActiveView("projects")}
          className={activeView === "projects" ? "active" : ""}
        >
          Projects
        </button>
        <button
          onClick={() => setActiveView("support")}
          className={activeView === "support" ? "active" : ""}
        >
          Support
        </button>
        <button
          onClick={() => setActiveView("project-health")}
          className={activeView === "project-health" ? "active" : ""}
        >
          Project Health
        </button>
        <button
          onClick={() => setActiveView("competitor-analysis")}
          className={activeView === "competitor-analysis" ? "active" : ""}
        >
          Competitor Analysis
        </button>
        <button
          onClick={() => setActiveView("learning-assistant")}
          className={activeView === "learning-assistant" ? "active" : ""}
        >
          Learning Assistant
        </button>
        <button
          onClick={() => setActiveView("settings")}
          className={activeView === "settings" ? "active" : ""}
        >
          Settings
        </button>
        <button
            onClick={() => setActiveView("finance")}
            className={activeView === "finance" ? "active" : ""}
        >
            Finance
        </button>
      </nav>
      <main className="app-content">{renderContent()}</main>
    </div>
  );
}

export default App;

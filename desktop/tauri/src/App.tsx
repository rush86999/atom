import React, { useState } from "react";
import Chat from "./Chat";
import Sales from "./Sales";
import Projects from "./Projects";
import Support from "./Support";
import UserRole, { Role } from "./UserRole";
import Research from "./Research";
import Social from "./Social";
import Content from "./Content";
import Shopping from "./Shopping";
import SmartSearch from "./SmartSearch";
import Dashboard from "./Dashboard";
import FeatureViewGuard from "./components/FeatureViewGuard";
import ProjectHealth from './ProjectHealth';
import CompetitorAnalysis from './CompetitorAnalysis';
import LearningAssistant from './LearningAssistant';
import Finance from './Finance';
import Integrations from "./components/Integrations";
import "./App.css";

// Define the roles available in the desktop application.
const AVAILABLE_ROLES: Role[] = [
  "sales",
  "support",
  "developer",
  "project_manager",
  "financial_analyst",
  "researcher",
  "social_media_manager",
  "content_creator",
  "shopper",
];

/**
 * The main application component for the desktop app.
 * It handles navigation between different views (Chat, Sales, Settings)
 * and manages role-based access to features.
 */
function App() {
  // State to manage the currently displayed view. Defaults to 'chat'.
  const [activeView, setActiveView] = useState<
    "chat" | "sales" | "projects" | "support" | "settings" | "project-health" | "competitor-analysis" | "learning-assistant" | "finance" | "research" | "social" | "content" | "shopping" | "integrations"
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
      case "integrations":
        return <Integrations />;
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
      case "research":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="researcher"
            roleName="Researcher"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Research />
          </FeatureViewGuard>
        );
      case "social":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="social_media_manager"
            roleName="Social Media Manager"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Social />
          </FeatureViewGuard>
        );
      case "content":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="content_creator"
            roleName="Content Creator"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Content />
          </FeatureViewGuard>
        );
      case "shopping":
        return (
          <FeatureViewGuard
            activeRoles={activeRoles}
            requiredRole="shopper"
            roleName="Shopper"
            onNavigateToSettings={() => setActiveView("settings")}
          >
            <Shopping />
          </FeatureViewGuard>
        );
      default:
        return <Chat />;
    }
  };

  return (
    <div className="App">
      <Dashboard setActiveView={setActiveView} />
      <div className="content">
        {renderContent()}
      </div>
    </div>
  );
}

export default App;

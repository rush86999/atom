import React from "react";
import { Dispatch, SetStateAction } from "react";

interface DashboardProps {
  setActiveView: Dispatch<
    SetStateAction<
      | "sales"
      | "support"
      | "chat"
      | "github-chat"
      | "outlook-chat"
      | "projects"
      | "settings"
      | "integrations"
      | "automations"
      | "content"
      | "project-health"
      | "competitor-analysis"
      | "learning-assistant"
      | "finance"
      | "research"
      | "social"
      | "shopping"
      | "calendar"
      | "tasks"
      | "communication"
    >
  >;
}

const Dashboard = ({ setActiveView }: DashboardProps) => {
  return (
    <div className="navigation">
      <button onClick={() => setActiveView("chat" as any)}>Chat</button>
      <button onClick={() => setActiveView("github-chat" as any)}>GitHub Chat</button>
      <button onClick={() => setActiveView("outlook-chat" as any)}>Outlook Chat</button>
      <button onClick={() => setActiveView("sales" as any)}>Sales</button>
      <button onClick={() => setActiveView("projects" as any)}>Projects</button>
      <button onClick={() => setActiveView("support" as any)}>Support</button>
      <button onClick={() => setActiveView("settings" as any)}>Settings</button>
      <button onClick={() => setActiveView("integrations" as any)}>
        Integrations
      </button>
      <button onClick={() => setActiveView("automations" as any)}>
        Automations
      </button>
      <button onClick={() => setActiveView("calendar" as any)}>Calendar</button>
      <button onClick={() => setActiveView("tasks" as any)}>Tasks</button>
      <button onClick={() => setActiveView("communication" as any)}>
        Communication
      </button>
      <button onClick={() => setActiveView("finance" as any)}>Finance</button>
      <button onClick={() => setActiveView("research" as any)}>Research</button>
    </div>
  );
};

export default Dashboard;

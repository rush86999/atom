import React from "react";
import { Dispatch, SetStateAction } from "react";

interface DashboardProps {
  setActiveView: Dispatch<
    SetStateAction<
      | "sales"
      | "support"
      | "chat"
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
    >
  >;
}

const Dashboard = ({ setActiveView }: DashboardProps) => {
  return (
    <div className="navigation">
      <button onClick={() => setActiveView("chat" as any)}>Chat</button>
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
    </div>
  );
};

export default Dashboard;

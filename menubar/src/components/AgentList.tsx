import type { AgentSummary } from "../types";

interface AgentListProps {
  agents: AgentSummary[];
  getMaturityColor: (maturity: string) => string;
}

export default function AgentList({ agents, getMaturityColor }: AgentListProps) {
  if (agents.length === 0) {
    return (
      <div style={{ padding: "12px", color: "#888", fontSize: "12px" }}>
        No recent agents
      </div>
    );
  }

  return (
    <ul className="item-list">
      {agents.map((agent) => (
        <li key={agent.id}>
          <div className="item-name">
            {agent.name}
            <span className={`badge ${getMaturityColor(agent.maturity_level)}`}>
              {agent.maturity_level}
            </span>
          </div>
          <div className="item-meta">
            {agent.execution_count} executions
            {agent.last_execution && (
              <span>
                {" • Last: {new Date(agent.last_execution).toLocaleDateString()}
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

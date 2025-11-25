import React from 'react';
import AgentManager from '../components/Agents/AgentManager';

const AgentsPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <AgentManager />
    </div>
  );
};

export default AgentsPage;

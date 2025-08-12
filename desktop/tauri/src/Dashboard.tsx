import React from "react";

const Dashboard = ({ setActiveView }) => {
  return (
    <div className="navigation">
      <button onClick={() => setActiveView('chat')}>Chat</button>
      <button onClick={() => setActiveView('sales')}>Sales</button>
      <button onClick={() => setActiveView('projects')}>Projects</button>
      <button onClick={() => setActiveView('support')}>Support</button>
      <button onClick={() => setActiveView('settings')}>Settings</button>
      <button onClick={() => setActiveView('integrations')}>Integrations</button>
      <button onClick={() => setActiveView('automations')}>Automations</button>
    </div>
  );
};

export default Dashboard;

import React from 'react';
import SystemStatusDashboard from '../components/SystemStatusDashboard';

const SystemStatusPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <SystemStatusDashboard />
    </div>
  );
};

export default SystemStatusPage;

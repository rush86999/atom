import React from 'react';
import CommunicationCommandCenter from '@/components/dashboards/CommunicationCommandCenter';

const CommunicationPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white">
      <CommunicationCommandCenter />
    </div>
  );
};

export default CommunicationPage;

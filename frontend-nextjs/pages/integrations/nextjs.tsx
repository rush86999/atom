/**
 * Next.js Integration Page
 * Dedicated page for Next.js/Vercel integration
 */

import React, { useState } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import the NextjsManager component
const NextjsManager = dynamic(
  () => import('../../../../src/ui-shared/integrations/nextjs/components/NextjsManager'),
  { 
    ssr: false,
    loading: () => (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh' 
      }}>
        <div>Loading Next.js Integration...</div>
      </div>
    )
  }
);

const NextjsIntegrationPage: React.FC = () => {
  const [atomIngestionPipeline, setAtomIngestionPipeline] = useState<any>(null);
  const [userId, setUserId] = useState<string>('demo-user');

  const handleConfigurationChange = (config: any) => {
    console.log('Configuration changed:', config);
  };

  const handleIngestionComplete = (result: any) => {
    console.log('Ingestion complete:', result);
  };

  const handleError = (error: Error) => {
    console.error('Integration error:', error);
  };

  // Mock ATOM ingestion pipeline for demo
  React.useEffect(() => {
    const mockPipeline = {
      executeSkill: async (skill: string, params: any) => {
        console.log(`Executing skill: ${skill}`, params);
        return {
          success: true,
          data: { message: `${skill} executed successfully` }
        };
      },
      registerIntegration: async (integration: any) => {
        console.log('Registering integration:', integration);
        return { success: true };
      }
    };
    setAtomIngestionPipeline(mockPipeline);
  }, []);

  return (
    <div style={{ minHeight: '100vh' }}>
      <NextjsManager
        atomIngestionPipeline={atomIngestionPipeline}
        onConfigurationChange={handleConfigurationChange}
        onIngestionComplete={handleIngestionComplete}
        onError={handleError}
        userId={userId}
      />
    </div>
  );
};

export default NextjsIntegrationPage;
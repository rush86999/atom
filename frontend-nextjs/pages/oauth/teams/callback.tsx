/**
 * Microsoft Teams OAuth Callback Page
 * Uses shared TeamsCallback component from src folder
 */

import React from 'react';
import dynamic from 'next/dynamic';

// Dynamically import the TeamsCallback component from shared components
const TeamsCallback = dynamic(
  () => import('../../../../src/ui-shared/integrations/teams/components/TeamsCallback'),
  { ssr: false }
);

const TeamsCallbackPage: React.FC = () => {
  return <TeamsCallback />;
};

export default TeamsCallbackPage;

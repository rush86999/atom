/**
 * Trello OAuth Callback Page
 * Uses shared TrelloCallback component from src folder
 */

import React from 'react';
import dynamic from 'next/dynamic';

// Dynamically import the TrelloCallback component from shared components
const TrelloCallback = dynamic(
  () => import('../../../../src/ui-shared/integrations/trello/components/TrelloCallback'),
  { ssr: false }
);

const TrelloCallbackPage: React.FC = () => {
  return <TrelloCallback />;
};

export default TrelloCallbackPage;

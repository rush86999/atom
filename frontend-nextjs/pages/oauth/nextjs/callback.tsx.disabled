/**
 * Next.js OAuth Callback Page
 * Uses shared NextjsCallback component from src folder
 */

import React from 'react';
import dynamic from 'next/dynamic';

// Dynamically import the NextjsCallback component from shared components
const NextjsCallback = dynamic(
  () => import('../../../../src/ui-shared/integrations/nextjs/components/NextjsCallback'),
  { ssr: false }
);

const NextjsCallbackPage: React.FC = () => {
  return <NextjsCallback />;
};

export default NextjsCallbackPage;
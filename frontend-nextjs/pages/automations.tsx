import React from 'react';
import { Box } from '@chakra-ui/react';
import WorkflowAutomation from '../components/WorkflowAutomation';

const AutomationsPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="gray.50">
      <WorkflowAutomation />
    </Box>
  );
};

export default AutomationsPage;

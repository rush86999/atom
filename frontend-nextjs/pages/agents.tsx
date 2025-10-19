import React from 'react';
import { Box } from '@chakra-ui/react';
import AgentManager from '../components/Agents/AgentManager';

const AgentsPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="gray.50">
      <AgentManager />
    </Box>
  );
};

export default AgentsPage;

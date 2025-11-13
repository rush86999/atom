import React from 'react';
import { Box } from '@chakra-ui/react';
import SystemStatusDashboard from '../components/SystemStatusDashboard';

const SystemStatusPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="gray.50">
      <SystemStatusDashboard />
    </Box>
  );
};

export default SystemStatusPage;

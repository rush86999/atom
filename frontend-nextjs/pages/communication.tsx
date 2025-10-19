import React from 'react';
import { Box } from '@chakra-ui/react';
import CommunicationHub from '../components/CommunicationHub';

const CommunicationPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="gray.50">
      <CommunicationHub />
    </Box>
  );
};

export default CommunicationPage;

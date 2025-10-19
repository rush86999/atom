import React from 'react';
import { Box } from '@chakra-ui/react';
import CalendarManagement from '../components/CalendarManagement';

const CalendarPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="gray.50">
      <CalendarManagement />
    </Box>
  );
};

export default CalendarPage;

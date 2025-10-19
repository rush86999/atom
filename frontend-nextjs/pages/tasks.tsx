import React from 'react';
import { Box } from '@chakra-ui/react';
import TaskManagement from '../components/TaskManagement';

const TasksPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="gray.50">
      <TaskManagement />
    </Box>
  );
};

export default TasksPage;

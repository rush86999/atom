import React from 'react';
import TaskManagement from '../components/TaskManagement';

const TasksPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <TaskManagement />
    </div>
  );
};

export default TasksPage;

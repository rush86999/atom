import React from 'react';
import TaskManagement from '../components/TaskManagement';

const TasksPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-800" data-testid="new-task-btn">
      <TaskManagement />
    </div>
  );
};

export default TasksPage;

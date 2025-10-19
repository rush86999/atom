import React from "react";
import SharedTaskManagement from "../../../src/ui-shared/task/TaskManagement";

const Tasks: React.FC = () => {
  const handleTaskCreate = (task: any) => {
    console.log("Creating task:", task);
    // TODO: Implement actual task creation logic
  };

  const handleTaskUpdate = (taskId: string, updates: any) => {
    console.log("Updating task:", taskId, updates);
    // TODO: Implement actual task update logic
  };

  const handleTaskDelete = (taskId: string) => {
    console.log("Deleting task:", taskId);
    // TODO: Implement actual task deletion logic
  };

  const handleProjectCreate = (project: any) => {
    console.log("Creating project:", project);
    // TODO: Implement actual project creation logic
  };

  const handleProjectUpdate = (projectId: string, updates: any) => {
    console.log("Updating project:", projectId, updates);
    // TODO: Implement actual project update logic
  };

  return (
    <div className="tasks-page">
      <SharedTaskManagement
        onTaskCreate={handleTaskCreate}
        onTaskUpdate={handleTaskUpdate}
        onTaskDelete={handleTaskDelete}
        onProjectCreate={handleProjectCreate}
        onProjectUpdate={handleProjectUpdate}
      />
    </div>
  );
};

export default Tasks;

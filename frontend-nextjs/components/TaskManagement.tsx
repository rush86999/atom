import React from "react";
import TaskManagement from "./shared/TaskManagement";

const TaskManagementWrapper: React.FC = () => {
  return (
    <TaskManagement
      showNavigation={true}
      compactView={false}
      onTaskCreate={(task) => {
        console.log("Task created:", task);
        // TODO: Implement API call to backend
      }}
      onTaskUpdate={(taskId, updates) => {
        console.log("Task updated:", taskId, updates);
        // TODO: Implement API call to backend
      }}
      onTaskDelete={(taskId) => {
        console.log("Task deleted:", taskId);
        // TODO: Implement API call to backend
      }}
      onProjectCreate={(project) => {
        console.log("Project created:", project);
        // TODO: Implement API call to backend
      }}
      onProjectUpdate={(projectId, updates) => {
        console.log("Project updated:", projectId, updates);
        // TODO: Implement API call to backend
      }}
    />
  );
};

export default TaskManagementWrapper;

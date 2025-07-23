import React, { useEffect } from "react";
import {
  useProject,
  ProjectProvider,
} from "../../contexts/projects/projectContext";
import FeaturePageGuard from "../../lib/components/FeaturePageGuard";

/**
 * The main content component for the Project Status Reporter page.
 * It handles fetching, displaying, and refreshing project data,
 * and ensures the user has the correct role to view the content.
 */
const ProjectPageContent = () => {
  const { projectData, loading, error, fetchProjectData } = useProject();

  useEffect(() => {
    // Fetch data when the component mounts.
    fetchProjectData();
  }, [fetchProjectData]);

  // Show a loading message while fetching data.
  if (loading && !projectData) {
    return <div>Loading project data...</div>;
  }

  // Show an error message if fetching fails.
  if (error) {
    return <div>Error: {error.message}</div>;
  }

  // Helper to determine the color for the project status badge.
  const getStatusColor = (status: "On Track" | "At Risk" | "Off Track") => {
    switch (status) {
      case "On Track":
        return "green";
      case "At Risk":
        return "orange";
      case "Off Track":
        return "red";
      default:
        return "grey";
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Project Status Reporter</h1>
        <button
          onClick={() => fetchProjectData()}
          disabled={loading}
          style={{ padding: "10px 15px", cursor: "pointer" }}
        >
          {loading ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>

      {projectData ? (
        <div>
          {/* Project Overview Section */}
          <div style={{ marginBottom: "30px" }}>
            <h2>
              {projectData.project.name}{" "}
              <span
                style={{
                  backgroundColor: getStatusColor(projectData.project.status),
                  color: "white",
                  padding: "4px 8px",
                  borderRadius: "12px",
                  fontSize: "0.8em",
                  verticalAlign: "middle",
                }}
              >
                {projectData.project.status}
              </span>
            </h2>
            <p>{projectData.project.description}</p>
          </div>

          {/* Tasks Section */}
          <div style={{ marginBottom: "30px" }}>
            <h3>Tasks</h3>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {projectData.tasks.map((task) => (
                <li
                  key={task.id}
                  style={{ borderBottom: "1px solid #eee", padding: "10px 0" }}
                >
                  <strong>{task.title}</strong> - {task.assignee} ({task.status}
                  )
                </li>
              ))}
            </ul>
          </div>

          {/* Team Section */}
          <div style={{ marginBottom: "30px" }}>
            <h3>Team</h3>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {projectData.team.map((member) => (
                <li key={member.id} style={{ padding: "5px 0" }}>
                  {member.name} ({member.role})
                </li>
              ))}
            </ul>
          </div>

          {/* Activity Stream Section */}
          <div>
            <h3>Recent Activity</h3>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {projectData.activityStream.map((activity) => (
                <li
                  key={activity.id}
                  style={{ borderBottom: "1px solid #eee", padding: "10px 0" }}
                >
                  <span style={{ color: "#666" }}>
                    {new Date(activity.timestamp).toLocaleString()}:
                  </span>{" "}
                  {activity.description}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <p>No project data available. Click "Refresh Data" to load.</p>
      )}
    </div>
  );
};

/**
 * The main Projects page component.
 * It wraps the page content with the ProjectProvider to ensure
 * the context is available to all child components.
 */
const ProjectsPage = () => (
  <FeaturePageGuard
    role="project_manager"
    roleName="Project Manager Agent Skill"
  >
    <ProjectProvider>
      <ProjectPageContent />
    </ProjectProvider>
  </FeaturePageGuard>
);

export default ProjectsPage;

import React, { useEffect, useCallback } from "react";
import { useDataFetching } from "./hooks/useDataFetching";

// Define TypeScript interfaces for our data structures for type safety.
interface Project {
  id: string;
  name: string;
  description: string;
  status: "On Track" | "At Risk" | "Off Track";
}

interface Task {
  id: string;
  title: string;
  status: "To Do" | "In Progress" | "Done";
  assignee: string;
}

interface TeamMember {
  id: string;
  name: string;
  role: string;
}

interface Activity {
  id: string;
  description: string;
  timestamp: string;
}

interface ProjectData {
  project: Project;
  tasks: Task[];
  team: TeamMember[];
  activityStream: Activity[];
}

/**
 * Project Status Reporter component for the desktop application.
 * It simulates fetching project data and displays it in a dashboard format.
 */
const Projects: React.FC = () => {
  const {
    data: projectData,
    loading,
    error,
    fetchData,
  } = useDataFetching<ProjectData>();

  // Function to simulate fetching data from a project management tool.
  const fetchProjectData = useCallback(() => {
    const dataFetcher = () =>
      new Promise<ProjectData>((resolve) => {
        setTimeout(() => {
          const mockDesktopProjectData: ProjectData = {
            project: {
              id: "proj-apollo-desktop",
              name: "Project Apollo (Desktop)",
              description:
                "A mission to revolutionize space travel through AI-driven logistics on desktop.",
              status: "At Risk",
            },
            tasks: [
              {
                id: "task-d-101",
                title: "Desktop: Develop propulsion system prototype",
                status: "In Progress",
                assignee: "Alex Ray",
              },
              {
                id: "task-d-102",
                title: "Desktop: Design mission control UI",
                status: "To Do",
                assignee: "Casey Jordan",
              },
              {
                id: "task-d-103",
                title: "Desktop: Set up local build environment",
                status: "Done",
                assignee: "Dev Team",
              },
            ],
            team: [
              {
                id: "team-d-1",
                name: "Alex Ray (Desktop)",
                role: "Lead Engineer",
              },
              {
                id: "team-d-2",
                name: "Casey Jordan (Desktop)",
                role: "UX/UI Designer",
              },
            ],
            activityStream: [
              {
                id: "act-d-1",
                description:
                  "Alex Ray flagged a risk in the propulsion system development.",
                timestamp: "2024-08-01T11:00:00Z",
              },
              {
                id: "act-d-2",
                description:
                  'A new task "Design mission control UI" was assigned to Casey Jordan.',
                timestamp: "2024-07-31T16:00:00Z",
              },
            ],
          };
          resolve(mockDesktopProjectData);
        }, 1000); // 1-second delay.
      });
    fetchData(dataFetcher);
  }, [fetchData]);

  // Fetch data when the component first mounts.
  useEffect(() => {
    fetchProjectData();
  }, [fetchProjectData]);

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

  if (loading && !projectData) {
    return <div style={{ padding: "20px" }}>Loading project data...</div>;
  }

  if (error) {
    return (
      <div style={{ padding: "20px", color: "red" }}>
        Error: {error.message}
      </div>
    );
  }

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Project Status Reporter (Desktop)</h1>
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

export default Projects;

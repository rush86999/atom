import React, {
  createContext,
  useContext,
  ReactNode,
  useCallback,
} from "react";
import { useDataFetching } from "../../lib/hooks/useDataFetching";

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

// Define the shape of the context data
interface ProjectContextType {
  projectData: ProjectData | null;
  loading: boolean;
  error: Error | null;
  fetchProjectData: () => Promise<void>;
}

// Create the context with a default value
const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

// Custom hook to use the ProjectContext
export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
};

// Create the provider component
export const ProjectProvider = ({ children }: { children: ReactNode }) => {
  const {
    data: projectData,
    loading,
    error,
    fetchData,
  } = useDataFetching<ProjectData>();

  // Function to fetch data from the project management API, memoized with useCallback.
  const fetchProjectData = useCallback(async () => {
    await fetchData("/api/projects/data");
  }, [fetchData]);

  const value = {
    projectData,
    loading,
    error,
    fetchProjectData,
  };

  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
};

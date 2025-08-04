import { ReactNode } from "react";
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
interface ProjectContextType {
    projectData: ProjectData | null;
    loading: boolean;
    error: Error | null;
    fetchProjectData: () => Promise<void>;
}
export declare const useProject: () => ProjectContextType;
export declare const ProjectProvider: ({ children }: {
    children: ReactNode;
}) => JSX.Element;
export {};

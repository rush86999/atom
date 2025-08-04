import type { NextApiRequest, NextApiResponse } from 'next';
interface Project {
    id: string;
    name: string;
    description: string;
    status: 'On Track' | 'At Risk' | 'Off Track';
}
interface Task {
    id: string;
    title: string;
    status: 'To Do' | 'In Progress' | 'Done';
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
 * API handler for fetching project management data.
 * Simulates a network request with a 1-second delay.
 *
 * @param {NextApiRequest} req - The incoming API request.
 * @param {NextApiResponse<ProjectData>} res - The outgoing API response.
 */
export default function handler(req: NextApiRequest, res: NextApiResponse<ProjectData>): void;
export {};

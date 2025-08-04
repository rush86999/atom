import type { NextApiRequest, NextApiResponse } from 'next';

// Define TypeScript interfaces for our data structures for type safety.
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
  assignee: string; // Team member's name
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

// This is our mock database for project management data (like Jira or Asana).
const mockProjectData: ProjectData = {
  project: {
    id: 'proj-apollo',
    name: 'Project Apollo',
    description:
      'A mission to revolutionize space travel through AI-driven logistics.',
    status: 'On Track',
  },
  tasks: [
    {
      id: 'task-101',
      title: 'Develop propulsion system prototype',
      status: 'In Progress',
      assignee: 'Alex Ray',
    },
    {
      id: 'task-102',
      title: 'Design user interface for mission control',
      status: 'In Progress',
      assignee: 'Casey Jordan',
    },
    {
      id: 'task-103',
      title: 'Set up CI/CD pipeline for deployment',
      status: 'Done',
      assignee: 'Dev Team',
    },
    {
      id: 'task-104',
      title: 'Perform initial risk assessment',
      status: 'Done',
      assignee: 'Alex Ray',
    },
    {
      id: 'task-105',
      title: 'Finalize Q3 budget and resource allocation',
      status: 'To Do',
      assignee: 'Casey Jordan',
    },
  ],
  team: [
    { id: 'team-1', name: 'Alex Ray', role: 'Lead Engineer' },
    { id: 'team-2', name: 'Casey Jordan', role: 'UX/UI Designer' },
  ],
  activityStream: [
    {
      id: 'act-1',
      description:
        'Casey Jordan updated the status of "Design user interface for mission control" to "In Progress".',
      timestamp: '2024-08-01T10:00:00Z',
    },
    {
      id: 'act-2',
      description:
        'Alex Ray completed the task "Perform initial risk assessment".',
      timestamp: '2024-07-31T15:30:00Z',
    },
    {
      id: 'act-3',
      description:
        'A new task "Finalize Q3 budget and resource allocation" was added to the project.',
      timestamp: '2024-07-30T11:00:00Z',
    },
  ],
};

/**
 * API handler for fetching project management data.
 * Simulates a network request with a 1-second delay.
 *
 * @param {NextApiRequest} req - The incoming API request.
 * @param {NextApiResponse<ProjectData>} res - The outgoing API response.
 */
export default function handler(
  req: NextApiRequest,
  res: NextApiResponse<ProjectData>
) {
  // Simulate a network delay of 1 second.
  setTimeout(() => {
    res.status(200).json(mockProjectData);
  }, 1000);
}

import { NextApiRequest, NextApiResponse } from "next";

// Backend API URL - configurable via environment variable
const BACKEND_API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || "http://localhost:8000";

interface CalendarEvent {
  id: string;
  title: string;
  start: string;  // ISO string
  end: string;    // ISO string
  description?: string;
  location?: string;
  status: string;
}

interface Task {
  id: string;
  title: string;
  description?: string;
  due_date?: string;  // ISO string
  priority: "high" | "medium" | "low";
  status: string;
  created_at: string;  // ISO string
  updated_at: string;  // ISO string
}

interface Message {
  id: string;
  platform: string;
  from_user?: string;
  subject: string;
  preview: string;
  timestamp: string;  // ISO string
  unread: boolean;
  priority: "high" | "normal" | "low";
}

interface DashboardStats {
  upcoming_events: number;
  overdue_tasks: number;
  unread_messages: number;
  completed_tasks: number;
  active_workflows: number;
  total_agents: number;
}

interface DashboardData {
  calendar: CalendarEvent[];
  tasks: Task[];
  messages: Message[];
  stats: DashboardStats;
}

interface DashboardApiResponse {
  success: boolean;
  data: {
    calendar: CalendarEvent[];
    tasks: Task[];
    messages: Message[];
  };
  stats: DashboardStats;
  timestamp: string;
}

/**
 * Dashboard API Endpoint
 * Fetches real data from the backend dashboard API
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    // Extract query parameters
    const { user_id, limit } = req.query;

    // Build query params for backend API
    const params = new URLSearchParams();
    if (user_id) params.append("user_id", user_id as string);
    if (limit) params.append("limit", limit as string);

    // Fetch from backend dashboard API
    const response = await fetch(`${BACKEND_API_URL}/api/dashboard/data?${params.toString()}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        // Add authentication header if needed
        // "Authorization": `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Backend API returned ${response.status}: ${response.statusText}`);
    }

    const data: DashboardApiResponse = await response.json();

    if (!data.success) {
      throw new Error("Backend API returned unsuccessful response");
    }

    // Transform backend data to match frontend interface
    const dashboardData: DashboardData = {
      calendar: data.data.calendar.map((event: any) => ({
        id: event.id,
        title: event.title,
        start: event.start,
        end: event.end,
        description: event.description,
        location: event.location,
        status: event.status,
      })),
      tasks: data.data.tasks.map((task: any) => ({
        id: task.id,
        title: task.title,
        description: task.description,
        due_date: task.due_date,
        priority: task.priority,
        status: task.status,
        created_at: task.created_at,
        updated_at: task.updated_at,
      })),
      messages: data.data.messages.map((msg: any) => ({
        id: msg.id,
        platform: msg.platform,
        from_user: msg.from_user,
        subject: msg.subject,
        preview: msg.preview,
        timestamp: msg.timestamp,
        unread: msg.unread,
        priority: msg.priority,
      })),
      stats: data.stats,
    };

    // Return the transformed data
    res.status(200).json(dashboardData);

  } catch (error) {
    console.error("Dashboard API error:", error);

    // Return error response
    res.status(500).json({
      error: "Failed to fetch dashboard data",
      message: error instanceof Error ? error.message : "Unknown error",
      timestamp: new Date().toISOString(),
    });
  }
}

/**
 * Legacy function to get mock data for fallback/testing
 * This is kept for development purposes when backend is not available
 */
function getMockDashboardData(): DashboardData {
  const now = new Date();

  return {
    calendar: [
    {
      id: "mock-1",
      title: "Team Standup Meeting",
      start: new Date(now.getTime() + 2 * 60 * 60 * 1000).toISOString(),
      end: new Date(now.getTime() + 3 * 60 * 60 * 1000).toISOString(),
      description: "Daily team synchronization",
      location: "Conference Room A",
      status: "confirmed",
    },
    {
      id: "mock-2",
      title: "Client Presentation",
      start: new Date(now.getTime() + 5 * 60 * 60 * 1000).toISOString(),
      end: new Date(now.getTime() + 6 * 60 * 60 * 1000).toISOString(),
      description: "Quarterly review with client",
      location: "Client Office",
      status: "tentative",
    },
  ],
  tasks: [
    {
      id: "mock-1",
      title: "Complete project proposal",
      description: "Finish the client project proposal document",
      due_date: new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString(),
      priority: "high",
      status: "in-progress",
      created_at: now.toISOString(),
      updated_at: now.toISOString(),
    },
    {
      id: "mock-2",
      title: "Review team code submissions",
      description: "Code review for pull requests",
      due_date: new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      priority: "medium",
      status: "todo",
      created_at: now.toISOString(),
      updated_at: now.toISOString(),
    },
  ],
  messages: [
    {
      id: "mock-1",
      platform: "email",
      from_user: "client@example.com",
      subject: "Project Update Request",
      preview: "Hi, could you please provide an update on the current project status?",
      timestamp: new Date(now.getTime() - 30 * 60 * 1000).toISOString(),
      unread: true,
      priority: "high",
    },
  ],
  stats: {
    upcoming_events: 2,
    overdue_tasks: 1,
    unread_messages: 1,
    completed_tasks: 0,
    active_workflows: 0,
    total_agents: 0,
  },
};

    unread: true,
    priority: "normal",
  },
  {
    id: "4",
    platform: "discord",
    from: "Development Community",
    subject: "Weekly Tech Talk",
    preview: "Join us this Thursday for a discussion on AI assistants",
    timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000), // 6 hours ago
    unread: false,
    priority: "low",
  },
];

// Function to fetch real calendar data from backend API
async function fetchRealCalendarData(): Promise<CalendarEvent[]> {
  try {
    const response = await fetch("http://localhost:5058/api/calendar/events", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.events || [];
  } catch (error) {
    console.error("Error fetching calendar data:", error);
    // Fall back to mock data if real API is unavailable
    return mockCalendarData;
  }
}

// Function to fetch real task data from backend API
async function fetchRealTaskData(): Promise<Task[]> {
  try {
    const response = await fetch("http://localhost:5058/api/tasks", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.tasks || [];
  } catch (error) {
    console.error("Error fetching task data:", error);
    // Fall back to mock data if real API is unavailable
    return mockTasksData;
  }
}

// Function to fetch real message data from backend API
async function fetchRealMessageData(): Promise<Message[]> {
  try {
    const response = await fetch("http://localhost:5058/api/messages", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.messages || [];
  } catch (error) {
    console.error("Error fetching message data:", error);
    // Fall back to mock data if real API is unavailable
    return mockMessagesData;
  }
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Development version - bypass authentication
  // Add CORS headers for development
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader(
    "Access-Control-Allow-Methods",
    "GET, POST, PUT, DELETE, OPTIONS",
  );
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  // Handle preflight requests
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  try {
    // Fetch real data from backend services
    const [calendarData, taskData, messageData] = await Promise.all([
      fetchRealCalendarData(),
      fetchRealTaskData(),
      fetchRealMessageData(),
    ]);

    // Calculate statistics
    const now = new Date();
    const upcomingEvents = calendarData.filter(
      (event) => new Date(event.start) > now,
    ).length;

    const overdueTasks = taskData.filter(
      (task) => task.status !== "completed" && new Date(task.dueDate) < now,
    ).length;

    const unreadMessages = messageData.filter(
      (message) => message.unread,
    ).length;

    const completedTasks = taskData.filter(
      (task) => task.status === "completed",
    ).length;

    const dashboardData: DashboardData = {
      calendar: calendarData,
      tasks: taskData,
      messages: messageData,
      stats: {
        upcomingEvents,
        overdueTasks,
        unreadMessages,
        completedTasks,
      },
    };

    res.status(200).json(dashboardData);
  } catch (error) {
    console.error("Error fetching dashboard data:", error);
    res.status(500).json({ message: "Internal server error" });
  }
}

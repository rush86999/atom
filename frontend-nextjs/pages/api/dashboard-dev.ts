import { NextApiRequest, NextApiResponse } from "next";

interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  description?: string;
  location?: string;
  attendees?: string[];
  status: "confirmed" | "tentative" | "cancelled";
}

interface Task {
  id: string;
  title: string;
  description?: string;
  dueDate: Date;
  priority: "high" | "medium" | "low";
  status: "todo" | "in-progress" | "completed";
  project?: string;
  tags?: string[];
}

interface Message {
  id: string;
  platform: "email" | "slack" | "teams" | "discord";
  from: string;
  subject: string;
  preview: string;
  timestamp: Date;
  unread: boolean;
  priority: "high" | "normal" | "low";
}

interface DashboardData {
  calendar: CalendarEvent[];
  tasks: Task[];
  messages: Message[];
  stats: {
    upcomingEvents: number;
    overdueTasks: number;
    unreadMessages: number;
    completedTasks: number;
  };
}

// Mock data for demonstration - in production, this would fetch from actual services
const mockCalendarData: CalendarEvent[] = [
  {
    id: "1",
    title: "Team Standup Meeting",
    start: new Date(Date.now() + 2 * 60 * 60 * 1000), // 2 hours from now
    end: new Date(Date.now() + 3 * 60 * 60 * 1000),
    description: "Daily team synchronization",
    location: "Conference Room A",
    attendees: ["team@example.com", "manager@example.com"],
    status: "confirmed",
  },
  {
    id: "2",
    title: "Client Presentation",
    start: new Date(Date.now() + 5 * 60 * 60 * 1000),
    end: new Date(Date.now() + 6 * 60 * 60 * 1000),
    description: "Quarterly review with client",
    location: "Client Office",
    status: "tentative",
  },
  {
    id: "3",
    title: "Lunch with Sarah",
    start: new Date(Date.now() + 7 * 60 * 60 * 1000),
    end: new Date(Date.now() + 8 * 60 * 60 * 1000),
    location: "Downtown Cafe",
    status: "confirmed",
  },
];

const mockTasksData: Task[] = [
  {
    id: "1",
    title: "Complete project proposal",
    description: "Finish the client project proposal document",
    dueDate: new Date(Date.now() + 24 * 60 * 60 * 1000), // Tomorrow
    priority: "high",
    status: "in-progress",
    project: "Client Project",
    tags: ["documentation", "client"],
  },
  {
    id: "2",
    title: "Review team code submissions",
    description: "Code review for pull requests",
    dueDate: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000), // 2 days ago (overdue)
    priority: "medium",
    status: "todo",
    project: "Development",
    tags: ["code-review", "team"],
  },
  {
    id: "3",
    title: "Prepare monthly report",
    description: "Compile metrics and performance data",
    dueDate: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000), // 3 days from now
    priority: "medium",
    status: "todo",
    project: "Reporting",
    tags: ["reporting", "metrics"],
  },
  {
    id: "4",
    title: "Schedule team training",
    description: "Organize React.js training session",
    dueDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 1 week from now
    priority: "low",
    status: "completed",
    project: "Team Development",
    tags: ["training", "react"],
  },
];

const mockMessagesData: Message[] = [
  {
    id: "1",
    platform: "email",
    from: "client@example.com",
    subject: "Project Update Request",
    preview:
      "Hi, could you please provide an update on the current project status?",
    timestamp: new Date(Date.now() - 30 * 60 * 1000), // 30 minutes ago
    unread: true,
    priority: "high",
  },
  {
    id: "2",
    platform: "slack",
    from: "John Smith",
    subject: "Meeting Notes",
    preview: "Here are the notes from yesterday's meeting...",
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2 hours ago
    unread: false,
    priority: "normal",
  },
  {
    id: "3",
    platform: "teams",
    from: "HR Department",
    subject: "Benefits Enrollment Reminder",
    preview: "Reminder: Benefits enrollment closes this Friday",
    timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), // 4 hours ago
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

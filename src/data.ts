import {
  Task,
  CalendarEvent,
  CommunicationsMessage,
  Transaction,
  UserProfile,
  WeatherData,
  NewsItem,
  HealthMetrics,
} from './types';

// ============================================================================
// Mock Data Exports
// ============================================================================

export const USER_PROFILE_DATA: UserProfile = {
  name: 'Alex Johnson',
  email: 'alex@example.com',
  preferences: {
    language: 'en',
    timezone: 'UTC-5',
    theme: 'light',
    notifications: {
      email: true,
      push: true,
      channels: {
        tasks: true,
        calendar: true,
        communications: true,
      },
    },
  },
};

export const WEATHER_DATA: WeatherData = {
  location: 'San Francisco, CA',
  temperature: 72,
  condition: 'Partly Cloudy',
  humidity: 65,
  windSpeed: 12,
  icon: 'sunny',
};

export const NEWS_DATA: NewsItem[] = [
  {
    id: 'news-1',
    title: 'Tech Industry Sees Record Growth',
    summary: 'Latest reports show the tech sector booming with new innovations',
    source: 'TechNews Daily',
    publishedAt: new Date().toISOString(),
    url: 'https://example.com/news/1',
  },
  {
    id: 'news-2',
    title: 'New AI Models Released',
    summary: 'Leading companies announce groundbreaking AI advancements',
    source: 'AI Weekly',
    publishedAt: new Date(Date.now() - 3600000).toISOString(),
    url: 'https://example.com/news/2',
  },
  {
    id: 'news-3',
    title: 'Blockchain Market Expands',
    summary: 'Cryptocurrency and blockchain adoption reaches new milestones',
    source: 'Crypto Times',
    publishedAt: new Date(Date.now() - 7200000).toISOString(),
    url: 'https://example.com/news/3',
  },
];

export const HEALTH_DATA: HealthMetrics = {
  steps: 8234,
  sleepHours: 7.5,
  heartRate: 72,
  caloriesBurned: 520,
};

export const TASKS_DATA: Task[] = [
  {
    id: 'task-1',
    title: 'Complete project documentation',
    description: 'Write comprehensive documentation for the Q4 project',
    status: 'in_progress',
    priority: 'high',
    dueDate: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
    isImportant: true,
    assignee: 'Alex Johnson',
    tags: ['documentation', 'project'],
    subtasks: [
      { id: 'sub-1', title: 'API docs', completed: true },
      { id: 'sub-2', title: 'User guide', completed: false },
    ],
    version: 1,
  },
  {
    id: 'task-2',
    title: 'Review code submissions',
    description: 'Review and approve pending pull requests',
    status: 'pending',
    priority: 'critical',
    dueDate: new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString(),
    isImportant: true,
    assignee: 'Alex Johnson',
    tags: ['code-review', 'urgent'],
    subtasks: [],
    version: 1,
  },
  {
    id: 'task-3',
    title: 'Update dependencies',
    description: 'Update npm packages to latest versions',
    status: 'pending',
    priority: 'medium',
    dueDate: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    isImportant: false,
    assignee: 'Alex Johnson',
    tags: ['maintenance'],
    subtasks: [],
    version: 1,
  },
  {
    id: 'task-4',
    title: 'Deploy to production',
    description: 'Deploy latest changes to production environment',
    status: 'pending',
    priority: 'high',
    dueDate: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
    isImportant: true,
    assignee: 'Alex Johnson',
    tags: ['deployment', 'release'],
    subtasks: [],
    version: 1,
  },
];

export const COMMUNICATIONS_DATA: CommunicationsMessage[] = [
  {
    id: 'msg-1',
    platform: 'email',
    from: { name: 'Sarah Chen', email: 'sarah@example.com' },
    subject: 'Project Update - Q4 Planning',
    preview: 'Let\'s discuss the upcoming Q4 initiatives...',
    body: 'Let\'s discuss the upcoming Q4 initiatives. I have some ideas to share with the team.',
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    unread: true,
    read: false,
  },
  {
    id: 'msg-2',
    platform: 'slack',
    from: { name: 'Mike Davis' },
    subject: 'Sprint Planning',
    preview: 'Sprint planning is tomorrow at 10 AM...',
    body: 'Sprint planning is tomorrow at 10 AM. Please come prepared with your updates.',
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    unread: true,
    read: false,
  },
  {
    id: 'msg-3',
    platform: 'email',
    from: { name: 'Emma Wilson', email: 'emma@example.com' },
    subject: 'Code Review Complete',
    preview: 'Your pull request has been reviewed...',
    body: 'Your pull request has been reviewed and approved. Great work!',
    timestamp: new Date(Date.now() - 86400000).toISOString(),
    unread: false,
    read: true,
  },
];

export const TRANSACTIONS_DATA: Transaction[] = [
  {
    id: 'trans-1',
    date: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    description: 'Coffee Shop - Morning',
    amount: 5.50,
    category: 'Food & Drink',
    type: 'debit',
  },
  {
    id: 'trans-2',
    date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    description: 'AWS Cloud Services',
    amount: 250.00,
    category: 'Technology',
    type: 'debit',
  },
  {
    id: 'trans-3',
    date: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    description: 'Salary Deposit',
    amount: 3500.00,
    category: 'Income',
    type: 'credit',
  },
  {
    id: 'trans-4',
    date: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString(),
    description: 'Office Supplies',
    amount: 85.40,
    category: 'Office',
    type: 'debit',
  },
];

// ============================================================================
// Calendar Events
// ============================================================================

export function getCalendarEventsForMonth(year: number, month: number): CalendarEvent[] {
  const today = new Date();
  const events: CalendarEvent[] = [];

  // Create sample events for the month
  events.push({
    id: 'event-1',
    title: 'Team Standup',
    startTime: new Date(year, month, today.getDate(), 9, 0).toISOString(),
    endTime: new Date(year, month, today.getDate(), 9, 30).toISOString(),
    color: 'blue',
  });

  events.push({
    id: 'event-2',
    title: 'Project Planning Meeting',
    startTime: new Date(year, month, today.getDate(), 14, 0).toISOString(),
    endTime: new Date(year, month, today.getDate(), 15, 30).toISOString(),
    color: 'purple',
  });

  events.push({
    id: 'event-3',
    title: 'Code Review Session',
    startTime: new Date(year, month, today.getDate() + 1, 10, 0).toISOString(),
    endTime: new Date(year, month, today.getDate() + 1, 11, 0).toISOString(),
    color: 'green',
  });

  events.push({
    id: 'event-4',
    title: 'Client Call',
    startTime: new Date(year, month, today.getDate() + 2, 16, 0).toISOString(),
    endTime: new Date(year, month, today.getDate() + 2, 17, 0).toISOString(),
    color: 'orange',
  });

  events.push({
    id: 'event-5',
    title: 'Department All-Hands',
    startTime: new Date(year, month, today.getDate() + 3, 11, 0).toISOString(),
    endTime: new Date(year, month, today.getDate() + 3, 12, 0).toISOString(),
    color: 'red',
  });

  return events;
}

// ============================================================================
// API Calls (Mock)
// ============================================================================

export const updateTask = async (task: Task): Promise<Task> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ ...task, version: task.version + 1, _optimistic: false });
    }, 500);
  });
};
import React, { useState, useEffect, useCallback, useMemo, useRef, FC } from 'react';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import {
    CalendarEvent,
    Task,
    CommunicationsMessage,
    Transaction,
    UserProfile,
    WeatherData,
    NewsItem,
    HealthMetrics,
    WidgetConfig
} from '../types';
import {
    getCalendarEventsForMonth,
    TASKS_DATA,
    COMMUNICATIONS_DATA,
    TRANSACTIONS_DATA,
    USER_PROFILE_DATA,
    WEATHER_DATA,
    NEWS_DATA,
    HEALTH_DATA
} from '../data';
import { useAppStore } from '../store';
import PerformanceTimeline from '../components/PerformanceTimeline';
import { useWebSocket } from '../hooks/useWebSocket';

// Advanced Analytics Component
interface AnalyticsData {
    totalActivities: number;
    completionRate: number;
    averageResponseTime: number;
    productivityScore: number;
    timeSpent: Record<string, number>;
}

// Helper function to check if a date is today
const isToday = (date: Date) => {
    const today = new Date();
    return date.getDate() === today.getDate() &&
           date.getMonth() === today.getMonth() &&
           date.getFullYear() === today.getFullYear();
};

const formatTime = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

// Advanced Analytics Widget
const AdvancedAnalyticsWidget: FC<{ tasks: Task[]; transactions: Transaction[]; events: CalendarEvent[] }> = ({ tasks, transactions, events }) => {
    const analytics: AnalyticsData = useMemo(() => {
        const completed = tasks.filter(t => t.status === 'completed').length;
        const total = tasks.length;
        const spent = transactions.filter(t => t.type === 'debit').reduce((a, b) => a + b.amount, 0);
        
        return {
            totalActivities: tasks.length + events.length,
            completionRate: total > 0 ? Math.round((completed / total) * 100) : 0,
            averageResponseTime: 2.5, // mock data
            productivityScore: Math.min(100, (completed / Math.max(1, total)) * 100 + 20),
            timeSpent: { tasks: 4.5, meetings: 2, focus: 1.5 }
        };
    }, [tasks, transactions, events]);

    return (
        <div className="dashboard-card analytics-card">
            <h3>📊 Advanced Analytics</h3>
            <div className="analytics-grid">
                <div className="analytics-item">
                    <span className="analytics-label">Completion Rate</span>
                    <div className="circular-progress" style={{ position: 'relative', width: 80, height: 80 }}>
                        <svg width="80" height="80" style={{ transform: 'rotate(-90deg)' }}>
                            <circle cx="40" cy="40" r="35" fill="none" stroke="#e0e0e0" strokeWidth="4" />
                            <circle
                                cx="40"
                                cy="40"
                                r="35"
                                fill="none"
                                stroke="#3b82f6"
                                strokeWidth="4"
                                strokeDasharray={`${2 * Math.PI * 35}`}
                                strokeDashoffset={`${2 * Math.PI * 35 * (1 - analytics.completionRate / 100)}`}
                                strokeLinecap="round"
                            />
                        </svg>
                        <span style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontSize: 16, fontWeight: 'bold' }}>
                            {analytics.completionRate}%
                        </span>
                    </div>
                </div>
                <div className="analytics-item">
                    <span className="analytics-label">Productivity Score</span>
                    <p style={{ fontSize: 24, fontWeight: 'bold', margin: '10px 0' }}>{Math.round(analytics.productivityScore)}/100</p>
                </div>
                <div className="analytics-item">
                    <span className="analytics-label">Total Activities</span>
                    <p style={{ fontSize: 24, fontWeight: 'bold' }}>{analytics.totalActivities}</p>
                </div>
                <div className="analytics-item">
                    <span className="analytics-label">Time Breakdown</span>
                    <ul style={{ fontSize: 12 }}>
                        {Object.entries(analytics.timeSpent).map(([key, val]) => (
                            <li key={key}>{key}: {val}h</li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    );
};

// Smart Assistant Widget
const SmartAssistantWidget: FC = () => {
    const [suggestions, setSuggestions] = useState<string[]>([
        '📌 Focus on high-priority tasks this morning',
        '💡 You completed 75% of tasks - Great progress!',
        '⏰ Schedule a 15-min break before your next meeting',
        '🎯 Productivity peak between 10AM-12PM'
    ]);

    return (
        <div className="dashboard-card assistant-card">
            <h3>🤖 Smart Assistant</h3>
            <div className="suggestions-list">
                {suggestions.map((suggestion, i) => (
                    <div key={i} className="suggestion-item">
                        <p>{suggestion}</p>
                        <button className="dismiss-btn" aria-label="Dismiss suggestion">×</button>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Collaboration & Presence Widget
const CollaborationWidget: FC<{ presenceList: any[] }> = ({ presenceList }) => {
    const [activeCollaborations, setActiveCollaborations] = useState<number>(0);

    useEffect(() => {
        setActiveCollaborations(presenceList.filter(p => p.room === 'projects').length);
    }, [presenceList]);

    return (
        <div className="dashboard-card collaboration-card">
            <h3>👥 Team Collaboration</h3>
            <div className="collaboration-stats">
                <div className="stat">
                    <span className="stat-value">{presenceList.length}</span>
                    <span className="stat-label">Online Members</span>
                </div>
                <div className="stat">
                    <span className="stat-value">{activeCollaborations}</span>
                    <span className="stat-label">Active Collaborations</span>
                </div>
            </div>
            <div className="collaboration-members">
                {presenceList.slice(0, 5).map(member => (
                    <div key={member.socketId} className="member-avatar" title={member.username || member.userId}>
                        {(member.username || member.userId)?.charAt(0).toUpperCase()}
                    </div>
                ))}
                {presenceList.length > 5 && <div className="member-avatar">+{presenceList.length - 5}</div>}
            </div>
        </div>
    );
};


// Widget for Today's Schedule
const TodaysSchedule: React.FC<{ events: CalendarEvent[] }> = ({ events }) => {
    const today = new Date();
    const todaysEvents = events
        .filter(event => isToday(new Date(event.startTime)))
        .sort((a,b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());

    return (
        <div className="dashboard-card">
            <h3>Today's Schedule</h3>
            {todaysEvents.length > 0 ? (
                <div className="schedule-list">
                    {todaysEvents.map(event => (
                        <div key={event.id} className="schedule-item">
                            <div className={`event-color-bar ${event.color}`}></div>
                            <div className="event-info">
                                <p className="event-title">{event.title}</p>
                                <p className="event-time">{formatTime(event.startTime)} - {formatTime(event.endTime)}</p>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <p>No events scheduled for today.</p>
            )}
        </div>
    );
};

// Widget for Priority Tasks
const PriorityTasks: React.FC<{ tasks: Task[], onTaskUpdate?: (taskId: string, updates: Partial<Task>) => void }> = ({ tasks, onTaskUpdate }) => {
    const [editingTask, setEditingTask] = React.useState<string | null>(null);
    const [editTitle, setEditTitle] = React.useState('');

    const priorityTasks = tasks
        .filter(task => (task.isImportant || task.priority === 'critical' || task.priority === 'high') && task.status !== 'completed')
        .slice(0, 5); // Show top 5

    const handleEditStart = (task: Task) => {
        setEditingTask(task.id);
        setEditTitle(task.title);
    };

    const handleEditSave = (taskId: string) => {
        if (onTaskUpdate && editTitle.trim()) {
            onTaskUpdate(taskId, { title: editTitle.trim() });
        }
        setEditingTask(null);
        setEditTitle('');
    };

    const handleStatusToggle = (taskId: string, currentStatus: string) => {
        if (onTaskUpdate) {
            onTaskUpdate(taskId, { status: currentStatus === 'completed' ? 'pending' : 'completed' });
        }
    };

    return (
        <div className="dashboard-card">
            <h3>Priority Tasks</h3>
            {priorityTasks.length > 0 ? (
                <div className="priority-tasks-list">
                    {priorityTasks.map(task => (
                        <div key={task.id} className="priority-task-item">
                            <input
                                type="checkbox"
                                checked={task.status === 'completed'}
                                onChange={() => handleStatusToggle(task.id, task.status)}
                            />
                            <span className={`priority-indicator ${task.priority}`}></span>
                            <div className="task-content">
                                {editingTask === task.id ? (
                                    <input
                                        type="text"
                                        value={editTitle}
                                        onChange={e => setEditTitle(e.target.value)}
                                        onBlur={() => handleEditSave(task.id)}
                                        onKeyPress={e => e.key === 'Enter' && handleEditSave(task.id)}
                                        autoFocus
                                    />
                                ) : (
                                    <p className="task-title" onClick={() => handleEditStart(task)}>{task.title}</p>
                                )}
                                <small>Due: {new Date(task.dueDate).toLocaleDateString()}</small>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <p>No priority tasks at the moment.</p>
            )}
        </div>
    );
};

// Widget for Inbox Summary
const InboxSummary: React.FC<{ messages: CommunicationsMessage[] }> = ({ messages }) => {
    const unreadCount = messages.filter(msg => msg.unread).length;

    return (
        <div className="dashboard-card summary-card">
            <h4>Unread Messages</h4>
            <p className="summary-value">{unreadCount}</p>
        </div>
    );
};

// Widget for Financial Snapshot
const FinancialSnapshot: React.FC<{ transactions: Transaction[] }> = ({ transactions }) => {
    const totalSpending = transactions
        .filter(t => t.type === 'debit')
        .reduce((acc, t) => acc + t.amount, 0);

    return (
        <div className="dashboard-card summary-card">
            <h4>Spending (30d)</h4>
            <p className="summary-value">${totalSpending.toFixed(2)}</p>
        </div>
    );
};

// Widget for Current Weather
const CurrentWeather: React.FC<{ weather: WeatherData }> = ({ weather }) => {
    return (
        <div className="dashboard-card weather-card">
            <h4>Current Weather</h4>
            <div className="weather-content">
                <div className="weather-main">
                    <div className="weather-icon">{weather.icon === 'sunny' ? '☀️' : '🌤️'}</div>
                    <div className="weather-temp">{weather.temperature}°F</div>
                </div>
                <div className="weather-details">
                    <p className="weather-condition">{weather.condition}</p>
                    <p className="weather-location">{weather.location}</p>
                    <div className="weather-stats">
                        <span>Humidity: {weather.humidity}%</span>
                        <span>Wind: {weather.windSpeed} mph</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

// Widget for News Feed
const NewsFeed: React.FC<{ news: NewsItem[] }> = ({ news }) => {
    return (
        <div className="dashboard-card news-card">
            <h4>Latest News</h4>
            <div className="news-list">
                {news.slice(0, 3).map(item => (
                    <div key={item.id} className="news-item">
                        <h5>{item.title}</h5>
                        <p>{item.summary}</p>
                        <small>{item.source} • {new Date(item.publishedAt).toLocaleDateString()}</small>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Widget for Health Metrics
const HealthMetricsWidget: React.FC<{ health: HealthMetrics }> = ({ health }) => {
    return (
        <div className="dashboard-card health-card">
            <h4>Today's Health</h4>
            <div className="health-metrics">
                <div className="metric">
                    <span className="metric-value">{health.steps.toLocaleString()}</span>
                    <span className="metric-label">Steps</span>
                </div>
                <div className="metric">
                    <span className="metric-value">{health.sleepHours}h</span>
                    <span className="metric-label">Sleep</span>
                </div>
                <div className="metric">
                    <span className="metric-value">{health.heartRate}</span>
                    <span className="metric-label">BPM</span>
                </div>
                <div className="metric">
                    <span className="metric-value">{health.caloriesBurned}</span>
                    <span className="metric-label">Cal</span>
                </div>
            </div>
        </div>
    );
};

// Widget for Productivity Chart
const ProductivityChart: React.FC<{ tasks: Task[] }> = ({ tasks }) => {
    const completedTasks = tasks.filter(task => task.status === 'completed').length;
    const totalTasks = tasks.length;
    const completionRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

    const priorityBreakdown = {
        critical: tasks.filter(t => t.priority === 'critical').length,
        high: tasks.filter(t => t.priority === 'high').length,
        medium: tasks.filter(t => t.priority === 'medium').length,
        low: tasks.filter(t => t.priority === 'low').length,
    };

    return (
        <div className="dashboard-card chart-card">
            <h4>Productivity Overview</h4>
            <div className="productivity-stats">
                <div className="stat">
                    <span className="stat-value">{completionRate}%</span>
                    <span className="stat-label">Tasks Completed</span>
                </div>
                <div className="stat">
                    <span className="stat-value">{totalTasks - completedTasks}</span>
                    <span className="stat-label">Pending Tasks</span>
                </div>
            </div>
            <div className="priority-breakdown">
                <h5>Priority Breakdown</h5>
                <div className="priority-bars">
                    {Object.entries(priorityBreakdown).map(([priority, count]) => (
                        <div key={priority} className="priority-bar">
                            <span className="priority-label">{priority}</span>
                            <div className="bar">
                                <div
                                    className={`bar-fill ${priority}`}
                                    style={{ width: `${totalTasks > 0 ? (count / totalTasks) * 100 : 0}%` }}
                                ></div>
                            </div>
                            <span className="count">{count}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// Real-time Clock Widget
const RealTimeClock: React.FC = () => {
    const [time, setTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="dashboard-card clock-card">
            <h4>Current Time</h4>
            <div className="clock-time">{time.toLocaleTimeString()}</div>
            <div className="clock-date">{time.toLocaleDateString()}</div>
        </div>
    );
};


export const DashboardView = () => {
    const {
        userProfile,
        calendarEvents,
        tasks,
        messages,
        transactions,
        widgets,
        setWidgets,
        updateTask,
        addTask,
        addNote,
        setLoading,
        setError,
        loading,
        errors,
        setCurrentView,
        addNotification
    } = useAppStore();

        // Presence list maintained locally from socket events
        const [presenceList, setPresenceList] = useState<Array<{ userId?: string; username?: string; socketId?: string; room?: string }>>([]);
        const { subscribe, unsubscribe, emit, isConnected } = useWebSocket({ enabled: true });

        const [serverMetrics, setServerMetrics] = useState<{ currentConnections: number; messagesSent: number; messagesReceived: number }>({ currentConnections: 0, messagesSent: 0, messagesReceived: 0 });
        const saveTimeoutRef = useRef<number | null>(null);

        useEffect(() => {
            const onJoin = (user: any) => {
                setPresenceList(prev => {
                    const exists = prev.find(p => p.socketId === user.socketId || p.userId === user.userId);
                    if (exists) return prev;
                    return [...prev, user];
                });
            };

            const onLeave = (user: any) => {
                setPresenceList(prev => prev.filter(p => p.socketId !== user.socketId && p.userId !== user.userId));
            };

            subscribe('presence:joined', onJoin);
            subscribe('presence:left', onLeave);
            // server metrics
            const onMetrics = (m: any) => {
                setServerMetrics(prev => ({
                    currentConnections: typeof m.currentConnections === 'number' ? m.currentConnections : prev.currentConnections,
                    messagesSent: typeof m.messagesSent === 'number' ? m.messagesSent : prev.messagesSent,
                    messagesReceived: typeof m.messagesReceived === 'number' ? m.messagesReceived : prev.messagesReceived,
                }));
            };
            subscribe('metrics:update', onMetrics);

            return () => {
                unsubscribe('presence:joined', onJoin);
                unsubscribe('presence:left', onLeave);
                unsubscribe('metrics:update', onMetrics);
            };
        }, [subscribe, unsubscribe]);

        const handleBroadcast = async () => {
            const message = window.prompt('Enter announcement to broadcast to connected clients:');
            if (!message) return;
            try {
                emit?.('broadcast:announcement', { from: (userProfile as any)?.id, text: message, timestamp: new Date().toISOString() });
                addNotification?.({ type: 'success', title: 'Broadcast Sent', message: 'Announcement sent to connected clients' });
            } catch (e) {
                addNotification?.({ type: 'error', title: 'Broadcast Failed', message: 'Failed to send announcement' });
            }
        };

        const handleStartDM = (p: any) => {
            // Emit an intent to start a DM and navigate to chat view
            emit?.('dm:init', { from: (userProfile as any)?.id, to: p.userId || p.socketId });
            setCurrentView('chat');
        };

    const [events, setEvents] = useState<CalendarEvent[]>([]);
    const [weather, setWeather] = useState<WeatherData>(WEATHER_DATA);
    const [news, setNews] = useState<NewsItem[]>(NEWS_DATA);
    const [health, setHealth] = useState<HealthMetrics>(HEALTH_DATA);
    const [showTaskModal, setShowTaskModal] = useState(false);
    const [showNoteModal, setShowNoteModal] = useState(false);
    const [showWidgetSettings, setShowWidgetSettings] = useState(false);
    const [newTaskTitle, setNewTaskTitle] = useState('');
    const [newTaskDescription, setNewTaskDescription] = useState('');
    const [newNoteTitle, setNewNoteTitle] = useState('');
    const [newNoteContent, setNewNoteContent] = useState('');

    useEffect(() => {
        const today = new Date();
        setEvents(getCalendarEventsForMonth(today.getFullYear(), today.getMonth()));
    }, []);

    // Real-time data polling (faster refresh)
    useEffect(() => {
        const pollData = () => {
            try {
                setLoading('tasks', true);
                setLoading('messages', true);
                setLoading('transactions', true);
                // Simulate API calls with mock data updates
                setTimeout(() => {
                    setWeather(WEATHER_DATA);
                    setNews(NEWS_DATA);
                    setHealth(HEALTH_DATA);
                    setLoading('tasks', false);
                    setLoading('messages', false);
                    setLoading('transactions', false);
                    setError('general', null);
                }, 1000);
            } catch (error) {
                setError('general', 'Failed to refresh data');
                setLoading('tasks', false);
                setLoading('messages', false);
                setLoading('transactions', false);
            }
        };
        pollData(); // Initial load
        const interval = setInterval(pollData, 15000); // Poll every 15 seconds for snappier updates
        return () => clearInterval(interval);
    }, [setLoading, setError]);

    const handleTaskUpdate = useCallback((taskId: string, updates: Partial<Task>) => {
        updateTask(taskId, updates);
    }, [updateTask]);

    const handleCreateTask = useCallback(() => {
        if (newTaskTitle.trim()) {
            addTask({
                id: `task-${Date.now()}`,
                title: newTaskTitle.trim(),
                description: newTaskDescription.trim(),
                status: 'pending',
                priority: 'medium',
                dueDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
                isImportant: false,
                assignee: userProfile?.name || 'User',
                tags: [],
                subtasks: [],
                version: 1,
            });
            setNewTaskTitle('');
            setNewTaskDescription('');
            setShowTaskModal(false);
        }
    }, [newTaskTitle, newTaskDescription, addTask, userProfile]);

    const handleCreateNote = useCallback(() => {
        if (newNoteTitle.trim()) {
            addNote({
                id: `note-${Date.now()}`,
                title: newNoteTitle.trim(),
                content: newNoteContent.trim(),
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
                type: 'personal_memo'
            });
            setNewNoteTitle('');
            setNewNoteContent('');
            setShowNoteModal(false);
        }
    }, [newNoteTitle, newNoteContent, addNote]);

    const handleDragEnd = useCallback((result: DropResult) => {
        if (!result.destination) return;

        const items = Array.from(widgets);
        const [reorderedItem] = items.splice(result.source.index, 1);
        items.splice(result.destination.index, 0, reorderedItem);

        // Update positions
        const updatedItems = items.map((item, index) => ({ ...item, position: index }));
        setWidgets(updatedItems);
        // Persist will be handled by debounced effect below
    }, [widgets, setWidgets]);

    const toggleWidgetVisibility = useCallback((widgetId: string) => {
        const updatedWidgets = widgets.map(widget =>
            widget.id === widgetId ? { ...widget, visible: !widget.visible } : widget
        );
        setWidgets(updatedWidgets);
    }, [widgets, setWidgets]);

    // Debounced save to localStorage when widgets change
    useEffect(() => {
        if (saveTimeoutRef.current) {
            window.clearTimeout(saveTimeoutRef.current);
        }
        // store id returned by setTimeout (number in browsers)
        saveTimeoutRef.current = window.setTimeout(() => {
            try {
                localStorage.setItem('dashboardWidgets', JSON.stringify(widgets));
            } catch (e) {
                // ignore storage errors
            }
            saveTimeoutRef.current = null;
        }, 500);

        return () => {
            if (saveTimeoutRef.current) {
                window.clearTimeout(saveTimeoutRef.current);
                saveTimeoutRef.current = null;
            }
        };
    }, [widgets]);

    const sortedWidgets = useMemo(() => widgets.slice().sort((a, b) => a.position - b.position), [widgets]);

    const renderWidget = (widgetId: string) => {
        const widget = widgets.find(w => w.id === widgetId);
        if (!widget?.visible) return null;

        const isWidgetLoading = loading[widgetId] || false;
        const widgetError = errors[widgetId];

        const widgetContent = () => {
            switch (widgetId) {
                case 'schedule': return <TodaysSchedule events={events} />;
                case 'tasks': return <PriorityTasks tasks={tasks} onTaskUpdate={handleTaskUpdate} />;
                case 'inbox': return <InboxSummary messages={messages} />;
                case 'finance': return <FinancialSnapshot transactions={transactions} />;
                case 'weather': return <CurrentWeather weather={weather} />;
                case 'news': return <NewsFeed news={news} />;
                case 'health': return <HealthMetricsWidget health={health} />;
                case 'productivity': return <ProductivityChart tasks={tasks} />;
                case 'clock': return <RealTimeClock />;
                case 'advanced-analytics': return <AdvancedAnalyticsWidget tasks={tasks} transactions={transactions} events={events} />;
                case 'smart-assistant': return <SmartAssistantWidget />;
                case 'collaboration': return <CollaborationWidget presenceList={presenceList} />;
                case 'advanced-project':
                    return (
                        <div className="dashboard-card advanced-project-card">
                            <h3>Advanced Project</h3>
                            <p>Active connections: {serverMetrics.currentConnections}</p>
                            <p>Messages sent: {serverMetrics.messagesSent}</p>
                            <p>Messages received: {serverMetrics.messagesReceived}</p>
                            <p>Online collaborators: {presenceList.length}</p>
                            <div className="advanced-actions">
                                <button onClick={() => handleBroadcast?.()} aria-label="Broadcast announcement">Broadcast</button>
                                <button onClick={() => setCurrentView('projects')} aria-label="Open projects">Open Projects</button>
                            </div>
                        </div>
                    );
                case 'quick-actions':
                    return (
                        <div className="dashboard-card quick-actions" role="region" aria-labelledby="quick-actions-title">
                            <h3 id="quick-actions-title">Quick Actions</h3>
                            <button onClick={() => setShowTaskModal(true)} aria-label="Create new task">+ New Task</button>
                            <button onClick={() => setShowNoteModal(true)} aria-label="Create new note">+ New Note</button>
                            <button onClick={() => setCurrentView('calendar')} aria-label="Schedule meeting">Schedule Meeting</button>
                            <button onClick={() => setCurrentView('communications')} aria-label="Send quick message">Send Quick Message</button>
                            <button onClick={() => setCurrentView('workflows')} aria-label="Start workflow">Start Workflow</button>
                        </div>
                    );
                default: return null;
            }
        };

        return (
            <Draggable key={widgetId} draggableId={widgetId} index={widget.position}>
                {(provided, snapshot) => (
                    <div
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                        {...provided.dragHandleProps}
                        className={`dashboard-widget ${snapshot.isDragging ? 'dragging' : ''}`}
                        role="article"
                        aria-label={`${widget.title} widget`}
                    >
                        {isWidgetLoading && <div className="loading-spinner" aria-label="Loading">Loading...</div>}
                        {widgetError && <div className="error-message" role="alert">{widgetError}</div>}
                        {!isWidgetLoading && !widgetError && widgetContent()}
                    </div>
                )}
            </Draggable>
        );
    };

    return (
        <div className="dashboard-view">
            <header className="view-header">
                <h1>Welcome back, {userProfile?.name ? userProfile.name.split(' ')[0] : 'there'}!</h1>
                <p>Here's a snapshot of your day.</p>
                <button
                    onClick={() => setShowWidgetSettings(true)}
                    className="widget-settings-btn"
                    aria-label="Customize dashboard widgets"
                >
                    ⚙️ Customize
                </button>
            </header>
            {errors.general && <div className="error-banner" role="alert">{errors.general}</div>}
            <DragDropContext onDragEnd={handleDragEnd}>
                <Droppable droppableId="dashboard-widgets">
                    {(provided) => (
                        <div
                            className="dashboard-grid"
                            {...provided.droppableProps}
                            ref={provided.innerRef}
                            role="main"
                            aria-label="Dashboard widgets"
                        >
                            {/* Presence panel */}
                            <div className="dashboard-widget presence-panel" role="region" aria-label="Presence">
                                <div className="dashboard-card">
                                    <h3>Active Now</h3>
                                    {presenceList.length === 0 ? (
                                        <p className="text-sm text-gray-500">No one else is online</p>
                                    ) : (
                                        <ul className="presence-list">
                                            {presenceList.map(p => (
                                                <li key={p.socketId || p.userId} className="presence-item">
                                                    <span className="presence-dot" aria-hidden style={{ background: '#34d399', display: 'inline-block', width: 10, height: 10, borderRadius: 999 }}></span>
                                                    <span className="presence-name">{p.username || p.userId || 'Unknown'}</span>
                                                    {p.room && <small className="presence-room">{p.room}</small>}
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            </div>
                            {sortedWidgets.map(widget => renderWidget(widget.id))}
                            {provided.placeholder}
                        </div>
                    )}
                </Droppable>
            </DragDropContext>
            {showTaskModal && (
                <div className="modal-overlay" onClick={() => setShowTaskModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h3>New Task</h3>
                        <input
                            type="text"
                            placeholder="Task title"
                            value={newTaskTitle}
                            onChange={e => setNewTaskTitle(e.target.value)}
                        />
                        <textarea
                            placeholder="Task description"
                            value={newTaskDescription}
                            onChange={e => setNewTaskDescription(e.target.value)}
                        ></textarea>
                        <div className="modal-actions">
                            <button onClick={handleCreateTask} disabled={!newTaskTitle.trim()}>Create</button>
                            <button onClick={() => setShowTaskModal(false)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}
            {showNoteModal && (
                <div className="modal-overlay" onClick={() => setShowNoteModal(false)} role="dialog" aria-modal="true" aria-labelledby="note-modal-title">
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h3 id="note-modal-title">New Note</h3>
                        <input
                            type="text"
                            placeholder="Note title"
                            value={newNoteTitle}
                            onChange={e => setNewNoteTitle(e.target.value)}
                            aria-label="Note title"
                        />
                        <textarea
                            placeholder="Note content"
                            value={newNoteContent}
                            onChange={e => setNewNoteContent(e.target.value)}
                            aria-label="Note content"
                        ></textarea>
                        <div className="modal-actions">
                            <button onClick={handleCreateNote} disabled={!newNoteTitle.trim()} aria-label="Create note">Create</button>
                            <button onClick={() => setShowNoteModal(false)} aria-label="Cancel note creation">Cancel</button>
                        </div>
                    </div>
                </div>
            )}
            {showWidgetSettings && (
                <div className="modal-overlay" onClick={() => setShowWidgetSettings(false)} role="dialog" aria-modal="true" aria-labelledby="widget-settings-title">
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h3 id="widget-settings-title">Customize Dashboard Widgets</h3>
                        <div className="widget-settings-list">
                            {widgets.map(widget => (
                                <div key={widget.id} className="widget-setting-item">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={widget.visible}
                                            onChange={() => toggleWidgetVisibility(widget.id)}
                                            aria-label={`Toggle ${widget.title} widget visibility`}
                                        />
                                        {widget.title}
                                    </label>
                                </div>
                            ))}
                        </div>
                        <div className="modal-actions">
                            <button onClick={() => setShowWidgetSettings(false)} aria-label="Close widget settings">Done</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

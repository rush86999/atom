import React, { useState, useEffect } from 'react';
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

// Helper function to check if a date is today
const isToday = (date: Date) => {
    const today = new Date();
    return date.getDate() === today.getDate() &&
           date.getMonth() === today.getMonth() &&
           date.getFullYear() === today.getFullYear();
};

const formatTime = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });


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
        isLoading,
        errors
    } = useAppStore();

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

    // Real-time data polling
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
        const interval = setInterval(pollData, 30000); // Poll every 30 seconds
        return () => clearInterval(interval);
    }, [setLoading, setError]);

    const handleTaskUpdate = (taskId: string, updates: Partial<Task>) => {
        updateTask(taskId, updates);
    };

    const handleCreateTask = () => {
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
                subtasks: []
            });
            setNewTaskTitle('');
            setNewTaskDescription('');
            setShowTaskModal(false);
        }
    };

    const handleCreateNote = () => {
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
    };

    const handleDragEnd = (result: DropResult) => {
        if (!result.destination) return;

        const items = Array.from(widgets);
        const [reorderedItem] = items.splice(result.source.index, 1);
        items.splice(result.destination.index, 0, reorderedItem);

        // Update positions
        const updatedItems = items.map((item, index) => ({ ...item, position: index }));
        setWidgets(updatedItems);

        // Persist to localStorage or user profile
        localStorage.setItem('dashboardWidgets', JSON.stringify(updatedItems));
    };

    const toggleWidgetVisibility = (widgetId: string) => {
        const updatedWidgets = widgets.map(widget =>
            widget.id === widgetId ? { ...widget, visible: !widget.visible } : widget
        );
        setWidgets(updatedWidgets);
    };

    const renderWidget = (widgetId: string) => {
        const widget = widgets.find(w => w.id === widgetId);
        if (!widget?.visible) return null;

        const isLoading = isLoading[widgetId] || false;
        const error = errors[widgetId];

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
                case 'quick-actions':
                    return (
                        <div className="dashboard-card quick-actions" role="region" aria-labelledby="quick-actions-title">
                            <h3 id="quick-actions-title">Quick Actions</h3>
                            <button onClick={() => setShowTaskModal(true)} aria-label="Create new task">+ New Task</button>
                            <button onClick={() => setShowNoteModal(true)} aria-label="Create new note">+ New Note</button>
                            <button aria-label="Schedule meeting">Schedule Meeting</button>
                            <button aria-label="Send quick message">Send Quick Message</button>
                            <button aria-label="Start workflow">Start Workflow</button>
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
                        {isLoading && <div className="loading-spinner" aria-label="Loading">Loading...</div>}
                        {error && <div className="error-message" role="alert">{error}</div>}
                        {!isLoading && !error && widgetContent()}
                    </div>
                )}
            </Draggable>
        );
    };

    return (
        <div className="dashboard-view">
            <header className="view-header">
                <h1>Welcome back, {userProfile?.name.split(' ')[0]}!</h1>
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
                            {widgets
                                .sort((a, b) => a.position - b.position)
                                .map(widget => renderWidget(widget.id))}
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

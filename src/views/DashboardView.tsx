import React, { useState, useEffect } from 'react';
import { 
    CalendarEvent, 
    Task, 
    CommunicationsMessage, 
    Transaction,
    UserProfile
} from '../types';
import { 
    getCalendarEventsForMonth, 
    TASKS_DATA, 
    COMMUNICATIONS_DATA,
    TRANSACTIONS_DATA,
    USER_PROFILE_DATA
} from '../data';

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
const PriorityTasks: React.FC<{ tasks: Task[] }> = ({ tasks }) => {
    const priorityTasks = tasks
        .filter(task => (task.isImportant || task.priority === 'critical' || task.priority === 'high') && task.status !== 'completed')
        .slice(0, 5); // Show top 5

    return (
        <div className="dashboard-card">
            <h3>Priority Tasks</h3>
            {priorityTasks.length > 0 ? (
                <div className="priority-tasks-list">
                    {priorityTasks.map(task => (
                        <div key={task.id} className="priority-task-item">
                            <span className={`priority-indicator ${task.priority}`}></span>
                            <div>
                                <p className="task-title">{task.title}</p>
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


export const DashboardView = () => {
    const [userProfile] = useState<UserProfile>(USER_PROFILE_DATA);
    const [events, setEvents] = useState<CalendarEvent[]>([]);
    const [tasks] = useState<Task[]>(TASKS_DATA);
    const [messages] = useState<CommunicationsMessage[]>(COMMUNICATIONS_DATA);
    const [transactions] = useState<Transaction[]>(TRANSACTIONS_DATA);

    useEffect(() => {
        const today = new Date();
        setEvents(getCalendarEventsForMonth(today.getFullYear(), today.getMonth()));
    }, []);

    return (
        <div className="dashboard-view">
            <header className="view-header">
                <h1>Welcome back, {userProfile.name.split(' ')[0]}!</h1>
                <p>Here's a snapshot of your day.</p>
            </header>
            <div className="dashboard-grid">
                <div className="dashboard-main-column">
                    <TodaysSchedule events={events} />
                    <PriorityTasks tasks={tasks} />
                </div>
                <div className="dashboard-side-column">
                    <InboxSummary messages={messages} />
                    <FinancialSnapshot transactions={transactions} />
                     <div className="dashboard-card quick-actions">
                        <h3>Quick Actions</h3>
                        <button>+ New Task</button>
                        <button>+ New Note</button>
                        <button>Schedule Meeting</button>
                    </div>
                </div>
            </div>
        </div>
    );
};

import React, { useState, useEffect } from 'react';
import { Task } from '../types';
import { TASKS_DATA } from '../data';

const TaskCard: React.FC<{ task: Task; onToggleImportant: (id: string) => void; }> = ({ task, onToggleImportant }) => {
    const isOverdue = new Date(task.dueDate) < new Date() && task.status !== 'completed';
    return (
        <div className={`task-card ${task.isImportant ? 'important' : ''}`}>
            <div className={`priority-indicator ${task.priority}`}></div>
            <div className="task-card-content">
                <h4>{task.title}</h4>
                <p>{task.description}</p>
            </div>
            <div className="task-card-footer">
                <div className={`task-due-date ${isOverdue ? 'overdue' : ''}`}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor"><path d="M8 8a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 8z" /><path fillRule="evenodd" d="M2 3.5c0-.966.784-1.75 1.75-1.75h8.5A1.75 1.75 0 0114 3.5v8.5A1.75 1.75 0 0112.25 14h-8.5A1.75 1.75 0 012 12.25v-8.5ZM3.75 3a.25.25 0 00-.25.25v8.5c0 .138.112.25.25.25h8.5a.25.25 0 00.25-.25v-8.5a.25.25 0 00-.25-.25h-8.5Z" clipRule="evenodd" /></svg>
                    <span>{new Date(task.dueDate).toLocaleDateString()}</span>
                </div>
                <button className="important-toggle" onClick={() => onToggleImportant(task.id)} aria-label={task.isImportant ? "Unmark as important" : "Mark as important"}>
                    {task.isImportant ? (
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10.868 2.884c.321-.772 1.415-.772 1.736 0l1.983 4.795a1 1 0 00.758.548l5.293.769c.84.122 1.177 1.14.566 1.745l-3.83 3.734a1 1 0 00-.287.885l.905 5.272c.143.828-.73 1.464-1.488 1.079L12 18.334a1 1 0 00-.936 0l-4.722 2.484c-.758.385-1.631-.251-1.488-1.08l.905-5.272a1 1 0 00-.287-.885l-3.83-3.734c-.611-.605-.274-1.623.566-1.745l5.293-.769a1 1 0 00.758-.548l1.983-4.795z" clipRule="evenodd" /></svg>
                    ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" /></svg>
                    )}
                </button>
            </div>
        </div>
    );
};

const TaskColumn: React.FC<{ title: string; tasks: Task[]; status: Task['status']; onToggleImportant: (id: string) => void; }> = ({ title, tasks, status, onToggleImportant }) => {
    const columnTasks = tasks.filter(t => t.status === status);
    return (
        <div className="task-column">
            <div className="column-header"><h3>{title}</h3><span className="task-count">{columnTasks.length}</span></div>
            <div className="column-body">{columnTasks.map(task => <TaskCard key={task.id} task={task} onToggleImportant={onToggleImportant} />)}</div>
        </div>
    );
};

export const TasksView = () => {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [statusFilter, setStatusFilter] = useState('all');
    const [priorityFilter, setPriorityFilter] = useState('all');
    const [dateFilter, setDateFilter] = useState('');

    useEffect(() => { setTasks(TASKS_DATA); }, []);

    const handleToggleImportant = (taskId: string) => {
        setTasks(tasks.map(task => 
            task.id === taskId ? { ...task, isImportant: !task.isImportant } : task
        ));
    };

    const clearFilters = () => {
        setStatusFilter('all');
        setPriorityFilter('all');
        setDateFilter('');
    };

    const filteredTasks = tasks
        .filter(task => priorityFilter === 'all' || task.priority === priorityFilter)
        .filter(task => {
            if (!dateFilter) return true;
            const taskDate = new Date(task.dueDate);
            const filterDate = new Date(dateFilter);
            // Compare year, month, and day, ignoring time
            return taskDate.getFullYear() === filterDate.getFullYear() &&
                   taskDate.getMonth() === filterDate.getMonth() &&
                   taskDate.getDate() === filterDate.getDate();
        });

    const statuses: Task['status'][] = ['pending', 'in_progress', 'completed'];
    const columnsToRender = statusFilter === 'all' ? statuses : [statusFilter as Task['status']];

    return (
        <div className="tasks-view">
            <header className="view-header">
                <h1>Task Management</h1>
                <p>Organize your work with a Kanban board.</p>
            </header>

            <div className="tasks-filter-bar">
                <div className="filter-group">
                    <label htmlFor="status-filter">Status</label>
                    <select id="status-filter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
                        <option value="all">All</option>
                        <option value="pending">Pending</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                    </select>
                </div>
                <div className="filter-group">
                    <label htmlFor="priority-filter">Priority</label>
                    <select id="priority-filter" value={priorityFilter} onChange={e => setPriorityFilter(e.target.value)}>
                        <option value="all">All</option>
                        <option value="critical">Critical</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                    </select>
                </div>
                <div className="filter-group">
                    <label htmlFor="date-filter">Due Date</label>
                    <input type="date" id="date-filter" value={dateFilter} onChange={e => setDateFilter(e.target.value)} />
                </div>
                <button className="clear-filters-btn" onClick={clearFilters}>Clear</button>
            </div>

            <div className={`tasks-board cols-${columnsToRender.length}`}>
                {columnsToRender.map(status => (
                    <TaskColumn 
                        key={status}
                        title={status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
                        tasks={filteredTasks}
                        status={status}
                        onToggleImportant={handleToggleImportant}
                    />
                ))}
            </div>
        </div>
    );
};
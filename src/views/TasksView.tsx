import React, { useState, useEffect } from 'react';
import { Task, Subtask } from '../types';
import { TASKS_DATA } from '../data';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

const TaskCard: React.FC<{ task: Task; onToggleImportant: (id: string) => void; onToggleSubtask: (taskId: string, subtaskId: string) => void; }> = ({ task, onToggleImportant, onToggleSubtask }) => {
    const isOverdue = new Date(task.dueDate) < new Date() && task.status !== 'completed';
    return (
        <div className={`task-card ${task.isImportant ? 'important' : ''}`}>
            <div className={`priority-indicator ${task.priority}`}></div>
            <div className="task-card-content">
                <h4>{task.title}</h4>
                <p>{task.description}</p>
                {task.tags && task.tags.length > 0 && (
                    <div className="task-tags">
                        {task.tags.map(tag => <span key={tag} className="tag">{tag}</span>)}
                    </div>
                )}
                {task.subtasks && task.subtasks.length > 0 && (
                    <div className="subtasks">
                        {task.subtasks.map(subtask => (
                            <label key={subtask.id} className="subtask-item">
                                <input
                                    type="checkbox"
                                    checked={subtask.completed}
                                    onChange={() => onToggleSubtask(task.id, subtask.id)}
                                />
                                {subtask.title}
                            </label>
                        ))}
                    </div>
                )}
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

const TaskColumn: React.FC<{ title: string; tasks: Task[]; status: Task['status']; onToggleImportant: (id: string) => void; onToggleSubtask: (taskId: string, subtaskId: string) => void; }> = ({ title, tasks, status, onToggleImportant, onToggleSubtask }) => {
    const columnTasks = tasks.filter(t => t.status === status);
    return (
        <Droppable droppableId={status}>
            {(provided) => (
                <div className="task-column" ref={provided.innerRef} {...provided.droppableProps}>
                    <div className="column-header"><h3>{title}</h3><span className="task-count">{columnTasks.length}</span></div>
                    <div className="column-body">
                        {columnTasks.map((task, index) => (
                            <Draggable key={task.id} draggableId={task.id} index={index}>
                                {(provided) => (
                                    <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}>
                                        <TaskCard task={task} onToggleImportant={onToggleImportant} onToggleSubtask={onToggleSubtask} />
                                    </div>
                                )}
                            </Draggable>
                        ))}
                        {provided.placeholder}
                    </div>
                </div>
            )}
        </Droppable>
    );
};

export const TasksView = () => {
    const { tasks, setTasks, updateTask, deleteTask, addTask } = useAppStore();
    const { toast } = useToast();
    const [statusFilter, setStatusFilter] = useState('all');
    const [priorityFilter, setPriorityFilter] = useState('all');
    const [dateFilter, setDateFilter] = useState('');
    const [assigneeFilter, setAssigneeFilter] = useState('all');
    const [tagFilter, setTagFilter] = useState('all');
    const [selectedTasks, setSelectedTasks] = useState<string[]>([]);

    useEffect(() => {
        if (tasks.length === 0) {
            setTasks(TASKS_DATA);
        }
    }, [tasks.length, setTasks]);

    const handleToggleImportant = (taskId: string) => {
        const task = tasks.find(t => t.id === taskId);
        if (task) {
            updateTask(taskId, { isImportant: !task.isImportant });
            toast.success('Task Updated', `Task marked as ${!task.isImportant ? 'important' : 'not important'}`);
        }
    };

    const handleToggleSubtask = (taskId: string, subtaskId: string) => {
        const task = tasks.find(t => t.id === taskId);
        if (task && task.subtasks) {
            const updatedSubtasks = task.subtasks.map(subtask =>
                subtask.id === subtaskId ? { ...subtask, completed: !subtask.completed } : subtask
            );
            updateTask(taskId, { subtasks: updatedSubtasks });
            toast.success('Subtask Updated', 'Subtask status changed');
        }
    };

    const handleDragEnd = (result: any) => {
        if (!result.destination) return;
        const { source, destination } = result;
        if (source.droppableId === destination.droppableId) return; // Same column

        updateTask(result.draggableId, { status: destination.droppableId as Task['status'] });
        toast.success('Task Moved', `Task moved to ${destination.droppableId.replace('_', ' ')}`);
    };

    const clearFilters = () => {
        setStatusFilter('all');
        setPriorityFilter('all');
        setDateFilter('');
        setAssigneeFilter('all');
        setTagFilter('all');
    };

    const handleSelectTask = (taskId: string) => {
        setSelectedTasks(prev =>
            prev.includes(taskId) ? prev.filter(id => id !== taskId) : [...prev, taskId]
        );
    };

    const handleBulkDelete = () => {
        selectedTasks.forEach(taskId => deleteTask(taskId));
        setSelectedTasks([]);
        toast.success('Tasks Deleted', `${selectedTasks.length} tasks deleted`);
    };

    const filteredTasks = tasks
        .filter(task => priorityFilter === 'all' || task.priority === priorityFilter)
        .filter(task => assigneeFilter === 'all' || task.assignee === assigneeFilter)
        .filter(task => tagFilter === 'all' || task.tags?.includes(tagFilter))
        .filter(task => {
            if (!dateFilter) return true;
            const taskDate = new Date(task.dueDate);
            const filterDate = new Date(dateFilter);
            return taskDate.getFullYear() === filterDate.getFullYear() &&
                   taskDate.getMonth() === filterDate.getMonth() &&
                   taskDate.getDate() === filterDate.getDate();
        });

    const statuses: Task['status'][] = ['pending', 'in_progress', 'completed'];
    const columnsToRender = statusFilter === 'all' ? statuses : [statusFilter as Task['status']];
    const uniqueAssignees = Array.from(new Set(tasks.map(t => t.assignee).filter(Boolean)));
    const uniqueTags = Array.from(new Set(tasks.flatMap(t => t.tags || [])));

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
                    <label htmlFor="assignee-filter">Assignee</label>
                    <select id="assignee-filter" value={assigneeFilter} onChange={e => setAssigneeFilter(e.target.value)}>
                        <option value="all">All</option>
                        {uniqueAssignees.map(assignee => <option key={assignee} value={assignee}>{assignee}</option>)}
                    </select>
                </div>
                <div className="filter-group">
                    <label htmlFor="tag-filter">Tag</label>
                    <select id="tag-filter" value={tagFilter} onChange={e => setTagFilter(e.target.value)}>
                        <option value="all">All</option>
                        {uniqueTags.map(tag => <option key={tag} value={tag}>{tag}</option>)}
                    </select>
                </div>
                <div className="filter-group">
                    <label htmlFor="date-filter">Due Date</label>
                    <input type="date" id="date-filter" value={dateFilter} onChange={e => setDateFilter(e.target.value)} />
                </div>
                <button className="clear-filters-btn" onClick={clearFilters}>Clear</button>
            </div>

            {selectedTasks.length > 0 && (
                <div className="bulk-actions">
                    <span>{selectedTasks.length} selected</span>
                    <button onClick={handleBulkDelete}>Delete Selected</button>
                </div>
            )}

            <DragDropContext onDragEnd={handleDragEnd}>
                <div className={`tasks-board cols-${columnsToRender.length}`}>
                    {columnsToRender.map(status => (
                        <TaskColumn
                            key={status}
                            title={status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
                            tasks={filteredTasks}
                            status={status}
                            onToggleImportant={handleToggleImportant}
                            onToggleSubtask={handleToggleSubtask}
                        />
                    ))}
                </div>
            </DragDropContext>
        </div>
    );
};

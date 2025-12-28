import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Circle, Clock, Layout, ListTodo, Plus, Search, X, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { useRouter } from 'next/router';
import { toast } from 'sonner';
import { CommentSection } from '@/components/shared/CommentSection';
import { useLiveProjects } from '@/hooks/useLiveProjects';
import { useMemorySearch } from '@/hooks/useMemorySearch';
import { PipelineSettingsPanel } from '@/components/shared/PipelineSettingsPanel';
import { Button } from '@/components/ui/button';

interface Task {
    id: string;
    title: string;
    status: string;
    platform: 'jira' | 'asana' | 'trello' | 'monday';
    url: string;
}

import { useWebSocket } from '@/hooks/useWebSocket';

export const ProjectCommandCenter: React.FC = () => {
    const router = useRouter();
    const highlightTaskId = router.query.highlight as string;

    // Parallel Pipeline: Live Data Hook
    const { tasks: liveTasks, stats, isLoading: loading, refresh } = useLiveProjects();
    const [showSettings, setShowSettings] = useState(false);

    // WebSocket for Real-Time Sync Refreshes
    const { lastMessage } = useWebSocket({
        initialChannels: ['communication_stats']
    });

    useEffect(() => {
        if (lastMessage && lastMessage.type === 'status_update') {
            toast.info('Sync complete: Refreshing project data...');
            refresh();
        }
    }, [lastMessage, refresh]);

    // Unified Search
    const [searchQuery, setSearchQuery] = useState('');
    const [showSearchResults, setShowSearchResults] = useState(false);
    const { results: searchResults, isSearching, searchMemory, clearSearch } = useMemorySearch({ tag: 'project' });

    // Map unified tasks to component expected format
    const tasks: Task[] = liveTasks.map(t => ({
        id: t.id,
        title: t.name,
        status: t.status,
        platform: t.platform as any,
        url: t.url || '#'
    }));

    useEffect(() => {
        if (highlightTaskId) {
            toast.info(`Highlighting related task: ${highlightTaskId}`);
        }
    }, [highlightTaskId]);

    const getPlatformColor = (platform: string) => {
        switch (platform) {
            case 'jira': return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
            case 'asana': return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
            case 'trello': return 'bg-sky-500/10 text-sky-500 border-sky-500/20';
            case 'monday': return 'bg-indigo-500/10 text-indigo-500 border-indigo-500/20';
            default: return 'bg-gray-500/10 text-gray-500 border-gray-500/20';
        }
    };

    const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
        const query = e.target.value;
        setSearchQuery(query);
        if (query.length > 2) {
            searchMemory(query);
            setShowSearchResults(true);
        } else {
            setShowSearchResults(false);
            clearSearch();
        }
    };

    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newTask, setNewTask] = useState({ title: '', platform: 'jira' as 'jira' | 'asana' });
    const [creating, setCreating] = useState(false);

    const handleCreateTask = async () => {
        if (!newTask.title) return;
        try {
            setCreating(true);
            await axios.post('/api/intelligence/execute', {
                action_type: 'tool',
                action_payload: {
                    tool_name: 'create_task',
                    arguments: {
                        title: newTask.title,
                        platform: newTask.platform,
                        status: 'To Do'
                    }
                }
            });
            toast.success(`Task created successfully in ${newTask.platform}`);
            setShowCreateModal(false);
            setNewTask({ title: '', platform: 'jira' });
            refresh();
        } catch (error) {
            console.error('Failed to create task:', error);
            toast.error('Failed to create task across systems.');
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto animate-in fade-in duration-700">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
                        Project Command Center
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Unified view across all your project management platforms.
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowSettings(!showSettings)}
                        className="bg-white/5 border-white/10"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Sync Settings
                    </Button>
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-lg transition-all text-sm font-semibold"
                    >
                        <Plus className="w-4 h-4" />
                        Quick Create
                    </button>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search tasks..."
                            className="pl-10 pr-10 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm w-64 text-white"
                            value={searchQuery}
                            onChange={handleSearch}
                        />
                        {searchQuery && (
                            <button
                                onClick={() => { setSearchQuery(''); setShowSearchResults(false); clearSearch(); }}
                                className="absolute right-3 top-1/2 -translate-y-1/2"
                            >
                                <X className="w-4 h-4 text-muted-foreground hover:text-white" />
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {showCreateModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
                    <div className="bg-[#121212] border border-white/10 rounded-xl p-6 w-[400px] shadow-2xl animate-in zoom-in-95 duration-300">
                        <h2 className="text-xl font-bold mb-4 text-white">Quick Create Task</h2>
                        <div className="space-y-4">
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold mb-1.5 block">Task Title</label>
                                <input
                                    autoFocus
                                    className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                                    placeholder="Enter task summary..."
                                    value={newTask.title}
                                    onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold mb-1.5 block">Platform</label>
                                <div className="grid grid-cols-2 gap-2">
                                    {(['jira', 'asana'] as const).map(p => (
                                        <button
                                            key={p}
                                            onClick={() => setNewTask({ ...newTask, platform: p })}
                                            className={`py-2 rounded-lg border text-sm capitalize transition-all ${newTask.platform === p
                                                ? 'bg-primary/20 border-primary text-primary'
                                                : 'bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10'
                                                }`}
                                        >
                                            {p}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="flex gap-3 pt-4">
                                <button
                                    disabled={creating}
                                    onClick={() => setShowCreateModal(false)}
                                    className="flex-1 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white transition-all text-sm"
                                >
                                    Cancel
                                </button>
                                <button
                                    disabled={creating || !newTask.title}
                                    onClick={handleCreateTask}
                                    className="flex-1 py-2 rounded-lg bg-primary hover:bg-primary-hover text-primary-foreground font-bold transition-all text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                                >
                                    {creating && <div className="w-3 h-3 border-2 border-primary-foreground/20 border-t-primary-foreground rounded-full animate-spin" />}
                                    {creating ? 'Creating...' : 'Create Task'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <PipelineSettingsPanel isOpen={showSettings} />

            {showSearchResults ? (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold text-white">Search Results for "{searchQuery}"</h2>
                        <button onClick={() => { setShowSearchResults(false); setSearchQuery(''); clearSearch(); }} className="text-sm text-primary hover:underline">Clear Search</button>
                    </div>
                    {isSearching ? (
                        <div className="flex items-center gap-2 text-muted-foreground"><Clock className="w-4 h-4 animate-spin" /> Searching memory...</div>
                    ) : searchResults.length > 0 ? (
                        <div className="grid grid-cols-1 gap-4">
                            {searchResults.map((result) => (
                                <Card key={result.id} className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors pointer-cursor">
                                    <CardContent className="p-4">
                                        <div className="flex justify-between items-start mb-2">
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="capitalize text-[10px]">{result.app_type}</Badge>
                                                <span className="font-semibold text-white">{result.subject || result.sender}</span>
                                            </div>
                                            <span className="text-xs text-muted-foreground">{new Date(result.timestamp).toLocaleString()}</span>
                                        </div>
                                        <p className="text-sm text-gray-300 line-clamp-2">{result.content}</p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12 text-muted-foreground border border-dashed border-white/10 rounded-xl">No historical records found for "{searchQuery}".</div>
                    )}
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    <div className="lg:col-span-3 space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Total Tasks</CardTitle>
                                    <Layout className="w-4 h-4 text-primary" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">{tasks.length}</div>
                                    <p className="text-xs text-muted-foreground mt-1">+2 from yesterday</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Active Platforms</CardTitle>
                                    <Clock className="w-4 h-4 text-blue-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">
                                        {Object.keys(stats.tasks_by_platform || {}).length || 0}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1 font-mono">
                                        {Object.keys(stats.tasks_by_platform || {}).join(', ')}
                                    </p>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                    <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Critical Overdue</CardTitle>
                                    <CheckCircle2 className="w-4 h-4 text-green-400" />
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold text-white">
                                        {stats.overdue_count}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1">High Priority</p>
                                </CardContent>
                            </Card>
                        </div>

                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="text-xs text-muted-foreground uppercase bg-white/5">
                                        <tr>
                                            <th className="px-6 py-4 font-semibold">ID</th>
                                            <th className="px-6 py-4 font-semibold">Task</th>
                                            <th className="px-6 py-4 font-semibold">Platform</th>
                                            <th className="px-6 py-4 font-semibold">Status</th>
                                            <th className="px-6 py-4 font-semibold">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {loading ? (
                                            Array.from({ length: 3 }).map((_, i) => (
                                                <tr key={i} className="animate-pulse">
                                                    <td colSpan={5} className="px-6 py-8 h-16 bg-white/2" />
                                                </tr>
                                            ))
                                        ) : tasks.filter(t => t.title.toLowerCase().includes(searchQuery.toLowerCase())).map((task) => (
                                            <tr
                                                key={task.id}
                                                className={`hover:bg-white/5 transition-all duration-500 group ${highlightTaskId === task.id ? 'bg-primary/10 border-l-2 border-l-primary ring-1 ring-primary/20' : ''
                                                    }`}
                                            >
                                                <td className="px-6 py-4 font-mono text-xs text-muted-foreground">
                                                    {task.id}
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="font-medium text-white group-hover:text-primary transition-colors">
                                                        {task.title}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <Badge variant="outline" className={`capitalize font-medium ${getPlatformColor(task.platform)}`}>
                                                        {task.platform}
                                                    </Badge>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <span className="flex items-center gap-2 text-muted-foreground">
                                                        {task.status === 'Done' || task.status === 'Completed' ? (
                                                            <CheckCircle2 className="w-4 h-4 text-green-400" />
                                                        ) : (
                                                            <Circle className="w-4 h-4" />
                                                        )}
                                                        {task.status}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <a
                                                        href={task.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-primary hover:underline font-medium"
                                                    >
                                                        View details
                                                    </a>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    </div>

                    <div className="lg:col-span-1 h-[600px] lg:h-[calc(100vh-200px)] sticky top-6">
                        <CommentSection channel="projects" title="Project Collab" />
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProjectCommandCenter;

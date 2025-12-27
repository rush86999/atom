import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Circle, Clock, Layout, ListTodo, Plus, Search } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';
import { CommentSection } from '@/components/shared/CommentSection';

interface Task {
    id: string;
    title: string;
    status: string;
    platform: 'jira' | 'asana' | 'trello' | 'monday';
    url: string;
}

export const ProjectCommandCenter: React.FC = () => {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');

    const fetchTasks = async () => {
        try {
            setLoading(true);
            const response = await axios.get<Task[]>('/api/projects/unified-tasks');
            setTasks(response.data);
        } catch (error) {
            console.error('Failed to fetch tasks:', error);
            toast.error('Failed to load project data. Integration required.');
            setTasks([
                { id: 'ATOM-101', title: 'Implement WebSocket Sync', status: 'In Progress', platform: 'jira', url: '#' },
                { id: '982734', title: 'Update Sidebar Glow Effect', status: 'To Do', platform: 'asana', url: '#' },
                { id: 'card_55', title: 'Finalize Phase 14 Assets', status: 'Done', platform: 'trello', url: '#' }
            ]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTasks();
    }, []);

    const getPlatformColor = (platform: string) => {
        switch (platform) {
            case 'jira': return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
            case 'asana': return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
            case 'trello': return 'bg-sky-500/10 text-sky-500 border-sky-500/20';
            case 'monday': return 'bg-indigo-500/10 text-indigo-500 border-indigo-500/20';
            default: return 'bg-gray-500/10 text-gray-500 border-gray-500/20';
        }
    };

    const filteredTasks = tasks.filter(t =>
        t.title.toLowerCase().includes(filter.toLowerCase()) ||
        t.platform.toLowerCase().includes(filter.toLowerCase())
    );

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
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search tasks..."
                            className="pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm w-64 text-white"
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                        />
                    </div>
                </div>
            </div>

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
                                    {new Set(tasks.map(t => t.platform)).size}
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">Jira, Asana, Trello</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-black/40 border-white/5 backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground uppercase">Completion</CardTitle>
                                <CheckCircle2 className="w-4 h-4 text-green-400" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-white">
                                    {tasks.length > 0 ? Math.round((tasks.filter(t => t.status === 'Done' || t.status === 'Completed').length / tasks.length) * 100) : 0}%
                                </div>
                                <div className="w-full bg-white/5 rounded-full h-1 mt-2">
                                    <div
                                        className="bg-green-400 h-1 rounded-full transition-all duration-1000"
                                        style={{ width: `${tasks.length > 0 ? (tasks.filter(t => t.status === 'Done' || t.status === 'Completed').length / tasks.length) * 100 : 0}%` }}
                                    />
                                </div>
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
                                    ) : filteredTasks.map((task) => (
                                        <tr key={task.id} className="hover:bg-white/5 transition-colors group">
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
        </div>
    );
};

export default ProjectCommandCenter;

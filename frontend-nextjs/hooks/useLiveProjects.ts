import { useState, useEffect } from 'react';

export interface UnifiedTask {
    id: string;
    name: string;
    platform: 'asana' | 'jira' | 'trello' | 'clickup' | 'zoho' | 'planner';
    status: string;
    priority?: string;
    assignee?: string;
    due_date?: string;
    project_name?: string;
    url?: string;
}

export interface ProjectStats {
    total_active_tasks: number;
    completed_today: number;
    overdue_count: number;
    tasks_by_platform: Record<string, number>;
}

interface LiveProjectsResponse {
    ok: boolean;
    stats: ProjectStats;
    tasks: UnifiedTask[];
    providers: Record<string, boolean>;
}

export function useLiveProjects() {
    const [tasks, setTasks] = useState<UnifiedTask[]>([]);
    const [stats, setStats] = useState<ProjectStats>({
        total_active_tasks: 0,
        completed_today: 0,
        overdue_count: 0,
        tasks_by_platform: {}
    });
    const [isLoading, setIsLoading] = useState(true);
    const [activeProviders, setActiveProviders] = useState<Record<string, boolean>>({});

    const fetchLiveBoard = async () => {
        try {
            const res = await fetch('/api/atom/projects/live/board');
            if (res.ok) {
                const data: LiveProjectsResponse = await res.json();
                setTasks(data.tasks);
                setStats(data.stats);
                setActiveProviders(data.providers);
            }
        } catch (error) {
            console.error("Failed to fetch live project board:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchLiveBoard();

        // Poll every 60s
        const interval = setInterval(fetchLiveBoard, 60000);
        return () => clearInterval(interval);
    }, []);

    return {
        tasks,
        stats,
        isLoading,
        activeProviders,
        refresh: fetchLiveBoard
    };
}

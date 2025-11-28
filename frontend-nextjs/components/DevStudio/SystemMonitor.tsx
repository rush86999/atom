import React, { useState, useEffect } from 'react';
import { CheckCircle, AlertTriangle, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Spinner } from '../ui/spinner';

interface SystemStatusData {
    timestamp: string;
    overall_status: string;
    resources: {
        cpu: {
            percent: number;
            count: number;
        };
        memory: {
            percent: number;
            system_used_percent: number;
            system_total_mb: number;
            system_available_mb: number;
        };
        disk: {
            percent: number;
            free_gb: number;
            total_gb: number;
        };
    };
    services: {
        [key: string]: {
            name: string;
            status: string;
            response_time_ms: number;
        };
    };
    uptime: {
        system_seconds: number;
    };
}

const SystemMonitor = () => {
    const [status, setStatus] = useState<SystemStatusData | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchStatus = async () => {
        try {
            const response = await fetch('/api/system/status');
            const data = await response.json();
            setStatus(data);
            setLoading(false);
        } catch (error) {
            console.error("Failed to fetch system status:", error);
        }
    };

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 5000); // Refresh every 5 seconds
        return () => clearInterval(interval);
    }, []);

    if (!status) {
        return (
            <div className="flex justify-center p-4">
                <Spinner size="sm" />
            </div>
        );
    }

    const formatUptime = (seconds: number) => {
        const days = Math.floor(seconds / (3600 * 24));
        const hours = Math.floor((seconds % (3600 * 24)) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${days}d ${hours}h ${minutes}m`;
    };

    const getStatusColor = (status: string) => {
        switch (status?.toLowerCase()) {
            case 'healthy':
            case 'operational':
                return 'success';
            case 'degraded':
                return 'warning';
            case 'unhealthy':
            case 'unreachable':
                return 'destructive';
            default:
                return 'secondary';
        }
    };

    const getProgressColor = (percent: number) => {
        if (percent > 90) return 'bg-red-600';
        if (percent > 75) return 'bg-orange-500';
        return 'bg-blue-600';
    };

    return (
        <div className="p-4 space-y-6">
            <div className="flex justify-between items-center">
                <div className="space-y-1">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">System Monitor</h2>
                    <p className="text-sm text-gray-500">Last updated: {new Date(status.timestamp).toLocaleTimeString()}</p>
                </div>
                <Badge
                    variant={getStatusColor(status.overall_status) as "success" | "warning" | "destructive" | "secondary"}
                    className="text-lg px-3 py-1"
                >
                    System: {status.overall_status.toUpperCase()}
                </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card>
                    <CardContent className="pt-6">
                        <div className="space-y-2">
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">CPU Usage</p>
                            <div className="text-2xl font-bold">{status.resources.cpu.percent}%</div>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {status.resources.cpu.count} Cores Active
                            </p>
                            <Progress
                                value={status.resources.cpu.percent}
                                indicatorClassName={getProgressColor(status.resources.cpu.percent)}
                                className="mt-2"
                            />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="space-y-2">
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Memory Usage</p>
                            <div className="text-2xl font-bold">{status.resources.memory.percent}%</div>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {status.resources.memory.system_available_mb} MB Available
                            </p>
                            <Progress
                                value={status.resources.memory.percent}
                                indicatorClassName={getProgressColor(status.resources.memory.percent)}
                                className="mt-2"
                            />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="space-y-2">
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">System Uptime</p>
                            <div className="text-2xl font-bold">{formatUptime(status.uptime.system_seconds)}</div>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                Since last reboot
                            </p>
                            <div className="mt-2 h-2 w-full rounded-full bg-green-100 dark:bg-green-900/30">
                                <div className="h-full w-full rounded-full bg-green-500" />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="space-y-4">
                <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">Service Health</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(status.services).map(([key, service]) => (
                        <Card key={key}>
                            <CardContent className="pt-6">
                                <div className="flex justify-between items-start mb-2">
                                    <span className="font-bold text-gray-900 dark:text-gray-100">{service.name}</span>
                                    {service.status === 'healthy' ? (
                                        <CheckCircle className="h-5 w-5 text-green-500" />
                                    ) : (
                                        <AlertTriangle className="h-5 w-5 text-yellow-500" />
                                    )}
                                </div>
                                <div className="flex justify-between items-center">
                                    <Badge variant={getStatusColor(service.status) as any}>
                                        {service.status}
                                    </Badge>
                                    <span className="text-xs text-gray-500">{service.response_time_ms}ms</span>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default SystemMonitor;


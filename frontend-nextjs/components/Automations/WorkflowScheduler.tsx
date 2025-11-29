import React, { useState, useEffect } from 'react';
import { Trash2, RefreshCw, Clock, Repeat, Calendar } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";

interface ScheduleConfig {
    trigger_type: 'cron' | 'interval' | 'date';
    trigger_config: Record<string, any>;
    input_data?: Record<string, any>;
}

interface ScheduledJob {
    id: string;
    next_run_time: string | null;
    trigger: string;
}

interface WorkflowSchedulerProps {
    workflowId: string;
    workflowName?: string;
}

const WorkflowScheduler: React.FC<WorkflowSchedulerProps> = ({
    workflowId,
    workflowName
}) => {
    const [scheduleType, setScheduleType] = useState<'cron' | 'interval' | 'date'>('interval');
    const [loading, setLoading] = useState(false);
    const [scheduledJobs, setScheduledJobs] = useState<ScheduledJob[]>([]);
    const [refreshing, setRefreshing] = useState(false);
    const { toast } = useToast();

    const [intervalMinutes, setIntervalMinutes] = useState(30);
    const [intervalHours, setIntervalHours] = useState(0);
    const [intervalDays, setIntervalDays] = useState(0);

    const [cronExpression, setCronExpression] = useState('0 9 * * *');
    const [cronPreset, setCronPreset] = useState('daily_9am');

    const [runDate, setRunDate] = useState('');
    const [runTime, setRunTime] = useState('');

    const cronPresets = [
        { value: 'custom', label: 'Custom', expression: '' },
        { value: 'hourly', label: 'Every Hour', expression: '0 * * * *' },
        { value: 'daily_9am', label: 'Daily at 9 AM', expression: '0 9 * * *' },
        { value: 'daily_5pm', label: 'Daily at 5 PM', expression: '0 17 * * *' },
        { value: 'weekly_monday', label: 'Weekly on Monday', expression: '0 9 * * 1' },
        { value: 'monthly', label: 'Monthly (1st day)', expression: '0 9 1 * *' },
    ];

    useEffect(() => {
        loadScheduledJobs();
    }, [workflowId]);

    const loadScheduledJobs = async () => {
        try {
            setRefreshing(true);
            const response = await fetch('/api/v1/scheduler/jobs');
            if (response.ok) {
                const allJobs = await response.json();
                const workflowJobs = allJobs.filter((job: ScheduledJob) =>
                    job.id.includes(workflowId)
                );
                setScheduledJobs(workflowJobs);
            }
        } catch (error) {
            console.error('Error loading scheduled jobs:', error);
        } finally {
            setRefreshing(false);
        }
    };

    const handleSchedule = async () => {
        if (!workflowId) {
            toast({
                title: 'Error',
                description: 'Workflow must be saved first',
                variant: 'destructive',
            });
            return;
        }

        let scheduleConfig: ScheduleConfig;

        try {
            setLoading(true);

            switch (scheduleType) {
                case 'interval':
                    const totalSeconds =
                        intervalDays * 86400 +
                        intervalHours * 3600 +
                        intervalMinutes * 60;

                    if (totalSeconds === 0) {
                        throw new Error('Please specify an interval');
                    }

                    scheduleConfig = {
                        trigger_type: 'interval',
                        trigger_config: { seconds: totalSeconds }
                    };
                    break;

                case 'cron':
                    if (!cronExpression.trim()) {
                        throw new Error('Please enter a cron expression');
                    }

                    const cronParts = cronExpression.trim().split(' ');
                    if (cronParts.length !== 5) {
                        throw new Error('Invalid cron expression format (use 5 fields)');
                    }

                    scheduleConfig = {
                        trigger_type: 'cron',
                        trigger_config: {
                            minute: cronParts[0],
                            hour: cronParts[1],
                            day: cronParts[2],
                            month: cronParts[3],
                            day_of_week: cronParts[4]
                        }
                    };
                    break;

                case 'date':
                    if (!runDate || !runTime) {
                        throw new Error('Please specify both date and time');
                    }

                    const runDateTime = new Date(`${runDate}T${runTime}:00`);

                    if (runDateTime <= new Date()) {
                        throw new Error('Run time must be in the future');
                    }

                    scheduleConfig = {
                        trigger_type: 'date',
                        trigger_config: {
                            run_date: runDateTime.toISOString()
                        }
                    };
                    break;

                default:
                    throw new Error('Invalid schedule type');
            }

            const response = await fetch(`/api/v1/workflows/${workflowId}/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scheduleConfig),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to schedule workflow');
            }

            const result = await response.json();

            toast({
                title: 'Workflow Scheduled',
                description: `Job ID: ${result.job_id}`,
            });

            await loadScheduledJobs();

            if (scheduleType === 'date') {
                setRunDate('');
                setRunTime('');
            }
        } catch (error) {
            toast({
                title: 'Scheduling Failed',
                description: error instanceof Error ? error.message : 'Unknown error',
                variant: 'destructive',
            });
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteSchedule = async (jobId: string) => {
        try {
            const response = await fetch(`/api/v1/workflows/${workflowId}/schedule/${jobId}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                throw new Error('Failed to delete schedule');
            }

            toast({ title: 'Schedule Deleted' });
            await loadScheduledJobs();
        } catch (error) {
            toast({
                title: 'Error',
                description: error instanceof Error ? error.message : 'Failed to delete schedule',
                variant: 'destructive',
            });
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-semibold mb-2">Schedule Workflow</h2>
                {workflowName && (
                    <p className="text-sm text-muted-foreground">Workflow: {workflowName}</p>
                )}
            </div>

            <Tabs defaultValue="interval" onValueChange={(v) => setScheduleType(v as any)}>
                <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="interval">
                        <Repeat className="mr-2 h-4 w-4" />
                        Interval
                    </TabsTrigger>
                    <TabsTrigger value="cron">
                        <Clock className="mr-2 h-4 w-4" />
                        Cron
                    </TabsTrigger>
                    <TabsTrigger value="date">
                        <Calendar className="mr-2 h-4 w-4" />
                        Specific Date
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="interval">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Run at Regular Intervals</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <Alert>
                                <AlertTitle>Interval Schedule</AlertTitle>
                                <AlertDescription>
                                    The workflow will run repeatedly at the specified interval.
                                </AlertDescription>
                            </Alert>

                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <Label>Days</Label>
                                    <Input
                                        type="number"
                                        min="0"
                                        value={intervalDays}
                                        onChange={(e) => setIntervalDays(parseInt(e.target.value) || 0)}
                                    />
                                </div>
                                <div>
                                    <Label>Hours</Label>
                                    <Input
                                        type="number"
                                        min="0"
                                        max="23"
                                        value={intervalHours}
                                        onChange={(e) => setIntervalHours(parseInt(e.target.value) || 0)}
                                    />
                                </div>
                                <div>
                                    <Label>Minutes</Label>
                                    <Input
                                        type="number"
                                        min="0"
                                        max="59"
                                        value={intervalMinutes}
                                        onChange={(e) => setIntervalMinutes(parseInt(e.target.value) || 0)}
                                    />
                                </div>
                            </div>

                            <p className="text-sm text-muted-foreground">
                                Total: {intervalDays}d {intervalHours}h {intervalMinutes}m
                            </p>

                            <Button onClick={handleSchedule} disabled={loading}>
                                {loading ? 'Scheduling...' : 'Schedule Workflow'}
                            </Button>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="cron">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Schedule with Cron Expression</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <Alert>
                                <AlertTitle>Cron Schedule</AlertTitle>
                                <AlertDescription>
                                    Use cron expressions for complex scheduling patterns.
                                </AlertDescription>
                            </Alert>

                            <div>
                                <Label>Preset Schedules</Label>
                                <Select
                                    value={cronPreset}
                                    onValueChange={(value) => {
                                        const preset = cronPresets.find(p => p.value === value);
                                        setCronPreset(value);
                                        if (preset && preset.expression) {
                                            setCronExpression(preset.expression);
                                        }
                                    }}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {cronPresets.map(preset => (
                                            <SelectItem key={preset.value} value={preset.value}>
                                                {preset.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div>
                                <Label>Cron Expression</Label>
                                <Input
                                    value={cronExpression}
                                    onChange={(e) => {
                                        setCronExpression(e.target.value);
                                        setCronPreset('custom');
                                    }}
                                    placeholder="0 9 * * *"
                                    className="font-mono"
                                />
                                <p className="text-xs text-muted-foreground mt-1">
                                    Format: minute hour day month day_of_week (e.g., "0 9 * * *" = Daily at 9 AM)
                                </p>
                            </div>

                            <Button onClick={handleSchedule} disabled={loading}>
                                {loading ? 'Scheduling...' : 'Schedule Workflow'}
                            </Button>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="date">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Run Once at Specific Time</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <Alert>
                                <AlertTitle>One-Time Schedule</AlertTitle>
                                <AlertDescription>
                                    The workflow will run once at the specified date and time.
                                </AlertDescription>
                            </Alert>

                            <div>
                                <Label>Date</Label>
                                <Input
                                    type="date"
                                    value={runDate}
                                    onChange={(e) => setRunDate(e.target.value)}
                                    min={new Date().toISOString().split('T')[0]}
                                />
                            </div>

                            <div>
                                <Label>Time</Label>
                                <Input
                                    type="time"
                                    value={runTime}
                                    onChange={(e) => setRunTime(e.target.value)}
                                />
                            </div>

                            {runDate && runTime && (
                                <p className="text-sm text-muted-foreground">
                                    Will run at: {new Date(`${runDate}T${runTime}`).toLocaleString()}
                                </p>
                            )}

                            <Button onClick={handleSchedule} disabled={loading}>
                                {loading ? 'Scheduling...' : 'Schedule Workflow'}
                            </Button>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            <Card>
                <CardHeader>
                    <div className="flex justify-between items-center">
                        <CardTitle className="text-base">Scheduled Jobs</CardTitle>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={loadScheduledJobs}
                            disabled={refreshing}
                        >
                            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </CardHeader>
                <CardContent>
                    {scheduledJobs.length === 0 ? (
                        <p className="text-muted-foreground text-center py-4">
                            No scheduled jobs for this workflow
                        </p>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Job ID</TableHead>
                                    <TableHead>Next Run</TableHead>
                                    <TableHead>Trigger</TableHead>
                                    <TableHead className="w-24">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {scheduledJobs.map((job) => (
                                    <TableRow key={job.id}>
                                        <TableCell className="font-mono text-xs">{job.id}</TableCell>
                                        <TableCell>
                                            {job.next_run_time
                                                ? new Date(job.next_run_time).toLocaleString()
                                                : 'Never'}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="secondary">
                                                {job.trigger.split('[')[0]}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleDeleteSchedule(job.id)}
                                            >
                                                <Trash2 className="h-4 w-4 text-red-500" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

export default WorkflowScheduler;

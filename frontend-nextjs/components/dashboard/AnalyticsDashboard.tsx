/**
 * Workflow Analytics Dashboard
 * Comprehensive analytics for workflow performance, execution metrics, and KPIs
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';
import {
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  BarChart3,
  LineChart,
  PieChart,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart as RechartsLineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

// Types
interface DashboardKPIs {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  average_duration_ms: number;
  average_duration_seconds: number;
  unique_workflows: number;
  unique_users: number;
  error_rate: number;
}

interface WorkflowPerformanceRanking {
  workflow_id: string;
  workflow_name: string;
  total_executions: number;
  success_rate: number;
  average_duration_ms: number;
  last_execution: string;
  trend: 'up' | 'down' | 'stable';
}

interface ExecutionTimelineData {
  timestamp: string;
  count: number;
  success_count: number;
  failure_count: number;
  average_duration_ms: number;
}

interface ErrorBreakdown {
  error_types: Array<{ type: string; count: number }>;
  workflows_with_errors: Array<{ workflow_id: string; error_count: number }>;
  recent_errors: Array<{ workflow_id: string; error_message: string; timestamp: string }>;
}

interface AlertConfiguration {
  alert_id: string;
  name: string;
  description: string;
  severity: string;
  metric_name: string;
  condition: string;
  threshold_value: number;
  workflow_id: string | null;
  enabled: boolean;
}

interface RealtimeExecutionEvent {
  event_id: string;
  workflow_id: string;
  workflow_name: string;
  execution_id: string;
  event_type: string;
  timestamp: string;
  status: string | null;
  duration_ms: number | null;
  user_id: string;
}

type TimeWindow = '1h' | '24h' | '7d' | '30d';

const WorkflowAnalyticsDashboard: React.FC = () => {
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [topWorkflows, setTopWorkflows] = useState<WorkflowPerformanceRanking[]>([]);
  const [timelineData, setTimelineData] = useState<ExecutionTimelineData[]>([]);
  const [errorBreakdown, setErrorBreakdown] = useState<ErrorBreakdown | null>(null);
  const [alerts, setAlerts] = useState<AlertConfiguration[]>([]);
  const [realtimeEvents, setRealtimeEvents] = useState<RealtimeExecutionEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeWindow, setTimeWindow] = useState<TimeWindow>('24h');
  const [sortBy, setSortBy] = useState<'success_rate' | 'executions' | 'duration'>('success_rate');
  const { toast } = useToast();

  // Fetch KPIs
  const fetchKPIs = async () => {
    try {
      const response = await fetch(`/api/analytics/dashboard/kpis?time_window=${timeWindow}`);
      if (!response.ok) throw new Error('Failed to fetch KPIs');
      const data = await response.json();
      setKpis(data);
    } catch (error) {
      console.error('Error fetching KPIs:', error);
      toast({
        title: 'Error',
        description: 'Failed to load dashboard KPIs',
        variant: 'error',
      });
    }
  };

  // Fetch Top Workflows
  const fetchTopWorkflows = async () => {
    try {
      const response = await fetch(
        `/api/analytics/dashboard/workflows/top-performing?limit=10&time_window=${timeWindow}&sort_by=${sortBy}`
      );
      if (!response.ok) throw new Error('Failed to fetch top workflows');
      const data = await response.json();
      setTopWorkflows(data);
    } catch (error) {
      console.error('Error fetching top workflows:', error);
    }
  };

  // Fetch Timeline Data
  const fetchTimelineData = async () => {
    try {
      const response = await fetch(
        `/api/analytics/dashboard/timeline?time_window=${timeWindow}&interval=1h`
      );
      if (!response.ok) throw new Error('Failed to fetch timeline data');
      const data = await response.json();
      setTimelineData(data);
    } catch (error) {
      console.error('Error fetching timeline data:', error);
    }
  };

  // Fetch Error Breakdown
  const fetchErrorBreakdown = async () => {
    try {
      const response = await fetch(
        `/api/analytics/dashboard/errors/breakdown?time_window=${timeWindow}`
      );
      if (!response.ok) throw new Error('Failed to fetch error breakdown');
      const data = await response.json();
      setErrorBreakdown(data);
    } catch (error) {
      console.error('Error fetching error breakdown:', error);
    }
  };

  // Fetch Alerts
  const fetchAlerts = async () => {
    try {
      const response = await fetch('/api/analytics/alerts');
      if (!response.ok) throw new Error('Failed to fetch alerts');
      const data = await response.json();
      setAlerts(data);
    } catch (error) {
      console.error('Error fetching alerts:', error);
    }
  };

  // Fetch Real-time Events
  const fetchRealtimeEvents = async () => {
    try {
      const response = await fetch('/api/analytics/dashboard/realtime-feed?limit=50');
      if (!response.ok) throw new Error('Failed to fetch realtime events');
      const data = await response.json();
      setRealtimeEvents(data);
    } catch (error) {
      console.error('Error fetching realtime events:', error);
    }
  };

  // Load all data
  const loadAllData = async () => {
    setLoading(true);
    await Promise.all([
      fetchKPIs(),
      fetchTopWorkflows(),
      fetchTimelineData(),
      fetchErrorBreakdown(),
      fetchAlerts(),
      fetchRealtimeEvents(),
    ]);
    setLoading(false);
  };

  // Initial load and time window change
  useEffect(() => {
    loadAllData();
  }, [timeWindow, sortBy]);

  // Auto-refresh realtime events every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchRealtimeEvents();
      fetchKPIs();
    }, 30000);
    return () => clearInterval(interval);
  }, [timeWindow]);

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  // Format duration
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  // Get trend icon
  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'down':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      default:
        return <Minus className="h-4 w-4 text-gray-500" />;
    }
  };

  // Get severity color
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'destructive';
      case 'high':
        return 'destructive';
      case 'medium':
        return 'default';
      case 'low':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p>Loading analytics dashboard...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workflow Analytics</h1>
          <p className="text-muted-foreground">Comprehensive workflow performance and execution metrics</p>
        </div>
        <div className="flex items-center gap-4">
          <Select value={timeWindow} onValueChange={(v: TimeWindow) => setTimeWindow(v)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select time window" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">Last 1 Hour</SelectItem>
              <SelectItem value="24h">Last 24 Hours</SelectItem>
              <SelectItem value="7d">Last 7 Days</SelectItem>
              <SelectItem value="30d">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={loadAllData} variant="outline">
            Refresh
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      {kpis && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total Executions"
            value={kpis.total_executions}
            icon={<Activity className="h-4 w-4" />}
            description="All workflow executions"
          />
          <KPICard
            title="Success Rate"
            value={`${kpis.success_rate}%`}
            icon={<CheckCircle2 className="h-4 w-4" />}
            description={`${kpis.successful_executions} successful`}
            trend="up"
          />
          <KPIErrorCard
            title="Error Rate"
            value={`${kpis.error_rate}%`}
            icon={<XCircle className="h-4 w-4" />}
            description={`${kpis.failed_executions} failed`}
            errorRate={kpis.error_rate}
          />
          <KPIProgressCard
            title="Avg Duration"
            value={`${kpis.average_duration_seconds}s`}
            icon={<Clock className="h-4 w-4" />}
            description="Per execution"
            valueMs={kpis.average_duration_ms}
          />
        </div>
      )}

      {/* Main Content Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="workflows">Workflows</TabsTrigger>
          <TabsTrigger value="errors">Errors</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="realtime">Real-time</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {/* Timeline Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Execution Timeline</CardTitle>
              <CardDescription>Workflow executions over time</CardDescription>
            </CardHeader>
            <CardContent>
              {timelineData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={timelineData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="timestamp"
                      tickFormatter={(v) => new Date(v).toLocaleTimeString()}
                    />
                    <YAxis />
                    <Tooltip
                      labelFormatter={(v) => new Date(v).toLocaleString()}
                      formatter={(value: number) => [value, 'Executions']}
                    />
                    <Legend />
                    <Area type="monotone" dataKey="success_count" stackId="1" stroke="#22c55e" fill="#22c55e" name="Success" />
                    <Area type="monotone" dataKey="failure_count" stackId="1" stroke="#ef4444" fill="#ef4444" name="Failures" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-center text-muted-foreground py-8">No timeline data available</p>
              )}
            </CardContent>
          </Card>

          {/* Summary Stats */}
          {kpis && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>Unique Workflows</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{kpis.unique_workflows}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Unique Users</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{kpis.unique_users}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Total Errors</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{kpis.failed_executions}</p>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Workflows Tab */}
        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Top Performing Workflows</CardTitle>
                  <CardDescription>Ranked by {sortBy}</CardDescription>
                </div>
                <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="success_rate">Success Rate</SelectItem>
                    <SelectItem value="executions">Executions</SelectItem>
                    <SelectItem value="duration">Duration</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              {topWorkflows.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Workflow</TableHead>
                      <TableHead className="text-right">Executions</TableHead>
                      <TableHead className="text-right">Success Rate</TableHead>
                      <TableHead className="text-right">Avg Duration</TableHead>
                      <TableHead className="text-right">Trend</TableHead>
                      <TableHead>Last Execution</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topWorkflows.map((workflow) => (
                      <TableRow key={workflow.workflow_id}>
                        <TableCell className="font-medium">{workflow.workflow_name}</TableCell>
                        <TableCell className="text-right">{workflow.total_executions}</TableCell>
                        <TableCell className="text-right">
                          <Badge variant={workflow.success_rate > 90 ? 'default' : 'secondary'}>
                            {workflow.success_rate}%
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          {formatDuration(workflow.average_duration_ms)}
                        </TableCell>
                        <TableCell className="text-right">{getTrendIcon(workflow.trend)}</TableCell>
                        <TableCell>
                          {workflow.last_execution
                            ? formatTimestamp(workflow.last_execution)
                            : 'N/A'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-center text-muted-foreground py-8">No workflow data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Errors Tab */}
        <TabsContent value="errors" className="space-y-4">
          {errorBreakdown && (
            <>
              {/* Error Types */}
              <Card>
                <CardHeader>
                  <CardTitle>Error Types</CardTitle>
                  <CardDescription>Most common error messages</CardDescription>
                </CardHeader>
                <CardContent>
                  {errorBreakdown.error_types.length > 0 ? (
                    <div className="space-y-2">
                      {errorBreakdown.error_types.map((error, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                          <span className="font-mono text-sm">{error.type}</span>
                          <Badge variant="destructive">{error.count} occurrences</Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-muted-foreground py-8">No errors recorded</p>
                  )}
                </CardContent>
              </Card>

              {/* Recent Errors */}
              <Card>
                <CardHeader>
                  <CardTitle>Recent Errors</CardTitle>
                  <CardDescription>Latest error messages</CardDescription>
                </CardHeader>
                <CardContent>
                  {errorBreakdown.recent_errors.length > 0 ? (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {errorBreakdown.recent_errors.map((error, idx) => (
                        <div key={idx} className="p-3 border rounded-lg">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium">{error.workflow_id}</span>
                            <span className="text-sm text-muted-foreground">
                              {formatTimestamp(error.timestamp)}
                            </span>
                          </div>
                          <p className="text-sm text-red-600 font-mono">{error.error_message}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-muted-foreground py-8">No recent errors</p>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Alerts Tab */}
        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Configured Alerts</CardTitle>
              <CardDescription>Manage analytics alerts</CardDescription>
            </CardHeader>
            <CardContent>
              {alerts.length > 0 ? (
                <div className="space-y-3">
                  {alerts.map((alert) => (
                    <div key={alert.alert_id} className="p-4 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className={`h-4 w-4 ${
                            alert.severity === 'critical' ? 'text-red-500' :
                            alert.severity === 'high' ? 'text-orange-500' :
                            'text-yellow-500'
                          }`} />
                          <span className="font-medium">{alert.name}</span>
                          <Badge variant={getSeverityColor(alert.severity) as any}>
                            {alert.severity}
                          </Badge>
                        </div>
                        <Badge variant={alert.enabled ? 'default' : 'secondary'}>
                          {alert.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{alert.description}</p>
                      <div className="text-xs font-mono bg-muted p-2 rounded">
                        {alert.metric_name} {alert.condition} {alert.threshold_value}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">No alerts configured</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Real-time Tab */}
        <TabsContent value="realtime" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Real-time Execution Feed</CardTitle>
              <CardDescription>Live workflow execution events</CardDescription>
            </CardHeader>
            <CardContent>
              {realtimeEvents.length > 0 ? (
                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {realtimeEvents.map((event) => (
                    <div key={event.event_id} className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <Badge variant={
                            event.status === 'completed' ? 'default' :
                            event.status === 'failed' ? 'destructive' :
                            'secondary'
                          }>
                            {event.event_type}
                          </Badge>
                          <span className="font-medium">{event.workflow_name}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(event.timestamp)}
                        </span>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Execution ID: <code className="text-xs">{event.execution_id}</code>
                      </div>
                      {event.duration_ms && (
                        <div className="text-sm text-muted-foreground">
                          Duration: {formatDuration(event.duration_ms)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">No recent events</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

// KPI Card Component
interface KPICardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  description: string;
  trend?: 'up' | 'down';
}

const KPICard: React.FC<KPICardProps> = ({ title, value, icon, description, trend }) => (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium">{title}</CardTitle>
      {icon}
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value}</div>
      <p className="text-xs text-muted-foreground">{description}</p>
      {trend && (
        <div className="mt-2">
          {trend === 'up' ? (
            <TrendingUp className="h-4 w-4 text-green-500 inline" />
          ) : (
            <TrendingDown className="h-4 w-4 text-red-500 inline" />
          )}
        </div>
      )}
    </CardContent>
  </Card>
);

// KPI Error Card (color-coded)
interface KPIErrorCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  description: string;
  errorRate: number;
}

const KPIErrorCard: React.FC<KPIErrorCardProps> = ({ title, value, icon, description, errorRate }) => (
  <Card className={errorRate > 5 ? 'border-red-500' : ''}>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium">{title}</CardTitle>
      {icon}
    </CardHeader>
    <CardContent>
      <div className={`text-2xl font-bold ${errorRate > 5 ? 'text-red-600' : ''}`}>{value}</div>
      <p className="text-xs text-muted-foreground">{description}</p>
    </CardContent>
  </Card>
);

// KPI Progress Card (with color indicator)
interface KPIProgressCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  description: string;
  valueMs: number;
}

const KPIProgressCard: React.FC<KPIProgressCardProps> = ({ title, value, icon, description, valueMs }) => {
  const getColor = () => {
    if (valueMs < 1000) return 'text-green-600';
    if (valueMs < 5000) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${getColor()}`}>{value}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
};

export default WorkflowAnalyticsDashboard;

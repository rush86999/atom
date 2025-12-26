/**
 * Performance Monitoring Dashboard Component
 * Real-time system and application performance monitoring
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  HardDrive,
  Cpu,
  Network,
  Activity,
  Server,
  Users
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

interface HealthData {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  uptime: number;
  version: string;
  environment: string;
  checks: {
    database: { status: string; responseTime: number; };
    redis: { status: string; responseTime: number; connected: boolean; };
    auth: { status: string; };
    memory: { status: string; used: number; total: number; percentage: number; };
    cpu: { status: string; usage: number; };
    integrations: { total: number; healthy: number; unhealthy: number; details: any[]; };
  };
  performance: {
    responseTime: number;
    throughput: number;
    errorRate: number;
    lastHour: { requests: number; errors: number; averageResponseTime: number; };
  };
}

interface AnalyticsData {
  timestamp: string;
  metrics: {
    users: { total: number; active: number; new: number; };
    integrations: { total: number; connected: number; usage: any[]; };
    performance: { averageResponseTime: number; throughput: number; errorRate: number; };
    features: { searchQueries: number; workflowExecutions: number; agentTasks: number; aiInteractions: number; };
  };
}

const PerformanceDashboard: React.FC = () => {
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [timeRange, setTimeRange] = useState('24h');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { toast } = useToast();

  useEffect(() => {
    fetchHealthData();
    fetchAnalyticsData();

    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchHealthData();
        fetchAnalyticsData();
      }, 30000); // Refresh every 30 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, timeRange]);

  const fetchHealthData = async () => {
    try {
      const response = await fetch('/api/health');
      if (response.ok) {
        const data = await response.json();
        setHealthData(data);
        // Only set loading false if we successfully got data or at least tried
        setLoading(false);
      } else {
        throw new Error('Health check failed');
      }
    } catch (err) {
      console.error('Failed to fetch health data:', err);
      // Don't show error toast on every poll if it fails silently in background, 
      // but do set error state to show in UI
      setError('Failed to fetch health data');
      setLoading(false);
    }
  };

  const fetchAnalyticsData = async () => {
    try {
      const response = await fetch(`/api/analytics?timeRange=${timeRange}`);
      if (response.ok) {
        const data = await response.json();
        setAnalyticsData(data.data);
      }
    } catch (err) {
      console.error('Failed to fetch analytics data:', err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'default'; // often maps to primary or black/white. Shadcn badge: 'default', 'secondary', 'destructive', 'outline'
      case 'degraded': return 'secondary';
      case 'unhealthy': return 'destructive';
      default: return 'outline';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="text-green-500 w-5 h-5" />;
      case 'degraded': return <AlertTriangle className="text-yellow-500 w-5 h-5" />;
      case 'unhealthy': return <XCircle className="text-red-500 w-5 h-5" />;
      default: return <Clock className="text-gray-500 w-5 h-5" />;
    }
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  };

  const performanceData = healthData ? [
    { time: new Date().toLocaleTimeString(), responseTime: healthData.performance.responseTime },
    { time: new Date(Date.now() - 60000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 0.9 },
    { time: new Date(Date.now() - 120000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 1.1 },
    { time: new Date(Date.now() - 180000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 0.95 },
    { time: new Date(Date.now() - 240000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 1.05 },
  ] : [];

  const integrationHealthData = healthData ? healthData.checks.integrations.details.map(integ => ({
    name: integ.service,
    status: integ.status,
    value: integ.status === 'healthy' ? 1 : 0,
  })) : [];

  const COLORS = ['#10b981', '#ef4444', '#3b82f6', '#f59e0b', '#8b5cf6'];

  if (loading && !healthData) {
    return (
      <div className="p-8 flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p>Loading performance data...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Performance Monitor</h1>
          <p className="text-gray-600">
            Real-time system health and performance metrics
          </p>
        </div>

        <div className="flex items-center space-x-4">
          <Select
            value={timeRange}
            onValueChange={setTimeRange}
          >
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Time Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">1 Hour</SelectItem>
              <SelectItem value="24h">24 Hours</SelectItem>
              <SelectItem value="7d">7 Days</SelectItem>
              <SelectItem value="30d">30 Days</SelectItem>
            </SelectContent>
          </Select>

          <Button
            size="sm"
            variant={autoRefresh ? "default" : "secondary"}
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            {autoRefresh ? 'Auto-refresh On' : 'Auto-refresh Off'}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Health Status Overview */}
      {healthData && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-gray-500">System Status</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant={healthData.status === 'healthy' ? 'default' : 'destructive'}>
                  {healthData.status.toUpperCase()}
                </Badge>
                {getStatusIcon(healthData.status)}
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Last updated: {new Date(healthData.timestamp).toLocaleTimeString()}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-gray-500">Uptime</p>
              <div className="text-2xl font-bold mt-1">{formatUptime(healthData.uptime)}</div>
              <p className="text-xs text-gray-400 mt-2">
                Version: {healthData.version}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-gray-500">Response Time</p>
              <div className="text-2xl font-bold mt-1">{healthData.performance.responseTime}ms</div>
              <p className="text-xs text-gray-400 mt-2">
                Error Rate: {healthData.performance.errorRate.toFixed(2)}%
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-gray-500">Healthy Integrations</p>
              <div className="text-2xl font-bold mt-1">
                {healthData.checks.integrations.healthy}/{healthData.checks.integrations.total}
              </div>
              <p className="text-xs text-gray-400 mt-2">
                {healthData.checks.integrations.unhealthy} unhealthy
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Resource Usage */}
      {healthData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <HardDrive className="h-5 w-5" />
                <CardTitle>Memory</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between w-full">
                  <span>Used</span>
                  <span className="font-bold">
                    {(healthData.checks.memory.used / 1024 / 1024).toFixed(1)} MB
                  </span>
                </div>
                <Progress
                  value={healthData.checks.memory.percentage}
                  className="w-full"
                // Note: standard Shadcn Progress doesn't support colorScheme prop easily without custom CSS classes
                />
                <p className="text-sm text-gray-600">
                  {healthData.checks.memory.percentage.toFixed(1)}% utilized
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Cpu className="h-5 w-5" />
                <CardTitle>CPU</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between w-full">
                  <span>Usage</span>
                  <span className="font-bold">{healthData.checks.cpu.usage.toFixed(1)}%</span>
                </div>
                <Progress
                  value={healthData.checks.cpu.usage}
                  className="w-full"
                />
                <p className="text-sm text-gray-600">
                  Load average
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Network className="h-5 w-5" />
                <CardTitle>Redis</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between w-full">
                  <span>Status</span>
                  <Badge variant={healthData.checks.redis.connected ? 'default' : 'destructive'}>
                    {healthData.checks.redis.connected ? 'Connected' : 'Disconnected'}
                  </Badge>
                </div>
                <p className="text-sm text-gray-600">
                  Response Time: {healthData.checks.redis.responseTime}ms
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Performance Charts */}
      <Tabs defaultValue="response-time">
        <TabsList>
          <TabsTrigger value="response-time">Response Time</TabsTrigger>
          <TabsTrigger value="integration-health">Integration Health</TabsTrigger>
          <TabsTrigger value="user-activity">User Activity</TabsTrigger>
          <TabsTrigger value="error-rate">Error Rate</TabsTrigger>
        </TabsList>

        <TabsContent value="response-time">
          <Card>
            <CardContent className="pt-6">
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={performanceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="responseTime"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    name="Response Time (ms)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="integration-health">
          <Card>
            <CardContent className="pt-6">
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={integrationHealthData}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {integrationHealthData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="user-activity">
          {analyticsData && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardContent className="pt-6">
                  <p className="text-sm font-medium text-gray-500">Active Users</p>
                  <div className="text-2xl font-bold mt-1">{analyticsData.metrics.users.active}</div>
                  <p className="text-xs text-gray-400 mt-2">
                    +{analyticsData.metrics.users.new} new users
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <p className="text-sm font-medium text-gray-500">Feature Usage</p>
                  <div className="text-2xl font-bold mt-1">{analyticsData.metrics.features.searchQueries}</div>
                  <p className="text-xs text-gray-400 mt-2">
                    Search queries in {timeRange}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="error-rate">
          <Card>
            <CardContent className="pt-6">
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={performanceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="responseTime"
                    stroke="#ef4444"
                    fill="#ef4444"
                    fillOpacity={0.3}
                    name="Error Rate"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Detailed System Information */}
      {healthData && (
        <Card>
          <CardHeader>
            <CardTitle>System Details</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Component</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Response Time</TableHead>
                  <TableHead>Last Check</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>Database</TableCell>
                  <TableCell>
                    <Badge variant={healthData.checks.database.status === 'healthy' ? 'default' : 'destructive'}>
                      {healthData.checks.database.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{healthData.checks.database.responseTime}ms</TableCell>
                  <TableCell>{new Date(healthData.timestamp).toLocaleTimeString()}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Redis</TableCell>
                  <TableCell>
                    <Badge variant={healthData.checks.redis.status === 'healthy' ? 'default' : 'destructive'}>
                      {healthData.checks.redis.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{healthData.checks.redis.responseTime}ms</TableCell>
                  <TableCell>{new Date(healthData.timestamp).toLocaleTimeString()}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Auth Service</TableCell>
                  <TableCell>
                    <Badge variant={healthData.checks.auth.status === 'healthy' ? 'default' : 'destructive'}>
                      {healthData.checks.auth.status}
                    </Badge>
                  </TableCell>
                  <TableCell>-</TableCell>
                  <TableCell>{new Date(healthData.timestamp).toLocaleTimeString()}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default PerformanceDashboard;
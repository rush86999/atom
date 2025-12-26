import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useToast } from '@/components/ui/use-toast';
import {
  CheckCircle,
  AlertTriangle,
  Clock,
  Settings,
  RefreshCw,
  X,
  Sun,
  ExternalLink,
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
} from 'lucide-react';
import { systemAPI, serviceRegistryAPI, byokAPI, workflowAPI } from '../lib/api';

interface SystemStatusData {
  timestamp: string;
  overall_status: string;
  system: any;
  resources: any;
  services: any;
  features: any;
  uptime: any;
  version: any;
}

interface ServiceStatus {
  name: string;
  status: string;
  status_code?: number;
  response_time_ms?: number;
  error?: string;
  last_checked: string;
}

const SystemStatusDashboard: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [services, setServices] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { toast } = useToast();

  const fetchSystemData = async () => {
    try {
      setRefreshing(true);

      // Fetch system status
      const statusResponse = await systemAPI.getSystemStatus();
      setSystemStatus((statusResponse.data as any));

      // Fetch services
      const servicesResponse = await serviceRegistryAPI.getServices();
      setServices((servicesResponse.data as any).services || []);

      // Fetch AI providers
      const providersResponse = await byokAPI.getProviders();
      setProviders((providersResponse.data as any).providers || []);

      // Fetch workflow templates
      const workflowsResponse = await workflowAPI.getTemplates();
      setWorkflows((workflowsResponse.data as any).templates || []);

    } catch (error) {
      console.error('Error fetching system data:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch system status',
        variant: 'error',
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchSystemData();

    // Refresh every 30 seconds
    const interval = setInterval(fetchSystemData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'operational':
        return 'bg-green-500 hover:bg-green-600';
      case 'degraded':
        return 'bg-yellow-500 hover:bg-yellow-600';
      case 'unhealthy':
      case 'unreachable':
        return 'bg-red-500 hover:bg-red-600';
      default:
        return 'bg-gray-500 hover:bg-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'operational':
        return <CheckCircle className="w-4 h-4" />;
      case 'degraded':
        return <AlertTriangle className="w-4 h-4" />;
      case 'unhealthy':
      case 'unreachable':
        return <X className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const formatBytes = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mb-4" />
        <p className="text-gray-600">Loading system status...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">System Status Dashboard</h1>
          <p className="text-sm text-gray-600">
            Last updated: {systemStatus ? new Date(systemStatus.timestamp).toLocaleString() : 'Unknown'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={getStatusColor(systemStatus?.overall_status)}>
            <span className="flex items-center gap-1">
              {getStatusIcon(systemStatus?.overall_status)}
              {systemStatus?.overall_status?.toUpperCase() || 'UNKNOWN'}
            </span>
          </Badge>
          <Button
            variant="outline"
            size="icon"
            onClick={fetchSystemData}
            disabled={refreshing}
            title="Refresh status"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* System Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-600">System Uptime</span>
              </div>
              <p className="text-3xl font-bold">
                {systemStatus ? formatUptime(systemStatus.uptime.system_seconds) : 'N/A'}
              </p>
              <p className="text-xs text-gray-500">
                Process: {systemStatus ? formatUptime(systemStatus.uptime.process_seconds) : 'N/A'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-600">CPU Usage</span>
              </div>
              <p className="text-3xl font-bold">
                {systemStatus?.resources?.cpu?.percent?.toFixed(1) || '0'}%
              </p>
              <Progress
                value={systemStatus?.resources?.cpu?.percent || 0}
                className="h-2"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <MemoryStick className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-600">Memory Usage</span>
              </div>
              <p className="text-3xl font-bold">
                {systemStatus?.resources?.memory?.system_used_percent?.toFixed(1) || '0'}%
              </p>
              <p className="text-xs text-gray-500">
                {systemStatus?.resources?.memory?.rss_mb || '0'} MB used
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-600">Disk Usage</span>
              </div>
              <p className="text-3xl font-bold">
                {systemStatus?.resources?.disk?.percent?.toFixed(1) || '0'}%
              </p>
              <p className="text-xs text-gray-500">
                {systemStatus?.resources?.disk?.free_gb || '0'} GB free
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Services Status */}
      <Card>
        <CardHeader>
          <h2 className="text-xl font-semibold">Services Status</h2>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {systemStatus?.services && Object.entries(systemStatus.services).map(([serviceId, service]: [string, any]) => (
              <Card key={serviceId} className="border">
                <CardContent className="pt-6">
                  <div className="flex justify-between items-start">
                    <div className="space-y-1 flex-1">
                      <p className="font-medium">{service.name}</p>
                      <Badge className={getStatusColor(service.status)}>
                        {service.status}
                      </Badge>
                      {service.response_time_ms && (
                        <p className="text-xs text-gray-500">
                          {service.response_time_ms}ms
                        </p>
                      )}
                    </div>
                    <div className="text-gray-500">
                      {getStatusIcon(service.status)}
                    </div>
                  </div>
                  {service.error && (
                    <p className="text-xs text-red-500 mt-2">
                      {service.error}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Features & Integrations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Services & Providers */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <h2 className="text-xl font-semibold">Services & AI Providers</h2>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Registered Services */}
            <div>
              <p className="font-medium mb-2">Registered Services ({services.length})</p>
              <div className="grid grid-cols-2 gap-2">
                {services.map((service) => (
                  <Badge key={service.id} variant="secondary" className="px-2 py-1">
                    {service.name}
                  </Badge>
                ))}
              </div>
            </div>

            {/* AI Providers */}
            <div>
              <p className="font-medium mb-2">AI Providers ({providers.length})</p>
              <div className="grid grid-cols-2 gap-2">
                {providers.map((provider) => (
                  <Badge key={provider.id} variant="secondary" className="bg-green-100 text-green-800 px-2 py-1">
                    {provider.name}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* System Info */}
        <Card>
          <CardHeader>
            <h2 className="text-xl font-semibold">System Information</h2>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-sm text-gray-600">Platform</p>
              <p className="text-sm font-medium">{systemStatus?.system?.platform?.system || 'Unknown'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Node</p>
              <p className="text-sm font-medium">{systemStatus?.system?.platform?.node || 'Unknown'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Python Version</p>
              <p className="text-sm font-medium">{systemStatus?.system?.python?.version?.split(' ')[0] || 'Unknown'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Process ID</p>
              <p className="text-sm font-medium">{systemStatus?.system?.process?.pid || 'Unknown'}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Feature Status */}
      <Card>
        <CardHeader>
          <h2 className="text-xl font-semibold">Feature Status</h2>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {systemStatus?.features && Object.entries(systemStatus.features).map(([featureId, feature]: [string, any]) => (
              <Card key={featureId} className="border">
                <CardContent className="pt-6 space-y-2">
                  <Badge className={getStatusColor(feature.status)}>
                    {feature.status}
                  </Badge>
                  <p className="font-medium">{feature.description}</p>
                  {feature.providers && (
                    <p className="text-sm text-gray-600">
                      {feature.providers} providers
                    </p>
                  )}
                  {feature.services_registered && (
                    <p className="text-sm text-gray-600">
                      {feature.services_registered} services
                    </p>
                  )}
                  {feature.templates_available && (
                    <p className="text-sm text-gray-600">
                      {feature.templates_available} templates
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Alerts */}
      {systemStatus?.overall_status !== 'healthy' && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>System Status: {systemStatus?.overall_status?.toUpperCase()}</AlertTitle>
          <AlertDescription>
            Some services may be experiencing issues. Check the services status above for details.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};

export default SystemStatusDashboard;

import React, { useState, useEffect, useCallback } from "react";
import {
  Server,
  Cpu,
  Database,
  GitBranch,
  Package,
  Shield,
  Monitor,
  RefreshCw,
  Play,
  StopCircle,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Terminal,
  Folder,
  Activity
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";

// Tauri imports for desktop functionality
const { invoke } =
  typeof window !== "undefined" ? require("@tauri-apps/api") : { invoke: null };

interface ServiceStatus {
  name: string;
  status: string;
  responseTime: number | null;
  lastCheck: Date;
  error?: string;
}

interface BuildStatus {
  lastBuild: Date;
  buildTime: string;
  status: string;
  tests: {
    total: number;
    passed: number;
    failed: number;
    coverage: string;
  };
}

const DevStatus = () => {
  const { toast } = useToast();
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [servicesStatus, setServicesStatus] = useState<Record<string, ServiceStatus>>({});
  const [buildStatus, setBuildStatus] = useState<BuildStatus>({
    lastBuild: new Date(),
    buildTime: "",
    status: "",
    tests: { total: 0, passed: 0, failed: 0, coverage: "0%" }
  });
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Load system status
  const loadSystemStatus = useCallback(async () => {
    setIsRefreshing(true);
    try {
      // Load system info if available
      if (invoke) {
        const systemInfo = await invoke("get_system_info");
        setSystemStatus(systemInfo);
      }

      // Simulate service status checks
      const services = {
        frontend: await checkService("Frontend", "http://localhost:3000"),
        backend: await checkService("Backend", "http://localhost:5059", false, "GET"),
        database: await checkService("Database", null, true), // Assume database is running
        desktop: await checkService("Desktop App", null, true), // Assume desktop is running
      };

      setServicesStatus(services);

      // Check build status
      const buildInfo = {
        lastBuild: new Date(Date.now() - 300000), // 5 minutes ago
        buildTime: "2m 15s",
        status: "success",
        tests: {
          total: 156,
          passed: 152,
          failed: 4,
          coverage: "87%",
        },
      };
      setBuildStatus(buildInfo);

      setLastUpdate(new Date());
    } catch (error) {
      console.error("Failed to load system status:", error);
      toast({
        title: "Error",
        description: "Failed to load system status",
        variant: "error",
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [toast]);

  // Simulate service health check
  const checkService = async (
    name: string,
    url: string | null,
    isRunning: boolean = false,
    method: string = "HEAD",
  ): Promise<ServiceStatus> => {
    if (url) {
      try {
        const response = await fetch(url, { method });
        return {
          name,
          status: response.ok ? "healthy" : "unhealthy",
          responseTime: Math.random() * 100 + 50, // ms
          lastCheck: new Date(),
        };
      } catch (error) {
        return {
          name,
          status: "unhealthy",
          responseTime: null,
          lastCheck: new Date(),
          error: (error as Error).message,
        };
      }
    } else {
      return {
        name,
        status: isRunning ? "healthy" : "unknown",
        responseTime: null,
        lastCheck: new Date(),
      };
    }
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case "healthy":
      case "success":
        return "bg-green-500";
      case "warning":
      case "degraded":
        return "bg-yellow-500";
      case "unhealthy":
      case "error":
      case "failed":
        return "bg-red-500";
      default:
        return "bg-gray-500";
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case "healthy":
      case "success":
        return CheckCircle;
      case "warning":
      case "degraded":
        return AlertTriangle;
      case "unhealthy":
      case "error":
      case "failed":
        return XCircle;
      default:
        return Info;
    }
  };

  useEffect(() => {
    loadSystemStatus();
    const interval = setInterval(loadSystemStatus, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [loadSystemStatus]);

  const serviceList = Object.values(servicesStatus);

  return (
    <div className="min-h-screen bg-gray-50 p-6 dark:bg-gray-900">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header */}
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-100">Development Status</h1>
            <p className="text-gray-500 dark:text-gray-400">
              Real-time monitoring of development environment and services
            </p>
          </div>
          <Button
            onClick={loadSystemStatus}
            disabled={isRefreshing}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {/* System Overview */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between space-y-0 pb-2">
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Platform</p>
                <Monitor className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {systemStatus?.platform ? systemStatus.platform.toUpperCase() : "Web"}
              </div>
              <div className="flex items-center pt-1 text-xs text-gray-500">
                <Activity className="mr-1 h-3 w-3 text-green-500" />
                {systemStatus?.architecture || "Unknown"}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between space-y-0 pb-2">
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Services</p>
                <Server className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {serviceList.filter((s) => s.status === "healthy").length}/{serviceList.length}
              </div>
              <p className="text-xs text-gray-500 pt-1">Healthy Services</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between space-y-0 pb-2">
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Test Coverage</p>
                <Shield className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {buildStatus.tests?.coverage || "0%"}
              </div>
              <p className="text-xs text-gray-500 pt-1">
                {buildStatus.tests?.passed}/{buildStatus.tests?.total} tests passed
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between space-y-0 pb-2">
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Last Update</p>
                <RefreshCw className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {mounted ? lastUpdate.toLocaleTimeString() : "--:--:--"}
              </div>
              <p className="text-xs text-gray-500 pt-1">{mounted ? lastUpdate.toLocaleDateString() : "--/--/----"}</p>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="services" className="w-full">
          <TabsList className="grid w-full grid-cols-3 lg:w-[400px]">
            <TabsTrigger value="services" className="flex items-center gap-2">
              <Server className="h-4 w-4" />
              Services
            </TabsTrigger>
            <TabsTrigger value="build" className="flex items-center gap-2">
              <Package className="h-4 w-4" />
              Build Status
            </TabsTrigger>
            <TabsTrigger value="system" className="flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              System Info
            </TabsTrigger>
          </TabsList>

          {/* Services Panel */}
          <TabsContent value="services" className="space-y-6 mt-6">
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {serviceList.map((service, index) => {
                const StatusIcon = getStatusIcon(service.status);
                const statusColor = getStatusColor(service.status);

                return (
                  <Card key={index} className="border-l-4" style={{ borderLeftColor: statusColor.replace('bg-', 'var(--') }}>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{service.name}</h3>
                        <StatusIcon className={`h-5 w-5 ${statusColor.replace('bg-', 'text-')}`} />
                      </div>
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-500 dark:text-gray-400">Status:</span>
                          <Badge className={`${statusColor} text-white hover:${statusColor}`}>
                            {service.status}
                          </Badge>
                        </div>
                        {service.responseTime && (
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-gray-500 dark:text-gray-400">Response Time:</span>
                            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                              {service.responseTime.toFixed(0)}ms
                            </span>
                          </div>
                        )}
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-500 dark:text-gray-400">Last Check:</span>
                          <span className="text-sm text-gray-900 dark:text-gray-100">
                            {mounted ? service.lastCheck.toLocaleTimeString() : "--:--:--"}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {/* Service Health Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Service Health Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="relative w-full overflow-auto">
                  <table className="w-full caption-bottom text-sm">
                    <thead className="[&_tr]:border-b">
                      <tr className="border-b transition-colors hover:bg-gray-100/50 data-[state=selected]:bg-gray-100 dark:hover:bg-gray-800/50 dark:data-[state=selected]:bg-gray-800">
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Service</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Status</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Response Time</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Last Check</th>
                        <th className="h-12 px-4 text-left align-middle font-medium text-gray-500 dark:text-gray-400">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="[&_tr:last-child]:border-0">
                      {serviceList.map((service, index) => (
                        <tr key={index} className="border-b transition-colors hover:bg-gray-100/50 data-[state=selected]:bg-gray-100 dark:hover:bg-gray-800/50 dark:data-[state=selected]:bg-gray-800">
                          <td className="p-4 align-middle font-medium">{service.name}</td>
                          <td className="p-4 align-middle">
                            <Badge className={`${getStatusColor(service.status)} text-white hover:${getStatusColor(service.status)}`}>
                              {service.status}
                            </Badge>
                          </td>
                          <td className="p-4 align-middle">
                            {service.responseTime ? `${service.responseTime.toFixed(0)}ms` : "N/A"}
                          </td>
                          <td className="p-4 align-middle">{mounted ? service.lastCheck.toLocaleTimeString() : "--:--:--"}</td>
                          <td className="p-4 align-middle">
                            <Button variant="outline" size="sm">
                              Restart
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Build Status Panel */}
          <TabsContent value="build" className="space-y-6 mt-6">
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Last Build</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-gray-400">Status:</span>
                    <Badge className={`${getStatusColor(buildStatus.status)} text-white hover:${getStatusColor(buildStatus.status)}`}>
                      {buildStatus.status}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-gray-400">Time:</span>
                    <span className="font-medium text-gray-900 dark:text-gray-100">{buildStatus.buildTime}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-gray-400">Completed:</span>
                    <span className="text-sm text-gray-900 dark:text-gray-100">
                      {mounted ? (buildStatus.lastBuild ? buildStatus.lastBuild.toLocaleString() : "Never") : "..."}
                    </span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Test Results</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-gray-400">Total Tests:</span>
                    <span className="font-medium text-gray-900 dark:text-gray-100">{buildStatus.tests?.total}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-gray-400">Passed:</span>
                    <span className="font-medium text-green-600 dark:text-green-400">{buildStatus.tests?.passed}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-gray-400">Failed:</span>
                    <span className="font-medium text-red-600 dark:text-red-400">{buildStatus.tests?.failed}</span>
                  </div>
                  <Progress
                    value={(buildStatus.tests?.passed / buildStatus.tests?.total) * 100 || 0}
                    className="h-2"
                  />
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Build Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4">
                  <Button className="bg-green-600 hover:bg-green-700 text-white">
                    <Play className="mr-2 h-4 w-4" />
                    Start Build
                  </Button>
                  <Button variant="outline" className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 dark:border-red-900 dark:hover:bg-red-900/20">
                    <StopCircle className="mr-2 h-4 w-4" />
                    Stop Build
                  </Button>
                  <Button variant="outline" className="text-blue-600 border-blue-200 hover:bg-blue-50 hover:text-blue-700 dark:border-blue-900 dark:hover:bg-blue-900/20">
                    <Package className="mr-2 h-4 w-4" />
                    Package Release
                  </Button>
                  <Button variant="outline" className="text-purple-600 border-purple-200 hover:bg-purple-50 hover:text-purple-700 dark:border-purple-900 dark:hover:bg-purple-900/20">
                    <Terminal className="mr-2 h-4 w-4" />
                    Run Tests
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* System Info Panel */}
          <TabsContent value="system" className="space-y-6 mt-6">
            {systemStatus ? (
              <div className="grid gap-6 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Platform Information</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {Object.entries(systemStatus).map(([key, value]) => (
                      <div key={key} className="flex justify-between items-center">
                        <span className="font-medium capitalize text-gray-700 dark:text-gray-300">
                          {key.replace(/_/g, " ")}:
                        </span>
                        <span className="text-gray-900 dark:text-gray-100">{String(value)}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Capabilities</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {systemStatus.features &&
                      Object.entries(systemStatus.features).map(([feature, enabled]) => (
                        <div key={feature} className="flex justify-between items-center">
                          <span className="text-gray-700 dark:text-gray-300">
                            {feature.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                          </span>
                          <Badge className={enabled ? "bg-green-500 hover:bg-green-600" : "bg-red-500 hover:bg-red-600"}>
                            {enabled ? "Enabled" : "Disabled"}
                          </Badge>
                        </div>
                      ))}
                  </CardContent>
                </Card>
              </div>
            ) : (
              <Alert>
                <Info className="h-4 w-4" />
                <AlertTitle>Web Environment</AlertTitle>
                <AlertDescription>
                  System information is only available in the desktop application.
                </AlertDescription>
              </Alert>
            )}

            {/* Development Tools Quick Access */}
            <Card>
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <Button variant="outline" className="flex items-center gap-2">
                    <Terminal className="h-4 w-4" />
                    Dev Tools
                  </Button>
                  <Button variant="outline" className="flex items-center gap-2">
                    <Folder className="h-4 w-4" />
                    File Explorer
                  </Button>
                  <Button variant="outline" className="flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    Database
                  </Button>
                  <Button variant="outline" className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4" />
                    Git Status
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default DevStatus;

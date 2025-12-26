import React, { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { Spinner } from "@/components/ui/spinner";
import {
  Clock,
  MessageSquare,
  CheckCircle,
  Settings,
  Eye,
  RotateCcw,
  Plus,
  Mail,
  Slack,
  MessageCircle, // For Discord/Teams generic
  Briefcase
} from "lucide-react";
import WorkflowAutomation from "./WorkflowAutomation";

interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  description?: string;
  location?: string;
  attendees?: string[];
  status: "confirmed" | "tentative" | "cancelled";
}

interface Task {
  id: string;
  title: string;
  description?: string;
  dueDate: Date;
  priority: "high" | "medium" | "low";
  status: "todo" | "in-progress" | "completed";
  project?: string;
  tags?: string[];
}

interface Message {
  id: string;
  platform: "email" | "slack" | "teams" | "discord";
  from: string;
  subject: string;
  preview: string;
  timestamp: Date;
  unread: boolean;
  priority: "high" | "normal" | "low";
}

interface DashboardData {
  calendar: CalendarEvent[];
  tasks: Task[];
  messages: Message[];
  stats: {
    upcomingEvents: number;
    overdueTasks: number;
    unreadMessages: number;
    completedTasks: number;
  };
}

const Dashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { toast } = useToast();

  const fetchDashboardData = async () => {
    try {
      const response = await fetch("/api/dashboard-dev");
      if (!response.ok) {
        throw new Error("Failed to fetch dashboard data");
      }
      const result = await response.json();
      setData(result);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load dashboard data",
        variant: "error",
      });
      console.error("Error fetching dashboard data:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchDashboardData();
  };

  const handleCompleteTask = async (taskId: string) => {
    try {
      const response = await fetch(`/api/tasks/${taskId}/complete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status: "completed" }),
      });
      if (response.ok) {
        toast({
          title: "Task completed",
          variant: "success",
        });
        fetchDashboardData(); // Refresh data
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to complete task",
        variant: "error",
      });
    }
  };

  const handleMarkAsRead = async (messageId: string) => {
    try {
      const response = await fetch(`/api/messages/${messageId}/read`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ read: true }),
      });
      if (response.ok) {
        fetchDashboardData(); // Refresh data
      }
    } catch (error) {
      console.error("Error marking message as read:", error);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p>Loading your dashboard...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 flex flex-col items-center gap-4">
        <h2 className="text-2xl font-bold">Unable to load dashboard</h2>
        <p>Please try refreshing the page</p>
        <Button onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </div>
    );
  }

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleDateString();
  };

  const isToday = (date: Date) => {
    const today = new Date();
    return new Date(date).toDateString() === today.toDateString();
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "destructive";
      case "medium":
        return "secondary"; // orange equivalent? or 'warning' if available, defaulting to secondary
      case "low":
        return "outline";
      default:
        return "secondary";
    }
  };

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case "email":
        return <Mail className="w-5 h-5" />;
      case "slack":
        return <Slack className="w-5 h-5" />;
      case "teams":
        return <Briefcase className="w-5 h-5" />;
      case "discord":
        return <MessageCircle className="w-5 h-5" />;
      default:
        return <MessageSquare className="w-5 h-5" />;
    }
  };

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">Atom Agent Dashboard</h1>
          <p className="text-gray-500">
            Welcome back! Manage your workflows and connected services.
          </p>
        </div>
        <Button onClick={handleRefresh} disabled={refreshing} variant="default">
          <RotateCcw className="mr-2 h-4 w-4" />
          {refreshing ? "Refreshing" : "Refresh"}
        </Button>
      </div>

      {/* Main Dashboard Tabs */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="workflow">Workflow Automation</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Stats Overview */}
          <div className="grid grid-cols-5 gap-6">
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center">
                  <Clock className="w-8 h-8 text-blue-500 mb-2" />
                  <span className="text-2xl font-bold">{data.stats.upcomingEvents}</span>
                  <span className="text-gray-500">Upcoming Events</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center">
                  <Clock className="w-8 h-8 text-red-500 mb-2" />
                  <span className="text-2xl font-bold">{data.stats.overdueTasks}</span>
                  <span className="text-gray-500">Overdue Tasks</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center">
                  <MessageSquare className="w-8 h-8 text-green-500 mb-2" />
                  <span className="text-2xl font-bold">{data.stats.unreadMessages}</span>
                  <span className="text-gray-500">Unread Messages</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center">
                  <CheckCircle className="w-8 h-8 text-purple-500 mb-2" />
                  <span className="text-2xl font-bold">{data.stats.completedTasks}</span>
                  <span className="text-gray-500">Completed Today</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center">
                  <Settings className="w-8 h-8 text-orange-500 mb-2" />
                  <span className="text-2xl font-bold">8</span>
                  <span className="text-gray-500">Connected Services</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Calendar Events */}
            <div className="col-span-1">
              <Card className="h-full">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-lg font-bold">Today&apos;s Calendar</CardTitle>
                  <Badge variant="secondary">
                    {data.calendar.length} events
                  </Badge>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col space-y-4">
                    {data.calendar.slice(0, 5).map((event) => (
                      <div
                        key={event.id}
                        className="p-3 border rounded-md flex justify-between items-start"
                      >
                        <div className="space-y-1">
                          <p className="font-bold">{event.title}</p>
                          <p className="text-sm text-gray-500">
                            {formatTime(event.start)} - {formatTime(event.end)}
                          </p>
                          {event.location && (
                            <p className="text-sm text-gray-400">
                              {event.location}
                            </p>
                          )}
                        </div>
                        <Badge variant={event.status === "confirmed" ? "default" : "secondary"}>
                          {event.status}
                        </Badge>
                      </div>
                    ))}
                    {data.calendar.length === 0 && (
                      <p className="text-gray-500 text-center">
                        No events scheduled for today
                      </p>
                    )}
                  </div>
                </CardContent>
                <CardFooter>
                  <Button variant="outline" className="w-full">
                    <Clock className="mr-2 h-4 w-4" />
                    View Full Calendar
                  </Button>
                </CardFooter>
              </Card>
            </div>

            {/* Tasks */}
            <div className="col-span-1">
              <Card className="h-full">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-lg font-bold">Tasks</CardTitle>
                  <Badge variant="secondary">
                    {data.tasks.length} tasks
                  </Badge>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col space-y-3">
                    {data.tasks.slice(0, 6).map((task) => (
                      <div
                        key={task.id}
                        className={`p-3 border rounded-md ${task.status === "completed" ? "bg-green-50" : "bg-white"
                          }`}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              <span
                                className={`font-bold ${task.status === "completed" ? "line-through text-gray-500" : ""
                                  }`}
                              >
                                {task.title}
                              </span>
                              <Badge variant={task.priority === 'high' ? 'destructive' : 'outline'}>
                                {task.priority}
                              </Badge>
                            </div>
                            {task.description && (
                              <p className="text-sm text-gray-500 truncate">
                                {task.description}
                              </p>
                            )}
                            <p className="text-sm text-gray-400">
                              Due: {isToday(task.dueDate) ? "Today" : formatDate(task.dueDate)}
                            </p>
                          </div>
                          {task.status !== "completed" && (
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => handleCompleteTask(task.id)}
                            >
                              <CheckCircle className="h-4 w-4 text-green-500" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                    {data.tasks.length === 0 && (
                      <p className="text-gray-500 text-center">
                        No tasks assigned
                      </p>
                    )}
                  </div>
                </CardContent>
                <CardFooter>
                  <Button variant="outline" className="w-full">
                    <Plus className="mr-2 h-4 w-4" />
                    Add New Task
                  </Button>
                </CardFooter>
              </Card>
            </div>

            {/* Messages */}
            <div className="col-span-1">
              <Card className="h-full">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-lg font-bold">Messages</CardTitle>
                  <Badge variant="secondary">
                    {data.messages.length} messages
                  </Badge>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col space-y-3">
                    {data.messages.slice(0, 5).map((message) => (
                      <div
                        key={message.id}
                        className={`p-3 border rounded-md cursor-pointer ${message.unread ? "bg-blue-50 border-blue-200" : "bg-white"
                          }`}
                        onClick={() => handleMarkAsRead(message.id)}
                      >
                        <div className="flex gap-3 items-start">
                          <div className="pt-1">
                            {getPlatformIcon(message.platform)}
                          </div>
                          <div className="flex-1 space-y-1">
                            <div className="flex justify-between w-full">
                              <span className="font-bold truncate">{message.from}</span>
                              <span className="text-xs text-gray-500">
                                {formatTime(message.timestamp)}
                              </span>
                            </div>
                            <p className="font-medium truncate">{message.subject}</p>
                            <p className="text-sm text-gray-500 line-clamp-2">
                              {message.preview}
                            </p>
                          </div>
                          {message.unread && (
                            <Badge variant="default" className="bg-blue-500">New</Badge>
                          )}
                        </div>
                      </div>
                    ))}
                    {data.messages.length === 0 && (
                      <p className="text-gray-500 text-center">
                        No messages
                      </p>
                    )}
                  </div>
                </CardContent>
                <CardFooter>
                  <Button variant="outline" className="w-full">
                    <Eye className="mr-2 h-4 w-4" />
                    View All Messages
                  </Button>
                </CardFooter>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Workflow Automation Tab */}
        <TabsContent value="workflow">
          <WorkflowAutomation />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Dashboard;

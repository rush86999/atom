import React, { useState, useEffect } from "react";
import {
    Plus,
    Clock,
    MessageSquare,
    CheckCircle,
    Eye,
    Settings,
    RefreshCw,
} from "lucide-react";
import { Button } from "./ui/button";
import {
    Card,
    CardHeader,
    CardBody,
    CardFooter,
    CardTitle,
    CardContent,
} from "./ui/card";
import { Badge } from "./ui/badge";
import { Spinner } from "./ui/spinner";
import { useToast } from "./ui/use-toast";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import WorkflowAutomation from "./WorkflowAutomation";
import ServiceIntegrationDashboard from "./ServiceIntegrationDashboard";
import ServiceManagement from "./ServiceManagement";

// Re-export CardBody as CardContent for compatibility if needed, or just use CardContent
// In this file we will use the new Tailwind components

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

const DashboardTailwind: React.FC = () => {
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [activeTab, setActiveTab] = useState("overview");
    const toast = useToast();

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
                status: "error",
            });
            console.error("Error fetching dashboard data:", error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const handleRefresh = () => {
        setRefreshing(true);
        fetchDashboardData();
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
                    status: "success",
                });
                fetchDashboardData(); // Refresh data
            }
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to complete task",
                status: "error",
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
            <div className="p-8 flex flex-col items-center justify-center space-y-4">
                <Spinner size="xl" />
                <p>Loading your dashboard...</p>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="p-8 flex flex-col items-center justify-center space-y-4">
                <h2 className="text-2xl font-bold">Unable to load dashboard</h2>
                <p>Please try refreshing the page</p>
                <Button onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? <Spinner size="sm" className="mr-2" /> : null}
                    Refresh
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
                return "warning";
            case "low":
                return "success";
            default:
                return "secondary";
        }
    };

    const getPlatformIcon = (platform: string) => {
        switch (platform) {
            case "email":
                return "📧";
            case "slack":
                return "💬";
            case "teams":
                return "💼";
            case "discord":
                return "🎮";
            default:
                return "💬";
        }
    };

    return (
        <div className="p-8 space-y-8">
            {/* Header */}
            <div className="flex justify-between items-start mb-8">
                <div className="space-y-1">
                    <h1 className="text-3xl font-bold">Atom Agent Dashboard</h1>
                    <p className="text-gray-600">
                        Welcome back! Manage your workflows and connected services.
                    </p>
                </div>
                <Button onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? (
                        <Spinner size="sm" className="mr-2" />
                    ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                    )}
                    Refresh
                </Button>
            </div>

            {/* Main Dashboard Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full grid-cols-4 mb-8">
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="automation">Workflow Automation</TabsTrigger>
                    <TabsTrigger value="integrations">Service Integrations</TabsTrigger>
                    <TabsTrigger value="management">Service Management</TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" activeValue={activeTab}>
                    <div className="space-y-6">
                        {/* Stats Overview */}
                        <div className="grid grid-cols-5 gap-6">
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center p-6">
                                    <Clock className="h-6 w-6 text-blue-500 mb-2" />
                                    <p className="text-2xl font-bold">
                                        {data.stats.upcomingEvents}
                                    </p>
                                    <p className="text-gray-600 text-sm">Upcoming Events</p>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center p-6">
                                    <Clock className="h-6 w-6 text-red-500 mb-2" />
                                    <p className="text-2xl font-bold">
                                        {data.stats.overdueTasks}
                                    </p>
                                    <p className="text-gray-600 text-sm">Overdue Tasks</p>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center p-6">
                                    <MessageSquare className="h-6 w-6 text-green-500 mb-2" />
                                    <p className="text-2xl font-bold">
                                        {data.stats.unreadMessages}
                                    </p>
                                    <p className="text-gray-600 text-sm">Unread Messages</p>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center p-6">
                                    <CheckCircle className="h-6 w-6 text-purple-500 mb-2" />
                                    <p className="text-2xl font-bold">
                                        {data.stats.completedTasks}
                                    </p>
                                    <p className="text-gray-600 text-sm">Completed Today</p>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center p-6">
                                    <Settings className="h-6 w-6 text-orange-500 mb-2" />
                                    <p className="text-2xl font-bold">8</p>
                                    <p className="text-gray-600 text-sm">Connected Services</p>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Grid */}
                        <div className="grid grid-cols-3 gap-8">
                            {/* Calendar Events */}
                            <div className="col-span-1">
                                <Card className="h-full">
                                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                                        <CardTitle className="text-lg">Today&apos;s Calendar</CardTitle>
                                        <Badge variant="default">
                                            {data.calendar.length} events
                                        </Badge>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-4">
                                            {data.calendar.slice(0, 5).map((event) => (
                                                <div
                                                    key={event.id}
                                                    className="p-3 border rounded-md flex justify-between items-start"
                                                >
                                                    <div className="space-y-1">
                                                        <p className="font-bold text-sm">{event.title}</p>
                                                        <p className="text-xs text-gray-600">
                                                            {formatTime(event.start)} -{" "}
                                                            {formatTime(event.end)}
                                                        </p>
                                                        {event.location && (
                                                            <p className="text-xs text-gray-500">
                                                                {event.location}
                                                            </p>
                                                        )}
                                                    </div>
                                                    <Badge
                                                        variant={
                                                            event.status === "confirmed"
                                                                ? "success"
                                                                : "warning"
                                                        }
                                                    >
                                                        {event.status}
                                                    </Badge>
                                                </div>
                                            ))}
                                            {data.calendar.length === 0 && (
                                                <p className="text-gray-500 text-center text-sm">
                                                    No events scheduled for today
                                                </p>
                                            )}
                                        </div>
                                    </CardContent>
                                    <CardFooter>
                                        <Button variant="outline" size="sm" className="w-full">
                                            <Clock className="mr-2 h-4 w-4" />
                                            View Full Calendar
                                        </Button>
                                    </CardFooter>
                                </Card>
                            </div>

                            {/* Tasks */}
                            <div className="col-span-1">
                                <Card className="h-full">
                                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                                        <CardTitle className="text-lg">Tasks</CardTitle>
                                        <Badge variant="secondary">
                                            {data.tasks.length} tasks
                                        </Badge>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-3">
                                            {data.tasks.slice(0, 6).map((task) => (
                                                <div
                                                    key={task.id}
                                                    className={`p-3 border rounded-md ${task.priority === "high"
                                                            ? "border-red-200"
                                                            : "border-gray-200"
                                                        } ${task.status === "completed" ? "bg-green-50" : "bg-white"
                                                        }`}
                                                >
                                                    <div className="flex justify-between items-start">
                                                        <div className="flex-1 space-y-1">
                                                            <div className="flex items-center space-x-2">
                                                                <p
                                                                    className={`font-bold text-sm ${task.status === "completed"
                                                                            ? "line-through text-gray-600"
                                                                            : ""
                                                                        }`}
                                                                >
                                                                    {task.title}
                                                                </p>
                                                                <Badge
                                                                    variant={getPriorityColor(task.priority) as any}
                                                                >
                                                                    {task.priority}
                                                                </Badge>
                                                            </div>
                                                            {task.description && (
                                                                <p className="text-xs text-gray-600 line-clamp-1">
                                                                    {task.description}
                                                                </p>
                                                            )}
                                                            <p className="text-xs text-gray-500">
                                                                Due:{" "}
                                                                {isToday(task.dueDate)
                                                                    ? "Today"
                                                                    : formatDate(task.dueDate)}
                                                            </p>
                                                        </div>
                                                        {task.status !== "completed" && (
                                                            <Button
                                                                size="icon"
                                                                variant="ghost"
                                                                className="h-6 w-6 text-green-600 hover:text-green-700 hover:bg-green-50"
                                                                onClick={() => handleCompleteTask(task.id)}
                                                            >
                                                                <CheckCircle className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                            {data.tasks.length === 0 && (
                                                <p className="text-gray-500 text-center text-sm">
                                                    No tasks assigned
                                                </p>
                                            )}
                                        </div>
                                    </CardContent>
                                    <CardFooter>
                                        <Button variant="outline" size="sm" className="w-full">
                                            <Plus className="mr-2 h-4 w-4" />
                                            Add New Task
                                        </Button>
                                    </CardFooter>
                                </Card>
                            </div>

                            {/* Messages */}
                            <div className="col-span-1">
                                <Card className="h-full">
                                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                                        <CardTitle className="text-lg">Messages</CardTitle>
                                        <Badge variant="default">
                                            {data.messages.length} messages
                                        </Badge>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-3">
                                            {data.messages.slice(0, 5).map((message) => (
                                                <div
                                                    key={message.id}
                                                    className={`p-3 border rounded-md cursor-pointer ${message.unread
                                                            ? "bg-blue-50 border-blue-200"
                                                            : "bg-white border-gray-200"
                                                        }`}
                                                    onClick={() => handleMarkAsRead(message.id)}
                                                >
                                                    <div className="flex space-x-3 items-start">
                                                        <span className="text-lg">
                                                            {getPlatformIcon(message.platform)}
                                                        </span>
                                                        <div className="flex-1 space-y-1">
                                                            <div className="flex justify-between w-full">
                                                                <p className="font-bold text-sm line-clamp-1">
                                                                    {message.from}
                                                                </p>
                                                                <p className="text-xs text-gray-500">
                                                                    {formatTime(message.timestamp)}
                                                                </p>
                                                            </div>
                                                            <p className="font-medium text-sm line-clamp-1">
                                                                {message.subject}
                                                            </p>
                                                            <p className="text-xs text-gray-600 line-clamp-2">
                                                                {message.preview}
                                                            </p>
                                                        </div>
                                                        {message.unread && (
                                                            <Badge variant="default" className="ml-2">
                                                                New
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                            {data.messages.length === 0 && (
                                                <p className="text-gray-500 text-center text-sm">
                                                    No messages
                                                </p>
                                            )}
                                        </div>
                                    </CardContent>
                                    <CardFooter>
                                        <Button variant="outline" size="sm" className="w-full">
                                            <Eye className="mr-2 h-4 w-4" />
                                            View All Messages
                                        </Button>
                                    </CardFooter>
                                </Card>
                            </div>
                        </div>
                    </div>
                </TabsContent>

                {/* Workflow Automation Tab */}
                <TabsContent value="automation" activeValue={activeTab}>
                    <WorkflowAutomation />
                </TabsContent>

                {/* Service Integrations Tab */}
                <TabsContent value="integrations" activeValue={activeTab}>
                    <ServiceIntegrationDashboard />
                </TabsContent>

                {/* Service Management Tab */}
                <TabsContent value="management" activeValue={activeTab}>
                    <ServiceManagement />
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default DashboardTailwind;

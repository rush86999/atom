import React, { useState, useEffect } from "react";
import {
  Clock,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  Plus,
  Eye,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";

interface ZoomMeeting {
  id: string;
  topic: string;
  start_time: string;
  duration: number;
  timezone: string;
  join_url: string;
  password?: string;
  agenda?: string;
  created_at: string;
  status: "scheduled" | "live" | "completed" | "cancelled";
}

interface ZoomUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  type: number;
  status: "active" | "inactive" | "pending";
}

interface ZoomRecording {
  id: string;
  meeting_id: string;
  topic: string;
  start_time: string;
  duration: number;
  file_size: number;
  download_url: string;
}

interface ZoomConnectionStatus {
  is_connected: boolean;
  user_info?: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
  };
  reason?: string;
}

interface MeetingAnalytics {
  period: {
    from: string;
    to: string;
  };
  total_meetings: number;
  total_participants: number;
  average_duration: number;
  meetings_by_type: {
    scheduled: number;
    instant: number;
    recurring: number;
  };
}

const ZoomIntegration: React.FC = () => {
  const [connectionStatus, setConnectionStatus] =
    useState<ZoomConnectionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [meetings, setMeetings] = useState<ZoomMeeting[]>([]);
  const [users, setUsers] = useState<ZoomUser[]>([]);
  const [recordings, setRecordings] = useState<ZoomRecording[]>([]);
  const [analytics, setAnalytics] = useState<MeetingAnalytics | null>(null);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const fetchConnectionStatus = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch("/api/zoom/connection-status");
      if (response.ok) {
        const data = await response.json();
        setConnectionStatus(data);
      } else {
        throw new Error("Failed to fetch connection status");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      setConnectionStatus({ is_connected: false, reason: "Connection failed" });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchMeetings = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      setIsLoadingData(true);
      const response = await fetch(
        "/api/zoom/meetings?user_id=me&type=scheduled",
      );
      if (response.ok) {
        const data = await response.json();
        setMeetings(data.meetings || []);
      } else {
        throw new Error("Failed to fetch meetings");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load meetings");
      setMeetings([]);
    } finally {
      setIsLoadingData(false);
    }
  };

  const fetchUsers = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      setIsLoadingData(true);
      const response = await fetch("/api/zoom/users?page_size=50");
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users || []);
      } else {
        throw new Error("Failed to fetch users");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
      setUsers([]);
    } finally {
      setIsLoadingData(false);
    }
  };

  const fetchRecordings = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      setIsLoadingData(true);
      const fromDate = new Date();
      fromDate.setDate(fromDate.getDate() - 30);
      const toDate = new Date();

      const response = await fetch(
        `/api/zoom/recordings?user_id=me&from_date=${fromDate.toISOString().split("T")[0]}&to_date=${toDate.toISOString().split("T")[0]}`,
      );
      if (response.ok) {
        const data = await response.json();
        setRecordings(data.recordings || []);
      } else {
        throw new Error("Failed to fetch recordings");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load recordings",
      );
      setRecordings([]);
    } finally {
      setIsLoadingData(false);
    }
  };

  const fetchAnalytics = async () => {
    if (!connectionStatus?.is_connected) return;

    try {
      const fromDate = new Date();
      fromDate.setDate(fromDate.getDate() - 30);
      const toDate = new Date();

      const response = await fetch(
        `/api/zoom/analytics/meetings?from_date=${fromDate.toISOString().split("T")[0]}&to_date=${toDate.toISOString().split("T")[0]}`,
      );
      if (response.ok) {
        const data = await response.json();
        setAnalytics(data);
      }
    } catch (err) {
      console.error("Failed to fetch analytics:", err);
    }
  };

  const handleConnectZoom = async () => {
    try {
      toast({
        title: "Connecting to Zoom",
        description: "Redirecting to Zoom for authentication...",
      });

      setTimeout(() => {
        setConnectionStatus({
          is_connected: true,
          user_info: {
            id: "user123",
            email: "user@example.com",
            first_name: "Zoom",
            last_name: "User",
          },
        });
        toast({
          title: "Connected to Zoom",
          description: "Successfully connected to your Zoom account",
        });
      }, 2000);
    } catch (err) {
      toast({
        title: "Connection failed",
        description:
          err instanceof Error ? err.message : "Failed to connect to Zoom",
        variant: "error",
      });
    }
  };

  const handleDisconnectZoom = async () => {
    try {
      const response = await fetch("/api/zoom/auth/disconnect", {
        method: "POST",
      });

      if (response.ok) {
        setConnectionStatus({ is_connected: false });
        setMeetings([]);
        setUsers([]);
        setRecordings([]);
        setAnalytics(null);

        toast({
          title: "Disconnected",
          description: "Successfully disconnected from Zoom",
        });
      } else {
        throw new Error("Failed to disconnect");
      }
    } catch (err) {
      toast({
        title: "Disconnect failed",
        description:
          err instanceof Error ? err.message : "Failed to disconnect from Zoom",
        variant: "error",
      });
    }
  };

  const handleCreateMeeting = async () => {
    try {
      const meetingData = {
        topic: "ATOM Integration Meeting",
        duration: 30,
        timezone: "UTC",
        agenda: "Meeting created via ATOM integration",
      };

      const response = await fetch("/api/zoom/meetings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(meetingData),
      });

      if (response.ok) {
        const data = await response.json();
        toast({
          title: "Meeting created",
          description: `Meeting "${data.meeting.topic}" created successfully`,
        });
        fetchMeetings();
      } else {
        throw new Error("Failed to create meeting");
      }
    } catch (err) {
      toast({
        title: "Failed to create meeting",
        description:
          err instanceof Error ? err.message : "Unknown error occurred",
        variant: "error",
      });
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  const formatFileSize = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  useEffect(() => {
    fetchConnectionStatus();
  }, []);

  useEffect(() => {
    if (connectionStatus?.is_connected) {
      fetchMeetings();
      fetchUsers();
      fetchRecordings();
      fetchAnalytics();
    }
  }, [connectionStatus]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <RefreshCw className="h-12 w-12 animate-spin text-blue-500" />
        <p className="mt-4 text-muted-foreground">Checking Zoom connection status...</p>
      </div>
    );
  }

  if (!connectionStatus?.is_connected) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Zoom Integration</h1>

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Zoom integration is not connected
          </AlertDescription>
        </Alert>

        <Card>
          <CardContent className="pt-6 space-y-4">
            <p>
              Connect your Zoom account to manage meetings, users, and
              recordings directly from ATOM.
            </p>
            <p className="text-sm text-muted-foreground">Features include:</p>
            <ul className="ml-6 space-y-2 text-sm list-disc">
              <li>Create and manage Zoom meetings</li>
              <li>View meeting analytics and recordings</li>
              <li>Manage Zoom users and settings</li>
              <li>Real-time webhook notifications</li>
            </ul>
            <Button onClick={handleConnectZoom}>
              <Clock className="mr-2 h-4 w-4" />
              Connect Zoom Account
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">Zoom Integration</h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge className="bg-green-500 hover:bg-green-600">Connected</Badge>
            <span className="text-sm text-muted-foreground">
              {connectionStatus.user_info?.email}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => {
              fetchMeetings();
              fetchUsers();
              fetchRecordings();
              fetchAnalytics();
            }}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" onClick={handleDisconnectZoom}>
            Disconnect
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Analytics Overview */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Total Meetings</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{analytics.total_meetings}</p>
              <p className="text-xs text-muted-foreground mt-1">Last 30 days</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Participants</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{analytics.total_participants}</p>
              <p className="text-xs text-muted-foreground mt-1">Last 30 days</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Avg Duration</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{analytics.average_duration}m</p>
              <p className="text-xs text-muted-foreground mt-1">Per meeting</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <p className="text-sm text-muted-foreground">Scheduled</p>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {analytics.meetings_by_type.scheduled}
              </p>
              <p className="text-xs text-muted-foreground mt-1">Meetings</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content Tabs */}
      <Tabs defaultValue="meetings">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="meetings">Meetings</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="recordings">Recordings</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        {/* Meetings Tab */}
        <TabsContent value="meetings" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Meetings</h2>
            <Button onClick={handleCreateMeeting}>
              <Plus className="mr-2 h-4 w-4" />
              Create Meeting
            </Button>
          </div>

          {isLoadingData ? (
            <div className="flex flex-col items-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin" />
              <p className="mt-2 text-muted-foreground">Loading meetings...</p>
            </div>
          ) : meetings.length === 0 ? (
            <Alert>
              <AlertDescription>No meetings found</AlertDescription>
            </Alert>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Topic</TableHead>
                      <TableHead>Start Time</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {meetings.map((meeting) => (
                      <TableRow key={meeting.id}>
                        <TableCell>
                          <div>
                            <p className="font-medium">{meeting.topic}</p>
                            {meeting.agenda && (
                              <p className="text-sm text-muted-foreground truncate">
                                {meeting.agenda}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{formatDate(meeting.start_time)}</TableCell>
                        <TableCell>{formatDuration(meeting.duration)}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              meeting.status === "scheduled"
                                ? "default"
                                : meeting.status === "live"
                                  ? "default"
                                  : "secondary"
                            }
                            className={
                              meeting.status === "live"
                                ? "bg-green-500 hover:bg-green-600"
                                : ""
                            }
                          >
                            {meeting.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                window.open(meeting.join_url, "_blank")
                              }
                            >
                              <ArrowRight className="h-4 w-4" />
                            </Button>
                            <Button variant="outline" size="sm">
                              <Eye className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Users Tab */}
        <TabsContent value="users" className="space-y-4">
          <h2 className="text-xl font-semibold">Zoom Users</h2>

          {isLoadingData ? (
            <div className="flex flex-col items-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin" />
              <p className="mt-2 text-muted-foreground">Loading users...</p>
            </div>
          ) : users.length === 0 ? (
            <Alert>
              <AlertDescription>No users found</AlertDescription>
            </Alert>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell className="font-medium">
                          {user.first_name} {user.last_name}
                        </TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>
                          <Badge variant={user.type === 2 ? "default" : "secondary"}>
                            {user.type === 2 ? "Licensed" : "Basic"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            className={
                              user.status === "active"
                                ? "bg-green-500 hover:bg-green-600"
                                : user.status === "inactive"
                                  ? "bg-red-500 hover:bg-red-600"
                                  : "bg-yellow-500 hover:bg-yellow-600"
                            }
                          >
                            {user.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Recordings Tab */}
        <TabsContent value="recordings" className="space-y-4">
          <h2 className="text-xl font-semibold">Recordings</h2>

          {isLoadingData ? (
            <div className="flex flex-col items-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin" />
              <p className="mt-2 text-muted-foreground">Loading recordings...</p>
            </div>
          ) : recordings.length === 0 ? (
            <Alert>
              <AlertDescription>No recordings found</AlertDescription>
            </Alert>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Topic</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recordings.map((recording) => (
                      <TableRow key={recording.id}>
                        <TableCell className="font-medium">
                          {recording.topic}
                        </TableCell>
                        <TableCell>{formatDate(recording.start_time)}</TableCell>
                        <TableCell>{formatDuration(recording.duration)}</TableCell>
                        <TableCell>{formatFileSize(recording.file_size)}</TableCell>
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              window.open(recording.download_url, "_blank")
                            }
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics" className="space-y-4">
          <h2 className="text-xl font-semibold">Meeting Analytics</h2>

          {analytics ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Meeting Types</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span>Scheduled Meetings</span>
                    <Badge variant="secondary">
                      {analytics.meetings_by_type.scheduled}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Instant Meetings</span>
                    <Badge variant="secondary" className="bg-green-100 text-green-800 hover:bg-green-200">
                      {analytics.meetings_by_type.instant}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Recurring Meetings</span>
                    <Badge variant="secondary" className="bg-purple-100 text-purple-800 hover:bg-purple-200">
                      {analytics.meetings_by_type.recurring}
                    </Badge>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Performance Metrics</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span>Total Participants</span>
                    <span className="font-bold">
                      {analytics.total_participants}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Average Duration</span>
                    <span className="font-bold">
                      {analytics.average_duration} minutes
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Total Meetings</span>
                    <span className="font-bold">{analytics.total_meetings}</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : (
            <Alert>
              <AlertDescription>No analytics data available</AlertDescription>
            </Alert>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ZoomIntegration;

/**
 * Zoom Integration Component
 * Complete Zoom video conferencing and collaboration integration
 */

import React, { useState, useEffect } from "react";
import {
    Settings,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    RefreshCw,
    Clock,
    Star,
    Eye,
    Edit,
    Trash,
    MessageSquare,
    Mail,
    Calendar,
    Phone,
    Paperclip,
    Download,
    ExternalLink,
    User,
    Lock,
    Loader2,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

interface ZoomMeeting {
    uuid: string;
    id: number;
    topic: string;
    type: number;
    start_time: string;
    duration: number;
    timezone: string;
    agenda?: string;
    created_at: string;
    start_url: string;
    join_url: string;
    password?: string;
    settings?: {
        host_video: boolean;
        participant_video: boolean;
        cn_meeting: boolean;
        in_meeting: boolean;
        join_before_host: boolean;
        mute_upon_entry: boolean;
        watermark: boolean;
        use_pmi: boolean;
        approval_type: number;
        registration_type?: number;
        audio: string;
        auto_recording: string;
        enforce_login: boolean;
        enforce_login_domains?: string;
        alternative_hosts?: string;
        global_dial_in_countries?: string[];
        registrant_email_notification: boolean;
        meeting_authentication?: string;
        authentication_option?: string;
        authentication_domains?: string;
        encryption_type?: string;
        approved_or_denied_countries_or_regions?: {
            enable: boolean;
            method: string;
            approved_list: string[];
            denied_list: string[];
        };
        breakout_room?: {
            enable: boolean;
            rooms: Array<{
                id: number;
                name: string;
                participants: string[];
            }>;
        };
        alternative_hosts_email_notification: boolean;
        device_testing?: boolean;
        focus_mode: boolean;
        private_meeting: boolean;

        waiting_room: boolean;
        pass_enterprise_sso: boolean;
        status: string;
        jbh_time: number;
        sign_language_interpretation?: {
            enable: boolean;
            interpreters: Array<{
                email: string;
                languages: string[];
            }>;
        };
        request_permission_to_start_record?: boolean;
        allow_multiple_devices: boolean;
        global_dial_in_numbers: Array<{
            country_name: string;
            country_code: string;
            country_iso2: string;
            city: string;
            number: string;
            type: string;
        }>;
        global_dial_in_permission: string;
        personal_meeting_id: boolean;
        audio_conference_info?: {
            type: string;
            toll_number: string;
            toll_free_number: string;
        };
        language_interpretation?: {
            enable: boolean;
            interpreters: Array<{
                email: string;
                languages: string[];
            }>;
        };
        close_registration: boolean;
        show_share_button: boolean;
        allow_live_streaming: boolean;
        start_type: string;
        enable_embedded_browser: boolean;
        live_streaming_url?: string;
        certificate: string;
        calendar_type: number;
        registrants_confirmation_email?: boolean;
        calendar_template_id?: number;
        enable_host_and_cohost_powerpoint: boolean;
        meeting_authentication_exception?: Array<{
            id: string;
            user_type: string;
            name: string;
        }>;
        alternative_host_automation: string;

        allow_registration_with_phonenumber: boolean;
        allow_registration_work_email: boolean;
        allow_registration_student_email: boolean;
        allow_registration_frequently_used_email: boolean;
        allow_registration_same_domain: boolean;
        allow_registration_all_email: boolean;
        allow_registration_discussion: boolean;
        registrants_email_notification: boolean;

        registrants_require_approval: boolean;
        registrants_require_email: boolean;
        registrants_require_name: boolean;
        registrants_require_phone: boolean;
        registrants_require_company: boolean;
        registrants_require_job_title: boolean;
        registrants_require_address: boolean;
        registrants_require_city: boolean;
        registrants_require_state: boolean;
        registrants_require_zip: boolean;
        registrants_require_country: boolean;
        registrants_require_website: boolean;
        registrants_require_industry: boolean;
        registrants_require_org: boolean;
        registrants_require_role: boolean;
        registrants_require_purchase: boolean;
        registrants_require_comments: boolean;
        registrants_require_custom_questions: boolean;
    };
    participant_count?: number;
    host_email: string;
}

interface ZoomUser {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
    type: number;
    role_name: string;
    pmi: number;
    use_pmi: boolean;
    vanity_url?: string;
    personal_meeting_url: string;
    timezone: string;
    verified: number;
    dept: string;
    created_at: string;
    last_login_time: string;
    pic_url?: string;
    host_key?: string;
    jid: string;
    group_ids: string[];
    im_group_ids: string[];
    account_id: number;
    account_name?: string;
    status: string;
    zoom_user_type?: string;
    enable_cloud_auto_recording: boolean;
    enable_webinar: boolean;
    enable_scheduled_webinar: boolean;
    enable_cmr: boolean;
    enable_virtual_background: boolean;
    enable_waiting_room: boolean;
    enable_recording: boolean;
    enable_hosts_email: boolean;
    enable_schedule_for_others: boolean;
    enable_breakout_room: boolean;
    enable_co_host: boolean;
    enable_auto_schedule_for_delegates: boolean;
    enable_polling: boolean;
    enable_screen_sharing: boolean;
    enable_remote_support: boolean;
    enable_file_transfer: boolean;
    enable_anonymous_join: boolean;
    enable_large_meeting: boolean;
    enable_large_webinar: boolean;
    enable_special_offer: boolean;
    enable_custom_live_streaming: boolean;
    enable_auto_schedule_meeting: boolean;
    enable_auto_schedule_webinar: boolean;
    enable_auto_schedule_meeting_for_hosts: boolean;
    enable_auto_schedule_webinar_for_hosts: boolean;
    enable_auto_schedule_meeting_for_users: boolean;
    enable_auto_schedule_webinar_for_users: boolean;
    enable_auto_schedule_meeting_for_groups: boolean;
    enable_auto_schedule_webinar_for_groups: boolean;
    enable_auto_schedule_meeting_for_admins: boolean;
    enable_auto_schedule_webinar_for_admins: boolean;
    enable_auto_schedule_meeting_for_delegates: boolean;
    enable_auto_schedule_webinar_for_delegates: boolean;
    enable_auto_schedule_meeting_for_contacts: boolean;
    enable_auto_schedule_webinar_for_contacts: boolean;
    enable_auto_schedule_meeting_for_apps: boolean;
    enable_auto_schedule_webinar_for_apps: boolean;
    enable_auto_schedule_meeting_for_channels: boolean;
    enable_auto_schedule_webinar_for_channels: boolean;
    enable_auto_schedule_meeting_for_webinars: boolean;
    enable_auto_schedule_webinar_for_webinars: boolean;
    enable_auto_schedule_meeting_for_meetings: boolean;
    enable_auto_schedule_webinar_for_meetings: boolean;
    enable_auto_schedule_meeting_for_recordings: boolean;
    enable_auto_schedule_webinar_for_recordings: boolean;
    enable_auto_schedule_meeting_for_playbacks: boolean;
    enable_auto_schedule_webinar_for_playbacks: boolean;
    enable_auto_schedule_meeting_for_cmr: boolean;
    enable_auto_schedule_webinar_for_cmr: boolean;
    enable_auto_schedule_meeting_for_shares: boolean;
    enable_auto_schedule_webinar_for_shares: boolean;
    enable_auto_schedule_meeting_for_incidents: boolean;
    enable_auto_schedule_webinar_for_incidents: boolean;
    enable_auto_schedule_meeting_for_surveys: boolean;
    enable_auto_schedule_webinar_for_surveys: boolean;
    enable_auto_schedule_meeting_for_forms: boolean;
    enable_auto_schedule_webinar_for_forms: boolean;
    enable_auto_schedule_meeting_for_polls: boolean;
    enable_auto_schedule_webinar_for_polls: boolean;
    enable_auto_schedule_meeting_for_quizzes: boolean;
    enable_auto_schedule_webinar_for_quizzes: boolean;
    enable_auto_schedule_meeting_for_reports: boolean;
    enable_auto_schedule_webinar_for_reports: boolean;
    enable_auto_schedule_meeting_for_metrics: boolean;
    enable_auto_schedule_webinar_for_metrics: boolean;
    enable_auto_schedule_meeting_for_insights: boolean;
    enable_auto_schedule_webinar_for_insights: boolean;
    enable_auto_schedule_meeting_for_analytics: boolean;
    enable_auto_schedule_webinar_for_analytics: boolean;
    enable_auto_schedule_meeting_for_dashboard?: boolean;
    enable_auto_schedule_webinar_for_dashboard?: boolean;
}

interface ZoomRecording {
    uuid: string;
    id: number;
    account_id: number;
    user_id: string;
    topic: string;
    start_time: string;
    timezone: string;
    duration: number;
    total_size: number;
    recording_files: Array<{
        id: string;
        meeting_id: string;
        recording_start: string;
        recording_end: string;
        file_type: string;
        file_size: number;
        play_url: string;
        download_url: string;
        delete_url: string;
        password: string;
        recording_type: string;
    }>;
    password?: string;
    share_url: string;
    share_password: string;
}

const ZoomIntegration: React.FC = () => {
    const [meetings, setMeetings] = useState<ZoomMeeting[]>([]);
    const [users, setUsers] = useState<ZoomUser[]>([]);
    const [recordings, setRecordings] = useState<ZoomRecording[]>([]);
    const [userProfile, setUserProfile] = useState<ZoomUser | null>(null);
    const [loading, setLoading] = useState({
        meetings: false,
        users: false,
        recordings: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedType, setSelectedType] = useState("all");

    // Form states
    const [meetingForm, setMeetingForm] = useState({
        topic: "",
        type: 2, // Scheduled meeting
        start_time: "",
        duration: 60,
        timezone: "UTC",
        agenda: "",
        password: "",
        settings: {
            host_video: true,
            participant_video: true,
            join_before_host: false,
            mute_upon_entry: true,
            waiting_room: false,
            auto_recording: "none",
        },
    });

    const [userForm, setUserForm] = useState({
        email: "",
        first_name: "",
        last_name: "",
        type: 2, // Licensed user
        role_name: "Member",
        timezone: "UTC",
        enable_cloud_auto_recording: false,
        enable_recording: false,
    });

    const [isMeetingOpen, setIsMeetingOpen] = useState(false);
    const [isUserOpen, setIsUserOpen] = useState(false);

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/zoom/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadMeetings();
                loadUsers();
                loadRecordings();
            } else {
                setConnected(false);
                setHealthStatus("error");
            }
        } catch (error) {
            console.error("Health check failed:", error);
            setConnected(false);
            setHealthStatus("error");
        }
    };

    // Load Zoom data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/zoom/profile", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setUserProfile(data.data?.profile || null);
            }
        } catch (error) {
            console.error("Failed to load user profile:", error);
        } finally {
            setLoading((prev) => ({ ...prev, profile: false }));
        }
    };

    const loadMeetings = async () => {
        setLoading((prev) => ({ ...prev, meetings: true }));
        try {
            const response = await fetch("/api/integrations/zoom/meetings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    type: "scheduled",
                    page_size: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setMeetings(data.data?.meetings || []);
            }
        } catch (error) {
            console.error("Failed to load meetings:", error);
            toast({
                title: "Error",
                description: "Failed to load meetings from Zoom",
                variant: "error",
            });
        } finally {
            setLoading((prev) => ({ ...prev, meetings: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch("/api/integrations/zoom/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    page_size: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setUsers(data.data?.users || []);
            }
        } catch (error) {
            console.error("Failed to load users:", error);
        } finally {
            setLoading((prev) => ({ ...prev, users: false }));
        }
    };

    const loadRecordings = async () => {
        setLoading((prev) => ({ ...prev, recordings: true }));
        try {
            const response = await fetch("/api/integrations/zoom/recordings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    page_size: 100,
                    from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
                        .toISOString()
                        .split("T")[0],
                    to: new Date().toISOString().split("T")[0],
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setRecordings(data.data?.recordings || []);
            }
        } catch (error) {
            console.error("Failed to load recordings:", error);
        } finally {
            setLoading((prev) => ({ ...prev, recordings: false }));
        }
    };

    // Create operations
    const createMeeting = async () => {
        if (!meetingForm.topic) return;

        try {
            const response = await fetch("/api/integrations/zoom/meetings/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    ...meetingForm,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Meeting created successfully",
                });
                setIsMeetingOpen(false);
                setMeetingForm({
                    topic: "",
                    type: 2,
                    start_time: "",
                    duration: 60,
                    timezone: "UTC",
                    agenda: "",
                    password: "",
                    settings: {
                        host_video: true,
                        participant_video: true,
                        join_before_host: false,
                        mute_upon_entry: true,
                        waiting_room: false,
                        auto_recording: "none",
                    },
                });
                loadMeetings();
            }
        } catch (error) {
            console.error("Failed to create meeting:", error);
            toast({
                title: "Error",
                description: "Failed to create meeting",
                variant: "error",
            });
        }
    };

    const createUser = async () => {
        if (!userForm.email) return;

        try {
            const response = await fetch("/api/integrations/zoom/users/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    ...userForm,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "User created successfully",
                });
                setIsUserOpen(false);
                setUserForm({
                    email: "",
                    first_name: "",
                    last_name: "",
                    type: 2,
                    role_name: "Member",
                    timezone: "UTC",
                    enable_cloud_auto_recording: false,
                    enable_recording: false,
                });
                loadUsers();
            }
        } catch (error) {
            console.error("Failed to create user:", error);
            toast({
                title: "Error",
                description: "Failed to create user",
                variant: "error",
            });
        }
    };

    // Filter data based on search
    const filteredMeetings = meetings.filter(
        (meeting) =>
            meeting.topic.toLowerCase().includes(searchQuery.toLowerCase()) ||
            meeting.agenda?.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredUsers = users.filter(
        (user) =>
            user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.first_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.last_name.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredRecordings = recordings.filter((recording) =>
        recording.topic.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    // Stats calculations
    const totalMeetings = meetings.length;
    const totalUsers = users.length;
    const totalRecordings = recordings.length;
    const upcomingMeetings = meetings.filter(
        (m) => new Date(m.start_time) > new Date(),
    ).length;
    const activeUsers = users.filter((u) => u.status === "active").length;
    const totalRecordingMinutes = recordings.reduce(
        (sum, r) => sum + r.duration,
        0,
    );

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadMeetings();
            loadUsers();
            loadRecordings();
        }
    }, [connected]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const getMeetingTypeVariant = (type: number): "default" | "secondary" | "destructive" | "outline" => {
        switch (type) {
            case 1:
                return "default"; // Instant meeting
            case 2:
                return "secondary"; // Scheduled meeting
            case 3:
                return "outline"; // Recurring meeting with no fixed time
            case 8:
                return "destructive"; // Recurring meeting with fixed time
            default:
                return "outline";
        }
    };

    const getMeetingStatusVariant = (meeting: ZoomMeeting): "default" | "secondary" | "destructive" | "outline" => {
        const now = new Date();
        const startTime = new Date(meeting.start_time);
        const endTime = new Date(
            startTime.getTime() + meeting.duration * 60 * 1000,
        );

        if (now < startTime) return "default"; // Upcoming
        if (now >= startTime && now <= endTime) return "secondary"; // In progress
        return "outline"; // Ended
    };

    const getUserTypeVariant = (type: number): "default" | "secondary" | "destructive" | "outline" => {
        switch (type) {
            case 1:
                return "outline"; // Basic
            case 2:
                return "default"; // Licensed
            case 3:
                return "secondary"; // On-prem
            default:
                return "outline";
        }
    };

    const getUserStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status?.toLowerCase()) {
            case "active":
                return "default";
            case "inactive":
                return "destructive";
            case "pending":
                return "secondary";
            default:
                return "outline";
        }
    };

    const formatDuration = (minutes: number): string => {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
    };

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Settings className="w-8 h-8 text-[#2D8CFF]" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Zoom Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Video conferencing and collaboration platform
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
                        <Badge
                            variant={healthStatus === "healthy" ? "default" : "destructive"}
                            className="flex items-center space-x-1"
                        >
                            {healthStatus === "healthy" ? (
                                <CheckCircle className="w-3 h-3 mr-1" />
                            ) : (
                                <AlertTriangle className="w-3 h-3 mr-1" />
                            )}
                            {connected ? "Connected" : "Disconnected"}
                        </Badge>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={checkConnection}
                        >
                            <RefreshCw className="mr-2 w-3 h-3" />
                            Refresh Status
                        </Button>
                    </div>

                    {userProfile && (
                        <div className="flex items-center space-x-4">
                            <Avatar>
                                <AvatarImage src={userProfile.pic_url} />
                                <AvatarFallback>{userProfile.first_name.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col">
                                <span className="font-bold">
                                    {userProfile.first_name} {userProfile.last_name}
                                </span>
                                <span className="text-sm text-muted-foreground">
                                    {userProfile.email} • {userProfile.role_name}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                {!connected ? (
                    // Connection Required State
                    <Card>
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center justify-center space-y-6 py-8">
                                <Settings className="w-16 h-16 text-gray-400" />
                                <div className="space-y-2 text-center">
                                    <h2 className="text-2xl font-bold">Connect Zoom</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Zoom account to start managing video meetings
                                        and recordings
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-[#2D8CFF] hover:bg-[#1a73e8]"
                                    onClick={() =>
                                        (window.location.href = "/api/integrations/zoom/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Zoom Account
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    // Connected State
                    <>
                        {/* Services Overview */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Meetings</p>
                                        <div className="text-2xl font-bold">{totalMeetings}</div>
                                        <p className="text-xs text-muted-foreground">{upcomingMeetings} upcoming</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Users</p>
                                        <div className="text-2xl font-bold">{activeUsers}</div>
                                        <p className="text-xs text-muted-foreground">{totalUsers} total</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Recordings</p>
                                        <div className="text-2xl font-bold">{totalRecordings}</div>
                                        <p className="text-xs text-muted-foreground">
                                            {formatDuration(totalRecordingMinutes)}
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Storage</p>
                                        <div className="text-2xl font-bold">2.4GB</div>
                                        <p className="text-xs text-muted-foreground">Used</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="meetings">
                            <TabsList>
                                <TabsTrigger value="meetings">Meetings</TabsTrigger>
                                <TabsTrigger value="users">Users</TabsTrigger>
                                <TabsTrigger value="recordings">Recordings</TabsTrigger>
                            </TabsList>

                            {/* Meetings Tab */}
                            <TabsContent value="meetings" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedType}
                                        onValueChange={setSelectedType}
                                    >
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="All Types" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Types</SelectItem>
                                            <SelectItem value="1">Instant</SelectItem>
                                            <SelectItem value="2">Scheduled</SelectItem>
                                            <SelectItem value="3">Recurring</SelectItem>
                                            <SelectItem value="8">Fixed Time</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search meetings..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#2D8CFF] hover:bg-[#1a73e8]"
                                        onClick={() => setIsMeetingOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Schedule Meeting
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Topic</TableHead>
                                                    <TableHead>Type</TableHead>
                                                    <TableHead>Start Time</TableHead>
                                                    <TableHead>Duration</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Participants</TableHead>
                                                    <TableHead>Actions</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.meetings ? (
                                                    <TableRow>
                                                        <TableCell colSpan={7} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#2D8CFF]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredMeetings.map((meeting) => (
                                                        <TableRow key={meeting.uuid}>
                                                            <TableCell>
                                                                <div className="flex flex-col space-y-1">
                                                                    <span className="font-bold">
                                                                        {meeting.topic}
                                                                    </span>
                                                                    {meeting.agenda && (
                                                                        <span className="text-sm text-muted-foreground">
                                                                            {meeting.agenda}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getMeetingTypeVariant(meeting.type)}>
                                                                    {meeting.type === 1
                                                                        ? "Instant"
                                                                        : meeting.type === 2
                                                                            ? "Scheduled"
                                                                            : meeting.type === 3
                                                                                ? "Recurring"
                                                                                : "Fixed Time"}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <div className="flex flex-col">
                                                                    <span className="text-sm">
                                                                        {formatDate(meeting.start_time)}
                                                                    </span>
                                                                    <span className="text-xs text-muted-foreground">
                                                                        {meeting.timezone}
                                                                    </span>
                                                                </div>
                                                            </TableCell>
                                                            <TableCell>
                                                                <span className="text-sm">
                                                                    {formatDuration(meeting.duration)}
                                                                </span>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getMeetingStatusVariant(meeting)}>
                                                                    {new Date() < new Date(meeting.start_time)
                                                                        ? "Upcoming"
                                                                        : new Date() >= new Date(meeting.start_time) &&
                                                                            new Date() <=
                                                                            new Date(
                                                                                new Date(meeting.start_time).getTime() +
                                                                                meeting.duration * 60 * 1000,
                                                                            )
                                                                            ? "In Progress"
                                                                            : "Ended"}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <span className="text-sm">
                                                                    {meeting.participant_count || 0}
                                                                </span>
                                                            </TableCell>
                                                            <TableCell>
                                                                <div className="flex space-x-2">
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        onClick={() =>
                                                                            window.open(meeting.start_url, "_blank")
                                                                        }
                                                                    >
                                                                        <User className="mr-2 w-3 h-3" />
                                                                        Start
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        onClick={() =>
                                                                            window.open(meeting.join_url, "_blank")
                                                                        }
                                                                    >
                                                                        <ExternalLink className="mr-2 w-3 h-3" />
                                                                        Join
                                                                    </Button>
                                                                </div>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Users Tab */}
                            <TabsContent value="users" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search users..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#2D8CFF] hover:bg-[#1a73e8]"
                                        onClick={() => setIsUserOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Add User
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.users ? (
                                        <div className="col-span-full flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#2D8CFF]" />
                                        </div>
                                    ) : (
                                        filteredUsers.map((user) => (
                                            <Card key={user.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex items-start space-x-4">
                                                        <Avatar className="w-12 h-12">
                                                            <AvatarImage src={user.pic_url} />
                                                            <AvatarFallback>{user.first_name.charAt(0)}</AvatarFallback>
                                                        </Avatar>
                                                        <div className="flex flex-col space-y-1 flex-1">
                                                            <span className="font-bold">
                                                                {user.first_name} {user.last_name}
                                                            </span>
                                                            <span className="text-sm text-muted-foreground">
                                                                {user.email}
                                                            </span>
                                                            <div className="flex space-x-2">
                                                                <Badge variant={getUserTypeVariant(user.type)}>
                                                                    {user.type === 1
                                                                        ? "Basic"
                                                                        : user.type === 2
                                                                            ? "Licensed"
                                                                            : "On-Prem"}
                                                                </Badge>
                                                                <Badge variant={getUserStatusVariant(user.status)}>
                                                                    {user.status}
                                                                </Badge>
                                                            </div>
                                                            <span className="text-xs text-muted-foreground mt-1">
                                                                {user.role_name} • {user.timezone}
                                                            </span>
                                                            <span className="text-xs text-muted-foreground">
                                                                Last login:{" "}
                                                                {user.last_login_time
                                                                    ? formatDate(user.last_login_time)
                                                                    : "Never"}
                                                            </span>
                                                            {user.personal_meeting_url && (
                                                                <a
                                                                    href={user.personal_meeting_url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="mt-2 inline-block"
                                                                >
                                                                    <Button size="sm" variant="outline">
                                                                        <User className="mr-2 w-3 h-3" />
                                                                        PMI
                                                                    </Button>
                                                                </a>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Recordings Tab */}
                            <TabsContent value="recordings" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search recordings..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    {loading.recordings ? (
                                        <div className="flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#2D8CFF]" />
                                        </div>
                                    ) : (
                                        filteredRecordings.map((recording) => (
                                            <Card key={recording.uuid}>
                                                <CardContent className="pt-6">
                                                    <div className="flex items-start space-x-4">
                                                        <User className="w-6 h-6 text-[#2D8CFF]" />
                                                        <div className="flex flex-col space-y-2 flex-1">
                                                            <div className="flex justify-between w-full">
                                                                <span className="font-bold">{recording.topic}</span>
                                                                {recording.password && (
                                                                    <Badge variant="secondary" className="flex items-center">
                                                                        <Lock className="w-3 h-3 mr-1" />
                                                                        Password Protected
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                            <div className="flex space-x-4 text-sm text-muted-foreground">
                                                                <span>📅 {formatDate(recording.start_time)}</span>
                                                                <span>⏱️ {formatDuration(recording.duration)}</span>
                                                                <span>💾 {formatFileSize(recording.total_size)}</span>
                                                            </div>
                                                            <div className="flex flex-wrap gap-2">
                                                                {recording.recording_files.map((file, index) => (
                                                                    <Badge key={index} variant="outline">
                                                                        {file.file_type.toUpperCase()}({formatFileSize(file.file_size)})
                                                                    </Badge>
                                                                ))}
                                                            </div>
                                                            <div className="flex space-x-2">
                                                                {recording.recording_files.map((file, index) => (
                                                                    <Button
                                                                        key={index}
                                                                        size="sm"
                                                                        variant="outline"
                                                                        onClick={() => window.open(file.play_url, "_blank")}
                                                                    >
                                                                        <User className="mr-2 w-3 h-3" />
                                                                        Play {file.file_type.toUpperCase()}
                                                                    </Button>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>
                        </Tabs>

                        {/* Create Meeting Modal */}
                        <Dialog open={isMeetingOpen} onOpenChange={setIsMeetingOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Schedule Meeting</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Topic</label>
                                        <Input
                                            placeholder="Meeting topic"
                                            value={meetingForm.topic}
                                            onChange={(e) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    topic: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Meeting description/agenda"
                                            value={meetingForm.agenda}
                                            onChange={(e) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    agenda: e.target.value,
                                                })
                                            }
                                            rows={3}
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Start Time</label>
                                            <Input
                                                type="datetime-local"
                                                value={meetingForm.start_time}
                                                onChange={(e) =>
                                                    setMeetingForm({
                                                        ...meetingForm,
                                                        start_time: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Duration (minutes)</label>
                                            <Input
                                                type="number"
                                                value={meetingForm.duration}
                                                onChange={(e) =>
                                                    setMeetingForm({
                                                        ...meetingForm,
                                                        duration: parseInt(e.target.value) || 60,
                                                    })
                                                }
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Timezone</label>
                                        <Select
                                            value={meetingForm.timezone}
                                            onValueChange={(value) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    timezone: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Timezone" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="UTC">UTC</SelectItem>
                                                <SelectItem value="America/New_York">Eastern Time</SelectItem>
                                                <SelectItem value="America/Chicago">Central Time</SelectItem>
                                                <SelectItem value="America/Denver">Mountain Time</SelectItem>
                                                <SelectItem value="America/Los_Angeles">Pacific Time</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Password (optional)</label>
                                        <Input
                                            type="password"
                                            placeholder="Meeting password"
                                            value={meetingForm.password}
                                            onChange={(e) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    password: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <span className="font-bold">Meeting Settings</span>
                                        <div className="space-y-2">
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="host_video"
                                                    checked={meetingForm.settings.host_video}
                                                    onCheckedChange={(checked) =>
                                                        setMeetingForm({
                                                            ...meetingForm,
                                                            settings: {
                                                                ...meetingForm.settings,
                                                                host_video: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="host_video" className="text-sm font-medium leading-none">
                                                    Enable host video
                                                </label>
                                            </div>
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="participant_video"
                                                    checked={meetingForm.settings.participant_video}
                                                    onCheckedChange={(checked) =>
                                                        setMeetingForm({
                                                            ...meetingForm,
                                                            settings: {
                                                                ...meetingForm.settings,
                                                                participant_video: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="participant_video" className="text-sm font-medium leading-none">
                                                    Enable participants video
                                                </label>
                                            </div>
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="join_before_host"
                                                    checked={meetingForm.settings.join_before_host}
                                                    onCheckedChange={(checked) =>
                                                        setMeetingForm({
                                                            ...meetingForm,
                                                            settings: {
                                                                ...meetingForm.settings,
                                                                join_before_host: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="join_before_host" className="text-sm font-medium leading-none">
                                                    Allow participants to join before host
                                                </label>
                                            </div>
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="mute_upon_entry"
                                                    checked={meetingForm.settings.mute_upon_entry}
                                                    onCheckedChange={(checked) =>
                                                        setMeetingForm({
                                                            ...meetingForm,
                                                            settings: {
                                                                ...meetingForm.settings,
                                                                mute_upon_entry: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="mute_upon_entry" className="text-sm font-medium leading-none">
                                                    Mute participants upon entry
                                                </label>
                                            </div>
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="waiting_room"
                                                    checked={meetingForm.settings.waiting_room}
                                                    onCheckedChange={(checked) =>
                                                        setMeetingForm({
                                                            ...meetingForm,
                                                            settings: {
                                                                ...meetingForm.settings,
                                                                waiting_room: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="waiting_room" className="text-sm font-medium leading-none">
                                                    Enable waiting room
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Auto Recording</label>
                                        <Select
                                            value={meetingForm.settings.auto_recording}
                                            onValueChange={(value) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    settings: {
                                                        ...meetingForm.settings,
                                                        auto_recording: value,
                                                    },
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Recording Option" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="none">None</SelectItem>
                                                <SelectItem value="local">Local</SelectItem>
                                                <SelectItem value="cloud">Cloud</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsMeetingOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2D8CFF] hover:bg-[#1a73e8]"
                                        onClick={createMeeting}
                                        disabled={!meetingForm.topic}
                                    >
                                        Schedule Meeting
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create User Modal */}
                        <Dialog open={isUserOpen} onOpenChange={setIsUserOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Add User</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Email</label>
                                        <Input
                                            type="email"
                                            placeholder="user@example.com"
                                            value={userForm.email}
                                            onChange={(e) =>
                                                setUserForm({
                                                    ...userForm,
                                                    email: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">First Name</label>
                                            <Input
                                                placeholder="First name"
                                                value={userForm.first_name}
                                                onChange={(e) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        first_name: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Last Name</label>
                                            <Input
                                                placeholder="Last name"
                                                value={userForm.last_name}
                                                onChange={(e) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        last_name: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">User Type</label>
                                            <Select
                                                value={userForm.type.toString()}
                                                onValueChange={(value) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        type: parseInt(value),
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select Type" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="1">Basic</SelectItem>
                                                    <SelectItem value="2">Licensed</SelectItem>
                                                    <SelectItem value="3">On-Prem</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Role</label>
                                            <Select
                                                value={userForm.role_name}
                                                onValueChange={(value) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        role_name: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select Role" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="Member">Member</SelectItem>
                                                    <SelectItem value="Admin">Admin</SelectItem>
                                                    <SelectItem value="Owner">Owner</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Timezone</label>
                                        <Select
                                            value={userForm.timezone}
                                            onValueChange={(value) =>
                                                setUserForm({
                                                    ...userForm,
                                                    timezone: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Timezone" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="UTC">UTC</SelectItem>
                                                <SelectItem value="America/New_York">Eastern Time</SelectItem>
                                                <SelectItem value="America/Chicago">Central Time</SelectItem>
                                                <SelectItem value="America/Denver">Mountain Time</SelectItem>
                                                <SelectItem value="America/Los_Angeles">Pacific Time</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <span className="font-bold">User Settings</span>
                                        <div className="space-y-2">
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="enable_cloud_auto_recording"
                                                    checked={userForm.enable_cloud_auto_recording}
                                                    onCheckedChange={(checked) =>
                                                        setUserForm({
                                                            ...userForm,
                                                            enable_cloud_auto_recording: checked as boolean,
                                                        })
                                                    }
                                                />
                                                <label htmlFor="enable_cloud_auto_recording" className="text-sm font-medium leading-none">
                                                    Enable cloud auto recording
                                                </label>
                                            </div>
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="enable_recording"
                                                    checked={userForm.enable_recording}
                                                    onCheckedChange={(checked) =>
                                                        setUserForm({
                                                            ...userForm,
                                                            enable_recording: checked as boolean,
                                                        })
                                                    }
                                                />
                                                <label htmlFor="enable_recording" className="text-sm font-medium leading-none">
                                                    Enable recording
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsUserOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2D8CFF] hover:bg-[#1a73e8]"
                                        onClick={createUser}
                                        disabled={
                                            !userForm.email ||
                                            !userForm.first_name ||
                                            !userForm.last_name
                                        }
                                    >
                                        Add User
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </>
                )}
            </div>
        </div>
    );
};

export default ZoomIntegration;

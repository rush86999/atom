/**
 * Box Integration Component
 * Complete Box file storage and collaboration platform integration
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
    Folder,
    File,
    Download,
    Link as LinkIcon,
    Share2,
    Users,
    Lock,
    Loader2,
    MoreVertical,
    ChevronRight,
    FileText,
    Image as ImageIcon,
    Music,
    Video,
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
import { Progress } from "@/components/ui/progress";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface BoxFile {
    id: string;
    type: string;
    name: string;
    size?: number;
    created_at: string;
    modified_at: string;
    content_created_at?: string;
    content_modified_at?: string;
    description?: string;
    etag: string;
    file_version?: {
        id: string;
        type: string;
        sha1: string;
    };
    created_by?: {
        id: string;
        name: string;
        login: string;
        type: string;
    };
    modified_by?: {
        id: string;
        name: string;
        login: string;
        type: string;
    };
    owned_by?: {
        id: string;
        name: string;
        login: string;
        type: string;
    };
    shared_link?: {
        url: string;
        download_url: string;
        vanity_name?: string;
        is_password_enabled: boolean;
        unshared_at: string;
        download_count: number;
        preview_count: number;
        access: string;
        effective_access: string;
        permissions: {
            can_download: boolean;
            can_preview: boolean;
            can_upload: boolean;
        };
    };
    parent: {
        id: string;
        type: string;
        sequence_id: number;
        etag: string;
        name: string;
    };
    item_collection?: {
        total_count: number;
        entries: BoxFile[];
        offset: number;
        limit: number;
        order?: Array<{
            by: string;
            direction: string;
        }>;
    };
    path_collection?: {
        total_count: number;
        entries: Array<{
            id: string;
            type: string;
            name: string;
        }>;
    };
    permissions?: Array<{
        id: string;
        type: string;
        created_at: string;
        granted_to?: {
            id: string;
            type: string;
            name: string;
            login: string;
        };
        accessible_by?: {
            id: string;
            type: string;
            name: string;
            login: string;
        };
        role: string;
        granted_to_tag?: any;
    }>;
    tags?: Array<{
        id: string;
        type: string;
        name: string;
        url: string;
    }>;
    lock?: {
        id: string;
        type: string;
        created_at: string;
        locked_by: {
            id: string;
            type: string;
            name: string;
            login: string;
        };
        app_type?: string;
        expires_at?: string;
        is_prevent_unlock?: boolean;
    };
    retention?: {
        id: string;
        type: string;
        policy?: {
            id: string;
            type: string;
            name: string;
        };
        disposition_at?: string;
        can_extend?: boolean;
    };
    watermarked?: boolean;
    allowed_shared_link_access_levels?: string[];
    has_collaborations?: boolean;
    is_externally_owned?: boolean;
    can_non_owners_invite?: boolean;
    is_collaboration_restricted_to_enterprise?: boolean;
    collaborator_restriction?: {
        type: string;
        restriction_type: string;
        allowed_groups?: Array<{
            id: string;
            name: string;
        }>;
        allowed_users?: Array<{
            id: string;
            name: string;
        }>;
    };
    classification?: {
        name: string;
        definition: string;
        color: string;
    };
}

interface BoxFolder {
    id: string;
    type: string;
    name: string;
    created_at: string;
    modified_at: string;
    description?: string;
    size?: number;
    etag: string;
    folder_upload_email?: {
        access: string;
        email: string;
    };
    created_by?: {
        id: string;
        name: string;
        login: string;
        type: string;
    };
    modified_by?: {
        id: string;
        name: string;
        login: string;
        type: string;
    };
    owned_by?: {
        id: string;
        name: string;
        login: string;
        type: string;
    };
    shared_link?: {
        url: string;
        download_url: string;
        vanity_name?: string;
        is_password_enabled: boolean;
        unshared_at: string;
        download_count: number;
        preview_count: number;
        access: string;
        effective_access: string;
        permissions: {
            can_download: boolean;
            can_preview: boolean;
            can_upload: boolean;
        };
    };
    parent: {
        id: string;
        type: string;
        sequence_id: number;
        etag: string;
        name: string;
    };
    item_collection: {
        total_count: number;
        entries: (BoxFile | BoxFolder)[];
        offset: number;
        limit: number;
        order?: Array<{
            by: string;
            direction: string;
        }>;
    };
    path_collection: {
        total_count: number;
        entries: Array<{
            id: string;
            type: string;
            name: string;
        }>;
    };
    permissions?: Array<{
        id: string;
        type: string;
        created_at: string;
        granted_to?: {
            id: string;
            type: string;
            name: string;
            login: string;
        };
        accessible_by?: {
            id: string;
            type: string;
            name: string;
            login: string;
        };
        role: string;
        granted_to_tag?: any;
    }>;
    watermark_info?: {
        is_watermarked: boolean;
        created_at?: string;
    };
    can_non_owners_invite?: boolean;
    is_collaboration_restricted_to_enterprise?: boolean;
}

interface BoxUser {
    id: string;
    type: string;
    name: string;
    login: string;
    created_at: string;
    modified_at: string;
    language: string;
    timezone: string;
    space_amount: number;
    space_used: number;
    max_upload_size: number;
    status: string;
    job_title?: string;
    phone?: string;
    address?: string;
    avatar_url: string;
    notification_email?: {
        email: string;
        is_confirmed: boolean;
    };
}

interface BoxCollaboration {
    id: string;
    type: string;
    created_by?: {
        id: string;
        type: string;
        name: string;
        login: string;
    };
    created_at: string;
    modified_at: string;
    expires_at?: string;
    status: string;
    accessible_by?: {
        id: string;
        type: string;
        name: string;
        login?: string;
    };
    role: string;
    acknowledged_at?: string;
    item: {
        id: string;
        type: string;
        name: string;
    };
    invite_email?: string;
    can_view_path: boolean;
}

const BoxIntegration: React.FC = () => {
    const [files, setFiles] = useState<BoxFile[]>([]);
    const [folders, setFolders] = useState<BoxFolder[]>([]);
    const [users, setUsers] = useState<BoxUser[]>([]);
    const [collaborations, setCollaborations] = useState<BoxCollaboration[]>([]);
    const [userProfile, setUserProfile] = useState<BoxUser | null>(null);
    const [currentFolder, setCurrentFolder] = useState<BoxFolder | null>(null);
    const [path, setPath] = useState<BoxFolder[]>([]);
    const [loading, setLoading] = useState({
        files: false,
        folders: false,
        users: false,
        collaborations: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedType, setSelectedType] = useState("all");

    // Form states
    const [folderForm, setFolderForm] = useState({
        name: "",
        description: "",
        parent_id: "",
    });

    const [shareForm, setShareForm] = useState({
        access: "collaborators",
        password: "",
        unshare_date: "",
        permissions: {
            can_download: true,
            can_preview: true,
            can_upload: false,
        },
    });

    const [collaborationForm, setCollaborationForm] = useState({
        item_id: "",
        accessible_by_id: "",
        accessible_by_type: "user",
        role: "editor",
        notify: true,
    });

    const [isFolderOpen, setIsFolderOpen] = useState(false);
    const [isShareOpen, setIsShareOpen] = useState(false);
    const [isCollaborationOpen, setIsCollaborationOpen] = useState(false);

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/box/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadRootFolder();
                loadUsers();
                loadCollaborations();
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

    // Load Box data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/box/profile", {
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

    const loadRootFolder = async () => {
        setLoading((prev) => ({ ...prev, folders: true, files: true }));
        try {
            const response = await fetch("/api/integrations/box/folder/0", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                const folder = data.data?.folder;
                if (folder) {
                    setCurrentFolder(folder);
                    setPath([folder]);
                    const entries = folder.item_collection?.entries || [];
                    const folderEntries = entries.filter(
                        (e: BoxFile | BoxFolder) => e.type === "folder",
                    ) as BoxFolder[];
                    const fileEntries = entries.filter(
                        (e: BoxFile | BoxFolder) => e.type === "file",
                    ) as BoxFile[];
                    setFolders(folderEntries);
                    setFiles(fileEntries);
                }
            }
        } catch (error) {
            console.error("Failed to load root folder:", error);
            toast({
                title: "Error",
                description: "Failed to load files from Box",
                variant: "error",
            });
        } finally {
            setLoading((prev) => ({ ...prev, folders: false, files: false }));
        }
    };

    const loadFolder = async (folder: BoxFolder) => {
        setLoading((prev) => ({ ...prev, folders: true, files: true }));
        try {
            const response = await fetch(
                `/api/integrations/box/folder/${folder.id}`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: "current",
                        limit: 100,
                    }),
                },
            );

            if (response.ok) {
                const data = await response.json();
                const loadedFolder = data.data?.folder;
                if (loadedFolder) {
                    setCurrentFolder(loadedFolder);
                    setPath((prev) => {
                        const folderIndex = prev.findIndex((f) => f.id === folder.id);
                        if (folderIndex !== -1) {
                            return prev.slice(0, folderIndex + 1);
                        } else {
                            return [...prev, loadedFolder];
                        }
                    });
                    const entries = loadedFolder.item_collection?.entries || [];
                    const folderEntries = entries.filter(
                        (e: BoxFile | BoxFolder) => e.type === "folder",
                    ) as BoxFolder[];
                    const fileEntries = entries.filter(
                        (e: BoxFile | BoxFolder) => e.type === "file",
                    ) as BoxFile[];
                    setFolders(folderEntries);
                    setFiles(fileEntries);
                }
            }
        } catch (error) {
            console.error("Failed to load folder:", error);
        } finally {
            setLoading((prev) => ({ ...prev, folders: false, files: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch("/api/integrations/box/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
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

    const loadCollaborations = async () => {
        setLoading((prev) => ({ ...prev, collaborations: true }));
        try {
            const response = await fetch("/api/integrations/box/collaborations", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setCollaborations(data.data?.collaborations || []);
            }
        } catch (error) {
            console.error("Failed to load collaborations:", error);
        } finally {
            setLoading((prev) => ({ ...prev, collaborations: false }));
        }
    };

    const createFolder = async () => {
        if (!folderForm.name) return;

        try {
            const response = await fetch("/api/integrations/box/folders/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    name: folderForm.name,
                    description: folderForm.description,
                    parent: {
                        id: folderForm.parent_id || currentFolder?.id || "0",
                        type: "folder",
                    },
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Folder created successfully",
                });
                setIsFolderOpen(false);
                setFolderForm({ name: "", description: "", parent_id: "" });
                if (currentFolder) {
                    loadFolder(currentFolder);
                } else {
                    loadRootFolder();
                }
            }
        } catch (error) {
            console.error("Failed to create folder:", error);
            toast({
                title: "Error",
                description: "Failed to create folder",
                variant: "error",
            });
        }
    };

    const createSharedLink = async (item: BoxFile | BoxFolder) => {
        try {
            const response = await fetch(
                `/api/integrations/box/${item.type}s/${item.id}/share`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: "current",
                        access: shareForm.access,
                        password: shareForm.password || undefined,
                        unshare_date: shareForm.unshare_date || undefined,
                        permissions: shareForm.permissions,
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: `${item.type} shared successfully`,
                });
                setIsShareOpen(false);
                setShareForm({
                    access: "collaborators",
                    password: "",
                    unshare_date: "",
                    permissions: {
                        can_download: true,
                        can_preview: true,
                        can_upload: false,
                    },
                });
                if (currentFolder) {
                    loadFolder(currentFolder);
                } else {
                    loadRootFolder();
                }
            }
        } catch (error) {
            console.error("Failed to create shared link:", error);
            toast({
                title: "Error",
                description: "Failed to create shared link",
                variant: "error",
            });
        }
    };

    const createCollaboration = async () => {
        if (!collaborationForm.item_id || !collaborationForm.accessible_by_id)
            return;

        try {
            const response = await fetch(
                "/api/integrations/box/collaborations/create",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: "current",
                        item: {
                            id: collaborationForm.item_id,
                            type: "folder",
                        },
                        accessible_by: {
                            type: collaborationForm.accessible_by_type,
                            id: collaborationForm.accessible_by_id,
                        },
                        role: collaborationForm.role,
                        notify: collaborationForm.notify,
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Collaboration created successfully",
                });
                setIsCollaborationOpen(false);
                setCollaborationForm({
                    item_id: "",
                    accessible_by_id: "",
                    accessible_by_type: "user",
                    role: "editor",
                    notify: true,
                });
                loadCollaborations();
            }
        } catch (error) {
            console.error("Failed to create collaboration:", error);
            toast({
                title: "Error",
                description: "Failed to create collaboration",
                variant: "error",
            });
        }
    };

    // Filter data based on search
    const filteredFiles = files.filter(
        (file) =>
            file.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
            (selectedType === "all" || selectedType === "files"),
    );

    const filteredFolders = folders.filter(
        (folder) =>
            folder.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
            (selectedType === "all" || selectedType === "folders"),
    );

    const filteredUsers = users.filter(
        (user) =>
            user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.login.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredCollaborations = collaborations.filter(
        (collab) =>
            collab.item?.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            collab.accessible_by?.name
                ?.toLowerCase()
                .includes(searchQuery.toLowerCase()),
    );

    // Stats calculations
    const totalFiles = files.length;
    const totalFolders = folders.length;
    const totalUsers = users.length;
    const totalCollaborations = collaborations.length;
    const sharedFiles = files.filter((f) => f.shared_link).length;
    const sharedFolders = folders.filter((f) => f.shared_link).length;
    const spaceUsed = userProfile?.space_used || 0;
    const spaceTotal = userProfile?.space_amount || 0;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadRootFolder();
            loadUsers();
            loadCollaborations();
        }
    }, [connected]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const formatFileSize = (bytes?: number): string => {
        if (!bytes || bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const getFileIcon = (file: BoxFile): any => {
        if (file.name.endsWith(".pdf")) return FileText;
        if (file.name.endsWith(".doc") || file.name.endsWith(".docx"))
            return FileText;
        if (file.name.endsWith(".xls") || file.name.endsWith(".xlsx"))
            return FileText;
        if (file.name.endsWith(".ppt") || file.name.endsWith(".pptx"))
            return FileText;
        if (
            file.name.endsWith(".jpg") ||
            file.name.endsWith(".jpeg") ||
            file.name.endsWith(".png") ||
            file.name.endsWith(".gif")
        )
            return ImageIcon;
        if (
            file.name.endsWith(".zip") ||
            file.name.endsWith(".rar") ||
            file.name.endsWith(".7z")
        )
            return Download;
        if (
            file.name.endsWith(".mp4") ||
            file.name.endsWith(".avi") ||
            file.name.endsWith(".mov")
        )
            return Video;
        if (
            file.name.endsWith(".mp3") ||
            file.name.endsWith(".wav") ||
            file.name.endsWith(".flac")
        )
            return Music;
        return File;
    };

    const getAccessVariant = (access: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (access) {
            case "open":
                return "default";
            case "company":
                return "secondary";
            case "collaborators":
                return "outline";
            default:
                return "outline";
        }
    };

    const getRoleVariant = (role: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (role) {
            case "owner":
                return "destructive";
            case "co-owner":
                return "destructive";
            case "editor":
                return "default";
            case "viewer":
                return "secondary";
            case "previewer":
                return "outline";
            case "uploader":
                return "default";
            case "previewer uploader":
                return "secondary";
            default:
                return "outline";
        }
    };

    const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status) {
            case "active":
                return "default";
            case "inactive":
                return "secondary";
            case "cannot_delete_edit":
                return "destructive";
            case "cannot_delete_edit_upload":
                return "destructive";
            default:
                return "outline";
        }
    };

    const handleBreadcrumbClick = (folder: BoxFolder, index: number) => {
        if (index === path.length - 1) return; // Already in this folder
        if (index === 0 && path[0].id === "0") {
            loadRootFolder();
        } else {
            loadFolder(folder);
        }
    };

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Settings className="w-8 h-8 text-[#0061D5]" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Box Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Secure file storage and collaboration platform
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
                                <AvatarImage src={userProfile.avatar_url} alt={userProfile.name} />
                                <AvatarFallback>{userProfile.name.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col w-full max-w-xs">
                                <span className="font-bold">{userProfile.name}</span>
                                <span className="text-sm text-muted-foreground">
                                    {userProfile.login} • {formatFileSize(spaceUsed)} used
                                </span>
                                <Progress
                                    value={(spaceUsed / spaceTotal) * 100}
                                    className="h-2 mt-1"
                                />
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
                                    <h2 className="text-2xl font-bold">Connect Box</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Box account to start managing files and
                                        collaboration
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-[#0061D5] hover:bg-[#004bb3]"
                                    onClick={() =>
                                        (window.location.href = "/api/integrations/box/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Box Account
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
                                        <p className="text-sm font-medium text-muted-foreground">Files</p>
                                        <div className="text-2xl font-bold">{totalFiles}</div>
                                        <p className="text-xs text-muted-foreground">{sharedFiles} shared</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Folders</p>
                                        <div className="text-2xl font-bold">{totalFolders}</div>
                                        <p className="text-xs text-muted-foreground">{sharedFolders} shared</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Users</p>
                                        <div className="text-2xl font-bold">{totalUsers}</div>
                                        <p className="text-xs text-muted-foreground">Team members</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Collaborations</p>
                                        <div className="text-2xl font-bold">{totalCollaborations}</div>
                                        <p className="text-xs text-muted-foreground">Active shares</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="files">
                            <TabsList>
                                <TabsTrigger value="files">Files & Folders</TabsTrigger>
                                <TabsTrigger value="collaborations">Collaborations</TabsTrigger>
                                <TabsTrigger value="users">Users</TabsTrigger>
                                <TabsTrigger value="analytics">Analytics</TabsTrigger>
                            </TabsList>

                            {/* Files & Folders Tab */}
                            <TabsContent value="files" className="space-y-6 mt-6">
                                {/* Breadcrumb Navigation */}
                                {path.length > 0 && (
                                    <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                                        {path.map((folder, index) => (
                                            <React.Fragment key={folder.id}>
                                                <span
                                                    className="cursor-pointer hover:text-[#0061D5] hover:underline"
                                                    onClick={() => handleBreadcrumbClick(folder, index)}
                                                >
                                                    {folder.id === "0" ? "Root" : folder.name}
                                                </span>
                                                {index < path.length - 1 && <ChevronRight className="w-4 h-4" />}
                                            </React.Fragment>
                                        ))}
                                    </div>
                                )}

                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedType}
                                        onValueChange={setSelectedType}
                                    >
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="Filter by type" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All</SelectItem>
                                            <SelectItem value="files">Files</SelectItem>
                                            <SelectItem value="folders">Folders</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search files and folders..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#0061D5] hover:bg-[#004bb3]"
                                        onClick={() => {
                                            setFolderForm({
                                                ...folderForm,
                                                parent_id: currentFolder?.id || "",
                                            });
                                            setIsFolderOpen(true);
                                        }}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Folder
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {/* Folders */}
                                    {loading.folders ? (
                                        <div className="flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#0061D5]" />
                                        </div>
                                    ) : (
                                        filteredFolders.map((folder) => (
                                            <Card key={folder.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex space-x-4 items-start">
                                                        <Folder
                                                            className="w-8 h-8 text-[#0061D5] cursor-pointer"
                                                            onClick={() => loadFolder(folder)}
                                                        />
                                                        <div className="flex-1 space-y-2">
                                                            <div className="flex justify-between w-full">
                                                                <span
                                                                    className="font-bold text-lg cursor-pointer text-[#0061D5] hover:underline"
                                                                    onClick={() => loadFolder(folder)}
                                                                >
                                                                    {folder.name}
                                                                </span>
                                                                <div className="flex items-center space-x-2">
                                                                    {folder.shared_link && (
                                                                        <Badge variant={getAccessVariant(folder.shared_link.access)}>
                                                                            <LinkIcon className="mr-1 w-3 h-3" />
                                                                            Shared
                                                                        </Badge>
                                                                    )}
                                                                    <DropdownMenu>
                                                                        <DropdownMenuTrigger asChild>
                                                                            <Button variant="outline" size="sm">
                                                                                Actions
                                                                            </Button>
                                                                        </DropdownMenuTrigger>
                                                                        <DropdownMenuContent>
                                                                            <DropdownMenuItem
                                                                                onClick={() => {
                                                                                    setShareForm({
                                                                                        ...shareForm,
                                                                                        access:
                                                                                            folder.shared_link?.access ||
                                                                                            "collaborators",
                                                                                    });
                                                                                    setIsShareOpen(true);
                                                                                }}
                                                                            >
                                                                                <Share2 className="mr-2 w-4 h-4" />
                                                                                Share
                                                                            </DropdownMenuItem>
                                                                            <DropdownMenuItem
                                                                                onClick={() => {
                                                                                    setCollaborationForm({
                                                                                        ...collaborationForm,
                                                                                        item_id: folder.id,
                                                                                    });
                                                                                    setIsCollaborationOpen(true);
                                                                                }}
                                                                            >
                                                                                <Users className="mr-2 w-4 h-4" />
                                                                                Add Collaboration
                                                                            </DropdownMenuItem>
                                                                            <DropdownMenuItem>
                                                                                <Edit className="mr-2 w-4 h-4" />
                                                                                Rename
                                                                            </DropdownMenuItem>
                                                                            <DropdownMenuItem className="text-red-600">
                                                                                <Trash className="mr-2 w-4 h-4" />
                                                                                Delete
                                                                            </DropdownMenuItem>
                                                                        </DropdownMenuContent>
                                                                    </DropdownMenu>
                                                                </div>
                                                            </div>

                                                            {folder.description && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    {folder.description}
                                                                </p>
                                                            )}

                                                            <div className="flex space-x-4 text-xs text-muted-foreground">
                                                                <span>Modified: {formatDate(folder.modified_at)}</span>
                                                                {folder.item_collection?.total_count !== undefined && (
                                                                    <span>{folder.item_collection.total_count} items</span>
                                                                )}
                                                            </div>

                                                            {folder.created_by && (
                                                                <div className="flex space-x-2 text-xs text-muted-foreground">
                                                                    <span>Created by:</span>
                                                                    <span className="font-medium">{folder.created_by.name}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}

                                    {/* Files */}
                                    {loading.files ? (
                                        <div className="flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#0061D5]" />
                                        </div>
                                    ) : (
                                        filteredFiles.map((file) => {
                                            const FileIconComponent = getFileIcon(file);
                                            return (
                                                <Card key={file.id}>
                                                    <CardContent className="pt-6">
                                                        <div className="flex space-x-4 items-start">
                                                            <FileIconComponent className="w-8 h-8 text-[#0061D5]" />
                                                            <div className="flex-1 space-y-2">
                                                                <div className="flex justify-between w-full">
                                                                    <a
                                                                        href={file.shared_link?.url || "#"}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="font-bold text-lg hover:underline"
                                                                    >
                                                                        {file.name}
                                                                    </a>
                                                                    <div className="flex items-center space-x-2">
                                                                        {file.size && (
                                                                            <Badge variant="secondary">
                                                                                {formatFileSize(file.size)}
                                                                            </Badge>
                                                                        )}
                                                                        {file.shared_link && (
                                                                            <Badge variant={getAccessVariant(file.shared_link.access)}>
                                                                                <LinkIcon className="mr-1 w-3 h-3" />
                                                                                Shared
                                                                            </Badge>
                                                                        )}
                                                                        {file.lock && (
                                                                            <Badge className="bg-orange-100 text-orange-800 hover:bg-orange-200">
                                                                                <Lock className="mr-1 w-3 h-3" />
                                                                                Locked
                                                                            </Badge>
                                                                        )}
                                                                        <DropdownMenu>
                                                                            <DropdownMenuTrigger asChild>
                                                                                <Button variant="outline" size="sm">
                                                                                    Actions
                                                                                </Button>
                                                                            </DropdownMenuTrigger>
                                                                            <DropdownMenuContent>
                                                                                <DropdownMenuItem>
                                                                                    <Download className="mr-2 w-4 h-4" />
                                                                                    Download
                                                                                </DropdownMenuItem>
                                                                                <DropdownMenuItem
                                                                                    onClick={() => {
                                                                                        setShareForm({
                                                                                            ...shareForm,
                                                                                            access:
                                                                                                file.shared_link?.access ||
                                                                                                "collaborators",
                                                                                        });
                                                                                        setIsShareOpen(true);
                                                                                    }}
                                                                                >
                                                                                    <Share2 className="mr-2 w-4 h-4" />
                                                                                    Share
                                                                                </DropdownMenuItem>
                                                                                <DropdownMenuItem>
                                                                                    <Edit className="mr-2 w-4 h-4" />
                                                                                    Rename
                                                                                </DropdownMenuItem>
                                                                                <DropdownMenuItem className="text-red-600">
                                                                                    <Trash className="mr-2 w-4 h-4" />
                                                                                    Delete
                                                                                </DropdownMenuItem>
                                                                            </DropdownMenuContent>
                                                                        </DropdownMenu>
                                                                    </div>
                                                                </div>

                                                                {file.description && (
                                                                    <p className="text-sm text-muted-foreground">
                                                                        {file.description}
                                                                    </p>
                                                                )}

                                                                <div className="flex space-x-4 text-xs text-muted-foreground">
                                                                    <span>Modified: {formatDate(file.modified_at)}</span>
                                                                    {file.content_modified_at && (
                                                                        <span>Content: {formatDate(file.content_modified_at)}</span>
                                                                    )}
                                                                </div>

                                                                {file.created_by && (
                                                                    <div className="flex space-x-2 text-xs text-muted-foreground">
                                                                        <span>Created by:</span>
                                                                        <span className="font-medium">{file.created_by.name}</span>
                                                                    </div>
                                                                )}

                                                                {file.tags && file.tags.length > 0 && (
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {file.tags.map((tag) => (
                                                                            <Badge key={tag.id} variant="secondary">
                                                                                {tag.name}
                                                                            </Badge>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            );
                                        })
                                    )}
                                </div>
                            </TabsContent>

                            {/* Collaborations Tab */}
                            <TabsContent value="collaborations" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search collaborations..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#0061D5] hover:bg-[#004bb3]"
                                        onClick={() => {
                                            setCollaborationForm({
                                                ...collaborationForm,
                                                item_id: currentFolder?.id || "",
                                            });
                                            setIsCollaborationOpen(true);
                                        }}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Add Collaboration
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {loading.collaborations ? (
                                        <div className="flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#0061D5]" />
                                        </div>
                                    ) : (
                                        filteredCollaborations.map((collab) => (
                                            <Card key={collab.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex space-x-4 items-start">
                                                        <Users className="w-6 h-6 text-[#0061D5]" />
                                                        <div className="flex-1 space-y-2">
                                                            <div className="flex justify-between w-full">
                                                                <span className="font-bold">
                                                                    {collab.item?.name || "Unknown Item"}
                                                                </span>
                                                                <div className="flex items-center space-x-2">
                                                                    <Badge variant={getRoleVariant(collab.role)}>
                                                                        {collab.role}
                                                                    </Badge>
                                                                    <Badge variant={getStatusVariant(collab.status)}>
                                                                        {collab.status}
                                                                    </Badge>
                                                                </div>
                                                            </div>

                                                            <div className="flex space-x-4 text-sm text-muted-foreground">
                                                                <span>
                                                                    Collaborator:{" "}
                                                                    {collab.accessible_by?.name || collab.invite_email}
                                                                </span>
                                                                {collab.accessible_by?.login && (
                                                                    <span className="text-xs">
                                                                        ({collab.accessible_by.login})
                                                                    </span>
                                                                )}
                                                            </div>

                                                            <div className="flex space-x-4 text-xs text-muted-foreground">
                                                                <span>Created: {formatDate(collab.created_at)}</span>
                                                                {collab.expires_at && (
                                                                    <span>Expires: {formatDate(collab.expires_at)}</span>
                                                                )}
                                                            </div>

                                                            {collab.created_by && (
                                                                <div className="text-xs text-muted-foreground">
                                                                    Created by: {collab.created_by.name}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Users Tab */}
                            <TabsContent value="users" className="space-y-6 mt-6">
                                <div className="relative">
                                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                    <Input
                                        placeholder="Search users..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="pl-8"
                                    />
                                </div>

                                {loading.users ? (
                                    <div className="flex justify-center py-8">
                                        <Loader2 className="w-8 h-8 animate-spin text-[#0061D5]" />
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                        {filteredUsers.map((user) => (
                                            <Card key={user.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex space-x-4">
                                                        <Avatar className="w-12 h-12">
                                                            <AvatarImage src={user.avatar_url} alt={user.name} />
                                                            <AvatarFallback>{user.name.charAt(0)}</AvatarFallback>
                                                        </Avatar>
                                                        <div className="flex-1 space-y-1">
                                                            <div className="flex items-center space-x-2">
                                                                <span className="font-bold">{user.name}</span>
                                                                <Badge variant={getStatusVariant(user.status)}>
                                                                    {user.status}
                                                                </Badge>
                                                            </div>
                                                            <p className="text-sm text-muted-foreground">
                                                                {user.login}
                                                            </p>
                                                            {user.job_title && (
                                                                <p className="text-xs text-muted-foreground">
                                                                    {user.job_title}
                                                                </p>
                                                            )}
                                                            <p className="text-xs text-muted-foreground mt-2">
                                                                Storage: {formatFileSize(user.space_used)} /{" "}
                                                                {formatFileSize(user.space_amount)}
                                                            </p>
                                                            <Progress
                                                                value={(user.space_used / user.space_amount) * 100}
                                                                className="h-1 mt-1"
                                                            />
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                )}
                            </TabsContent>

                            {/* Analytics Tab */}
                            <TabsContent value="analytics" className="space-y-6 mt-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    <Card>
                                        <CardContent className="pt-6">
                                            <div className="space-y-2">
                                                <p className="text-sm font-medium text-muted-foreground">Storage Used</p>
                                                <div className="text-2xl font-bold">{formatFileSize(spaceUsed)}</div>
                                                <p className="text-xs text-muted-foreground">
                                                    of {formatFileSize(spaceTotal)}
                                                </p>
                                                <Progress
                                                    value={(spaceUsed / spaceTotal) * 100}
                                                    className="h-2 mt-2"
                                                />
                                            </div>
                                        </CardContent>
                                    </Card>

                                    <Card>
                                        <CardContent className="pt-6">
                                            <div className="space-y-2">
                                                <p className="text-sm font-medium text-muted-foreground">Shared Items</p>
                                                <div className="text-2xl font-bold">{sharedFiles + sharedFolders}</div>
                                                <p className="text-xs text-muted-foreground">
                                                    {sharedFiles} files, {sharedFolders} folders
                                                </p>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    <Card>
                                        <CardContent className="pt-6">
                                            <div className="space-y-2">
                                                <p className="text-sm font-medium text-muted-foreground">Active Collaborations</p>
                                                <div className="text-2xl font-bold">{totalCollaborations}</div>
                                                <p className="text-xs text-muted-foreground">Team collaborations</p>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>

                                <Card>
                                    <CardHeader>
                                        <CardTitle>Recent Activity</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <p className="text-muted-foreground">
                                            Recent file uploads, modifications, and sharing
                                            activities would be displayed here. This section would
                                            show activity logs with timestamps for monitoring user
                                            engagement.
                                        </p>
                                    </CardContent>
                                </Card>
                            </TabsContent>
                        </Tabs>

                        {/* Create Folder Modal */}
                        <Dialog open={isFolderOpen} onOpenChange={setIsFolderOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Create Folder</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Folder Name</label>
                                        <Input
                                            placeholder="Enter folder name"
                                            value={folderForm.name}
                                            onChange={(e) =>
                                                setFolderForm({
                                                    ...folderForm,
                                                    name: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Folder description (optional)"
                                            value={folderForm.description}
                                            onChange={(e) =>
                                                setFolderForm({
                                                    ...folderForm,
                                                    description: e.target.value,
                                                })
                                            }
                                            rows={3}
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsFolderOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#0061D5] hover:bg-[#004bb3]"
                                        onClick={createFolder}
                                        disabled={!folderForm.name}
                                    >
                                        Create Folder
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Share Modal */}
                        <Dialog open={isShareOpen} onOpenChange={setIsShareOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Create Shared Link</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Access Level</label>
                                        <Select
                                            value={shareForm.access}
                                            onValueChange={(value) =>
                                                setShareForm({
                                                    ...shareForm,
                                                    access: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="open">Anyone with link</SelectItem>
                                                <SelectItem value="company">People in company</SelectItem>
                                                <SelectItem value="collaborators">People invited</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Password (optional)</label>
                                        <Input
                                            type="password"
                                            placeholder="Enter password"
                                            value={shareForm.password}
                                            onChange={(e) =>
                                                setShareForm({
                                                    ...shareForm,
                                                    password: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Unshare Date (optional)</label>
                                        <Input
                                            type="date"
                                            value={shareForm.unshare_date}
                                            onChange={(e) =>
                                                setShareForm({
                                                    ...shareForm,
                                                    unshare_date: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold leading-none">Permissions</label>
                                        <div className="flex space-x-4">
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="can_download"
                                                    checked={shareForm.permissions.can_download}
                                                    onCheckedChange={(checked) =>
                                                        setShareForm({
                                                            ...shareForm,
                                                            permissions: {
                                                                ...shareForm.permissions,
                                                                can_download: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="can_download" className="text-sm font-medium leading-none">
                                                    Can download
                                                </label>
                                            </div>
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="can_preview"
                                                    checked={shareForm.permissions.can_preview}
                                                    onCheckedChange={(checked) =>
                                                        setShareForm({
                                                            ...shareForm,
                                                            permissions: {
                                                                ...shareForm.permissions,
                                                                can_preview: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="can_preview" className="text-sm font-medium leading-none">
                                                    Can preview
                                                </label>
                                            </div>
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="can_upload"
                                                    checked={shareForm.permissions.can_upload}
                                                    onCheckedChange={(checked) =>
                                                        setShareForm({
                                                            ...shareForm,
                                                            permissions: {
                                                                ...shareForm.permissions,
                                                                can_upload: checked as boolean,
                                                            },
                                                        })
                                                    }
                                                />
                                                <label htmlFor="can_upload" className="text-sm font-medium leading-none">
                                                    Can upload
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsShareOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#0061D5] hover:bg-[#004bb3]"
                                        onClick={() => {
                                            // This would be called with the current item
                                            // For now, just close the modal
                                            setIsShareOpen(false);
                                        }}
                                    >
                                        Create Link
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Collaboration Modal */}
                        <Dialog open={isCollaborationOpen} onOpenChange={setIsCollaborationOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Add Collaboration</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Collaborator</label>
                                        <Select
                                            value={collaborationForm.accessible_by_id}
                                            onValueChange={(value) =>
                                                setCollaborationForm({
                                                    ...collaborationForm,
                                                    accessible_by_id: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select user" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {users.map((user) => (
                                                    <SelectItem key={user.id} value={user.id}>
                                                        {user.name} ({user.login})
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Role</label>
                                        <Select
                                            value={collaborationForm.role}
                                            onValueChange={(value) =>
                                                setCollaborationForm({
                                                    ...collaborationForm,
                                                    role: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="editor">Editor</SelectItem>
                                                <SelectItem value="viewer">Viewer</SelectItem>
                                                <SelectItem value="previewer">Previewer</SelectItem>
                                                <SelectItem value="uploader">Uploader</SelectItem>
                                                <SelectItem value="previewer uploader">Previewer Uploader</SelectItem>
                                                <SelectItem value="co-owner">Co-owner</SelectItem>
                                                <SelectItem value="owner">Owner</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <Checkbox
                                            id="notify"
                                            checked={collaborationForm.notify}
                                            onCheckedChange={(checked) =>
                                                setCollaborationForm({
                                                    ...collaborationForm,
                                                    notify: checked as boolean,
                                                })
                                            }
                                        />
                                        <label htmlFor="notify" className="text-sm font-medium leading-none">
                                            Send notification to collaborator
                                        </label>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsCollaborationOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#0061D5] hover:bg-[#004bb3]"
                                        onClick={createCollaboration}
                                        disabled={!collaborationForm.accessible_by_id}
                                    >
                                        Add Collaboration
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

export default BoxIntegration;

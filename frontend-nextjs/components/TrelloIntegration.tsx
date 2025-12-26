/**
 * Trello Integration Component
 * Complete Trello project management and task tracking integration
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
    Trash2,
    MessageSquare,
    Calendar,
    Loader2,
    Layout,
    List,
    Users,
    ExternalLink,
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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface TrelloBoard {
    id: string;
    name: string;
    desc: string;
    closed: boolean;
    idOrganization: string;
    pinned: boolean;
    url: string;
    shortUrl: string;
    prefs: {
        background: string;
        backgroundImage: string;
        backgroundImageScaled: any[];
        backgroundTile: boolean;
        backgroundBrightness: string;
        backgroundTopColor: string;
        backgroundSideColor: string;
        canBePublic: boolean;
        canBeOrg: boolean;
        canBePrivate: boolean;
        canInvite: boolean;
    };
    labelNames: {
        green: string;
        yellow: string;
        orange: string;
        red: string;
        purple: string;
        blue: string;
        sky: string;
        lime: string;
        pink: string;
        black: string;
    };
    limits: any;
    dateLastActivity: string;
    dateLastView: string;
    shortLink: string;
    starred: boolean;
    memberships: Array<{
        id: string;
        idMember: string;
        memberType: string;
        unconfirmed: boolean;
        deactivated: boolean;
    }>;
    invited: boolean;
    organization: {
        id: string;
        name: string;
        displayName: string;
        desc: string;
        website: string;
        logoHash: string;
        products: any[];
        powerUps: any[];
        limits: any;
    };
    enterpriseId?: string;
    enterpriseName?: string;
    enterprisePermissions?: string[];
    invitedToEnterprise?: boolean;
    isEnterpriseManaged?: boolean;
}

interface TrelloList {
    id: string;
    name: string;
    closed: boolean;
    idBoard: string;
    pos: number;
    softLimit?: number;
    subscribed?: boolean;
}

interface TrelloCard {
    id: string;
    name: string;
    desc: string;
    closed: boolean;
    idChecklists: string[];
    idChecklistStates: any[];
    idBoard: string;
    idList: string;
    idMembers: string[];
    idLabels: string[];
    idShort: number;
    idAttachmentCover: string;
    manualCoverAttachment: boolean;
    due: string;
    dueComplete: boolean;
    start: string;
    url: string;
    shortUrl: string;
    shortLink: string;
    pos: number;
    subscribed: boolean;
    badges: {
        attachments: number;
        attachmentsByType: {
            upload: number;
            trello: number;
            s3: number;
            ios: number;
            dropbox: number;
            google: number;
            onedrive: number;
        };
        location: number;
        comments: number;
        description: boolean;
        dueComplete: boolean;
        due: boolean;
        fogbugz: string;
        checkItems: number;
        checkItemsChecked: number;
        viewMemberVotes: number;
        voting: number;
    };
    createdAt: string;
    dateLastActivity: string;
}

interface TrelloMember {
    id: string;
    username: string;
    fullName: string;
    initials: string;
    avatarHash: string;
    avatarUrl: string;
    avatarUrl30: string;
    avatarUrl50: string;
    avatarUrl72: string;
    avatarUrl170: string;
    avatarUrl195: string;
    avatarUrl232: string;
    idMemberReferrer?: string;
    idPremOrgsAdmin?: any[];
    activityBlocked: boolean;
    bio?: string;
    bioData?: {
        emoji: any;
        text: string;
    };
    confirmed: boolean;
    idEnterprises?: string[];
    enterprises?: Array<{
        id: string;
        displayName: string;
        name: string;
        logoHash: string;
        logoUrl: string;
        premiumFeatures: any[];
        product: string;
    }>;
    idEnterprisesAdmin?: string[];
    idOrganizations: string[];
    memberType: string;
    products: string[];
    uploadedAvatar: boolean;
    url: string;
    email?: string;
    emailVerified: boolean;
    marketingOptIn: boolean;
    marketingOptOut: boolean;
    oneTimeMessagesDismissed: string[];
    prefs: {
        blockedSuppliers: string[];
        cardCovers: boolean;
        cardCoversAll: boolean;
        cardAgeMinutes: number;
        cardShortUrl: boolean;
        customBoardBgColor: string;
        customBoardBgImage?: string;
        customBoardBgImageScaled?: any[];
        customBoardBgImageURL?: string;
        customBoardBgTile: boolean;
        customEmoji: any;
        customStickers: any[];
        defaultBoardBgColor: string;
        defaultCardList: string;
        defaultBoardBgImage?: string;
        defaultBoardBgImageURL?: string;
        defaultBoardBgTile?: boolean;
        defaultStatus: string;
        desc: string;
        developer: boolean;
        disableActivityGrouping: boolean;
        domain: string;
        emailActivity: boolean;
        embedlyFeatures: boolean;
        greeting: string;
        includeOriginalAttachmentsInCardBacks: boolean;
        invitationPref: string;
        language: string;
        minutePlusOffset: number;
        name: string;
        noAttachComments: boolean;
        noBillableGuests: boolean;
        noInvites: boolean;
        noRecentActivity: boolean;
        noUpdatesEmail: boolean;
        noVisitBillableMembers: boolean;
        noWelcome: boolean;
        notifications: string[];
        orgPermissionLevel: string;
        organizations: any[];
        permissionLevel: string;
        starredBoards: string[];
        showCardsLimit: boolean;
        showDetailsOnCardDrag: boolean;
        showUlist: boolean;
        suggestions: string[];
        minutesBetweenSummaries: number;
        minutesBeforeDeadline: number;
        minutesBeforeDue: number;
        sendEmailOnRightNow: boolean;
        showTip: boolean;
        sumIncludeLinked: boolean;
        timelineAutoLoad: boolean;
        timeTrackingEnabled: boolean;
        timelineVisible: boolean;
        seeInvites: boolean;
        timezone: string;
        timezoneInfo: {
            offset: number;
        };
        twoFactorAuth: boolean;
        twoFactorAuthProvider: string;
        virtualBoardFilters: string[];
    };
    status: string;
    enterpriseType?: string;
    enterpriseOrganization?: any;
    trialBadge: string;
}

const TrelloIntegration: React.FC = () => {
    const [boards, setBoards] = useState<TrelloBoard[]>([]);
    const [lists, setLists] = useState<TrelloList[]>([]);
    const [cards, setCards] = useState<TrelloCard[]>([]);
    const [members, setMembers] = useState<TrelloMember[]>([]);
    const [userProfile, setUserProfile] = useState<TrelloMember | null>(null);
    const [loading, setLoading] = useState({
        boards: false,
        lists: false,
        cards: false,
        members: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedBoard, setSelectedBoard] = useState("");
    const [selectedList, setSelectedList] = useState("");

    // Form states
    const [cardForm, setCardForm] = useState({
        name: "",
        description: "",
        list_id: "",
        board_id: "",
        due: "",
        members: [] as string[],
        labels: [] as string[],
    });

    const [boardForm, setBoardForm] = useState({
        name: "",
        description: "",
        default_labels: true,
        default_lists: true,
        permission_level: "private",
        source_board_id: "",
        keep_from_source: "",
    });

    const [isCardOpen, setIsCardOpen] = useState(false);
    const [isBoardOpen, setIsBoardOpen] = useState(false);

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/trello/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadBoards();
                loadMembers();
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

    // Load Trello data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/trello/profile", {
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

    const loadBoards = async () => {
        setLoading((prev) => ({ ...prev, boards: true }));
        try {
            const response = await fetch("/api/integrations/trello/boards", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    filter: "open",
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setBoards(data.data?.boards || []);
            }
        } catch (error) {
            console.error("Failed to load boards:", error);
            toast({
                title: "Error",
                description: "Failed to load boards from Trello",
                variant: "error",
            });
        } finally {
            setLoading((prev) => ({ ...prev, boards: false }));
        }
    };

    const loadLists = async (boardId?: string) => {
        if (!boardId && !selectedBoard) return;

        setLoading((prev) => ({ ...prev, lists: true }));
        try {
            const response = await fetch("/api/integrations/trello/lists", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    board_id: boardId || selectedBoard,
                    filter: "open",
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setLists(data.data?.lists || []);
            }
        } catch (error) {
            console.error("Failed to load lists:", error);
        } finally {
            setLoading((prev) => ({ ...prev, lists: false }));
        }
    };

    const loadCards = async (listId?: string) => {
        if (!listId && !selectedList) return;

        setLoading((prev) => ({ ...prev, cards: true }));
        try {
            const response = await fetch("/api/integrations/trello/cards", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    board_id: selectedBoard,
                    list_id: listId || selectedList,
                    filter: "open",
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setCards(data.data?.cards || []);
            }
        } catch (error) {
            console.error("Failed to load cards:", error);
        } finally {
            setLoading((prev) => ({ ...prev, cards: false }));
        }
    };

    const loadMembers = async () => {
        setLoading((prev) => ({ ...prev, members: true }));
        try {
            const response = await fetch("/api/integrations/trello/members", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setMembers(data.data?.members || []);
            }
        } catch (error) {
            console.error("Failed to load members:", error);
        } finally {
            setLoading((prev) => ({ ...prev, members: false }));
        }
    };

    const createCard = async () => {
        if (!cardForm.name || !cardForm.list_id) return;

        try {
            const response = await fetch("/api/integrations/trello/cards/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    name: cardForm.name,
                    description: cardForm.description,
                    list_id: cardForm.list_id,
                    due: cardForm.due,
                    id_members: cardForm.members,
                    id_labels: cardForm.labels,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Card created successfully",
                });
                setIsCardOpen(false);
                setCardForm({
                    name: "",
                    description: "",
                    list_id: "",
                    board_id: "",
                    due: "",
                    members: [],
                    labels: [],
                });
                loadCards();
            }
        } catch (error) {
            console.error("Failed to create card:", error);
            toast({
                title: "Error",
                description: "Failed to create card",
                variant: "error",
            });
        }
    };

    const createBoard = async () => {
        if (!boardForm.name) return;

        try {
            const response = await fetch("/api/integrations/trello/boards/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    name: boardForm.name,
                    description: boardForm.description,
                    default_labels: boardForm.default_labels,
                    default_lists: boardForm.default_lists,
                    permission_level: boardForm.permission_level,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Board created successfully",
                });
                setIsBoardOpen(false);
                setBoardForm({
                    name: "",
                    description: "",
                    default_labels: true,
                    default_lists: true,
                    permission_level: "private",
                    source_board_id: "",
                    keep_from_source: "",
                });
                loadBoards();
            }
        } catch (error) {
            console.error("Failed to create board:", error);
            toast({
                title: "Error",
                description: "Failed to create board",
                variant: "error",
            });
        }
    };

    // Filter data based on search
    const filteredBoards = boards.filter(
        (board) =>
            board.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            board.desc.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredCards = cards.filter(
        (card) =>
            card.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            card.desc.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredMembers = members.filter(
        (member) =>
            member.fullName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            member.username.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Stats calculations
    const totalBoards = boards.length;
    const openBoards = boards.filter(b => !b.closed).length;
    const totalCards = cards.length;
    const cardsWithDue = cards.filter(c => c.due).length;
    const cardsOverdue = cards.filter(c => c.due && !c.dueComplete && new Date(c.due) < new Date()).length;
    const totalMembers = members.length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadBoards();
            loadMembers();
        }
    }, [connected]);

    useEffect(() => {
        if (selectedBoard) {
            loadLists();
            loadCards();
        }
    }, [selectedBoard]);

    useEffect(() => {
        if (selectedList) {
            loadCards();
        }
    }, [selectedList]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const getCardDueVariant = (due: string, dueComplete: boolean): "default" | "secondary" | "destructive" | "outline" => {
        if (!due) return "outline";
        if (dueComplete) return "default"; // green-ish
        if (new Date(due) < new Date()) return "destructive";
        if (new Date(due) < new Date(Date.now() + 24 * 60 * 60 * 1000)) return "secondary"; // orange-ish
        return "outline"; // blue-ish
    };

    const getBoardBgColor = (prefs: TrelloBoard["prefs"]): string => {
        switch (prefs.background) {
            case "blue":
                return "#026AA7";
            case "green":
                return "#1F845A";
            case "red":
                return "#B04632";
            case "yellow":
                return "#B35900";
            case "purple":
                return "#7965E0";
            case "pink":
                return "#CD5A91";
            case "sky":
                return "#00C2E0";
            case "lime":
                return "#67B96A";
            default:
                return "#0079BF";
        }
    };

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <div className="p-2 bg-[#026AA7] rounded-lg">
                            <Layout className="w-8 h-8 text-white" />
                        </div>
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Trello Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Project management and task tracking platform
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
                                <AvatarImage src={userProfile.avatarUrl} alt={userProfile.fullName} />
                                <AvatarFallback>{userProfile.initials}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col">
                                <span className="font-bold">{userProfile.fullName}</span>
                                <span className="text-sm text-muted-foreground">@{userProfile.username}</span>
                            </div>
                        </div>
                    )}
                </div>

                {!connected ? (
                    // Connection Required State
                    <Card>
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center justify-center space-y-6 py-8">
                                <Layout className="w-16 h-16 text-gray-400" />
                                <div className="space-y-2 text-center">
                                    <h2 className="text-2xl font-bold">Connect Trello</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Trello account to start managing boards and tasks
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-blue-600 hover:bg-blue-700"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/trello/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Trello Account
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
                                        <p className="text-sm font-medium text-muted-foreground">Boards</p>
                                        <div className="text-2xl font-bold">{totalBoards}</div>
                                        <p className="text-xs text-muted-foreground">{openBoards} open</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Cards</p>
                                        <div className="text-2xl font-bold">{totalCards}</div>
                                        <p className="text-xs text-muted-foreground">{cardsOverdue} overdue</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Due Tasks</p>
                                        <div className="text-2xl font-bold">{cardsWithDue}</div>
                                        <p className="text-xs text-muted-foreground">With deadlines</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Team Members</p>
                                        <div className="text-2xl font-bold">{totalMembers}</div>
                                        <p className="text-xs text-muted-foreground">Collaborators</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="boards">
                            <TabsList>
                                <TabsTrigger value="boards">Boards</TabsTrigger>
                                <TabsTrigger value="cards">Cards</TabsTrigger>
                                <TabsTrigger value="lists">Lists</TabsTrigger>
                                <TabsTrigger value="team">Team</TabsTrigger>
                            </TabsList>

                            {/* Boards Tab */}
                            <TabsContent value="boards" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search boards..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={() => setIsBoardOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Board
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.boards ? (
                                        <div className="flex justify-center p-8 col-span-full">
                                            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                        </div>
                                    ) : (
                                        filteredBoards.map((board) => (
                                            <Card
                                                key={board.id}
                                                className="cursor-pointer hover:shadow-md transition-all duration-200 border-2"
                                                style={{
                                                    borderColor: selectedBoard === board.id ? "#3b82f6" : "transparent",
                                                }}
                                                onClick={() => setSelectedBoard(board.id)}
                                            >
                                                <div
                                                    className="p-4 rounded-t-lg text-white"
                                                    style={{ backgroundColor: getBoardBgColor(board.prefs) }}
                                                >
                                                    <div className="flex justify-between items-start">
                                                        <h3 className="font-bold text-lg">{board.name}</h3>
                                                        <div className="flex space-x-1">
                                                            {board.pinned && (
                                                                <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-100 hover:bg-yellow-500/30">
                                                                    Pinned
                                                                </Badge>
                                                            )}
                                                            {board.starred && (
                                                                <Badge variant="secondary" className="bg-orange-500/20 text-orange-100 hover:bg-orange-500/30">
                                                                    Starred
                                                                </Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <p className="text-sm text-white/90 mt-2 line-clamp-2">
                                                        {board.desc}
                                                    </p>
                                                </div>
                                                <CardContent className="pt-4 space-y-3">
                                                    <div className="flex justify-between text-sm text-muted-foreground">
                                                        <span>Last activity: {formatDate(board.dateLastActivity)}</span>
                                                    </div>
                                                    {board.organization && (
                                                        <p className="text-xs text-muted-foreground">
                                                            Organization: {board.organization.displayName}
                                                        </p>
                                                    )}
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        className="w-full"
                                                        onClick={() => window.open(board.url, "_blank")}
                                                    >
                                                        <ExternalLink className="w-4 h-4 mr-2" />
                                                        Open in Trello
                                                    </Button>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Cards Tab */}
                            <TabsContent value="cards" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedBoard}
                                        onValueChange={(value) => {
                                            setSelectedBoard(value);
                                            setSelectedList("");
                                        }}
                                    >
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Select board" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {boards.map((board) => (
                                                <SelectItem key={board.id} value={board.id}>
                                                    {board.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <Select
                                        value={selectedList}
                                        onValueChange={setSelectedList}
                                    >
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Select list" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {lists.map((list) => (
                                                <SelectItem key={list.id} value={list.id}>
                                                    {list.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search cards..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={() => setIsCardOpen(true)}
                                        disabled={!selectedList}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Card
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {loading.cards ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                        </div>
                                    ) : selectedList ? (
                                        filteredCards.map((card) => (
                                            <Card key={card.id}>
                                                <CardContent className="p-4">
                                                    <div className="flex flex-col space-y-2">
                                                        <div className="flex justify-between items-start">
                                                            <a
                                                                href={card.url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="font-bold text-lg hover:underline"
                                                            >
                                                                {card.name}
                                                            </a>
                                                            <div className="flex space-x-2">
                                                                {card.due && (
                                                                    <Badge variant={getCardDueVariant(card.due, card.dueComplete)}>
                                                                        Due: {formatDate(card.due)}
                                                                    </Badge>
                                                                )}
                                                                {card.dueComplete && (
                                                                    <Badge variant="default" className="bg-green-600">
                                                                        Complete
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                        </div>

                                                        {card.desc && (
                                                            <p className="text-sm text-muted-foreground line-clamp-2">
                                                                {card.desc}
                                                            </p>
                                                        )}

                                                        <div className="flex items-center space-x-6 pt-2">
                                                            <div className="flex items-center space-x-1 text-muted-foreground">
                                                                <MessageSquare className="w-4 h-4" />
                                                                <span className="text-xs">{card.badges.comments}</span>
                                                            </div>
                                                            <div className="flex items-center space-x-1 text-muted-foreground">
                                                                <CheckCircle className="w-4 h-4" />
                                                                <span className="text-xs">
                                                                    {card.badges.checkItemsChecked}/{card.badges.checkItems}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center space-x-1 text-muted-foreground">
                                                                <Eye className="w-4 h-4" />
                                                                <span className="text-xs">{card.badges.attachments}</span>
                                                            </div>

                                                            {card.idMembers.length > 0 && (
                                                                <div className="flex -space-x-2">
                                                                    {card.idMembers.slice(0, 3).map((memberId) => {
                                                                        const member = members.find((m) => m.id === memberId);
                                                                        return member ? (
                                                                            <Avatar key={memberId} className="w-6 h-6 border-2 border-white">
                                                                                <AvatarImage src={member.avatarUrl50} alt={member.fullName} />
                                                                                <AvatarFallback>{member.initials}</AvatarFallback>
                                                                            </Avatar>
                                                                        ) : null;
                                                                    })}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : (
                                        <div className="text-center py-12 text-muted-foreground">
                                            Select a board and list to view cards
                                        </div>
                                    )}
                                </div>
                            </TabsContent>

                            {/* Lists Tab */}
                            <TabsContent value="lists" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedBoard}
                                        onValueChange={setSelectedBoard}
                                    >
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Select board" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {boards.map((board) => (
                                                <SelectItem key={board.id} value={board.id}>
                                                    {board.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-4">
                                    {loading.lists ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                        </div>
                                    ) : selectedBoard ? (
                                        lists.map((list) => (
                                            <Card key={list.id}>
                                                <CardContent className="p-4 flex items-center space-x-4">
                                                    <List className="w-6 h-6 text-blue-500" />
                                                    <div className="flex-1">
                                                        <h3 className="font-bold text-lg">{list.name}</h3>
                                                        <p className="text-sm text-muted-foreground">
                                                            Position: {list.pos}
                                                        </p>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : (
                                        <div className="text-center py-12 text-muted-foreground">
                                            Select a board to view lists
                                        </div>
                                    )}
                                </div>
                            </TabsContent>

                            {/* Team Tab */}
                            <TabsContent value="team" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search team members..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.members ? (
                                        <div className="flex justify-center p-8 col-span-full">
                                            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                        </div>
                                    ) : (
                                        filteredMembers.map((member) => (
                                            <Card key={member.id}>
                                                <CardContent className="p-4 flex space-x-4">
                                                    <Avatar className="w-12 h-12">
                                                        <AvatarImage src={member.avatarUrl50} alt={member.fullName} />
                                                        <AvatarFallback>{member.initials}</AvatarFallback>
                                                    </Avatar>
                                                    <div className="flex-1 space-y-1">
                                                        <h3 className="font-bold">{member.fullName}</h3>
                                                        <p className="text-sm text-muted-foreground">@{member.username}</p>
                                                        <div className="flex space-x-2 pt-1">
                                                            <Badge variant="secondary">{member.memberType}</Badge>
                                                            <Badge variant={member.confirmed ? "default" : "destructive"}>
                                                                {member.confirmed ? "Confirmed" : "Unconfirmed"}
                                                            </Badge>
                                                        </div>
                                                        {member.bio && (
                                                            <p className="text-xs text-muted-foreground pt-2 line-clamp-2">
                                                                {member.bio}
                                                            </p>
                                                        )}
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>
                        </Tabs>

                        {/* Create Card Modal */}
                        <Dialog open={isCardOpen} onOpenChange={setIsCardOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Card</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Card Title</label>
                                        <Input
                                            placeholder="Enter card title"
                                            value={cardForm.name}
                                            onChange={(e) =>
                                                setCardForm({
                                                    ...cardForm,
                                                    name: e.target.value,
                                                })
                                            }
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Card description..."
                                            value={cardForm.description}
                                            onChange={(e) =>
                                                setCardForm({
                                                    ...cardForm,
                                                    description: e.target.value,
                                                })
                                            }
                                            rows={4}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">List</label>
                                        <Select
                                            value={cardForm.list_id}
                                            onValueChange={(value) =>
                                                setCardForm({
                                                    ...cardForm,
                                                    list_id: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select a list" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {lists.map((list) => (
                                                    <SelectItem key={list.id} value={list.id}>
                                                        {list.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Due Date</label>
                                        <Input
                                            type="datetime-local"
                                            value={cardForm.due}
                                            onChange={(e) =>
                                                setCardForm({
                                                    ...cardForm,
                                                    due: e.target.value,
                                                })
                                            }
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Members</label>
                                        <Select
                                            value={cardForm.members[0] || ""}
                                            onValueChange={(value) =>
                                                setCardForm({
                                                    ...cardForm,
                                                    members: value ? [value] : [],
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Assign members" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {members.map((member) => (
                                                    <SelectItem key={member.id} value={member.id}>
                                                        {member.fullName}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsCardOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={createCard}
                                        disabled={!cardForm.name || !cardForm.list_id}
                                    >
                                        Create Card
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create Board Modal */}
                        <Dialog open={isBoardOpen} onOpenChange={setIsBoardOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Board</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Board Name</label>
                                        <Input
                                            placeholder="Enter board name"
                                            value={boardForm.name}
                                            onChange={(e) =>
                                                setBoardForm({
                                                    ...boardForm,
                                                    name: e.target.value,
                                                })
                                            }
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Board description..."
                                            value={boardForm.description}
                                            onChange={(e) =>
                                                setBoardForm({
                                                    ...boardForm,
                                                    description: e.target.value,
                                                })
                                            }
                                            rows={3}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Permission Level</label>
                                        <Select
                                            value={boardForm.permission_level}
                                            onValueChange={(value) =>
                                                setBoardForm({
                                                    ...boardForm,
                                                    permission_level: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Permission Level" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="private">Private</SelectItem>
                                                <SelectItem value="org">Organization</SelectItem>
                                                <SelectItem value="public">Public</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="flex space-x-6">
                                        <div className="flex items-center space-x-2">
                                            <Input
                                                type="checkbox"
                                                id="default_labels"
                                                className="w-4 h-4"
                                                checked={boardForm.default_labels}
                                                onChange={(e) =>
                                                    setBoardForm({
                                                        ...boardForm,
                                                        default_labels: e.target.checked,
                                                    })
                                                }
                                            />
                                            <label htmlFor="default_labels" className="text-sm font-medium leading-none">
                                                Default Labels
                                            </label>
                                        </div>

                                        <div className="flex items-center space-x-2">
                                            <Input
                                                type="checkbox"
                                                id="default_lists"
                                                className="w-4 h-4"
                                                checked={boardForm.default_lists}
                                                onChange={(e) =>
                                                    setBoardForm({
                                                        ...boardForm,
                                                        default_lists: e.target.checked,
                                                    })
                                                }
                                            />
                                            <label htmlFor="default_lists" className="text-sm font-medium leading-none">
                                                Default Lists
                                            </label>
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsBoardOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={createBoard}
                                        disabled={!boardForm.name}
                                    >
                                        Create Board
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

export default TrelloIntegration;

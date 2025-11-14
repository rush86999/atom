/**
 * Trello Integration Page
 * Complete Trello project management and task tracking integration
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  Input,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  useDisclosure,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Tag,
  TagLabel,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Avatar,
  Spinner,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  RepeatIcon,
  TimeIcon,
  StarIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ChatIcon,
  CalendarIcon,
} from "@chakra-ui/icons";

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
    checkItems: number;
    checkItemsChecked: number;
    comments: number;
    attachments: number;
    viewMemberVotes: number;
    voting: number;
    fogbugz: string;
    checkItems: number;
    checkItemsChecked: number;
    attachments: number;
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

interface TrelloChecklist {
  id: string;
  name: string;
  idCard: string;
  idBoard: string;
  pos: number;
  checkItems: Array<{
    id: string;
    name: string;
    state: "incomplete" | "complete";
    idMember: string;
    type?: string;
    pos?: number;
  }>;
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

  const {
    isOpen: isCardOpen,
    onOpen: onCardOpen,
    onClose: onCardClose,
  } = useDisclosure();
  const {
    isOpen: isBoardOpen,
    onOpen: onBoardOpen,
    onClose: onBoardClose,
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

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
        status: "error",
        duration: 3000,
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
          status: "success",
          duration: 3000,
        });
        onCardClose();
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
        status: "error",
        duration: 3000,
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
          status: "success",
          duration: 3000,
        });
        onBoardClose();
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
        status: "error",
        duration: 3000,
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

  const getCardDueColor = (due: string, dueComplete: boolean): string => {
    if (!due) return "gray";
    if (dueComplete) return "green";
    if (new Date(due) < new Date()) return "red";
    if (new Date(due) < new Date(Date.now() + 24 * 60 * 60 * 1000)) return "orange";
    return "blue";
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
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="#026AA7" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Trello Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Project management and task tracking platform
              </Text>
            </VStack>
          </HStack>

          <HStack spacing={4}>
            <Badge
              colorScheme={healthStatus === "healthy" ? "green" : "red"}
              display="flex"
              alignItems="center"
            >
              {healthStatus === "healthy" ? (
                <CheckCircleIcon mr={1} />
              ) : (
                <WarningTwoIcon mr={1} />
              )}
              {connected ? "Connected" : "Disconnected"}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={checkConnection}
            >
              Refresh Status
            </Button>
          </HStack>

          {userProfile && (
            <HStack spacing={4}>
              <Avatar src={userProfile.avatarUrl} name={userProfile.fullName} />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{userProfile.fullName}</Text>
                <Text fontSize="sm" color="gray.600">
                  @{userProfile.username}
                </Text>
              </VStack>
            </HStack>
          )}
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={SettingsIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Trello</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Trello account to start managing boards and tasks
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/trello/auth/start")
                  }
                >
                  Connect Trello Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Services Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Boards</StatLabel>
                    <StatNumber>{totalBoards}</StatNumber>
                    <StatHelpText>{openBoards} open</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Cards</StatLabel>
                    <StatNumber>{totalCards}</StatNumber>
                    <StatHelpText>{cardsOverdue} overdue</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Due Tasks</StatLabel>
                    <StatNumber>{cardsWithDue}</StatNumber>
                    <StatHelpText>With deadlines</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Team Members</StatLabel>
                    <StatNumber>{totalMembers}</StatNumber>
                    <StatHelpText>Collaborators</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Boards</Tab>
                <Tab>Cards</Tab>
                <Tab>Lists</Tab>
                <Tab>Team</Tab>
              </TabList>

              <TabPanels>
                {/* Boards Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search boards..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onBoardOpen}
                      >
                        Create Board
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.boards ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredBoards.map((board) => (
                          <Card
                            key={board.id}
                            cursor="pointer"
                            _hover={{ shadow: "md", transform: "translateY(-2px)" }}
                            transition="all 0.2s"
                            onClick={() => setSelectedBoard(board.id)}
                            borderWidth="1px"
                            borderColor={selectedBoard === board.id ? "blue.500" : borderColor}
                          >
                            <CardHeader
                              p={4}
                              style={{
                                backgroundColor: getBoardBgColor(board.prefs),
                                color: "white",
                              }}
                            >
                              <VStack align="start" spacing={2}>
                                <HStack justify="space-between" width="100%">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {board.name}
                                  </Text>
                                  <HStack spacing={1}>
                                    {board.pinned && (
                                      <Tag colorScheme="yellow" size="sm">
                                        Pinned
                                      </Tag>
                                    )}
                                    {board.starred && (
                                      <Tag colorScheme="orange" size="sm">
                                        Starred
                                      </Tag>
                                    )}
                                  </HStack>
                                </HStack>
                                <Text fontSize="sm" color="whiteAlpha.900">
                                  {board.desc}
                                </Text>
                              </VStack>
                            </CardHeader>
                            <CardBody>
                              <VStack spacing={3} align="stretch">
                                <HStack justify="space-between">
                                  <Text fontSize="sm" color="gray.500">
                                    Last activity: {formatDate(board.dateLastActivity)}
                                  </Text>
                                </HStack>
                                {board.organization && (
                                  <Text fontSize="xs" color="gray.500">
                                    Organization: {board.organization.displayName}
                                  </Text>
                                )}
                                <Link href={board.url} isExternal>
                                  <Button size="sm" variant="outline" leftIcon={<ViewIcon />}>
                                    Open in Trello
                                  </Button>
                                </Link>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Cards Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select board"
                        value={selectedBoard}
                        onChange={(e) => {
                          setSelectedBoard(e.target.value);
                          setSelectedList("");
                        }}
                        width="200px"
                      >
                        {boards.map((board) => (
                          <option key={board.id} value={board.id}>
                            {board.name}
                          </option>
                        ))}
                      </Select>
                      <Select
                        placeholder="Select list"
                        value={selectedList}
                        onChange={(e) => setSelectedList(e.target.value)}
                        width="200px"
                      >
                        {lists.map((list) => (
                          <option key={list.id} value={list.id}>
                            {list.name}
                          </option>
                        ))}
                      </Select>
                      <Input
                        placeholder="Search cards..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onCardOpen}
                        disabled={!selectedList}
                      >
                        Create Card
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.cards ? (
                        <Spinner size="xl" />
                      ) : selectedList ? (
                        filteredCards.map((card) => (
                          <Card key={card.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <VStack spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <Link href={card.url} isExternal>
                                      <Text fontWeight="bold" fontSize="lg">
                                        {card.name}
                                      </Text>
                                    </Link>
                                    <HStack>
                                      {card.due && (
                                        <Tag
                                          colorScheme={getCardDueColor(card.due, card.dueComplete)}
                                          size="sm"
                                        >
                                          Due: {formatDate(card.due)}
                                        </Tag>
                                      )}
                                      {card.dueComplete && (
                                        <Tag colorScheme="green" size="sm">
                                          Complete
                                        </Tag>
                                      )}
                                    </HStack>
                                  </HStack>
                                  
                                  {card.desc && (
                                    <Text fontSize="sm" color="gray.600">
                                      {card.desc.substring(0, 200)}
                                      {card.desc.length > 200 && "..."}
                                    </Text>
                                  )}
                                  
                                  <HStack spacing={4}>
                                    <HStack spacing={1}>
                                      <ChatIcon boxSize={4} color="gray.500" />
                                      <Text fontSize="xs">{card.badges.comments}</Text>
                                    </HStack>
                                    <HStack spacing={1}>
                                      <CheckCircleIcon boxSize={4} color="gray.500" />
                                      <Text fontSize="xs">
                                        {card.badges.checkItemsChecked}/{card.badges.checkItems}
                                      </Text>
                                    </HStack>
                                    <HStack spacing={1}>
                                      <ViewIcon boxSize={4} color="gray.500" />
                                      <Text fontSize="xs">{card.badges.attachments}</Text>
                                    </HStack>
                                  </HStack>

                                  {card.idMembers.length > 0 && (
                                    <AvatarGroup size="sm" max={3}>
                                      {card.idMembers.map((memberId) => {
                                        const member = members.find((m) => m.id === memberId);
                                        return member ? (
                                          <Avatar
                                            key={memberId}
                                            src={member.avatarUrl50}
                                            name={member.fullName}
                                            title={member.fullName}
                                          />
                                        ) : null;
                                      })}
                                    </AvatarGroup>
                                  )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a board and list to view cards
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Lists Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select board"
                        value={selectedBoard}
                        onChange={(e) => setSelectedBoard(e.target.value)}
                        width="200px"
                      >
                        {boards.map((board) => (
                          <option key={board.id} value={board.id}>
                            {board.name}
                          </option>
                        ))}
                      </Select>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.lists ? (
                        <Spinner size="xl" />
                      ) : selectedBoard ? (
                        lists.map((list) => (
                          <Card key={list.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Icon as={SettingsIcon} w={6} h={6} color="blue.500" />
                                <VStack align="start" spacing={2} flex={1}>
                                  <Text fontWeight="bold" fontSize="lg">
                                    {list.name}
                                  </Text>
                                  <Text fontSize="sm" color="gray.500">
                                    Position: {list.pos}
                                  </Text>
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a board to view lists
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Team Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search team members..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.members ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredMembers.map((member) => (
                          <Card key={member.id}>
                            <CardBody>
                              <HStack spacing={4}>
                                <Avatar
                                  src={member.avatarUrl50}
                                  name={member.fullName}
                                  size="lg"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">{member.fullName}</Text>
                                  <Text fontSize="sm" color="gray.600">
                                    @{member.username}
                                  </Text>
                                  <HStack spacing={2}>
                                    <Tag colorScheme="blue" size="sm">
                                      {member.memberType}
                                    </Tag>
                                    <Tag colorScheme={member.confirmed ? "green" : "red"} size="sm">
                                      {member.confirmed ? "Confirmed" : "Unconfirmed"}
                                    </Tag>
                                  </HStack>
                                  {member.bio && (
                                    <Text fontSize="xs" color="gray.500">
                                      {member.bio}
                                    </Text>
                                  )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Card Modal */}
            <Modal isOpen={isCardOpen} onClose={onCardClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Card</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Card Title</FormLabel>
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
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
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
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>List</FormLabel>
                      <Select
                        value={cardForm.list_id}
                        onChange={(e) =>
                          setCardForm({
                            ...cardForm,
                            list_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Select a list</option>
                        {lists.map((list) => (
                          <option key={list.id} value={list.id}>
                            {list.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Due Date</FormLabel>
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
                    </FormControl>

                    <FormControl>
                      <FormLabel>Members</FormLabel>
                      <Select
                        value={cardForm.members[0] || ""}
                        onChange={(e) =>
                          setCardForm({
                            ...cardForm,
                            members: e.target.value ? [e.target.value] : [],
                          })
                        }
                      >
                        <option value="">Assign members</option>
                        {members.map((member) => (
                          <option key={member.id} value={member.id}>
                            {member.fullName}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onCardClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createCard}
                    disabled={!cardForm.name || !cardForm.list_id}
                  >
                    Create Card
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Board Modal */}
            <Modal isOpen={isBoardOpen} onClose={onBoardClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Board</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Board Name</FormLabel>
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
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
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
                    </FormControl>

                    <FormControl>
                      <FormLabel>Permission Level</FormLabel>
                      <Select
                        value={boardForm.permission_level}
                        onChange={(e) =>
                          setBoardForm({
                            ...boardForm,
                            permission_level: e.target.value,
                          })
                        }
                      >
                        <option value="private">Private</option>
                        <option value="org">Organization</option>
                        <option value="public">Public</option>
                      </Select>
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Default Labels</FormLabel>
                        <Input
                          type="checkbox"
                          isChecked={boardForm.default_labels}
                          onChange={(e) =>
                            setBoardForm({
                              ...boardForm,
                              default_labels: e.target.checked,
                            })
                          }
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Default Lists</FormLabel>
                        <Input
                          type="checkbox"
                          isChecked={boardForm.default_lists}
                          onChange={(e) =>
                            setBoardForm({
                              ...boardForm,
                              default_lists: e.target.checked,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onBoardClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createBoard}
                    disabled={!boardForm.name}
                  >
                    Create Board
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </Box>
  );
};

export default TrelloIntegration;
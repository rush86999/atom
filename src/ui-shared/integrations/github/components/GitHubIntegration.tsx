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
  Progress,
  Divider,
  useColorModeValue,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Input,
  Select,
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
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Alert,
  AlertIcon,
  Spinner,
  Flex,
  Avatar,
  Tag,
  Switch,
  Code,
} from "@chakra-ui/react";
import {
  CheckCircleIcon,
  WarningTwoIcon,
  TimeIcon,
  ArrowForwardIcon,
  PlusSquareIcon,
  StarIcon,
  ForkIcon,
  CodeIcon,
  GitPullRequestIcon,
  IssueIcon,
  PersonIcon,
  SettingsIcon,
  ChevronDownIcon,
  SearchIcon,
  ChevronUpIcon,
} from "@chakra-ui/icons";

interface GitHubRepository {
  id: string;
  name: string;
  full_name: string;
  description: string;
  html_url: string;
  language: string;
  stargazers_count: number;
  forks_count: number;
  open_issues_count: number;
  updated_at: string;
  private: boolean;
  owner: {
    login: string;
    avatar_url: string;
  };
}

interface GitHubIssue {
  id: string;
  number: number;
  title: string;
  body: string;
  state: "open" | "closed";
  html_url: string;
  created_at: string;
  updated_at: string;
  user: {
    login: string;
    avatar_url: string;
  };
  labels: Array<{
    name: string;
    color: string;
  }>;
  assignee?: {
    login: string;
    avatar_url: string;
  };
}

interface GitHubPullRequest {
  id: string;
  number: number;
  title: string;
  body: string;
  state: "open" | "closed" | "merged";
  html_url: string;
  created_at: string;
  updated_at: string;
  user: {
    login: string;
    avatar_url: string;
  };
  base: {
    ref: string;
  };
  head: {
    ref: string;
  };
  mergeable: boolean;
  review_comments: number;
  additions: number;
  deletions: number;
}

interface GitHubUser {
  id: string;
  login: string;
  name: string;
  avatar_url: string;
  html_url: string;
  public_repos: number;
  followers: number;
  following: number;
  created_at: string;
}

interface GitHubAnalytics {
  totalRepositories: number;
  totalStars: number;
  totalForks: number;
  totalIssues: number;
  totalPullRequests: number;
  activeContributors: number;
  repositoryGrowth: number;
  starGrowth: number;
}

const GitHubIntegration: React.FC = () => {
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [pullRequests, setPullRequests] = useState<GitHubPullRequest[]>([]);
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [analytics, setAnalytics] = useState<GitHubAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);
  const [isCreateRepoOpen, setIsCreateRepoOpen] = useState(false);
  const [isCreateIssueOpen, setIsCreateIssueOpen] = useState(false);
  const [isCreatePROpen, setIsCreatePROpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [languageFilter, setLanguageFilter] = useState("all");
  const [newRepoName, setNewRepoName] = useState("");
  const [newRepoDescription, setNewRepoDescription] = useState("");
  const [newIssueTitle, setNewIssueTitle] = useState("");
  const [newIssueBody, setNewIssueBody] = useState("");
  const [selectedRepo, setSelectedRepo] = useState("");

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Mock data for demonstration
  const mockRepositories: GitHubRepository[] = [
    {
      id: "1",
      name: "atom-platform",
      full_name: "atom/atom-platform",
      description: "Main ATOM platform repository",
      html_url: "https://github.com/atom/atom-platform",
      language: "TypeScript",
      stargazers_count: 245,
      forks_count: 32,
      open_issues_count: 12,
      updated_at: "2024-01-15T10:30:00Z",
      private: false,
      owner: {
        login: "atom",
        avatar_url: "https://github.com/atom.png",
      },
    },
    {
      id: "2",
      name: "backend-services",
      full_name: "atom/backend-services",
      description: "Backend services for ATOM platform",
      html_url: "https://github.com/atom/backend-services",
      language: "Python",
      stargazers_count: 89,
      forks_count: 15,
      open_issues_count: 5,
      updated_at: "2024-01-14T14:20:00Z",
      private: false,
      owner: {
        login: "atom",
        avatar_url: "https://github.com/atom.png",
      },
    },
    {
      id: "3",
      name: "mobile-app",
      full_name: "atom/mobile-app",
      description: "Mobile application for ATOM platform",
      html_url: "https://github.com/atom/mobile-app",
      language: "React Native",
      stargazers_count: 67,
      forks_count: 8,
      open_issues_count: 3,
      updated_at: "2024-01-13T09:15:00Z",
      private: true,
      owner: {
        login: "atom",
        avatar_url: "https://github.com/atom.png",
      },
    },
  ];

  const mockIssues: GitHubIssue[] = [
    {
      id: "1",
      number: 123,
      title: "Fix authentication bug",
      body: "There is an issue with the authentication flow...",
      state: "open",
      html_url: "https://github.com/atom/atom-platform/issues/123",
      created_at: "2024-01-15T10:30:00Z",
      updated_at: "2024-01-15T10:30:00Z",
      user: {
        login: "developer1",
        avatar_url: "https://github.com/developer1.png",
      },
      labels: [
        { name: "bug", color: "d73a4a" },
        { name: "high-priority", color: "b60205" },
      ],
    },
    {
      id: "2",
      number: 122,
      title: "Add new integration feature",
      body: "Implement new integration capabilities...",
      state: "open",
      html_url: "https://github.com/atom/atom-platform/issues/122",
      created_at: "2024-01-14T14:20:00Z",
      updated_at: "2024-01-14T14:20:00Z",
      user: {
        login: "developer2",
        avatar_url: "https://github.com/developer2.png",
      },
      labels: [
        { name: "enhancement", color: "a2eeef" },
        { name: "feature", color: "0075ca" },
      ],
    },
  ];

  const mockPullRequests: GitHubPullRequest[] = [
    {
      id: "1",
      number: 45,
      title: "Refactor authentication service",
      body: "This PR refactors the authentication service for better performance...",
      state: "open",
      html_url: "https://github.com/atom/atom-platform/pull/45",
      created_at: "2024-01-15T10:30:00Z",
      updated_at: "2024-01-15T10:30:00Z",
      user: {
        login: "developer3",
        avatar_url: "https://github.com/developer3.png",
      },
      base: { ref: "main" },
      head: { ref: "feature/auth-refactor" },
      mergeable: true,
      review_comments: 3,
      additions: 245,
      deletions: 89,
    },
    {
      id: "2",
      number: 44,
      title: "Add Stripe integration",
      body: "This PR adds Stripe payment processing integration...",
      state: "merged",
      html_url: "https://github.com/atom/atom-platform/pull/44",
      created_at: "2024-01-14T14:20:00Z",
      updated_at: "2024-01-14T14:20:00Z",
      user: {
        login: "developer4",
        avatar_url: "https://github.com/developer4.png",
      },
      base: { ref: "main" },
      head: { ref: "feature/stripe-integration" },
      mergeable: null,
      review_comments: 8,
      additions: 567,
      deletions: 123,
    },
  ];

  const mockUser: GitHubUser = {
    id: "1",
    login: "atom",
    name: "ATOM Platform",
    avatar_url: "https://github.com/atom.png",
    html_url: "https://github.com/atom",
    public_repos: 15,
    followers: 245,
    following: 32,
    created_at: "2023-01-01T00:00:00Z",
  };

  const mockAnalytics: GitHubAnalytics = {
    totalRepositories: 15,
    totalStars: 401,
    totalForks: 55,
    totalIssues: 20,
    totalPullRequests: 45,
    activeContributors: 12,
    repositoryGrowth: 25.5,
    starGrowth: 18.3,
  };

  const loadGitHubData = async () => {
    setLoading(true);
    try {
      // In a real implementation, these would be API calls
      await new Promise((resolve) => setTimeout(resolve, 1000));

      setRepositories(mockRepositories);
      setIssues(mockIssues);
      setPullRequests(mockPullRequests);
      setUser(mockUser);
      setAnalytics(mockAnalytics);

      toast({
        title: "GitHub data loaded",
        status: "success",
        duration: 2000,
      });
    } catch (error) {
      toast({
        title: "Failed to load GitHub data",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading(false);
    }
  };

  const createRepository = async (name: string, description: string) => {
    try {
      // In a real implementation, this would be an API call
      const newRepo: GitHubRepository = {
        id: Math.random().toString(36).substr(2, 9),
        name,
        full_name: `atom/${name}`,
        description,
        html_url: `https://github.com/atom/${name}`,
        language: "",
        stargazers_count: 0,
        forks_count: 0,
        open_issues_count: 0,
        updated_at: new Date().toISOString(),
        private: false,
        owner: {
          login: "atom",
          avatar_url: "https://github.com/atom.png",
        },
      };

      setRepositories((prev) => [newRepo, ...prev]);
      setIsCreateRepoOpen(false);
      setNewRepoName("");
      setNewRepoDescription("");

      toast({
        title: "Repository created successfully",
        variant: "default",
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: "Failed to create repository",
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  const createIssue = async (title: string, body: string) => {
    try {
      // In a real implementation, this would be an API call
      const newIssue: GitHubIssue = {
        id: Math.random().toString(36).substr(2, 9),
        number: Math.floor(Math.random() * 1000),
        title,
        body,
        state: "open",
        html_url: `https://github.com/atom/atom-platform/issues/${Math.floor(Math.random() * 1000)}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        user: {
          login: "current-user",
          avatar_url: "https://github.com/current-user.png",
        },
        labels: [],
      };

      setIssues((prev) => [newIssue, ...prev]);
      setIsCreateIssueOpen(false);
      setNewIssueTitle("");
      setNewIssueBody("");

      toast({
        title: "Issue created successfully",
        status: "success",
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: "Failed to create issue",
        status: "error",
        duration: 3000,
      });
    }
  };

  const getStatusColor = (state: string) => {
    switch (state) {
      case "open":
        return "green";
      case "closed":
        return "red";
      case "merged":
        return "purple";
      default:
        return "gray";
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const filteredRepositories = repositories.filter((repo) => {
    const matchesSearch =
      repo.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      repo.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesLanguage =
      languageFilter === "all" || repo.language === languageFilter;
    return matchesSearch && matchesLanguage;
  });

  const languages = Array.from(
    new Set(repositories.map((repo) => repo.language).filter(Boolean)),
  );

  useEffect(() => {
    loadGitHubData();
  }, []);

  if (loading && repositories.length === 0) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minH="400px"
      >
        <VStack spacing={4}>
          <Spinner size="xl" color="blue.500" />
          <Text>Loading GitHub integration...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={2}>
          <Heading size="2xl">GitHub Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete repository and project management
          </Text>
        </VStack>

        {/* Quick Stats */}
        {analytics && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Repositories</StatLabel>
                  <StatNumber>{analytics.totalRepositories}</StatNumber>
                  <StatHelpText>
                    <StatArrow
                      type={
                        analytics.repositoryGrowth > 0 ? "increase" : "decrease"
                      }
                    />
                    {Math.abs(analytics.repositoryGrowth)}%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Stars</StatLabel>
                  <StatNumber>{analytics.totalStars}</StatNumber>
                  <StatHelpText>
                    <StatArrow
                      type={analytics.starGrowth > 0 ? "increase" : "decrease"}
                    />
                    {Math.abs(analytics.starGrowth)}%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Active Contributors</StatLabel>
                  <StatNumber>{analytics.activeContributors}</StatNumber>
                  <StatHelpText>Team members</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Open Issues</StatLabel>
                  <StatNumber>{analytics.totalIssues}</StatNumber>
                  <StatHelpText>Across all repositories</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* User Profile */}
        {user && (
          <Card>
            <CardBody>
              <HStack spacing={4}>
                <Avatar size="lg" src={user.avatar_url} />
                <VStack align="start" spacing={1}>
                  <Heading size="md">{user.name}</Heading>
                  <Text color="gray.600">@{user.login}</Text>
                  <HStack spacing={4}>
                    <Text fontSize="sm">
                      <strong>{user.public_repos}</strong> repositories
                    </Text>
                    <Text fontSize="sm">
                      <strong>{user.followers}</strong> followers
                    </Text>
                    <Text fontSize="sm">
                      <strong>{user.following}</strong> following
                    </Text>
                  </HStack>
                </VStack>
              </HStack>
            </CardBody>
          </Card>
        )}

        {/* Main Content Tabs */}
        <Card>
          <CardHeader>
            <Tabs variant="enclosed" onChange={setActiveTab}>
              <TabList>
                <Tab>Repositories</Tab>
                <Tab>Issues</Tab>
                <Tab>Pull Requests</Tab>
                <Tab>Analytics</Tab>
              </TabList>
              <TabPanels>
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search repositories..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        leftIcon={<SearchIcon />}
                      />
                      <Select
                        value={languageFilter}
                        onChange={(e) => setLanguageFilter(e.target.value)}
                        minW="150px"
                      >
                        <option value="all">All Languages</option>
                        {languages.map((lang) => (
                          <option key={lang} value={lang}>
                            {lang}
                          </option>
                        ))}
                      </Select>
                      <Button
                        colorScheme="blue"
                        leftIcon={<PlusSquareIcon />}
                        onClick={() => setIsCreateRepoOpen(true)}
                      >
                        New Repository
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {filteredRepositories.map((repo) => (
                        <Card key={repo.id} variant="outline">
                          <CardBody>
                            <VStack spacing={4} align="start">
                              <HStack spacing={3} w="full">
                                <Avatar size="sm" src={repo.owner.avatar_url} />
                                <VStack align="start" spacing={0}>
                                  <Heading size="md">{repo.name}</Heading>
                                  <Text color="gray.600" fontSize="sm">
                                    {repo.owner.login}
                                  </Text>
                                </VStack>
                                {repo.private && (
                                  <Badge colorScheme="red" ml="auto">
                                    Private
                                  </Badge>
                                )}
                              </HStack>

                              {repo.description && (
                                <Text color="gray.700">{repo.description}</Text>
                              )}

                              {repo.language && (
                                <Badge colorScheme="blue">
                                  {repo.language}
                                </Badge>
                              )}

                              <HStack spacing={4} w="full">
                                <HStack spacing={1}>
                                  <StarIcon color="yellow.500" />
                                  <Text fontSize="sm">
                                    {repo.stargazers_count}
                                  </Text>
                                </HStack>
                                <HStack spacing={1}>
                                  <ForkIcon />
                                  <Text fontSize="sm">{repo.forks_count}</Text>
                                </HStack>
                                <HStack spacing={1}>
                                  <IssueIcon />
                                  <Text fontSize="sm">
                                    {repo.open_issues_count}
                                  </Text>
                                </HStack>
                              </HStack>

                              <Text fontSize="sm" color="gray.500">
                                Updated {formatDate(repo.updated_at)}
                              </Text>

                              <Button
                                size="sm"
                                colorScheme="blue"
                                variant="outline"
                                onClick={() =>
                                  window.open(repo.html_url, "_blank")
                                }
                                w="full"
                              >
                                View Repository
                              </Button>
                            </VStack>
                          </CardBody>
                        </Card>
                      ))}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search issues..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        leftIcon={<SearchIcon />}
                      />
                      <Button
                        colorScheme="blue"
                        leftIcon={<PlusSquareIcon />}
                        onClick={() => setIsCreateIssueOpen(true)}
                      >
                        New Issue
                      </Button>
                    </HStack>

                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Issue</Th>
                          <Th>Status</Th>
                          <Th>Created</Th>
                          <Th>Assignee</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {issues.map((issue) => (
                          <Tr key={issue.id}>
                            <Td>
                              <VStack align="start" spacing={1}>
                                <Text fontWeight="medium">{issue.title}</Text>
                                <Text
                                  fontSize="sm"
                                  color="gray.600"
                                  noOfLines={2}
                                >
                                  {issue.body}
                                </Text>
                                <HStack spacing={2}>
                                  {issue.labels.map((label) => (
                                    <Badge
                                      key={label.name}
                                      colorScheme="gray"
                                      bg={`#${label.color}`}
                                      color="white"
                                    >
                                      {label.name}
                                    </Badge>
                                  ))}
                                </HStack>
                              </VStack>
                            </Td>
                            <Td>
                              <Badge
                                colorScheme={
                                  issue.state === "open" ? "green" : "red"
                                }
                              >
                                {issue.state}
                              </Badge>
                            </Td>
                            <Td>{formatDate(issue.created_at)}</Td>
                            <Td>
                              {issue.assignee ? (
                                <HStack spacing={2}>
                                  <Avatar
                                    size="xs"
                                    src={issue.assignee.avatar_url}
                                  />
                                  <Text fontSize="sm">
                                    {issue.assignee.login}
                                  </Text>
                                </HStack>
                              ) : (
                                <Text color="gray.500">Unassigned</Text>
                              )}
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </VStack>
                </TabPanel>

                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Pull Request</Th>
                          <Th>Status</Th>
                          <Th>Branch</Th>
                          <Th>Changes</Th>
                          <Th>Created</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {pullRequests.map((pr) => (
                          <Tr key={pr.id}>
                            <Td>
                              <VStack align="start" spacing={1}>
                                <Text fontWeight="medium">{pr.title}</Text>
                                <Text
                                  fontSize="sm"
                                  color="gray.600"
                                  noOfLines={2}
                                >
                                  {pr.body}
                                </Text>
                              </VStack>
                            </Td>
                            <Td>
                              <Badge colorScheme={getStatusColor(pr.state)}>
                                {pr.state}
                              </Badge>
                            </Td>
                            <Td>
                              <Code fontSize="sm">
                                {pr.head.ref} → {pr.base.ref}
                              </Code>
                            </Td>
                            <Td>
                              <HStack spacing={2}>
                                <Badge colorScheme="green">
                                  +{pr.additions}
                                </Badge>
                                <Badge colorScheme="red">-{pr.deletions}</Badge>
                              </HStack>
                            </Td>
                            <Td>{formatDate(pr.created_at)}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </VStack>
                </TabPanel>

                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Heading size="lg">Repository Analytics</Heading>
                    <Text color="gray.600">
                      Detailed analytics and insights for your GitHub
                      repositories
                    </Text>
                    {/* Analytics content would go here */}
                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="center">
                          <Text fontSize="lg" fontWeight="medium">
                            Analytics Dashboard
                          </Text>
                          <Text color="gray.600" textAlign="center">
                            Repository analytics and insights will be displayed
                            here. This feature is currently under development.
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </CardHeader>
        </Card>

        {/* Create Repository Modal */}
        <Modal
          isOpen={isCreateRepoOpen}
          onClose={() => setIsCreateRepoOpen(false)}
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Repository</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Repository Name</FormLabel>
                  <Input
                    value={newRepoName}
                    onChange={(e) => setNewRepoName(e.target.value)}
                    placeholder="my-new-repository"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={newRepoDescription}
                    onChange={(e) => setNewRepoDescription(e.target.value)}
                    placeholder="Repository description..."
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                mr={3}
                onClick={() => setIsCreateRepoOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={() =>
                  createRepository(newRepoName, newRepoDescription)
                }
                isDisabled={!newRepoName}
              >
                Create Repository
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Issue Modal */}
        <Modal
          isOpen={isCreateIssueOpen}
          onClose={() => setIsCreateIssueOpen(false)}
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Issue</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Issue Title</FormLabel>
                  <Input
                    value={newIssueTitle}
                    onChange={(e) => setNewIssueTitle(e.target.value)}
                    placeholder="Issue title..."
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={newIssueBody}
                    onChange={(e) => setNewIssueBody(e.target.value)}
                    placeholder="Issue description..."
                    rows={6}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                mr={3}
                onClick={() => setIsCreateIssueOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={() => createIssue(newIssueTitle, newIssueBody)}
                isDisabled={!newIssueTitle}
              >
                Create Issue
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default GitHubIntegration;

/**
 * GitHub Integration Page
 * Complete GitHub repository and project management integration
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
  AvatarGroup,
  Link,
  Spinner,
  Code,
} from "@chakra-ui/react";
import {
  TimeIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  StarIcon,
  ExternalLinkIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ChatIcon,
} from "@chakra-ui/icons";

interface GitHubRepository {
  id: number;
  name: string;
  full_name: string;
  description: string;
  private: boolean;
  fork: boolean;
  html_url: string;
  clone_url: string;
  ssh_url: string;
  language: string;
  languages_url: string;
  stargazers_count: number;
  watchers_count: number;
  forks_count: number;
  open_issues_count: number;
  size: number;
  default_branch: string;
  created_at: string;
  updated_at: string;
  pushed_at: string;
  owner: {
    login: string;
    id: number;
    avatar_url: string;
    type: string;
  };
}

interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  body: string;
  state: "open" | "closed";
  locked: boolean;
  comments: number;
  created_at: string;
  updated_at: string;
  closed_at: string;
  user: {
    login: string;
    id: number;
    avatar_url: string;
  };
  assignee?: {
    login: string;
    id: number;
    avatar_url: string;
  };
  labels: Array<{
    id: number;
    name: string;
    color: string;
  }>;
  milestone?: {
    id: number;
    title: string;
    state: string;
  };
  pull_request?: {
    url: string;
    html_url: string;
  };
}

interface GitHubUser {
  id: number;
  login: string;
  name: string;
  email?: string;
  bio?: string;
  company?: string;
  location?: string;
  blog?: string;
  avatar_url: string;
  html_url: string;
  public_repos: number;
  followers: number;
  following: number;
  created_at: string;
  updated_at: string;
  type: "User" | "Bot";
}

const GitHubIntegration: React.FC = () => {
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [userProfile, setUserProfile] = useState<GitHubUser | null>(null);
  const [loading, setLoading] = useState({
    repositories: false,
    issues: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRepository, setSelectedRepository] = useState("");

  const {
    isOpen: isIssueOpen,
    onOpen: onIssueOpen,
    onClose: onIssueClose,
  } = useDisclosure();
  const {
    isOpen: isRepoOpen,
    onOpen: onRepoOpen,
    onClose: onRepoClose,
  } = useDisclosure();
  
  const [newIssue, setNewIssue] = useState({
    title: "",
    body: "",
    repository: "",
    labels: [] as string[],
  });
  
  const [newRepository, setNewRepository] = useState({
    name: "",
    description: "",
    private: false,
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/github/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
        loadRepositories();
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

  // Load GitHub data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/github/profile", {
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

  const loadRepositories = async () => {
    setLoading((prev) => ({ ...prev, repositories: true }));
    try {
      const response = await fetch("/api/integrations/github/repositories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
          type: "owner",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setRepositories(data.data?.repositories || []);
      }
    } catch (error) {
      console.error("Failed to load repositories:", error);
      toast({
        title: "Error",
        description: "Failed to load repositories from GitHub",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, repositories: false }));
    }
  };

  const loadIssues = async (repoName?: string) => {
    setLoading((prev) => ({ ...prev, issues: true }));
    try {
      const response = await fetch("/api/integrations/github/issues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          repository: repoName || selectedRepository,
          state: "open",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setIssues(data.data?.issues || []);
      }
    } catch (error) {
      console.error("Failed to load issues:", error);
    } finally {
      setLoading((prev) => ({ ...prev, issues: false }));
    }
  };

  const createIssue = async () => {
    if (!newIssue.title || !newIssue.repository) return;

    try {
      const response = await fetch("/api/integrations/github/issues/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          repository: newIssue.repository,
          title: newIssue.title,
          body: newIssue.body,
          labels: newIssue.labels,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Issue created successfully",
          status: "success",
          duration: 3000,
        });
        onIssueClose();
        setNewIssue({ title: "", body: "", repository: "", labels: [] });
        if (newIssue.repository === selectedRepository) {
          loadIssues(selectedRepository);
        }
      }
    } catch (error) {
      console.error("Failed to create issue:", error);
      toast({
        title: "Error",
        description: "Failed to create issue",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredRepositories = repositories.filter(
    (repo) =>
      repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      repo.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      repo.language?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredIssues = issues.filter(
    (issue) =>
      issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.body?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.user.login.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalRepos = repositories.length;
  const publicRepos = repositories.filter(repo => !repo.private).length;
  const privateRepos = repositories.filter(repo => repo.private).length;
  const totalStars = repositories.reduce((sum, repo) => sum + repo.stargazers_count, 0);
  const totalForks = repositories.reduce((sum, repo) => sum + repo.forks_count, 0);
  const openIssues = issues.filter(issue => issue.state === "open").length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadRepositories();
    }
  }, [connected]);

  useEffect(() => {
    if (selectedRepository) {
      loadIssues(selectedRepository);
    }
  }, [selectedRepository]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getLanguageColor = (language: string): string => {
    const colors: { [key: string]: string } = {
      JavaScript: "yellow",
      TypeScript: "blue",
      Python: "green",
      Java: "orange",
      Go: "cyan",
      Rust: "orange",
      Ruby: "red",
      PHP: "purple",
      "C++": "blue",
      C: "gray",
      Shell: "gray",
      HTML: "orange",
      CSS: "blue",
    };
    return colors[language] || "gray";
  };

  const getStateColor = (state: string): string => {
    return state === "open" ? "green" : "gray";
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={ViewIcon} w={8} h={8} color="black" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">GitHub Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Complete repository and project management platform
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
              <Avatar src={userProfile.avatar_url} name={userProfile.login} />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{userProfile.name || userProfile.login}</Text>
                <Text fontSize="sm" color="gray.600">@{userProfile.login}</Text>
              </VStack>
            </HStack>
          )}
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={ViewIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect GitHub</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your GitHub account to start managing repositories and projects
                  </Text>
                </VStack>
                <Button
                  colorScheme="black"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/github/auth/start")
                  }
                >
                  Connect GitHub Account
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
                    <StatLabel>Repositories</StatLabel>
                    <StatNumber>{totalRepos}</StatNumber>
                    <StatHelpText>{privateRepos} private, {publicRepos} public</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Stars</StatLabel>
                    <StatNumber>{totalStars}</StatNumber>
                    <StatHelpText>Across all repos</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Open Issues</StatLabel>
                    <StatNumber>{openIssues}</StatNumber>
                    <StatHelpText>Need attention</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Forks</StatLabel>
                    <StatNumber>{totalForks}</StatNumber>
                    <StatHelpText>Community contributions</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Repositories</Tab>
                <Tab>Issues</Tab>
                <Tab>Profile</Tab>
              </TabList>

              <TabPanels>
                {/* Repositories Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search repositories..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="black"
                        leftIcon={<AddIcon />}
                        onClick={onRepoOpen}
                      >
                        New Repository
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.repositories ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredRepositories.map((repo) => (
                          <Card
                            key={repo.id}
                            cursor="pointer"
                            _hover={{ shadow: "md", transform: "translateY(-2px)" }}
                            transition="all 0.2s"
                            onClick={() => setSelectedRepository(repo.full_name)}
                            borderWidth="1px"
                            borderColor={selectedRepository === repo.full_name ? "blue.500" : borderColor}
                          >
                            <CardHeader>
                              <VStack align="start" spacing={2}>
                                <HStack justify="space-between" width="100%">
                                  <Text fontWeight="bold" fontSize="lg">
                                    {repo.name}
                                  </Text>
                                  <HStack spacing={1}>
                                    {repo.private && (
                                      <Tag colorScheme="gray" size="sm">
                                        Private
                                      </Tag>
                                    )}
                                    {repo.fork && (
                                      <Tag colorScheme="blue" size="sm">
                                        Fork
                                      </Tag>
                                    )}
                                  </HStack>
                                </HStack>
                                <Text fontSize="sm" color="gray.600">
                                  {repo.description}
                                </Text>
                              </VStack>
                            </CardHeader>
                            <CardBody>
                              <VStack spacing={3} align="stretch">
                                {repo.language && (
                                  <Tag colorScheme={getLanguageColor(repo.language)}>
                                    {repo.language}
                                  </Tag>
                                )}
                                <HStack justify="space-between">
                                  <HStack spacing={4}>
                                    <HStack>
                                      <StarIcon boxSize={4} color="yellow.500" />
                                      <Text fontSize="sm">{repo.stargazers_count}</Text>
                                    </HStack>
                                    <HStack>
                                      <Icon as={ViewIcon} boxSize={4} color="blue.500" />
                                      <Text fontSize="sm">{repo.watchers_count}</Text>
                                    </HStack>
                                  </HStack>
                                  <Link href={repo.html_url} isExternal>
                                    <ExternalLinkIcon />
                                  </Link>
                                </HStack>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Issues Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Select repository"
                        value={selectedRepository}
                        onChange={(e) => setSelectedRepository(e.target.value)}
                        width="300px"
                      >
                        {repositories.map((repo) => (
                          <option key={repo.id} value={repo.full_name}>
                            {repo.full_name}
                          </option>
                        ))}
                      </Select>
                      <Input
                        placeholder="Search issues..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="black"
                        leftIcon={<AddIcon />}
                        onClick={onIssueOpen}
                        disabled={!selectedRepository}
                      >
                        Create Issue
                      </Button>
                    </HStack>

                    <VStack spacing={4} align="stretch">
                      {loading.issues ? (
                        <Spinner size="xl" />
                      ) : selectedRepository ? (
                        filteredIssues.map((issue) => (
                          <Card key={issue.id}>
                            <CardBody>
                              <HStack spacing={4} align="start">
                                <Avatar
                                  src={issue.user.avatar_url}
                                  name={issue.user.login}
                                  size="sm"
                                />
                                <VStack align="start" spacing={2} flex={1}>
                                  <HStack justify="space-between" width="100%">
                                    <HStack>
                                      <Link href={issue.html_url} isExternal>
                                        <Text fontWeight="bold">
                                          #{issue.number} {issue.title}
                                        </Text>
                                      </Link>
                                      <Tag colorScheme={getStateColor(issue.state)} size="sm">
                                        {issue.state}
                                      </Tag>
                                    </HStack>
                                    <Text fontSize="xs" color="gray.500">
                                      {formatDate(issue.created_at)}
                                    </Text>
                                  </HStack>
                                  <Text fontSize="sm" color="gray.600">
                                    {issue.body?.substring(0, 200)}
                                    {issue.body && issue.body.length > 200 && "..."}
                                  </Text>
                                  <HStack spacing={4}>
                                    {issue.labels.map((label) => (
                                      <Tag
                                        key={label.id}
                                        size="sm"
                                        backgroundColor={`#${label.color}`}
                                      >
                                        {label.name}
                                      </Tag>
                                    ))}
                                    <HStack spacing={1}>
                                      <ChatIcon boxSize={4} color="gray.500" />
                                      <Text fontSize="xs">{issue.comments}</Text>
                                    </HStack>
                                  </HStack>
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      ) : (
                        <Text color="gray.500" textAlign="center" py={8}>
                          Select a repository to view issues
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>

                {/* Profile Tab */}
                <TabPanel>
                  <Card>
                    <CardBody>
                      {userProfile ? (
                        <VStack spacing={6} align="stretch">
                          <HStack spacing={6}>
                            <Avatar
                              src={userProfile.avatar_url}
                              name={userProfile.login}
                              size="2xl"
                            />
                            <VStack align="start" spacing={2}>
                              <Heading size="lg">
                                {userProfile.name || userProfile.login}
                              </Heading>
                              <Text color="gray.600">@{userProfile.login}</Text>
                              {userProfile.bio && (
                                <Text>{userProfile.bio}</Text>
                              )}
                              <HStack spacing={4}>
                                <Link href={userProfile.html_url} isExternal>
                                  <Button
                                    size="sm"
                                    leftIcon={<ExternalLinkIcon />}
                                  >
                                    View Profile
                                  </Button>
                                </Link>
                              </HStack>
                            </VStack>
                          </HStack>

                          <Divider />

                          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
                            <Stat>
                              <StatLabel>Public Repositories</StatLabel>
                              <StatNumber>{userProfile.public_repos}</StatNumber>
                            </Stat>
                            <Stat>
                              <StatLabel>Followers</StatLabel>
                              <StatNumber>{userProfile.followers}</StatNumber>
                            </Stat>
                            <Stat>
                              <StatLabel>Following</StatLabel>
                              <StatNumber>{userProfile.following}</StatNumber>
                            </Stat>
                          </SimpleGrid>

                          <Divider />

                          <VStack align="start" spacing={2}>
                            <Text fontWeight="bold">Account Details</Text>
                            {userProfile.company && (
                              <Text>Company: {userProfile.company}</Text>
                            )}
                            {userProfile.location && (
                              <Text>Location: {userProfile.location}</Text>
                            )}
                            {userProfile.blog && (
                              <Text>Website: {userProfile.blog}</Text>
                            )}
                            {userProfile.email && (
                              <Text>Email: {userProfile.email}</Text>
                            )}
                            <Text>Account Type: {userProfile.type}</Text>
                            <Text>
                              Member Since: {formatDate(userProfile.created_at)}
                            </Text>
                          </VStack>
                        </VStack>
                      ) : (
                        <Text color="gray.500">Loading profile information...</Text>
                      )}
                    </CardBody>
                  </Card>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Issue Modal */}
            <Modal isOpen={isIssueOpen} onClose={onIssueClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Issue</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Repository</FormLabel>
                      <Select
                        value={newIssue.repository}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            repository: e.target.value,
                          })
                        }
                      >
                        <option value="">Select a repository</option>
                        {repositories.map((repo) => (
                          <option key={repo.id} value={repo.full_name}>
                            {repo.full_name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Title</FormLabel>
                      <Input
                        placeholder="Issue title"
                        value={newIssue.title}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            title: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Describe the issue..."
                        value={newIssue.body}
                        onChange={(e) =>
                          setNewIssue({
                            ...newIssue,
                            body: e.target.value,
                          })
                        }
                        rows={6}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onIssueClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="black"
                    onClick={createIssue}
                    disabled={!newIssue.title || !newIssue.repository}
                  >
                    Create Issue
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

export default GitHubIntegration;
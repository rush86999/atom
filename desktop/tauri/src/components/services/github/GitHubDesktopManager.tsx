/**
 * GitHub Desktop Manager Component
 * Following Outlook pattern for consistency
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Button,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  SimpleGrid,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Divider,
  Alert,
  AlertIcon,
  useToast,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Tooltip,
  Input,
  Select,
  Textarea,
  FormControl,
  FormLabel,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Avatar,
  AvatarBadge,
  Spinner,
  Tag,
  TagLabel,
  TagLeftIcon,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Switch
} from '@chakra-ui/react';
import {
  FiGithub,
  FiCheck,
  FiX,
  FiPlus,
  FiSearch,
  FiFilter,
  FiRefresh,
  FiSettings,
  FiUser,
  FiRepo,
  FiGitPullRequest,
  FiGitBranch,
  FiIssue,
  FiActivity,
  FiLink,
  FiEdit3,
  FiTrash2,
  FiStar,
  FiFork,
  FiMoreVertical,
  FiExternalLink,
  FiGitMerge,
  FiGitCommit
} from 'react-icons/fi';
import { invoke } from '@tauri-apps/api/tauri';
import { EventBus } from '../../utils/EventBus';
import { Logger } from '../../utils/Logger';

interface GitHubUserInfo {
  id: number;
  login: string;
  name?: string;
  email?: string;
  avatar_url?: string;
  company?: string;
  location?: string;
  bio?: string;
  public_repos: number;
  followers: number;
  following: number;
  created_at?: string;
  updated_at?: string;
  html_url: string;
  type: string;
}

interface GitHubRepository {
  id: number;
  name: string;
  full_name: string;
  description?: string;
  private: boolean;
  fork: boolean;
  html_url: string;
  clone_url: string;
  ssh_url: string;
  default_branch: string;
  language?: string;
  stargazers_count: number;
  watchers_count: number;
  forks_count: number;
  open_issues_count: number;
  created_at: string;
  updated_at: string;
  pushed_at: string;
  size: number;
}

interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: 'open' | 'closed';
  locked: boolean;
  user: GitHubUserInfo;
  assignees: GitHubUserInfo[];
  labels: GitHubLabel[];
  milestone?: GitHubMilestone;
  comments: number;
  created_at: string;
  updated_at: string;
  closed_at?: string;
  html_url: string;
  repository_url: string;
}

interface GitHubPullRequest {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: 'open' | 'closed' | 'merged';
  locked: boolean;
  user: GitHubUserInfo;
  assignees: GitHubUserInfo[];
  requested_reviewers: GitHubUserInfo[];
  labels: GitHubLabel[];
  milestone?: GitHubMilestone;
  comments: number;
  review_comments: number;
  commits: number;
  additions: number;
  deletions: number;
  changed_files: number;
  created_at: string;
  updated_at: string;
  closed_at?: string;
  merged_at?: string;
  mergeable?: boolean;
  html_url: string;
  diff_url?: string;
  repository_url: string;
  head: GitHubPullRequestBranch;
  base: GitHubPullRequestBranch;
}

interface GitHubPullRequestBranch {
  label: string;
  ref_field: string;
  sha: string;
  user: GitHubUserInfo;
  repo?: GitHubRepository;
}

interface GitHubLabel {
  id: number;
  name: string;
  description?: string;
  color: string;
  default: boolean;
}

interface GitHubMilestone {
  id: number;
  number: number;
  title: string;
  description?: string;
  state: 'open' | 'closed';
  open_issues: number;
  closed_issues: number;
  created_at: string;
  updated_at: string;
  due_on?: string;
  closed_at?: string;
  html_url: string;
}

interface GitHubDesktopManagerProps {
  userId: string;
  onConnectionChange?: (connected: boolean) => void;
}

const GitHubDesktopManager: React.FC<GitHubDesktopManagerProps> = ({
  userId,
  onConnectionChange
}) => {
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting' | 'error'>('disconnected');
  const [userInfo, setUserInfo] = useState<GitHubUserInfo | null>(null);
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [pullRequests, setPullRequests] = useState<GitHubPullRequest[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRepo, setSelectedRepo] = useState('');
  const [activeTab, setActiveTab] = useState(0);

  // Modal states
  const { isOpen: isCreateIssueOpen, onOpen: onCreateIssueOpen, onClose: onCreateIssueClose } = useDisclosure();
  const { isOpen: isCreatePROpen, onOpen: onCreatePROpen, onClose: onCreatePRClose } = useDisclosure();

  // Form states
  const [issueTitle, setIssueTitle] = useState('');
  const [issueBody, setIssueBody] = useState('');
  const [prTitle, setPrTitle] = useState('');
  const [prBody, setPrBody] = useState('');
  const [prHead, setPrHead] = useState('');
  const [prBase, setPrBase] = useState('');

  const logger = new Logger('GitHubDesktopManager');
  const toast = useToast();

  // Check connection status on mount
  useEffect(() => {
    checkConnectionStatus();
    
    // Listen for GitHub events
    EventBus.on('github:connected', handleGitHubConnected);
    EventBus.on('github:disconnected', handleGitHubDisconnected);

    return () => {
      EventBus.off('github:connected');
      EventBus.off('github:disconnected');
    };
  }, []);

  // Notify parent of connection changes
  useEffect(() => {
    if (onConnectionChange) {
      onConnectionChange(connectionStatus === 'connected');
    }
  }, [connectionStatus, onConnectionChange]);

  const checkConnectionStatus = async () => {
    try {
      const result = await invoke<any>('get_github_connection', { userId });
      
      if (result.connected) {
        setConnectionStatus('connected');
        setUserInfo(result.user_info);
        await loadUserData();
      } else {
        setConnectionStatus('disconnected');
      }
    } catch (error) {
      logger.error('Failed to check GitHub connection', error);
      setConnectionStatus('error');
    }
  };

  const loadUserData = async () => {
    setIsLoading(true);
    try {
      // Load repositories
      const repos = await invoke<GitHubRepository[]>('get_github_user_repositories', {
        userId,
        limit: 20
      });
      setRepositories(repos);

      if (repos.length > 0) {
        setSelectedRepo(repos[0].full_name);
        await loadRepositoryData(repos[0].full_name);
      }
    } catch (error) {
      logger.error('Failed to load GitHub data', error);
      toast({
        title: 'Failed to load GitHub data',
        description: 'Please check your connection and try again.',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const loadRepositoryData = async (repoFullName: string) => {
    try {
      const [owner, repo] = repoFullName.split('/');
      
      // Load issues
      const issuesData = await invoke<GitHubIssue[]>('get_github_repository_issues', {
        userId,
        owner,
        repo,
        state: 'open',
        limit: 10
      });
      setIssues(issuesData);

      // Load pull requests
      const prData = await invoke<GitHubPullRequest[]>('get_github_pull_requests', {
        userId,
        owner,
        repo,
        state: 'open',
        limit: 10
      });
      setPullRequests(prData);
    } catch (error) {
      logger.error('Failed to load repository data', error);
    }
  };

  const handleConnect = async () => {
    try {
      setConnectionStatus('connecting');
      
      const result = await invoke<any>('get_github_oauth_url', { userId });
      
      // Open OAuth URL in browser
      if (window.open(result.oauth_url, '_blank')) {
        // Listen for OAuth callback
        const handleOAuthCallback = (event: MessageEvent) => {
          if (event.data.type === 'github_oauth_success') {
            window.removeEventListener('message', handleOAuthCallback);
            handleGitHubConnected();
          } else if (event.data.type === 'github_oauth_error') {
            window.removeEventListener('message', handleOAuthCallback);
            setConnectionStatus('error');
          }
        };
        
        window.addEventListener('message', handleOAuthCallback);
      }
    } catch (error) {
      logger.error('Failed to initiate GitHub OAuth', error);
      setConnectionStatus('error');
      toast({
        title: 'Failed to connect to GitHub',
        description: 'Please try again later.',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleDisconnect = async () => {
    try {
      await invoke<any>('disconnect_github', { userId });
      handleGitHubDisconnected();
    } catch (error) {
      logger.error('Failed to disconnect from GitHub', error);
    }
  };

  const handleGitHubConnected = () => {
    setConnectionStatus('connected');
    loadUserData();
    EventBus.emit('github:connected', { userId });
  };

  const handleGitHubDisconnected = () => {
    setConnectionStatus('disconnected');
    setUserInfo(null);
    setRepositories([]);
    setIssues([]);
    setPullRequests([]);
    EventBus.emit('github:disconnected', { userId });
  };

  const handleCreateIssue = async () => {
    if (!issueTitle || !selectedRepo) return;

    try {
      const [owner, repo] = selectedRepo.split('/');
      
      const result = await invoke<any>('create_github_issue', {
        userId,
        owner,
        repo,
        title: issueTitle,
        body: issueBody
      });

      if (result.success) {
        toast({
          title: 'Issue created successfully',
          description: `Issue #${result.issue_number} created`,
          status: 'success',
          duration: 5000,
        });
        
        // Refresh issues
        await loadRepositoryData(selectedRepo);
        onCreateIssueClose();
        setIssueTitle('');
        setIssueBody('');
      }
    } catch (error) {
      logger.error('Failed to create issue', error);
      toast({
        title: 'Failed to create issue',
        description: 'Please try again.',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleCreatePR = async () => {
    if (!prTitle || !selectedRepo || !prHead || !prBase) return;

    try {
      const [owner, repo] = selectedRepo.split('/');
      
      const result = await invoke<any>('create_github_pull_request', {
        userId,
        owner,
        repo,
        title: prTitle,
        body: prBody,
        head: prHead,
        base: prBase
      });

      if (result.success) {
        toast({
          title: 'Pull request created successfully',
          description: `PR #${result.pr_number} created`,
          status: 'success',
          duration: 5000,
        });
        
        // Refresh PRs
        await loadRepositoryData(selectedRepo);
        onCreatePRClose();
        setPrTitle('');
        setPrBody('');
        setPrHead('');
        setPrBase('');
      }
    } catch (error) {
      logger.error('Failed to create pull request', error);
      toast({
        title: 'Failed to create pull request',
        description: 'Please try again.',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const formatDateTime = (dateTimeStr: string) => {
    return new Date(dateTimeStr).toLocaleString();
  };

  const getConnectionBadge = () => {
    switch (connectionStatus) {
      case 'connected':
        return <Badge colorScheme="green">Connected</Badge>;
      case 'connecting':
        return <Badge colorScheme="yellow">Connecting...</Badge>;
      case 'error':
        return <Badge colorScheme="red">Error</Badge>;
      default:
        return <Badge colorScheme="gray">Disconnected</Badge>;
    }
  };

  return (
    <VStack spacing={6} align="stretch">
      {/* Header */}
      <HStack justify="space-between" align="center">
        <HStack spacing={3}>
          <Icon as={FiGithub} box={6} color="gray.700" />
          <Heading size="md" color="gray.800">GitHub Integration</Heading>
          {getConnectionBadge()}
        </HStack>
        
        <HStack spacing={2}>
          {connectionStatus === 'connected' ? (
            <>
              <Tooltip label="Refresh data">
                <IconButton
                  icon={<FiRefresh />}
                  aria-label="Refresh"
                  variant="ghost"
                  onClick={loadUserData}
                  isLoading={isLoading}
                />
              </Tooltip>
              <Tooltip label="Disconnect">
                <IconButton
                  icon={<FiX />}
                  aria-label="Disconnect"
                  variant="ghost"
                  colorScheme="red"
                  onClick={handleDisconnect}
                />
              </Tooltip>
            </>
          ) : (
            <Button
              leftIcon={<FiGithub />}
              onClick={handleConnect}
              isLoading={connectionStatus === 'connecting'}
            >
              Connect GitHub
            </Button>
          )}
        </HStack>
      </HStack>

      {/* Connection Status */}
      {connectionStatus === 'connected' && userInfo ? (
        <Card>
          <CardBody>
            <HStack spacing={4}>
              <Avatar
                size="lg"
                src={userInfo.avatar_url}
                name={userInfo.name || userInfo.login}
              >
                <AvatarBadge boxSize="1.25em" bg="green.500" />
              </Avatar>
              <VStack align="start" spacing={0}>
                <Text fontSize="lg" fontWeight="bold">
                  {userInfo.name || userInfo.login}
                </Text>
                <Text fontSize="sm" color="gray.600">@{userInfo.login}</Text>
                {userInfo.company && (
                  <Text fontSize="xs" color="gray.500">{userInfo.company}</Text>
                )}
                {userInfo.bio && (
                  <Text fontSize="xs" color="gray.500" maxWidth="400px" noOfLines={2}>
                    {userInfo.bio}
                  </Text>
                )}
              </VStack>
              
              <HStack spacing={6} ml="auto">
                <Stat>
                  <StatNumber>{userInfo.public_repos}</StatNumber>
                  <StatLabel fontSize="sm">Repos</StatLabel>
                </Stat>
                <Stat>
                  <StatNumber>{userInfo.followers}</StatNumber>
                  <StatLabel fontSize="sm">Followers</StatLabel>
                </Stat>
                <Stat>
                  <StatNumber>{userInfo.following}</StatNumber>
                  <StatLabel fontSize="sm">Following</StatLabel>
                </Stat>
              </HStack>
            </HStack>
          </CardBody>
        </Card>
      ) : connectionStatus === 'disconnected' ? (
        <Alert status="info">
          <FiGithub />
          <Box>
            <Text fontWeight="bold">GitHub is not connected</Text>
            <Text>Connect your GitHub account to access repositories, issues, and pull requests.</Text>
          </Box>
        </Alert>
      ) : connectionStatus === 'error' ? (
        <Alert status="error">
          <FiX />
          <Box>
            <Text fontWeight="bold">GitHub connection error</Text>
            <Text>There was an error connecting to GitHub. Please try again.</Text>
          </Box>
        </Alert>
      ) : null}

      {/* Main Content */}
      {connectionStatus === 'connected' ? (
        <Tabs variant="soft-rounded" colorScheme="blue" index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack spacing={2}>
                <Icon as={FiRepo} />
                <Text>Repositories</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack spacing={2}>
                <Icon as={FiIssue} />
                <Text>Issues</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack spacing={2}>
                <Icon as={FiGitPullRequest} />
                <Text>Pull Requests</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Repositories Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Input
                    placeholder="Search repositories..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    leftElement={<FiSearch />}
                  />
                  <Button leftIcon={<FiRefresh />} onClick={loadUserData} isLoading={isLoading}>
                    Refresh
                  </Button>
                </HStack>

                <SimpleGrid columns={1} spacing={4}>
                  {repositories.map((repo) => (
                    <Card key={repo.id} variant="outline">
                      <CardBody>
                        <HStack justify="space-between">
                          <VStack align="start" spacing={2}>
                            <HStack>
                              <Icon as={FiRepo} color="gray.600" />
                              <Text fontWeight="bold">{repo.full_name}</Text>
                              {repo.private && <Icon as={FiLock} color="gray.500" />}
                              {repo.fork && <Icon as={FiFork} color="gray.500" />}
                            </HStack>
                            {repo.description && (
                              <Text fontSize="sm" color="gray.600" maxWidth="500px" noOfLines={2}>
                                {repo.description}
                              </Text>
                            )}
                            <HStack spacing={4} fontSize="sm" color="gray.500">
                              <HStack spacing={1}>
                                <FiStar />
                                <Text>{repo.stargazers_count}</Text>
                              </HStack>
                              <HStack spacing={1}>
                                <FiFork />
                                <Text>{repo.forks_count}</Text>
                              </HStack>
                              <HStack spacing={1}>
                                <FiIssue />
                                <Text>{repo.open_issues_count}</Text>
                              </HStack>
                              {repo.language && (
                                <Tag size="sm" colorScheme="gray">
                                  <TagLabel>{repo.language}</TagLabel>
                                </Tag>
                              )}
                            </HStack>
                          </VStack>
                          
                          <VStack align="end" spacing={2}>
                            <Button
                              size="sm"
                              onClick={() => {
                                setSelectedRepo(repo.full_name);
                                loadRepositoryData(repo.full_name);
                                setActiveTab(1);
                              }}
                            >
                              View Issues
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              leftIcon={<FiExternalLink />}
                              as="a"
                              href={repo.html_url}
                              target="_blank"
                            >
                              View on GitHub
                            </Button>
                          </VStack>
                        </HStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Issues Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <FormControl maxW="300px">
                    <FormLabel>Repository</FormLabel>
                    <Select
                      value={selectedRepo}
                      onChange={(e) => {
                        setSelectedRepo(e.target.value);
                        loadRepositoryData(e.target.value);
                      }}
                    >
                      {repositories.map((repo) => (
                        <option key={repo.id} value={repo.full_name}>
                          {repo.full_name}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                  
                  <Button leftIcon={<FiPlus />} onClick={onCreateIssueOpen}>
                    Create Issue
                  </Button>
                </HStack>

                <VStack spacing={3}>
                  {issues.map((issue) => (
                    <Card key={issue.id} variant="outline">
                      <CardBody>
                        <HStack justify="space-between">
                          <VStack align="start" spacing={2}>
                            <HStack>
                              <Icon as={FiIssue} color={issue.state === 'open' ? 'orange.500' : 'green.500'} />
                              <Text fontWeight="bold">
                                {issue.title}
                              </Text>
                              <Badge colorScheme={issue.state === 'open' ? 'orange' : 'green'}>
                                {issue.state}
                              </Badge>
                            </HStack>
                            
                            {issue.body && (
                              <Text fontSize="sm" color="gray.600" maxWidth="600px" noOfLines={2}>
                                {issue.body}
                              </Text>
                            )}
                            
                            <HStack spacing={4}>
                              <Text fontSize="xs" color="gray.500">
                                #{issue.number} • opened {formatDateTime(issue.created_at)}
                              </Text>
                              
                              {issue.labels.length > 0 && (
                                <HStack spacing={1}>
                                  {issue.labels.map((label) => (
                                    <Tag key={label.id} size="sm" backgroundColor={`#${label.color}`}>
                                      <TagLabel>{label.name}</TagLabel>
                                    </Tag>
                                  ))}
                                </HStack>
                              )}
                            </HStack>
                          </VStack>
                          
                          <VStack align="end">
                            <HStack>
                              <Avatar size="sm" src={issue.user.avatar_url} name={issue.user.login} />
                              <Text fontSize="xs" color="gray.500">{issue.user.login}</Text>
                            </HStack>
                            
                            <Button
                              size="sm"
                              variant="outline"
                              leftIcon={<FiExternalLink />}
                              as="a"
                              href={issue.html_url}
                              target="_blank"
                            >
                              View on GitHub
                            </Button>
                          </VStack>
                        </HStack>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              </VStack>
            </TabPanel>

            {/* Pull Requests Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <FormControl maxW="300px">
                    <FormLabel>Repository</FormLabel>
                    <Select
                      value={selectedRepo}
                      onChange={(e) => {
                        setSelectedRepo(e.target.value);
                        loadRepositoryData(e.target.value);
                      }}
                    >
                      {repositories.map((repo) => (
                        <option key={repo.id} value={repo.full_name}>
                          {repo.full_name}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                  
                  <Button leftIcon={<FiPlus />} onClick={onCreatePROpen}>
                    Create PR
                  </Button>
                </HStack>

                <VStack spacing={3}>
                  {pullRequests.map((pr) => (
                    <Card key={pr.id} variant="outline">
                      <CardBody>
                        <HStack justify="space-between">
                          <VStack align="start" spacing={2}>
                            <HStack>
                              <Icon as={FiGitPullRequest} color={pr.state === 'open' ? 'blue.500' : pr.state === 'merged' ? 'purple.500' : 'green.500'} />
                              <Text fontWeight="bold">
                                {pr.title}
                              </Text>
                              <Badge colorScheme={
                                pr.state === 'open' ? 'blue' :
                                pr.state === 'merged' ? 'purple' : 'green'
                              }>
                                {pr.state}
                              </Badge>
                            </HStack>
                            
                            {pr.body && (
                              <Text fontSize="sm" color="gray.600" maxWidth="600px" noOfLines={2}>
                                {pr.body}
                              </Text>
                            )}
                            
                            <HStack spacing={4}>
                              <Text fontSize="xs" color="gray.500">
                                #{pr.number} • {pr.head.label} → {pr.base.label}
                              </Text>
                              <Text fontSize="xs" color="gray.500">
                                {pr.additions} additions, {pr.deletions} deletions
                              </Text>
                              <Text fontSize="xs" color="gray.500">
                                opened {formatDateTime(pr.created_at)}
                              </Text>
                              
                              {pr.labels.length > 0 && (
                                <HStack spacing={1}>
                                  {pr.labels.map((label) => (
                                    <Tag key={label.id} size="sm" backgroundColor={`#${label.color}`}>
                                      <TagLabel>{label.name}</TagLabel>
                                    </Tag>
                                  ))}
                                </HStack>
                              )}
                            </HStack>
                          </VStack>
                          
                          <VStack align="end">
                            <HStack>
                              <Avatar size="sm" src={pr.user.avatar_url} name={pr.user.login} />
                              <Text fontSize="xs" color="gray.500">{pr.user.login}</Text>
                            </HStack>
                            
                            <Button
                              size="sm"
                              variant="outline"
                              leftIcon={<FiExternalLink />}
                              as="a"
                              href={pr.html_url}
                              target="_blank"
                            >
                              View on GitHub
                            </Button>
                          </VStack>
                        </HStack>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      ) : null}

      {/* Create Issue Modal */}
      <Modal isOpen={isCreateIssueOpen} onClose={onCreateIssueClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create Issue</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Title</FormLabel>
                <Input
                  value={issueTitle}
                  onChange={(e) => setIssueTitle(e.target.value)}
                  placeholder="Issue title"
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={issueBody}
                  onChange={(e) => setIssueBody(e.target.value)}
                  placeholder="Issue description"
                  rows={6}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="outline" onClick={onCreateIssueClose}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={handleCreateIssue} isLoading={isLoading}>
              Create Issue
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Create Pull Request Modal */}
      <Modal isOpen={isCreatePROpen} onClose={onCreatePrClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create Pull Request</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Title</FormLabel>
                <Input
                  value={prTitle}
                  onChange={(e) => setPrTitle(e.target.value)}
                  placeholder="Pull request title"
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={prBody}
                  onChange={(e) => setPrBody(e.target.value)}
                  placeholder="Pull request description"
                  rows={6}
                />
              </FormControl>
              
              <HStack spacing={4} width="full">
                <FormControl>
                  <FormLabel>Head Branch</FormLabel>
                  <Input
                    value={prHead}
                    onChange={(e) => setPrHead(e.target.value)}
                    placeholder="feature-branch"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Base Branch</FormLabel>
                  <Input
                    value={prBase}
                    onChange={(e) => setPrBase(e.target.value)}
                    placeholder="main"
                  />
                </FormControl>
              </HStack>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="outline" onClick={onCreatePrClose}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={handleCreatePR} isLoading={isLoading}>
              Create PR
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </VStack>
  );
};

export default GitHubDesktopManager;
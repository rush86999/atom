/**
 * ATOM GitHub Manager - TypeScript
 * Development → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomGitHubManagerProps, 
  AtomGitHubState,
  GitHubConfig,
  AtomGitHubAPI,
  GitHubRepository,
  GitHubIssue,
  GitHubPullRequest,
  GitHubCommit,
  GitHubUser,
  GitHubRelease,
  GitHubWebhook,
  GitHubSearchResponse
} from '../types';

export const ATOMGitHubManager: React.FC<AtomGitHubManagerProps> = ({
  // GitHub Authentication
  personalAccessToken,
  oauthToken,
  onTokenRefresh,
  
  // GitHub Configuration
  config = {},
  platform = 'auto',
  theme = 'auto',
  
  // Events
  onRepoSelected,
  onIssueSelected,
  onPRSelected,
  onCommitSelected,
  onError,
  onSuccess,
  onReposLoaded,
  onIssuesLoaded,
  onPRsLoaded,
  onCommitsLoaded,
  onReleasesLoaded,
  onUsersLoaded,
  onWebhooksLoaded,
  
  // Children
  children
}) => {
  
  // State Management
  const [state, setState] = useState<AtomGitHubState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    repositories: [],
    issues: [],
    pullRequests: [],
    commits: [],
    files: [],
    releases: [],
    webhooks: [],
    users: [],
    searchResults: {
      total_count: 0,
      incomplete_results: false,
      items: []
    },
    currentRepo: undefined,
    selectedItems: [],
    sortBy: 'updated',
    sortOrder: 'desc',
    viewMode: 'list',
    filters: {
      languages: [],
      topics: [],
      minStars: 0,
      minSize: 0,
      includePrivate: false,
      includeForks: false,
      includeArchived: false,
      authors: [],
      labels: [],
      states: ['open'],
      fileTypes: []
    }
  });

  // Configuration
  const [gitHubConfig] = useState<GitHubConfig>(() => ({
    // API Configuration
    apiBaseUrl: 'https://api.github.com',
    graphqlUrl: 'https://api.github.com/graphql',
    
    // Authentication
    personalAccessToken: personalAccessToken,
    oauthToken: oauthToken,
    clientId: config.clientId,
    clientSecret: config.clientSecret,
    
    // Repository Discovery
    includePrivate: config.includePrivate ?? false,
    includeArchived: config.includeArchived ?? false,
    includeForks: config.includeForks ?? false,
    includedRepos: config.includedRepos ?? [],
    excludedRepos: config.excludedRepos ?? [],
    repoLanguages: config.repoLanguages ?? ['JavaScript', 'TypeScript', 'Python', 'Java', 'Go', 'Rust', 'C++', 'C#'],
    minStars: config.minStars ?? 0,
    minSize: config.minSize ?? 0,
    
    // Issue Discovery
    includeIssues: config.includeIssues ?? true,
    includePullRequests: config.includePullRequests ?? true,
    includeClosed: config.includeClosed ?? false,
    issueDateRange: config.issueDateRange,
    maxIssuesPerRepo: config.maxIssuesPerRepo ?? 1000,
    
    // Code Discovery
    includeCode: config.includeCode ?? true,
    includeDocumentation: config.includeDocumentation ?? true,
    includeTests: config.includeTests ?? false,
    includedFileTypes: config.includedFileTypes ?? ['.md', '.txt', '.json', '.yaml', '.yml', '.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'],
    excludedFileTypes: config.excludedFileTypes ?? ['.exe', '.dll', '.so', '.dylib', '.bin', '.zip', '.tar', '.gz', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.mp4', '.avi', '.mov', '.wmv', '.mp3', '.wav', '.flac'],
    maxFileSize: config.maxFileSize ?? 10 * 1024 * 1024,
    
    // Commit Discovery
    includeCommits: config.includeCommits ?? true,
    commitDateRange: config.commitDateRange,
    maxCommitsPerRepo: config.maxCommitsPerRepo ?? 1000,
    
    // Search Settings
    searchQuery: config.searchQuery,
    searchType: config.searchType ?? 'repositories',
    maxSearchResults: config.maxSearchResults ?? 100,
    
    // Rate Limiting
    apiCallsPerHour: config.apiCallsPerHour ?? 5000,
    useRateLimiter: config.useRateLimiter ?? true,
    
    ...config
  }));

  // Platform Detection
  const [currentPlatform, setCurrentPlatform] = useState<'nextjs' | 'tauri'>('nextjs');

  useEffect(() => {
    if (platform !== 'auto') {
      setCurrentPlatform(platform);
      return;
    }
    
    if (typeof window !== 'undefined' && (window as any).__TAURI__) {
      setCurrentPlatform('tauri');
    } else {
      setCurrentPlatform('nextjs');
    }
  }, [platform]);

  // Rate Limiting
  const [apiCallCount, setApiCallCount] = useState(0);
  const [rateLimitReset, setRateLimitReset] = useState(Date.now() + 3600000);
  
  const checkRateLimit = useCallback(() => {
    const now = Date.now();
    if (now > rateLimitReset) {
      setApiCallCount(0);
      setRateLimitReset(now + 3600000);
      return true;
    }
    return apiCallCount < gitHubConfig.apiCallsPerHour;
  }, [apiCallCount, rateLimitReset, gitHubConfig.apiCallsPerHour]);

  const incrementApiCall = useCallback(() => {
    setApiCallCount(prev => prev + 1);
  }, []);

  // GitHub API Integration
  const gitHubApi = useMemo((): AtomGitHubAPI => {
    const authToken = gitHubConfig.personalAccessToken || gitHubConfig.oauthToken;
    const headers: Record<string, string> = {
      'Accept': 'application/vnd.github.v3+json',
      'Authorization': `token ${authToken}`,
      'User-Agent': 'ATOM-Agent/1.0'
    };

    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      // Rate limiting
      if (gitHubConfig.useRateLimiter && !checkRateLimit()) {
        throw new Error('GitHub API rate limit exceeded. Please try again later.');
      }
      
      const url = `${gitHubConfig.apiBaseUrl}${endpoint}`;
      
      try {
        const response = await fetch(url, {
          ...options,
          headers: {
            ...headers,
            ...options.headers as Record<string, string>
          }
        });

        if (gitHubConfig.useRateLimiter) {
          incrementApiCall();
        }

        // Handle rate limiting
        if (response.status === 403) {
          const rateLimitRemaining = response.headers.get('X-RateLimit-Remaining');
          const rateLimitReset = response.headers.get('X-RateLimit-Reset');
          
          if (rateLimitRemaining === '0' && rateLimitReset) {
            const resetTime = parseInt(rateLimitReset) * 1000;
            const waitTime = resetTime - Date.now();
            throw new Error(`GitHub API rate limit exceeded. Resets in ${Math.ceil(waitTime / 1000 / 60)} minutes.`);
          }
        }

        if (response.status === 401) {
          throw new Error('GitHub authentication failed - please check your access token');
        }

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(`GitHub API Error: ${response.status} - ${errorData.message || response.statusText}`);
        }

        return response.json();
      } catch (error) {
        console.error('GitHub API request failed:', error);
        throw error;
      }
    };

    const makePaginatedRequest = async <T,>(
      endpoint: string,
      options: RequestInit = {},
      maxPages = 10
    ): Promise<T[]> => {
      const items: T[] = [];
      let page = 1;
      
      while (page <= maxPages) {
        const searchParams = new URLSearchParams({
          per_page: '100',
          page: page.toString(),
          ...options.body && JSON.parse(options.body as string)
        });
        
        const paginatedEndpoint = endpoint.includes('?') 
          ? `${endpoint}&${searchParams}`
          : `${endpoint}?${searchParams}`;
          
        const response = await makeRequest(paginatedEndpoint, {
          ...options,
          body: undefined
        });
        
        if (Array.isArray(response)) {
          items.push(...response);
          if (response.length < 100) break;
        } else if (response.items) {
          items.push(...response.items);
          if (response.items.length < 100) break;
        } else {
          break;
        }
        
        page++;
      }
      
      return items;
    };

    return {
      // Authentication
      authenticate: async (token: string) => {
        return {
          token,
          expires_in: 3600,
          token_type: 'Bearer'
        };
      },
      
      // Repository Operations
      getUserRepos: async (username, type = 'all', sort = 'updated', direction = 'desc', perPage = 100, page = 1) => {
        const endpoint = username 
          ? `/users/${username}/repos`
          : '/user/repos';
        
        return await makePaginatedRequest<GitHubRepository>(
          endpoint,
          {
            body: JSON.stringify({
              type,
              sort,
              direction,
              per_page: perPage,
              page
            })
          }
        );
      },
      
      getOrgRepos: async (org, type = 'all', sort = 'updated', direction = 'desc', perPage = 100, page = 1) => {
        return await makePaginatedRequest<GitHubRepository>(
          `/orgs/${org}/repos`,
          {
            body: JSON.stringify({
              type,
              sort,
              direction,
              per_page: perPage,
              page
            })
          }
        );
      },
      
      getRepo: async (owner: string, repo: string) => {
        return await makeRequest(`/repos/${owner}/${repo}`);
      },
      
      getRepoContent: async (owner: string, repo: string, path: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}`);
      },
      
      downloadRepoContent: async (owner: string, repo: string, path: string) => {
        const file = await gitHubApi.getRepoContent(owner, repo, path);
        
        if (!file || !('download_url' in file) || !file.download_url) {
          throw new Error('File not found or not downloadable');
        }
        
        const response = await fetch(file.download_url);
        return await response.blob();
      },
      
      createRepo: async (repo: Partial<GitHubRepository>) => {
        return await makeRequest('/user/repos', {
          method: 'POST',
          body: JSON.stringify({
            name: repo.name,
            description: repo.description,
            private: repo.private || false,
            auto_init: true
          })
        });
      },
      
      updateRepo: async (owner: string, repo: string, updates: Partial<GitHubRepository>) => {
        return await makeRequest(`/repos/${owner}/${repo}`, {
          method: 'PATCH',
          body: JSON.stringify(updates)
        });
      },
      
      deleteRepo: async (owner: string, repo: string) => {
        return await makeRequest(`/repos/${owner}/${repo}`, {
          method: 'DELETE'
        });
      },
      
      forkRepo: async (owner: string, repo: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/forks`, {
          method: 'POST'
        });
      },
      
      // Issue Operations
      getIssues: async (owner: string, repo: string, state = 'all', labels: string[] = [], sort = 'created', direction = 'desc', perPage = 100, page = 1) => {
        const labelQuery = labels.length > 0 ? `&labels=${labels.join(',')}` : '';
        return await makePaginatedRequest<GitHubIssue>(
          `/repos/${owner}/${repo}/issues?state=${state}&sort=${sort}&direction=${direction}${labelQuery}`
        );
      },
      
      getIssue: async (owner: string, repo: string, issueNumber: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/${issueNumber}`);
      },
      
      createIssue: async (owner: string, repo: string, issue: Partial<GitHubIssue>) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues`, {
          method: 'POST',
          body: JSON.stringify({
            title: issue.title,
            body: issue.body,
            labels: issue.labels?.map(l => l.name),
            assignees: issue.assignees?.map(a => a.login)
          })
        });
      },
      
      updateIssue: async (owner: string, repo: string, issueNumber: number, updates: Partial<GitHubIssue>) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/${issueNumber}`, {
          method: 'PATCH',
          body: JSON.stringify(updates)
        });
      },
      
      closeIssue: async (owner: string, repo: string, issueNumber: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/${issueNumber}`, {
          method: 'PATCH',
          body: JSON.stringify({ state: 'closed' })
        });
      },
      
      listPullRequests: async (owner: string, repo: string, filters?: any) => {
        const params = new URLSearchParams({
          state: filters?.state || 'all',
          sort: filters?.sort || 'updated',
          direction: filters?.direction || 'desc'
        });
        
        return await makeRequest(`/repos/${owner}/${repo}/pulls?${params}`);
      },
      
      mergePullRequest: async (owner: string, repo: string, prNumber: number, mergeMethod?: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/pulls/${prNumber}/merge`, {
          method: 'PUT',
          body: JSON.stringify({ merge_method: mergeMethod || 'merge' })
        });
      }
    }
  };

  // GitHub Manager Component with ATOM Integration
  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <Heading size="md">GitHub Integration</Heading>
          <HStack>
            <Badge
              colorScheme={state.connectionStatus === 'connected' ? 'green' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon as={state.connectionStatus === 'connected' ? CheckCircleIcon : WarningIcon} mr={1} />
              {state.connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<RepeatIcon />}
              onClick={checkGitHubConnection}
              isLoading={state.loading}
            >
              Refresh
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* Authentication Status */}
          {state.connectionStatus !== 'connected' && (
            <VStack>
              <Button
                colorScheme="gray"
                leftIcon={<GitHubLogoIcon />}
                onClick={startGitHubOAuth}
                width="full"
                size="lg"
              >
                Connect to GitHub
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Connect your GitHub account to enable advanced features
              </Text>
            </VStack>
          )}

          {/* Repository Management */}
          {state.connectionStatus === 'connected' && (
            <>
              <FormControl>
                <FormLabel>Selected Repositories</FormLabel>
                <VStack align="start" spacing={2} maxH="200px" overflowY="auto">
                  {repositories.map((repo) => (
                    <HStack key={repo.id} justify="space-between" w="full">
                      <Checkbox
                        isChecked={selectedRepos.includes(repo.id)}
                        onChange={(e) => toggleRepositorySelection(repo.id, e.target.checked)}
                      >
                        <Text fontSize="sm">{repo.full_name}</Text>
                      </Checkbox>
                      <HStack spacing={2}>
                        {repo.private && (
                          <Badge size="sm" colorScheme="yellow">Private</Badge>
                        )}
                        <Badge size="sm" colorScheme="blue">
                          {repo.stars} ⭐
                        </Badge>
                      </HStack>
                    </HStack>
                  ))}
                </VStack>
                <FormHelperText>
                  Select repositories to ingest data from
                </FormHelperText>
              </FormControl>

              {/* Data Types to Ingest */}
              <FormControl>
                <FormLabel>Data Types</FormLabel>
                <Stack direction="row" spacing={4}>
                  {['issues', 'pull_requests', 'commits', 'releases', 'workflows'].map((type) => (
                    <Checkbox
                      key={type}
                      isChecked={dataTypes.includes(type)}
                      onChange={(e) => toggleDataTypeSelection(type, e.target.checked)}
                    >
                      {type.replace(/_/g, ' ').charAt(0).toUpperCase() + type.replace(/_/g, ' ').slice(1)}
                    </Checkbox>
                  ))}
                </Stack>
              </FormControl>

              {/* Date Range */}
              <FormControl>
                <FormLabel>Date Range</FormLabel>
                <HStack>
                  <Input
                    type="date"
                    value={dateRange.start.toISOString().split('T')[0]}
                    onChange={(e) => updateDateRange('start', new Date(e.target.value))}
                  />
                  <Text>to</Text>
                  <Input
                    type="date"
                    value={dateRange.end.toISOString().split('T')[0]}
                    onChange={(e) => updateDateRange('end', new Date(e.target.value))}
                  />
                </HStack>
              </FormControl>

              {/* ATOM Ingestion Controls */}
              <VStack spacing={4}>
                <HStack justify="space-between" w="full">
                  <Text fontWeight="bold">ATOM Ingestion</Text>
                  <Switch
                    isChecked={ingestionConfig.enabled}
                    onChange={(e) => updateIngestionConfig('enabled', e.target.checked)}
                  />
                </HStack>

                <Collapse in={ingestionConfig.enabled}>
                  <VStack spacing={3} align="stretch">
                    <FormControl>
                      <FormLabel>Sync Frequency</FormLabel>
                      <Select
                        value={ingestionConfig.syncFrequency}
                        onChange={(e) => updateIngestionConfig('syncFrequency', e.target.value)}
                      >
                        <option value="realtime">Real-time</option>
                        <option value="hourly">Hourly</option>
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Max Items per Sync</FormLabel>
                      <Input
                        type="number"
                        value={ingestionConfig.maxItems}
                        onChange={(e) => updateIngestionConfig('maxItems', parseInt(e.target.value) || 100)}
                      />
                    </FormControl>

                    <HStack>
                      <Checkbox
                        isChecked={ingestionConfig.includePrivate}
                        onChange={(e) => updateIngestionConfig('includePrivate', e.target.checked)}
                      >
                        Include Private Repos
                      </Checkbox>
                      <Checkbox
                        isChecked={ingestionConfig.includeForks}
                        onChange={(e) => updateIngestionConfig('includeForks', e.target.checked)}
                      >
                        Include Forks
                      </Checkbox>
                    </HStack>
                  </VStack>
                </Collapse>

                {/* Ingestion Progress */}
                {ingestionStatus.running && (
                  <Card>
                    <CardBody>
                      <VStack spacing={3}>
                        <HStack justify="space-between" w="full">
                          <Text>Ingesting GitHub data...</Text>
                          <Text>{Math.round(ingestionStatus.progress)}%</Text>
                        </HStack>
                        <Progress
                          value={ingestionStatus.progress}
                          size="md"
                          colorScheme="green"
                          w="full"
                        />
                        <Text fontSize="sm" color="gray.600">
                          {ingestionStatus.repositoriesProcessed} repositories processed
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                )}

                {/* Action Buttons */}
                <HStack justify="space-between" w="full">
                  <Button
                    variant="outline"
                    leftIcon={<ExternalLinkIcon />}
                    onClick={() => window.open('https://github.com', '_blank')}
                  >
                    Open GitHub
                  </Button>

                  <Button
                    colorScheme="green"
                    leftIcon={<AddIcon />}
                    onClick={startIngestion}
                    isDisabled={
                      selectedRepos.length === 0 ||
                      dataTypes.length === 0 ||
                      !ingestionConfig.enabled ||
                      ingestionStatus.running
                    }
                    isLoading={ingestionStatus.running}
                  >
                    {ingestionStatus.running ? 'Ingesting...' : 'Start Ingestion'}
                  </Button>
                </HStack>
              </VStack>
            </>
          )}

          {/* Health Status */}
          {healthStatus && (
            <Alert status={healthStatus.healthy ? 'success' : 'warning'}>
              <AlertIcon />
              <Box>
                <Text fontWeight="bold">
                  GitHub service {healthStatus.healthy ? 'healthy' : 'unhealthy'}
                </Text>
                <Text fontSize="sm">{healthStatus.message}</Text>
              </Box>
            </Alert>
          )}

          {/* Error Display */}
          {state.error && (
            <Alert status="error">
              <AlertIcon />
              <Text>{state.error}</Text>
            </Alert>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
};
      
      reopenIssue: async (owner: string, repo: string, issueNumber: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/${issueNumber}`, {
          method: 'PATCH',
          body: JSON.stringify({ state: 'open' })
        });
      },
      
      // Pull Request Operations
      getPullRequests: async (owner: string, repo: string, state = 'all', head: string = '', base: string = '', sort = 'created', direction = 'desc', perPage = 100, page = 1) => {
        const params = new URLSearchParams({
          state,
          sort,
          direction
        });
        
        if (head) params.set('head', head);
        if (base) params.set('base', base);
        
        return await makePaginatedRequest<GitHubPullRequest>(
          `/repos/${owner}/${repo}/pulls?${params.toString()}`
        );
      },
      
      getPullRequest: async (owner: string, repo: string, prNumber: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/pulls/${prNumber}`);
      },
      
      createPullRequest: async (owner: string, repo: string, pr: Partial<GitHubPullRequest>) => {
        return await makeRequest(`/repos/${owner}/${repo}/pulls`, {
          method: 'POST',
          body: JSON.stringify({
            title: pr.title,
            body: pr.body,
            head: pr.head?.ref,
            base: pr.base?.ref
          })
        });
      },
      
      updatePullRequest: async (owner: string, repo: string, prNumber: number, updates: Partial<GitHubPullRequest>) => {
        return await makeRequest(`/repos/${owner}/${repo}/pulls/${prNumber}`, {
          method: 'PATCH',
          body: JSON.stringify(updates)
        });
      },
      
      mergePullRequest: async (owner: string, repo: string, prNumber: number, commitTitle?: string, commitMessage?: string, mergeMethod = 'merge') => {
        return await makeRequest(`/repos/${owner}/${repo}/pulls/${prNumber}/merge`, {
          method: 'PUT',
          body: JSON.stringify({
            commit_title: commitTitle,
            commit_message: commitMessage,
            merge_method: mergeMethod
          })
        });
      },
      
      closePullRequest: async (owner: string, repo: string, prNumber: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/pulls/${prNumber}`, {
          method: 'PATCH',
          body: JSON.stringify({ state: 'closed' })
        });
      },
      
      // Commit Operations
      getCommits: async (owner: string, repo: string, sha?: string, path?: string, since?: string, until?: string, perPage = 100, page = 1) => {
        const params = new URLSearchParams({
          per_page: perPage.toString(),
          page: page.toString()
        });
        
        if (sha) params.set('sha', sha);
        if (path) params.set('path', path);
        if (since) params.set('since', since);
        if (until) params.set('until', until);
        
        return await makePaginatedRequest<GitHubCommit>(
          `/repos/${owner}/${repo}/commits?${params.toString()}`
        );
      },
      
      getCommit: async (owner: string, repo: string, sha: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/commits/${sha}`);
      },
      
      compareCommits: async (owner: string, repo: string, base: string, head: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/compare/${base}...${head}`);
      },
      
      // Comment Operations
      getIssueComments: async (owner: string, repo: string, issueNumber: number, sort = 'created', direction = 'desc', perPage = 100, page = 1) => {
        return await makePaginatedRequest<any>(
          `/repos/${owner}/${repo}/issues/${issueNumber}/comments?sort=${sort}&direction=${direction}`
        );
      },
      
      getPRComments: async (owner: string, repo: string, prNumber: number, sort = 'created', direction = 'desc', perPage = 100, page = 1) => {
        return await makePaginatedRequest<any>(
          `/repos/${owner}/${repo}/pulls/${prNumber}/comments?sort=${sort}&direction=${direction}`
        );
      },
      
      getCommitComments: async (owner: string, repo: string, sha: string, sort = 'created', direction = 'desc', perPage = 100, page = 1) => {
        return await makePaginatedRequest<any>(
          `/repos/${owner}/${repo}/commits/${sha}/comments?sort=${sort}&direction=${direction}`
        );
      },
      
      createComment: async (owner: string, repo: string, issueNumber: number, body: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/${issueNumber}/comments`, {
          method: 'POST',
          body: JSON.stringify({ body })
        });
      },
      
      updateComment: async (owner: string, repo: string, commentId: number, body: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/comments/${commentId}`, {
          method: 'PATCH',
          body: JSON.stringify({ body })
        });
      },
      
      deleteComment: async (owner: string, repo: string, commentId: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/comments/${commentId}`, {
          method: 'DELETE'
        });
      },
      
      // Release Operations
      getReleases: async (owner: string, repo: string, perPage = 100, page = 1) => {
        return await makePaginatedRequest<GitHubRelease>(
          `/repos/${owner}/${repo}/releases?per_page=${perPage}&page=${page}`
        );
      },
      
      getRelease: async (owner: string, repo: string, releaseId: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/releases/${releaseId}`);
      },
      
      createRelease: async (owner: string, repo: string, release: Partial<GitHubRelease>) => {
        return await makeRequest(`/repos/${owner}/${repo}/releases`, {
          method: 'POST',
          body: JSON.stringify({
            tag_name: release.tag_name,
            name: release.name,
            body: release.body,
            draft: release.draft || false,
            prerelease: release.prerelease || false
          })
        });
      },
      
      updateRelease: async (owner: string, repo: string, releaseId: number, updates: Partial<GitHubRelease>) => {
        return await makeRequest(`/repos/${owner}/${repo}/releases/${releaseId}`, {
          method: 'PATCH',
          body: JSON.stringify(updates)
        });
      },
      
      deleteRelease: async (owner: string, repo: string, releaseId: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/releases/${releaseId}`, {
          method: 'DELETE'
        });
      },
      
      // Search Operations
      searchRepos: async (query: string, sort = 'stars', order = 'desc', perPage = 100, page = 1) => {
        return await makeRequest<GitHubSearchResponse<GitHubRepository>>(
          `/search/repositories?q=${encodeURIComponent(query)}&sort=${sort}&order=${order}&per_page=${perPage}&page=${page}`
        );
      },
      
      searchIssues: async (query: string, sort = 'created', order = 'desc', perPage = 100, page = 1) => {
        return await makeRequest<GitHubSearchResponse<GitHubIssue>>(
          `/search/issues?q=${encodeURIComponent(query)}&sort=${sort}&order=${order}&per_page=${perPage}&page=${page}`
        );
      },
      
      searchCode: async (query: string, sort = 'indexed', order = 'desc', perPage = 100, page = 1) => {
        return await makeRequest<GitHubSearchResponse<any>>(
          `/search/code?q=${encodeURIComponent(query)}&sort=${sort}&order=${order}&per_page=${perPage}&page=${page}`
        );
      },
      
      searchUsers: async (query: string, sort = 'followers', order = 'desc', perPage = 100, page = 1) => {
        return await makeRequest<GitHubSearchResponse<GitHubUser>>(
          `/search/users?q=${encodeURIComponent(query)}&sort=${sort}&order=${order}&per_page=${perPage}&page=${page}`
        );
      },
      
      // Webhook Operations
      getWebhooks: async (owner: string, repo: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/hooks`);
      },
      
      createWebhook: async (owner: string, repo: string, webhook: Partial<GitHubWebhook>) => {
        return await makeRequest(`/repos/${owner}/${repo}/hooks`, {
          method: 'POST',
          body: JSON.stringify({
            name: webhook.name,
            active: webhook.active ?? true,
            events: webhook.events || ['push'],
            config: webhook.config || {
              url: webhook.config?.url || '',
              content_type: 'json'
            }
          })
        });
      },
      
      updateWebhook: async (owner: string, repo: string, webhookId: number, updates: Partial<GitHubWebhook>) => {
        return await makeRequest(`/repos/${owner}/${repo}/hooks/${webhookId}`, {
          method: 'PATCH',
          body: JSON.stringify(updates)
        });
      },
      
      deleteWebhook: async (owner: string, repo: string, webhookId: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/hooks/${webhookId}`, {
          method: 'DELETE'
        });
      },
      
      // User Operations
      getCurrentUser: async () => {
        return await makeRequest('/user');
      },
      
      getUser: async (username: string) => {
        return await makeRequest(`/users/${username}`);
      },
      
      // GraphQL Operations
      graphqlQuery: async (query: string, variables: any = {}) => {
        return await makeRequest(gitHubConfig.graphqlUrl, {
          method: 'POST',
          body: JSON.stringify({
            query,
            variables
          })
        });
      }
    };
  }, [gitHubConfig, checkRateLimit, incrementApiCall]);

  // Initialize GitHub connection
  const initializeGitHub = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Test authentication
      const user = await gitHubApi.getCurrentUser();
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        initialized: true
      }));
      
      if (onSuccess) {
        onSuccess({
          connected: true,
          user: user.login,
          plan: user.plan?.name || 'free'
        });
      }
      
    } catch (error) {
      const errorMessage = `Failed to initialize GitHub: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'initialization');
      }
    }
  }, [gitHubApi, onSuccess, onError]);

  // Load User Repositories
  const loadUserRepos = useCallback(async (username?: string) => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const repositories = await gitHubApi.getUserRepos(
        username,
        'all',
        'updated',
        'desc'
      );
      
      // Filter repositories based on configuration
      const filteredRepos = repositories.filter(repo => {
        // Check if repository is explicitly included
        if (gitHubConfig.includedRepos.length > 0) {
          return gitHubConfig.includedRepos.includes(repo.full_name);
        }
        
        // Check if repository is excluded
        if (gitHubConfig.excludedRepos.includes(repo.full_name)) {
          return false;
        }
        
        // Check privacy
        if (!gitHubConfig.includePrivate && repo.private) {
          return false;
        }
        
        // Check archived
        if (!gitHubConfig.includeArchived && repo.archived) {
          return false;
        }
        
        // Check forks
        if (!gitHubConfig.includeForks && repo.fork) {
          return false;
        }
        
        // Check stars
        if (repo.stargazers_count < (gitHubConfig.minStars || 0)) {
          return false;
        }
        
        // Check size
        if (repo.size < (gitHubConfig.minSize || 0)) {
          return false;
        }
        
        // Check language
        if (gitHubConfig.repoLanguages.length > 0 && repo.language) {
          return gitHubConfig.repoLanguages.includes(repo.language);
        }
        
        return true;
      });
      
      setState(prev => ({
        ...prev,
        loading: false,
        repositories: filteredRepos
      }));
      
      if (onReposLoaded) {
        onReposLoaded(filteredRepos);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load repositories: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadRepos');
      }
    }
  }, [gitHubApi, gitHubConfig, onReposLoaded, onError]);

  // Load Issues
  const loadIssues = useCallback(async (repo: string) => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const [owner, repoName] = repo.split('/');
      const issues = await gitHubApi.getIssues(owner, repoName, 'all');
      
      // Filter out pull requests (GitHub API returns both)
      const regularIssues = issues.filter(issue => !issue.pull_request);
      
      setState(prev => ({
        ...prev,
        loading: false,
        issues: regularIssues
      }));
      
      if (onIssuesLoaded) {
        onIssuesLoaded(regularIssues);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load issues: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadIssues');
      }
    }
  }, [gitHubApi, onIssuesLoaded, onError]);

  // Load Pull Requests
  const loadPullRequests = useCallback(async (repo: string) => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const [owner, repoName] = repo.split('/');
      const pullRequests = await gitHubApi.getPullRequests(owner, repoName, 'all');
      
      setState(prev => ({
        ...prev,
        loading: false,
        pullRequests: pullRequests
      }));
      
      if (onPRsLoaded) {
        onPRsLoaded(pullRequests);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load pull requests: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadPRs');
      }
    }
  }, [gitHubApi, onPRsLoaded, onError]);

  // Load Commits
  const loadCommits = useCallback(async (repo: string) => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const [owner, repoName] = repo.split('/');
      const commits = await gitHubApi.getCommits(owner, repoName);
      
      setState(prev => ({
        ...prev,
        loading: false,
        commits: commits
      }));
      
      if (onCommitsLoaded) {
        onCommitsLoaded(commits);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load commits: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadCommits');
      }
    }
  }, [gitHubApi, onCommitsLoaded, onError]);

  // Load Releases
  const loadReleases = useCallback(async (repo: string) => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      const [owner, repoName] = repo.split('/');
      const releases = await gitHubApi.getReleases(owner, repoName);
      
      setState(prev => ({
        ...prev,
        loading: false,
        releases: releases
      }));
      
      if (onReleasesLoaded) {
        onReleasesLoaded(releases);
      }
      
    } catch (error) {
      const errorMessage = `Failed to load releases: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'loadReleases');
      }
    }
  }, [gitHubApi, onReleasesLoaded, onError]);

  // Search Repositories
  const searchRepos = useCallback(async (query: string, filters?: any) => {
    try {
      const response = await gitHubApi.searchRepos(
        query,
        filters?.sort || 'stars',
        filters?.order || 'desc'
      );
      
      setState(prev => ({
        ...prev,
        searchResults: response
      }));
      
      return response;
      
    } catch (error) {
      const errorMessage = `Failed to search repositories: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        error: errorMessage
      }));
      
      if (onError) {
        onError(errorMessage, 'searchRepos');
      }
      
      return { total_count: 0, incomplete_results: false, items: [] };
    }
  }, [gitHubApi, onError]);

  // Create Repository
  const createRepo = useCallback(async (repo: Partial<GitHubRepository>) => {
    try {
      const newRepo = await gitHubApi.createRepo(repo);
      
      if (onSuccess) {
        onSuccess({
          action: 'repo_created',
          repository: newRepo
        });
      }
      
      return newRepo;
      
    } catch (error) {
      const errorMessage = `Failed to create repository: ${(error as Error).message}`;
      
      if (onError) {
        onError(errorMessage, 'createRepo');
      }
      
      throw error;
    }
  }, [gitHubApi, onSuccess, onError]);

  // Initialize on mount
  useEffect(() => {
    if ((gitHubConfig.personalAccessToken || gitHubConfig.oauthToken)) {
      initializeGitHub();
    }
  }, [gitHubConfig.personalAccessToken, gitHubConfig.oauthToken]);

  // Theme Resolution
  const resolvedTheme = theme === 'auto' 
    ? (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;

  const themeClasses = {
    light: 'bg-white text-gray-900 border-gray-200',
    dark: 'bg-gray-900 text-gray-100 border-gray-700'
  };

  // Render Component or Children
  const renderContent = () => {
    if (children) {
      return children({
        state,
        api: gitHubApi,
        config: gitHubConfig,
        actions: {
          initializeGitHub,
          loadUserRepos,
          loadIssues,
          loadPullRequests,
          loadCommits,
          loadReleases,
          createRepo,
          searchRepos,
          // Navigation Actions
          navigateToRepo: (repo: GitHubRepository) => {
            setState(prev => ({ ...prev, currentRepo: repo }));
            if (onRepoSelected) onRepoSelected(repo);
          },
          navigateToIssue: (issue: GitHubIssue) => {
            if (onIssueSelected) onIssueSelected(issue);
          },
          navigateToPR: (pr: GitHubPullRequest) => {
            if (onPRSelected) onPRSelected(pr);
          },
          navigateToCommit: (commit: GitHubCommit) => {
            if (onCommitSelected) onCommitSelected(commit);
          },
          // Search Actions
          searchIssues: async (query: string, filters?: any) => {
            return await gitHubApi.searchIssues(query, filters?.sort || 'created', filters?.order || 'desc');
          },
          searchCode: async (query: string, filters?: any) => {
            return await gitHubApi.searchCode(query, filters?.sort || 'indexed', filters?.order || 'desc');
          },
          searchUsers: async (query: string, filters?: any) => {
            return await gitHubApi.searchUsers(query, filters?.sort || 'followers', filters?.order || 'desc');
          },
          // UI Actions
          selectItems: (items: any[]) => {
            setState(prev => ({ ...prev, selectedItems: items }));
          },
          sortBy: (field: any, order: any) => {
            setState(prev => ({ ...prev, sortBy: field, sortOrder: order }));
          },
          setViewMode: (mode: 'grid' | 'list' | 'table') => {
            setState(prev => ({ ...prev, viewMode: mode }));
          },
          setFilters: (filters: any) => {
            setState(prev => ({ ...prev, filters }));
          },
          // Data Actions
          refresh: async () => {
            await Promise.all([
              loadUserRepos(),
              loadReleases(state.currentRepo?.full_name || ''),
            ]);
          },
          clearSelection: () => {
            setState(prev => ({ ...prev, selectedItems: [] }));
          }
        }
      });
    }

    // Default UI
    return (
      <div className={`atom-github-manager ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          💻 ATOM GitHub Manager
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Connection Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Connection Status</h3>
          <div className={`px-3 py-2 rounded text-sm font-medium ${
            state.connected ? 'bg-green-100 text-green-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {state.connected ? 'Connected to GitHub' : 'Not Connected'}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.repositories.length}
            </div>
            <div className="text-sm text-gray-500">Repositories</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.issues.length}
            </div>
            <div className="text-sm text-gray-500">Issues</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.pullRequests.length}
            </div>
            <div className="text-sm text-gray-500">Pull Requests</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-orange-600">
              {state.commits.length}
            </div>
            <div className="text-sm text-gray-500">Commits</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-indigo-600">
              {state.searchResults.total_count}
            </div>
            <div className="text-sm text-gray-500">Search Results</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Quick Actions</h3>
          <div className="flex space-x-2">
            <button
              onClick={initializeGitHub}
              disabled={state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Connect
            </button>
            <button
              onClick={() => loadUserRepos()}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Load Repos
            </button>
            <button
              onClick={() => state.currentRepo && loadIssues(state.currentRepo.full_name)}
              disabled={!state.connected || state.loading || !state.currentRepo}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Load Issues
            </button>
            <button
              onClick={() => state.currentRepo && loadPullRequests(state.currentRepo.full_name)}
              disabled={!state.connected || state.loading || !state.currentRepo}
              className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
            >
              Load PRs
            </button>
          </div>
        </div>

        {/* Configuration */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Configuration</h3>
          <div className="text-sm space-y-1">
            <div>Include Private: {gitHubConfig.includePrivate ? 'Yes' : 'No'}</div>
            <div>Include Forks: {gitHubConfig.includeForks ? 'Yes' : 'No'}</div>
            <div>Include Archived: {gitHubConfig.includeArchived ? 'Yes' : 'No'}</div>
            <div>Min Stars: {gitHubConfig.minStars}</div>
            <div>Max Issues Per Repo: {gitHubConfig.maxIssuesPerRepo}</div>
            <div>Max Commits Per Repo: {gitHubConfig.maxCommitsPerRepo}</div>
            <div>Max File Size: {(gitHubConfig.maxFileSize / 1024 / 1024).toFixed(1)}MB</div>
            <div>API Calls Per Hour: {gitHubConfig.apiCallsPerHour}</div>
          </div>
        </div>

        {/* Rate Limit Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Rate Limit Status</h3>
          <div className="text-sm">
            <div>Calls Used: {apiCallCount} / {gitHubConfig.apiCallsPerHour}</div>
            <div>Resets In: {Math.ceil((rateLimitReset - Date.now()) / 1000 / 60)} minutes</div>
          </div>
        </div>

        {/* Error Display */}
        {state.error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded">
            <p className="text-red-700 text-sm">{state.error}</p>
          </div>
        )}
      </div>
    );
  };

  return renderContent();
};

export default ATOMGitHubManager;
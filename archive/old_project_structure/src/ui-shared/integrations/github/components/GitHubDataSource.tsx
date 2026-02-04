/**
 * ATOM GitHub Data Source - TypeScript
 * Development → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomGitHubDataSourceProps, 
  AtomGitHubDataSourceState,
  AtomGitHubIngestionConfig,
  AtomGitHubDataSource,
  GitHubRepository,
  GitHubIssue,
  GitHubPullRequest,
  GitHubCommit,
  GitHubUser,
  GitHubRelease,
  GitHubFile,
  GitHubComment,
  GitHubRepositoryEnhanced,
  GitHubIssueEnhanced,
  GitHubPullRequestEnhanced,
  GitHubCommitEnhanced
} from '../types';

export const ATOMGitHubDataSource: React.FC<AtomGitHubDataSourceProps> = ({
  // GitHub Authentication
  personalAccessToken,
  oauthToken,
  onTokenRefresh,
  
  // Existing ATOM Pipeline Integration
  atomIngestionPipeline,
  dataSourceRegistry,
  
  // Data Source Configuration
  config = {},
  platform = 'auto',
  theme = 'auto',
  
  // Events
  onDataSourceReady,
  onIngestionStart,
  onIngestionComplete,
  onIngestionProgress,
  onDataSourceError,
  
  // Children
  children
}) => {
  
  // State Management
  const [state, setState] = useState<AtomGitHubDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    dataSource: null,
    ingestionStatus: 'idle',
    lastIngestionTime: null,
    discoveredRepositories: [],
    discoveredIssues: [],
    discoveredPullRequests: [],
    discoveredCommits: [],
    discoveredFiles: [],
    discoveredComments: [],
    discoveredReleases: [],
    ingestionQueue: [],
    processingIngestion: false,
    stats: {
      totalRepositories: 0,
      totalIssues: 0,
      totalPullRequests: 0,
      totalCommits: 0,
      totalFiles: 0,
      totalComments: 0,
      totalReleases: 0,
      ingestedRepositories: 0,
      ingestedIssues: 0,
      failedIngestions: 0,
      lastSyncTime: null,
      dataSize: 0
    }
  });

  // Configuration
  const [dataSourceConfig] = useState<AtomGitHubIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'github-integration',
    sourceName: 'GitHub',
    sourceType: 'github',
    
    // API Configuration
    apiBaseUrl: 'https://api.github.com',
    graphqlUrl: 'https://api.github.com/graphql',
    personalAccessToken: personalAccessToken,
    oauthToken: oauthToken,
    
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
    maxFileSize: config.maxFileSize ?? 10 * 1024 * 1024, // 10MB
    
    // Commit Discovery
    includeCommits: config.includeCommits ?? true,
    commitDateRange: config.commitDateRange,
    maxCommitsPerRepo: config.maxCommitsPerRepo ?? 1000,
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 1800000, // 30 minutes
    realTimeIngest: true,
    batchSize: 50,
    maxConcurrentIngestions: 2,
    
    // Processing
    extractMarkdown: true,
    includeCodeAnalysis: true,
    includeComments: true,
    chunkSize: 1000,
    chunkOverlap: 100,
    
    // Sync Settings
    useWebhooks: true,
    webhookEvents: config.webhookEvents ?? ['push', 'issues', 'pull_request', 'release'],
    webhookSecret: config.webhookSecret,
    syncInterval: 600000, // 10 minutes
    incrementalSync: true,
    
    // Pipeline Integration
    pipelineConfig: {
      targetTable: 'atom_memory',
      embeddingModel: 'text-embedding-3-large',
      embeddingDimension: 3072,
      indexType: 'IVF_FLAT',
      numPartitions: 256
    },
    
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
    return apiCallCount < 5000; // GitHub rate limit for authenticated requests
  }, [apiCallCount, rateLimitReset]);

  const incrementApiCall = useCallback(() => {
    setApiCallCount(prev => prev + 1);
  }, []);

  // GitHub API Integration (simplified for data source)
  const gitHubApi = useMemo(() => {
    const authToken = dataSourceConfig.personalAccessToken || dataSourceConfig.oauthToken;
    const headers: Record<string, string> = {
      'Accept': 'application/vnd.github.v3+json',
      'Authorization': `token ${authToken}`,
      'User-Agent': 'ATOM-Agent/1.0'
    };

    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      // Rate limiting
      if (!checkRateLimit()) {
        throw new Error('GitHub API rate limit exceeded. Please try again later.');
      }
      
      const url = `${dataSourceConfig.apiBaseUrl}${endpoint}`;
      
      try {
        const response = await fetch(url, {
          ...options,
          headers: {
            ...headers,
            ...options.headers as Record<string, string>
          }
        });

        incrementApiCall();

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
          token_type: 'Bearer'
        };
      },
      
      // Repository Operations
      getUserRepos: async (username, type = 'all', sort = 'updated', direction = 'desc') => {
        const endpoint = username 
          ? `/users/${username}/repos`
          : '/user/repos';
        
        return await makePaginatedRequest<GitHubRepository>(
          `${endpoint}?type=${type}&sort=${sort}&direction=${direction}`
        );
      },
      
      getOrgRepos: async (org, type = 'all', sort = 'updated', direction = 'desc') => {
        return await makePaginatedRequest<GitHubRepository>(
          `/orgs/${org}/repos?type=${type}&sort=${sort}&direction=${direction}`
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
      
      // Issue Operations
      getIssues: async (owner: string, repo: string, state = 'all') => {
        return await makePaginatedRequest<GitHubIssue>(
          `/repos/${owner}/${repo}/issues?state=${state}`
        );
      },
      
      getIssue: async (owner: string, repo: string, issueNumber: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/issues/${issueNumber}`);
      },
      
      // Pull Request Operations
      getPullRequests: async (owner: string, repo: string, state = 'all') => {
        return await makePaginatedRequest<GitHubPullRequest>(
          `/repos/${owner}/${repo}/pulls?state=${state}`
        );
      },
      
      getPullRequest: async (owner: string, repo: string, prNumber: number) => {
        return await makeRequest(`/repos/${owner}/${repo}/pulls/${prNumber}`);
      },
      
      // Commit Operations
      getCommits: async (owner: string, repo: string) => {
        return await makePaginatedRequest<GitHubCommit>(
          `/repos/${owner}/${repo}/commits`
        );
      },
      
      getCommit: async (owner: string, repo: string, sha: string) => {
        return await makeRequest(`/repos/${owner}/${repo}/commits/${sha}`);
      },
      
      // Comment Operations
      getIssueComments: async (owner: string, repo: string, issueNumber: number) => {
        return await makePaginatedRequest<GitHubComment>(
          `/repos/${owner}/${repo}/issues/${issueNumber}/comments`
        );
      },
      
      getPRComments: async (owner: string, repo: string, prNumber: number) => {
        return await makePaginatedRequest<GitHubComment>(
          `/repos/${owner}/${repo}/pulls/${prNumber}/comments`
        );
      },
      
      // Release Operations
      getReleases: async (owner: string, repo: string) => {
        return await makePaginatedRequest<GitHubRelease>(
          `/repos/${owner}/${repo}/releases`
        );
      },
      
      // Search Operations
      searchRepos: async (query: string, sort = 'stars', order = 'desc') => {
        return await makeRequest(`/search/repositories?q=${encodeURIComponent(query)}&sort=${sort}&order=${order}`);
      },
      
      searchIssues: async (query: string, sort = 'created', order = 'desc') => {
        return await makeRequest(`/search/issues?q=${encodeURIComponent(query)}&sort=${sort}&order=${order}`);
      },
      
      // User Operations
      getCurrentUser: async () => {
        return await makeRequest('/user');
      }
    };
  }, [dataSourceConfig, checkRateLimit, incrementApiCall]);

  // Extract Text from File
  const extractTextFromFile = async (blob: Blob, fileName: string, contentType: string): Promise<string> => {
    try {
      switch (contentType) {
        case 'text/plain':
        case 'text/markdown':
        case 'text/html':
        case 'text/css':
        case 'text/csv':
        case 'application/json':
        case 'application/xml':
        case 'text/yaml':
        case 'text/x-yaml':
        case 'application/x-yaml':
        case 'text/x-yml':
        case 'application/x-yml':
        case 'text/javascript':
        case 'application/javascript':
        case 'text/typescript':
        case 'application/x-typescript':
        case 'text/jsx':
        case 'text/tsx':
        case 'text/x-python':
        case 'text/x-java':
        case 'text/x-c':
        case 'text/x-c++':
        case 'text/x-csharp':
        case 'text/x-php':
        case 'text/x-ruby':
        case 'text/x-go':
        case 'text/x-rust':
        case 'text/x-shellscript':
        case 'application/x-sh':
        case 'text/x-dockerfile':
        case 'application/dockerfile':
        case 'text/x-sql':
        case 'application/sql':
          return await blob.text();
          
        case 'application/pdf':
          return `[PDF content extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'application/msword':
        case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
          return `[Word document content extraction not implemented - Size: ${blob.size} bytes]`;
          
        default:
          console.warn(`Text extraction not supported for content type: ${contentType}`);
          return '';
      }
    } catch (error) {
      console.error(`Error extracting text from ${fileName}:`, error);
      return '';
    }
  };

  // Process Repository Content
  const processRepositoryContent = async (repo: GitHubRepository): Promise<{
    readmeContent?: string;
    languageStats?: Record<string, number>;
    contributorCount?: number;
    lastActivity?: string;
  }> => {
    const [owner, repoName] = repo.full_name.split('/');
    
    try {
      // Get README content
      let readmeContent: string | undefined;
      try {
        const readmeFile = await gitHubApi.getRepoContent(owner, repoName, 'README.md');
        if (readmeFile && 'content' in readmeFile && readmeFile.content) {
          readmeContent = Buffer.from(readmeFile.content, 'base64').toString('utf-8');
        }
      } catch (error) {
        console.log(`No README.md found for ${repo.full_name}`);
      }
      
      // Get language stats
      let languageStats: Record<string, number> = {};
      try {
        const repoDetails = await gitHubApi.getRepo(owner, repoName);
        if (repoDetails.languages_url) {
          const langResponse = await fetch(repoDetails.languages_url, {
            headers: {
              'Authorization': `token ${dataSourceConfig.personalAccessToken || dataSourceConfig.oauthToken}`,
              'User-Agent': 'ATOM-Agent/1.0'
            }
          });
          if (langResponse.ok) {
            languageStats = await langResponse.json();
          }
        }
      } catch (error) {
        console.log(`Could not fetch language stats for ${repo.full_name}`);
      }
      
      return {
        readmeContent,
        languageStats,
        contributorCount: repo.forks_count, // Simplified
        lastActivity: repo.updated_at
      };
    } catch (error) {
      console.error(`Error processing repository ${repo.full_name}:`, error);
      return {};
    }
  };

  // Register GitHub as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Create GitHub data source configuration
      const gitHubDataSource: AtomGitHubDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'github',
        config: dataSourceConfig,
        authentication: {
          type: 'token',
          accessToken: dataSourceConfig.personalAccessToken || dataSourceConfig.oauthToken,
          tokenType: 'Bearer'
        },
        capabilities: {
          fileDiscovery: true,
          realTimeSync: true,
          incrementalSync: true,
          batchProcessing: true,
          metadataExtraction: true,
          previewGeneration: false,
          textExtraction: true
        },
        status: 'active',
        createdAt: new Date(),
        lastUpdated: new Date()
      };
      
      // Register with existing ATOM pipeline
      if (atomIngestionPipeline && atomIngestionPipeline.registerDataSource) {
        await atomIngestionPipeline.registerDataSource(gitHubDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(gitHubDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: gitHubDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(gitHubDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register GitHub data source: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'registration');
      }
    }
  }, [dataSourceConfig, atomIngestionPipeline, dataSourceRegistry, onDataSourceReady, onDataSourceError]);

  // Discover Repositories
  const discoverRepos = useCallback(async (username?: string, org?: string): Promise<GitHubRepositoryEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let allRepos: GitHubRepository[] = [];
      
      // Get repositories
      if (username) {
        allRepos = await gitHubApi.getUserRepos(username);
      } else if (org) {
        allRepos = await gitHubApi.getOrgRepos(org);
      } else {
        allRepos = await gitHubApi.getUserRepos();
      }
      
      // Filter repositories based on configuration
      const filteredRepos = allRepos.filter(repo => {
        // Check if repository is explicitly included
        if (dataSourceConfig.includedRepos.length > 0) {
          return dataSourceConfig.includedRepos.includes(repo.full_name);
        }
        
        // Check if repository is excluded
        if (dataSourceConfig.excludedRepos.includes(repo.full_name)) {
          return false;
        }
        
        // Check privacy
        if (!dataSourceConfig.includePrivate && repo.private) {
          return false;
        }
        
        // Check archived
        if (!dataSourceConfig.includeArchived && repo.archived) {
          return false;
        }
        
        // Check forks
        if (!dataSourceConfig.includeForks && repo.fork) {
          return false;
        }
        
        // Check stars
        if (repo.stargazers_count < (dataSourceConfig.minStars || 0)) {
          return false;
        }
        
        // Check size
        if (repo.size < (dataSourceConfig.minSize || 0)) {
          return false;
        }
        
        // Check language
        if (dataSourceConfig.repoLanguages.length > 0 && repo.language) {
          return dataSourceConfig.repoLanguages.includes(repo.language);
        }
        
        return true;
      });
      
      // Process repositories
      const enhancedRepos = await Promise.all(
        filteredRepos.map(async (repo) => {
          const { readmeContent, languageStats, contributorCount, lastActivity } = await processRepositoryContent(repo);
          
          return {
            ...repo,
            source: 'github' as const,
            discoveredAt: new Date().toISOString(),
            processedAt: undefined,
            issuesProcessed: false,
            commitsProcessed: false,
            codeProcessed: false,
            embeddingGenerated: false,
            ingested: false,
            ingestionTime: undefined,
            documentId: undefined,
            vectorCount: undefined,
            languageStats,
            contributorCount,
            lastActivity,
            readmeContent,
            codebaseInfo: {
              totalFiles: 0, // Would need additional API calls
              totalLines: 0,
              languages: languageStats,
              fileTypes: {}, // Would need additional API calls
              dependencies: [], // Would need additional API calls
              hasTests: false,
              hasCI: false,
              hasDocs: !!readmeContent,
              lastUpdated: repo.updated_at
            }
          };
        })
      );
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredRepositories: enhancedRepos,
        stats: {
          ...prev.stats,
          totalRepositories: enhancedRepos.length
        }
      }));
      
      return enhancedRepos;
      
    } catch (error) {
      const errorMessage = `Repository discovery failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'discovery');
      }
      
      return [];
    }
  }, [gitHubApi, dataSourceConfig, onDataSourceError]);

  // Discover Issues
  const discoverIssues = useCallback(async (repos: string[]): Promise<GitHubIssueEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let allIssues: GitHubIssueEnhanced[] = [];
      
      for (const repoFullName of repos) {
        try {
          const [owner, repoName] = repoFullName.split('/');
          const issues = await gitHubApi.getIssues(owner, repoName, 'all');
          
          // Filter out pull requests (GitHub API returns both)
          const regularIssues = issues.filter(issue => !issue.pull_request);
          
          // Process issues
          const enhancedIssues = regularIssues.map((issue) => {
            const markdownContent = `# ${issue.title}\n\n${issue.body || ''}`;
            const plainTextContent = `${issue.title}\n\n${issue.body || ''}`;
            
            return {
              ...issue,
              source: 'github' as const,
              discoveredAt: new Date().toISOString(),
              processedAt: undefined,
              commentsProcessed: false,
              reactionsProcessed: false,
              embeddingGenerated: false,
              ingested: false,
              ingestionTime: undefined,
              documentId: undefined,
              vectorCount: undefined,
              commentInfo: {
                totalComments: issue.comments,
                processedComments: [],
                totalAuthors: [],
                lastCommentDate: undefined,
                totalReactions: 0
              },
              reactionInfo: {
                totalReactions: 0,
                reactionsByType: {},
                reactors: []
              },
              markdownContent,
              plainTextContent
            };
          });
          
          allIssues.push(...enhancedIssues);
        } catch (error) {
          console.error(`Failed to discover issues for ${repoFullName}:`, error);
        }
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredIssues: allIssues,
        stats: {
          ...prev.stats,
          totalIssues: allIssues.length
        }
      }));
      
      return allIssues;
      
    } catch (error) {
      const errorMessage = `Issue discovery failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'discovery');
      }
      
      return [];
    }
  }, [gitHubApi, onDataSourceError]);

  // Discover Pull Requests
  const discoverPullRequests = useCallback(async (repos: string[]): Promise<GitHubPullRequestEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let allPRs: GitHubPullRequestEnhanced[] = [];
      
      for (const repoFullName of repos) {
        try {
          const [owner, repoName] = repoFullName.split('/');
          const pullRequests = await gitHubApi.getPullRequests(owner, repoName, 'all');
          
          // Process pull requests
          const enhancedPRs = pullRequests.map((pr) => {
            const markdownContent = `# ${pr.title}\n\n${pr.body || ''}`;
            const plainTextContent = `${pr.title}\n\n${pr.body || ''}`;
            
            return {
              ...pr,
              source: 'github' as const,
              discoveredAt: new Date().toISOString(),
              processedAt: undefined,
              commentsProcessed: false,
              reviewsProcessed: false,
              embeddingGenerated: false,
              ingested: false,
              ingestionTime: undefined,
              documentId: undefined,
              vectorCount: undefined,
              commentInfo: {
                totalComments: pr.comments,
                processedComments: [],
                totalAuthors: [],
                lastCommentDate: undefined,
                totalReactions: 0
              },
              reviewInfo: {
                totalReviews: 0,
                processedReviews: [],
                totalReviewers: [],
                lastReviewDate: undefined
              },
              markdownContent,
              plainTextContent
            };
          });
          
          allPRs.push(...enhancedPRs);
        } catch (error) {
          console.error(`Failed to discover pull requests for ${repoFullName}:`, error);
        }
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredPullRequests: allPRs,
        stats: {
          ...prev.stats,
          totalPullRequests: allPRs.length
        }
      }));
      
      return allPRs;
      
    } catch (error) {
      const errorMessage = `Pull request discovery failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'discovery');
      }
      
      return [];
    }
  }, [gitHubApi, onDataSourceError]);

  // Discover Commits
  const discoverCommits = useCallback(async (repos: string[]): Promise<GitHubCommitEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let allCommits: GitHubCommitEnhanced[] = [];
      
      for (const repoFullName of repos) {
        try {
          const [owner, repoName] = repoFullName.split('/');
          const commits = await gitHubApi.getCommits(owner, repoName);
          
          // Process commits
          const enhancedCommits = commits.map((commit) => {
            const markdownContent = `# ${commit.sha.substring(0, 7)}\n\n${commit.commit.message}`;
            const plainTextContent = `${commit.sha.substring(0, 7)}\n\n${commit.commit.message}`;
            
            return {
              ...commit,
              source: 'github' as const,
              discoveredAt: new Date().toISOString(),
              processedAt: undefined,
              filesProcessed: false,
              embeddingGenerated: false,
              ingested: false,
              ingestionTime: undefined,
              documentId: undefined,
              vectorCount: undefined,
              fileStats: {
                totalFiles: commit.files?.length || 0,
                filesByType: {},
                totalAdditions: commit.stats?.additions || 0,
                totalDeletions: commit.stats?.deletions || 0,
                totalChanges: commit.stats?.total || 0,
                largestFile: undefined,
                mostChangedFile: undefined
              },
              markdownContent,
              plainTextContent
            };
          });
          
          allCommits.push(...enhancedCommits);
        } catch (error) {
          console.error(`Failed to discover commits for ${repoFullName}:`, error);
        }
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredCommits: allCommits,
        stats: {
          ...prev.stats,
          totalCommits: allCommits.length
        }
      }));
      
      return allCommits;
      
    } catch (error) {
      const errorMessage = `Commit discovery failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'discovery');
      }
      
      return [];
    }
  }, [gitHubApi, onDataSourceError]);

  // Ingest Repositories with Existing Pipeline
  const ingestRepos = useCallback(async (repos: GitHubRepositoryEnhanced[]): Promise<void> => {
    if (!atomIngestionPipeline || !state.dataSource) {
      throw new Error('ATOM ingestion pipeline not available');
    }
    
    try {
      setState(prev => ({
        ...prev,
        processingIngestion: true,
        ingestionStatus: 'processing'
      }));
      
      if (onIngestionStart) {
        onIngestionStart({
          dataSource: state.dataSource,
          reposCount: repos.length
        });
      }
      
      // Process repositories in batches
      const batchSize = dataSourceConfig.batchSize;
      let successCount = 0;
      let errorCount = 0;
      
      for (let i = 0; i < repos.length; i += batchSize) {
        const batch = repos.slice(i, i + batchSize);
        
        try {
          // Prepare batch for existing pipeline
          const preparedBatch = batch.map((repo) => {
            const content = repo.readmeContent || '';
            
            return {
              id: repo.id.toString(),
              sourceId: dataSourceConfig.sourceId,
              sourceName: dataSourceConfig.sourceName,
              sourceType: 'github',
              documentType: 'repository',
              title: repo.name,
              content: content,
              url: repo.html_url,
              timestamp: repo.created_at,
              author: repo.owner.login,
              tags: [
                'language:' + (repo.language || 'unknown'),
                'visibility:' + (repo.private ? 'private' : 'public'),
                'size:' + repo.size.toString(),
                'stars:' + repo.stargazers_count.toString(),
                ...(repo.topics || [])
              ],
              metadata: {
                githubRepo: repo,
                fullName: repo.full_name,
                description: repo.description,
                language: repo.language,
                topics: repo.topics,
                stars: repo.stargazers_count,
                forks: repo.forks_count,
                size: repo.size,
                isOpenSource: !repo.private,
                hasIssues: repo.has_issues,
                hasWiki: repo.has_wiki,
                hasPages: repo.has_pages,
                hasProjects: repo.has_projects,
                defaultBranch: repo.default_branch,
                languageStats: repo.languageStats,
                contributorCount: repo.contributorCount,
                lastActivity: repo.lastActivity,
                codebaseInfo: repo.codebaseInfo,
                extractedAt: new Date().toISOString()
              },
              content: content,
              chunkSize: dataSourceConfig.chunkSize,
              chunkOverlap: dataSourceConfig.chunkOverlap
            };
          });
          
          // Send batch to existing ATOM ingestion pipeline
          const batchResult = await atomIngestionPipeline.ingestBatch({
            dataSourceId: dataSourceConfig.sourceId,
            items: preparedBatch,
            config: dataSourceConfig.pipelineConfig
          });
          
          successCount += batchResult.successful;
          errorCount += batchResult.failed;
          
          // Update progress
          const progress = ((i + batchSize) / repos.length) * 100;
          
          if (onIngestionProgress) {
            onIngestionProgress({
              dataSource: state.dataSource,
              progress,
              processedCount: i + batchSize,
              totalCount: repos.length,
              successCount,
              errorCount,
              currentBatch: Math.floor(i / batchSize) + 1,
              totalBatches: Math.ceil(repos.length / batchSize)
            });
          }
          
          setState(prev => ({
            ...prev,
            stats: {
              ...prev.stats,
              ingestedRepositories: prev.stats.ingestedRepositories + batchResult.successful,
              failedIngestions: prev.stats.failedIngestions + batchResult.failed
            }
          }));
          
        } catch (batchError) {
          console.error('Batch ingestion error:', batchError);
          errorCount += batch.length;
        }
      }
      
      setState(prev => ({
        ...prev,
        processingIngestion: false,
        ingestionStatus: 'completed',
        lastIngestionTime: new Date()
      }));
      
      if (onIngestionComplete) {
        onIngestionComplete({
          dataSource: state.dataSource,
          successCount,
          errorCount,
          totalRepositories: repos.length,
          duration: Date.now() - (prev.lastIngestionTime?.getTime() || Date.now())
        });
      }
      
    } catch (error) {
      const errorMessage = `Repository ingestion failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        processingIngestion: false,
        ingestionStatus: 'failed',
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'ingestion');
      }
    }
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

  // Ingest Issues with Existing Pipeline
  const ingestIssues = useCallback(async (issues: GitHubIssueEnhanced[]): Promise<void> => {
    if (!atomIngestionPipeline || !state.dataSource) {
      throw new Error('ATOM ingestion pipeline not available');
    }
    
    try {
      setState(prev => ({
        ...prev,
        processingIngestion: true,
        ingestionStatus: 'processing'
      }));
      
      if (onIngestionStart) {
        onIngestionStart({
          dataSource: state.dataSource,
          issuesCount: issues.length
        });
      }
      
      // Process issues in batches
      const batchSize = dataSourceConfig.batchSize;
      let successCount = 0;
      let errorCount = 0;
      
      for (let i = 0; i < issues.length; i += batchSize) {
        const batch = issues.slice(i, i + batchSize);
        
        try {
          // Prepare batch for existing pipeline
          const preparedBatch = batch.map((issue) => {
            const content = dataSourceConfig.extractMarkdown ? issue.markdownContent : issue.plainTextContent;
            
            return {
              id: issue.id.toString(),
              sourceId: dataSourceConfig.sourceId,
              sourceName: dataSourceConfig.sourceName,
              sourceType: 'github',
              documentType: 'issue',
              title: issue.title,
              content: content,
              url: issue.html_url,
              timestamp: issue.created_at,
              author: issue.user.login,
              tags: [
                'state:' + issue.state,
                'type:' + 'issue',
                ...(issue.labels || []).map(label => 'label:' + label.name),
                'assignee:' + (issue.assignees?.map(a => a.login).join(',') || 'none'),
                'milestone:' + (issue.milestone?.title || 'none')
              ],
              metadata: {
                githubIssue: issue,
                issueNumber: issue.number,
                state: issue.state,
                milestone: issue.milestone?.title,
                assignees: issue.assignees?.map(a => a.login) || [],
                labels: issue.labels?.map(l => l.name) || [],
                comments: issue.comments,
                reactions: issue.reactions,
                closedAt: issue.closed_at,
                closedBy: issue.closed_by?.login,
                repositoryUrl: issue.repository_url,
                issueUrl: issue.url,
                htmlUrl: issue.html_url,
                authorAssociation: issue.author_association,
                commentInfo: issue.commentInfo,
                reactionInfo: issue.reactionInfo,
                extractedAt: new Date().toISOString()
              },
              content: content,
              chunkSize: dataSourceConfig.chunkSize,
              chunkOverlap: dataSourceConfig.chunkOverlap
            };
          });
          
          // Send batch to existing ATOM ingestion pipeline
          const batchResult = await atomIngestionPipeline.ingestBatch({
            dataSourceId: dataSourceConfig.sourceId,
            items: preparedBatch,
            config: dataSourceConfig.pipelineConfig
          });
          
          successCount += batchResult.successful;
          errorCount += batchResult.failed;
          
          // Update progress
          const progress = ((i + batchSize) / issues.length) * 100;
          
          if (onIngestionProgress) {
            onIngestionProgress({
              dataSource: state.dataSource,
              progress,
              processedCount: i + batchSize,
              totalCount: issues.length,
              successCount,
              errorCount,
              currentBatch: Math.floor(i / batchSize) + 1,
              totalBatches: Math.ceil(issues.length / batchSize)
            });
          }
          
          setState(prev => ({
            ...prev,
            stats: {
              ...prev.stats,
              ingestedIssues: prev.stats.ingestedIssues + batchResult.successful,
              failedIngestions: prev.stats.failedIngestions + batchResult.failed
            }
          }));
          
        } catch (batchError) {
          console.error('Batch ingestion error:', batchError);
          errorCount += batch.length;
        }
      }
      
      setState(prev => ({
        ...prev,
        processingIngestion: false,
        ingestionStatus: 'completed',
        lastIngestionTime: new Date()
      }));
      
      if (onIngestionComplete) {
        onIngestionComplete({
          dataSource: state.dataSource,
          successCount,
          errorCount,
          totalIssues: issues.length,
          duration: Date.now() - (prev.lastIngestionTime?.getTime() || Date.now())
        });
      }
      
    } catch (error) {
      const errorMessage = `Issue ingestion failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        processingIngestion: false,
        ingestionStatus: 'failed',
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'ingestion');
      }
    }
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

  // Sync Repositories
  const syncRepos = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Simplified sync - just discover new repositories
      const discoveredRepos = await discoverRepos();
      
      if (discoveredRepos.length > 0) {
        await ingestRepos(discoveredRepos);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        stats: {
          ...prev.stats,
          lastSyncTime: new Date()
        }
      }));
      
    } catch (error) {
      const errorMessage = `Sync failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'sync');
      }
    }
  }, [discoverRepos, ingestRepos, onDataSourceError]);

  // Initialize Data Source
  useEffect(() => {
    if ((dataSourceConfig.personalAccessToken || dataSourceConfig.oauthToken) && atomIngestionPipeline) {
      registerDataSource();
    }
  }, [dataSourceConfig.personalAccessToken, dataSourceConfig.oauthToken, atomIngestionPipeline, registerDataSource]);

  // Start Auto Ingestion
  useEffect(() => {
    if (!dataSourceConfig.autoIngest || !state.connected) {
      return;
    }
    
    // Initial discovery and ingestion
    const initializeAutoIngestion = async () => {
      // Discover repositories
      const discoveredRepos = await discoverRepos();
      
      if (discoveredRepos.length > 0) {
        await ingestRepos(discoveredRepos);
      }
      
      // Optionally discover and ingest issues
      if (dataSourceConfig.includeIssues && discoveredRepos.length > 0) {
        const issues = await discoverIssues(discoveredRepos.map(r => r.full_name));
        if (issues.length > 0) {
          await ingestIssues(issues);
        }
      }
    };
    
    initializeAutoIngestion();
    
    // Set up periodic ingestion
    const ingestionInterval = setInterval(async () => {
      if (dataSourceConfig.incrementalSync) {
        await syncRepos();
      } else {
        const discoveredRepos = await discoverRepos();
        if (discoveredRepos.length > 0) {
          await ingestRepos(discoveredRepos);
        }
      }
    }, dataSourceConfig.ingestInterval);
    
    // Set up periodic sync
    const syncInterval = setInterval(() => {
      syncRepos();
    }, dataSourceConfig.syncInterval);
    
    return () => {
      clearInterval(ingestionInterval);
      clearInterval(syncInterval);
    };
  }, [dataSourceConfig, state.connected, discoverRepos, discoverIssues, ingestRepos, ingestIssues, syncRepos]);

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
        actions: {
          discoverRepos,
          discoverIssues,
          discoverPullRequests,
          discoverCommits,
          ingestRepos,
          ingestIssues,
          syncRepos,
          registerDataSource
        },
        config: dataSourceConfig,
        dataSource: state.dataSource
      });
    }

    // Default UI
    return (
      <div className={`atom-github-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          💻 ATOM GitHub Data Source
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Status Overview */}
        <div className="grid grid-cols-7 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.stats.totalRepositories}
            </div>
            <div className="text-sm text-gray-500">Repositories</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.stats.totalIssues}
            </div>
            <div className="text-sm text-gray-500">Issues</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.stats.totalPullRequests}
            </div>
            <div className="text-sm text-gray-500">Pull Requests</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-orange-600">
              {state.stats.totalCommits}
            </div>
            <div className="text-sm text-gray-500">Commits</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-indigo-600">
              {state.stats.totalFiles}
            </div>
            <div className="text-sm text-gray-500">Files</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-pink-600">
              {state.stats.totalComments}
            </div>
            <div className="text-sm text-gray-500">Comments</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-teal-600">
              {state.stats.ingestedRepositories + state.stats.ingestedIssues}
            </div>
            <div className="text-sm text-gray-500">Ingested</div>
          </div>
        </div>

        {/* Data Source Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Data Source Status</h3>
          <div className={`px-3 py-2 rounded text-sm font-medium ${
            state.connected ? 'bg-green-100 text-green-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {state.connected ? 'Connected & Registered' : 'Not Connected'}
          </div>
        </div>

        {/* Ingestion Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Ingestion Status</h3>
          <div className={`px-3 py-2 rounded text-sm font-medium ${
            state.ingestionStatus === 'processing' ? 'bg-blue-100 text-blue-800' :
            state.ingestionStatus === 'completed' ? 'bg-green-100 text-green-800' :
            state.ingestionStatus === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {state.ingestionStatus.charAt(0).toUpperCase() + state.ingestionStatus.slice(1)}
          </div>
          {state.lastIngestionTime && (
            <div className="text-xs text-gray-500 mt-1">
              Last ingestion: {state.lastIngestionTime.toLocaleString()}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Quick Actions</h3>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => discoverRepos()}
              disabled={!state.connected || state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Discover Repos
            </button>
            <button
              onClick={() => state.discoveredRepositories.length > 0 && discoverIssues(state.discoveredRepositories.map(r => r.full_name))}
              disabled={!state.connected || state.loading || state.discoveredRepositories.length === 0}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Discover Issues
            </button>
            <button
              onClick={() => state.discoveredRepositories.length > 0 && discoverPullRequests(state.discoveredRepositories.map(r => r.full_name))}
              disabled={!state.connected || state.loading || state.discoveredRepositories.length === 0}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Discover PRs
            </button>
            <button
              onClick={() => state.discoveredRepositories.length > 0 && discoverCommits(state.discoveredRepositories.map(r => r.full_name))}
              disabled={!state.connected || state.loading || state.discoveredRepositories.length === 0}
              className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
            >
              Discover Commits
            </button>
            <button
              onClick={() => ingestRepos(state.discoveredRepositories)}
              disabled={!state.connected || state.processingIngestion || state.discoveredRepositories.length === 0}
              className="bg-indigo-500 text-white px-4 py-2 rounded hover:bg-indigo-600 disabled:bg-indigo-300"
            >
              Ingest Repos
            </button>
            <button
              onClick={() => ingestIssues(state.discoveredIssues)}
              disabled={!state.connected || state.processingIngestion || state.discoveredIssues.length === 0}
              className="bg-pink-500 text-white px-4 py-2 rounded hover:bg-pink-600 disabled:bg-pink-300"
            >
              Ingest Issues
            </button>
            <button
              onClick={syncRepos}
              disabled={!state.connected || state.loading}
              className="bg-teal-500 text-white px-4 py-2 rounded hover:bg-teal-600 disabled:bg-teal-300"
            >
              Sync Now
            </button>
          </div>
        </div>

        {/* Configuration */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Configuration</h3>
          <div className="text-sm space-y-1">
            <div>Auto Ingest: {dataSourceConfig.autoIngest ? 'Enabled' : 'Disabled'}</div>
            <div>Ingestion Interval: {(dataSourceConfig.ingestInterval / 60000).toFixed(0)} minutes</div>
            <div>Sync Interval: {(dataSourceConfig.syncInterval / 60000).toFixed(0)} minutes</div>
            <div>Batch Size: {dataSourceConfig.batchSize}</div>
            <div>Include Private: {dataSourceConfig.includePrivate ? 'Yes' : 'No'}</div>
            <div>Include Forks: {dataSourceConfig.includeForks ? 'Yes' : 'No'}</div>
            <div>Include Archived: {dataSourceConfig.includeArchived ? 'Yes' : 'No'}</div>
            <div>Min Stars: {dataSourceConfig.minStars}</div>
            <div>Min Size: {dataSourceConfig.minSize}KB</div>
            <div>Include Issues: {dataSourceConfig.includeIssues ? 'Yes' : 'No'}</div>
            <div>Include Pull Requests: {dataSourceConfig.includePullRequests ? 'Yes' : 'No'}</div>
            <div>Include Commits: {dataSourceConfig.includeCommits ? 'Yes' : 'No'}</div>
            <div>Include Code: {dataSourceConfig.includeCode ? 'Yes' : 'No'}</div>
            <div>Max File Size: {(dataSourceConfig.maxFileSize / 1024 / 1024).toFixed(1)}MB</div>
          </div>
        </div>

        {/* Rate Limit Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Rate Limit Status</h3>
          <div className="text-sm">
            <div>Calls Used: {apiCallCount} / 5000</div>
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

export default ATOMGitHubDataSource;
/**
 * ATOM GitHub Integration - TypeScript Types
 * Development → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// GitHub API Types
export interface GitHubUser {
  id: number;
  login: string;
  node_id: string;
  avatar_url: string;
  gravatar_id: string;
  url: string;
  html_url: string;
  followers_url: string;
  following_url: string;
  gists_url: string;
  starred_url: string;
  subscriptions_url: string;
  organizations_url: string;
  repos_url: string;
  events_url: string;
  received_events_url: string;
  type: 'User' | 'Bot';
  site_admin: boolean;
  name?: string;
  company?: string;
  blog?: string;
  location?: string;
  email?: string;
  hireable?: boolean;
  bio?: string;
  twitter_username?: string;
  public_repos: number;
  public_gists: number;
  followers: number;
  following: number;
  created_at: string;
  updated_at: string;
}

export interface GitHubRepository {
  id: number;
  node_id: string;
  name: string;
  full_name: string;
  private: boolean;
  owner: GitHubUser;
  html_url: string;
  description?: string;
  fork: boolean;
  url: string;
  archive_url: string;
  assignees_url: string;
  blobs_url: string;
  branches_url: string;
  collaborators_url: string;
  comments_url: string;
  commits_url: string;
  compare_url: string;
  contents_url: string;
  contributors_url: string;
  deployments_url: string;
  downloads_url: string;
  events_url: string;
  forks_url: string;
  git_commits_url: string;
  git_refs_url: string;
  git_tags_url: string;
  git_url: string;
  issue_comment_url: string;
  issue_events_url: string;
  issues_url: string;
  keys_url: string;
  labels_url: string;
  languages_url: string;
  merges_url: string;
  milestones_url: string;
  notifications_url: string;
  pulls_url: string;
  releases_url: string;
  ssh_url: string;
  stargazers_url: string;
  statuses_url: string;
  subscribers_url: string;
  subscription_url: string;
  tags_url: string;
  teams_url: string;
  trees_url: string;
  clone_url: string;
  mirror_url: string;
  hooks_url: string;
  svn_url: string;
  homepage?: string;
  language?: string;
  forks_count: number;
  stargazers_count: number;
  watchers_count: number;
  size: number;
  default_branch: string;
  open_issues_count: number;
  topics?: string[];
  has_issues: boolean;
  has_projects: boolean;
  has_wiki: boolean;
  has_pages: boolean;
  has_downloads: boolean;
  archived: boolean;
  disabled: boolean;
  visibility: 'public' | 'private';
  pushed_at: string;
  created_at: string;
  updated_at: string;
  allow_rebase_merge: boolean;
  allow_merge_commit: boolean;
  allow_squash_merge: boolean;
  delete_branch_on_merge: boolean;
  subscribers_count: number;
  network_count: number;
  license?: GitHubLicense;
}

export interface GitHubLicense {
  key: string;
  name: string;
  spdx_id: string;
  url: string;
  node_id: string;
}

export interface GitHubIssue {
  id: number;
  node_id: string;
  url: string;
  repository_url: string;
  labels_url: string;
  comments_url: string;
  events_url: string;
  html_url: string;
  number: number;
  state: 'open' | 'closed';
  title: string;
  body?: string;
  user: GitHubUser;
  assignees: GitHubUser[];
  milestone?: GitHubMilestone;
  locked: boolean;
  comments: number;
  pull_request?: GitHubPullRequestReference;
  closed_at?: string;
  created_at: string;
  updated_at: string;
  closed_by?: GitHubUser;
  author_association: 'COLLABORATOR' | 'CONTRIBUTOR' | 'FIRST_TIMER' | 'FIRST_TIME_CONTRIBUTOR' | 'MANNEQUIN' | 'MEMBER' | 'NONE' | 'OWNER';
  labels: GitHubLabel[];
  reactions?: GitHubReactions;
}

export interface GitHubPullRequestReference {
  url: string;
  html_url: string;
  diff_url: string;
  patch_url: string;
}

export interface GitHubMilestone {
  url: string;
  html_url: string;
  labels_url: string;
  id: number;
  node_id: string;
  number: number;
  state: 'open' | 'closed';
  title: string;
  description?: string;
  creator: GitHubUser;
  open_issues: number;
  closed_issues: number;
  created_at: string;
  updated_at: string;
  closed_at?: string;
  due_on?: string;
}

export interface GitHubLabel {
  id: number;
  node_id: string;
  url: string;
  name: string;
  color: string;
  default: boolean;
  description?: string;
}

export interface GitHubReactions {
  url: string;
  total_count: number;
  plus_one: number;
  minus_one: number;
  laugh: number;
  hooray: number;
  confused: number;
  heart: number;
  rocket: number;
  eyes: number;
}

export interface GitHubPullRequest {
  id: number;
  node_id: string;
  url: string;
  html_url: string;
  diff_url: string;
  patch_url: string;
  issue_url: string;
  number: number;
  state: 'open' | 'closed';
  title: string;
  body?: string;
  user: GitHubUser;
  assignees: GitHubUser[];
  requested_reviewers?: GitHubUser[];
  requested_teams?: any[];
  labels: GitHubLabel[];
  milestone?: GitHubMilestone;
  locked: boolean;
  created_at: string;
  updated_at: string;
  closed_at?: string;
  merged_at?: string;
  merge_commit_sha?: string;
  assignee?: GitHubUser;
  reviewers?: GitHubUser[];
  mergeable?: boolean;
  merged: boolean;
  merged_by?: GitHubUser;
  comments: number;
  review_comments: number;
  maintainer_can_modify: boolean;
  commits: number;
  additions: number;
  deletions: number;
  changed_files: number;
  head: GitHubPullRequestBranch;
  base: GitHubPullRequestBranch;
  author_association: 'COLLABORATOR' | 'CONTRIBUTOR' | 'FIRST_TIMER' | 'FIRST_TIME_CONTRIBUTOR' | 'MANNEQUIN' | 'MEMBER' | 'NONE' | 'OWNER';
  draft: boolean;
  repo: {
    id: number;
    name: string;
    full_name: string;
    private: boolean;
    owner: GitHubUser;
  };
  base_repo?: GitHubRepository;
  head_repo?: GitHubRepository;
}

export interface GitHubPullRequestBranch {
  label: string;
  ref: string;
  sha: string;
  user: GitHubUser;
  repo?: GitHubRepository;
}

export interface GitHubCommit {
  sha: string;
  node_id: string;
  url: string;
  html_url: string;
  comments_url: string;
  commit: {
    url: string;
    author: GitHubCommitAuthor;
    committer: GitHubCommitAuthor;
    message: string;
    tree: {
      sha: string;
      url: string;
    };
    comment_count: number;
    verification?: GitHubVerification;
  };
  author?: GitHubUser;
  committer?: GitHubUser;
  parents: GitHubCommitParent[];
  stats?: {
    total: number;
    additions: number;
    deletions: number;
  };
  files?: GitHubCommitFile[];
}

export interface GitHubCommitAuthor {
  name: string;
  email: string;
  date: string;
}

export interface GitHubVerification {
  verified: boolean;
  reason: string;
  signature?: string;
  payload?: string;
}

export interface GitHubCommitParent {
  sha: string;
  url: string;
  html_url: string;
}

export interface GitHubCommitFile {
  sha: string;
  filename: string;
  status: 'added' | 'removed' | 'modified' | 'renamed' | 'copied' | 'changed' | 'unchanged';
  additions: number;
  deletions: number;
  changes: number;
  blob_url: string;
  raw_url: string;
  contents_url: string;
  patch?: string;
  previous_filename?: string;
}

export interface GitHubComment {
  id: number;
  node_id: string;
  url: string;
  html_url: string;
  issue_url?: string;
  pull_request_url?: string;
  body?: string;
  user: GitHubUser;
  created_at: string;
  updated_at: string;
  issue_url?: string;
  pull_request_url?: string;
  author_association: 'COLLABORATOR' | 'CONTRIBUTOR' | 'FIRST_TIMER' | 'FIRST_TIME_CONTRIBUTOR' | 'MANNEQUIN' | 'MEMBER' | 'NONE' | 'OWNER';
  reactions?: GitHubReactions;
}

export interface GitHubRelease {
  id: number;
  node_id: string;
  tag_name: string;
  target_commitish: string;
  name?: string;
  body?: string;
  draft: boolean;
  prerelease: boolean;
  created_at: string;
  published_at?: string;
  author: GitHubUser;
  assets: GitHubReleaseAsset[];
  url: string;
  html_url: string;
  upload_url: string;
  tarball_url: string;
  zipball_url: string;
  discussion_url?: string;
}

export interface GitHubReleaseAsset {
  url: string;
  browser_download_url: string;
  id: number;
  node_id: string;
  name: string;
  label?: string;
  state: 'uploaded' | 'open';
  content_type: string;
  size: number;
  download_count: number;
  created_at: string;
  updated_at: string;
  uploader: GitHubUser;
}

export interface GitHubFile {
  name: string;
  path: string;
  sha: string;
  size: number;
  url: string;
  html_url: string;
  git_url: string;
  download_url?: string;
  type: 'file' | 'dir' | 'submodule' | 'symlink';
  content?: string;
  encoding?: string;
  target?: string;
  submodule_git_url?: string;
  license?: GitHubLicense;
}

export interface GitHubSearchResponse<T> {
  total_count: number;
  incomplete_results: boolean;
  items: T[];
}

export interface GitHubWebhook {
  id: number;
  url: string;
  test_url?: string;
  ping_url?: string;
  name: string;
  events: GitHubWebhookEvent[];
  active: boolean;
  created_at: string;
  updated_at: string;
  last_response?: GitHubWebhookResponse;
  config: {
    content_type: string;
    insecure_ssl: boolean;
    url: string;
    secret?: string;
    digest?: string;
    correlation_id?: string;
    auth?: {
      type: string;
      token?: string;
      secret?: string;
    };
  };
}

export type GitHubWebhookEvent = 
  | 'push'
  | 'commit_comment'
  | 'create'
  | 'delete'
  | 'deployment'
  | 'deployment_status'
  | 'fork'
  | 'gollum'
  | 'issue_comment'
  | 'issues'
  | 'label'
  | 'member'
  | 'membership'
  | 'milestone'
  | 'organization'
  | 'org_block'
  | 'page_build'
  | 'project'
  | 'project_card'
  | 'project_column'
  | 'public'
  | 'pull_request'
  | 'pull_request_review'
  | 'pull_request_review_comment'
  | 'push'
  | 'release'
  | 'repository'
  | 'repository_dispatch'
  | 'schedule'
  | 'status'
  | 'team_add'
  | 'watch'
  | 'workflow_dispatch'
  | 'workflow_run';

export interface GitHubWebhookResponse {
  code: number;
  status: string;
  message: string;
  errors?: string[];
}

export interface GitHubWorkflowRun {
  id: number;
  name: string;
  head_branch: string;
  head_sha: string;
  status: 'queued' | 'in_progress' | 'completed';
  conclusion: 'success' | 'failure' | 'neutral' | 'cancelled' | 'skipped' | 'timed_out' | 'action_required' | null;
  workflow_id: number;
  url: string;
  html_url: string;
  created_at: string;
  updated_at: string;
  run_number: number;
  event: string;
  workflow: {
    id: number;
    name: string;
    path: string;
    state: 'active' | 'deleted' | 'disabled_fork';
    badge_url?: string;
    created_at: string;
    updated_at: string;
  };
  jobs_url: string;
  logs_url: string;
  check_suite_url: string;
  artifacts_url: string;
  cancel_url: string;
  rerun_url: string;
  previous_attempt_url?: string;
  head_repository?: {
    id: number;
    name: string;
    full_name: string;
    private: boolean;
    owner: GitHubUser;
  };
  head_commit?: {
    id: string;
    tree_id: string;
    message: string;
    timestamp: string;
    author: {
      name: string;
      email: string;
    };
    committer: {
      name: string;
      email: string;
    };
  };
  repository: GitHubRepository;
  actor: GitHubUser;
}

// GitHub Configuration Types
export interface GitHubConfig {
  // API Configuration
  apiBaseUrl: string;
  graphqlUrl: string;
  
  // Authentication
  personalAccessToken?: string;
  clientId?: string;
  clientSecret?: string;
  oauthToken?: string;
  
  // Repository Discovery
  includePrivate: boolean;
  includeArchived: boolean;
  includeForks: boolean;
  includedRepos: string[];
  excludedRepos: string[];
  repoLanguages: string[];
  minStars?: number;
  minSize?: number;
  
  // Issue Discovery
  includeIssues: boolean;
  includePullRequests: boolean;
  includeClosed: boolean;
  issueDateRange?: {
    start: Date;
    end: Date;
  };
  maxIssuesPerRepo: number;
  
  // Code Discovery
  includeCode: boolean;
  includeDocumentation: boolean;
  includeTests: boolean;
  includedFileTypes: string[];
  excludedFileTypes: string[];
  maxFileSize: number;
  
  // Commit Discovery
  includeCommits: boolean;
  commitDateRange?: {
    start: Date;
    end: Date;
  };
  maxCommitsPerRepo: number;
  
  // Search Settings
  searchQuery?: string;
  searchType: 'repositories' | 'issues' | 'code' | 'users' | 'commits';
  maxSearchResults: number;
  
  // Real-time Settings
  useWebhooks: boolean;
  webhookEvents: GitHubWebhookEvent[];
  webhookSecret?: string;
  
  // Rate Limiting
  apiCallsPerHour: number;
  useRateLimiter: boolean;
  
  // Platform-specific
  tauriCommands?: {
    downloadFile: string;
    cloneRepo: string;
  };
}

// Enhanced Types
export interface GitHubRepositoryEnhanced extends GitHubRepository {
  source: 'github';
  discoveredAt: string;
  processedAt?: string;
  issuesProcessed?: boolean;
  commitsProcessed?: boolean;
  codeProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  languageStats?: Record<string, number>;
  contributorCount?: number;
  lastActivity?: string;
  readmeContent?: string;
  codebaseInfo?: GitHubCodebaseInfo;
}

export interface GitHubIssueEnhanced extends GitHubIssue {
  source: 'github';
  discoveredAt: string;
  processedAt?: string;
  commentsProcessed?: boolean;
  reactionsProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  commentInfo?: GitHubCommentInfo;
  reactionInfo?: GitHubReactionInfo;
  markdownContent?: string;
  plainTextContent?: string;
}

export interface GitHubPullRequestEnhanced extends GitHubPullRequest {
  source: 'github';
  discoveredAt: string;
  processedAt?: string;
  commentsProcessed?: boolean;
  reviewsProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  commentInfo?: GitHubCommentInfo;
  reviewInfo?: GitHubReviewInfo;
  markdownContent?: string;
  plainTextContent?: string;
}

export interface GitHubCommitEnhanced extends GitHubCommit {
  source: 'github';
  discoveredAt: string;
  processedAt?: string;
  filesProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  fileStats?: GitHubFileStats;
  markdownContent?: string;
  plainTextContent?: string;
}

export interface GitHubCodebaseInfo {
  totalFiles: number;
  totalLines: number;
  languages: Record<string, number>;
  fileTypes: Record<string, number>;
  dependencies?: string[];
  hasTests: boolean;
  hasCI: boolean;
  hasDocs: boolean;
  lastUpdated: string;
}

export interface GitHubCommentInfo {
  totalComments: number;
  processedComments: GitHubComment[];
  totalAuthors: string[];
  lastCommentDate?: string;
  totalReactions: number;
}

export interface GitHubReactionInfo {
  totalReactions: number;
  reactionsByType: Record<string, number>;
  reactors: string[];
}

export interface GitHubFileStats {
  totalFiles: number;
  filesByType: Record<string, number>;
  totalAdditions: number;
  totalDeletions: number;
  totalChanges: number;
  largestFile?: string;
  mostChangedFile?: string;
}

// Component Props
export interface AtomGitHubManagerProps extends AtomIntegrationProps<GitHubConfig> {
  // GitHub-specific events
  onRepoCreated?: (repo: GitHubRepository) => void;
  onRepoUpdated?: (repo: GitHubRepository) => void;
  onRepoDeleted?: (repoId: string) => void;
  onIssueCreated?: (issue: GitHubIssue) => void;
  onIssueUpdated?: (issue: GitHubIssue) => void;
  onIssueClosed?: (issue: GitHubIssue) => void;
  onPRCreated?: (pr: GitHubPullRequest) => void;
  onPRUpdated?: (pr: GitHubPullRequest) => void;
  onPRMerged?: (pr: GitHubPullRequest) => void;
  onCommitPushed?: (commit: GitHubCommit) => void;
  onReleaseCreated?: (release: GitHubRelease) => void;
  onWebhookCreated?: (webhook: GitHubWebhook) => void;
  onWorkflowCompleted?: (run: GitHubWorkflowRun) => void;
}

export interface AtomGitHubDataSourceProps extends AtomIntegrationProps<GitHubConfig, AtomGitHubIngestionConfig> {
  // Ingestion-specific events
  onRepoDiscovered?: (repo: GitHubRepositoryEnhanced) => void;
  onIssueDiscovered?: (issue: GitHubIssueEnhanced) => void;
  onPRDiscovered?: (pr: GitHubPullRequestEnhanced) => void;
  onCommitDiscovered?: (commit: GitHubCommitEnhanced) => void;
  onFileDiscovered?: (file: GitHubFile) => void;
  onCommentDiscovered?: (comment: GitHubComment) => void;
  onReleaseDiscovered?: (release: GitHubRelease) => void;
}

// State Types
export interface AtomGitHubState extends AtomIntegrationState {
  repositories: GitHubRepository[];
  issues: GitHubIssue[];
  pullRequests: GitHubPullRequest[];
  commits: GitHubCommit[];
  files: GitHubFile[];
  releases: GitHubRelease[];
  webhooks: GitHubWebhook[];
  users: GitHubUser[];
  searchResults: GitHubSearchResponse<any>;
  currentRepo?: GitHubRepository;
  selectedItems: (GitHubRepository | GitHubIssue | GitHubPullRequest | GitHubCommit)[];
  sortBy: GitHubSortField;
  sortOrder: GitHubSortOrder;
  viewMode: 'grid' | 'list' | 'table';
  filters: GitHubFilters;
}

export interface AtomGitHubDataSourceState extends AtomIntegrationState {
  discoveredRepositories: GitHubRepositoryEnhanced[];
  discoveredIssues: GitHubIssueEnhanced[];
  discoveredPullRequests: GitHubPullRequestEnhanced[];
  discoveredCommits: GitHubCommitEnhanced[];
  discoveredFiles: GitHubFile[];
  discoveredComments: GitHubComment[];
  discoveredReleases: GitHubRelease[];
  ingestionQueue: any[];
  processingIngestion: boolean;
  stats: {
    totalRepositories: number;
    totalIssues: number;
    totalPullRequests: number;
    totalCommits: number;
    totalFiles: number;
    totalComments: number;
    totalReleases: number;
    ingestedRepositories: number;
    ingestedIssues: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataSize: number;
  };
}

// Ingestion Configuration
export interface AtomGitHubIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'github';
  
  // API Configuration
  apiBaseUrl: string;
  graphqlUrl: string;
  personalAccessToken?: string;
  clientId?: string;
  clientSecret?: string;
  oauthToken?: string;
  
  // Repository Discovery
  includePrivate: boolean;
  includeArchived: boolean;
  includeForks: boolean;
  includedRepos: string[];
  excludedRepos: string[];
  repoLanguages: string[];
  minStars?: number;
  minSize?: number;
  
  // Issue Discovery
  includeIssues: boolean;
  includePullRequests: boolean;
  includeClosed: boolean;
  issueDateRange?: {
    start: Date;
    end: Date;
  };
  maxIssuesPerRepo: number;
  
  // Code Discovery
  includeCode: boolean;
  includeDocumentation: boolean;
  includeTests: boolean;
  includedFileTypes: string[];
  excludedFileTypes: string[];
  maxFileSize: number;
  
  // Commit Discovery
  includeCommits: boolean;
  commitDateRange?: {
    start: Date;
    end: Date;
  };
  maxCommitsPerRepo: number;
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  realTimeIngest: boolean;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Processing
  extractMarkdown: boolean;
  includeCodeAnalysis: boolean;
  includeComments: boolean;
  chunkSize: number;
  chunkOverlap: number;
  
  // Sync Settings
  useWebhooks: boolean;
  webhookEvents: GitHubWebhookEvent[];
  webhookSecret?: string;
  syncInterval: number;
  incrementalSync: boolean;
  
  // Pipeline Integration
  pipelineConfig: {
    targetTable: string;
    embeddingModel: string;
    embeddingDimension: number;
    indexType: string;
    numPartitions: number;
  };
}

// API Types
export interface AtomGitHubAPI extends AtomIntegrationAPI<GitHubRepository | GitHubIssue, GitHubConfig> {
  // Authentication
  authenticate: (token: string) => Promise<GitHubAuthResponse>;
  
  // Repository Operations
  getUserRepos: (username?: string, type?: 'all' | 'owner' | 'member', sort?: 'created' | 'updated' | 'pushed' | 'full_name', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubRepository[]>;
  getOrgRepos: (org: string, type?: 'all' | 'public' | 'private' | 'forks' | 'sources' | 'member', sort?: 'created' | 'updated' | 'pushed' | 'full_name', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubRepository[]>;
  getRepo: (owner: string, repo: string) => Promise<GitHubRepository>;
  getRepoContent: (owner: string, repo: string, path: string) => Promise<GitHubFile | GitHubFile[]>;
  downloadRepoContent: (owner: string, repo: string, path: string) => Promise<Blob>;
  createRepo: (repo: Partial<GitHubRepository>) => Promise<GitHubRepository>;
  updateRepo: (owner: string, repo: string, updates: Partial<GitHubRepository>) => Promise<GitHubRepository>;
  deleteRepo: (owner: string, repo: string) => Promise<void>;
  forkRepo: (owner: string, repo: string) => Promise<GitHubRepository>;
  
  // Issue Operations
  getIssues: (owner: string, repo: string, state?: 'open' | 'closed' | 'all', labels?: string[], sort?: 'created' | 'updated' | 'comments', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubIssue[]>;
  getIssue: (owner: string, repo: string, issueNumber: number) => Promise<GitHubIssue>;
  createIssue: (owner: string, repo: string, issue: Partial<GitHubIssue>) => Promise<GitHubIssue>;
  updateIssue: (owner: string, repo: string, issueNumber: number, updates: Partial<GitHubIssue>) => Promise<GitHubIssue>;
  closeIssue: (owner: string, repo: string, issueNumber: number) => Promise<GitHubIssue>;
  reopenIssue: (owner: string, repo: string, issueNumber: number) => Promise<GitHubIssue>;
  
  // Pull Request Operations
  getPullRequests: (owner: string, repo: string, state?: 'open' | 'closed' | 'all', head?: string, base?: string, sort?: 'created' | 'updated' | 'popularity', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubPullRequest[]>;
  getPullRequest: (owner: string, repo: string, prNumber: number) => Promise<GitHubPullRequest>;
  createPullRequest: (owner: string, repo: string, pr: Partial<GitHubPullRequest>) => Promise<GitHubPullRequest>;
  updatePullRequest: (owner: string, repo: string, prNumber: number, updates: Partial<GitHubPullRequest>) => Promise<GitHubPullRequest>;
  mergePullRequest: (owner: string, repo: string, prNumber: number, commitTitle?: string, commitMessage?: string, mergeMethod?: 'merge' | 'squash' | 'rebase') => Promise<any>;
  closePullRequest: (owner: string, repo: string, prNumber: number) => Promise<GitHubPullRequest>;
  
  // Commit Operations
  getCommits: (owner: string, repo: string, sha?: string, path?: string, since?: string, until?: string, perPage?: number, page?: number) => Promise<GitHubCommit[]>;
  getCommit: (owner: string, repo: string, sha: string) => Promise<GitHubCommit>;
  compareCommits: (owner: string, repo: string, base: string, head: string) => Promise<any>;
  
  // Comment Operations
  getIssueComments: (owner: string, repo: string, issueNumber: number, sort?: 'created' | 'updated', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubComment[]>;
  getPRComments: (owner: string, repo: string, prNumber: number, sort?: 'created' | 'updated', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubComment[]>;
  getCommitComments: (owner: string, repo: string, sha: string, sort?: 'created' | 'updated', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubComment[]>;
  createComment: (owner: string, repo: string, issueNumber: number, body: string) => Promise<GitHubComment>;
  updateComment: (owner: string, repo: string, commentId: number, body: string) => Promise<GitHubComment>;
  deleteComment: (owner: string, repo: string, commentId: number) => Promise<void>;
  
  // Release Operations
  getReleases: (owner: string, repo: string, perPage?: number, page?: number) => Promise<GitHubRelease[]>;
  getRelease: (owner: string, repo: string, releaseId: number) => Promise<GitHubRelease>;
  createRelease: (owner: string, repo: string, release: Partial<GitHubRelease>) => Promise<GitHubRelease>;
  updateRelease: (owner: string, repo: string, releaseId: number, updates: Partial<GitHubRelease>) => Promise<GitHubRelease>;
  deleteRelease: (owner: string, repo: string, releaseId: number) => Promise<void>;
  
  // Search Operations
  searchRepos: (query: string, sort?: 'stars' | 'forks' | 'updated', order?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubSearchResponse<GitHubRepository>>;
  searchIssues: (query: string, sort?: 'comments' | 'reactions' | 'created' | 'updated', order?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubSearchResponse<GitHubIssue>>;
  searchCode: (query: string, sort?: 'indexed', order?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubSearchResponse<any>>;
  searchUsers: (query: string, sort?: 'followers' | 'repositories' | 'joined', order?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubSearchResponse<GitHubUser>>;
  
  // Webhook Operations
  getWebhooks: (owner: string, repo: string) => Promise<GitHubWebhook[]>;
  createWebhook: (owner: string, repo: string, webhook: Partial<GitHubWebhook>) => Promise<GitHubWebhook>;
  updateWebhook: (owner: string, repo: string, webhookId: number, updates: Partial<GitHubWebhook>) => Promise<GitHubWebhook>;
  deleteWebhook: (owner: string, repo: string, webhookId: number) => Promise<void>;
  
  // User Operations
  getCurrentUser: () => Promise<GitHubUser>;
  getUser: (username: string) => Promise<GitHubUser>;
  getUserRepos: (username: string, type?: 'all' | 'owner' | 'member', sort?: 'created' | 'updated' | 'pushed' | 'full_name', direction?: 'asc' | 'desc', perPage?: number, page?: number) => Promise<GitHubRepository[]>;
  
  // GraphQL Operations (optional)
  graphqlQuery: (query: string, variables?: any) => Promise<any>;
}

export interface GitHubAuthResponse {
  token: string;
  expires_in?: number;
  refresh_token?: string;
  scope?: string;
  token_type?: string;
}

// Hook Types
export interface AtomGitHubHookReturn extends AtomIntegrationHookReturn<GitHubRepository | GitHubIssue> {
  state: AtomGitHubState;
  api: AtomGitHubAPI;
  actions: AtomGitHubActions;
  config: GitHubConfig;
}

export interface AtomGitHubDataSourceHookReturn extends AtomIntegrationHookReturn<GitHubRepositoryEnhanced> {
  state: AtomGitHubDataSourceState;
  api: AtomGitHubAPI;
  actions: AtomGitHubDataSourceActions;
  config: AtomGitHubIngestionConfig;
}

// Actions Types
export interface AtomGitHubActions {
  // Repository Actions
  createRepo: (repo: Partial<GitHubRepository>) => Promise<GitHubRepository>;
  updateRepo: (owner: string, repo: string, updates: Partial<GitHubRepository>) => Promise<GitHubRepository>;
  deleteRepo: (owner: string, repo: string) => Promise<void>;
  forkRepo: (owner: string, repo: string) => Promise<GitHubRepository>;
  
  // Issue Actions
  createIssue: (owner: string, repo: string, issue: Partial<GitHubIssue>) => Promise<GitHubIssue>;
  updateIssue: (owner: string, repo: string, issueNumber: number, updates: Partial<GitHubIssue>) => Promise<GitHubIssue>;
  closeIssue: (owner: string, repo: string, issueNumber: number) => Promise<void>;
  reopenIssue: (owner: string, repo: string, issueNumber: number) => Promise<void>;
  
  // Pull Request Actions
  createPullRequest: (owner: string, repo: string, pr: Partial<GitHubPullRequest>) => Promise<GitHubPullRequest>;
  updatePullRequest: (owner: string, repo: string, prNumber: number, updates: Partial<GitHubPullRequest>) => Promise<GitHubPullRequest>;
  mergePullRequest: (owner: string, repo: string, prNumber: number, method?: 'merge' | 'squash' | 'rebase') => Promise<void>;
  closePullRequest: (owner: string, repo: string, prNumber: number) => Promise<void>;
  
  // Comment Actions
  createComment: (owner: string, repo: string, issueNumber: number, body: string) => Promise<GitHubComment>;
  updateComment: (owner: string, repo: string, commentId: number, body: string) => Promise<GitHubComment>;
  deleteComment: (owner: string, repo: string, commentId: number) => Promise<void>;
  
  // Navigation Actions
  navigateToRepo: (repo: GitHubRepository) => void;
  navigateToIssue: (issue: GitHubIssue) => void;
  navigateToPR: (pr: GitHubPullRequest) => void;
  
  // Search Actions
  searchRepos: (query: string, filters?: any) => Promise<GitHubSearchResponse<GitHubRepository>>;
  searchIssues: (query: string, filters?: any) => Promise<GitHubSearchResponse<GitHubIssue>>;
  searchCode: (query: string, filters?: any) => Promise<GitHubSearchResponse<any>>;
  
  // UI Actions
  selectItems: (items: (GitHubRepository | GitHubIssue | GitHubPullRequest | GitHubCommit)[]) => void;
  sortBy: (field: GitHubSortField, order: GitHubSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'table') => void;
  setFilters: (filters: GitHubFilters) => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface AtomGitHubDataSourceActions {
  // Discovery Actions
  discoverRepos: (username?: string, org?: string) => Promise<GitHubRepositoryEnhanced[]>;
  discoverIssues: (repos: string[]) => Promise<GitHubIssueEnhanced[]>;
  discoverPullRequests: (repos: string[]) => Promise<GitHubPullRequestEnhanced[]>;
  discoverCommits: (repos: string[]) => Promise<GitHubCommitEnhanced[]>;
  discoverFiles: (repos: string[], paths?: string[]) => Promise<GitHubFile[]>;
  discoverComments: (repos: string[]) => Promise<GitHubComment[]>;
  discoverReleases: (repos: string[]) => Promise<GitHubRelease[]>;
  
  // Ingestion Actions
  ingestRepos: (repos: GitHubRepositoryEnhanced[]) => Promise<void>;
  ingestIssues: (issues: GitHubIssueEnhanced[]) => Promise<void>;
  ingestPullRequests: (prs: GitHubPullRequestEnhanced[]) => Promise<void>;
  ingestCommits: (commits: GitHubCommitEnhanced[]) => Promise<void>;
  ingestFiles: (files: GitHubFile[]) => Promise<void>;
  
  // Sync Actions
  syncRepos: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Filters Type
export interface GitHubFilters {
  languages: string[];
  topics: string[];
  minStars: number;
  minSize: number;
  includePrivate: boolean;
  includeForks: boolean;
  includeArchived: boolean;
  dateRange?: {
    start: Date;
    end: Date;
  };
  authors: string[];
  labels: string[];
  states: string[];
  fileTypes: string[];
}

// Sort Types
export type GitHubSortField = 'name' | 'stars' | 'forks' | 'size' | 'updated' | 'created' | 'language' | 'issues' | 'open_issues' | 'watchers';
export type GitHubSortOrder = 'asc' | 'desc';

// Error Types
export class AtomGitHubError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;
  public statusCode?: number;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string, statusCode?: number) {
    super(message);
    this.name = 'AtomGitHubError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

// Constants
export const gitHubConfigDefaults: Partial<GitHubConfig> = {
  apiBaseUrl: 'https://api.github.com',
  graphqlUrl: 'https://api.github.com/graphql',
  includePrivate: false,
  includeArchived: false,
  includeForks: false,
  includedRepos: [],
  excludedRepos: [],
  repoLanguages: ['JavaScript', 'TypeScript', 'Python', 'Java', 'Go', 'Rust', 'C++', 'C#'],
  minStars: 0,
  minSize: 0,
  includeIssues: true,
  includePullRequests: true,
  includeClosed: false,
  maxIssuesPerRepo: 1000,
  includeCode: true,
  includeDocumentation: true,
  includeTests: false,
  includedFileTypes: ['.md', '.txt', '.json', '.yaml', '.yml', '.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'],
  excludedFileTypes: ['.exe', '.dll', '.so', '.dylib', '.bin', '.zip', '.tar', '.gz', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.mp4', '.avi', '.mov', '.wmv', '.mp3', '.wav', '.flac'],
  maxFileSize: 10 * 1024 * 1024, // 10MB
  includeCommits: true,
  maxCommitsPerRepo: 1000,
  searchType: 'repositories',
  maxSearchResults: 100,
  useWebhooks: true,
  webhookEvents: ['push', 'issues', 'pull_request', 'release'],
  apiCallsPerHour: 5000, // GitHub rate limit for authenticated requests
  useRateLimiter: true
};

export const gitHubIngestionConfigDefaults: Partial<AtomGitHubIngestionConfig> = {
  sourceId: 'github-integration',
  sourceName: 'GitHub',
  sourceType: 'github',
  apiBaseUrl: 'https://api.github.com',
  graphqlUrl: 'https://api.github.com/graphql',
  includePrivate: false,
  includeArchived: false,
  includeForks: false,
  includedRepos: [],
  excludedRepos: [],
  repoLanguages: ['JavaScript', 'TypeScript', 'Python', 'Java', 'Go', 'Rust', 'C++', 'C#'],
  minStars: 0,
  minSize: 0,
  includeIssues: true,
  includePullRequests: true,
  includeClosed: false,
  maxIssuesPerRepo: 1000,
  includeCode: true,
  includeDocumentation: true,
  includeTests: false,
  includedFileTypes: ['.md', '.txt', '.json', '.yaml', '.yml', '.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'],
  excludedFileTypes: ['.exe', '.dll', '.so', '.dylib', '.bin', '.zip', '.tar', '.gz', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.mp4', '.avi', '.mov', '.wmv', '.mp3', '.wav', '.flac'],
  maxFileSize: 10 * 1024 * 1024, // 10MB
  includeCommits: true,
  maxCommitsPerRepo: 1000,
  autoIngest: true,
  ingestInterval: 1800000, // 30 minutes
  realTimeIngest: true,
  batchSize: 50,
  maxConcurrentIngestions: 2,
  extractMarkdown: true,
  includeCodeAnalysis: true,
  includeComments: true,
  chunkSize: 1000,
  chunkOverlap: 100,
  useWebhooks: true,
  webhookEvents: ['push', 'issues', 'pull_request', 'release'],
  syncInterval: 600000, // 10 minutes
  incrementalSync: true,
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const gitHubSearchDefaults = {
  repositories: {
    sort: 'stars',
    order: 'desc',
    perPage: 100
  },
  issues: {
    sort: 'created',
    order: 'desc',
    perPage: 100
  },
  code: {
    sort: 'indexed',
    order: 'desc',
    perPage: 100
  }
};

export const gitHubSortFields: GitHubSortField[] = ['name', 'stars', 'forks', 'size', 'updated', 'created', 'language', 'issues', 'open_issues', 'watchers'];
export const gitHubSortOrders: GitHubSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';
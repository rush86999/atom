/**
 * GitLab Integration Types
 * TypeScript type definitions for GitLab integration
 */

export interface GitLabProject {
  id: number;
  name: string;
  description?: string;
  path: string;
  path_with_namespace: string;
  namespace: {
    id: number;
    name: string;
    path: string;
    kind: string;
    full_path: string;
    parent_id?: number;
    avatar_url?: string;
    web_url: string;
  };
  visibility: 'public' | 'internal' | 'private';
  archived: boolean;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  star_count: number;
  forks_count: number;
  open_issues_count: number;
  runners_token?: string;
  public_jobs: boolean;
  shared_with_groups?: any[];
  only_allow_merge_if_pipeline_succeeds: boolean;
  allow_merge_on_skipped_pipeline: boolean;
  remove_source_branch_after_merge: boolean;
  printing_merge_request_link_enabled: boolean;
  lfs_enabled: boolean;
  request_access_enabled: boolean;
  merge_method: 'merge' | 'rebase_merge' | 'ff';
  auto_devops_enabled?: boolean;
  auto_devops_deploy_strategy?: 'continuous' | 'manual' | 'timed_incremental';
  build_coverage_regex?: string;
  ci_config_path?: string;
  shared_runners_enabled: boolean;
  runners_enabled: boolean;
  runner_token_expires_at?: string;
  wiki_access_level: 'disabled' | 'enabled' | 'private';
  snippets_access_level: 'disabled' | 'enabled' | 'private';
  issues_access_level: 'disabled' | 'enabled' | 'private';
  repository_access_level: 'disabled' | 'enabled' | 'private';
  merge_requests_access_level: 'disabled' | 'enabled' | 'private';
  forking_access_level: 'disabled' | 'enabled' | 'private';
  builds_access_level: 'disabled' | 'enabled' | 'private';
  packages_enabled: boolean;
  service_desk_enabled: boolean;
  service_desk_address?: string;
  autoclose_referenced_issues: boolean;
  enforce_auth_checks_on_uploads: boolean;
  emails_disabled?: boolean;
  container_registry_enabled: boolean;
  container_expiration_policy?: {
    enabled: boolean;
    cadence: string;
    keep_n: number;
    older_than: string;
    name_regex_delete: string;
    name_regex_keep: string;
  };
  container_registry_access_level: 'disabled' | 'enabled' | 'private';
  security_and_compliance_enabled: boolean;
}

export interface GitLabCommit {
  id: string;
  short_id: string;
  created_at: string;
  parent_ids: string[];
  title: string;
  message: string;
  author_name: string;
  author_email: string;
  authored_date: string;
  committer_name: string;
  committer_email: string;
  committed_date: string;
  web_url: string;
  stats: {
    additions: number;
    deletions: number;
    total: number;
  };
  status?: string;
  project_id: number;
  last_pipeline?: GitLabPipeline;
}

export interface GitLabBranch {
  name: string;
  commit: {
    id: string;
    short_id: string;
    created_at: string;
    title: string;
    message: string;
    author_name: string;
    author_email: string;
    authored_date: string;
    committer_name: string;
    committer_email: string;
    committed_date: string;
  };
  protected: boolean;
  default: boolean;
  web_url: string;
  merged: boolean;
  can_push: boolean;
  developers_can_push: boolean;
  developers_can_merge: boolean;
}

export interface GitLabMergeRequest {
  id: number;
  iid: number;
  project_id: number;
  title: string;
  description: string;
  state: 'opened' | 'closed' | 'locked' | 'merged';
  created_at: string;
  updated_at: string;
  merged_at?: string;
  merged_by?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  closed_by?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  author: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  assignees: Array<{
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  }>;
  reviewers: Array<{
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  }>;
  source_branch: string;
  source_project_id: number;
  target_branch: string;
  target_project_id: number;
  labels: Array<{
    id: number;
    title: string;
    color: string;
    description?: string;
  }>;
  milestone?: {
    id: number;
    iid: number;
    title: string;
    description?: string;
    state: string;
    created_at: string;
    updated_at: string;
    due_date?: string;
    start_date?: string;
  };
  draft: boolean;
  work_in_progress?: boolean;
  merge_when_pipeline_succeeds: boolean;
  merge_status: 'can_be_merged' | 'cannot_be_merged' | 'unchecked' | 'checking' | 'ci_still_running';
  sha: string;
  merge_commit_sha?: string;
  squash_commit_sha?: string;
  discussions_locked: boolean;
  should_remove_source_branch: boolean;
  force_remove_source_branch: boolean;
  reference: string;
  references: {
    short: string;
    relative: string;
    full: string;
  };
  web_url: string;
  time_stats: {
    time_estimate: number;
    total_time_spent: number;
    human_time_estimate: string;
    human_total_time_spent: string;
  };
  squash: boolean;
  task_completion_status?: {
    count: number;
    completed_count: number;
  };
  has_conflicts: boolean;
  blocking_discussions_resolved: boolean;
  approvals_before_merge?: number;
}

export interface GitLabIssue {
  id: number;
  iid: number;
  project_id: number;
  title: string;
  description: string;
  state: 'opened' | 'closed';
  created_at: string;
  updated_at: string;
  closed_at?: string;
  closed_by?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  author: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  assignees: Array<{
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  }>;
  assignee?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  labels: Array<{
    id: number;
    title: string;
    color: string;
    description?: string;
  }>;
  milestone?: {
    id: number;
    iid: number;
    title: string;
    description?: string;
    state: string;
    created_at: string;
    updated_at: string;
    due_date?: string;
    start_date?: string;
  };
  notes?: Array<{
    id: number;
    body: string;
    attachment?: string;
    author: {
      id: number;
      name: string;
      username: string;
      state: string;
           avatar_url: string;
      web_url: string;
    };
    created_at: string;
    updated_at: string;
    system: boolean;
    noteable_type: 'Issue' | 'MergeRequest';
    noteable_iid: number;
    resolvable: boolean;
  }>;
  updated_by_id?: number;
  confidential: boolean;
  discussion_locked: boolean;
  due_date?: string;
  web_url: string;
  time_stats: {
    time_estimate: number;
    total_time_spent: number;
    human_time_estimate: string;
    human_total_time_spent: string;
  };
  task_completion_status?: {
    count: number;
    completed_count: number;
  };
  weight?: number;
  blocked?: boolean;
  blocked_by?: Array<{
    id: number;
    title: string;
    state: string;
    web_url: string;
  }>;
  epic?: {
    id: number;
    iid: number;
    title: string;
    url: string;
  };
  epic_iid?: number;
  iteration?: {
    id: number;
    iid: number;
    title: string;
    url: string;
  };
  iteration_iid?: number;
  user_notes_count: number;
  merge_requests_count?: number;
  upvotes: number;
  downvotes: number;
  duplicate_of?: {
    id: number;
    iid: number;
    title: string;
    state: string;
  };
  moved_to_id?: number;
  duplicated_by?: Array<{
    id: number;
    iid: number;
    title: string;
    state: string;
  }>;
  promoted_to_epic?: {
    id: number;
    iid: number;
    title: string;
    url: string;
  };
  subscribed: boolean;
  _links: {
    self: string;
    notes: string;
    award_emoji: string;
    project: string;
  };
}

export interface GitLabPipeline {
  id: number;
  iid: number;
  project_id: number;
  sha: string;
  ref: string;
  status: 'created' | 'waiting_for_resource' | 'preparing' | 'pending' | 'running' | 'success' | 'failed' | 'canceled' | 'skipped' | 'manual' | 'scheduled';
  source: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  finished_at?: string;
  committed_at?: string;
  duration?: number;
  coverage?: string;
  web_url: string;
  user?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  variables?: Array<{
    key: string;
    value: string;
    variable_type: 'env_var' | 'file';
    protected: boolean;
    masked: boolean;
    raw: boolean;
  }>;
  jobs: Array<{
    id: number;
    name: string;
    stage: string;
    status: string;
    started_at?: string;
    created_at: string;
    finished_at?: string;
    retry: number;
    duration?: number;
    runner: {
      id: number;
      description: string;
      active: boolean;
      is_shared: boolean;
    };
    artifacts: Array<{
      file_type: string;
      size: number;
      filename: string;
      file_format?: string;
    }>;
    failure_reason?: string;
    tag_list: string[];
    allow_failure: boolean;
    artifacts_file?: {
      filename: string;
      size: number;
    };
    coverage_regex?: string;
  }>;
  triggered_by?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  tag?: boolean;
  yaml_errors?: string;
  child: boolean;
  upstream?: {
    id: number;
    iid: number;
    project_id: number;
    sha: string;
    ref: string;
    status: string;
  };
  downstream?: Array<{
    id: number;
    iid: number;
    project_id: number;
    sha: string;
    ref: string;
    status: string;
  }>;
  config: {
    path?: string;
    variables?: Array<{
      key: string;
      value: string;
    }>;
  };
}

export interface GitLabJob {
  id: number;
  name: string;
  stage: string;
  status: 'created' | 'waiting_for_resource' | 'preparing' | 'pending' | 'running' | 'success' | 'failed' | 'canceled' | 'skipped' | 'manual' | 'scheduled';
  created_at: string;
  started_at?: string;
  finished_at?: string;
  duration?: number;
  queued_duration?: number;
  artifacts_expire_at?: string;
  tag: boolean;
  ref: string;
  coverage?: string;
  allow_failure: boolean;
  retry: number;
  user?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  commit: {
    id: string;
    short_id: string;
    title: string;
    message: string;
    author_name: string;
    author_email: string;
    created_at: string;
  };
  pipeline?: {
    id: number;
    iid: number;
    project_id: number;
    sha: string;
    ref: string;
    status: string;
    created_at: string;
    updated_at: string;
    web_url: string;
  };
  web_url: string;
  artifacts: Array<{
    file_type: string;
    size: number;
    filename: string;
    file_format?: string;
  }>;
  runner: {
    id: number;
    description: string;
    active: boolean;
    is_shared: boolean;
    tags?: string[];
  };
  artifacts_file?: {
    filename: string;
    size: number;
  };
  tag_list: string[];
  failure_reason?: string;
  project: {
    id: number;
    name: string;
    path_with_namespace: string;
    avatar_url?: string;
    web_url: string;
  };
  protected: boolean;
  coverage_regex?: string;
  needs: Array<{
    id: number;
    name: string;
    stage: string;
    status: string;
    created_at: string;
  }>;
  retry_count: number;
  release: {
    tag_name: string;
    description: string;
  };
  variables?: Array<{
    key: string;
    value: string;
    variable_type: 'env_var' | 'file';
    protected: boolean;
    masked: boolean;
    raw: boolean;
  }>;
  dependencies: Array<{
    id: number;
    name: string;
    stage: string;
    status: string;
    created_at: string;
  }>;
  triggered_by?: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  scheduling_type: 'stage' | 'dag';
  execution_status?: string;
  priority?: number;
}

export interface GitLabUser {
  id: number;
  name: string;
  username: string;
  state: 'active' | 'blocked';
  avatar_url: string;
  web_url: string;
  created_at: string;
  bio?: string;
  location?: string;
  public_email: string;
  skype: string;
  linkedin: string;
  twitter: string;
  website_url: string;
  organization?: string;
  job_title?: string;
  pronouns?: string;
  bot: boolean;
  work_information: {
    profession?: string;
    organization?: string;
    seniority?: string;
  };
  followers: number;
  following: number;
  starred_projects: number;
  is_followed: boolean;
  local_time: string;
  last_sign_in_at?: string;
  confirmed_at: string;
  last_activity_on?: string;
  email?: string;
  theme_id: number;
  color_scheme_id: number;
  projects_limit: number;
  current_sign_in_at?: string;
  identities?: Array<{
    provider: string;
    extern_uid: string;
    saml_provider_id?: string;
  }>;
  can_create_group: boolean;
  can_create_project: boolean;
  two_factor_enabled: boolean;
  external: boolean;
  shared_runners_minutes_limit?: number;
  shared_runners_minutes?: number;
}

export interface GitLabGroup {
  id: number;
  name: string;
  path: string;
  description?: string;
  visibility: 'public' | 'internal' | 'private';
  avatar_url?: string;
  web_url: string;
  request_access_enabled: boolean;
  require_two_factor_authentication: boolean;
  two_factor_grace_period: number;
  project_creation_level: string;
  auto_devops_enabled: boolean;
  subgroup_creation_level: string;
  emails_disabled?: boolean;
  mentions_disabled?: boolean;
  lfs_enabled: boolean;
  share_with_group_lock: boolean;
  file_template_project_id?: number;
  email_confirmation_disabled: boolean;
  default_branch_protection: number;
  default_branch_protection_defaults: {
    developer_can_merge: boolean;
    allow_force_push: boolean;
  };
  cluster_type: string;
  created_at: string;
  updated_at: string;
  parent_id?: number;
  path: string;
  full_name: string;
  full_path: string;
  members_count_with_descendants?: number;
  projects_count?: number;
}

export interface GitLabRunner {
  id: number;
  description: string;
  ip_address?: string;
  active: boolean;
  paused: boolean;
  is_shared: boolean;
  name: string;
  online: boolean;
  status: 'online' | 'offline' | 'paused';
  architecture: string;
  platform: string;
  run_untagged: boolean;
  contacted_at?: string;
  version: string;
  revision: string;
  tag_list: string[];
  run_list?: Array<{
    id: number;
    status: string;
    project_id: number;
    project_name?: string;
    started_at?: string;
    finished_at?: string;
  }>;
  maximum_timeout?: number;
  locked: boolean;
  access_level: string;
  groups?: Array<{
    id: number;
    name: string;
    path: string;
    description?: string;
    visibility: string;
    avatar_url?: string;
    web_url: string;
    created_at: string;
    updated_at: string;
    members_count_with_descendants?: number;
    projects_count?: number;
  }>;
  projects?: Array<{
    id: number;
    name: string;
    path: string;
    description?: string;
    visibility: string;
    avatar_url?: string;
    web_url: string;
    created_at: string;
    updated_at: string;
  }>;
}

export interface GitLabRelease {
  name: string;
  description: string;
  tag_name: string;
  created_at: string;
  released_at: string;
  author: {
    id: number;
    name: string;
    username: string;
    state: string;
    avatar_url: string;
    web_url: string;
  };
  commit: {
    id: string;
    short_id: string;
    title: string;
    message: string;
    created_at: string;
    author_name: string;
    author_email: string;
    authored_date: string;
    committer_name: string;
    committer_email: string;
    committed_date: string;
  };
  commit_path: string;
  tag_commit_sha: string;
  assets: {
    count: number;
    sources?: Array<{
      format: string;
      url: string;
    }>;
    links?: Array<{
      id: number;
      name: string;
      url: string;
      external: boolean;
      link_type: string;
    }>;
  };
  milestones?: Array<{
    id: number;
    iid: number;
    title: string;
    description?: string;
    state: string;
    created_at: string;
    updated_at: string;
    due_date?: string;
    start_date?: string;
  }>;
  evidences?: Array<{
    id: number;
    sha: string;
    filepath: string;
    collected_at: string;
  }>;
}

export interface GitLabWebhook {
  id: number;
  url: string;
  project_id?: number;
  group_id?: number;
  push_events: boolean;
  issues_events: boolean;
  confidential_issues_events: boolean;
  merge_requests_events: boolean;
  tag_push_events: boolean;
  note_events: boolean;
  confidential_note_events: boolean;
  wiki_page_events: boolean;
  pipeline_events: boolean;
  job_events: boolean;
  deployment_events: boolean;
  releases_events: boolean;
  emoji_events: boolean;
  resource_access_token_events: boolean;
  created_at: string;
}

export interface GitLabConfig {
  platform: 'gitlab';
  projects: number[];
  groups: number[];
  include_private_projects: boolean;
  include_internal_projects: boolean;
  include_public_projects: boolean;
  sync_frequency: 'realtime' | 'hourly' | 'daily' | 'weekly';
  include_pipelines: boolean;
  include_jobs: boolean;
  include_issues: boolean;
  include_merge_requests: boolean;
  include_releases: boolean;
  include_webhooks: boolean;
  max_projects: number;
  max_pipelines: number;
  max_jobs: number;
  max_issues: number;
  max_merge_requests: number;
  date_range: {
    start: Date;
    end: Date;
  };
  webhook_events: string[];
  enable_notifications: boolean;
  background_sync: boolean;
  token_data?: {
    access_token: string;
    refresh_token?: string;
    expires_at?: Date;
    scope: string[];
  };
}
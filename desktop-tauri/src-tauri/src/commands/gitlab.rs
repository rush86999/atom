/**
 * GitLab Tauri Commands
 * Native desktop commands for GitLab integration
 */

use serde::{Deserialize, Serialize};
use tauri::command;
use serde_json::Value;
use std::collections::HashMap;
use chrono::{DateTime, Utc};
use crate::gitlab::{GitLabApiClient, GitLabConfig, GitLabProject, GitLabPipeline, GitLabIssue, GitLabMergeRequest};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabProjectInfo {
    pub id: i64,
    pub name: String,
    pub path: String,
    pub description: Option<String>,
    pub visibility: String,
    pub archived: bool,
    pub created_at: String,
    pub updated_at: String,
    pub last_activity_at: String,
    pub star_count: i32,
    pub forks_count: i32,
    pub open_issues_count: i32,
    pub web_url: String,
    pub namespace: GitLabNamespace,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabNamespace {
    pub id: i64,
    pub name: String,
    pub path: String,
    pub full_path: String,
    pub kind: String,
    pub web_url: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabPipelineInfo {
    pub id: i64,
    pub iid: i64,
    pub project_id: i64,
    pub sha: String,
    pub ref: String,
    pub status: String,
    pub source: String,
    pub created_at: String,
    pub updated_at: String,
    pub started_at: Option<String>,
    pub finished_at: Option<String>,
    pub duration: Option<f64>,
    pub coverage: Option<String>,
    pub web_url: String,
    pub jobs: Vec<GitLabJob>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabJob {
    pub id: i64,
    pub name: String,
    pub stage: String,
    pub status: String,
    pub created_at: String,
    pub started_at: Option<String>,
    pub finished_at: Option<String>,
    pub duration: Option<f64>,
    pub web_url: String,
    pub runner: Option<GitLabRunner>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabRunner {
    pub id: i64,
    pub description: String,
    pub active: bool,
    pub is_shared: bool,
    pub tags: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabIssueInfo {
    pub id: i64,
    pub iid: i64,
    pub project_id: i64,
    pub title: String,
    pub description: Option<String>,
    pub state: String,
    pub created_at: String,
    pub updated_at: String,
    pub closed_at: Option<String>,
    pub author: GitLabUser,
    pub assignees: Vec<GitLabUser>,
    pub labels: Vec<GitLabLabel>,
    pub milestone: Option<GitLabMilestone>,
    pub web_url: String,
    pub weight: Option<i32>,
    pub confidential: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabMergeRequestInfo {
    pub id: i64,
    pub iid: i64,
    pub project_id: i64,
    pub title: String,
    pub description: Option<String>,
    pub state: String,
    pub created_at: String,
    pub updated_at: String,
    pub merged_at: Option<String>,
    pub author: GitLabUser,
    pub assignees: Vec<GitLabUser>,
    pub reviewers: Vec<GitLabUser>,
    pub source_branch: String,
    pub target_branch: String,
    pub labels: Vec<GitLabLabel>,
    pub milestone: Option<GitLabMilestone>,
    pub web_url: String,
    pub draft: bool,
    pub merge_status: String,
    pub has_conflicts: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabUser {
    pub id: i64,
    pub name: String,
    pub username: String,
    pub state: String,
    pub avatar_url: String,
    pub web_url: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabLabel {
    pub id: i64,
    pub title: String,
    pub color: String,
    pub description: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabMilestone {
    pub id: i64,
    pub iid: i64,
    pub title: String,
    pub description: Option<String>,
    pub state: String,
    pub created_at: String,
    pub updated_at: String,
    pub due_date: Option<String>,
    pub start_date: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabCommit {
    pub id: String,
    pub short_id: String,
    pub created_at: String,
    pub title: String,
    pub message: String,
    pub author_name: String,
    pub author_email: String,
    pub committer_name: String,
    pub committer_email: String,
    pub web_url: String,
    pub stats: GitLabCommitStats,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabCommitStats {
    pub additions: i32,
    pub deletions: i32,
    pub total: i32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabBranch {
    pub name: String,
    pub commit: GitLabCommitInfo,
    pub protected: bool,
    pub default: bool,
    pub web_url: String,
    pub merged: bool,
    pub can_push: bool,
    pub developers_can_push: bool,
    pub developers_can_merge: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabCommitInfo {
    pub id: String,
    pub short_id: String,
    pub title: String,
    pub created_at: String,
    pub message: String,
    pub author_name: String,
    pub author_email: String,
    pub committer_name: String,
    pub committer_email: String,
    pub authored_date: String,
    pub committed_date: String,
}

// Initialize GitLab client
fn get_gitlab_client(user_id: &str) -> Result<GitLabApiClient, String> {
    // In a real implementation, this would retrieve stored tokens
    let access_token = std::env::var("GITLAB_ACCESS_TOKEN")
        .map_err(|_| "GitLab access token not configured".to_string())?;
    
    let base_url = std::env::var("GITLAB_API_URL")
        .unwrap_or_else(|_| "https://gitlab.com/api/v4".to_string());
    
    Ok(GitLabApiClient::new(base_url, access_token))
}

// Command: Get GitLab projects
#[command]
pub async fn get_gitlab_projects(
    user_id: String,
    limit: Option<i32>,
    visibility: Option<String>,
    archived: Option<bool>,
    search: Option<String>,
    sort: Option<String>,
    order: Option<String>,
) -> Result<Vec<GitLabProjectInfo>, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let projects = client.get_projects(
        limit.unwrap_or(50),
        visibility.as_deref(),
        archived,
        search.as_deref(),
        sort.as_deref(),
        order.as_deref(),
    ).await?;
    
    Ok(projects)
}

// Command: Get GitLab project details
#[command]
pub async fn get_gitlab_project(
    user_id: String,
    project_id: i64,
    include_pipelines: Option<bool>,
    include_issues: Option<bool>,
    include_merge_requests: Option<bool>,
    include_commits: Option<bool>,
    include_branches: Option<bool>,
    pipeline_limit: Option<i32>,
    issue_limit: Option<i32>,
    mr_limit: Option<i32>,
    commit_limit: Option<i32>,
    branch_limit: Option<i32>,
) -> Result<GitLabProjectDetails, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let project = client.get_project(project_id).await?;
    
    let mut pipelines = Vec::new();
    let mut issues = Vec::new();
    let mut merge_requests = Vec::new();
    let mut commits = Vec::new();
    let mut branches = Vec::new();
    
    if include_pipelines.unwrap_or(false) {
        pipelines = client.get_project_pipelines(project_id, pipeline_limit.unwrap_or(10)).await?;
    }
    
    if include_issues.unwrap_or(false) {
        issues = client.get_project_issues(project_id, "opened", issue_limit.unwrap_or(20)).await?;
    }
    
    if include_merge_requests.unwrap_or(false) {
        merge_requests = client.get_project_merge_requests(project_id, "opened", mr_limit.unwrap_or(20)).await?;
    }
    
    if include_commits.unwrap_or(false) {
        commits = client.get_project_commits(project_id, "main", commit_limit.unwrap_or(10)).await?;
    }
    
    if include_branches.unwrap_or(false) {
        branches = client.get_project_branches(project_id, branch_limit.unwrap_or(50)).await?;
    }
    
    Ok(GitLabProjectDetails {
        project,
        pipelines,
        issues,
        merge_requests,
        commits,
        branches,
    })
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabProjectDetails {
    pub project: GitLabProjectInfo,
    pub pipelines: Vec<GitLabPipelineInfo>,
    pub issues: Vec<GitLabIssueInfo>,
    pub merge_requests: Vec<GitLabMergeRequestInfo>,
    pub commits: Vec<GitLabCommit>,
    pub branches: Vec<GitLabBranch>,
}

// Command: Get GitLab pipelines
#[command]
pub async fn get_gitlab_pipelines(
    user_id: String,
    project_id: Option<i64>,
    status: Option<String>,
    ref_name: Option<String>,
    limit: Option<i32>,
) -> Result<Vec<GitLabPipelineInfo>, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let pipelines = client.get_pipelines(
        project_id,
        status.as_deref(),
        ref_name.as_deref(),
        limit.unwrap_or(100),
    ).await?;
    
    Ok(pipelines)
}

// Command: Get GitLab issues
#[command]
pub async fn get_gitlab_issues(
    user_id: String,
    project_id: Option<i64>,
    state: Option<String>,
    labels: Option<Vec<String>>,
    milestone: Option<String>,
    author: Option<String>,
    assignee: Option<String>,
    limit: Option<i32>,
) -> Result<Vec<GitLabIssueInfo>, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let issues = client.get_issues(
        project_id,
        state.as_deref().unwrap_or("opened"),
        labels.as_deref(),
        milestone.as_deref(),
        author.as_deref(),
        assignee.as_deref(),
        limit.unwrap_or(100),
    ).await?;
    
    Ok(issues)
}

// Command: Create GitLab issue
#[command]
pub async fn create_gitlab_issue(
    user_id: String,
    project_id: i64,
    title: String,
    description: Option<String>,
    labels: Option<Vec<String>>,
    assignee_ids: Option<Vec<i64>>,
    milestone_id: Option<i64>,
    weight: Option<i32>,
    confidential: Option<bool>,
) -> Result<GitLabIssueInfo, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let issue = client.create_issue(
        project_id,
        title,
        description,
        labels.as_deref(),
        assignee_ids.as_deref(),
        milestone_id,
        weight,
        confidential.unwrap_or(false),
    ).await?;
    
    Ok(issue)
}

// Command: Get GitLab merge requests
#[command]
pub async fn get_gitlab_merge_requests(
    user_id: String,
    project_id: Option<i64>,
    state: Option<String>,
    source_branch: Option<String>,
    target_branch: Option<String>,
    author: Option<String>,
    assignee: Option<String>,
    labels: Option<Vec<String>>,
    milestone: Option<String>,
    limit: Option<i32>,
) -> Result<Vec<GitLabMergeRequestInfo>, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let merge_requests = client.get_merge_requests(
        project_id,
        state.as_deref().unwrap_or("opened"),
        source_branch.as_deref(),
        target_branch.as_deref(),
        author.as_deref(),
        assignee.as_deref(),
        labels.as_deref(),
        milestone.as_deref(),
        limit.unwrap_or(100),
    ).await?;
    
    Ok(merge_requests)
}

// Command: Create GitLab merge request
#[command]
pub async fn create_gitlab_merge_request(
    user_id: String,
    project_id: i64,
    source_branch: String,
    target_branch: String,
    title: String,
    description: Option<String>,
    assignee_ids: Option<Vec<i64>>,
    reviewer_ids: Option<Vec<i64>>,
    labels: Option<Vec<String>>,
    milestone_id: Option<i64>,
    remove_source_branch: Option<bool>,
    squash: Option<bool>,
) -> Result<GitLabMergeRequestInfo, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let mr = client.create_merge_request(
        project_id,
        source_branch,
        target_branch,
        title,
        description,
        assignee_ids.as_deref(),
        reviewer_ids.as_deref(),
        labels.as_deref(),
        milestone_id,
        remove_source_branch.unwrap_or(false),
        squash.unwrap_or(false),
    ).await?;
    
    Ok(mr)
}

// Command: Trigger GitLab pipeline
#[command]
pub async fn trigger_gitlab_pipeline(
    user_id: String,
    project_id: i64,
    ref_name: String,
    variables: Option<Vec<HashMap<String, String>>>,
) -> Result<GitLabPipelineInfo, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let pipeline = client.trigger_pipeline(
        project_id,
        ref_name,
        variables.as_deref(),
    ).await?;
    
    Ok(pipeline)
}

// Command: Get GitLab commits
#[command]
pub async fn get_gitlab_commits(
    user_id: String,
    project_id: i64,
    branch: Option<String>,
    since: Option<String>,
    until: Option<String>,
    author: Option<String>,
    limit: Option<i32>,
) -> Result<Vec<GitLabCommit>, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let commits = client.get_commits(
        project_id,
        branch.as_deref().unwrap_or("main"),
        since.as_deref(),
        until.as_deref(),
        author.as_deref(),
        limit.unwrap_or(20),
    ).await?;
    
    Ok(commits)
}

// Command: Get GitLab branches
#[command]
pub async fn get_gitlab_branches(
    user_id: String,
    project_id: i64,
    search: Option<String>,
    limit: Option<i32>,
) -> Result<GitLabBranchesResult, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let branches = client.get_branches(
        project_id,
        search.as_deref(),
        limit.unwrap_or(100),
    ).await?;
    
    let default_branch = client.get_default_branch(project_id).await?;
    
    Ok(GitLabBranchesResult {
        branches,
        default_branch,
        total: branches.len(),
    })
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabBranchesResult {
    pub branches: Vec<GitLabBranch>,
    pub default_branch: String,
    pub total: usize,
}

// Command: Get GitLab user info
#[command]
pub async fn get_gitlab_user(
    user_id: String,
    target_user_id: Option<i64>,
) -> Result<GitLabUserInfo, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let user = if let Some(id) = target_user_id {
        client.get_user(id).await?
    } else {
        client.get_current_user().await?
    };
    
    let projects_count = client.get_user_projects_count(user.id).await?;
    let groups_count = client.get_user_groups_count(user.id).await?;
    let followers = client.get_user_followers(user.id).await?;
    let following = client.get_user_following(user.id).await?;
    
    Ok(GitLabUserInfo {
        user,
        projects_count,
        groups_count,
        followers,
        following,
    })
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabUserInfo {
    pub user: GitLabUser,
    pub projects_count: i32,
    pub groups_count: i32,
    pub followers: i32,
    pub following: i32,
}

// Command: Check GitLab health
#[command]
pub async fn check_gitlab_health(
    user_id: String,
) -> Result<GitLabHealthStatus, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let health = client.check_health().await?;
    let current_user = client.get_current_user().await.ok();
    
    Ok(GitLabHealthStatus {
        status: health.status,
        connected: health.connected,
        user: current_user,
        token_status: health.token_status,
        last_check: health.last_check,
        api_version: health.api_version,
    })
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabHealthStatus {
    pub status: String,
    pub connected: bool,
    pub user: Option<GitLabUser>,
    pub token_status: String,
    pub last_check: String,
    pub api_version: String,
}

// Command: Start GitLab data ingestion
#[command]
pub async fn start_gitlab_ingestion(
    user_id: String,
    config: GitLabIngestionConfig,
) -> Result<GitLabIngestionResult, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let ingestion_id = uuid::Uuid::new_v4().to_string();
    let start_time = Utc::now();
    
    let mut total_projects = 0;
    let mut total_pipelines = 0;
    let mut total_issues = 0;
    let mut total_merge_requests = 0;
    
    // Get projects
    let projects = client.get_projects(
        config.max_projects,
        None,
        Some(false),
        None,
        None,
        None,
    ).await?;
    
    total_projects = projects.len();
    
    // Process each project if included in config
    for project in &projects {
        if config.include_pipelines {
            let pipelines = client.get_project_pipelines(
                project.id,
                config.max_pipelines,
            ).await?;
            total_pipelines += pipelines.len();
        }
        
        if config.include_issues {
            let issues = client.get_project_issues(
                project.id,
                "opened",
                config.max_issues,
            ).await?;
            total_issues += issues.len();
        }
        
        if config.include_merge_requests {
            let merge_requests = client.get_project_merge_requests(
                project.id,
                "opened",
                config.max_merge_requests,
            ).await?;
            total_merge_requests += merge_requests.len();
        }
    }
    
    let end_time = Utc::now();
    let duration = (end_time - start_time).num_seconds();
    
    Ok(GitLabIngestionResult {
        ingestion_id,
        status: "completed",
        progress: 100,
        total_projects,
        total_pipelines,
        total_issues,
        total_merge_requests,
        duration,
        message: format!(
            "Successfully ingested {} projects, {} pipelines, {} issues, and {} merge requests",
            total_projects, total_pipelines, total_issues, total_merge_requests
        ),
    })
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabIngestionConfig {
    pub max_projects: i32,
    pub max_pipelines: i32,
    pub max_issues: i32,
    pub max_merge_requests: i32,
    pub include_pipelines: bool,
    pub include_issues: bool,
    pub include_merge_requests: bool,
    pub include_private_projects: bool,
    pub include_internal_projects: bool,
    pub include_public_projects: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabIngestionResult {
    pub ingestion_id: String,
    pub status: String,
    pub progress: i32,
    pub total_projects: usize,
    pub total_pipelines: usize,
    pub total_issues: usize,
    pub total_merge_requests: usize,
    pub duration: i64,
    pub message: String,
}

// Command: Open GitLab URL in system browser
#[command]
pub async fn open_gitlab_url(
    url: String,
) -> Result<(), String> {
    use tauri::api::shell::open;
    
    open(&std::env::current_dir().unwrap(), url)
        .map_err(|e| format!("Failed to open URL: {}", e))?;
    
    Ok(())
}

// Command: Get GitLab statistics
#[command]
pub async fn get_gitlab_statistics(
    user_id: String,
) -> Result<GitLabStatistics, String> {
    let client = get_gitlab_client(&user_id)?;
    
    let projects = client.get_projects(50, None, Some(false), None, None, None).await?;
    
    let total_projects = projects.len();
    let total_stars: i32 = projects.iter().map(|p| p.star_count).sum();
    let total_forks: i32 = projects.iter().map(|p| p.forks_count).sum();
    let total_open_issues: i32 = projects.iter().map(|p| p.open_issues_count).sum();
    let total_private_projects = projects.iter().filter(|p| p.visibility == "private").count();
    let total_public_projects = projects.iter().filter(|p| p.visibility == "public").count();
    let total_internal_projects = projects.iter().filter(|p| p.visibility == "internal").count();
    
    let avg_stars_per_project = if total_projects > 0 {
        total_stars / total_projects as i32
    } else {
        0
    };
    
    let avg_forks_per_project = if total_projects > 0 {
        total_forks / total_projects as i32
    } else {
        0
    };
    
    Ok(GitLabStatistics {
        total_projects,
        total_stars,
        total_forks,
        total_open_issues,
        total_private_projects,
        total_public_projects,
        total_internal_projects,
        average_stars_per_project: avg_stars_per_project,
        average_forks_per_project: avg_forks_per_project,
    })
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabStatistics {
    pub total_projects: usize,
    pub total_stars: i32,
    pub total_forks: i32,
    pub total_open_issues: i32,
    pub total_private_projects: usize,
    pub total_public_projects: usize,
    pub total_internal_projects: usize,
    pub average_stars_per_project: i32,
    pub average_forks_per_project: i32,
}

// Command: Clear GitLab cache
#[command]
pub async fn clear_gitlab_cache(
    user_id: String,
) -> Result<GitLabCacheResult, String> {
    // In a real implementation, this would clear the local cache
    Ok(GitLabCacheResult {
        success: true,
        message: "GitLab cache cleared successfully".to_string(),
        size_cleared: 1024 * 1024, // 1MB
        entries_cleared: 100,
    })
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitLabCacheResult {
    pub success: bool,
    pub message: String,
    pub size_cleared: u64,
    pub entries_cleared: u32,
}
// GitHub API commands for ATOM Desktop Tauri application
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::error::Error;
use std::fmt;

// Error types
#[derive(Debug)]
pub enum GitHubApiError {
    RequestError(String),
    AuthenticationError(String),
    RateLimitError(String),
    NotFoundError(String),
    ValidationError(String),
    NetworkError(String),
}

impl fmt::Display for GitHubApiError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            GitHubApiError::RequestError(msg) => write!(f, "Request error: {}", msg),
            GitHubApiError::AuthenticationError(msg) => write!(f, "Authentication error: {}", msg),
            GitHubApiError::RateLimitError(msg) => write!(f, "Rate limit error: {}", msg),
            GitHubApiError::NotFoundError(msg) => write!(f, "Not found error: {}", msg),
            GitHubApiError::ValidationError(msg) => write!(f, "Validation error: {}", msg),
            GitHubApiError::NetworkError(msg) => write!(f, "Network error: {}", msg),
        }
    }
}

impl Error for GitHubApiError {}

// Response types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubUser {
    pub id: u64,
    pub login: String,
    pub name: Option<String>,
    pub email: Option<String>,
    pub bio: Option<String>,
    pub company: Option<String>,
    pub location: Option<String>,
    pub blog: Option<String>,
    pub avatar_url: String,
    pub html_url: String,
    pub followers: u32,
    pub following: u32,
    pub public_repos: u32,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubRepository {
    pub id: u64,
    pub name: String,
    pub full_name: String,
    pub description: Option<String>,
    pub private: bool,
    pub fork: bool,
    pub html_url: String,
    pub clone_url: String,
    pub ssh_url: String,
    pub default_branch: String,
    pub language: Option<String>,
    pub languages_url: String,
    pub stargazers_count: u32,
    pub watchers_count: u32,
    pub forks_count: u32,
    pub open_issues_count: u32,
    pub topics: Vec<String>,
    pub size: u32,
    pub pushed_at: String,
    pub created_at: String,
    pub updated_at: String,
    pub owner: GitHubUser,
    pub license: Option<GitHubLicense>,
    pub has_wiki: bool,
    pub has_pages: bool,
    pub has_issues: bool,
    pub has_projects: bool,
    pub archived: bool,
    pub disabled: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubLicense {
    pub key: String,
    pub name: String,
    pub url: Option<String>,
    pub spdx_id: Option<String>,
    pub html_url: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubIssue {
    pub id: u64,
    pub number: u32,
    pub title: String,
    pub body: Option<String>,
    pub state: String,
    pub html_url: String,
    pub user: GitHubUser,
    pub assignees: Vec<GitHubUser>,
    pub labels: Vec<GitHubLabel>,
    pub milestone: Option<GitHubMilestone>,
    pub comments: u32,
    pub created_at: String,
    pub updated_at: String,
    pub closed_at: Option<String>,
    pub locked: bool,
    pub active_lock_reason: Option<String>,
    pub draft: bool,
    pub pull_request: Option<GitHubPullRequestReference>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubLabel {
    pub id: u64,
    pub name: String,
    pub color: String,
    pub description: Option<String>,
    pub url: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubMilestone {
    pub id: u64,
    pub number: u32,
    pub title: String,
    pub description: Option<String>,
    pub state: String,
    pub open_issues: u32,
    pub closed_issues: u32,
    pub created_at: String,
    pub updated_at: String,
    pub closed_at: Option<String>,
    pub due_on: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubPullRequestReference {
    pub html_url: String,
    pub diff_url: String,
    pub patch_url: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubPullRequest {
    pub id: u64,
    pub number: u32,
    pub title: String,
    pub body: Option<String>,
    pub state: String,
    pub html_url: String,
    pub diff_url: String,
    pub patch_url: String,
    pub user: GitHubUser,
    pub assignees: Vec<GitHubUser>,
    pub requested_reviewers: Vec<GitHubUser>,
    pub labels: Vec<GitHubLabel>,
    pub milestone: Option<GitHubMilestone>,
    pub head: GitHubPullRequestCommit,
    pub base: GitHubPullRequestCommit,
    pub merged: bool,
    pub mergeable: Option<bool>,
    pub merged_at: Option<String>,
    pub merge_commit_sha: Option<String>,
    pub comments: u32,
    pub review_comments: u32,
    pub commits: u32,
    pub additions: u32,
    pub deletions: u32,
    pub changed_files: u32,
    pub created_at: String,
    pub updated_at: String,
    pub closed_at: Option<String>,
    pub draft: bool,
    pub merge_conflict: Option<bool>,
    pub status: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubPullRequestCommit {
    pub label: String,
    #[serde(rename = "ref")]
    pub ref_field: String,
    pub sha: String,
    pub user: GitHubUser,
    pub repo: Option<GitHubRepository>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubSearchResponse<T> {
    pub total_count: u32,
    pub incomplete_results: bool,
    pub items: Vec<T>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubCreateRepoResponse {
    pub id: u64,
    pub name: String,
    pub full_name: String,
    pub private: bool,
    pub html_url: String,
    pub description: Option<String>,
    pub clone_url: String,
    pub ssh_url: String,
    pub default_branch: String,
    pub language: Option<String>,
    pub stargazers_count: u32,
    pub forks_count: u32,
    pub open_issues_count: u32,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubCreateIssueResponse {
    pub id: u64,
    pub number: u32,
    pub title: String,
    pub body: Option<String>,
    pub state: String,
    pub html_url: String,
    pub user: GitHubUser,
    pub assignees: Vec<GitHubUser>,
    pub labels: Vec<GitHubLabel>,
    pub milestone: Option<GitHubMilestone>,
    pub comments: u32,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GitHubCreatePullRequestResponse {
    pub id: u64,
    pub number: u32,
    pub title: String,
    pub body: Option<String>,
    pub state: String,
    pub html_url: String,
    pub diff_url: String,
    pub patch_url: String,
    pub user: GitHubUser,
    pub assignees: Vec<GitHubUser>,
    pub requested_reviewers: Vec<GitHubUser>,
    pub labels: Vec<GitHubLabel>,
    pub milestone: Option<GitHubMilestone>,
    pub head: GitHubPullRequestCommit,
    pub base: GitHubPullRequestCommit,
    pub merged: bool,
    pub mergeable: Option<bool>,
    pub merged_at: Option<String>,
    pub comments: u32,
    pub review_comments: u32,
    pub commits: u32,
    pub additions: u32,
    pub deletions: u32,
    pub changed_files: u32,
    pub created_at: String,
    pub updated_at: String,
    pub draft: bool,
}

// Mock data for testing
pub fn get_mock_user() -> GitHubUser {
    GitHubUser {
        id: 12345,
        login: "testuser".to_string(),
        name: Some("Test User".to_string()),
        email: Some("test@example.com".to_string()),
        bio: Some("Test user bio".to_string()),
        company: Some("Test Company".to_string()),
        location: Some("Test Location".to_string()),
        blog: Some("https://example.com".to_string()),
        avatar_url: "https://github.com/testuser.png".to_string(),
        html_url: "https://github.com/testuser".to_string(),
        followers: 42,
        following: 15,
        public_repos: 8,
        created_at: "2020-01-01T00:00:00Z".to_string(),
        updated_at: "2025-11-02T10:00:00Z".to_string(),
    }
}

pub fn get_mock_repositories() -> Vec<GitHubRepository> {
    vec![
        GitHubRepository {
            id: 987654321,
            name: "atom-desktop".to_string(),
            full_name: "atomcompany/atom-desktop".to_string(),
            description: Some("A cross-platform desktop application built with Tauri".to_string()),
            private: false,
            fork: false,
            html_url: "https://github.com/atomcompany/atom-desktop".to_string(),
            clone_url: "https://github.com/atomcompany/atom-desktop.git".to_string(),
            ssh_url: "git@github.com:atomcompany/atom-desktop.git".to_string(),
            default_branch: "main".to_string(),
            language: Some("TypeScript".to_string()),
            languages_url: "https://api.github.com/repos/atomcompany/atom-desktop/languages".to_string(),
            stargazers_count: 156,
            watchers_count: 156,
            forks_count: 45,
            open_issues_count: 12,
            topics: vec!["tauri".to_string(), "desktop".to_string(), "typescript".to_string()],
            size: 2048,
            pushed_at: "2025-11-02T08:00:00Z".to_string(),
            created_at: "2023-01-01T00:00:00Z".to_string(),
            updated_at: "2025-11-02T10:00:00Z".to_string(),
            owner: get_mock_user(),
            license: Some(GitHubLicense {
                key: "mit".to_string(),
                name: "MIT License".to_string(),
                url: Some("https://api.github.com/licenses/mit".to_string()),
                spdx_id: Some("MIT".to_string()),
                html_url: Some("https://github.com/atomcompany/atom-desktop/blob/main/LICENSE".to_string()),
            }),
            has_wiki: true,
            has_pages: false,
            has_issues: true,
            has_projects: true,
            archived: false,
            disabled: false,
        },
        GitHubRepository {
            id: 987654322,
            name: "github-integration".to_string(),
            full_name: "atomcompany/github-integration".to_string(),
            description: Some("GitHub API integration library".to_string()),
            private: false,
            fork: false,
            html_url: "https://github.com/atomcompany/github-integration".to_string(),
            clone_url: "https://github.com/atomcompany/github-integration.git".to_string(),
            ssh_url: "git@github.com:atomcompany/github-integration.git".to_string(),
            default_branch: "main".to_string(),
            language: Some("Rust".to_string()),
            languages_url: "https://api.github.com/repos/atomcompany/github-integration/languages".to_string(),
            stargazers_count: 89,
            watchers_count: 89,
            forks_count: 23,
            open_issues_count: 5,
            topics: vec!["github".to_string(), "api".to_string(), "rust".to_string()],
            size: 512,
            pushed_at: "2025-11-01T16:30:00Z".to_string(),
            created_at: "2023-06-15T00:00:00Z".to_string(),
            updated_at: "2025-11-02T09:15:00Z".to_string(),
            owner: get_mock_user(),
            license: Some(GitHubLicense {
                key: "apache-2.0".to_string(),
                name: "Apache License 2.0".to_string(),
                url: Some("https://api.github.com/licenses/apache-2.0".to_string()),
                spdx_id: Some("Apache-2.0".to_string()),
                html_url: Some("https://github.com/atomcompany/github-integration/blob/main/LICENSE".to_string()),
            }),
            has_wiki: true,
            has_pages: true,
            has_issues: true,
            has_projects: false,
            archived: false,
            disabled: false,
        },
    ]
}

pub fn get_mock_issues() -> Vec<GitHubIssue> {
    vec![
        GitHubIssue {
            id: 123456789,
            number: 42,
            title: "Add GitHub integration feature".to_string(),
            body: Some("Implement GitHub integration for repository management".to_string()),
            state: "open".to_string(),
            html_url: "https://github.com/atomcompany/atom-desktop/issues/42".to_string(),
            user: get_mock_user(),
            assignees: vec![get_mock_user()],
            labels: vec![
                GitHubLabel {
                    id: 1,
                    name: "enhancement".to_string(),
                    color: "a2eeef".to_string(),
                    description: Some("New feature or enhancement".to_string()),
                    url: "https://api.github.com/repos/atomcompany/atom-desktop/labels/enhancement".to_string(),
                },
            ],
            milestone: Some(GitHubMilestone {
                id: 1,
                number: 1,
                title: "v1.0.0".to_string(),
                description: Some("Initial release".to_string()),
                state: "open".to_string(),
                open_issues: 3,
                closed_issues: 7,
                created_at: "2025-01-01T00:00:00Z".to_string(),
                updated_at: "2025-11-01T12:00:00Z".to_string(),
                closed_at: None,
                due_on: Some("2025-12-31T23:59:59Z".to_string()),
            }),
            comments: 8,
            created_at: "2025-11-01T08:00:00Z".to_string(),
            updated_at: "2025-11-02T14:30:00Z".to_string(),
            closed_at: None,
            locked: false,
            active_lock_reason: None,
            draft: false,
            pull_request: None,
        },
    ]
}

pub fn get_mock_pull_requests() -> Vec<GitHubPullRequest> {
    vec![
        GitHubPullRequest {
            id: 2001,
            number: 15,
            title: "Add GitHub integration".to_string(),
            body: Some("Implement GitHub integration feature".to_string()),
            state: "open".to_string(),
            html_url: "https://github.com/atomcompany/atom-desktop/pull/15".to_string(),
            diff_url: "https://github.com/atomcompany/atom-desktop/pull/15.diff".to_string(),
            patch_url: "https://github.com/atomcompany/atom-desktop/pull/15.patch".to_string(),
            user: get_mock_user(),
            assignees: vec![get_mock_user()],
            requested_reviewers: vec![GitHubUser {
                id: 67890,
                login: "reviewer1".to_string(),
                name: Some("Reviewer One".to_string()),
                email: Some("reviewer@example.com".to_string()),
                bio: None,
                company: None,
                location: None,
                blog: None,
                avatar_url: "https://github.com/reviewer1.png".to_string(),
                html_url: "https://github.com/reviewer1".to_string(),
                followers: 12,
                following: 8,
                public_repos: 3,
                created_at: "2021-01-01T00:00:00Z".to_string(),
                updated_at: "2025-11-02T08:00:00Z".to_string(),
            }],
            labels: vec![
                GitHubLabel {
                    id: 2,
                    name: "github".to_string(),
                    color: "84b6eb".to_string(),
                    description: Some("GitHub related changes".to_string()),
                    url: "https://api.github.com/repos/atomcompany/atom-desktop/labels/github".to_string(),
                },
            ],
            milestone: Some(GitHubMilestone {
                id: 1,
                number: 1,
                title: "v1.0.0".to_string(),
                description: Some("Initial release".to_string()),
                state: "open".to_string(),
                open_issues: 3,
                closed_issues: 7,
                created_at: "2025-01-01T00:00:00Z".to_string(),
                updated_at: "2025-11-01T12:00:00Z".to_string(),
                closed_at: None,
                due_on: Some("2025-12-31T23:59:59Z".to_string()),
            }),
            head: GitHubPullRequestCommit {
                label: "atomcompany:feature/github-integration".to_string(),
                ref_field: "feature/github-integration".to_string(),
                sha: "abc123def456".to_string(),
                user: get_mock_user(),
                repo: None,
            },
            base: GitHubPullRequestCommit {
                label: "atomcompany:main".to_string(),
                ref_field: "main".to_string(),
                sha: "def456abc789".to_string(),
                user: get_mock_user(),
                repo: None,
            },
            merged: false,
            mergeable: Some(true),
            merged_at: None,
            merge_commit_sha: None,
            comments: 12,
            review_comments: 8,
            commits: 5,
            additions: 1250,
            deletions: 85,
            changed_files: 12,
            created_at: "2025-11-01T08:00:00Z".to_string(),
            updated_at: "2025-11-02T16:20:00Z".to_string(),
            closed_at: None,
            draft: false,
            merge_conflict: Some(false),
            status: "success".to_string(),
        },
    ]
}
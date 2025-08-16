# GitHub Integration Guide

This guide provides instructions on how to set up and use the GitHub integration in Atom.

## Prerequisites

- You must have an Atom account.
- You must have a GitHub account.

## 1. Enable the 'Developer' Role

To use the GitHub integration, you must first enable the 'Developer' role in your Atom settings.

1.  Go to **Settings**.
2.  Under the **Roles** section, enable the **Developer** role.

## 2. Connect Your GitHub Account

Once you have enabled the 'Developer' role, you can connect your GitHub account.

1.  Go to **Settings** > **Integrations**.
2.  You should now see the **GitHub** integration.
3.  Click the **Connect** button.
4.  You will be redirected to GitHub to authorize the application.
5.  Once you have authorized the application, you will be redirected back to Atom.

Your GitHub account is now connected.

## 3. Using the GitHub Integration

You can now use the GitHub integration to interact with your repositories.

### Create a GitHub Issue

You can create a new issue in a repository using the `createGithubIssue` skill.

**Example:**

```
createGithubIssue(repo: "owner/repo", title: "New Issue", body: "This is a new issue.")
```

### List GitHub Repositories

You can list your repositories using the `listGithubRepos` skill.

**Example:**

```
listGithubRepos()
```

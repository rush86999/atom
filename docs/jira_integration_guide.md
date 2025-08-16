# Jira Integration Guide

This guide provides instructions on how to set up and use the Jira integration in Atom.

## Prerequisites

- You must have an Atom account.
- You must have a Jira Cloud account.

## 1. Connect Your Jira Account

1.  Go to **Settings** > **Integrations**.
2.  You should see the **Jira** integration.
3.  Click the **Connect** button.
4.  You will be redirected to Atlassian to authorize the application.
5.  Once you have authorized the application, you will be redirected back to Atom.

Your Jira account is now connected.

## 2. Using the Jira Integration

You can now use the Jira integration to interact with your projects and issues.

### List Your Projects

You can list your projects using the `listJiraProjects` skill.

**Example:**

```
listJiraProjects()
```

### List Issues in a Project

You can list the issues in a project using the `listJiraIssues` skill.

**Example:**

```
listJiraIssues(projectId: "your_project_id")
```

### Create an Issue

You can create a new issue using the `createJiraIssue` skill.

**Example:**

```
createJiraIssue(projectId: "your_project_id", summary: "New Issue", description: "This is a new issue.")
```

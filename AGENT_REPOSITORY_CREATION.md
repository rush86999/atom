# 🎯 ATOM AI Repository Creation - Agent Integration Guide

## Overview
The ATOM AI system now automatically **creates new GitHub repositories** for web app development via conversational triggers. Instead of running builds in the main ATOM repo, the 9-agent orchestration system **spawns fresh repositories** for each user project.

## How It Works

### 🤖 Conversation Triggers
The ATOM agent automatically detects when users want to create new web applications:

**Example Conversations:**
```
User: "Create a next.js blog project called my-awesome-blog"
ATOM: 🎉 **Your new web app has been created!**

User: "Build a react website named portfolio, make it private"
ATOM: ✅ Repository created: portfolio-abc123 (private)

User: "Start a vanilla javascript calculator app"
ATOM: 🚀 Repository ready: calculator-app-xyz789
```

### 📋 Available Templates
| Template Type | Description | Agent Triggers |
|---------------|-------------|----------------|
| **nextjs-basic** | Next.js 14 with TypeScript, Tailwind | "nextjs", "react app", "spa" |
| **nextjs-fullstack** | Next.js + API routes + Database | "fullstack", "full-stack", "crud" |
| **react-vite** | React + Vite (client-only) | "react", "vite", "frontend" |
| **vanilla-js** | Plain HTML/CSS/JS | "vanilla", "plain", "simple" |
| **node-express** | Node.js + Express API | "node", "express", "api" |

## 🚀 Quick Start for Users

### Option 1: Via ATOM Conversation
Simply message ATOM with natural language:
```
"Make me a nextjs project for a SaaS landing page"
```

### Option 2: Via Direct API
```bash
POST /api/agent/create-repository
{
  "userId": "current-user",
  "intent": "create-web-app",
  "parameters": {
    "projectName": "my-awesome-app",
    "templateType": "nextjs-basic",
    "isPrivate": false
  }
+}
+```
+
+## 📁 What You Get
+Each new repository includes:
+
+✅ **Modern setup** with chosen template
+✅ **GitHub Actions** for automatic Vercel deployment  
+✅ **README** with setup instructions
+✅ **Development scripts** (`dev`, `build`, `start`)
+✅ **Live deployment** on `git push`
+✅ **Isolated environment** - no interference with ATOM repo
+
+## 🔧 Development Setup
+
+### Existing System Components
+
+**Files Created:**
+- `src/orchestration/AgentRepositoryIntegration.ts` - Main agent handler
+- `src/orchestration/webAppRepositoryOrchestrator.ts` - Repository creation logic
+- `src/orchestration/repositoryCreationEndpoint.ts` - REST API endpoints
+- `src/skills/githubSkills.ts` - GitHub API integration
+
+### Environment Variables Required
+```bash
+GITHUB_TOKEN=your_github_personal_access_token
+ATOM_AGENT_SECRET=your_agent_secret_key
+```
+
+### Registering with ATOM Agent System
+Add to your orchestration initialization:
+```typescript
+import { AgentRepositoryIntegration } from './AgentRepositoryIntegration';
+
+// Register the repository creation agent
+AgentRepositoryIntegration.register(orchestrationEngine);
+```
+
+## 🛡️ Security & Authentication
+
+### GitHub Token Requirements
+- **Personal Access Token** (PAT) with these scopes:
+  - `repo` (full repository access)
+  - `workflow` (GitHub Actions)
+  - `admin:repo_hook` (webhooks)
+
+### Token Storage
+Tokens are securely stored via the existing ATOM auth system and reused across requests.
+
+## 🔄 Integration Flow: ATOM → New Repository
+
+1. **Conversation Detected** → ATOM agent parses natural language
+2. **Intent Recognition** → Extracts project name + template
+3. **Repository Creation** → Creates GitHub repo via PAT
+4. **Template Generation** → Populates with chosen framework
+5. **Response Delivery** → Provides clone URL and next steps
+
+## 🗣️ Example Agent Conversations
+
+### Complex Request
+```
+User: "I need a fullstack next.js application for a todo app with auth,
+       call it taskmaster, make it private please"
+
+ATOM: 🎉 **Your new project "taskmaster-abc123" has been created!**
+
+🔗 Repository: https://github.com/username/taskmaster-abc123
+📂 Template: Next.js (Full-stack)
+🔒 Visibility: Private

# 🚀 Creating New Web Apps with ATOM AI

## Overview
The ATOM repository now uses a **repository-spawning approach** instead of building within this main repo. This prevents GitHub Actions from triggering unnecessarily and keeps each web app project in its own focused repository.

## How It Works
Instead of running builds in this repo, ATOM **creates entirely new repositories** for each web development project. This gives you:
- Clean, isolated environments per project
- No interference with this ATOM dev repo
- Optimized CI/CD for each individual app
- Better collaboration and version control per project

## Creating a New Web App

### Method 1: Via GitHub Actions (One Click)
1. Go to **GitHub Actions tab** in this repository
2. Select **"Create New Web App Repository"**
3. Fill in:
   - **Project Name**: Your app's name
   - **Template**: Choose from Next.js, React, Vanilla JS, or Node.js
   - **Private**: Check if you want a private repo
4. Click **"Run workflow"**
5. Grab your new repo URL when it's ready!

### Method 2: Via GitHub CLI
```bash
# Using GitHub CLI
gh workflow run create-new-app-repo.yml -f project_name="my-awesome-app" -f template_type="nextjs-basic"
```

### Method 3: Manually via GitHub Web
1. Navigate to: `https://github.com/[your-username]/atom/actions/workflows/create-new-app-repo.yml`
2. Click **"Run workflow"**
3. Fill out the form and submit

## Available Templates
| Template | Description | Best For |
|---|---|---|
| **nextjs-basic** | Next.js 14 with TypeScript, Tailwind | Modern React SPA |
| **nextjs-fullstack** | Next.js with API routes, Prisma | Full-stack apps |
| **react-vite** | Vite + React (client only) | Fast development |
| **vanilla-js** | Simple HTML/CSS/JS | Learning/small projects |
| **node-express** | Node.js with Express.js | APIs and backends |

## What You Get
Each new repository includes:
- ✅ Pre-configured development environment
- ✅ GitHub Actions for automatic deployment
- ✅ README with setup instructions
- ✅ Development scripts (`dev`, `build`, `start`)
- ✅ GitHub Pages ready (for frontend templates)
- ✅ Vercel deployment config

## Example Usage Flow
```bash
# 1. Create new app via GitHub Actions UI
# Get: https://github.com/yourusername/my-app-123456789

# 2. Clone and develop
git clone https://github.com/yourusername/my-app-123456789.git
cd my-app-123456789
npm install
npm run dev

# 3. Push to deploy to Vercel
git add .
git commit -m "feature: new landing page"
git push origin main
```

## Managing Your App Repositories
- **Find all app repos**: They'll be in your GitHub account with descriptive names
- **Template updates**: Each repo is self-contained - no auto-synchronization
- **Collaboration**: Invite team members directly to individual project repos
- **Deployment**: One-click deploy to your chosen service (Vercel/Netlify/etc.)

## Troubleshooting
- **Actions not running?**: Ensure you have GitHub Actions enabled and sufficient quota
- **Permission errors**: Ensure your GitHub token has repo creation permissions
- **Name conflicts**: The system auto-generates unique names (timestamps appended)

## Best Practices
- Use **descriptive project names** in the input
- Choose **templates** based on your actual needs
- Make repos **private** for client work or sensitive projects
- **Don't hesitate** - creating repos is free and unlimited!

---

*This approach keeps the main ATOM repository clean while giving you unlimited separate project repositories for web development.*
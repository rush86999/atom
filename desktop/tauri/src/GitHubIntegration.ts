// atom/desktop/tauri/src/GitHubIntegration.ts
// Real GitHub integration for desktop app - personalized repositories

import { invoke } from '@tauri-apps/api/tauri';
import { open } from '@tauri-apps/api/shell';

interface GitHubUser {
  token: string;
  login: string;
  avatar_url: string;
  html_url: string;
}

interface RepositoryData {
  name: string;
  full_name: string;
  private: boolean;
  description: string;
  clone_url: string;
  html_url: string;
}

interface BuildResult {
  repo: RepositoryData;
  vercelUrl: string;
  netlifyUrl?: string;
  localPath?: string;
  logs: string[];
}

class GitHubIntegration {
  private baseUrl = 'https://api.github.com';
  private userToken: string | null = null;
  private userLogin: string | null = null;

  async authenticate(token: string) {
    this.userToken = token;

    try {
      const response = await fetch(`${this.baseUrl}/user`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      });
      const userData = await response.json();

      if (userData.login) {
        this.userLogin = userData.login;
        await invoke('store_user_token', { token, login: userData.login });
      }

      return this.userLogin;
    } catch (error) {
      throw new Error('Invalid GitHub token');
    }
  }

  async getAuthenticatedUser(): Promise<GitHubUser | null> {
    if (!this.userToken) return null;

    try {
      const response = await fetch(`${this.baseUrl}/user`, {
        headers: {
          'Authorization': `Bearer ${this.userToken}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      });
      return await response.json();
    } catch (error) {
      console.error('Failed to get user:', error);
      return null;
    }
  }

  async createProject(projectName: string, instruction: string): Promise<BuildResult> {
    if (!this.userLogin) throw new Error('User not authenticated');

    const repoName = `atom-${projectName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')}-${Date.now().toString(36)}`;

    // Create repository via Tauri
    const repo = await this.createRepository(repoName, instruction);

    // Setup Vercel deployment
    const vercelUrl = await this.setupVercelDeployment(repo.full_name, repoName);

    // Setup Netlify as fallback
    const netlifyUrl = await this.setupNetlifyDeployment(repo.full_name);

    return {
      repo,
      vercelUrl,
      netlifyUrl,
      logs: [`Created repository: ${repo.full_name}`, `Vercel deployed to: ${vercelUrl}`]
    };
  }

  private async createRepository(name: string, description: string): Promise<RepositoryData> {
    if (!this.userToken) throw new Error('Not authenticated');

    // Create empty repository
    const response = await fetch(`${this.baseUrl}/user/repos`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.userToken}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name,
        description: `AI-generated via ATOM: ${description}`,
        auto_init: true,
        private: false,
        gitignore_template: 'Node'
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to create repository: ${response.statusText}`);
    }

    return await response.json();
  }

  async pushStarterTemplate(repoFullName: string, template: string = 'nextjs-basic'): Promise<void> {
    const templates = {
      'nextjs-basic': {
        files: {
          'package.json': JSON.stringify({
            name: repoFullName.split('/')[1],
            version: "1.0.0",
            scripts: {
              dev: "next dev",
              build: "next build",
              start: "next start"
            },
            dependencies: {
              next: "^14.0.0",
              react: "^18.2.0",
              "react-dom": "^18.2.0",
              tailwindcss: "^3.3.0",
              autoprefixer: "^10.4.0"
            }
          }, null, 2),
          'next.config.js': `module.exports = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true
}`,
          'tailwind.config.js': `module.exports = {
  content: ['./pages/**/*.{js

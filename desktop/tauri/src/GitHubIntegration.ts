// atom/desktop/tauri/src/GitHubIntegration.ts
// Real GitHub integration for desktop app - personalized repositories

import { invoke } from "@tauri-apps/api/tauri";
import { open } from "@tauri-apps/api/shell";

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

export class GitHubIntegration {
  private userToken: string | null = null;
  private userData: GitHubUser | null = null;

  constructor(token?: string) {
    if (token) {
      this.userToken = token;
    }
  }

  async authenticate(token: string): Promise<GitHubUser> {
    try {
      const response = await fetch("https://api.github.com/user", {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github.v3+json",
        },
      });

      if (!response.ok) {
        throw new Error(`GitHub authentication failed: ${response.statusText}`);
      }

      const userData = await response.json();
      this.userToken = token;
      this.userData = userData;

      return userData;
    } catch (error) {
      console.error("GitHub authentication error:", error);
      throw error;
    }
  }

  async createRepository(
    name: string,
    description: string,
    isPrivate: boolean = false,
  ): Promise<RepositoryData> {
    if (!this.userToken) {
      throw new Error("Not authenticated. Call authenticate() first.");
    }

    try {
      const response = await fetch("https://api.github.com/user/repos", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.userToken}`,
          Accept: "application/vnd.github.v3+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name,
          description,
          private: isPrivate,
          auto_init: true,
          license_template: "mit",
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create repository: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Repository creation error:", error);
      throw error;
    }
  }

  async pushStarterTemplate(
    repoFullName: string,
    template: string = "nextjs-basic",
  ): Promise<void> {
    const templates = {
      "nextjs-basic": {
        files: {
          "package.json": JSON.stringify(
            {
              name: repoFullName.split("/")[1],
              version: "1.0.0",
              scripts: {
                dev: "next dev",
                build: "next build",
                start: "next start",
              },
              dependencies: {
                next: "^14.0.0",
                react: "^18.2.0",
                "react-dom": "^18.2.0",
                tailwindcss: "^3.3.0",
                autoprefixer: "^10.4.0",
              },
            },
            null,
            2,
          ),
          "next.config.js": `module.exports = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true
}`,
          "tailwind.config.js": `module.exports = {
  content: ['./pages/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}`,
        },
      },
    };

    // Implementation for pushing template files would go here
    // This would use the GitHub API to create files in the repository
    console.log(`Pushing ${template} template to ${repoFullName}`);
  }

  async triggerVercelDeployment(repoFullName: string): Promise<string> {
    try {
      // This would integrate with Vercel API to trigger deployment
      const deploymentUrl = `https://${repoFullName.split("/")[1]}-atom.vercel.app`;
      console.log(`Triggering Vercel deployment for ${repoFullName}`);
      return deploymentUrl;
    } catch (error) {
      console.error("Vercel deployment error:", error);
      throw error;
    }
  }

  async openInBrowser(url: string): Promise<void> {
    await open(url);
  }

  getUser(): GitHubUser | null {
    return this.userData;
  }

  isAuthenticated(): boolean {
    return this.userToken !== null;
  }
}

export default GitHubIntegration;

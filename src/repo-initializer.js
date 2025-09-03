// atom/src/repo-initializer.js
// Personalized GitHub repository creation for each end user's projects
// Runs on user's behalf with their GitHub account

const fs = require('fs').promises;
const path = require('path');

class GitHubRepositoryInitializer {
  constructor(githubToken, userLogin) {
    this.token = githubToken;
    this.userLogin = userLogin;
    this.baseUrl = 'https://api.github.com';
  }

  async createUserRepository(projectName, template = 'nextjs-conversation-starter') {
    const repoName = `${projectName}-${Date.now().toString(36)}`;

    const repoData = {
      name: repoName,
      description: `ATOM AI generated ${projectName} via conversation`,
      private: false,
      auto_init: true,
      gitignore_template: 'Node',
      license_template: 'mit'
    };

    // Get user's GitHub token (desktop app handles this)
    const repo = await this.apiCall('/user/repos', 'POST', repoData);
    if (!repo) throw new Error('Failed to create repository');

    // Add Next.js starter template
    await this.pushStarterTemplate(repo.full_name);

    return {
      repoUrl: repo.html_url,
      cloneUrl: repo.clone_url,
      id: repo.id,
      name: repo.name,
      fullName: repo.full_name
    };
  }

  async apiCall(endpoint, method = 'GET', body = null) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
      },
      body: body ? JSON.stringify(body) : null
    });

    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  async pushStarterTemplate(repoFullName) {
    const templateFiles = await this.prepareNextJSTemplate();
    const commitMessage = 'Initial commit with Next.js template';

    // Create root commit with template files
    const tree = await this.createTree(repoFullName, templateFiles);
    const commit = await this.createCommit(repoFullName, tree.sha, commitMessage);
    await this.updateMainRef(repoFullName, commit.sha);

    return true;
  }

  async prepareNextJSTemplate() {
    return [
      {
        path: 'package.json',
        content: JSON.stringify({
          name: 'atom-generated-site',
          version: '1.0.0',
          scripts: {
            dev: 'next dev',
            build: 'next build',
            start: 'next start',
            export: 'next export'
          },
          dependencies: {
            next: '^14.0.0',
            react: '^18.2.0',
            react-dom: '^18.2.0',
            tailwindcss: '^3.3.0',
            autoprefixer: '^10.4.0',
            postcss: '^8.4.0'
          }
        }, null, 2)
      },
      {
        path: 'next.config.js',
        content: `module.exports = {
  output: 'export',
  images: {
    unoptimized: true
  }
}`
      },
      {
        path: 'pages/index.js',
        content: `import Head from 'next/head'

export default function Home({ features = [] }) {
  return (
    <div className="min-h-screen bg-white">
      <Head>
        <title>ATOM Generated Page</title>
        <meta name="description" content="Generated via ATOM AI" />
      </Head>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Welcome to Your Custom Site
          </h1>
          <p className="text-xl text-gray-600">
            This page was generated via ATOM AI conversation
          </p>
        </div>
      </main>
    </div>
  );
}`
      },
      {
        path: 'tailwind.config.js',
        content: `module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}`
      },
      {
        path: 'postcss.config.js',
        content: `module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}`
      },
      {
        path: 'pages/_app.js',
        content: `import '../styles/globals.css'

export default function App({ Component, pageProps }) {
  return <Component {...pageProps} />
}`
      },
      {
        path: 'styles/globals.css',
        content: `@tailwind base;
@tailwind components;
@tailwind utilities;`
      }
    ];
  }

  async createTree(repoFullName, files) {
    const treeItems = [];

    for (const file of files) {
      const encodedContent = Buffer.from(file.content).toString('base64');

      treeItems.push({
        path: file.path,
        mode: '100644',
        type: 'blob',
        content: encodedContent
      });
    }

    const response = await this.apiCall(`/repos/${repoFullName}/git/trees`, 'POST', {
      tree: treeItems,
      base_tree: null // Create new tree
    });

    return response;
  }

  async createCommit(repoFullName, treeSha, message) {
    // Get the current HEAD commit to use as parent
    const refResponse = await this.apiCall(`/repos/${repoFullName}/git/refs/heads/main`);
    const parentSha = refResponse.object.sha;

    const response = await this.apiCall(`/repos/${repoFullName}/git/commits`, 'POST', {
      message,
      tree: treeSha,
      parents: [parentSha]
    });

    return response;
  }

  async updateMainRef(repoFullName, commitSha) {
    const response = await this.apiCall(`/repos/${repoFullName}/git/refs/heads/main`, 'PATCH', {
      sha: commitSha,
      force: false
    });

    return response;
  }

  async getRepository(repoFullName) {
    return this.apiCall(`/repos/${repoFullName}`);
  }

  async listUserRepositories() {
    return this.apiCall('/user/repos');
  }

  async deleteRepository(repoFullName) {
    return this.apiCall(`/repos/${repoFullName}`, 'DELETE');
  }

  async enablePages(repoFullName) {
    return this.apiCall(`/repos/${repoFullName}/pages`, 'POST', {
      source: {
        branch: 'main',
        path: '/'
      }
    });
  }

  async getPagesStatus(repoFullName) {
    return this.apiCall(`/repos/${repoFullName}/pages`);
  }

  async triggerGitHubAction(repoFullName, workflowId, inputs = {}) {
    return this.apiCall(`/repos/${repoFullName}/actions/workflows/${workflowId}/dispatches`, 'POST', {
      ref: 'main',
      inputs
    });
  }

  async getWorkflowRuns(repoFullName) {
    return this.apiCall(`/repos/${repoFullName}/actions/runs`);
  }
}

module.exports = GitHubRepositoryInitializer;

// Utility function for direct usage
async function createRepositoryFromConversation(projectName, githubToken, userLogin) {
  const initializer = new GitHubRepositoryInitializer(githubToken, userLogin);
  return initializer.createUserRepository(projectName);
}

module.exports.createRepositoryFromConversation = createRepositoryFromConversation;

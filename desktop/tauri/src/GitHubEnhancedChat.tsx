/**
 * Enhanced GitHub Chat Component
 * Natural language GitHub automation
 */

import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/tauri";
import { 
  githubRepoSkill, 
  githubIssueSkill,
  githubPullRequestSkill,
  GitHubRepoSkillParams,
  GitHubIssueSkillParams,
  GitHubPullRequestSkillParams
} from "../skills/githubSkills";
import { 
  nlpService, 
  Intent, 
  Entity, 
  SkillExecutionContext 
} from "../services/nlpService";
import { EventBus } from "../utils/EventBus";
import { Logger } from "../utils/Logger";
import "./App.css";

interface Message {
  id: string;
  text: string;
  sender: "user" | "agent";
  timestamp: string;
  skillsUsed?: string[];
  context?: any;
}

interface ChatResponse {
  text: string;
  skillsExecuted?: string[];
  context?: any;
  suggestions?: string[];
}

interface GitHubSkillResult {
  success: boolean;
  data?: any;
  error?: string;
}

function GitHubEnhancedChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [githubConnected, setGitHubConnected] = useState(false);
  
  const logger = new Logger('GitHubEnhancedChat');

  // Check GitHub connection status
  useEffect(() => {
    checkGitHubConnection();
    
    // Listen for GitHub events
    EventBus.on('github:repo:created', (data) => {
      logger.info('GitHub repo created', data);
      addSystemMessage(`✅ Repository created: ${data.repo_name}`);
    });
    
    EventBus.on('github:issue:created', (data) => {
      logger.info('GitHub issue created', data);
      addSystemMessage(`🐛 Issue created: #${data.issue_number} - ${data.issue_title}`);
    });
    
    EventBus.on('github:pr:created', (data) => {
      logger.info('GitHub PR created', data);
      addSystemMessage(`🔄 Pull request created: #${data.pr_number} - ${data.pr_title}`);
    });
    
    EventBus.on('github:issues:processed', (data) => {
      logger.info('GitHub issues processed', data);
      addSystemMessage(`📊 Processed ${data.total} issues: ${data.open} open, ${data.closed} closed`);
    });

    return () => {
      EventBus.off('github:repo:created');
      EventBus.off('github:issue:created');
      EventBus.off('github:pr:created');
      EventBus.off('github:issues:processed');
    };
  }, []);

  const checkGitHubConnection = async () => {
    try {
      const result = await invoke<any>('get_github_connection', {
        userId: 'desktop-user'
      });
      setGitHubConnected(result.connected);
    } catch (error) {
      logger.warn('Failed to check GitHub connection', error);
      setGitHubConnected(false);
    }
  };

  const addSystemMessage = (text: string) => {
    const systemMessage: Message = {
      id: Date.now().toString(),
      text,
      sender: "agent",
      timestamp: new Date().toISOString(),
      skillsUsed: ["system"]
    };
    setMessages(prev => [...prev, systemMessage]);
  };

  const handleSend = async () => {
    if (input.trim() === "") return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: input,
      sender: "user",
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    const userInput = input;
    setInput("");
    setIsLoading(true);

    try {
      // Process the message with NLP
      const nlpResult = await nlpService.processMessage(userInput);
      const response = await processUserMessage(userInput, nlpResult);
      
      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.text,
        sender: "agent",
        timestamp: new Date().toISOString(),
        skillsUsed: response.skillsExecuted,
        context: response.context
      };
      
      setMessages(prev => [...prev, agentMessage]);
      
      // Add suggestions if available
      if (response.suggestions && response.suggestions.length > 0) {
        setTimeout(() => {
          const suggestionsMessage: Message = {
            id: (Date.now() + 2).toString(),
            text: `💡 Suggestions: ${response.suggestions.join(" • ")}`,
            sender: "agent",
            timestamp: new Date().toISOString(),
            skillsUsed: ["suggestions"]
          };
          setMessages(prev => [...prev, suggestionsMessage]);
        }, 500);
      }
      
    } catch (error) {
      logger.error('Failed to process message', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: "Sorry, I encountered an error processing your request. Please try again.",
        sender: "agent",
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const processUserMessage = async (message: string, nlpResult: any): Promise<ChatResponse> => {
    const { intent, entities, confidence } = nlpResult;
    
    logger.info('Processing GitHub message', { intent, entities, confidence });
    
    // Create execution context
    const context: SkillExecutionContext = {
      userId: 'desktop-user',
      sessionId: Date.now().toString(),
      timestamp: new Date().toISOString(),
      intent: intent,
      entities: entities,
      confidence: confidence
    };

    // Handle GitHub-specific intents
    switch (intent) {
      case 'github_list_repos':
        return await handleListRepositories(entities, context);
        
      case 'github_create_repo':
        return await handleCreateRepository(entities, context);
        
      case 'github_search_repos':
        return await handleSearchRepositories(entities, context);
        
      case 'github_list_issues':
        return await handleListIssues(entities, context);
        
      case 'github_create_issue':
        return await handleCreateIssue(entities, context);
        
      case 'github_search_issues':
        return await handleSearchIssues(entities, context);
        
      case 'github_list_prs':
        return await handleListPullRequests(entities, context);
        
      case 'github_create_pr':
        return await handleCreatePullRequest(entities, context);
        
      case 'github_search_prs':
        return await handleSearchPullRequests(entities, context);
        
      case 'github_help':
        return getGitHubHelp();
        
      case 'github_status':
        return getGitHubStatus();
        
      default:
        return await handleGeneralMessage(message, nlpResult, context);
    }
  };

  const handleListRepositories = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!githubConnected) {
      return {
        text: "❌ GitHub is not connected. Please connect your GitHub account in Settings first.",
        skillsExecuted: ["github_check"]
      };
    }

    const limit = extractEntityValue(entities, 'count') || extractEntityValue(entities, 'limit') || 10;
    const owner = extractEntityValue(entities, 'owner');
    const type = extractEntityValue(entities, 'type');

    try {
      let params: GitHubRepoSkillParams = {
        action: 'list',
        limit: typeof limit === 'string' ? parseInt(limit) : limit
      };

      // Handle specific owner repositories
      if (owner) {
        params.owner = owner;
        params.action = 'list_user';
      }

      // Handle repository type
      if (type === 'private' || type === 'public') {
        params.type = type;
      }

      const result = await githubRepoSkill.execute(params, context);
      
      if (result.success && result.repositories) {
        const repoList = result.repositories.map((repo: any) => 
          `• ${repo.full_name} (${repo.private ? 'Private' : 'Public'}) - ${repo.stargazers_count} ⭐, ${repo.forks_count} 🍴${repo.language ? ` - ${repo.language}` : ''}`
        ).join('\n');

        return {
          text: `📚 Found ${result.count} repositories:\n\n${repoList}`,
          skillsExecuted: ["github_repo_list"],
          context: result,
          suggestions: [
            "Create a new repository",
            "Search repositories",
            "View repository details"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to retrieve repositories: ${error}`,
        skillsExecuted: ["github_repo_list"]
      };
    }
  };

  const handleCreateRepository = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!githubConnected) {
      return {
        text: "❌ GitHub is not connected. Please connect your GitHub account in Settings first.",
        skillsExecuted: ["github_check"]
      };
    }

    const name = extractEntityValue(entities, 'repo_name') || extractEntityValue(entities, 'repository');
    const description = extractEntityValue(entities, 'description');
    const isPrivate = extractEntityValue(entities, 'private') !== undefined;
    const language = extractEntityValue(entities, 'language');

    if (!name) {
      return {
        text: "📚 I need a repository name to create one. For example: \"Create a new repository 'my-project' with description 'My awesome project'\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubRepoSkillParams = {
        action: 'create',
        name: name,
        description: description,
        private: isPrivate,
        language: language
      };

      const result = await githubRepoSkill.execute(params, context);
      
      if (result.success) {
        return {
          text: `✅ Repository "${result.repository_name}" created successfully${result.repository_url ? ` at ${result.repository_url}` : ''}`,
          skillsExecuted: ["github_repo_create"],
          context: result,
          suggestions: [
            "Initialize the repository with a README",
            "Add collaborators to the repository",
            "Create the first issue or pull request"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to create repository: ${error}`,
        skillsExecuted: ["github_repo_create"]
      };
    }
  };

  const handleSearchRepositories = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    const searchQuery = extractEntityValue(entities, 'search_query') || extractEntityValue(entities, 'query');
    
    if (!searchQuery) {
      return {
        text: "🔍 What would you like me to search for in repositories? For example: \"Search repositories for 'react components'\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubRepoSkillParams = {
        action: 'search',
        searchQuery: typeof searchQuery === 'string' ? searchQuery : searchQuery.toString(),
        limit: 10
      };

      const result = await githubRepoSkill.execute(params, context);
      
      if (result.success && result.repositories) {
        const repoList = result.repositories.map((repo: any) => 
          `• ${repo.full_name} - ${repo.description || 'No description'} - ${repo.stargazers_count} ⭐${repo.language ? ` - ${repo.language}` : ''}`
        ).join('\n');

        return {
          text: `🔍 Found ${result.count} repositories matching "${searchQuery}":\n\n${repoList}`,
          skillsExecuted: ["github_repo_search"],
          context: result
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to search repositories: ${error}`,
        skillsExecuted: ["github_repo_search"]
      };
    }
  };

  const handleListIssues = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!githubConnected) {
      return {
        text: "❌ GitHub is not connected. Please connect your GitHub account in Settings first.",
        skillsExecuted: ["github_check"]
      };
    }

    const repo = extractEntityValue(entities, 'repository') || extractEntityValue(entities, 'repo');
    const owner = extractEntityValue(entities, 'owner');
    const state = extractEntityValue(entities, 'state') || extractEntityValue(entities, 'status');
    const limit = extractEntityValue(entities, 'count') || extractEntityValue(entities, 'limit') || 10;

    if (!repo || !owner) {
      return {
        text: "🐛 I need the owner and repository name to list issues. For example: \"List open issues for atomcompany/atom-desktop\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubIssueSkillParams = {
        action: 'list',
        owner: owner,
        repo: repo,
        state: state === 'open' || state === 'closed' ? state : 'open',
        limit: typeof limit === 'string' ? parseInt(limit) : limit
      };

      const result = await githubIssueSkill.execute(params, context);
      
      if (result.success && result.issues) {
        const issueList = result.issues.map((issue: any) => 
          `• #${issue.number} ${issue.title} (${issue.state})${issue.assignees.length > 0 ? ` - Assigned to ${issue.assignees.map((a: any) => a.login).join(', ')}` : ''}${issue.labels.length > 0 ? ` - ${issue.labels.map((l: any) => l.name).join(', ')}` : ''}`
        ).join('\n');

        return {
          text: `🐛 Found ${result.count} issues in ${owner}/${repo}:\n\n${issueList}`,
          skillsExecuted: ["github_issue_list"],
          context: result,
          suggestions: [
            "Create a new issue",
            "Search for specific issues",
            "Filter issues by labels or assignees"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to retrieve issues: ${error}`,
        skillsExecuted: ["github_issue_list"]
      };
    }
  };

  const handleCreateIssue = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!githubConnected) {
      return {
        text: "❌ GitHub is not connected. Please connect your GitHub account in Settings first.",
        skillsExecuted: ["github_check"]
      };
    }

    const repo = extractEntityValue(entities, 'repository') || extractEntityValue(entities, 'repo');
    const owner = extractEntityValue(entities, 'owner');
    const title = extractEntityValue(entities, 'title') || extractEntityValue(entities, 'issue_title');
    const body = extractEntityValue(entities, 'body') || extractEntityValue(entities, 'description') || extractEntityValue(entities, 'issue_body');
    const labels = extractEntityValue(entities, 'labels');
    const assignees = extractEntityValue(entities, 'assignees');

    if (!repo || !owner || !title) {
      return {
        text: "🐛 I need the owner, repository, and issue title to create an issue. For example: \"Create issue 'Add GitHub integration' in atomcompany/atom-desktop with description 'Implement comprehensive GitHub integration'\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubIssueSkillParams = {
        action: 'create',
        owner: owner,
        repo: repo,
        title: title,
        body: body,
        labels: Array.isArray(labels) ? labels : labels ? [labels] : undefined,
        assignees: Array.isArray(assignees) ? assignees : assignees ? [assignees] : undefined
      };

      const result = await githubIssueSkill.execute(params, context);
      
      if (result.success) {
        return {
          text: `✅ Issue #${result.issue_number} "${result.issue_title}" created successfully in ${owner}/${repo}${result.issue_url ? ` - ${result.issue_url}` : ''}`,
          skillsExecuted: ["github_issue_create"],
          context: result,
          suggestions: [
            "View the issue on GitHub",
            "Add comments to the issue",
            "Create related issues or pull requests"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to create issue: ${error}`,
        skillsExecuted: ["github_issue_create"]
      };
    }
  };

  const handleSearchIssues = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    const searchQuery = extractEntityValue(entities, 'search_query') || extractEntityValue(entities, 'query');
    const repo = extractEntityValue(entities, 'repository') || extractEntityValue(entities, 'repo');
    const owner = extractEntityValue(entities, 'owner');
    
    if (!searchQuery) {
      return {
        text: "🔍 What would you like me to search for in issues? For example: \"Search issues for 'GitHub integration' in atomcompany/atom-desktop\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubIssueSkillParams = {
        action: 'search',
        searchQuery: typeof searchQuery === 'string' ? searchQuery : searchQuery.toString(),
        owner: owner,
        repo: repo,
        limit: 10
      };

      const result = await githubIssueSkill.execute(params, context);
      
      if (result.success && result.issues) {
        const issueList = result.issues.map((issue: any) => 
          `• #${issue.number} ${issue.title} in ${issue.repository.full_name} (${issue.state})`
        ).join('\n');

        return {
          text: `🔍 Found ${result.count} issues matching "${searchQuery}":\n\n${issueList}`,
          skillsExecuted: ["github_issue_search"],
          context: result
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to search issues: ${error}`,
        skillsExecuted: ["github_issue_search"]
      };
    }
  };

  const handleListPullRequests = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!githubConnected) {
      return {
        text: "❌ GitHub is not connected. Please connect your GitHub account in Settings first.",
        skillsExecuted: ["github_check"]
      };
    }

    const repo = extractEntityValue(entities, 'repository') || extractEntityValue(entities, 'repo');
    const owner = extractEntityValue(entities, 'owner');
    const state = extractEntityValue(entities, 'state') || extractEntityValue(entities, 'status');
    const limit = extractEntityValue(entities, 'count') || extractEntityValue(entities, 'limit') || 10;

    if (!repo || !owner) {
      return {
        text: "🔄 I need the owner and repository name to list pull requests. For example: \"List open pull requests for atomcompany/atom-desktop\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubPullRequestSkillParams = {
        action: 'list',
        owner: owner,
        repo: repo,
        state: state === 'open' || state === 'closed' || state === 'merged' ? state : 'open',
        limit: typeof limit === 'string' ? parseInt(limit) : limit
      };

      const result = await githubPullRequestSkill.execute(params, context);
      
      if (result.success && result.pullRequests) {
        const prList = result.pullRequests.map((pr: any) => 
          `• #${pr.number} ${pr.title} (${pr.state})${pr.user ? ` by ${pr.user.login}` : ''}${pr.additions !== undefined && pr.deletions !== undefined ? ` - +${pr.additions}/-${pr.deletions}` : ''}${pr.mergeable !== undefined ? ` - ${pr.mergeable ? 'Mergeable' : 'Not mergeable'}` : ''}`
        ).join('\n');

        return {
          text: `🔄 Found ${result.count} pull requests in ${owner}/${repo}:\n\n${prList}`,
          skillsExecuted: ["github_pr_list"],
          context: result,
          suggestions: [
            "Create a new pull request",
            "Search for specific pull requests",
            "Review and merge pull requests"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to retrieve pull requests: ${error}`,
        skillsExecuted: ["github_pr_list"]
      };
    }
  };

  const handleCreatePullRequest = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!githubConnected) {
      return {
        text: "❌ GitHub is not connected. Please connect your GitHub account in Settings first.",
        skillsExecuted: ["github_check"]
      };
    }

    const repo = extractEntityValue(entities, 'repository') || extractEntityValue(entities, 'repo');
    const owner = extractEntityValue(entities, 'owner');
    const title = extractEntityValue(entities, 'title') || extractEntityValue(entities, 'pr_title');
    const head = extractEntityValue(entities, 'head') || extractEntityValue(entities, 'source_branch');
    const base = extractEntityValue(entities, 'base') || extractEntityValue(entities, 'target_branch');
    const body = extractEntityValue(entities, 'body') || extractEntityValue(entities, 'description') || extractEntityValue(entities, 'pr_body');

    if (!repo || !owner || !title || !head || !base) {
      return {
        text: "🔄 I need the owner, repository, title, source branch, and target branch to create a pull request. For example: \"Create pull request 'Add GitHub integration' from 'feature/github' to 'main' in atomcompany/atom-desktop\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubPullRequestSkillParams = {
        action: 'create',
        owner: owner,
        repo: repo,
        title: title,
        head: head,
        base: base,
        body: body
      };

      const result = await githubPullRequestSkill.execute(params, context);
      
      if (result.success) {
        return {
          text: `✅ Pull request #${result.pr_number} "${result.pr_title}" created successfully in ${owner}/${repo}${result.pr_url ? ` - ${result.pr_url}` : ''}`,
          skillsExecuted: ["github_pr_create"],
          context: result,
          suggestions: [
            "View the pull request on GitHub",
            "Request reviews from team members",
            "Monitor CI/CD status"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to create pull request: ${error}`,
        skillsExecuted: ["github_pr_create"]
      };
    }
  };

  const handleSearchPullRequests = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    const searchQuery = extractEntityValue(entities, 'search_query') || extractEntityValue(entities, 'query');
    const repo = extractEntityValue(entities, 'repository') || extractEntityValue(entities, 'repo');
    const owner = extractEntityValue(entities, 'owner');
    
    if (!searchQuery) {
      return {
        text: "🔍 What would you like me to search for in pull requests? For example: \"Search pull requests for 'GitHub integration' in atomcompany/atom-desktop\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: GitHubPullRequestSkillParams = {
        action: 'search',
        searchQuery: typeof searchQuery === 'string' ? searchQuery : searchQuery.toString(),
        owner: owner,
        repo: repo,
        limit: 10
      };

      const result = await githubPullRequestSkill.execute(params, context);
      
      if (result.success && result.pullRequests) {
        const prList = result.pullRequests.map((pr: any) => 
          `• #${pr.number} ${pr.title} in ${pr.repository.full_name} (${pr.state})${pr.user ? ` by ${pr.user.login}` : ''}`
        ).join('\n');

        return {
          text: `🔍 Found ${result.count} pull requests matching "${searchQuery}":\n\n${prList}`,
          skillsExecuted: ["github_pr_search"],
          context: result
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to search pull requests: ${error}`,
        skillsExecuted: ["github_pr_search"]
      };
    }
  };

  const getGitHubHelp = (): ChatResponse => {
    return {
      text: `📚 **GitHub Help** - Here's what I can help you with:

**Repository Management:**
• List repositories: "Show me my repositories" or "List repos for atomcompany"
• Create repository: "Create a new repository 'my-project' with description 'My awesome project'"
• Search repositories: "Search repositories for 'react components'"

**Issue Management:**
• List issues: "Show me open issues for atomcompany/atom-desktop"
• Create issue: "Create issue 'Add GitHub integration' in atomcompany/atom-desktop"
• Search issues: "Search issues for 'bug' in atomcompany/atom-desktop"

**Pull Request Management:**
• List pull requests: "Show me open PRs for atomcompany/atom-desktop"
• Create pull request: "Create PR 'Add feature' from feature-branch to main"
• Search pull requests: "Search PRs for 'integration' in atomcompany/atom-desktop"

**Other Commands:**
• Check status: "Is GitHub connected?"
• Get help: "GitHub help"

${githubConnected ? '✅ GitHub is connected and ready to use!' : '❌ GitHub is not connected. Go to Settings to connect your account.'}`,
      skillsExecuted: ["help"],
      suggestions: [
        "Try creating a repository",
        "Check your repository issues",
        "Create your first pull request"
      ]
    };
  };

  const getGitHubStatus = (): ChatResponse => {
    return {
      text: githubConnected 
        ? "✅ GitHub is connected and ready to help with repository, issue, and pull request management!"
        : "❌ GitHub is not connected. Please go to Settings to connect your GitHub account.",
      skillsExecuted: ["status_check"],
      suggestions: githubConnected ? [
        "List your repositories",
        "Check for open issues",
        "Create a new repository"
      ] : [
        "Go to Settings to connect GitHub",
        "Check your OAuth configuration"
      ]
    };
  };

  const handleGeneralMessage = async (message: string, nlpResult: any, context: SkillExecutionContext): Promise<ChatResponse> => {
    // Check if it's a GitHub-related general message
    const messageLower = message.toLowerCase();
    
    if (messageLower.includes('github') || messageLower.includes('repo') || messageLower.includes('issue') || messageLower.includes('pull request') || messageLower.includes('pr')) {
      return {
        text: `📚 I can help you with GitHub repository, issue, and pull request management! 

Try commands like:
• "List my repositories"
• "Create a new repository"
• "Show me open issues"
• "Create a pull request"

Type "GitHub help" for more details.`,
        skillsExecuted: ["github_general"]
      };
    }

    // Fallback to general agent
    try {
      const response: string = await invoke("send_message_to_agent", { message });
      return {
        text: response,
        skillsExecuted: ["general_agent"]
      };
    } catch (error) {
      return {
        text: "I'm here to help with GitHub repositories, issues, and pull requests. What would you like to do?",
        skillsExecuted: ["fallback"]
      };
    }
  };

  // Helper functions
  const extractEntityValue = (entities: Entity[], entityType: string): any => {
    const entity = entities.find(e => e.type === entityType);
    return entity ? entity.value : undefined;
  };

  return (
    <div className="chat-container enhanced">
      {/* Connection Status */}
      <div className={`connection-status ${githubConnected ? 'connected' : 'disconnected'}`}>
        <span className="status-indicator"></span>
        <span className="status-text">
          GitHub {githubConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Messages */}
      <div className="messages enhanced">
        {messages.map((message, index) => (
          <div key={message.id} className={`message ${message.sender} enhanced`}>
            <div className="message-content">
              {message.text}
            </div>
            <div className="message-meta">
              <span className="timestamp">
                {new Date(message.timestamp).toLocaleTimeString()}
              </span>
              {message.skillsUsed && (
                <span className="skills-used">
                  🛠️ {message.skillsUsed.join(', ')}
                </span>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message agent enhanced">
            <div className="message-content">
              <span className="typing-indicator">
                🤔 Processing your request...
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="input-container enhanced">
        <div className="quick-actions">
          <button 
            onClick={() => setInput("Show me my repositories")}
            className="quick-action-btn"
            disabled={!githubConnected}
          >
            📚 My Repos
          </button>
          <button 
            onClick={() => setInput("Show me open issues for atomcompany/atom-desktop")}
            className="quick-action-btn"
            disabled={!githubConnected}
          >
            🐛 Open Issues
          </button>
          <button 
            onClick={() => setInput("Show me pull requests for atomcompany/atom-desktop")}
            className="quick-action-btn"
            disabled={!githubConnected}
          >
            🔄 Pull Requests
          </button>
          <button 
            onClick={() => setInput("GitHub help")}
            className="quick-action-btn"
          >
            ❓ Help
          </button>
        </div>
        <div className="input-row">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSend()}
            placeholder={
              githubConnected 
                ? "Ask me to manage repositories, issues, or pull requests..."
                : "Connect GitHub in Settings to use repository management..."
            }
            disabled={isLoading}
            className={`message-input ${!githubConnected ? 'disabled' : ''}`}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim() || !githubConnected}
            className="send-button"
          >
            {isLoading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default GitHubEnhancedChat;
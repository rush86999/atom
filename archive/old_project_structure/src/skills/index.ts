/**
 * Skills Index - Central Registry for ATOM Agent Skills
 *
 * Provides unified skill registration and management for the ATOM agentic OS.
 * This module serves as the central hub for all agent capabilities.
 */

import { registerSkill, SkillDefinition } from "../services/agentSkillRegistry";

// Core skill categories and types
export interface SkillCategory {
  id: string;
  name: string;
  description: string;
  icon: string;
  skills: SkillDefinition[];
}

// Core skill definitions
const coreSkills: SkillDefinition[] = [
  {
    id: "shell-command",
    name: "Execute Shell Command",
    description: "Execute shell commands and scripts",
    category: "system",
    icon: "💻",
    parameters: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description: "Shell command to execute",
          minLength: 1,
        },
        cwd: {
          type: "string",
          description: "Working directory (optional)",
          default: process.cwd(),
        },
        timeout: {
          type: "number",
          description: "Timeout in milliseconds (optional)",
          default: 30000,
        },
      },
      required: ["command"],
    },
    handler: async (userId: string, parameters: any) => {
      // Placeholder - would integrate with shellSkills
      return {
        ok: true,
        data: { message: "Shell command execution placeholder" },
      };
    },
    version: "1.0.0",
    enabled: true,
    tags: ["system", "command", "execution"],
  },
  {
    id: "github-create-repo",
    name: "Create GitHub Repository",
    description: "Create a new GitHub repository",
    category: "development",
    icon: "🐙",
    parameters: {
      type: "object",
      properties: {
        name: {
          type: "string",
          description: "Repository name",
          minLength: 1,
          maxLength: 100,
        },
        description: {
          type: "string",
          description: "Repository description",
          maxLength: 255,
        },
        private: {
          type: "boolean",
          description: "Make repository private",
          default: false,
        },
      },
      required: ["name"],
    },
    handler: async (userId: string, parameters: any) => {
      // Placeholder - would integrate with githubSkills
      return {
        ok: true,
        data: {
          message: "GitHub repository creation placeholder",
          repoName: parameters.name,
        },
      };
    },
    version: "1.0.0",
    enabled: true,
    tags: ["github", "repository", "development"],
  },
  {
    id: "jira-create-issue",
    name: "Create Jira Issue",
    description: "Create a new Jira issue",
    category: "project-management",
    icon: "🐛",
    parameters: {
      type: "object",
      properties: {
        projectKey: {
          type: "string",
          description: "Jira project key",
          minLength: 2,
          maxLength: 10,
        },
        summary: {
          type: "string",
          description: "Issue summary",
          minLength: 1,
          maxLength: 255,
        },
        description: {
          type: "string",
          description: "Issue description",
          maxLength: 32768,
        },
        issueType: {
          type: "string",
          enum: ["Story", "Task", "Bug", "Epic"],
          description: "Issue type",
          default: "Task",
        },
      },
      required: ["projectKey", "summary"],
    },
    handler: async (userId: string, parameters: any) => {
      // Placeholder - would integrate with jiraSkills
      return {
        ok: true,
        data: {
          message: "Jira issue creation placeholder",
          issueKey: `${parameters.projectKey}-123`,
        },
      };
    },
    version: "1.0.0",
    enabled: true,
    tags: ["jira", "issue", "project-management"],
  },
];

// Skill categories for organization
export const skillCategories: SkillCategory[] = [
  {
    id: "development",
    name: "Development",
    description: "Code and development related skills",
    icon: "💻",
    skills: coreSkills.filter((skill) => skill.category === "development"),
  },
  {
    id: "project-management",
    name: "Project Management",
    description: "Project and task management skills",
    icon: "📊",
    skills: coreSkills.filter(
      (skill) => skill.category === "project-management",
    ),
  },
  {
    id: "system",
    name: "System",
    description: "System and infrastructure skills",
    icon: "⚙️",
    skills: coreSkills.filter((skill) => skill.category === "system"),
  },
  {
    id: "communication",
    name: "Communication",
    description: "Messaging and notification skills",
    icon: "💬",
    skills: coreSkills.filter((skill) => skill.category === "communication"),
  },
];

/**
 * Register all core skills with the agent skill registry
 */
export async function registerAllSkills(): Promise<{
  success: boolean;
  registered: number;
  failed: number;
  details: string[];
}> {
  const results = {
    success: true,
    registered: 0,
    failed: 0,
    details: [] as string[],
  };

  console.log("🔧 Registering ATOM Agent Skills...");

  for (const skill of coreSkills) {
    try {
      const registered = await registerSkill(skill);
      if (registered) {
        results.registered++;
        results.details.push(`✅ ${skill.name}`);
      } else {
        results.failed++;
        results.details.push(`❌ ${skill.name} (registration failed)`);
        results.success = false;
      }
    } catch (error) {
      results.failed++;
      results.details.push(
        `❌ ${skill.name} (error: ${error instanceof Error ? error.message : "unknown"})`,
      );
      results.success = false;
    }
  }

  console.log(
    `📊 Skill registration complete: ${results.registered} successful, ${results.failed} failed`,
  );

  if (results.success) {
    console.log("✅ All skills registered successfully");
  } else {
    console.warn("⚠️ Some skills failed to register");
  }

  return results;
}

/**
 * Get skills by category
 */
export function getSkillsByCategory(categoryId: string): SkillDefinition[] {
  const category = skillCategories.find((cat) => cat.id === categoryId);
  return category ? category.skills : [];
}

/**
 * Search skills by name, description, or tags
 */
export function searchSkills(query: string): SkillDefinition[] {
  const lowerQuery = query.toLowerCase();
  return coreSkills.filter(
    (skill) =>
      skill.name.toLowerCase().includes(lowerQuery) ||
      skill.description.toLowerCase().includes(lowerQuery) ||
      skill.tags?.some((tag) => tag.toLowerCase().includes(lowerQuery)) ||
      false,
  );
}

/**
 * Get skill by ID
 */
export function getSkill(skillId: string): SkillDefinition | undefined {
  return coreSkills.find((skill) => skill.id === skillId);
}

/**
 * Get all available skills
 */
export function getAllSkills(): SkillDefinition[] {
  return [...coreSkills];
}

/**
 * Get skill categories with counts
 */
export function getSkillCategories(): Array<SkillCategory & { count: number }> {
  return skillCategories.map((category) => ({
    ...category,
    count: category.skills.length,
  }));
}

// Auto-register skills on import (optional - can be disabled for testing)
if (process.env.NODE_ENV !== "test") {
  registerAllSkills().catch(console.error);
}

// Default exports
export default {
  registerAllSkills,
  getAllSkills,
  getSkill,
  getSkillsByCategory,
  searchSkills,
  getSkillCategories,
  skillCategories,
  coreSkills,
};

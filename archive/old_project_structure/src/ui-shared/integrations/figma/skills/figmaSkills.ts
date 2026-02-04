import { Skill, SkillContext, SkillResult } from "../../../types/skillTypes";

/**
 * Figma File Creation Skill
 * Creates new Figma files with specified properties
 */
export class FigmaCreateFileSkill implements Skill {
  id = "figma_create_file";
  name = "Create Figma File";
  description = "Create a new Figma file with name and description";
  category = "design";
  examples = [
    "Create a new Figma file called Mobile App Design",
    "Create Figma file Website Wireframes with description",
    "Make new design file Dashboard UI",
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;

      // Extract file name from intent
      const fileName =
        this.extractFileName(intent) ||
        entities.find((e: any) => e.type === "file_name")?.value ||
        "New Design File";

      // Extract description
      const description =
        this.extractDescription(intent) ||
        entities.find((e: any) => e.type === "description")?.value ||
        `Created by ATOM platform on ${new Date().toLocaleDateString()}`;

      // Call Figma API
      const response = await fetch("/api/integrations/figma/files", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: context.user?.id || "default",
          operation: "create",
          data: {
            name: fileName,
            description: description,
            editor_type: "figma",
          },
        }),
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Successfully created Figma file: ${fileName}`,
          data: {
            file: result.data.file,
            url: result.data.url,
            file_key: result.data.file?.key,
            name: fileName,
            description: description,
          },
          actions: [
            {
              type: "open_url",
              label: `Open ${fileName} in Figma`,
              url: result.data.url,
            },
          ],
        };
      } else {
        return {
          success: false,
          message: `Failed to create Figma file: ${result.error?.message || "Unknown error"}`,
          error: result.error,
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Figma file: ${error}`,
        error: error as any,
      };
    }
  }

  private extractFileName(intent: string): string | null {
    // Pattern matching for file creation
    const patterns = [
      /create(?: a)? new figma file(?: called)? (.+)/i,
      /make(?: a)? new design file(?: called)? (.+)/i,
      /new figma file (.+)/i,
      /figma file (.+)/i,
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, "");
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    // Pattern matching for description
    const patterns = [
      /with description (.+)/i,
      /described as (.+)/i,
      /with details (.+)/i,
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, "");
      }
    }

    return null;
  }
}

/**
 * Figma File Listing Skill
 * Lists Figma files with filtering options
 */
export class FigmaListFilesSkill implements Skill {
  id = "figma_list_files";
  name = "List Figma Files";
  description = "List all Figma files or files from specific team";
  category = "design";
  examples = [
    "Show me all my Figma files",
    "List Figma files from Design Team",
    "Show my recent Figma designs",
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;

      // Extract team name from intent
      const teamName =
        this.extractTeamName(intent) ||
        entities.find((e: any) => e.type === "team")?.value;

      // Call Figma API
      const response = await fetch("/api/integrations/figma/files", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: context.user?.id || "default",
          operation: "list",
          team_id: teamName,
          limit: 50,
        }),
      });

      const result = await response.json();

      if (result.ok) {
        const files = result.data.files || [];
        const fileCount = files.length;

        let message = `Found ${fileCount} Figma file${fileCount !== 1 ? "s" : ""}`;
        if (teamName) {
          message += ` from ${teamName}`;
        }

        return {
          success: true,
          message: message,
          data: {
            files: files,
            total_count: result.data.total_count,
            team: teamName,
          },
          actions: files.map((file: any) => ({
            type: "open_url",
            label: `Open ${file.name}`,
            url: file.url,
          })),
        };
      } else {
        return {
          success: false,
          message: `Failed to list Figma files: ${result.error?.message || "Unknown error"}`,
          error: result.error,
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error listing Figma files: ${error}`,
        error: error as any,
      };
    }
  }

  private extractTeamName(intent: string): string | null {
    const patterns = [/from (.+) team/i, /(.+) team files/i, /team (.+)/i];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }

    return null;
  }
}

/**
 * Figma Component Search Skill
 * Searches for components across Figma files
 */
export class FigmaSearchComponentsSkill implements Skill {
  id = "figma_search_components";
  name = "Search Figma Components";
  description = "Search for specific components in Figma files";
  category = "design";
  examples = [
    "Search for button components in Figma",
    "Find input field components",
    "Search Figma for navigation components",
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;

      // Extract component type from intent
      const componentType =
        this.extractComponentType(intent) ||
        entities.find((e: any) => e.type === "component_type")?.value ||
        this.extractComponentType(intent); // Fallback

      if (!componentType) {
        return {
          success: false,
          message:
            "Please specify what type of component you want to search for",
          error: "Missing component type",
        };
      }

      // Call Figma search API
      const response = await fetch("/api/integrations/figma/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: context.user?.id || "default",
          query: componentType,
          type: "components",
          limit: 20,
        }),
      });

      const result = await response.json();

      if (result.ok) {
        const components = result.data.results || [];
        const componentCount = components.length;

        return {
          success: true,
          message: `Found ${componentCount} ${componentType} component${componentCount !== 1 ? "s" : ""}`,
          data: {
            components: components,
            total_count: result.data.total_count,
            query: componentType,
          },
          actions: components.map((component: any) => ({
            type: "open_url",
            label: `Open ${component.title}`,
            url: component.url,
          })),
        };
      } else {
        return {
          success: false,
          message: `Failed to search Figma components: ${result.error?.message || "Unknown error"}`,
          error: result.error,
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Figma components: ${error}`,
        error: error as any,
      };
    }
  }

  private extractComponentType(intent: string): string | null {
    const patterns = [
      /search for (.+) components?/i,
      /find (.+) components?/i,
      /(.+) components?/i,
      /search for (.+) in figma/i,
      /find (.+) in figma/i,
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().toLowerCase();
      }
    }

    return null;
  }
}

/**
 * Figma Feedback Skill
 * Adds comments/feedback to Figma files
 */
export class FigmaAddFeedbackSkill implements Skill {
  id = "figma_add_feedback";
  name = "Add Figma Feedback";
  description = "Add comments or feedback to Figma designs";
  category = "design";
  examples = [
    "Add comment about the button color",
    "Leave feedback on the navigation design",
    "Comment on the dashboard layout",
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;

      // Extract file name or key
      const fileName =
        this.extractFileName(intent) ||
        entities.find((e: any) => e.type === "file_name")?.value;

      // Extract comment message
      const comment =
        this.extractComment(intent) ||
        entities.find((e: any) => e.type === "comment")?.value;

      if (!fileName && !comment) {
        return {
          success: false,
          message:
            "Please specify which file and what feedback you want to add",
          error: "Missing file or comment information",
        };
      }

      // For demo purposes, we'll create a mock file key
      const fileKey = fileName
        ? `FILE_KEY_${fileName.replace(/\s+/g, "_").toUpperCase()}`
        : "MOCK_FILE_KEY";

      // Call Figma comment API
      const response = await fetch(
        `/api/integrations/figma/files/${fileKey}/comments`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: context.user?.id || "default",
            message: comment || "Added feedback via ATOM platform",
            client_id: "atom_platform",
          }),
        },
      );

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Successfully added feedback to Figma file`,
          data: {
            comment: result.data,
            file_key: fileKey,
            file_name: fileName,
            message: comment,
          },
        };
      } else {
        return {
          success: false,
          message: `Failed to add Figma feedback: ${result.error?.message || "Unknown error"}`,
          error: result.error,
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error adding Figma feedback: ${error}`,
        error: error as any,
      };
    }
  }

  private extractFileName(intent: string): string | null {
    const patterns = [
      /on (.+) file/i,
      /on (.+) design/i,
      /to (.+)/i,
      /(.+) file/i,
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }

    return null;
  }

  private extractComment(intent: string): string | null {
    const patterns = [
      /comment about (.+)/i,
      /feedback on (.+)/i,
      /about the (.+)/i,
      /comment (.+)/i,
      /feedback (.+)/i,
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }

    return null;
  }
}

// Export all Figma skills
export const FIGMA_SKILLS = [
  new FigmaCreateFileSkill(),
  new FigmaListFilesSkill(),
  new FigmaSearchComponentsSkill(),
  new FigmaAddFeedbackSkill(),
];

// Export skills registry
export const FIGMA_SKILLS_REGISTRY = {
  figma_create_file: FigmaCreateFileSkill,
  figma_list_files: FigmaListFilesSkill,
  figma_search_components: FigmaSearchComponentsSkill,
  figma_add_feedback: FigmaAddFeedbackSkill,
};

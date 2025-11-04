/**
 * Notion Skills for ATOM Workflow Automation
 * Complete integration with Notion API for pages, databases, and workspace management
 */

import { Skill, SkillContext, SkillResult } from '../../../types';

// Notion API Types
interface NotionPage {
  id: string;
  title: string;
  url: string;
  icon?: string;
  last_edited_time: string;
  parent?: {
    type: 'database_id' | 'page_id' | 'workspace';
    database_id?: string;
    page_id?: string;
  };
}

interface NotionDatabase {
  id: string;
  title: string;
  description?: string;
  url: string;
  icon?: string;
  last_edited_time: string;
}

interface NotionBlock {
  id: string;
  type: string;
  content: any;
  children?: NotionBlock[];
}

interface NotionSearchResult {
  object: 'page' | 'database';
  id: string;
  title: string;
  url: string;
  icon?: string;
  last_edited_time: string;
}

// Notion Skills Implementation
export const notionSkills: Skill[] = [
  {
    id: 'notion_search_pages',
    name: 'Search Notion Pages',
    description: 'Search across all pages in connected Notion workspaces',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query to find relevant pages'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results to return',
          default: 10
        }
      },
      required: ['query']
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { query, limit = 10 } = params;

        const response = await fetch('/api/integrations/notion/search', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            query,
            limit,
            filter: { property: 'object', value: 'page' }
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to search Notion pages: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            results: data.results || [],
            total: data.total || 0,
            query
          },
          message: `Found ${data.total || 0} pages matching "${query}"`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_search_databases',
    name: 'Search Notion Databases',
    description: 'Search across all databases in connected Notion workspaces',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query to find relevant databases'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results to return',
          default: 10
        }
      },
      required: ['query']
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { query, limit = 10 } = params;

        const response = await fetch('/api/integrations/notion/search', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            query,
            limit,
            filter: { property: 'object', value: 'database' }
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to search Notion databases: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            results: data.results || [],
            total: data.total || 0,
            query
          },
          message: `Found ${data.total || 0} databases matching "${query}"`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_create_page',
    name: 'Create Notion Page',
    description: 'Create a new page in Notion',
    parameters: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'Title of the new page'
        },
        content: {
          type: 'string',
          description: 'Content for the page (markdown supported)'
        },
        parent_page_id: {
          type: 'string',
          description: 'ID of the parent page (optional)'
        },
        parent_database_id: {
          type: 'string',
          description: 'ID of the parent database (optional)'
        }
      },
      required: ['title']
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { title, content, parent_page_id, parent_database_id } = params;

        const response = await fetch('/api/integrations/notion/pages', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            title,
            content,
            parent_page_id,
            parent_database_id
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to create Notion page: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            page: data.page,
            url: data.url
          },
          message: `Created new Notion page: "${title}"`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_update_page',
    name: 'Update Notion Page',
    description: 'Update an existing page in Notion',
    parameters: {
      type: 'object',
      properties: {
        page_id: {
          type: 'string',
          description: 'ID of the page to update'
        },
        title: {
          type: 'string',
          description: 'New title for the page (optional)'
        },
        content: {
          type: 'string',
          description: 'New content for the page (optional)'
        },
        properties: {
          type: 'object',
          description: 'Additional properties to update (database pages only)'
        }
      },
      required: ['page_id']
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { page_id, title, content, properties } = params;

        const response = await fetch(`/api/integrations/notion/pages/${page_id}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            title,
            content,
            properties
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to update Notion page: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            page: data.page,
            url: data.url
          },
          message: `Updated Notion page: "${title || 'Untitled'}"`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_get_page_content',
    name: 'Get Notion Page Content',
    description: 'Retrieve the content of a Notion page',
    parameters: {
      type: 'object',
      properties: {
        page_id: {
          type: 'string',
          description: 'ID of the page to retrieve'
        },
        include_children: {
          type: 'boolean',
          description: 'Whether to include child blocks',
          default: true
        }
      },
      required: ['page_id']
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { page_id, include_children = true } = params;

        const response = await fetch(`/api/integrations/notion/pages/${page_id}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            include_children
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to get Notion page: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            page: data.page,
            content: data.content,
            blocks: data.blocks || []
          },
          message: `Retrieved content from Notion page`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_list_databases',
    name: 'List Notion Databases',
    description: 'Get all databases from connected Notion workspaces',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of databases to return',
          default: 50
        }
      }
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { limit = 50 } = params;

        const response = await fetch('/api/integrations/notion/databases', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            limit
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to list Notion databases: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            databases: data.databases || [],
            total: data.total || 0
          },
          message: `Found ${data.total || 0} databases`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_query_database',
    name: 'Query Notion Database',
    description: 'Query and filter records from a Notion database',
    parameters: {
      type: 'object',
      properties: {
        database_id: {
          type: 'string',
          description: 'ID of the database to query'
        },
        filter: {
          type: 'object',
          description: 'Filter conditions for the query'
        },
        sorts: {
          type: 'array',
          description: 'Sorting criteria',
          items: {
            type: 'object'
          }
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results',
          default: 100
        }
      },
      required: ['database_id']
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { database_id, filter, sorts, limit = 100 } = params;

        const response = await fetch(`/api/integrations/notion/databases/${database_id}/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            filter,
            sorts,
            limit
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to query Notion database: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            results: data.results || [],
            total: data.total || 0,
            database_id
          },
          message: `Found ${data.total || 0} records in database`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_create_database_record',
    name: 'Create Database Record',
    description: 'Create a new record in a Notion database',
    parameters: {
      type: 'object',
      properties: {
        database_id: {
          type: 'string',
          description: 'ID of the database'
        },
        properties: {
          type: 'object',
          description: 'Properties for the new record'
        },
        content: {
          type: 'string',
          description: 'Additional content for the page (optional)'
        }
      },
      required: ['database_id', 'properties']
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { database_id, properties, content } = params;

        const response = await fetch(`/api/integrations/notion/databases/${database_id}/records`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            properties,
            content
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to create database record: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            record: data.record,
            url: data.url
          },
          message: `Created new record in database`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_get_workspaces',
    name: 'Get Notion Workspaces',
    description: 'Get all connected Notion workspaces',
    parameters: {
      type: 'object',
      properties: {
        include_stats: {
          type: 'boolean',
          description: 'Whether to include workspace statistics',
          default: true
        }
      }
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { include_stats = true } = params;

        const response = await fetch('/api/integrations/notion/workspaces', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            include_stats
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to get Notion workspaces: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            workspaces: data.workspaces || [],
            total: data.total || 0
          },
          message: `Found ${data.total || 0} workspaces`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  },

  {
    id: 'notion_sync_data',
    name: 'Sync Notion Data',
    description: 'Trigger a full sync of Notion pages and databases',
    parameters: {
      type: 'object',
      properties: {
        force_refresh: {
          type: 'boolean',
          description: 'Whether to force a full refresh',
          default: false
        }
      }
    },
    async execute(params: any, context: SkillContext): Promise<SkillResult> {
      try {
        const { force_refresh = false } = params;

        const response = await fetch('/api/integrations/notion/sync', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: context.userId,
            force_refresh
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to sync Notion data: ${response.statusText}`);
        }

        const data = await response.json();

        return {
          success: true,
          data: {
            pages_synced: data.pages_synced || 0,
            databases_synced: data.databases_synced || 0,
            duration: data.duration || 0
          },
          message: `Synced ${data.pages_synced || 0} pages and ${data.databases_synced || 0} databases`
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred',
          data: null
        };
      }
    }
  }
];

export default notionSkills;

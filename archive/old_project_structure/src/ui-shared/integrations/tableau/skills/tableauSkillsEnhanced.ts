"""
Tableau Enhanced Skills
Complete Tableau data visualization and business intelligence system
"""

import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * Tableau Enhanced Skills
 * Complete Tableau data visualization and business intelligence system
 */

// Workbook Management Skills
export class TableauCreateWorkbookSkill implements Skill {
  id = 'tableau_create_workbook';
  name = 'Create Tableau Workbook';
  description = 'Create a new workbook in Tableau';
  category = 'analytics';
  examples = [
    'Create Tableau workbook for sales data',
    'Start new dashboard for marketing analytics',
    'Create Tableau workbook called Customer Insights'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract workbook details
      const workbookName = this.extractWorkbookName(intent) ||
                         entities.find((e: any) => e.type === 'workbook_name')?.value ||
                         'new-workbook';
      
      const description = this.extractDescription(intent) ||
                        entities.find((e: any) => e.type === 'description')?.value ||
                        intent;
      
      const projectName = this.extractProjectName(intent) ||
                         entities.find((e: any) => e.type === 'project_name')?.value ||
                         'Default Project';
      
      const showTabs = this.extractShowTabs(intent) ||
                       entities.find((e: any) => e.type === 'show_tabs')?.value ||
                       true;

      if (!workbookName) {
        return {
          success: false,
          message: 'Workbook name is required',
          error: 'Missing workbook name'
        };
      }

      // Call Tableau API
      const response = await fetch('/api/integrations/tableau/workbooks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            name: workbookName,
            description: description,
            project_name: projectName,
            show_tabs: showTabs,
            publish: false // Create draft first
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Tableau workbook "${workbookName}" created successfully`,
          data: {
            workbook: result.data.workbook,
            url: result.data.url,
            embed_code: result.data.embed_code,
            name: workbookName,
            project_name: projectName
          },
          actions: [
            {
              type: 'open_url',
              label: 'View in Tableau',
              url: result.data.url
            },
            {
              type: 'copy_to_clipboard',
              label: 'Copy Embed Code',
              text: result.data.embed_code
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create Tableau workbook: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating Tableau workbook: ${error}`,
        error: error as any
      };
    }
  }

  private extractWorkbookName(intent: string): string | null {
    const patterns = [
      /create (?:tableau )?workbook (?:called|named) (.+?)(?: for|with|:|$)/i,
      /create (?:tableau )?dashboard (?:called|named) (.+?)(?: for|with|:|$)/i,
      /workbook (?:called|named) (.+?)(?: for|with|:|$)/i,
      /dashboard (?:called|named) (.+?)(?: for|with|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:for|with) (.+?)(?: project|tabs|:|$)/i,
      /description (.+?)(?: project|tabs|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return intent;
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /in (?:project )?(.+?)(?: for|with|:|$)/i,
      /project (.+?)(?: for|with|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractShowTabs(intent: string): boolean | null {
    if (intent.toLowerCase().includes('no tabs') || intent.toLowerCase().includes('single tab')) {
      return false;
    } else if (intent.toLowerCase().includes('tabs') || intent.toLowerCase().includes('multiple tabs')) {
      return true;
    }
    return null;
  }
}

export class TableauSearchWorkbooksSkill implements Skill {
  id = 'tableau_search_workbooks';
  name = 'Search Tableau Workbooks';
  description = 'Search workbooks in Tableau';
  category = 'analytics';
  examples = [
    'Search Tableau for sales dashboards',
    'Find marketing analytics workbooks on Tableau',
    'Look for customer insights workbooks'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                 entities.find((e: any) => e.type === 'query')?.value ||
                 intent;
      
      const projectName = this.extractProjectName(intent) ||
                         entities.find((e: any) => e.type === 'project_name')?.value;
      
      const ownerName = this.extractOwnerName(intent) ||
                       entities.find((e: any) => e.type === 'owner_name')?.value;
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Tableau API
      const response = await fetch('/api/integrations/tableau/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: query,
          type: 'workbooks',
          project_name: projectName,
          owner_name: ownerName,
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const workbooks = result.data.results || [];
        const workbookCount = workbooks.length;

        return {
          success: true,
          message: `Found ${workbookCount} Tableau workbook${workbookCount !== 1 ? 's' : ''} matching "${query}"`,
          data: {
            workbooks: workbooks,
            total_count: result.data.total_count,
            query: query,
            project_name: projectName,
            owner_name: ownerName
          },
          actions: workbooks.map((workbook: any) => ({
            type: 'open_url',
            label: `View ${workbook.name}`,
            url: workbook.webpage_url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search Tableau workbooks: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Tableau workbooks: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:tableau for )?(.+?)(?: workbooks|dashboards|:|$)/i,
      /find (.+?) (?:workbooks|dashboards|on tableau|:|$)/i,
      /look for (.+?) (?:workbooks|dashboards|on tableau|:|$)/i,
      /(.+?) (?:workbooks|dashboards|on tableau|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /in (?:project )?(.+?)(?: workbooks|dashboards|:|$)/i,
      /project (.+?)(?: workbooks|dashboards|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractOwnerName(intent: string): string | null {
    const patterns = [
      /by (.+?)(?: in|for|:|$)/i,
      /owner (.+?)(?: in|for|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

// Datasource Management Skills
export class TableauRefreshDatasourceSkill implements Skill {
  id = 'tableau_refresh_datasource';
  name = 'Refresh Tableau Datasource';
  description = 'Refresh a datasource in Tableau';
  category = 'analytics';
  examples = [
    'Refresh sales datasource in Tableau',
    'Update marketing analytics data',
    'Refresh customer insights datasource'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract datasource details
      const datasourceName = this.extractDatasourceName(intent) ||
                           entities.find((e: any) => e.type === 'datasource_name')?.value;
      
      const projectName = this.extractProjectName(intent) ||
                         entities.find((e: any) => e.type === 'project_name')?.value;

      if (!datasourceName) {
        return {
          success: false,
          message: 'Datasource name is required',
          error: 'Missing datasource name'
        };
      }

      // First search for the datasource to get its ID
      const searchResponse = await fetch('/api/integrations/tableau/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: datasourceName,
          type: 'datasources',
          project_name: projectName,
          limit: 10
        })
      });

      const searchResult = await searchResponse.json();
      
      if (!searchResult.ok || searchResult.data.results.length === 0) {
        return {
          success: false,
          message: `Datasource "${datasourceName}" not found`,
          error: 'Datasource not found'
        };
      }

      // Use the first matching datasource
      const datasource = searchResult.data.results[0];
      
      // Now refresh the datasource
      const refreshResponse = await fetch('/api/integrations/tableau/datasources', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'refresh',
          datasource_id: datasource.id
        })
      });

      const result = await refreshResponse.json();

      if (result.ok) {
        return {
          success: true,
          message: `Tableau datasource "${datasource.name}" refresh initiated successfully`,
          data: {
            datasource: datasource,
            job_id: result.data.job_id,
            status: result.data.status,
            name: datasource.name
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Datasource',
              url: datasource.webpage_url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to refresh Tableau datasource: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error refreshing Tableau datasource: ${error}`,
        error: error as any
      };
    }
  }

  private extractDatasourceName(intent: string): string | null {
    const patterns = [
      /refresh (?:tableau )?(?:datasource|data source) (.+?)(?: in|for|:|$)/i,
      /refresh (.+?) (?:datasource|data source|in tableau|:|$)/i,
      /update (?:datasource|data source) (.+?)(?: in|for|:|$)/i,
      /(.+?) (?:datasource|data source|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /in (?:project )?(.+?)(?: refresh|update|:|$)/i,
      /project (.+?)(?: refresh|update|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

// View Management Skills
export class TableauEmbedViewSkill implements Skill {
  id = 'tableau_embed_view';
  name = 'Embed Tableau View';
  description = 'Get embed code for a Tableau view';
  category = 'analytics';
  examples = [
    'Embed sales dashboard from Tableau',
    'Get embed code for marketing analytics view',
    'Create embed code for customer insights dashboard'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract view details
      const viewName = this.extractViewName(intent) ||
                     entities.find((e: any) => e.type === 'view_name')?.value;
      
      const workbookName = this.extractWorkbookName(intent) ||
                         entities.find((e: any) => e.type === 'workbook_name')?.value;
      
      const projectName = this.extractProjectName(intent) ||
                         entities.find((e: any) => e.type === 'project_name')?.value;
      
      const width = this.extractWidth(intent) ||
                  entities.find((e: any) => e.type === 'width')?.value ||
                  '1200';
      
      const height = this.extractHeight(intent) ||
                   entities.find((e: any) => e.type === 'height')?.value ||
                   '800';

      if (!viewName && !workbookName) {
        return {
          success: false,
          message: 'View name or workbook name is required',
          error: 'Missing view or workbook name'
        };
      }

      // Search for the view
      const searchResponse = await fetch('/api/integrations/tableau/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: viewName || workbookName,
          type: 'views',
          project_name: projectName,
          limit: 10
        })
      });

      const searchResult = await searchResponse.json();
      
      if (!searchResult.ok || searchResult.data.results.length === 0) {
        return {
          success: false,
          message: `View "${viewName || workbookName}" not found`,
          error: 'View not found'
        };
      }

      // Use the first matching view
      const view = searchResult.data.results[0];
      
      // Generate embed code for the view
      const embedCode = `<script type="text/javascript" src="https://10ax.online.tableau.com/javascripts/api/tableau-2.min.js"></script>
<div class="tableauPlaceholder" style="width:${width}px;height:${height}px;">
  <object class="tableauViz" width="${width}" height="${height}" style="display:none;">
    <param name="host_url" value="https%3A%2F%2F10ax.online.tableau.com%2F" />
    <param name="embed_code_version" value="3" />
    <param name="site_root" value="" />
    <param name="name" value="${view.content_url}" />
    <param name="tabs" value="yes" />
    <param name="toolbar" value="yes" />
    <param name="showShareOptions" value="true" />
  </object>
</div>`;
      
      return {
        success: true,
        message: `Embed code for "${view.name}" generated successfully`,
        data: {
          view: view,
          embed_code: embedCode,
          url: view.view_url,
          name: view.name,
          width: width,
          height: height
        },
        actions: [
          {
            type: 'copy_to_clipboard',
            label: 'Copy Embed Code',
            text: embedCode
          },
          {
            type: 'open_url',
            label: 'View in Tableau',
            url: view.view_url
          }
        ]
      };
    } catch (error) {
      return {
        success: false,
        message: `Error generating embed code: ${error}`,
        error: error as any
      };
    }
  }

  private extractViewName(intent: string): string | null {
    const patterns = [
      /embed (?:tableau )?view (.+?)(?: from|in|for|:|$)/i,
      /embed (.+?) (?:view|dashboard|from|in|:|$)/i,
      /get embed code (?:for )?(.+?)(?: from|in|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractWorkbookName(intent: string): string | null {
    const patterns = [
      /embed (?:tableau )?workbook (.+?)(?: from|in|for|:|$)/i,
      /embed (.+?) (?:workbook|dashboard|from|in|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /in (?:project )?(.+?)(?: embed|from|:|$)/i,
      /project (.+?)(?: embed|from|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractWidth(intent: string): string | null {
    const patterns = [
      /width (\d+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }

  private extractHeight(intent: string): string | null {
    const patterns = [
      /height (\d+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1];
      }
    }

    return null;
  }
}

// Tableau Search Skill
export class TableauSearchSkill implements Skill {
  id = 'tableau_search';
  name = 'Search Tableau';
  description = 'Search across Tableau workbooks, datasources, and views';
  category = 'analytics';
  examples = [
    'Search Tableau for sales analytics',
    'Find marketing dashboards on Tableau',
    'Look for customer insights across all Tableau content'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search details
      const query = this.extractQuery(intent) ||
                 entities.find((e: any) => e.type === 'query')?.value ||
                 intent;
      
      const searchType = this.extractSearchType(intent) ||
                       entities.find((e: any) => e.type === 'search_type')?.value ||
                       'all';
      
      const projectName = this.extractProjectName(intent) ||
                         entities.find((e: any) => e.type === 'project_name')?.value;
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Tableau API
      const response = await fetch('/api/integrations/tableau/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: query,
          type: searchType,
          project_name: projectName,
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const searchResults = result.data.results || [];
        const resultCount = searchResults.length;

        return {
          success: true,
          message: `Found ${resultCount} result${resultCount !== 1 ? 's' : ''} for "${query}" in Tableau`,
          data: {
            results: searchResults,
            total_count: result.data.total_count,
            query: query,
            search_type: searchType,
            project_name: projectName
          },
          actions: searchResults.map((item: any) => ({
            type: 'open_url',
            label: `View ${item.name}`,
            url: item.webpage_url || item.view_url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search Tableau: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Tableau: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:tableau for )?(.+?)(?: workbooks|datasources|views|:|$)/i,
      /find (.+?) (?:workbooks|datasources|views|on tableau|:|$)/i,
      /look for (.+?) (?:workbooks|datasources|views|on tableau|:|$)/i,
      /(.+?) (?:workbooks|datasources|views|on tableau|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractSearchType(intent: string): string | null {
    if (intent.toLowerCase().includes('workbooks')) {
      return 'workbooks';
    } else if (intent.toLowerCase().includes('datasources') || intent.toLowerCase().includes('data sources')) {
      return 'datasources';
    } else if (intent.toLowerCase().includes('views')) {
      return 'views';
    } else if (intent.toLowerCase().includes('projects')) {
      return 'projects';
    }
    return 'all';
  }

  private extractProjectName(intent: string): string | null {
    const patterns = [
      /in (?:project )?(.+?)(?: workbooks|datasources|views|:|$)/i,
      /project (.+?)(?: workbooks|datasources|views|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

// Export all Tableau skills
export const TABLEAU_SKILLS = [
  new TableauCreateWorkbookSkill(),
  new TableauSearchWorkbooksSkill(),
  new TableauRefreshDatasourceSkill(),
  new TableauEmbedViewSkill(),
  new TableauSearchSkill()
];

// Export skills registry
export const TABLEAU_SKILLS_REGISTRY = {
  'tableau_create_workbook': TableauCreateWorkbookSkill,
  'tableau_search_workbooks': TableauSearchWorkbooksSkill,
  'tableau_refresh_datasource': TableauRefreshDatasourceSkill,
  'tableau_embed_view': TableauEmbedViewSkill,
  'tableau_search': TableauSearchSkill
};
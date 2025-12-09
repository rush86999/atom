#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

class BraveSearchMCPServer {
  constructor() {
    this.server = new Server(
      {
        name: 'brave-search-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
  }

  setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'brave_search',
            description: 'Search the web using Brave Search API',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'Search query',
                },
                count: {
                  type: 'number',
                  description: 'Number of results to return (default: 10)',
                  default: 10,
                },
              },
              required: ['query'],
            },
          },
        ],
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      if (request.params.name === 'brave_search') {
        return await this.handleBraveSearch(request.params.arguments);
      }
      throw new Error(`Unknown tool: ${request.params.name}`);
    });
  }

  async handleBraveSearch(args) {
    const { query, count = 10 } = args;
    const apiKey = process.env.BRAVE_SEARCH_API_KEY;

    if (!apiKey) {
      throw new Error('BRAVE_SEARCH_API_KEY environment variable is required');
    }

    try {
      const response = await fetch(
        `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=${count}`,
        {
          headers: {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': apiKey,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Brave Search API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      const results = data.web?.results || [];
      const formattedResults = results.map(result => ({
        title: result.title,
        url: result.url,
        description: result.description,
        published_date: result.age ? result.age : null,
      }));

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              query,
              results: formattedResults,
              total_results: formattedResults.length,
            }, null, 2),
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: error.message,
              query,
            }, null, 2),
          },
        ],
        isError: true,
      };
    }
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Brave Search MCP server running on stdio');
  }
}

const server = new BraveSearchMCPServer();
server.run().catch(console.error);
// Graphile Client Module - Apollo Client and GraphQL utilities

const graphileLogger = {
  info: console.log.bind(console, '[GraphileClient] INFO:'),
  error: console.error.bind(console, '[GraphileClient] ERROR:'),
  warn: console.warn.bind(console, '[GraphileClient] WARN:'),
};

// Global client with retry logic
export class GraphileClient {
  private static instance: any = null;

  static getInstance() {
    if (!this.instance) {
      this.instance = {
        endpoint: process.env.POSTGRAPHILE_GRAPH_URL,
        headers: {
          'X-Postgraphile-Admin-Secret': process.env.POSTGRAPHILE_ADMIN_SECRET,
          'X-Postgraphile-Role': 'admin',
          'Content-Type': 'application/json'
        }
      };
    }
    return this.instance;
  }

  static async request(query: string, variables: any = {}) {
    try {
      graphileLogger.info('Making GraphQL request', { queryName: query.split(' ')[1]?.split('(')[0] || 'unknown' });

      const response = await fetch(this.getInstance().endpoint, {
        method: 'POST',
        headers: this.getInstance().headers,
        body: JSON.stringify({ query, variables })
      });

      const result = await response.json();

      if (result.errors) {
        graphileLogger.error('GraphQL errors', { errors: result.errors });
        throw new Error(result.errors.map((e: any) => e.message).join(', '));\n      }

      return result.data;\n    } catch (error) {
      graphileLogger.error('GraphQL request failed', { error: error });
n      throw error;\n    }\n  }

  static async withRetry<T>(\n    operation: () => Promise<T>,\n    maxRetries = 3,\n    delay = 1000\n  ): Promise<T> {\n    let lastError: any;\n    \n    for (let attempt = 0; attempt < maxRetries; attempt++) {\n      try {\n        return await operation();\n      } catch (error) {\n        lastError = error;\n        if (attempt < maxRetries - 1) {\n          await new Promise(resolve => setTimeout(resolve, delay * (2 ** attempt)));\n          graphileLogger.warn(`Retrying operation (attempt ${attempt + 1})`);\n        }\n      }\n    }\n    \n    throw lastError;\n  }\n}

// Global client instance
export const graphileClient = GraphileClient;

// Batch operation utility
export const batchQuery = async (\n  items: any[],\n  queryFn: (batch: any[]) => Promise<any>,\n  batchSize = 50\n) => {\n  const batches = [];\n  for (let i = 0; i < items.length; i += batchSize) {\n    batches.push(items.slice(i, i + batchSize));\n  }\n\n  const results = await Promise.all(\n    batches.map(batch => graphileClient.withRetry(() => queryFn(batch)))\n  );\n\n  return results.flat();\n};

// GraphQL query utilities
export const generateQueryWithFilters = (\n  tableName: string,\n  filters: any = {},\n  orderBy?: string,\n  direction: 'asc' | 'desc' = 'asc'\n): { query: string; variables: any } => {\n  const variables: any = {};\n  const filterParts: string[] = [];\n  \n  Object.entries(filters).forEach(([key, value], index) => {\n    if (value !== undefined && value !== null) {\n      const varName = `$${key}_${index}`;\n      variables[key] = value;\n      \n      if (typeof value === 'string' && value.includes('%')) {\n        filterParts.push(`${key}: { _ilike: ${varName} }`);\n      } else if (Array.isArray(value)) {\n        filterParts.push(`${key}: { _in: ${varName} }`);\n      } else {\n        filterParts.push(`${key}: { _eq: ${varName} }`);\n      }\n    }\n  });\n\n  const orderPart = orderBy \n    ? `order_by: { ${orderBy}: ${direction.toUpperCase()} }`\n    : '';\n\n  const query = `\n    query Query${tableName}($${Object.keys(variables).join(', $')}) {\n      ${tableName}(${filterParts.length ? \`where: { ${filterParts.join(', ')} }\` : ''} ${orderPart}) {\n        id\n        created_date\n        updated_at\n      }\n    }\n  `;\n\n  return { query, variables };\n};

// Export client
export default GraphileClient;

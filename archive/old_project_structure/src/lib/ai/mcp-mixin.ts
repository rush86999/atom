import { LLMRouter } from './llm-router'
import { DatabaseService } from '../database'

export interface MCPCapable {
    webSearch(query: string): Promise<any>
    fetchUrl(url: string): Promise<any>
}

/**
 * Mixin to provide MCP capabilities to any Agent class.
 * Usage: applyMixins(MyAgent, [MCPMixin])
 */
export class MCPMixin implements MCPCapable {
    // These must be provided by the consuming class
    llmRouter!: LLMRouter
    db!: DatabaseService
    tenantId!: string

    async webSearch(query: string): Promise<any> {
        console.log(`[MCP] Agent performing web search: ${query}`)

        // 1. Margin Protection: Enforce BYOK for Search
        // Check if tenant has a search provider key configured
        const settings = await this.db.query(`
            SELECT setting_value FROM tenant_settings 
            WHERE tenant_id = $1 AND setting_key IN ('TAVILY_API_KEY', 'SERPAPI_API_KEY', 'SEARCH_PROVIDER_KEY')
            LIMIT 1
        `, [this.tenantId])

        if (settings.rows.length === 0) {
            throw new Error(`
                [Payment Required] Web Search is a BYOK feature. 
                Please add TAVILY_API_KEY or SERPAPI_API_KEY to your Tenant Settings.
                We do not mark up search costs.
            `.trim())
        }

        const apiKey = settings.rows[0].setting_value

        // 2. Perform Real Search via Tavily API
        try {
            const response = await fetch('https://api.tavily.com/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    api_key: apiKey,
                    query,
                    search_depth: 'basic',
                    max_results: 5
                })
            })

            if (!response.ok) {
                throw new Error(`Tavily API error: ${response.status}`)
            }

            const data = await response.json()
            return {
                source: 'mcp_web_search',
                provider: 'tavily',
                query,
                results: data.results.map((r: any) => ({
                    title: r.title,
                    snippet: r.content,
                    link: r.url
                }))
            }
        } catch (error: any) {
            console.error('[MCP] Web search error:', error.message)
            throw new Error(`Web search failed: ${error.message}`)
        }
    }

    async fetchUrl(url: string): Promise<any> {
        console.log(`[MCP] Agent fetching URL: ${url}`)

        try {
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'AtomSaaS-Agent/1.0'
                }
            })

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`)
            }

            const content = await response.text()
            return {
                source: 'mcp_browser',
                url,
                content: content.substring(0, 10000), // Limit content size
                contentLength: content.length
            }
        } catch (error: any) {
            console.error('[MCP] URL fetch error:', error.message)
            throw new Error(`URL fetch failed: ${error.message}`)
        }
    }
}

// Helper to apply mixins to a class
export function applyMixins(derivedCtor: any, constructors: any[]) {
    constructors.forEach((baseCtor) => {
        Object.getOwnPropertyNames(baseCtor.prototype).forEach((name) => {
            Object.defineProperty(
                derivedCtor.prototype,
                name,
                Object.getOwnPropertyDescriptor(baseCtor.prototype, name) || Object.create(null)
            )
        })
    })
}

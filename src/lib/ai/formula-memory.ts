import { LLMRouter } from './llm-router';
import { getDatabase } from '../database';

export interface Formula {
    id: string
    name: string
    expression: string
    domain: string
    use_case: string
    parameters: any[]
}

export interface FormulaSearchResult {
    id: string
    name: string
    content: string
    score?: number
}

/**
 * Formula Memory Client
 * 
 * Bridges the Frontend to the Python Backend's Hybrid Memory (Postgres + LanceDB).
 */
export class FormulaMemory {
    private baseUrl: string

    constructor() {
        this.baseUrl = process.env.BACKEND_API_URL || 'http://localhost:8000'
    }

    /**
     * Store a formula via Backend API
     */
    async storeFormula(
        workspaceId: string, // Kept for interface compatibility, mostly handled by user token in real app
        data: {
            name: string
            expression: string
            domain: string
            use_case: string
            parameters: any[]
        }
    ): Promise<string> {
        // In a real scenario, we'd pass the auth token. 
        // For now assuming internal network trust or relying on forwarded headers if implemented.
        // The backend expects a USER context usually, so this might need enhancement for full tenancy.

        try {
            const response = await fetch(`${this.baseUrl}/api/formulas`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Workspace-ID': workspaceId // Passing context if middleware supports it
                },
                body: JSON.stringify({
                    name: data.name,
                    description: data.use_case,
                    category: data.domain,
                    steps: data.expression // Mapping to backend 'steps' field for now which takes the expression
                })
            })

            if (!response.ok) {
                throw new Error(`Failed to store formula: ${response.statusText}`)
            }

            const result = await response.json()
            return result.id
        } catch (error) {
            console.error("Formula store error:", error)
            throw error
        }
    }

    /**
     * Search for formulas semantically via Backend (LanceDB)
     */
    async searchFormulas(
        workspaceId: string,
        query: string,
        domain?: string,
        limit: number = 5
    ): Promise<FormulaSearchResult[]> {
        try {
            const params = new URLSearchParams({
                q: query,
                limit: limit.toString()
            })
            if (domain) params.append('domain', domain)

            const response = await fetch(`${this.baseUrl}/api/formulas/search?${params.toString()}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Workspace-ID': workspaceId
                }
            })

            if (!response.ok) {
                console.warn(`Formula search failed: ${response.statusText}`)
                return []
            }

            const results = await response.json()
            return results as FormulaSearchResult[]
        } catch (error) {
            console.error("Formula search error:", error)
            return []
        }
    }

    /**
     * Execute a formula via Backend Engine (Strict SQL)
     */
    async executeFormula(
        workspaceId: string,
        formulaId: string,
        inputs: Record<string, any>
    ): Promise<{ result: any; success: boolean; error?: string }> {
        try {
            const response = await fetch(`${this.baseUrl}/api/formulas/${formulaId}/execute`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Workspace-ID': workspaceId
                },
                body: JSON.stringify(inputs)
            })

            if (!response.ok) {
                const errorText = await response.text()
                return { result: null, success: false, error: errorText }
            }

            const json = await response.json()
            if (json.success === false) {
                return { result: null, success: false, error: json.error }
            }

            return { result: json.result, success: true }
        } catch (error: any) {
            return { result: null, success: false, error: error.message }
        }
    }

    /**
     * Use LLM to extract potential formulas or business logic from text
     */
    async extractFormulaFromContext(
        workspaceId: string,
        context: string
    ): Promise<{ name: string; expression: string; use_case: string } | null> {
        const llm = new LLMRouter(getDatabase());

        const prompt = `
        Analyze the following context and extract a mathematical or logical formula that represents the business logic described.
        
        Context:
        "${context}"
        
        Respond with JSON:
        {
          "name": "formula name",
          "expression": "mathematical expression (e.g. x * 1.2)",
          "use_case": "description of when to use this"
        }
        
        If no formula is identified, respond with null.
        `;

        try {
            const response = await llm.call(workspaceId, {
                type: 'analysis',
                messages: [{ role: 'user', content: prompt }],
                model: 'gpt-4o-mini'
            }) as { content: string };

            const jsonMatch = response.content.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return JSON.parse(jsonMatch[0]);
            }
        } catch (error) {
            console.error("Formula extraction error:", error);
        }
        return null;
    }
}

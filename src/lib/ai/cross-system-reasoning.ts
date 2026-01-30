import { LLMRouter } from './llm-router';
import { getDatabase } from '../database';
import { SalesforceClient } from '../integrations/salesforce';
import { HubSpotClient } from '../integrations/hubspot';
import { SlackClient } from '../integrations/slack';
import { GoogleCalendarClient } from '../integrations/google-calendar';

interface DataSource {
    name: string;
    type: 'crm' | 'communication' | 'calendar' | 'database';
    connected: boolean;
}

interface ReasoningResult {
    answer: string;
    sources: string[];
    confidence: number;
    dataUsed: Record<string, unknown>[];
}

/**
 * Cross-System Reasoning Engine
 * Correlates data from multiple integrations to answer complex queries
 */
export class CrossSystemReasoning {
    private tenantId: string;
    private llmRouter: LLMRouter;

    constructor(tenantId: string) {
        this.tenantId = tenantId;
        this.llmRouter = new LLMRouter(getDatabase());
    }

    /**
     * Get all connected data sources
     */
    async getDataSources(): Promise<DataSource[]> {
        const db = getDatabase();
        const result = await db.query(
            `SELECT provider FROM integration_tokens WHERE tenant_id = $1`,
            [this.tenantId]
        );

        const connectedProviders = result.rows.map((r) => r.provider);

        return [
            { name: 'Salesforce', type: 'crm', connected: connectedProviders.includes('salesforce') },
            { name: 'HubSpot', type: 'crm', connected: connectedProviders.includes('hubspot') },
            { name: 'Slack', type: 'communication', connected: connectedProviders.includes('slack') },
            { name: 'Google Calendar', type: 'calendar', connected: connectedProviders.includes('google') },
        ];
    }

    /**
     * Gather relevant data from all connected sources
     */
    async gatherData(query: string): Promise<Record<string, unknown>> {
        const data: Record<string, unknown> = {};
        const sources = await this.getDataSources();

        // Determine which sources are relevant
        const relevantSources = await this.determineRelevantSources(query, sources);

        for (const source of relevantSources) {
            try {
                switch (source.name) {
                    case 'Salesforce': {
                        const sf = new SalesforceClient(this.tenantId);
                        const hasTokens = await sf.loadTokens();
                        if (hasTokens) {
                            data.salesforce = {
                                accounts: await sf.getAccounts(5),
                                contacts: await sf.getContacts(5),
                                opportunities: await sf.getOpportunities(5),
                            };
                        }
                        break;
                    }
                    case 'HubSpot': {
                        const hs = new HubSpotClient(this.tenantId);
                        const hasTokens = await hs.loadTokens();
                        if (hasTokens) {
                            data.hubspot = {
                                contacts: await hs.getContacts(5),
                                companies: await hs.getCompanies(5),
                                deals: await hs.getDeals(5),
                            };
                        }
                        break;
                    }
                    case 'Slack': {
                        const slack = new SlackClient(this.tenantId);
                        const hasTokens = await slack.loadTokens();
                        if (hasTokens) {
                            data.slack = {
                                channels: await slack.getChannels(),
                            };
                        }
                        break;
                    }
                    case 'Google Calendar': {
                        const gcal = new GoogleCalendarClient(this.tenantId);
                        const hasTokens = await gcal.loadTokens();
                        if (hasTokens) {
                            data.calendar = {
                                events: await gcal.getEvents('primary', { maxResults: 10 }),
                            };
                        }
                        break;
                    }
                }
            } catch (error) {
                console.error(`Failed to gather data from ${source.name}:`, error);
            }
        }

        return data;
    }

    /**
     * Determine which sources are relevant to the query
     */
    private async determineRelevantSources(
        query: string,
        sources: DataSource[]
    ): Promise<DataSource[]> {
        const connectedSources = sources.filter((s) => s.connected);

        if (connectedSources.length === 0) return [];

        const prompt = `Given this user query and available data sources, which sources are relevant?

Query: "${query}"

Available sources:
${connectedSources.map((s) => `- ${s.name} (${s.type})`).join('\n')}

Return a JSON array of relevant source names, e.g. ["Salesforce", "Slack"]
Only include sources that would help answer the query.
JSON:`;

        try {
            const response = await this.llmRouter.call(this.tenantId, {
                type: 'analysis',
                messages: [{ role: 'user', content: prompt }],
                model: 'gpt-4o-mini',
            }) as { content: string; model: string; provider: string };

            const jsonMatch = response.content?.match(/\[[\s\S]*\]/);
            if (jsonMatch) {
                const relevantNames = JSON.parse(jsonMatch[0]) as string[];
                return connectedSources.filter((s) => relevantNames.includes(s.name));
            }
        } catch (error) {
            console.error('Failed to determine relevant sources:', error);
        }

        return connectedSources; // Fall back to all sources
    }

    /**
     * Main reasoning function - answers questions using cross-system data
     */
    async reason(query: string): Promise<ReasoningResult> {
        // Gather data from relevant sources
        const data = await this.gatherData(query);
        const sourcesUsed = Object.keys(data);

        if (sourcesUsed.length === 0) {
            return {
                answer: 'No data sources are connected. Please connect integrations to enable cross-system reasoning.',
                sources: [],
                confidence: 0,
                dataUsed: [],
            };
        }

        // Build context from gathered data
        const contextParts = sourcesUsed.map((source) => {
            return `=== ${source.toUpperCase()} DATA ===\n${JSON.stringify(data[source], null, 2)}`;
        });

        const prompt = `You are an AI assistant with access to data from multiple business systems.
Use the following data to answer the user's question accurately.
Correlate information across systems when relevant.
Be specific and cite which data you're using.

${contextParts.join('\n\n')}

USER QUESTION: ${query}

Provide a comprehensive answer based on the available data:`;

        const response = await this.llmRouter.call(this.tenantId, {
            type: 'analysis',
            messages: [{ role: 'user', content: prompt }],
            model: 'gpt-4o',
        }) as { content: string; model: string; provider: string };

        // Extract data items used
        const dataUsed: Record<string, unknown>[] = [];
        for (const source of sourcesUsed) {
            const sourceData = data[source] as Record<string, unknown[]>;
            for (const items of Object.values(sourceData)) {
                if (Array.isArray(items)) {
                    dataUsed.push(...(items.slice(0, 3) as Record<string, unknown>[]));
                }
            }
        }

        return {
            answer: response.content || 'Unable to generate response.',
            sources: sourcesUsed,
            confidence: sourcesUsed.length > 1 ? 0.85 : 0.7,
            dataUsed: dataUsed.slice(0, 5),
        };
    }

    /**
     * Find correlations between entities across systems
     */
    async findCorrelations(entityType: string, identifier: string): Promise<{
        matches: { source: string; entity: Record<string, unknown> }[];
        summary: string;
    }> {
        const data = await this.gatherData(`Find ${entityType} ${identifier}`);
        const matches: { source: string; entity: Record<string, unknown> }[] = [];

        // Search for matching entities
        for (const [source, sourceData] of Object.entries(data)) {
            const records = sourceData as Record<string, unknown[]>;
            for (const items of Object.values(records)) {
                if (Array.isArray(items)) {
                    for (const item of items) {
                        const itemStr = JSON.stringify(item).toLowerCase();
                        if (itemStr.includes(identifier.toLowerCase())) {
                            matches.push({ source, entity: item as Record<string, unknown> });
                        }
                    }
                }
            }
        }

        const summary = matches.length > 0
            ? `Found ${matches.length} matching records across ${Array.from(new Set(matches.map((m) => m.source))).join(', ')}`
            : 'No matching records found';

        return { matches, summary };
    }
}

export default CrossSystemReasoning;

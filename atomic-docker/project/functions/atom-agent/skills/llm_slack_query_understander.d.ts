export interface StructuredSlackQuery {
    fromUser?: string;
    inChannel?: string;
    mentionsUser?: string;
    hasFile?: boolean;
    hasLink?: boolean;
    hasReaction?: string;
    onDate?: string;
    beforeDate?: string;
    afterDate?: string;
    textKeywords?: string;
    exactPhrase?: string;
}
/**
 * Uses an LLM to understand a natural language Slack query and transform it
 * into a StructuredSlackQuery object.
 * @param rawUserQuery The user's natural language query about finding Slack messages.
 * @returns A Promise resolving to a Partial<StructuredSlackQuery> object.
 */
export declare function understandSlackSearchQueryLLM(rawUserQuery: string): Promise<Partial<StructuredSlackQuery>>;

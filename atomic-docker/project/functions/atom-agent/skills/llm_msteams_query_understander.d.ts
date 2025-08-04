export interface StructuredMSTeamsQuery {
    fromUser?: string;
    inChatOrChannel?: string;
    mentionsUser?: string;
    hasFile?: boolean;
    hasLink?: boolean;
    onDate?: string;
    beforeDate?: string;
    afterDate?: string;
    textKeywords?: string;
    subjectContains?: string;
    exactPhrase?: string;
}
/**
 * Uses an LLM to understand a natural language MS Teams query and transform it
 * into a StructuredMSTeamsQuery object.
 * @param rawUserQuery The user's natural language query about finding Teams messages.
 * @returns A Promise resolving to a Partial<StructuredMSTeamsQuery> object.
 */
export declare function understandMSTeamsSearchQueryLLM(rawUserQuery: string): Promise<Partial<StructuredMSTeamsQuery>>;

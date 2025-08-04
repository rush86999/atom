import { HybridSearchFilters } from '../../atomic-docker/project/functions/atom-agent/types';
/**
 * Represents the structured output from parsing a user's raw search query with an LLM.
 */
export interface ParsedSearchQuery {
    search_term: string;
    filters: HybridSearchFilters;
}
/**
 * Takes a user's raw natural language search query and uses an LLM to parse it
 * into a clean search term and a structured filters object.
 *
 * @param rawQuery The user's original search query string.
 * @returns A promise that resolves to a ParsedSearchQuery object.
 *          In case of parsing failure, it gracefully falls back to returning
 *          the original query as the search term and an empty filters object.
 */
export declare function parseSearchQueryWithLLM(rawQuery: string): Promise<ParsedSearchQuery>;

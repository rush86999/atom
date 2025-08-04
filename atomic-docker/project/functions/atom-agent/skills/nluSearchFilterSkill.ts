import { HybridSearchFilters } from '../../atomic-docker/project/functions/atom-agent/types';
import {
  OpenAIGroqService_Stub,
  StructuredLLMPrompt,
  SearchQueryParsingData,
} from '../lib/llmUtils'; // Assuming this is the path
import { logger } from '../../atomic-docker/project/functions/_utils/logger';

/**
 * Represents the structured output from parsing a user's raw search query with an LLM.
 */
export interface ParsedSearchQuery {
  search_term: string;
  filters: HybridSearchFilters;
}

const llmService = new OpenAIGroqService_Stub(process.env.GROQ_API_KEY); // Or however API key is managed

/**
 * Takes a user's raw natural language search query and uses an LLM to parse it
 * into a clean search term and a structured filters object.
 *
 * @param rawQuery The user's original search query string.
 * @returns A promise that resolves to a ParsedSearchQuery object.
 *          In case of parsing failure, it gracefully falls back to returning
 *          the original query as the search term and an empty filters object.
 */
export async function parseSearchQueryWithLLM(
  rawQuery: string
): Promise<ParsedSearchQuery> {
  const fallbackResponse: ParsedSearchQuery = {
    search_term: rawQuery,
    filters: {},
  };

  const currentDate = new Date().toISOString().split('T')[0]; // Get YYYY-MM-DD

  const prompt: StructuredLLMPrompt = {
    task: 'parse_search_query',
    data: {
      rawQuery: rawQuery,
      currentDate: currentDate,
    } as SearchQueryParsingData,
  };

  try {
    const llmResponse = await llmService.generate(prompt, 'llama3-8b-8192'); // Use a fast model

    if (!llmResponse.success || !llmResponse.content) {
      logger.error(
        `[parseSearchQueryWithLLM] LLM call failed or returned no content. Error: ${llmResponse.error}`
      );
      return fallbackResponse;
    }

    // The prompt asks for JSON only, so we attempt to parse it directly.
    const parsedJson = JSON.parse(llmResponse.content);

    // Basic validation of the parsed structure
    if (
      typeof parsedJson.search_term === 'string' &&
      typeof parsedJson.filters === 'object'
    ) {
      logger.info(
        `[parseSearchQueryWithLLM] Successfully parsed query. Term: "${parsedJson.search_term}", Filters:`,
        parsedJson.filters
      );
      return {
        search_term: parsedJson.search_term,
        filters: parsedJson.filters as HybridSearchFilters,
      };
    } else {
      logger.warn(
        `[parseSearchQueryWithLLM] Parsed JSON from LLM has incorrect structure.`,
        parsedJson
      );
      return fallbackResponse;
    }
  } catch (error: any) {
    logger.error(
      `[parseSearchQueryWithLLM] An exception occurred during LLM parsing. Error: ${error.message}`,
      error
    );
    return fallbackResponse;
  }
}

import { SearchResult, WebResearchSkillResponse, SkillError } from '../types';
import { google_web_search } from 'google_web_search';

export async function searchWeb(query: string): Promise<WebResearchSkillResponse<SearchResult[]>> {
  console.log(`Initiating web search for query: "${query}"`);

  if (!query || query.trim() === "") {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Search query cannot be empty.' } };
  }

  try {
    const searchResults = await google_web_search({ query });

    if (!searchResults || searchResults.length === 0) {
      return { ok: true, data: [] };
    }

    const mappedResults: SearchResult[] = searchResults.map((result: any) => ({
      title: result.title,
      link: result.link,
      snippet: result.snippet,
    }));

    return { ok: true, data: mappedResults };
  } catch (error: any) {
    console.error('Error during google_web_search:', error);
    const skillError: SkillError = {
      code: 'SEARCH_API_ERROR',
      message: `An error occurred during web search: ${error.message}`,
      details: error,
    };
    return { ok: false, error: skillError };
  }
}
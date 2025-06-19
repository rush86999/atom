import { SearchResult, WebResearchSkillResponse, SkillError } from '../types';
import { ATOM_SERPAPI_API_KEY } from '../_libs/constants'; // Use the new constant
import { getJson, SerpAPIError } from 'serpapi'; // Import SerpAPI client and error type

/**
 * Performs an actual web search using the SerpApi library.
 *
 * @param query The search query string.
 * @param apiKey The SerpApi API key.
 * @returns A promise that resolves to a WebResearchSkillResponse containing search results or an error.
 */
async function performActualWebSearch(query: string, apiKey: string): Promise<WebResearchSkillResponse<SearchResult[]>> {
  console.log(`Performing SerpApi search for query: "${query}"`);
  try {
    const params = {
      q: query,
      api_key: apiKey,
      // engine: "google", // Default, can be specified if needed
      // location: "Austin, Texas, United States", // Optional location
      // hl: "en", // Optional language
      // gl: "us", // Optional country
      // num: "10" // Optional number of results (default 10)
    };

    const response = await getJson("google", params); // "google" is the default engine for general web search with SerpApi

    if (response.error) {
      // SerpApi can return errors within the JSON response body
      console.error('SerpApi returned an error in the response body:', response.error);
      let errorCode: SkillError['code'] = 'SEARCH_API_ERROR';
      if (typeof response.error === 'string' && response.error.toLowerCase().includes('invalid api key')) {
        errorCode = 'SEARCH_API_AUTH_ERROR';
      }
      return {
        ok: false,
        error: {
          code: errorCode,
          message: `SerpApi error: ${response.error}`,
        },
      };
    }

    if (response.organic_results && Array.isArray(response.organic_results)) {
      const results: SearchResult[] = response.organic_results.map((item: any) => ({
        title: item.title || 'No title',
        link: item.link || '#',
        snippet: item.snippet || item.snippet_highlighted_words?.join(' ') || 'No snippet available.',
        // Other potential fields: item.source, item.date, item.position
      }));
      return { ok: true, data: results };
    }

    console.warn('SerpApi response format unexpected or no organic results:', response);
    return {
      ok: false,
      error: {
        code: 'API_RESPONSE_FORMAT_ERROR',
        message: 'SerpApi response format unexpected or no organic results found.',
        details: response
      }
    };

  } catch (error: any) {
    console.error('Error during SerpApi call:', error.message);

    let skillError: SkillError;

    if (error instanceof SerpAPIError) {
      // This is an error thrown by the serpapi library itself (e.g., network issue, non-JSON response)
      skillError = {
        code: 'SEARCH_API_ERROR', // Could be NETWORK_ERROR if distinguishable
        message: `SerpApi library error: ${error.message}`,
        details: error.stack,
      };
    } else if (error.name === 'SyntaxError' && error.message.includes('HTML output') && error.message.includes('Serp API')) {
      // This specific error from serpapi library indicates an issue like invalid API key or exceeded quota
      // where SerpApi returns an HTML error page instead of JSON.
      skillError = {
        code: 'SEARCH_API_AUTH_ERROR', // Or a more general SEARCH_API_ERROR
        message: 'SerpApi returned an HTML error page, often due to an invalid API key or exhausted quota.',
        details: error.message,
      };
    }
    else {
      // Generic error
      skillError = {
        code: 'UNKNOWN_SEARCH_ERROR',
        message: `An unknown error occurred during web search: ${error.message}`,
        details: error,
      };
    }
    return { ok: false, error: skillError };
  }
}

/**
 * Searches the web for a given query using SerpApi.
 *
 * @param query The search query string.
 * @returns A promise that resolves to a WebResearchSkillResponse containing search results or an error.
 */
export async function searchWeb(query: string): Promise<WebResearchSkillResponse<SearchResult[]>> {
  console.log(`Initiating web search for query: "${query}"`);

  if (!query || query.trim() === "") {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Search query cannot be empty.' } };
  }

  // Use the ATOM_SERPAPI_API_KEY from constants.ts
  const apiKey = ATOM_SERPAPI_API_KEY;

  if (!apiKey) {
    console.error('ATOM_SERPAPI_API_KEY is not configured.');
    return {
        ok: false,
        error: {
            code: 'CONFIG_ERROR',
            message: 'Web search functionality is not configured. ATOM_SERPAPI_API_KEY is missing.'
        }
    };
  }

  // Call the actual search implementation
  return await performActualWebSearch(query, apiKey);
}

[end of atomic-docker/project/functions/atom-agent/skills/webResearchSkills.ts]

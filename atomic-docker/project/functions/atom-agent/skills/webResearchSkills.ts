import { SearchResult, WebResearchSkillResponse, SkillError } from '../types';
import axios, { AxiosError } from 'axios';

// Note: mockSearchResults is removed as we will now return errors or empty data, not mocks.

async function performActualWebSearch(query: string, apiKey: string): Promise<WebResearchSkillResponse<SearchResult[]>> {
  const searchApiUrl = `https://api.exampleSearchEngine.com/search`; // Placeholder URL

  // Since this function is explicitly a placeholder for a real search engine,
  // if it's called, it means SEARCH_API_KEY was set, but this function wasn't replaced.
  // We will treat this as a "Not Implemented" scenario for the actual search functionality.
  // Alternatively, we could let it try the fake URL and fail with a network error.
  // For clarity, let's return a specific error if this placeholder is hit.
  if (searchApiUrl.includes("api.exampleSearchEngine.com")) {
    console.warn(`performActualWebSearch is using a placeholder URL: ${searchApiUrl}`);
    return {
        ok: false,
        error: {
            code: 'NOT_IMPLEMENTED',
            message: 'Actual web search functionality is not implemented; using a placeholder URL.',
            details: `Search URL: ${searchApiUrl}`
        }
    };
  }

  try {
    const response = await axios.get(searchApiUrl, {
      params: { q: query, key: apiKey },
    });

    if (response.data && Array.isArray(response.data.items)) {
      const results = response.data.items.map((item: any) => ({
        title: item.title || 'No title',
        link: item.link || '#',
        snippet: item.snippet || 'No snippet available.',
      }));
      return { ok: true, data: results };
    }
    console.warn('Web search API response format unexpected:', response.data);
    return { ok: false, error: { code: 'API_RESPONSE_FORMAT_ERROR', message: 'Web search API response format unexpected.', details: response.data } };
  } catch (error: any) {
    console.error('Error during web search API call:', error.message);
    const axiosError = error as AxiosError;
    let errorCode = 'API_ERROR';
    if (axiosError.isAxiosError) {
        if (axiosError.code === 'ENOTFOUND' || axiosError.code === 'ECONNREFUSED') {
            errorCode = 'NETWORK_ERROR';
        } else if (axiosError.response?.status) {
            errorCode = `API_HTTP_${axiosError.response.status}`;
        }
    }
    return {
        ok: false,
        error: {
            code: errorCode,
            message: `Failed to perform web search: ${error.message}`,
            details: axiosError.response?.data || axiosError.message
        }
    };
  }
}

export async function searchWeb(query: string): Promise<WebResearchSkillResponse<SearchResult[]>> {
  console.log(`Performing web search for query: "${query}"`);

  if (!query || query.trim() === "") {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Search query cannot be empty.' } };
  }

  const apiKey = process.env.SEARCH_API_KEY;

  if (!apiKey) {
    console.error('SEARCH_API_KEY is not configured.');
    return {
        ok: false,
        error: {
            code: 'CONFIG_ERROR',
            message: 'Web search functionality is not configured. SEARCH_API_KEY is missing.'
        }
    };
  }

  // The function performActualWebSearch now returns WebResearchSkillResponse, so just return its result.
  return await performActualWebSearch(query, apiKey);
}

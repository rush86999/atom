// Placeholder for web research skill functions
import { SearchResult } from '../types';
import axios from 'axios'; // Added import

// Keep existing mockSearchResults for fallback or if API key is missing
const mockSearchResults: SearchResult[] = [
  {
    title: 'Example Domain',
    link: 'http://example.com',
    snippet: 'Example Domain for use in illustrative examples in documents. You may use this domain in examples without prior coordination or asking for permission.',
  },
  {
    title: 'Internet Assigned Numbers Authority (IANA)',
    link: 'https://www.iana.org/',
    snippet: 'The Internet Assigned Numbers Authority (IANA) is responsible for coordinating some of the key elements that keep the Internet running smoothly.',
  },
  {
    title: 'World Wide Web Consortium (W3C)',
    link: 'https://www.w3.org/',
    snippet: 'The World Wide Web Consortium (W3C) is an international community that develops open standards to ensure the long-term growth of the Web.',
  }
];

async function performActualWebSearch(query: string, apiKey: string): Promise<SearchResult[]> {
  const searchApiUrl = `https://api.exampleSearchEngine.com/search`; // Placeholder URL
  try {
    const response = await axios.get(searchApiUrl, {
      params: { q: query, key: apiKey }, // Common way to pass query params
    });

    // Assuming the API returns data in the shape: { items: [{ title: string, link: string, snippet: string }] }
    if (response.data && Array.isArray(response.data.items)) {
      return response.data.items.map((item: any) => ({
        title: item.title || 'No title',
        link: item.link || '#',
        snippet: item.snippet || 'No snippet available.',
      }));
    }
    console.warn('Web search API response format unexpected:', response.data);
    return []; // Return empty if format is not as expected
  } catch (error: any) {
    console.error('Error during web search API call:', error.message);
    if (axios.isAxiosError(error) && error.response) {
      console.error('API Error Status:', error.response.status);
      console.error('API Error Data:', error.response.data);
    }
    throw new Error(`Failed to perform web search: ${error.message}`);
  }
}

export async function searchWeb(query: string): Promise<SearchResult[]> {
  console.log(`Performing web search for query: "${query}"`);
  const apiKey = process.env.SEARCH_API_KEY;

  if (!apiKey) {
    console.error('SEARCH_API_KEY is not configured. Returning mock results or an error message.');
    // Option 1: Return mock results (Filtering example, can be adjusted)
    // const lowerCaseQuery = query.toLowerCase();
    // const results = mockSearchResults.filter(
    //   result => result.title.toLowerCase().includes(lowerCaseQuery) || result.snippet.toLowerCase().includes(lowerCaseQuery)
    // );
    // if (results.length > 0) return Promise.resolve(results);

    // Option 2: Return an error-like search result
    return Promise.resolve([{
      title: 'Search Not Configured',
      link: '#',
      snippet: 'The web search functionality is not configured. Please set the SEARCH_API_KEY environment variable.'
    }]);
  }

  try {
    return await performActualWebSearch(query, apiKey);
  } catch (error: any) {
    console.error(`searchWeb failed: ${error.message}`);
    return Promise.resolve([{
      title: 'Search Error',
      link: '#',
      snippet: `An error occurred while trying to perform the web search: ${error.message}`
    }]);
  }
}

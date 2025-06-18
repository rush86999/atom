import got from 'got';
import { ATOM_SERPAPI_API_KEY, SERPAPI_BASE_URL } from '../_libs/constants';
import { SearchResult } from '../types';
import { URLSearchParams } from 'url'; // Node.js built-in

export async function searchWeb(query: string, userId?: string /* userId might be unused for global search but good for consistency */): Promise<SearchResult[]> {
    if (!ATOM_SERPAPI_API_KEY) {
        console.error("SerpApi API key is missing. Cannot perform web search.");
        // Return an empty array or throw an error to indicate configuration issue
        return [];
    }
    if (!query || query.trim() === "") {
        console.log("Search query is empty.");
        return [];
    }

    // Add userId to logs if available, for better tracing
    const logPrefix = userId ? `(userId: ${userId}) ` : "";
    console.log(`${logPrefix}Performing web search with SerpApi for query: "${query}"`);

    const params = new URLSearchParams({
        q: query,
        api_key: ATOM_SERPAPI_API_KEY,
        engine: 'google', // Or make this configurable if needed
        // You can add other params like 'location', 'num' (for number of results), etc.
        // num: '5' // example to limit to 5 results from API side
    });

    const url = `${SERPAPI_BASE_URL}?${params.toString()}`;

    try {
        // SerpApi typically returns JSON directly, so .json() might not be needed if got defaults to it or if type is specified.
        // However, explicitly calling .json() is safer if the Content-Type header isn't perfectly standard.
        // Forcing responseType to 'json' in options is often more robust.
        const response: any = await got.get(url, { responseType: 'json' }).json();

        if (response && response.organic_results && response.organic_results.length > 0) {
            return response.organic_results.map((item: any) => ({
                title: item.title || 'No title',
                link: item.link || '#',
                snippet: item.snippet || 'No snippet available.'
            })).slice(0, 5); // Limit to top 5 results for now
        } else if (response && response.answer_box) { // Handle cases like definitions or direct answers
            // Ensure answer_box fields are accessed safely
            const title = response.answer_box.title || response.answer_box.question || 'Direct Answer';
            const link = response.answer_box.link || (response.answer_box.source?.link) ||'#'; // Check source link too
            let snippet = response.answer_box.answer || response.answer_box.snippet || (Array.isArray(response.answer_box.lines) ? response.answer_box.lines.join(' ') : 'See link for details.');
            if(response.answer_box.result) snippet = response.answer_box.result; // Sometimes direct result is here

            return [{
                title: title,
                link: link,
                snippet: snippet
            }];
        }
        else {
            console.log(`${logPrefix}No organic results or answer box found for query: "${query}" in SerpApi response.`);
            return [];
        }
    } catch (error: any) {
        console.error(`${logPrefix}Error performing web search with SerpApi:`, error.response ? error.response.body : error.message);
        // Consider returning a specific error object or message
        return []; // Return empty array on error for now
    }
}

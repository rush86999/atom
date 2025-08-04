import { SearchResult } from '../../types';
import { searchWeb as search } from './webResearchSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleSearchWeb(entities: any): Promise<string> {
  try {
    const { query } = entities;
    if (!query || typeof query !== 'string') {
      return 'A search query is required to search the web via NLU.';
    } else {
      const results: SearchResult[] = await search(query);
      if (results.length === 0) {
        return `No web results found for "${query}" (via NLU).`;
      } else {
        const resultList = results
          .map(
            (result) =>
              `- ${result.title}\n  Link: ${result.link}\n  Snippet: ${result.snippet}`
          )
          .join('\n\n');
        return `Web search results for "${query}" (via NLU):\n\n${resultList}`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't perform the web search due to an error (NLU path)."
    );
  }
}

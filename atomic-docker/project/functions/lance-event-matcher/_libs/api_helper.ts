import OpenAI from 'openai';
import { OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, DEFAULT_SEARCH_LIMIT } from './constants';
import { getEventTable } from './lancedb_connect';
import { EventRecord } from './types';

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: OPENAI_API_KEY,
});

/**
 * Converts a given text string into a vector embedding using OpenAI API.
 * @param text The text to convert.
 * @returns A promise that resolves to the vector embedding.
 * @throws Error if the conversion fails.
 */
export async function convertTextToVector(text: string): Promise<number[]> {
  if (!text || text.trim() === '') {
    throw new Error('Input text cannot be empty.');
  }
  try {
    const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
      model: OPENAI_EMBEDDING_MODEL,
      input: text.trim(),
    };
    const res = await openai.embeddings.create(embeddingRequest);
    if (res?.data?.[0]?.embedding) {
      return res.data[0].embedding;
    } else {
      throw new Error('Failed to generate embedding from OpenAI: No embedding data returned.');
    }
  } catch (error) {
    console.error('Error converting text to OpenAI vector:', error);
    throw new Error(`OpenAI API error during vector conversion: ${error.message}`);
  }
}

/**
 * Searches for events in LanceDB based on a search vector and other criteria.
 * @param userId The ID of the user whose events to search.
 * @param searchVector The vector embedding of the search query.
 * @param startDate Optional start date for filtering events (ISO 8601).
 * @param endDate Optional end date for filtering events (ISO 8601).
 * @param limit Optional limit for the number of results.
 * @returns A promise that resolves to an array of matching event records.
 */
export async function searchEventsInLanceDB(
  userId: string,
  searchVector: number[],
  startDate?: string,
  endDate?: string,
  limit: number = DEFAULT_SEARCH_LIMIT
): Promise<EventRecord[]> {
  if (!userId) {
    throw new Error('User ID must be provided for searching events.');
  }
  if (!searchVector || searchVector.length === 0) {
    throw new Error('Search vector must be provided.');
  }

  try {
    const table = await getEventTable();
    let query = table.search(searchVector).where(`userId = '${userId.replace(/'/g, "''")}'`); // Escape single quotes in userId

    let dateFilter = '';
    if (startDate) {
      // Basic validation for date format can be added here if needed
      dateFilter += `start_date >= '${startDate.replace(/'/g, "''")}'`;
    }
    if (endDate) {
      // Basic validation for date format can be added here if needed
      if (dateFilter) dateFilter += ' AND ';
      dateFilter += `end_date <= '${endDate.replace(/'/g, "''")}'`;
    }

    if (dateFilter) {
      query = query.where(dateFilter);
    }

    query = query.limit(limit);

    const results = await query.execute<EventRecord>();
    // The results from LanceDB might be typed more generically by the library.
    // We cast to EventRecord[] based on our schema.
    return results as EventRecord[];
  } catch (error) {
    console.error('Error searching events in LanceDB:', error);
    // Log specific LanceDB errors if possible
    throw new Error(`LanceDB search failed: ${error.message}`);
  }
}

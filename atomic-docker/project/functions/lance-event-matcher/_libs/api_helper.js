import got from 'got';
import OpenAI from 'openai';
import { OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, DEFAULT_SEARCH_LIMIT, HASURA_GRAPHQL_URL,
// HASURA_ADMIN_SECRET is passed as an argument for security
 } from './constants';
import { getEventTable } from './lancedb_connect';
// Initialize OpenAI client
const openai = new OpenAI({
    apiKey: OPENAI_API_KEY, // This might be better initialized per-call if key can change
});
/**
 * Converts a given text string into a vector embedding using OpenAI API.
 * @param text The text to convert.
 * @returns A promise that resolves to the vector embedding.
 * @throws Error if the conversion fails.
 */
export async function convertTextToVector(text) {
    if (!text || text.trim() === '') {
        throw new Error('Input text cannot be empty.');
    }
    try {
        const embeddingRequest = {
            model: OPENAI_EMBEDDING_MODEL,
            input: text.trim(),
        };
        const res = await openai.embeddings.create(embeddingRequest);
        if (res?.data?.[0]?.embedding) {
            return res.data[0].embedding;
        }
        else {
            throw new Error('Failed to generate embedding from OpenAI: No embedding data returned.');
        }
    }
    catch (error) {
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
export async function searchEventsInLanceDB(userId, searchVector, startDate, endDate, limit = DEFAULT_SEARCH_LIMIT) {
    if (!userId) {
        throw new Error('User ID must be provided for searching events.');
    }
    if (!searchVector || searchVector.length === 0) {
        throw new Error('Search vector must be provided.');
    }
    try {
        const table = await getEventTable();
        let query = table
            .search(searchVector)
            .where(`userId = '${userId.replace(/'/g, "''")}'`); // Escape single quotes in userId
        let dateFilter = '';
        if (startDate) {
            // Basic validation for date format can be added here if needed
            dateFilter += `start_date >= '${startDate.replace(/'/g, "''")}'`;
        }
        if (endDate) {
            // Basic validation for date format can be added here if needed
            if (dateFilter)
                dateFilter += ' AND ';
            dateFilter += `end_date <= '${endDate.replace(/'/g, "''")}'`;
        }
        if (dateFilter) {
            query = query.where(dateFilter);
        }
        query = query.limit(limit);
        const results = await query.execute();
        // The results from LanceDB might be typed more generically by the library.
        // We cast to EventRecord[] based on our schema.
        return results;
    }
    catch (error) {
        console.error('Error searching events in LanceDB:', error);
        // Log specific LanceDB errors if possible
        throw new Error(`LanceDB search failed: ${error.message}`);
    }
}
/**
 * Fetches user categories from Hasura.
 * @param userId The ID of the user whose categories to fetch.
 * @param hasuraAdminSecret The Hasura admin secret for authentication.
 * @returns A promise that resolves to an array of CategoryType objects.
 * @throws Error if the fetching fails.
 */
export async function getUserCategories(userId, hasuraAdminSecret) {
    if (!userId) {
        throw new Error('User ID must be provided for fetching categories.');
    }
    if (!hasuraAdminSecret) {
        throw new Error('Hasura admin secret must be provided.');
    }
    const query = `
    query GetUserCategories($userId: uuid!) {
      Category(where: {userId: {_eq: $userId}, deleted: {_eq: false}}) {
        id
        name
        # description # Uncomment if your CategoryType and AI prompt can use it
      }
    }
  `;
    const variables = { userId };
    try {
        const response = await got.post(HASURA_GRAPHQL_URL, {
            json: {
                query,
                variables,
            },
            headers: {
                'x-hasura-admin-secret': hasuraAdminSecret,
                'Content-Type': 'application/json',
            },
            responseType: 'json',
        });
        // Type assertion for the body
        const body = response.body;
        if (body.errors) {
            console.error('Hasura errors:', body.errors);
            throw new Error(`Error fetching categories from Hasura: ${body.errors.map((e) => e.message).join(', ')}`);
        }
        return body.data?.Category || [];
    }
    catch (error) {
        console.error('Error during getUserCategories:', error.response ? error.response.body : error.message);
        // Check if it's a got HTTPError to get more details
        if (error.name === 'HTTPError' && error.response) {
            throw new Error(`Failed to fetch categories from Hasura. Status: ${error.response.statusCode}, Body: ${JSON.stringify(error.response.body)}`);
        }
        throw new Error(`Network or other error fetching categories: ${error.message}`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpX2hlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaV9oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBQ3RCLE9BQU8sTUFBTSxNQUFNLFFBQVEsQ0FBQztBQUM1QixPQUFPLEVBQ0wsY0FBYyxFQUNkLHNCQUFzQixFQUN0QixvQkFBb0IsRUFDcEIsa0JBQWtCO0FBQ2xCLDREQUE0RDtFQUM3RCxNQUFNLGFBQWEsQ0FBQztBQUNyQixPQUFPLEVBQUUsYUFBYSxFQUFFLE1BQU0sbUJBQW1CLENBQUM7QUFHbEQsMkJBQTJCO0FBQzNCLE1BQU0sTUFBTSxHQUFHLElBQUksTUFBTSxDQUFDO0lBQ3hCLE1BQU0sRUFBRSxjQUFjLEVBQUUsOERBQThEO0NBQ3ZGLENBQUMsQ0FBQztBQUVIOzs7OztHQUtHO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSxtQkFBbUIsQ0FBQyxJQUFZO0lBQ3BELElBQUksQ0FBQyxJQUFJLElBQUksSUFBSSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsRUFBRSxDQUFDO1FBQ2hDLE1BQU0sSUFBSSxLQUFLLENBQUMsNkJBQTZCLENBQUMsQ0FBQztJQUNqRCxDQUFDO0lBQ0QsSUFBSSxDQUFDO1FBQ0gsTUFBTSxnQkFBZ0IsR0FBNEM7WUFDaEUsS0FBSyxFQUFFLHNCQUFzQjtZQUM3QixLQUFLLEVBQUUsSUFBSSxDQUFDLElBQUksRUFBRTtTQUNuQixDQUFDO1FBQ0YsTUFBTSxHQUFHLEdBQUcsTUFBTSxNQUFNLENBQUMsVUFBVSxDQUFDLE1BQU0sQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1FBQzdELElBQUksR0FBRyxFQUFFLElBQUksRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLFNBQVMsRUFBRSxDQUFDO1lBQzlCLE9BQU8sR0FBRyxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUM7UUFDL0IsQ0FBQzthQUFNLENBQUM7WUFD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QUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUM3SCxDQUFDO1FBQ0osQ0FBQztRQUNELE1BQU0sSUFBSSxLQUFLLENBQ2IsK0NBQStDLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FDL0QsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHtcbiAgT1BFTkFJX0FQSV9LRVksXG4gIE9QRU5BSV9FTUJFRERJTkdfTU9ERUwsXG4gIERFRkFVTFRfU0VBUkNIX0xJTUlULFxuICBIQVNVUkFfR1JBUEhRTF9VUkwsXG4gIC8vIEhBU1VSQV9BRE1JTl9TRUNSRVQgaXMgcGFzc2VkIGFzIGFuIGFyZ3VtZW50IGZvciBzZWN1cml0eVxufSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBnZXRFdmVudFRhYmxlIH0gZnJvbSAnLi9sYW5jZWRiX2Nvbm5lY3QnO1xuaW1wb3J0IHsgRXZlbnRSZWNvcmQsIENhdGVnb3J5VHlwZSB9IGZyb20gJy4vdHlwZXMnOyAvLyBBZGRlZCBDYXRlZ29yeVR5cGVcblxuLy8gSW5pdGlhbGl6ZSBPcGVuQUkgY2xpZW50XG5jb25zdCBvcGVuYWkgPSBuZXcgT3BlbkFJKHtcbiAgYXBpS2V5OiBPUEVOQUlfQVBJX0tFWSwgLy8gVGhpcyBtaWdodCBiZSBiZXR0ZXIgaW5pdGlhbGl6ZWQgcGVyLWNhbGwgaWYga2V5IGNhbiBjaGFuZ2Vcbn0pO1xuXG4vKipcbiAqIENvbnZlcnRzIGEgZ2l2ZW4gdGV4dCBzdHJpbmcgaW50byBhIHZlY3RvciBlbWJlZGRpbmcgdXNpbmcgT3BlbkFJIEFQSS5cbiAqIEBwYXJhbSB0ZXh0IFRoZSB0ZXh0IHRvIGNvbnZlcnQuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byB0aGUgdmVjdG9yIGVtYmVkZGluZy5cbiAqIEB0aHJvd3MgRXJyb3IgaWYgdGhlIGNvbnZlcnNpb24gZmFpbHMuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjb252ZXJ0VGV4dFRvVmVjdG9yKHRleHQ6IHN0cmluZyk6IFByb21pc2U8bnVtYmVyW10+IHtcbiAgaWYgKCF0ZXh0IHx8IHRleHQudHJpbSgpID09PSAnJykge1xuICAgIHRocm93IG5ldyBFcnJvcignSW5wdXQgdGV4dCBjYW5ub3QgYmUgZW1wdHkuJyk7XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBlbWJlZGRpbmdSZXF1ZXN0OiBPcGVuQUkuRW1iZWRkaW5ncy5FbWJlZGRpbmdDcmVhdGVQYXJhbXMgPSB7XG4gICAgICBtb2RlbDogT1BFTkFJX0VNQkVERElOR19NT0RFTCxcbiAgICAgIGlucHV0OiB0ZXh0LnRyaW0oKSxcbiAgICB9O1xuICAgIGNvbnN0IHJlcyA9IGF3YWl0IG9wZW5haS5lbWJlZGRpbmdzLmNyZWF0ZShlbWJlZGRpbmdSZXF1ZXN0KTtcbiAgICBpZiAocmVzPy5kYXRhPy5bMF0/LmVtYmVkZGluZykge1xuICAgICAgcmV0dXJuIHJlcy5kYXRhWzBdLmVtYmVkZGluZztcbiAgICB9IGVsc2Uge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnRmFpbGVkIHRvIGdlbmVyYXRlIGVtYmVkZGluZyBmcm9tIE9wZW5BSTogTm8gZW1iZWRkaW5nIGRhdGEgcmV0dXJuZWQuJ1xuICAgICAgKTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgY29udmVydGluZyB0ZXh0IHRvIE9wZW5BSSB2ZWN0b3I6JywgZXJyb3IpO1xuICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgIGBPcGVuQUkgQVBJIGVycm9yIGR1cmluZyB2ZWN0b3IgY29udmVyc2lvbjogJHtlcnJvci5tZXNzYWdlfWBcbiAgICApO1xuICB9XG59XG5cbi8qKlxuICogU2VhcmNoZXMgZm9yIGV2ZW50cyBpbiBMYW5jZURCIGJhc2VkIG9uIGEgc2VhcmNoIHZlY3RvciBhbmQgb3RoZXIgY3JpdGVyaWEuXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlciB3aG9zZSBldmVudHMgdG8gc2VhcmNoLlxuICogQHBhcmFtIHNlYXJjaFZlY3RvciBUaGUgdmVjdG9yIGVtYmVkZGluZyBvZiB0aGUgc2VhcmNoIHF1ZXJ5LlxuICogQHBhcmFtIHN0YXJ0RGF0ZSBPcHRpb25hbCBzdGFydCBkYXRlIGZvciBmaWx0ZXJpbmcgZXZlbnRzIChJU08gODYwMSkuXG4gKiBAcGFyYW0gZW5kRGF0ZSBPcHRpb25hbCBlbmQgZGF0ZSBmb3IgZmlsdGVyaW5nIGV2ZW50cyAoSVNPIDg2MDEpLlxuICogQHBhcmFtIGxpbWl0IE9wdGlvbmFsIGxpbWl0IGZvciB0aGUgbnVtYmVyIG9mIHJlc3VsdHMuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhbiBhcnJheSBvZiBtYXRjaGluZyBldmVudCByZWNvcmRzLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VhcmNoRXZlbnRzSW5MYW5jZURCKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgc2VhcmNoVmVjdG9yOiBudW1iZXJbXSxcbiAgc3RhcnREYXRlPzogc3RyaW5nLFxuICBlbmREYXRlPzogc3RyaW5nLFxuICBsaW1pdDogbnVtYmVyID0gREVGQVVMVF9TRUFSQ0hfTElNSVRcbik6IFByb21pc2U8RXZlbnRSZWNvcmRbXT4ge1xuICBpZiAoIXVzZXJJZCkge1xuICAgIHRocm93IG5ldyBFcnJvcignVXNlciBJRCBtdXN0IGJlIHByb3ZpZGVkIGZvciBzZWFyY2hpbmcgZXZlbnRzLicpO1xuICB9XG4gIGlmICghc2VhcmNoVmVjdG9yIHx8IHNlYXJjaFZlY3Rvci5sZW5ndGggPT09IDApIHtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ1NlYXJjaCB2ZWN0b3IgbXVzdCBiZSBwcm92aWRlZC4nKTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgdGFibGUgPSBhd2FpdCBnZXRFdmVudFRhYmxlKCk7XG4gICAgbGV0IHF1ZXJ5ID0gdGFibGVcbiAgICAgIC5zZWFyY2goc2VhcmNoVmVjdG9yKVxuICAgICAgLndoZXJlKGB1c2VySWQgPSAnJHt1c2VySWQucmVwbGFjZSgvJy9nLCBcIicnXCIpfSdgKTsgLy8gRXNjYXBlIHNpbmdsZSBxdW90ZXMgaW4gdXNlcklkXG5cbiAgICBsZXQgZGF0ZUZpbHRlciA9ICcnO1xuICAgIGlmIChzdGFydERhdGUpIHtcbiAgICAgIC8vIEJhc2ljIHZhbGlkYXRpb24gZm9yIGRhdGUgZm9ybWF0IGNhbiBiZSBhZGRlZCBoZXJlIGlmIG5lZWRlZFxuICAgICAgZGF0ZUZpbHRlciArPSBgc3RhcnRfZGF0ZSA+PSAnJHtzdGFydERhdGUucmVwbGFjZSgvJy9nLCBcIicnXCIpfSdgO1xuICAgIH1cbiAgICBpZiAoZW5kRGF0ZSkge1xuICAgICAgLy8gQmFzaWMgdmFsaWRhdGlvbiBmb3IgZGF0ZSBmb3JtYXQgY2FuIGJlIGFkZGVkIGhlcmUgaWYgbmVlZGVkXG4gICAgICBpZiAoZGF0ZUZpbHRlcikgZGF0ZUZpbHRlciArPSAnIEFORCAnO1xuICAgICAgZGF0ZUZpbHRlciArPSBgZW5kX2RhdGUgPD0gJyR7ZW5kRGF0ZS5yZXBsYWNlKC8nL2csIFwiJydcIil9J2A7XG4gICAgfVxuXG4gICAgaWYgKGRhdGVGaWx0ZXIpIHtcbiAgICAgIHF1ZXJ5ID0gcXVlcnkud2hlcmUoZGF0ZUZpbHRlcik7XG4gICAgfVxuXG4gICAgcXVlcnkgPSBxdWVyeS5saW1pdChsaW1pdCk7XG5cbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgcXVlcnkuZXhlY3V0ZTxFdmVudFJlY29yZD4oKTtcbiAgICAvLyBUaGUgcmVzdWx0cyBmcm9tIExhbmNlREIgbWlnaHQgYmUgdHlwZWQgbW9yZSBnZW5lcmljYWxseSBieSB0aGUgbGlicmFyeS5cbiAgICAvLyBXZSBjYXN0IHRvIEV2ZW50UmVjb3JkW10gYmFzZWQgb24gb3VyIHNjaGVtYS5cbiAgICByZXR1cm4gcmVzdWx0cyBhcyBFdmVudFJlY29yZFtdO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIHNlYXJjaGluZyBldmVudHMgaW4gTGFuY2VEQjonLCBlcnJvcik7XG4gICAgLy8gTG9nIHNwZWNpZmljIExhbmNlREIgZXJyb3JzIGlmIHBvc3NpYmxlXG4gICAgdGhyb3cgbmV3IEVycm9yKGBMYW5jZURCIHNlYXJjaCBmYWlsZWQ6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgfVxufVxuXG4vKipcbiAqIEZldGNoZXMgdXNlciBjYXRlZ29yaWVzIGZyb20gSGFzdXJhLlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIgd2hvc2UgY2F0ZWdvcmllcyB0byBmZXRjaC5cbiAqIEBwYXJhbSBoYXN1cmFBZG1pblNlY3JldCBUaGUgSGFzdXJhIGFkbWluIHNlY3JldCBmb3IgYXV0aGVudGljYXRpb24uXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhbiBhcnJheSBvZiBDYXRlZ29yeVR5cGUgb2JqZWN0cy5cbiAqIEB0aHJvd3MgRXJyb3IgaWYgdGhlIGZldGNoaW5nIGZhaWxzLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0VXNlckNhdGVnb3JpZXMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBoYXN1cmFBZG1pblNlY3JldDogc3RyaW5nXG4pOiBQcm9taXNlPENhdGVnb3J5VHlwZVtdPiB7XG4gIGlmICghdXNlcklkKSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKCdVc2VyIElEIG11c3QgYmUgcHJvdmlkZWQgZm9yIGZldGNoaW5nIGNhdGVnb3JpZXMuJyk7XG4gIH1cbiAgaWYgKCFoYXN1cmFBZG1pblNlY3JldCkge1xuICAgIHRocm93IG5ldyBFcnJvcignSGFzdXJhIGFkbWluIHNlY3JldCBtdXN0IGJlIHByb3ZpZGVkLicpO1xuICB9XG5cbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgR2V0VXNlckNhdGVnb3JpZXMoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgIENhdGVnb3J5KHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZGVsZXRlZDoge19lcTogZmFsc2V9fSkge1xuICAgICAgICBpZFxuICAgICAgICBuYW1lXG4gICAgICAgICMgZGVzY3JpcHRpb24gIyBVbmNvbW1lbnQgaWYgeW91ciBDYXRlZ29yeVR5cGUgYW5kIEFJIHByb21wdCBjYW4gdXNlIGl0XG4gICAgICB9XG4gICAgfVxuICBgO1xuXG4gIGNvbnN0IHZhcmlhYmxlcyA9IHsgdXNlcklkIH07XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdC5wb3N0KEhBU1VSQV9HUkFQSFFMX1VSTCwge1xuICAgICAganNvbjoge1xuICAgICAgICBxdWVyeSxcbiAgICAgICAgdmFyaWFibGVzLFxuICAgICAgfSxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgJ3gtaGFzdXJhLWFkbWluLXNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICAgIHJlc3BvbnNlVHlwZTogJ2pzb24nLFxuICAgIH0pO1xuXG4gICAgLy8gVHlwZSBhc3NlcnRpb24gZm9yIHRoZSBib2R5XG4gICAgY29uc3QgYm9keSA9IHJlc3BvbnNlLmJvZHkgYXMge1xuICAgICAgZGF0YT86IHsgQ2F0ZWdvcnk/OiBDYXRlZ29yeVR5cGVbXSB9O1xuICAgICAgZXJyb3JzPzogYW55W107XG4gICAgfTtcblxuICAgIGlmIChib2R5LmVycm9ycykge1xuICAgICAgY29uc29sZS5lcnJvcignSGFzdXJhIGVycm9yczonLCBib2R5LmVycm9ycyk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBFcnJvciBmZXRjaGluZyBjYXRlZ29yaWVzIGZyb20gSGFzdXJhOiAke2JvZHkuZXJyb3JzLm1hcCgoZTogYW55KSA9PiBlLm1lc3NhZ2UpLmpvaW4oJywgJyl9YFxuICAgICAgKTtcbiAgICB9XG5cbiAgICByZXR1cm4gYm9keS5kYXRhPy5DYXRlZ29yeSB8fCBbXTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ0Vycm9yIGR1cmluZyBnZXRVc2VyQ2F0ZWdvcmllczonLFxuICAgICAgZXJyb3IucmVzcG9uc2UgPyBlcnJvci5yZXNwb25zZS5ib2R5IDogZXJyb3IubWVzc2FnZVxuICAgICk7XG4gICAgLy8gQ2hlY2sgaWYgaXQncyBhIGdvdCBIVFRQRXJyb3IgdG8gZ2V0IG1vcmUgZGV0YWlsc1xuICAgIGlmIChlcnJvci5uYW1lID09PSAnSFRUUEVycm9yJyAmJiBlcnJvci5yZXNwb25zZSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICBgRmFpbGVkIHRvIGZldGNoIGNhdGVnb3JpZXMgZnJvbSBIYXN1cmEuIFN0YXR1czogJHtlcnJvci5yZXNwb25zZS5zdGF0dXNDb2RlfSwgQm9keTogJHtKU09OLnN0cmluZ2lmeShlcnJvci5yZXNwb25zZS5ib2R5KX1gXG4gICAgICApO1xuICAgIH1cbiAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICBgTmV0d29yayBvciBvdGhlciBlcnJvciBmZXRjaGluZyBjYXRlZ29yaWVzOiAke2Vycm9yLm1lc3NhZ2V9YFxuICAgICk7XG4gIH1cbn1cbiJdfQ==
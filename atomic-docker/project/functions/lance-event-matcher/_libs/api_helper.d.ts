import { EventRecord, CategoryType } from './types';
/**
 * Converts a given text string into a vector embedding using OpenAI API.
 * @param text The text to convert.
 * @returns A promise that resolves to the vector embedding.
 * @throws Error if the conversion fails.
 */
export declare function convertTextToVector(text: string): Promise<number[]>;
/**
 * Searches for events in LanceDB based on a search vector and other criteria.
 * @param userId The ID of the user whose events to search.
 * @param searchVector The vector embedding of the search query.
 * @param startDate Optional start date for filtering events (ISO 8601).
 * @param endDate Optional end date for filtering events (ISO 8601).
 * @param limit Optional limit for the number of results.
 * @returns A promise that resolves to an array of matching event records.
 */
export declare function searchEventsInLanceDB(userId: string, searchVector: number[], startDate?: string, endDate?: string, limit?: number): Promise<EventRecord[]>;
/**
 * Fetches user categories from Hasura.
 * @param userId The ID of the user whose categories to fetch.
 * @param hasuraAdminSecret The Hasura admin secret for authentication.
 * @returns A promise that resolves to an array of CategoryType objects.
 * @throws Error if the fetching fails.
 */
export declare function getUserCategories(userId: string, hasuraAdminSecret: string): Promise<CategoryType[]>;

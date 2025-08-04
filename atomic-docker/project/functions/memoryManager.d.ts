import * as lancedb from '@lancedb/lancedb';
import type { ConversationState } from './conversationState';
/**
 * Placeholder for generating embeddings.
 * In a real implementation, this would call an actual embedding model.
 * @param text The text to embed.
 * @returns A promise that resolves to a vector (array of numbers) or null if an error occurs.
 */
export declare function generateEmbedding(text: string): Promise<number[] | null>;
export interface LtmQueryResult {
    id: string;
    text: string;
    score: number;
    metadata?: Record<string, any>;
    table: string;
}
/**
 * Processes Short-Term Memory (STM) and decides what to store in Long-Term Memory (LTM).
 * If successful, resolves the promise. If a critical error occurs during LTM storage (e.g., DB error),
 * the promise is rejected. Failure to generate an embedding logs an error but does not cause a rejection.
 * @param userId The ID of the user.
 * @param conversation The current conversation state.
 * @param db The LanceDB connection object.
 * @returns A promise that resolves if processing is successful or if embedding fails (with logged error),
 *          and rejects if there's a critical error during LTM storage.
 */
export declare function processSTMToLTM(userId: string, conversation: ConversationState, db: lancedb.Connection): Promise<void>;
/**
 * Retrieves relevant information from Long-Term Memory (LTM) based on a query.
 * Supports basic keyword filtering and optional recency boosting for results.
 * @param queryText The query text to search for.
 * @param userId The ID of the user, for context (can be null if not user-specific).
 * @param db The LanceDB connection object.
 * @param options Optional parameters to control retrieval:
 *   @param table - The LTM table to search (default: 'knowledge_base').
 *   @param topK - The number of results to return (default: 5).
 *   @param keywords - An array of keywords to filter by (uses LIKE '%keyword%'). Applied alongside vector search.
 *                     Primarily effective on 'text_content' (knowledge_base) or 'summary' (research_findings).
 *   @param boostRecency - If true, re-ranks results to balance similarity and recency (default: false).
 *   @param recencyWeight - Weight for recency score during re-ranking (0 to 1, default: 0.3). Only if boostRecency is true.
 *   @param similarityWeight - Weight for similarity score during re-ranking (0 to 1, default: 0.7). Only if boostRecency is true.
 * @returns A promise that resolves to an array of LTM query results, sorted by relevance.
 */
export declare function retrieveRelevantLTM(queryText: string, userId: string | null, db: lancedb.Connection, options?: {
    table?: string;
    topK?: number;
    keywords?: string[];
    boostRecency?: boolean;
    recencyWeight?: number;
    similarityWeight?: number;
}): Promise<LtmQueryResult[]>;
export interface ConversationStateActions {
    updateUserGoal: (goal: string | null) => void;
    updateIntentAndEntities: (intent: string | null, entities: Record<string, any> | null) => void;
    updateLtmRepoContext: (context: LtmQueryResult[] | null) => void;
}
/**
 * Loads retrieved LTM results into the Short-Term Memory (STM) or conversation state.
 * @param results The LTM query results to load.
 * @param conversationStateActions An object containing functions to update the conversation state.
 */
export declare function loadLTMToSTM(results: LtmQueryResult[], conversationStateActions: ConversationStateActions): Promise<void>;

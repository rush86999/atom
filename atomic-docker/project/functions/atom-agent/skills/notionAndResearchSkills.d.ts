import { SkillResponse, InitiateResearchData, ProcessResearchQueueData, CreateNoteData, NotionSimilarNoteResult, // Added this missing type
CreateNotionTaskParams, QueryNotionTasksParams, TaskQueryResponse, // Used directly by queryNotionTasks
UpdateNotionTaskParams, CreateTaskData, // For SkillResponse<CreateTaskData>
UpdateTaskData, // For TaskQueryResponse.tasks and PythonApiResponse<NotionTask[]>
NotionPageSummary } from '../types';
export declare function initiateResearch(userId: string, topic: string): Promise<SkillResponse<InitiateResearchData>>;
import { HybridSearchOptions } from '../../../src/skills/lanceDbStorageSkills';
import { HybridSearchResultItem } from '../types';
/**
 * Orchestrates a search by first parsing the raw query with an NLU LLM,
 * then executing a hybrid search with the parsed term and filters.
 * @param userId The ID of the user performing the search.
 * @param rawQuery The user's natural language search query.
 * @param options Optional limits for the search.
 * @returns A promise that resolves to a SkillResponse containing hybrid search results.
 */
export declare function performHybridSearchWithNLU(userId: string, rawQuery: string, options?: Omit<HybridSearchOptions, 'filters'>): Promise<SkillResponse<HybridSearchResultItem[]>>;
export declare function createNotionTask(userId: string, params: CreateNotionTaskParams, integrations: any): Promise<SkillResponse<CreateTaskData>>;
export declare function queryNotionTasks(userId: string, params: QueryNotionTasksParams): Promise<TaskQueryResponse>;
export declare function updateNotionTask(userId: string, params: UpdateNotionTaskParams): Promise<SkillResponse<UpdateTaskData>>;
/**
 * Searches for Notion notes similar to a given query text using vector similarity.
 *
 * @param userId The ID of the user performing the search (to scope results).
 * @param queryText The natural language text to search for.
 * @param limit Optional. The maximum number of similar notes to return.
 * @returns A promise that resolves to a SkillResponse containing an array of similar Notion notes.
 */
export declare function searchSimilarNotionNotes(userId: string, queryText: string, limit?: number): Promise<SkillResponse<NotionSimilarNoteResult[]>>;
export declare function processResearchQueue(userId: string): Promise<SkillResponse<ProcessResearchQueueData>>;
/**
 * Placeholder for fetching detailed summary of a specific Notion page by its ID.
 * This would call a Python backend endpoint (e.g., /get-notion-page-summary).
 * The Python backend would use Notion API to get page details and format them.
 * @param userId The ID of the user.
 * @param pageId The ID of the Notion page.
 * @returns A promise that resolves to a SkillResponse containing the NotionPageSummary.
 */
export declare function getNotionPageSummaryById(userId: string, pageId: string): Promise<SkillResponse<NotionPageSummary>>;
export declare function createNotionNote(userId: string, // For potential logging or if Python service uses it
title: string, content: string, notionDbId?: string): Promise<SkillResponse<CreateNoteData>>;
export declare function createAudioNoteFromUrl(userId: string, audioUrl: string, title: string, notionDbId?: string, notionSource?: string, linkedEventId?: string): Promise<SkillResponse<CreateNoteData>>;
export declare function searchNotionNotes(userId: string, // For context/logging
queryText: string, notionDbId?: string, source?: string): Promise<SkillResponse<NotionPageSummary[]>>;

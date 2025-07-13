import axios, { AxiosError } from 'axios';
import {
  GmailMessageSnippet,
  NotionPageSummary,
  SkillResponse,
  SkillError,
} from '../../atomic-docker/project/functions/atom-agent/types'; // Adjust path as needed
import { PYTHON_API_SERVICE_BASE_URL } from '../../atomic-docker/project/functions/atom-agent/_libs/constants'; // Assuming this hosts the new endpoints
import { logger } from '../../atomic-docker/project/functions/_utils/logger';

const LANCE_DB_STORAGE_API_TIMEOUT = 15000; // 15 seconds timeout for these specific calls

// Helper to construct SkillResponse from axios errors
function handleAxiosError(error: AxiosError, operationName: string): SkillResponse<null> {
  if (error.response) {
    logger.error(`[${operationName}] Error: ${error.response.status}`, error.response.data);
    const errData = error.response.data as any;
    return {
      ok: false,
      error: {
        code: errData?.error?.code || `HTTP_${error.response.status}`,
        message: errData?.error?.message || `Failed to ${operationName}. Status: ${error.response.status}`,
        details: errData?.error?.details || errData,
      },
    };
  } else if (error.request) {
    logger.error(`[${operationName}] Error: No response received`, error.request);
    return {
      ok: false,
      error: { code: 'NETWORK_ERROR', message: `No response received for ${operationName}.` },
    };
  } else {
    logger.error(`[${operationName}] Error: ${error.message}`);
    return {
      ok: false,
      error: { code: 'REQUEST_SETUP_ERROR', message: `Error setting up request for ${operationName}: ${error.message}` },
    };
  }
}

export async function storeEmailSnippetInLanceDb(
  userId: string,
  email: GmailMessageSnippet,
): Promise<SkillResponse<{ email_id: string; message: string } | null >> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured.";
    logger.error(`[storeEmailSnippetInLanceDb] ${errorMsg}`);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  if (!email || !email.id) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Valid email object with id is required.'}};


  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/lancedb/store-email-snippet`;
  const payload = {
    user_id: userId,
    email_data: email, // This matches the Python endpoint's expected 'email_data' key
  };

  logger.info(`[storeEmailSnippetInLanceDb] Storing email snippet for user ${userId}, email ID ${email.id}`);

  try {
    const response = await axios.post(endpoint, payload, { timeout: LANCE_DB_STORAGE_API_TIMEOUT });
    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[storeEmailSnippetInLanceDb] Successfully stored email snippet ID ${response.data.data.email_id}`);
      return { ok: true, data: response.data.data };
    } else {
      logger.warn(`[storeEmailSnippetInLanceDb] Failed to store email snippet. API ok: ${response.data?.ok}`, response.data?.error);
      return {
        ok: false,
        error: {
          code: response.data?.error?.code || 'PYTHON_API_ERROR',
          message: response.data?.error?.message || 'Failed to store email snippet via Python API.' ,
          details: response.data?.error?.details
        }
      };
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'storeEmailSnippetInLanceDb');
  }
}

export async function storeNotionPageSummaryInLanceDb(
  userId: string,
  page: NotionPageSummary,
): Promise<SkillResponse<{ notion_page_id: string; message: string } | null >> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured.";
    logger.error(`[storeNotionPageSummaryInLanceDb] ${errorMsg}`);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  if (!page || !page.id) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Valid Notion page object with id is required.'}};


  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/lancedb/store-notion-summary`;
  const payload = {
    user_id: userId,
    page_data: page, // Matches Python endpoint's 'page_data'
  };
  logger.info(`[storeNotionPageSummaryInLanceDb] Storing Notion page summary for user ${userId}, page ID ${page.id}`);

  try {
    const response = await axios.post(endpoint, payload, { timeout: LANCE_DB_STORAGE_API_TIMEOUT });
    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[storeNotionPageSummaryInLanceDb] Successfully stored Notion page summary ID ${response.data.data.notion_page_id}`);
      return { ok: true, data: response.data.data };
    } else {
      logger.warn(`[storeNotionPageSummaryInLanceDb] Failed to store Notion page summary. API ok: ${response.data?.ok}`, response.data?.error);
      return {
        ok: false,
        error: {
          code: response.data?.error?.code || 'PYTHON_API_ERROR',
          message: response.data?.error?.message || 'Failed to store Notion page summary via Python API.' ,
          details: response.data?.error?.details
        }
      };
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'storeNotionPageSummaryInLanceDb');
  }
}

import * as fs from 'fs'; // For reading file content
import * as path from 'path'; // For getting filename from path

export async function processAndStoreDocument(
  userId: string,
  filePath: string, // Changed from file: File
  docType: string, // e.g., 'pdf', 'docx'
  title?: string,
  sourceUri?: string, // Optional: original URI if not just filename (could be same as filePath)
): Promise<SkillResponse<{ doc_id: string; num_chunks_stored: number } | null>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured for document processing.";
    logger.error(`[processAndStoreDocument] ${errorMsg}`);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  if (!filePath) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'filePath is required.'}};
  if (!fs.existsSync(filePath)) {
    logger.error(`[processAndStoreDocument] File not found at path: ${filePath}`);
    return { ok: false, error: {code: 'FILE_NOT_FOUND', message: `File not found at path: ${filePath}`}};
  }

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/ingest-document`;
  let fileBuffer: Buffer;
  try {
    fileBuffer = fs.readFileSync(filePath);
  } catch (readError: any) {
    logger.error(`[processAndStoreDocument] Error reading file ${filePath}: ${readError.message}`);
    return {ok: false, error: {code: 'FILE_READ_ERROR', message: `Error reading file: ${readError.message}`}};
  }

  const formData = new FormData();
  const fileName = path.basename(filePath);
  formData.append('file', fileBuffer, fileName); // Send buffer with filename
  formData.append('user_id', userId);
  formData.append('doc_type', docType);

  const effectiveTitle = title || fileName;
  formData.append('title', effectiveTitle);

  const effectiveSourceUri = sourceUri || filePath; // Use filePath as sourceUri if not otherwise provided
  formData.append('source_uri', effectiveSourceUri);

  // Note: openai_api_key could be passed here if needed by backend per user/request
  // formData.append('openai_api_key', 'USER_SPECIFIC_KEY_IF_ANY');

  logger.info(`[processAndStoreDocument] Uploading document ${fileName} (from path ${filePath}) for user ${userId}, type ${docType}, title ${effectiveTitle}, sourceUri ${effectiveSourceUri}`);

  try {
    const response = await axios.post(endpoint, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 180000, // 3 minutes timeout for potentially large file processing & embedding
    });

    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[processAndStoreDocument] Successfully processed and initiated storage for document ID ${response.data.data.doc_id}`);
      return { ok: true, data: response.data.data };
    } else {
      logger.warn(`[processAndStoreDocument] Failed to process document. API ok: ${response.data?.ok}`, response.data?.error);
      return {
        ok: false,
        error: {
          code: response.data?.error?.code || 'PYTHON_API_ERROR',
          message: response.data?.error?.message || 'Failed to process document via Python API.' ,
          details: response.data?.error?.details
        }
      };
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'processAndStoreDocument');
  }
}

// --- Semantic Search Functionality ---

export interface SemanticSearchFilters {
  date_after?: string; // ISO 8601 string
  date_before?: string; // ISO 8601 string
  source_types?: SearchResultSourceType[]; // Use SearchResultSourceType from types.ts
  doc_type_filter?: string; // e.g., "pdf", "docx" - specific to document_chunk source_type
  // Add other potential filters as the backend evolves
}

// Ensure UniversalSearchResultItem is imported from types.ts
import { UniversalSearchResultItem, SearchResultSourceType, HybridSearchResultItem, HybridSearchFilters } from '../../atomic-docker/project/functions/atom-agent/types';

export interface HybridSearchOptions {
  semanticLimit?: number;
  keywordLimit?: number;
  filters?: HybridSearchFilters; // Use the new specific filter type
}

export async function hybridSearch(
  userId: string,
  queryText: string,
  options: HybridSearchOptions = {},
): Promise<SkillResponse<HybridSearchResultItem[]>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured for hybrid search.";
    logger.error(`[hybridSearch] ${errorMsg}`);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  if (!queryText || queryText.trim() === "") return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'queryText cannot be empty.'}};

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/search/hybrid`;
  const payload = {
    user_id: userId,
    query_text: queryText,
    limit_semantic: options.semanticLimit,
    limit_keyword: options.keywordLimit,
    filters: options.filters || {},
  };

  logger.info(`[hybridSearch] Performing hybrid search for user ${userId} with query "${queryText.substring(0, 50)}..."`);

  try {
    // Note: The response data should be `HybridSearchResultItem[]`
    const response = await axios.post<SkillResponse<HybridSearchResultItem[]>>(endpoint, payload, {
      timeout: LANCE_DB_STORAGE_API_TIMEOUT * 2.5 // Give hybrid search a bit more time
    });

    if (response.data && response.data.ok && Array.isArray(response.data.data)) {
      logger.info(`[hybridSearch] Successfully received ${response.data.data.length} hybrid search results.`);
      return { ok: true, data: response.data.data };
    } else if (response.data && !response.data.ok && response.data.error) {
        logger.warn(`[hybridSearch] Hybrid search failed. API ok:false`, response.data.error);
        return { ok: false, error: response.data.error };
    } else {
        logger.warn(`[hybridSearch] Unexpected response structure from hybrid search API.`, response.data);
        return {
            ok: false,
            error: {
              code: 'PYTHON_API_UNEXPECTED_RESPONSE',
              message: 'Unexpected response structure from Python hybrid search API.' ,
              details: response.data
            }
        };
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'hybridSearch');
  }
}


export async function semanticSearchLanceDb(
  userId: string,
  queryText: string,
  filters?: SemanticSearchFilters,
  limit: number = 10,
): Promise<SkillResponse<UniversalSearchResultItem[]>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured for semantic search.";
    logger.error(`[semanticSearchLanceDb] ${errorMsg}`);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  if (!queryText || queryText.trim() === "") return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'queryText cannot be empty.'}};

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/lancedb/semantic-search`;
  const payload = {
    user_id: userId,
    query_text: queryText,
    filters: filters || {}, // Send empty object if no filters
    limit: limit,
  };

  logger.info(`[semanticSearchLanceDb] Performing semantic search for user ${userId} with query "${queryText.substring(0, 50)}..."`);

  try {
    const response = await axios.post<SkillResponse<UniversalSearchResultItem[]>>(endpoint, payload, {
      timeout: LANCE_DB_STORAGE_API_TIMEOUT * 2 // Search might take longer
    });
    // Assuming Python endpoint directly returns SkillResponse-like structure with "ok" and "data" or "error"
    if (response.data && response.data.ok && response.data.data) {
      logger.info(`[semanticSearchLanceDb] Successfully received ${response.data.data.length} search results.`);
      return { ok: true, data: response.data.data };
    } else if (response.data && !response.data.ok && response.data.error) { // Python returned ok:false
        logger.warn(`[semanticSearchLanceDb] Semantic search failed. API ok:false`, response.data.error);
        return { ok: false, error: response.data.error };
    } else { // Unexpected response structure from Python
        logger.warn(`[semanticSearchLanceDb] Unexpected response structure from semantic search API.`, response.data);
        return {
            ok: false,
            error: {
              code: 'PYTHON_API_UNEXPECTED_RESPONSE',
              message: 'Unexpected response structure from Python semantic search API.' ,
              details: response.data
            }
        };
    }
  } catch (error) {
    return handleAxiosError(error as AxiosError, 'semanticSearchLanceDb');
  }
}
```

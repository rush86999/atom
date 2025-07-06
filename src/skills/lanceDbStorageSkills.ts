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

export async function processAndStoreDocument(
  userId: string,
  file: File, // Using browser File object type for conceptual client-side usage
  docType: string, // e.g., 'pdf', 'docx'
  title?: string,
  sourceUri?: string, // Optional: original URI if not just filename
): Promise<SkillResponse<{ doc_id: string; num_chunks_stored: number } | null>> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured for document processing.";
    logger.error(`[processAndStoreDocument] ${errorMsg}`);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }
  if (!userId) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.'}};
  if (!file) return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'File object is required.'}};

  const endpoint = `${PYTHON_API_SERVICE_BASE_URL}/api/ingest-document`;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('user_id', userId);
  formData.append('doc_type', docType);
  if (title) formData.append('title', title);
  if (sourceUri) formData.append('source_uri', sourceUri);
  // Note: openai_api_key could be passed here if needed by backend per user/request
  // formData.append('openai_api_key', 'USER_SPECIFIC_KEY_IF_ANY');


  logger.info(`[processAndStoreDocument] Uploading document ${file.name} for user ${userId}, type ${docType}`);

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
```

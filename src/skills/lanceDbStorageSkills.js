"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.storeEmailSnippetInLanceDb = storeEmailSnippetInLanceDb;
exports.storeNotionPageSummaryInLanceDb = storeNotionPageSummaryInLanceDb;
exports.processAndStoreDocument = processAndStoreDocument;
exports.hybridSearch = hybridSearch;
exports.semanticSearchLanceDb = semanticSearchLanceDb;
const axios_1 = __importDefault(require("axios"));
const constants_1 = require("../../atomic-docker/project/functions/atom-agent/_libs/constants"); // Assuming this hosts the new endpoints
const logger_1 = require("../../atomic-docker/project/functions/_utils/logger");
const LANCE_DB_STORAGE_API_TIMEOUT = 15000; // 15 seconds timeout for these specific calls
// Helper to construct SkillResponse from axios errors
function handleAxiosError(error, operationName) {
    if (error.response) {
        logger_1.logger.error(`[${operationName}] Error: ${error.response.status}`, error.response.data);
        const errData = error.response.data;
        return {
            ok: false,
            error: {
                code: errData?.error?.code || `HTTP_${error.response.status}`,
                message: errData?.error?.message || `Failed to ${operationName}. Status: ${error.response.status}`,
                details: errData?.error?.details || errData,
            },
        };
    }
    else if (error.request) {
        logger_1.logger.error(`[${operationName}] Error: No response received`, error.request);
        return {
            ok: false,
            error: { code: 'NETWORK_ERROR', message: `No response received for ${operationName}.` },
        };
    }
    else {
        logger_1.logger.error(`[${operationName}] Error: ${error.message}`);
        return {
            ok: false,
            error: { code: 'REQUEST_SETUP_ERROR', message: `Error setting up request for ${operationName}: ${error.message}` },
        };
    }
}
async function storeEmailSnippetInLanceDb(userId, email) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured.";
        logger_1.logger.error(`[storeEmailSnippetInLanceDb] ${errorMsg}`);
        return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
    }
    if (!userId)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' } };
    if (!email || !email.id)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Valid email object with id is required.' } };
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/lancedb/store-email-snippet`;
    const payload = {
        user_id: userId,
        email_data: email, // This matches the Python endpoint's expected 'email_data' key
    };
    logger_1.logger.info(`[storeEmailSnippetInLanceDb] Storing email snippet for user ${userId}, email ID ${email.id}`);
    try {
        const response = await axios_1.default.post(endpoint, payload, { timeout: LANCE_DB_STORAGE_API_TIMEOUT });
        if (response.data && response.data.ok && response.data.data) {
            logger_1.logger.info(`[storeEmailSnippetInLanceDb] Successfully stored email snippet ID ${response.data.data.email_id}`);
            return { ok: true, data: response.data.data };
        }
        else {
            logger_1.logger.warn(`[storeEmailSnippetInLanceDb] Failed to store email snippet. API ok: ${response.data?.ok}`, response.data?.error);
            return {
                ok: false,
                error: {
                    code: response.data?.error?.code || 'PYTHON_API_ERROR',
                    message: response.data?.error?.message || 'Failed to store email snippet via Python API.',
                    details: response.data?.error?.details
                }
            };
        }
    }
    catch (error) {
        return handleAxiosError(error, 'storeEmailSnippetInLanceDb');
    }
}
async function storeNotionPageSummaryInLanceDb(userId, page) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured.";
        logger_1.logger.error(`[storeNotionPageSummaryInLanceDb] ${errorMsg}`);
        return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
    }
    if (!userId)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' } };
    if (!page || !page.id)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Valid Notion page object with id is required.' } };
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/lancedb/store-notion-summary`;
    const payload = {
        user_id: userId,
        page_data: page, // Matches Python endpoint's 'page_data'
    };
    logger_1.logger.info(`[storeNotionPageSummaryInLanceDb] Storing Notion page summary for user ${userId}, page ID ${page.id}`);
    try {
        const response = await axios_1.default.post(endpoint, payload, { timeout: LANCE_DB_STORAGE_API_TIMEOUT });
        if (response.data && response.data.ok && response.data.data) {
            logger_1.logger.info(`[storeNotionPageSummaryInLanceDb] Successfully stored Notion page summary ID ${response.data.data.notion_page_id}`);
            return { ok: true, data: response.data.data };
        }
        else {
            logger_1.logger.warn(`[storeNotionPageSummaryInLanceDb] Failed to store Notion page summary. API ok: ${response.data?.ok}`, response.data?.error);
            return {
                ok: false,
                error: {
                    code: response.data?.error?.code || 'PYTHON_API_ERROR',
                    message: response.data?.error?.message || 'Failed to store Notion page summary via Python API.',
                    details: response.data?.error?.details
                }
            };
        }
    }
    catch (error) {
        return handleAxiosError(error, 'storeNotionPageSummaryInLanceDb');
    }
}
const fs = __importStar(require("fs")); // For reading file content
const path = __importStar(require("path")); // For getting filename from path
async function processAndStoreDocument(userId, filePath, // Changed from file: File
docType, // e.g., 'pdf', 'docx'
title, sourceUri) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured for document processing.";
        logger_1.logger.error(`[processAndStoreDocument] ${errorMsg}`);
        return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
    }
    if (!userId)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' } };
    if (!filePath)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'filePath is required.' } };
    if (!fs.existsSync(filePath)) {
        logger_1.logger.error(`[processAndStoreDocument] File not found at path: ${filePath}`);
        return { ok: false, error: { code: 'FILE_NOT_FOUND', message: `File not found at path: ${filePath}` } };
    }
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/ingest-document`;
    let fileBuffer;
    try {
        fileBuffer = fs.readFileSync(filePath);
    }
    catch (readError) {
        logger_1.logger.error(`[processAndStoreDocument] Error reading file ${filePath}: ${readError.message}`);
        return { ok: false, error: { code: 'FILE_READ_ERROR', message: `Error reading file: ${readError.message}` } };
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
    logger_1.logger.info(`[processAndStoreDocument] Uploading document ${fileName} (from path ${filePath}) for user ${userId}, type ${docType}, title ${effectiveTitle}, sourceUri ${effectiveSourceUri}`);
    try {
        const response = await axios_1.default.post(endpoint, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            timeout: 180000, // 3 minutes timeout for potentially large file processing & embedding
        });
        if (response.data && response.data.ok && response.data.data) {
            logger_1.logger.info(`[processAndStoreDocument] Successfully processed and initiated storage for document ID ${response.data.data.doc_id}`);
            return { ok: true, data: response.data.data };
        }
        else {
            logger_1.logger.warn(`[processAndStoreDocument] Failed to process document. API ok: ${response.data?.ok}`, response.data?.error);
            return {
                ok: false,
                error: {
                    code: response.data?.error?.code || 'PYTHON_API_ERROR',
                    message: response.data?.error?.message || 'Failed to process document via Python API.',
                    details: response.data?.error?.details
                }
            };
        }
    }
    catch (error) {
        return handleAxiosError(error, 'processAndStoreDocument');
    }
}
async function hybridSearch(userId, queryText, options = {}) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured for hybrid search.";
        logger_1.logger.error(`[hybridSearch] ${errorMsg}`);
        return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
    }
    if (!userId)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' } };
    if (!queryText || queryText.trim() === "")
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'queryText cannot be empty.' } };
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/search/hybrid`;
    const payload = {
        user_id: userId,
        query_text: queryText,
        limit_semantic: options.semanticLimit,
        limit_keyword: options.keywordLimit,
        filters: options.filters || {},
    };
    logger_1.logger.info(`[hybridSearch] Performing hybrid search for user ${userId} with query "${queryText.substring(0, 50)}..."`);
    try {
        // Note: The response data should be `HybridSearchResultItem[]`
        const response = await axios_1.default.post(endpoint, payload, {
            timeout: LANCE_DB_STORAGE_API_TIMEOUT * 2.5 // Give hybrid search a bit more time
        });
        if (response.data && response.data.ok && Array.isArray(response.data.data)) {
            logger_1.logger.info(`[hybridSearch] Successfully received ${response.data.data.length} hybrid search results.`);
            return { ok: true, data: response.data.data };
        }
        else if (response.data && !response.data.ok && response.data.error) {
            logger_1.logger.warn(`[hybridSearch] Hybrid search failed. API ok:false`, response.data.error);
            return { ok: false, error: response.data.error };
        }
        else {
            logger_1.logger.warn(`[hybridSearch] Unexpected response structure from hybrid search API.`, response.data);
            return {
                ok: false,
                error: {
                    code: 'PYTHON_API_UNEXPECTED_RESPONSE',
                    message: 'Unexpected response structure from Python hybrid search API.',
                    details: response.data
                }
            };
        }
    }
    catch (error) {
        return handleAxiosError(error, 'hybridSearch');
    }
}
async function semanticSearchLanceDb(userId, queryText, filters, limit = 10) {
    if (!constants_1.PYTHON_API_SERVICE_BASE_URL) {
        const errorMsg = "PYTHON_API_SERVICE_BASE_URL is not configured for semantic search.";
        logger_1.logger.error(`[semanticSearchLanceDb] ${errorMsg}`);
        return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
    }
    if (!userId)
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'userId is required.' } };
    if (!queryText || queryText.trim() === "")
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'queryText cannot be empty.' } };
    const endpoint = `${constants_1.PYTHON_API_SERVICE_BASE_URL}/api/lancedb/semantic-search`;
    const payload = {
        user_id: userId,
        query_text: queryText,
        filters: filters || {}, // Send empty object if no filters
        limit: limit,
    };
    logger_1.logger.info(`[semanticSearchLanceDb] Performing semantic search for user ${userId} with query "${queryText.substring(0, 50)}..."`);
    try {
        const response = await axios_1.default.post(endpoint, payload, {
            timeout: LANCE_DB_STORAGE_API_TIMEOUT * 2 // Search might take longer
        });
        // Assuming Python endpoint directly returns SkillResponse-like structure with "ok" and "data" or "error"
        if (response.data && response.data.ok && response.data.data) {
            logger_1.logger.info(`[semanticSearchLanceDb] Successfully received ${response.data.data.length} search results.`);
            return { ok: true, data: response.data.data };
        }
        else if (response.data && !response.data.ok && response.data.error) { // Python returned ok:false
            logger_1.logger.warn(`[semanticSearchLanceDb] Semantic search failed. API ok:false`, response.data.error);
            return { ok: false, error: response.data.error };
        }
        else { // Unexpected response structure from Python
            logger_1.logger.warn(`[semanticSearchLanceDb] Unexpected response structure from semantic search API.`, response.data);
            return {
                ok: false,
                error: {
                    code: 'PYTHON_API_UNEXPECTED_RESPONSE',
                    message: 'Unexpected response structure from Python semantic search API.',
                    details: response.data
                }
            };
        }
    }
    catch (error) {
        return handleAxiosError(error, 'semanticSearchLanceDb');
    }
}
`` `
;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGFuY2VEYlN0b3JhZ2VTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsYW5jZURiU3RvcmFnZVNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQXdDQSxnRUF3Q0M7QUFFRCwwRUF1Q0M7QUFLRCwwREFzRUM7QUFxQkQsb0NBa0RDO0FBR0Qsc0RBaURDO0FBL1RELGtEQUEwQztBQU8xQyxnR0FBK0csQ0FBQyx3Q0FBd0M7QUFDeEosZ0ZBQTZFO0FBRTdFLE1BQU0sNEJBQTRCLEdBQUcsS0FBSyxDQUFDLENBQUMsOENBQThDO0FBRTFGLHNEQUFzRDtBQUN0RCxTQUFTLGdCQUFnQixDQUFDLEtBQWlCLEVBQUUsYUFBcUI7SUFDaEUsSUFBSSxLQUFLLENBQUMsUUFBUSxFQUFFLENBQUM7UUFDbkIsZUFBTSxDQUFDLEtBQUssQ0FBQyxJQUFJLGFBQWEsWUFBWSxLQUFLLENBQUMsUUFBUSxDQUFDLE1BQU0sRUFBRSxFQUFFLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLENBQUM7UUFDeEYsTUFBTSxPQUFPLEdBQUcsS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFXLENBQUM7UUFDM0MsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLElBQUksSUFBSSxRQUFRLEtBQUssQ0FBQyxRQUFRLENBQUMsTUFBTSxFQUFFO2dCQUM3RCxPQUFPLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLElBQUksYUFBYSxhQUFhLGFBQWEsS0FBSyxDQUFDLFFBQVEsQ0FBQyxNQUFNLEVBQUU7Z0JBQ2xHLE9BQU8sRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxPQUFPO2FBQzVDO1NBQ0YsQ0FBQztJQUNKLENBQUM7U0FBTSxJQUFJLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FB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LENBQUMsS0FBSyxFQUFFLENBQUM7UUFDckQsQ0FBQzthQUFNLENBQUMsQ0FBQyw0Q0FBNEM7WUFDakQsZUFBTSxDQUFDLElBQUksQ0FBQyxpRkFBaUYsRUFBRSxRQUFRLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDOUcsT0FBTztnQkFDSCxFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLGdDQUFnQztvQkFDdEMsT0FBTyxFQUFFLGdFQUFnRTtvQkFDekUsT0FBTyxFQUFFLFFBQVEsQ0FBQyxJQUFJO2lCQUN2QjthQUNKLENBQUM7UUFDTixDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLGdCQUFnQixDQUFDLEtBQW1CLEVBQUUsdUJBQXVCLENBQUMsQ0FBQztJQUN4RSxDQUFDO0FBQ0gsQ0FBQztBQUNELEVBQUUsQ0FBQTtBQUNGLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7XG4gIEdtYWlsTWVzc2FnZVNuaXBwZXQsXG4gIE5vdGlvblBhZ2VTdW1tYXJ5LFxuICBTa2lsbFJlc3BvbnNlLFxuICBTa2lsbEVycm9yLFxufSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvdHlwZXMnOyAvLyBBZGp1c3QgcGF0aCBhcyBuZWVkZWRcbmltcG9ydCB7IFBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnOyAvLyBBc3N1bWluZyB0aGlzIGhvc3RzIHRoZSBuZXcgZW5kcG9pbnRzXG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9sb2dnZXInO1xuXG5jb25zdCBMQU5DRV9EQl9TVE9SQUdFX0FQSV9USU1FT1VUID0gMTUwMDA7IC8vIDE1IHNlY29uZHMgdGltZW91dCBmb3IgdGhlc2Ugc3BlY2lmaWMgY2FsbHNcblxuLy8gSGVscGVyIHRvIGNvbnN0cnVjdCBTa2lsbFJlc3BvbnNlIGZyb20gYXhpb3MgZXJyb3JzXG5mdW5jdGlvbiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yOiBBeGlvc0Vycm9yLCBvcGVyYXRpb25OYW1lOiBzdHJpbmcpOiBTa2lsbFJlc3BvbnNlPG51bGw+IHtcbiAgaWYgKGVycm9yLnJlc3BvbnNlKSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3I6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsIGVycm9yLnJlc3BvbnNlLmRhdGEpO1xuICAgIGNvbnN0IGVyckRhdGEgPSBlcnJvci5yZXNwb25zZS5kYXRhIGFzIGFueTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogZXJyRGF0YT8uZXJyb3I/LmNvZGUgfHwgYEhUVFBfJHtlcnJvci5yZXNwb25zZS5zdGF0dXN9YCxcbiAgICAgICAgbWVzc2FnZTogZXJyRGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHwgYEZhaWxlZCB0byAke29wZXJhdGlvbk5hbWV9LiBTdGF0dXM6ICR7ZXJyb3IucmVzcG9uc2Uuc3RhdHVzfWAsXG4gICAgICAgIGRldGFpbHM6IGVyckRhdGE/LmVycm9yPy5kZXRhaWxzIHx8IGVyckRhdGEsXG4gICAgICB9LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoZXJyb3IucmVxdWVzdCkge1xuICAgIGxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yOiBObyByZXNwb25zZSByZWNlaXZlZGAsIGVycm9yLnJlcXVlc3QpO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnTkVUV09SS19FUlJPUicsIG1lc3NhZ2U6IGBObyByZXNwb25zZSByZWNlaXZlZCBmb3IgJHtvcGVyYXRpb25OYW1lfS5gIH0sXG4gICAgfTtcbiAgfSBlbHNlIHtcbiAgICBsb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnUkVRVUVTVF9TRVRVUF9FUlJPUicsIG1lc3NhZ2U6IGBFcnJvciBzZXR0aW5nIHVwIHJlcXVlc3QgZm9yICR7b3BlcmF0aW9uTmFtZX06ICR7ZXJyb3IubWVzc2FnZX1gIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc3RvcmVFbWFpbFNuaXBwZXRJbkxhbmNlRGIoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbWFpbDogR21haWxNZXNzYWdlU25pcHBldCxcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTx7IGVtYWlsX2lkOiBzdHJpbmc7IG1lc3NhZ2U6IHN0cmluZyB9IHwgbnVsbCA+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgY29uc3QgZXJyb3JNc2cgPSBcIlBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCBpcyBub3QgY29uZmlndXJlZC5cIjtcbiAgICBsb2dnZXIuZXJyb3IoYFtzdG9yZUVtYWlsU25pcHBldEluTGFuY2VEYl0gJHtlcnJvck1zZ31gKTtcbiAgICByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiBlcnJvck1zZyB9IH07XG4gIH1cbiAgaWYgKCF1c2VySWQpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLCBtZXNzYWdlOiAndXNlcklkIGlzIHJlcXVpcmVkLid9fTtcbiAgaWYgKCFlbWFpbCB8fCAhZW1haWwuaWQpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLCBtZXNzYWdlOiAnVmFsaWQgZW1haWwgb2JqZWN0IHdpdGggaWQgaXMgcmVxdWlyZWQuJ319O1xuXG5cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9sYW5jZWRiL3N0b3JlLWVtYWlsLXNuaXBwZXRgO1xuICBjb25zdCBwYXlsb2FkID0ge1xuICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICBlbWFpbF9kYXRhOiBlbWFpbCwgLy8gVGhpcyBtYXRjaGVzIHRoZSBQeXRob24gZW5kcG9pbnQncyBleHBlY3RlZCAnZW1haWxfZGF0YScga2V5XG4gIH07XG5cbiAgbG9nZ2VyLmluZm8oYFtzdG9yZUVtYWlsU25pcHBldEluTGFuY2VEYl0gU3RvcmluZyBlbWFpbCBzbmlwcGV0IGZvciB1c2VyICR7dXNlcklkfSwgZW1haWwgSUQgJHtlbWFpbC5pZH1gKTtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChlbmRwb2ludCwgcGF5bG9hZCwgeyB0aW1lb3V0OiBMQU5DRV9EQl9TVE9SQUdFX0FQSV9USU1FT1VUIH0pO1xuICAgIGlmIChyZXNwb25zZS5kYXRhICYmIHJlc3BvbnNlLmRhdGEub2sgJiYgcmVzcG9uc2UuZGF0YS5kYXRhKSB7XG4gICAgICBsb2dnZXIuaW5mbyhgW3N0b3JlRW1haWxTbmlwcGV0SW5MYW5jZURiXSBTdWNjZXNzZnVsbHkgc3RvcmVkIGVtYWlsIHNuaXBwZXQgSUQgJHtyZXNwb25zZS5kYXRhLmRhdGEuZW1haWxfaWR9YCk7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzcG9uc2UuZGF0YS5kYXRhIH07XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKGBbc3RvcmVFbWFpbFNuaXBwZXRJbkxhbmNlRGJdIEZhaWxlZCB0byBzdG9yZSBlbWFpbCBzbmlwcGV0LiBBUEkgb2s6ICR7cmVzcG9uc2UuZGF0YT8ub2t9YCwgcmVzcG9uc2UuZGF0YT8uZXJyb3IpO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5jb2RlIHx8ICdQWVRIT05fQVBJX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHN0b3JlIGVtYWlsIHNuaXBwZXQgdmlhIFB5dGhvbiBBUEkuJyAsXG4gICAgICAgICAgZGV0YWlsczogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmRldGFpbHNcbiAgICAgICAgfVxuICAgICAgfTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ3N0b3JlRW1haWxTbmlwcGV0SW5MYW5jZURiJyk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHN0b3JlTm90aW9uUGFnZVN1bW1hcnlJbkxhbmNlRGIoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBwYWdlOiBOb3Rpb25QYWdlU3VtbWFyeSxcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTx7IG5vdGlvbl9wYWdlX2lkOiBzdHJpbmc7IG1lc3NhZ2U6IHN0cmluZyB9IHwgbnVsbCA+PiB7XG4gIGlmICghUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMKSB7XG4gICAgY29uc3QgZXJyb3JNc2cgPSBcIlBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCBpcyBub3QgY29uZmlndXJlZC5cIjtcbiAgICBsb2dnZXIuZXJyb3IoYFtzdG9yZU5vdGlvblBhZ2VTdW1tYXJ5SW5MYW5jZURiXSAke2Vycm9yTXNnfWApO1xuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6IGVycm9yTXNnIH0gfTtcbiAgfVxuICBpZiAoIXVzZXJJZCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICd1c2VySWQgaXMgcmVxdWlyZWQuJ319O1xuICBpZiAoIXBhZ2UgfHwgIXBhZ2UuaWQpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLCBtZXNzYWdlOiAnVmFsaWQgTm90aW9uIHBhZ2Ugb2JqZWN0IHdpdGggaWQgaXMgcmVxdWlyZWQuJ319O1xuXG5cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9sYW5jZWRiL3N0b3JlLW5vdGlvbi1zdW1tYXJ5YDtcbiAgY29uc3QgcGF5bG9hZCA9IHtcbiAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgcGFnZV9kYXRhOiBwYWdlLCAvLyBNYXRjaGVzIFB5dGhvbiBlbmRwb2ludCdzICdwYWdlX2RhdGEnXG4gIH07XG4gIGxvZ2dlci5pbmZvKGBbc3RvcmVOb3Rpb25QYWdlU3VtbWFyeUluTGFuY2VEYl0gU3RvcmluZyBOb3Rpb24gcGFnZSBzdW1tYXJ5IGZvciB1c2VyICR7dXNlcklkfSwgcGFnZSBJRCAke3BhZ2UuaWR9YCk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoZW5kcG9pbnQsIHBheWxvYWQsIHsgdGltZW91dDogTEFOQ0VfREJfU1RPUkFHRV9BUElfVElNRU9VVCB9KTtcbiAgICBpZiAocmVzcG9uc2UuZGF0YSAmJiByZXNwb25zZS5kYXRhLm9rICYmIHJlc3BvbnNlLmRhdGEuZGF0YSkge1xuICAgICAgbG9nZ2VyLmluZm8oYFtzdG9yZU5vdGlvblBhZ2VTdW1tYXJ5SW5MYW5jZURiXSBTdWNjZXNzZnVsbHkgc3RvcmVkIE5vdGlvbiBwYWdlIHN1bW1hcnkgSUQgJHtyZXNwb25zZS5kYXRhLmRhdGEubm90aW9uX3BhZ2VfaWR9YCk7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzcG9uc2UuZGF0YS5kYXRhIH07XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKGBbc3RvcmVOb3Rpb25QYWdlU3VtbWFyeUluTGFuY2VEYl0gRmFpbGVkIHRvIHN0b3JlIE5vdGlvbiBwYWdlIHN1bW1hcnkuIEFQSSBvazogJHtyZXNwb25zZS5kYXRhPy5va31gLCByZXNwb25zZS5kYXRhPy5lcnJvcik7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmNvZGUgfHwgJ1BZVEhPTl9BUElfRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gc3RvcmUgTm90aW9uIHBhZ2Ugc3VtbWFyeSB2aWEgUHl0aG9uIEFQSS4nICxcbiAgICAgICAgICBkZXRhaWxzOiByZXNwb25zZS5kYXRhPy5lcnJvcj8uZGV0YWlsc1xuICAgICAgICB9XG4gICAgICB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICByZXR1cm4gaGFuZGxlQXhpb3NFcnJvcihlcnJvciBhcyBBeGlvc0Vycm9yLCAnc3RvcmVOb3Rpb25QYWdlU3VtbWFyeUluTGFuY2VEYicpO1xuICB9XG59XG5cbmltcG9ydCAqIGFzIGZzIGZyb20gJ2ZzJzsgLy8gRm9yIHJlYWRpbmcgZmlsZSBjb250ZW50XG5pbXBvcnQgKiBhcyBwYXRoIGZyb20gJ3BhdGgnOyAvLyBGb3IgZ2V0dGluZyBmaWxlbmFtZSBmcm9tIHBhdGhcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHByb2Nlc3NBbmRTdG9yZURvY3VtZW50KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZmlsZVBhdGg6IHN0cmluZywgLy8gQ2hhbmdlZCBmcm9tIGZpbGU6IEZpbGVcbiAgZG9jVHlwZTogc3RyaW5nLCAvLyBlLmcuLCAncGRmJywgJ2RvY3gnXG4gIHRpdGxlPzogc3RyaW5nLFxuICBzb3VyY2VVcmk/OiBzdHJpbmcsIC8vIE9wdGlvbmFsOiBvcmlnaW5hbCBVUkkgaWYgbm90IGp1c3QgZmlsZW5hbWUgKGNvdWxkIGJlIHNhbWUgYXMgZmlsZVBhdGgpXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8eyBkb2NfaWQ6IHN0cmluZzsgbnVtX2NodW5rc19zdG9yZWQ6IG51bWJlciB9IHwgbnVsbD4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICBjb25zdCBlcnJvck1zZyA9IFwiUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIGlzIG5vdCBjb25maWd1cmVkIGZvciBkb2N1bWVudCBwcm9jZXNzaW5nLlwiO1xuICAgIGxvZ2dlci5lcnJvcihgW3Byb2Nlc3NBbmRTdG9yZURvY3VtZW50XSAke2Vycm9yTXNnfWApO1xuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0NPTkZJR19FUlJPUicsIG1lc3NhZ2U6IGVycm9yTXNnIH0gfTtcbiAgfVxuICBpZiAoIXVzZXJJZCkgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICd1c2VySWQgaXMgcmVxdWlyZWQuJ319O1xuICBpZiAoIWZpbGVQYXRoKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJywgbWVzc2FnZTogJ2ZpbGVQYXRoIGlzIHJlcXVpcmVkLid9fTtcbiAgaWYgKCFmcy5leGlzdHNTeW5jKGZpbGVQYXRoKSkge1xuICAgIGxvZ2dlci5lcnJvcihgW3Byb2Nlc3NBbmRTdG9yZURvY3VtZW50XSBGaWxlIG5vdCBmb3VuZCBhdCBwYXRoOiAke2ZpbGVQYXRofWApO1xuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHtjb2RlOiAnRklMRV9OT1RfRk9VTkQnLCBtZXNzYWdlOiBgRmlsZSBub3QgZm91bmQgYXQgcGF0aDogJHtmaWxlUGF0aH1gfX07XG4gIH1cblxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL2luZ2VzdC1kb2N1bWVudGA7XG4gIGxldCBmaWxlQnVmZmVyOiBCdWZmZXI7XG4gIHRyeSB7XG4gICAgZmlsZUJ1ZmZlciA9IGZzLnJlYWRGaWxlU3luYyhmaWxlUGF0aCk7XG4gIH0gY2F0Y2ggKHJlYWRFcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbcHJvY2Vzc0FuZFN0b3JlRG9jdW1lbnRdIEVycm9yIHJlYWRpbmcgZmlsZSAke2ZpbGVQYXRofTogJHtyZWFkRXJyb3IubWVzc2FnZX1gKTtcbiAgICByZXR1cm4ge29rOiBmYWxzZSwgZXJyb3I6IHtjb2RlOiAnRklMRV9SRUFEX0VSUk9SJywgbWVzc2FnZTogYEVycm9yIHJlYWRpbmcgZmlsZTogJHtyZWFkRXJyb3IubWVzc2FnZX1gfX07XG4gIH1cblxuICBjb25zdCBmb3JtRGF0YSA9IG5ldyBGb3JtRGF0YSgpO1xuICBjb25zdCBmaWxlTmFtZSA9IHBhdGguYmFzZW5hbWUoZmlsZVBhdGgpO1xuICBmb3JtRGF0YS5hcHBlbmQoJ2ZpbGUnLCBmaWxlQnVmZmVyLCBmaWxlTmFtZSk7IC8vIFNlbmQgYnVmZmVyIHdpdGggZmlsZW5hbWVcbiAgZm9ybURhdGEuYXBwZW5kKCd1c2VyX2lkJywgdXNlcklkKTtcbiAgZm9ybURhdGEuYXBwZW5kKCdkb2NfdHlwZScsIGRvY1R5cGUpO1xuXG4gIGNvbnN0IGVmZmVjdGl2ZVRpdGxlID0gdGl0bGUgfHwgZmlsZU5hbWU7XG4gIGZvcm1EYXRhLmFwcGVuZCgndGl0bGUnLCBlZmZlY3RpdmVUaXRsZSk7XG5cbiAgY29uc3QgZWZmZWN0aXZlU291cmNlVXJpID0gc291cmNlVXJpIHx8IGZpbGVQYXRoOyAvLyBVc2UgZmlsZVBhdGggYXMgc291cmNlVXJpIGlmIG5vdCBvdGhlcndpc2UgcHJvdmlkZWRcbiAgZm9ybURhdGEuYXBwZW5kKCdzb3VyY2VfdXJpJywgZWZmZWN0aXZlU291cmNlVXJpKTtcblxuICAvLyBOb3RlOiBvcGVuYWlfYXBpX2tleSBjb3VsZCBiZSBwYXNzZWQgaGVyZSBpZiBuZWVkZWQgYnkgYmFja2VuZCBwZXIgdXNlci9yZXF1ZXN0XG4gIC8vIGZvcm1EYXRhLmFwcGVuZCgnb3BlbmFpX2FwaV9rZXknLCAnVVNFUl9TUEVDSUZJQ19LRVlfSUZfQU5ZJyk7XG5cbiAgbG9nZ2VyLmluZm8oYFtwcm9jZXNzQW5kU3RvcmVEb2N1bWVudF0gVXBsb2FkaW5nIGRvY3VtZW50ICR7ZmlsZU5hbWV9IChmcm9tIHBhdGggJHtmaWxlUGF0aH0pIGZvciB1c2VyICR7dXNlcklkfSwgdHlwZSAke2RvY1R5cGV9LCB0aXRsZSAke2VmZmVjdGl2ZVRpdGxlfSwgc291cmNlVXJpICR7ZWZmZWN0aXZlU291cmNlVXJpfWApO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGVuZHBvaW50LCBmb3JtRGF0YSwge1xuICAgICAgaGVhZGVyczoge1xuICAgICAgICAnQ29udGVudC1UeXBlJzogJ211bHRpcGFydC9mb3JtLWRhdGEnLFxuICAgICAgfSxcbiAgICAgIHRpbWVvdXQ6IDE4MDAwMCwgLy8gMyBtaW51dGVzIHRpbWVvdXQgZm9yIHBvdGVudGlhbGx5IGxhcmdlIGZpbGUgcHJvY2Vzc2luZyAmIGVtYmVkZGluZ1xuICAgIH0pO1xuXG4gICAgaWYgKHJlc3BvbnNlLmRhdGEgJiYgcmVzcG9uc2UuZGF0YS5vayAmJiByZXNwb25zZS5kYXRhLmRhdGEpIHtcbiAgICAgIGxvZ2dlci5pbmZvKGBbcHJvY2Vzc0FuZFN0b3JlRG9jdW1lbnRdIFN1Y2Nlc3NmdWxseSBwcm9jZXNzZWQgYW5kIGluaXRpYXRlZCBzdG9yYWdlIGZvciBkb2N1bWVudCBJRCAke3Jlc3BvbnNlLmRhdGEuZGF0YS5kb2NfaWR9YCk7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzcG9uc2UuZGF0YS5kYXRhIH07XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKGBbcHJvY2Vzc0FuZFN0b3JlRG9jdW1lbnRdIEZhaWxlZCB0byBwcm9jZXNzIGRvY3VtZW50LiBBUEkgb2s6ICR7cmVzcG9uc2UuZGF0YT8ub2t9YCwgcmVzcG9uc2UuZGF0YT8uZXJyb3IpO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6IHJlc3BvbnNlLmRhdGE/LmVycm9yPy5jb2RlIHx8ICdQWVRIT05fQVBJX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiByZXNwb25zZS5kYXRhPy5lcnJvcj8ubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHByb2Nlc3MgZG9jdW1lbnQgdmlhIFB5dGhvbiBBUEkuJyAsXG4gICAgICAgICAgZGV0YWlsczogcmVzcG9uc2UuZGF0YT8uZXJyb3I/LmRldGFpbHNcbiAgICAgICAgfVxuICAgICAgfTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ3Byb2Nlc3NBbmRTdG9yZURvY3VtZW50Jyk7XG4gIH1cbn1cblxuLy8gLS0tIFNlbWFudGljIFNlYXJjaCBGdW5jdGlvbmFsaXR5IC0tLVxuXG5leHBvcnQgaW50ZXJmYWNlIFNlbWFudGljU2VhcmNoRmlsdGVycyB7XG4gIGRhdGVfYWZ0ZXI/OiBzdHJpbmc7IC8vIElTTyA4NjAxIHN0cmluZ1xuICBkYXRlX2JlZm9yZT86IHN0cmluZzsgLy8gSVNPIDg2MDEgc3RyaW5nXG4gIHNvdXJjZV90eXBlcz86IFNlYXJjaFJlc3VsdFNvdXJjZVR5cGVbXTsgLy8gVXNlIFNlYXJjaFJlc3VsdFNvdXJjZVR5cGUgZnJvbSB0eXBlcy50c1xuICBkb2NfdHlwZV9maWx0ZXI/OiBzdHJpbmc7IC8vIGUuZy4sIFwicGRmXCIsIFwiZG9jeFwiIC0gc3BlY2lmaWMgdG8gZG9jdW1lbnRfY2h1bmsgc291cmNlX3R5cGVcbiAgLy8gQWRkIG90aGVyIHBvdGVudGlhbCBmaWx0ZXJzIGFzIHRoZSBiYWNrZW5kIGV2b2x2ZXNcbn1cblxuLy8gRW5zdXJlIFVuaXZlcnNhbFNlYXJjaFJlc3VsdEl0ZW0gaXMgaW1wb3J0ZWQgZnJvbSB0eXBlcy50c1xuaW1wb3J0IHsgVW5pdmVyc2FsU2VhcmNoUmVzdWx0SXRlbSwgU2VhcmNoUmVzdWx0U291cmNlVHlwZSwgSHlicmlkU2VhcmNoUmVzdWx0SXRlbSwgSHlicmlkU2VhcmNoRmlsdGVycyB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC90eXBlcyc7XG5cbmV4cG9ydCBpbnRlcmZhY2UgSHlicmlkU2VhcmNoT3B0aW9ucyB7XG4gIHNlbWFudGljTGltaXQ/OiBudW1iZXI7XG4gIGtleXdvcmRMaW1pdD86IG51bWJlcjtcbiAgZmlsdGVycz86IEh5YnJpZFNlYXJjaEZpbHRlcnM7IC8vIFVzZSB0aGUgbmV3IHNwZWNpZmljIGZpbHRlciB0eXBlXG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoeWJyaWRTZWFyY2goXG4gIHVzZXJJZDogc3RyaW5nLFxuICBxdWVyeVRleHQ6IHN0cmluZyxcbiAgb3B0aW9uczogSHlicmlkU2VhcmNoT3B0aW9ucyA9IHt9LFxuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPEh5YnJpZFNlYXJjaFJlc3VsdEl0ZW1bXT4+IHtcbiAgaWYgKCFQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwpIHtcbiAgICBjb25zdCBlcnJvck1zZyA9IFwiUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIGlzIG5vdCBjb25maWd1cmVkIGZvciBoeWJyaWQgc2VhcmNoLlwiO1xuICAgIGxvZ2dlci5lcnJvcihgW2h5YnJpZFNlYXJjaF0gJHtlcnJvck1zZ31gKTtcbiAgICByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdDT05GSUdfRVJST1InLCBtZXNzYWdlOiBlcnJvck1zZyB9IH07XG4gIH1cbiAgaWYgKCF1c2VySWQpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLCBtZXNzYWdlOiAndXNlcklkIGlzIHJlcXVpcmVkLid9fTtcbiAgaWYgKCFxdWVyeVRleHQgfHwgcXVlcnlUZXh0LnRyaW0oKSA9PT0gXCJcIikgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdxdWVyeVRleHQgY2Fubm90IGJlIGVtcHR5Lid9fTtcblxuICBjb25zdCBlbmRwb2ludCA9IGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL3NlYXJjaC9oeWJyaWRgO1xuICBjb25zdCBwYXlsb2FkID0ge1xuICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICBxdWVyeV90ZXh0OiBxdWVyeVRleHQsXG4gICAgbGltaXRfc2VtYW50aWM6IG9wdGlvbnMuc2VtYW50aWNMaW1pdCxcbiAgICBsaW1pdF9rZXl3b3JkOiBvcHRpb25zLmtleXdvcmRMaW1pdCxcbiAgICBmaWx0ZXJzOiBvcHRpb25zLmZpbHRlcnMgfHwge30sXG4gIH07XG5cbiAgbG9nZ2VyLmluZm8oYFtoeWJyaWRTZWFyY2hdIFBlcmZvcm1pbmcgaHlicmlkIHNlYXJjaCBmb3IgdXNlciAke3VzZXJJZH0gd2l0aCBxdWVyeSBcIiR7cXVlcnlUZXh0LnN1YnN0cmluZygwLCA1MCl9Li4uXCJgKTtcblxuICB0cnkge1xuICAgIC8vIE5vdGU6IFRoZSByZXNwb25zZSBkYXRhIHNob3VsZCBiZSBgSHlicmlkU2VhcmNoUmVzdWx0SXRlbVtdYFxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdDxTa2lsbFJlc3BvbnNlPEh5YnJpZFNlYXJjaFJlc3VsdEl0ZW1bXT4+KGVuZHBvaW50LCBwYXlsb2FkLCB7XG4gICAgICB0aW1lb3V0OiBMQU5DRV9EQl9TVE9SQUdFX0FQSV9USU1FT1VUICogMi41IC8vIEdpdmUgaHlicmlkIHNlYXJjaCBhIGJpdCBtb3JlIHRpbWVcbiAgICB9KTtcblxuICAgIGlmIChyZXNwb25zZS5kYXRhICYmIHJlc3BvbnNlLmRhdGEub2sgJiYgQXJyYXkuaXNBcnJheShyZXNwb25zZS5kYXRhLmRhdGEpKSB7XG4gICAgICBsb2dnZXIuaW5mbyhgW2h5YnJpZFNlYXJjaF0gU3VjY2Vzc2Z1bGx5IHJlY2VpdmVkICR7cmVzcG9uc2UuZGF0YS5kYXRhLmxlbmd0aH0gaHlicmlkIHNlYXJjaCByZXN1bHRzLmApO1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmRhdGEuZGF0YSB9O1xuICAgIH0gZWxzZSBpZiAocmVzcG9uc2UuZGF0YSAmJiAhcmVzcG9uc2UuZGF0YS5vayAmJiByZXNwb25zZS5kYXRhLmVycm9yKSB7XG4gICAgICAgIGxvZ2dlci53YXJuKGBbaHlicmlkU2VhcmNoXSBIeWJyaWQgc2VhcmNoIGZhaWxlZC4gQVBJIG9rOmZhbHNlYCwgcmVzcG9uc2UuZGF0YS5lcnJvcik7XG4gICAgICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHJlc3BvbnNlLmRhdGEuZXJyb3IgfTtcbiAgICB9IGVsc2Uge1xuICAgICAgICBsb2dnZXIud2FybihgW2h5YnJpZFNlYXJjaF0gVW5leHBlY3RlZCByZXNwb25zZSBzdHJ1Y3R1cmUgZnJvbSBoeWJyaWQgc2VhcmNoIEFQSS5gLCByZXNwb25zZS5kYXRhKTtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICAgIGNvZGU6ICdQWVRIT05fQVBJX1VORVhQRUNURURfUkVTUE9OU0UnLFxuICAgICAgICAgICAgICBtZXNzYWdlOiAnVW5leHBlY3RlZCByZXNwb25zZSBzdHJ1Y3R1cmUgZnJvbSBQeXRob24gaHlicmlkIHNlYXJjaCBBUEkuJyAsXG4gICAgICAgICAgICAgIGRldGFpbHM6IHJlc3BvbnNlLmRhdGFcbiAgICAgICAgICAgIH1cbiAgICAgICAgfTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgcmV0dXJuIGhhbmRsZUF4aW9zRXJyb3IoZXJyb3IgYXMgQXhpb3NFcnJvciwgJ2h5YnJpZFNlYXJjaCcpO1xuICB9XG59XG5cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlbWFudGljU2VhcmNoTGFuY2VEYihcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHF1ZXJ5VGV4dDogc3RyaW5nLFxuICBmaWx0ZXJzPzogU2VtYW50aWNTZWFyY2hGaWx0ZXJzLFxuICBsaW1pdDogbnVtYmVyID0gMTAsXG4pOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8VW5pdmVyc2FsU2VhcmNoUmVzdWx0SXRlbVtdPj4ge1xuICBpZiAoIVBZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTCkge1xuICAgIGNvbnN0IGVycm9yTXNnID0gXCJQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgaXMgbm90IGNvbmZpZ3VyZWQgZm9yIHNlbWFudGljIHNlYXJjaC5cIjtcbiAgICBsb2dnZXIuZXJyb3IoYFtzZW1hbnRpY1NlYXJjaExhbmNlRGJdICR7ZXJyb3JNc2d9YCk7XG4gICAgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnQ09ORklHX0VSUk9SJywgbWVzc2FnZTogZXJyb3JNc2cgfSB9O1xuICB9XG4gIGlmICghdXNlcklkKSByZXR1cm4geyBvazogZmFsc2UsIGVycm9yOiB7IGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJywgbWVzc2FnZTogJ3VzZXJJZCBpcyByZXF1aXJlZC4nfX07XG4gIGlmICghcXVlcnlUZXh0IHx8IHF1ZXJ5VGV4dC50cmltKCkgPT09IFwiXCIpIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLCBtZXNzYWdlOiAncXVlcnlUZXh0IGNhbm5vdCBiZSBlbXB0eS4nfX07XG5cbiAgY29uc3QgZW5kcG9pbnQgPSBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9sYW5jZWRiL3NlbWFudGljLXNlYXJjaGA7XG4gIGNvbnN0IHBheWxvYWQgPSB7XG4gICAgdXNlcl9pZDogdXNlcklkLFxuICAgIHF1ZXJ5X3RleHQ6IHF1ZXJ5VGV4dCxcbiAgICBmaWx0ZXJzOiBmaWx0ZXJzIHx8IHt9LCAvLyBTZW5kIGVtcHR5IG9iamVjdCBpZiBubyBmaWx0ZXJzXG4gICAgbGltaXQ6IGxpbWl0LFxuICB9O1xuXG4gIGxvZ2dlci5pbmZvKGBbc2VtYW50aWNTZWFyY2hMYW5jZURiXSBQZXJmb3JtaW5nIHNlbWFudGljIHNlYXJjaCBmb3IgdXNlciAke3VzZXJJZH0gd2l0aCBxdWVyeSBcIiR7cXVlcnlUZXh0LnN1YnN0cmluZygwLCA1MCl9Li4uXCJgKTtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdDxTa2lsbFJlc3BvbnNlPFVuaXZlcnNhbFNlYXJjaFJlc3VsdEl0ZW1bXT4+KGVuZHBvaW50LCBwYXlsb2FkLCB7XG4gICAgICB0aW1lb3V0OiBMQU5DRV9EQl9TVE9SQUdFX0FQSV9USU1FT1VUICogMiAvLyBTZWFyY2ggbWlnaHQgdGFrZSBsb25nZXJcbiAgICB9KTtcbiAgICAvLyBBc3N1bWluZyBQeXRob24gZW5kcG9pbnQgZGlyZWN0bHkgcmV0dXJucyBTa2lsbFJlc3BvbnNlLWxpa2Ugc3RydWN0dXJlIHdpdGggXCJva1wiIGFuZCBcImRhdGFcIiBvciBcImVycm9yXCJcbiAgICBpZiAocmVzcG9uc2UuZGF0YSAmJiByZXNwb25zZS5kYXRhLm9rICYmIHJlc3BvbnNlLmRhdGEuZGF0YSkge1xuICAgICAgbG9nZ2VyLmluZm8oYFtzZW1hbnRpY1NlYXJjaExhbmNlRGJdIFN1Y2Nlc3NmdWxseSByZWNlaXZlZCAke3Jlc3BvbnNlLmRhdGEuZGF0YS5sZW5ndGh9IHNlYXJjaCByZXN1bHRzLmApO1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmRhdGEuZGF0YSB9O1xuICAgIH0gZWxzZSBpZiAocmVzcG9uc2UuZGF0YSAmJiAhcmVzcG9uc2UuZGF0YS5vayAmJiByZXNwb25zZS5kYXRhLmVycm9yKSB7IC8vIFB5dGhvbiByZXR1cm5lZCBvazpmYWxzZVxuICAgICAgICBsb2dnZXIud2FybihgW3NlbWFudGljU2VhcmNoTGFuY2VEYl0gU2VtYW50aWMgc2VhcmNoIGZhaWxlZC4gQVBJIG9rOmZhbHNlYCwgcmVzcG9uc2UuZGF0YS5lcnJvcik7XG4gICAgICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHJlc3BvbnNlLmRhdGEuZXJyb3IgfTtcbiAgICB9IGVsc2UgeyAvLyBVbmV4cGVjdGVkIHJlc3BvbnNlIHN0cnVjdHVyZSBmcm9tIFB5dGhvblxuICAgICAgICBsb2dnZXIud2FybihgW3NlbWFudGljU2VhcmNoTGFuY2VEYl0gVW5leHBlY3RlZCByZXNwb25zZSBzdHJ1Y3R1cmUgZnJvbSBzZW1hbnRpYyBzZWFyY2ggQVBJLmAsIHJlc3BvbnNlLmRhdGEpO1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgICAgY29kZTogJ1BZVEhPTl9BUElfVU5FWFBFQ1RFRF9SRVNQT05TRScsXG4gICAgICAgICAgICAgIG1lc3NhZ2U6ICdVbmV4cGVjdGVkIHJlc3BvbnNlIHN0cnVjdHVyZSBmcm9tIFB5dGhvbiBzZW1hbnRpYyBzZWFyY2ggQVBJLicgLFxuICAgICAgICAgICAgICBkZXRhaWxzOiByZXNwb25zZS5kYXRhXG4gICAgICAgICAgICB9XG4gICAgICAgIH07XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcikge1xuICAgIHJldHVybiBoYW5kbGVBeGlvc0Vycm9yKGVycm9yIGFzIEF4aW9zRXJyb3IsICdzZW1hbnRpY1NlYXJjaExhbmNlRGInKTtcbiAgfVxufVxuYGBgXG4iXX0=
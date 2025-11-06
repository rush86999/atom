/**
 * Complete Airtable Data Management Skills
 * All Airtable data management operations
 */

import axios, { AxiosResponse } from 'axios';
import { logger } from '@/utils/logging';

// Interfaces for Airtable data
interface AirtableBase {
  id: string;
  name: string;
  permission_level: string;
  sharing: string;
  created_time: string;
  last_modified_time: string;
  base_icon_url: string;
  base_color_theme: string;
  workspace_id: string;
  workspace_name: string;
  total_tables: number;
  total_records: number;
  total_fields: number;
  total_views: number;
  total_collaborators: number;
  collaboration: Record<string, any>;
}

interface AirtableTable {
  id: string;
  name: string;
  primary_field_id: string;
  primary_field_name: string;
  description: string;
  records_count: number;
  views_count: number;
  fields: Array<{
    id: string;
    name: string;
    type: string;
    description: string;
    options: Record<string, any>;
    required: boolean;
    unique: boolean;
    hidden: boolean;
    formula: string;
    validation: Record<string, any>;
    lookup: Record<string, any>;
    rollup: Record<string, any>;
    multiple_record_links: Record<string, any>;
  }>;
  views: Array<{
    id: string;
    name: string;
    type: string;
    personal: boolean;
    description: string;
    filters: Record<string, any>;
    sorts: Record<string, any>;
    field_options: Record<string, any>;
  }>;
  created_time: string;
  last_modified_time: string;
  icon_emoji: string;
  icon_url: string;
}

interface AirtableField {
  id: string;
  name: string;
  type: string;
  description: string;
  options: Record<string, any>;
  required: boolean;
  unique: boolean;
  hidden: boolean;
  formula: string;
  validation: Record<string, any>;
  lookup: Record<string, any>;
  rollup: Record<string, any>;
  multiple_record_links: Record<string, any>;
}

interface AirtableView {
  id: string;
  name: string;
  type: string;
  personal: boolean;
  description: string;
  filters: Record<string, any>;
  sorts: Record<string, any>;
  field_options: Record<string, any>;
}

interface AirtableRecord {
  id: string;
  created_time: string;
  fields: Record<string, any>;
  field_values: Record<string, any>;
  table_id: string;
  table_name: string;
  base_id: string;
  base_name: string;
  attachments: Array<{
    id: string;
    name: string;
    type: string;
    size: number;
    url: string;
  }>;
  linked_records: Array<{
    field: string;
    record_ids: string[];
  }>;
  comments_count: number;
  last_modified_time: string;
}

interface AirtableUser {
  id: string;
  email: string;
  name: string;
  state: string;
  invites: Array<Record<string, any>>;
  enterprise_info: Record<string, any>;
  group_info: Array<Record<string, any>>;
}

interface AirtableMemorySettings {
  userId: string;
  ingestionEnabled: boolean;
  syncFrequency: string;
  dataRetentionDays: number;
  includeBases: string[];
  excludeBases: string[];
  includeArchivedBases: boolean;
  includeTables: boolean;
  includeRecords: boolean;
  includeFields: boolean;
  includeViews: boolean;
  includeAttachments: boolean;
  includeWebhooks: boolean;
  maxRecordsPerSync: number;
  maxTableRecordsPerSync: number;
  syncDeletedRecords: boolean;
  syncRecordAttachments: boolean;
  indexRecordContent: boolean;
  searchEnabled: boolean;
  semanticSearchEnabled: boolean;
  metadataExtractionEnabled: boolean;
  baseTrackingEnabled: boolean;
  tableAnalysisEnabled: boolean;
  fieldAnalysisEnabled: boolean;
  lastSyncTimestamp?: string;
  nextSyncTimestamp?: string;
  syncInProgress: boolean;
  errorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

// Atom API client
const atomApiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Utility functions
const airtableUtils = {
  validateBaseId: (baseId: string): boolean => {
    return baseId && baseId.length >= 16 && baseId.length <= 64;
  },

  validateTableId: (tableId: string): boolean => {
    return tableId && tableId.length >= 16 && tableId.length <= 64;
  },

  validateRecordId: (recordId: string): boolean => {
    return recordId && recordId.length >= 16 && recordId.length <= 64;
  },

  validateFieldId: (fieldId: string): boolean => {
    return fieldId && fieldId.length >= 16 && fieldId.length <= 64;
  },

  validateViewId: (viewId: string): boolean => {
    return viewId && viewId.length >= 16 && viewId.length <= 64;
  },

  validateApiKey: (apiKey: string): boolean => {
    return apiKey && apiKey.length >= 20 && apiKey.length <= 256;
  },

  validateSearchQuery: (query: string): boolean => {
    if (!query) return false;
    if (query.length > 1000) return false;
    // Check for potentially dangerous characters
    const dangerousChars = /[<>]/;
    return !dangerousChars.test(query);
  },

  validateSyncFrequency: (frequency: string): boolean => {
    const validFrequencies = ['real-time', 'hourly', 'daily', 'weekly', 'manual'];
    return validFrequencies.includes(frequency);
  },

  getFieldTypeCategory: (fieldType: string): string => {
    const field_type_categories = {
      'text': ['single_line_text', 'long_text', 'rich_text', 'email', 'url'],
      'numeric': ['number', 'percent', 'currency', 'rating', 'duration'],
      'date': ['date', 'datetime', 'created_time', 'modified_time'],
      'select': ['single_select', 'multiple_selects'],
      'link': ['multiple_record_links'],
      'lookup': ['lookup'],
      'rollup': ['rollup'],
      'formula': ['formula'],
      'attachment': ['attachment'],
      'user': ['created_by', 'modified_by'],
      'other': ['checkbox', 'barcode', 'unknown']
    };
    
    for (const category in field_type_categories) {
      const types = field_type_categories[category];
      if (types.includes(fieldType)) {
        return category;
      }
    }
    return 'other';
  }
};

// Complete Airtable skills
const airtableSkills = {

  /**
   * Get Airtable bases
   */
  airtableGetBases: async (
    userId: string,
    apiKey: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable bases for user ${userId}`);
      
      const response = await atomApiClient.post('/api/airtable/data-management/bases/list', {
        user_id: userId,
        api_key: apiKey
      });
      
      const data = response.data;
      
      if (data.ok) {
        const bases = data.bases;
        logger.info(`Airtable bases retrieved: ${bases.length} bases`);
        return {
          success: true,
          bases: bases
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable bases');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetBases:', error);
      throw new Error(`Failed to get Airtable bases: ${error.message}`);
    }
  },

  /**
   * Get Airtable base details
   */
  airtableGetBase: async (
    userId: string,
    apiKey: string,
    baseId: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable base details for user ${userId}: ${baseId}`);
      
      if (!airtableUtils.validateBaseId(baseId)) {
        throw new Error('Invalid base ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/bases/get', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const base = data.base;
        logger.info(`Airtable base details retrieved: ${baseId}`);
        return {
          success: true,
          base: base
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable base');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetBase:', error);
      throw new Error(`Failed to get Airtable base: ${error.message}`);
    }
  },

  /**
   * Get Airtable tables
   */
  airtableGetTables: async (
    userId: string,
    apiKey: string,
    baseId: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable tables for user ${userId}: ${baseId}`);
      
      if (!airtableUtils.validateBaseId(baseId)) {
        throw new Error('Invalid base ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/tables/list', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const tables = data.tables;
        logger.info(`Airtable tables retrieved: ${tables.length} tables`);
        return {
          success: true,
          tables: tables
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable tables');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetTables:', error);
      throw new Error(`Failed to get Airtable tables: ${error.message}`);
    }
  },

  /**
   * Get Airtable table details
   */
  airtableGetTable: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable table details for user ${userId}: ${baseId}/${tableId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || !airtableUtils.validateTableId(tableId)) {
        throw new Error('Invalid base ID or table ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/tables/get', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const table = data.table;
        logger.info(`Airtable table details retrieved: ${tableId}`);
        return {
          success: true,
          table: table
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable table');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetTable:', error);
      throw new Error(`Failed to get Airtable table: ${error.message}`);
    }
  },

  /**
   * Get Airtable records
   */
  airtableGetRecords: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string,
    options: any = {}
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable records for user ${userId}: ${baseId}/${tableId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || !airtableUtils.validateTableId(tableId)) {
        throw new Error('Invalid base ID or table ID');
      }
      
      const {
        view_id,
        filter_by_formula,
        sort,
        fields,
        max_records = 100,
        page_size = 100,
        offset
      } = options;
      
      const response = await atomApiClient.post('/api/airtable/data-management/records/list', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId,
        view_id: view_id,
        filter_by_formula: filter_by_formula,
        sort: sort,
        fields: fields,
        max_records: max_records,
        page_size: page_size,
        offset: offset
      });
      
      const data = response.data;
      
      if (data.ok) {
        const records = data.records;
        const offset_result = data.offset;
        logger.info(`Airtable records retrieved: ${records.length} records`);
        return {
          success: true,
          records: records,
          offset: offset_result,
          total: records.length,
          filters: data.filters
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable records');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetRecords:', error);
      throw new Error(`Failed to get Airtable records: ${error.message}`);
    }
  },

  /**
   * Get Airtable record details
   */
  airtableGetRecord: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string,
    recordId: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable record details for user ${userId}: ${baseId}/${tableId}/${recordId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || 
          !airtableUtils.validateTableId(tableId) || 
          !airtableUtils.validateRecordId(recordId)) {
        throw new Error('Invalid base ID, table ID, or record ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/records/get', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId,
        record_id: recordId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const record = data.record;
        logger.info(`Airtable record details retrieved: ${recordId}`);
        return {
          success: true,
          record: record
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable record');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetRecord:', error);
      throw new Error(`Failed to get Airtable record: ${error.message}`);
    }
  },

  /**
   * Create Airtable record
   */
  airtableCreateRecord: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string,
    fields: Record<string, any>
  ): Promise<any> => {
    try {
      logger.info(`Creating Airtable record for user ${userId}: ${baseId}/${tableId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || !airtableUtils.validateTableId(tableId)) {
        throw new Error('Invalid base ID or table ID');
      }
      
      if (!fields || Object.keys(fields).length === 0) {
        throw new Error('Fields are required');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/records/create', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId,
        fields: fields
      });
      
      const data = response.data;
      
      if (data.ok) {
        const record = data.record;
        logger.info(`Airtable record created: ${record.id}`);
        return {
          success: true,
          record: record
        };
      } else {
        throw new Error(data.error || 'Failed to create Airtable record');
      }
    } catch (error: any) {
      logger.error('Error in airtableCreateRecord:', error);
      throw new Error(`Failed to create Airtable record: ${error.message}`);
    }
  },

  /**
   * Update Airtable record
   */
  airtableUpdateRecord: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string,
    recordId: string,
    fields: Record<string, any>
  ): Promise<any> => {
    try {
      logger.info(`Updating Airtable record for user ${userId}: ${baseId}/${tableId}/${recordId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || 
          !airtableUtils.validateTableId(tableId) || 
          !airtableUtils.validateRecordId(recordId)) {
        throw new Error('Invalid base ID, table ID, or record ID');
      }
      
      if (!fields || Object.keys(fields).length === 0) {
        throw new Error('Fields are required');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/records/update', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId,
        record_id: recordId,
        fields: fields
      });
      
      const data = response.data;
      
      if (data.ok) {
        const record = data.record;
        logger.info(`Airtable record updated: ${recordId}`);
        return {
          success: true,
          record: record
        };
      } else {
        throw new Error(data.error || 'Failed to update Airtable record');
      }
    } catch (error: any) {
      logger.error('Error in airtableUpdateRecord:', error);
      throw new Error(`Failed to update Airtable record: ${error.message}`);
    }
  },

  /**
   * Delete Airtable record
   */
  airtableDeleteRecord: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string,
    recordId: string
  ): Promise<boolean> => {
    try {
      logger.info(`Deleting Airtable record for user ${userId}: ${baseId}/${tableId}/${recordId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || 
          !airtableUtils.validateTableId(tableId) || 
          !airtableUtils.validateRecordId(recordId)) {
        throw new Error('Invalid base ID, table ID, or record ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/records/delete', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId,
        record_id: recordId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable record deleted: ${recordId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete Airtable record');
      }
    } catch (error: any) {
      logger.error('Error in airtableDeleteRecord:', error);
      throw new Error(`Failed to delete Airtable record: ${error.message}`);
    }
  },

  /**
   * Get Airtable fields
   */
  airtableGetFields: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable fields for user ${userId}: ${baseId}/${tableId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || !airtableUtils.validateTableId(tableId)) {
        throw new Error('Invalid base ID or table ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/fields/list', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const fields = data.fields;
        logger.info(`Airtable fields retrieved: ${fields.length} fields`);
        return {
          success: true,
          fields: fields
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable fields');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetFields:', error);
      throw new Error(`Failed to get Airtable fields: ${error.message}`);
    }
  },

  /**
   * Get Airtable views
   */
  airtableGetViews: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable views for user ${userId}: ${baseId}/${tableId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || !airtableUtils.validateTableId(tableId)) {
        throw new Error('Invalid base ID or table ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/views/list', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const views = data.views;
        logger.info(`Airtable views retrieved: ${views.length} views`);
        return {
          success: true,
          views: views
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable views');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetViews:', error);
      throw new Error(`Failed to get Airtable views: ${error.message}`);
    }
  },

  /**
   * Search Airtable records
   */
  airtableSearchRecords: async (
    userId: string,
    apiKey: string,
    baseId: string,
    tableId: string,
    searchQuery: string,
    options: any = {}
  ): Promise<any> => {
    try {
      logger.info(`Searching Airtable records for user ${userId}: ${baseId}/${tableId}`);
      
      if (!airtableUtils.validateBaseId(baseId) || !airtableUtils.validateTableId(tableId)) {
        throw new Error('Invalid base ID or table ID');
      }
      
      if (searchQuery && !airtableUtils.validateSearchQuery(searchQuery)) {
        throw new Error('Invalid search query');
      }
      
      const {
        view_id,
        fields,
        max_records = 100
      } = options;
      
      const response = await atomApiClient.post('/api/airtable/data-management/search/records', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId,
        table_id: tableId,
        search_query: searchQuery,
        view_id: view_id,
        fields: fields,
        max_records: max_records
      });
      
      const data = response.data;
      
      if (data.ok) {
        const records = data.records;
        const offset_result = data.offset;
        logger.info(`Airtable records search completed: ${records.length} results`);
        return {
          success: true,
          records: records,
          count: records.length,
          offset: offset_result,
          search_filters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Airtable records');
      }
    } catch (error: any) {
      logger.error('Error in airtableSearchRecords:', error);
      throw new Error(`Failed to search Airtable records: ${error.message}`);
    }
  },

  /**
   * Get Airtable webhooks
   */
  airtableGetWebhooks: async (
    userId: string,
    apiKey: string,
    baseId: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Airtable webhooks for user ${userId}: ${baseId}`);
      
      if (!airtableUtils.validateBaseId(baseId)) {
        throw new Error('Invalid base ID');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/webhooks/list', {
        user_id: userId,
        api_key: apiKey,
        base_id: baseId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const webhooks = data.webhooks;
        logger.info(`Airtable webhooks retrieved: ${webhooks.length} webhooks`);
        return {
          success: true,
          webhooks: webhooks
        };
      } else {
        throw new Error(data.error || 'Failed to get Airtable webhooks');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetWebhooks:', error);
      throw new Error(`Failed to get Airtable webhooks: ${error.message}`);
    }
  },

  /**
   * Get Airtable memory settings
   */
  airtableGetMemorySettings: async (userId: string): Promise<AirtableMemorySettings> => {
    try {
      logger.info(`Getting Airtable memory settings for user ${userId}`);
      
      const response = await atomApiClient.post('/api/airtable/data-management/memory/settings', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable memory settings retrieved for user ${userId}`);
        return data.settings;
      } else {
        throw new Error(data.error || 'Failed to get Airtable memory settings');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetMemorySettings:', error);
      throw new Error(`Failed to get Airtable memory settings: ${error.message}`);
    }
  },

  /**
   * Update Airtable memory settings
   */
  airtableUpdateMemorySettings: async (
    userId: string,
    settings: Partial<AirtableMemorySettings>
  ): Promise<boolean> => {
    try {
      logger.info(`Updating Airtable memory settings for user ${userId}`);
      
      // Validate sync frequency
      if (settings.syncFrequency && !airtableUtils.validateSyncFrequency(settings.syncFrequency)) {
        throw new Error('Invalid sync frequency');
      }
      
      const response = await atomApiClient.put('/api/airtable/data-management/memory/settings', {
        user_id: userId,
        ...settings
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable memory settings updated for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to update Airtable memory settings');
      }
    } catch (error: any) {
      logger.error('Error in airtableUpdateMemorySettings:', error);
      throw new Error(`Failed to update Airtable memory settings: ${error.message}`);
    }
  },

  /**
   * Start Airtable ingestion
   */
  airtableStartIngestion: async (
    userId: string,
    apiKey: string,
    baseIds: string[] = [],
    forceSync: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Starting Airtable ingestion for user ${userId}`);
      
      const response = await atomApiClient.post('/api/airtable/data-management/memory/ingest', {
        user_id: userId,
        api_key: apiKey,
        base_ids: baseIds,
        force_sync: forceSync
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable ingestion started: ${data.ingestion_result.bases_ingested} bases`);
        return data.ingestion_result;
      } else {
        throw new Error(data.error || 'Failed to start Airtable ingestion');
      }
    } catch (error: any) {
      logger.error('Error in airtableStartIngestion:', error);
      throw new Error(`Failed to start Airtable ingestion: ${error.message}`);
    }
  },

  /**
   * Get Airtable sync status
   */
  airtableGetSyncStatus: async (userId: string): Promise<any> => {
    try {
      logger.info(`Getting Airtable sync status for user ${userId}`);
      
      const response = await atomApiClient.post('/api/airtable/data-management/memory/status', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable sync status retrieved for user ${userId}`);
        return data.memory_status;
      } else {
        throw new Error(data.error || 'Failed to get Airtable sync status');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetSyncStatus:', error);
      throw new Error(`Failed to get Airtable sync status: ${error.message}`);
    }
  },

  /**
   * Search Airtable memory bases
   */
  airtableSearchMemoryBases: async (
    userId: string,
    query: string = '',
    sharing: string = null,
    limit: number = 50
  ): Promise<any> => {
    try {
      logger.info(`Searching Airtable memory bases for user ${userId}: ${query}`);
      
      if (query && !airtableUtils.validateSearchQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/memory/search/bases', {
        user_id: userId,
        query: query,
        sharing: sharing,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable memory bases search completed: ${data.count} results`);
        return {
          bases: data.bases,
          count: data.count,
          search_filters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Airtable memory bases');
      }
    } catch (error: any) {
      logger.error('Error in airtableSearchMemoryBases:', error);
      throw new Error(`Failed to search Airtable memory bases: ${error.message}`);
    }
  },

  /**
   * Search Airtable memory records
   */
  airtableSearchMemoryRecords: async (
    userId: string,
    query: string = '',
    baseId: string = null,
    tableId: string = null,
    fieldType: string = null,
    limit: number = 50
  ): Promise<any> => {
    try {
      logger.info(`Searching Airtable memory records for user ${userId}: ${query}`);
      
      if (query && !airtableUtils.validateSearchQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      const response = await atomApiClient.post('/api/airtable/data-management/memory/search/records', {
        user_id: userId,
        query: query,
        base_id: baseId,
        table_id: tableId,
        field_type: fieldType,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable memory records search completed: ${data.count} results`);
        return {
          records: data.records,
          count: data.count,
          search_filters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Airtable memory records');
      }
    } catch (error: any) {
      logger.error('Error in airtableSearchMemoryRecords:', error);
      throw new Error(`Failed to search Airtable memory records: ${error.message}`);
    }
  },

  /**
   * Get Airtable ingestion statistics
   */
  airtableGetIngestionStats: async (userId: string): Promise<any> => {
    try {
      logger.info(`Getting Airtable ingestion stats for user ${userId}`);
      
      const response = await atomApiClient.post('/api/airtable/data-management/memory/ingestion-stats', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable ingestion stats retrieved for user ${userId}`);
        return data.ingestion_stats;
      } else {
        throw new Error(data.error || 'Failed to get Airtable ingestion stats');
      }
    } catch (error: any) {
      logger.error('Error in airtableGetIngestionStats:', error);
      throw new Error(`Failed to get Airtable ingestion stats: ${error.message}`);
    }
  },

  /**
   * Delete Airtable user data
   */
  airtableDeleteUserData: async (userId: string): Promise<boolean> => {
    try {
      logger.info(`Deleting Airtable user data for user ${userId}`);
      
      const response = await atomApiClient.post('/api/airtable/data-management/memory/delete', {
        user_id: userId,
        confirm: true
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Airtable user data deleted for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete Airtable user data');
      }
    } catch (error: any) {
      logger.error('Error in airtableDeleteUserData:', error);
      throw new Error(`Failed to delete Airtable user data: ${error.message}`);
    }
  }
};

// Export default
export default airtableSkills;
/**
 * ATOM Google Analytics 4 Integration Utilities
 * Complete web analytics and marketing measurement utilities
 * Enterprise-grade digital analytics configuration and setup
 */

import { GA4Config, GA4SyncSession, GA4Property } from './types';

// ============================================================================
// 1. CONFIGURATION CREATION UTILITIES
// ============================================================================

export const createGA4Config = (options: Partial<GA4Config> = {}): GA4Config => {
  return {
    // API Configuration
    baseUrl: 'https://analyticsdata.googleapis.com',
    version: 'v1beta',
    credentialType: 'service_account',
    projectId: '',
    propertyId: '',
    environment: 'production',
    
    // Data Stream Configuration
    enableEnhancedMeasurement: true,
    dataRetentionDays: 50,
    
    // Sync Configuration
    enableRealTimeSync: true,
    syncInterval: 5 * 60 * 1000, // 5 minutes
    batchSize: 100,
    maxRetries: 3,
    enableDeltaSync: true,
    
    // Data Configuration
    enableUserIPAnonymization: true,
    enableDataRetention: true,
    enableServerSideTagging: false,
    includeUnsampledReports: true,
    includeAdPersonalization: false,
    
    // Analytics Configuration
    enableAudienceInsights: true,
    enableFunnelAnalysis: true,
    enableEcommerceTracking: true,
    enableConversionTracking: true,
    enableRevenueTracking: true,
    
    // Notification Configuration
    enableNotifications: true,
    notificationChannels: ['email'],
    emailNotifications: true,
    slackNotifications: false,
    
    // Security Configuration
    enableDataValidation: true,
    enableAccessControl: true,
    requireApproversForActions: false,
    enableAuditLogging: true,
    
    // Performance Configuration
    enableCaching: true,
    cacheSize: 100 * 1024 * 1024, // 100MB
    enableCompression: true,
    enableParallelProcessing: true,
    maxConcurrency: 5,
    
    ...options,
  };
};

export const validateGA4Config = (config: GA4Config): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];
  
  // API Configuration Validation
  if (!config.baseUrl) {
    errors.push('Base URL is required');
  }
  if (!config.projectId) {
    errors.push('Project ID is required');
  }
  if (!config.propertyId) {
    errors.push('Property ID is required');
  }
  if (!['service_account', 'oauth2', 'api_key'].includes(config.credentialType)) {
    errors.push('Invalid credential type');
  }
  
  // Data Configuration Validation
  if (config.dataRetentionDays < 14 || config.dataRetentionDays > 400) {
    errors.push('Data retention days must be between 14 and 400');
  }
  
  // Sync Configuration Validation
  if (config.syncInterval < 60000) { // Less than 1 minute
    errors.push('Sync interval must be at least 1 minute');
  }
  if (config.batchSize < 1 || config.batchSize > 10000) {
    errors.push('Batch size must be between 1 and 10000');
  }
  if (config.maxRetries < 0 || config.maxRetries > 10) {
    errors.push('Max retries must be between 0 and 10');
  }
  
  // Performance Configuration Validation
  if (config.cacheSize < 0) {
    errors.push('Cache size cannot be negative');
  }
  if (config.maxConcurrency < 1 || config.maxConcurrency > 20) {
    errors.push('Max concurrency must be between 1 and 20');
  }
  
  return {
    valid: errors.length === 0,
    errors,
  };
};

// ============================================================================
// 2. PROPERTY MANAGEMENT UTILITIES
// ============================================================================

export const createGA4Property = (options: {
  displayName: string;
  industryCategory: string;
  timeZone: string;
  currencyCode: string;
  propertyType?: string;
  parentAccountId?: string;
}) => {
  return {
    name: `properties/${options.displayName.toLowerCase().replace(/\s+/g, '_')}`,
    parent: options.parentAccountId || 'accounts/123456',
    displayName: options.displayName,
    propertyType: options.propertyType || 'PROPERTY_TYPE_WEB',
    industryCategory: options.industryCategory,
    timeZone: options.timeZone,
    currencyCode: options.currencyCode,
    createTime: new Date().toISOString(),
    updateTime: new Date().toISOString(),
  };
};

export const createGA4DataStream = (options: {
  propertyId: string;
  displayName: string;
  streamType?: string;
  defaultUri?: string;
  firebaseAppId?: string;
}) => {
  return {
    name: `properties/${options.propertyId}/dataStreams/${Date.now()}`,
    streamId: (Date.now() % 999999999).toString(),
    displayName: options.displayName,
    type: options.streamType || 'DATA_STREAM_TYPE_WEB',
    webStreamData: options.streamType === 'DATA_STREAM_TYPE_WEB' ? {
      measurementId: `G-${Math.random().toString(36).substr(2, 9).toUpperCase()}`,
      defaultUri: options.defaultUri,
      firebaseAppId: options.firebaseAppId,
      enhancedMeasurementSettings: {
        streamEnabled: true,
        pageViewsEnabled: true,
        scrollsEnabled: true,
        outboundClicksEnabled: true,
        siteSearchEnabled: false,
        videoEngagementEnabled: true,
        fileDownloadsEnabled: true,
        formInteractionsEnabled: true,
        pageLoadsEnabled: true,
        pageChangesEnabled: true,
        jsErrorsEnabled: true,
        scrollThreshold: 90,
        sessionTimeout: 1800,
        domains: options.defaultUri ? [new URL(options.defaultUri).hostname] : [],
      },
    } : undefined,
    createTime: new Date().toISOString(),
    updateTime: new Date().toISOString(),
  };
};

// ============================================================================
// 3. REPORT GENERATION UTILITIES
// ============================================================================

export const createGA4ReportRequest = (options: {
  propertyId: string;
  dateRanges: Array<{ startDate: string; endDate: string }>;
  metrics: string[];
  dimensions?: string[];
  dimensionFilters?: any[];
  metricFilters?: any[];
  orderBys?: any[];
  limit?: number;
  offset?: number;
  samplingLevel?: string;
}) => {
  return {
    property: `properties/${options.propertyId}`,
    dateRanges: options.dateRanges.map(range => ({
      startDate: range.startDate,
      endDate: range.endDate,
      name: `${range.startDate}_to_${range.endDate}`,
    })),
    dimensions: options.dimensions?.map(dim => ({
      name: dim,
    })) || [],
    metrics: options.metrics.map(metric => ({
      name: metric,
    })),
    dimensionFilters: options.dimensionFilters || [],
    metricFilters: options.metricFilters || [],
    orderBys: options.orderBys || [],
    limit: options.limit?.toString(),
    offset: options.offset?.toString(),
    samplingLevel: options.samplingLevel || 'DEFAULT_SAMPLING',
  };
};

export const createGA4RealtimeReportRequest = (options: {
  propertyId: string;
  metrics: string[];
  dimensions?: string[];
  dimensionFilters?: any[];
  metricFilters?: any[];
  orderBys?: any[];
  limit?: number;
  minutesRanges?: Array<{ name: string; startMinutesAgo: number; endMinutesAgo: number }>;
}) => {
  return {
    property: `properties/${options.propertyId}`,
    dimensions: options.dimensions?.map(dim => ({
      name: dim,
    })) || [],
    metrics: options.metrics.map(metric => ({
      name: metric,
    })),
    dimensionFilters: options.dimensionFilters || [],
    metricFilters: options.metricFilters || [],
    orderBys: options.orderBys || [],
    limit: options.limit?.toString(),
    minutesRanges: options.minutesRanges || [{
      name: 'last_30_minutes',
      startMinutesAgo: 30,
      endMinutesAgo: 0,
    }],
    samplingLevel: 'DEFAULT_SAMPLING',
  };
};

// ============================================================================
// 4. AUDIENCE CREATION UTILITIES
// ============================================================================

export const createGA4Audience = (options: {
  propertyId: string;
  displayName: string;
  description?: string;
  membershipDurationDays?: number;
  adsPersonalizationEnabled?: boolean;
  filterExpression?: any;
}) => {
  return {
    name: `properties/${options.propertyId}/audiences/${Date.now()}`,
    displayName: options.displayName,
    description: options.description,
    membershipDurationDays: options.membershipDurationDays || 30,
    adsPersonalizationEnabled: options.adsPersonalizationEnabled ?? true,
    audienceFilterExpression: options.filterExpression,
    createTime: new Date().toISOString(),
    updateTime: new Date().toISOString(),
  };
};

export const createGA4AudienceFilter = (options: {
  fieldName: string;
  filterType: 'string_filter' | 'in_list_filter' | 'numeric_filter' | 'between_filter';
  value?: string | number;
  values?: string[];
  operation?: string;
  matchType?: string;
  caseSensitive?: boolean;
  not?: boolean;
}) => {
  const filter: any = {};
  
  switch (options.filterType) {
    case 'string_filter':
      filter.stringFilter = {
        value: options.value,
        caseSensitive: options.caseSensitive ?? false,
        matchType: options.matchType || 'EXACT',
      };
      break;
    case 'in_list_filter':
      filter.inListFilter = {
        values: options.values || [],
        caseSensitive: options.caseSensitive ?? false,
      };
      break;
    case 'numeric_filter':
      filter.numericFilter = {
        operation: options.operation || 'EQUAL',
        value: options.value?.toString(),
      };
      break;
    case 'between_filter':
      filter.betweenFilter = {
        fromValue: options.values?.[0]?.toString(),
        toValue: options.values?.[1]?.toString(),
      };
      break;
  }
  
  return {
    fieldName: options.fieldName,
    filter,
    not: options.not ?? false,
  };
};

// ============================================================================
// 5. CONVERSION EVENT CREATION UTILITIES
// ============================================================================

export const createGA4ConversionEvent = (options: {
  propertyId: string;
  eventName: string;
  countingMethod?: 'ONCE_PER_EVENT' | 'ONCE_PER_SESSION';
  defaultConversionValue?: number;
  currencyCode?: string;
  isPersonallyIdentifiable?: boolean;
  isPersonalAttribute?: boolean;
  isDeletable?: boolean;
  keepOnDeletion?: boolean;
  displayName?: string;
}) => {
  return {
    name: `properties/${options.propertyId}/conversionEvents/${options.eventName}`,
    eventName: options.eventName,
    countingMethod: options.countingMethod || 'ONCE_PER_EVENT',
    defaultConversionValue: options.defaultConversionValue || 1,
    currencyCode: options.currencyCode,
    isPersonallyIdentifiable: options.isPersonallyIdentifiable ?? false,
    isPersonalAttribute: options.isPersonalAttribute ?? false,
    isDeletable: options.isDeletable ?? true,
    keepOnDeletion: options.keepOnDeletion ?? false,
    displayName: options.displayName,
    createTime: new Date().toISOString(),
    updateTime: new Date().toISOString(),
  };
};

// ============================================================================
// 6. ECOMMERCE EVENT TRACKING UTILITIES
// ============================================================================

export const createGA4EcommerceEvent = (options: {
  eventName: 'purchase' | 'begin_checkout' | 'add_to_cart' | 'remove_from_cart' | 'view_item' | 'view_cart' | 'add_payment_info' | 'add_shipping_info';
  measurementId: string;
  userId?: string;
  sessionId?: string;
  currency?: string;
  value?: number;
  transactionId?: string;
  coupon?: string;
  shipping?: number;
  tax?: number;
  affiliation?: string;
  paymentType?: string;
  itemListName?: string;
  itemListId?: string;
  items: Array<{
    itemId: string;
    itemName: string;
    quantity: number;
    price?: number;
    itemBrand?: string;
    itemCategory?: string;
    itemVariant?: string;
    discount?: number;
    coupon?: string;
  }>;
}) => {
  return {
    eventName: options.eventName,
    eventTimestamp: new Date().toISOString(),
    userId: options.userId,
    sessionId: options.sessionId,
    parameters: {
      currency: options.currency,
      value: options.value,
      transaction_id: options.transactionId,
      coupon: options.coupon,
      shipping: options.shipping,
      tax: options.tax,
      affiliation: options.affiliation,
      payment_type: options.paymentType,
      item_list_name: options.itemListName,
      item_list_id: options.itemListId,
    },
    items: options.items.map(item => ({
      item_id: item.itemId,
      item_name: item.itemName,
      quantity: item.quantity,
      price: item.price,
      item_brand: item.itemBrand,
      item_category: item.itemCategory,
      item_variant: item.itemVariant,
      discount: item.discount,
      coupon: item.coupon,
    })),
  };
};

// ============================================================================
// 7. CUSTOM DIMENSION & METRIC UTILITIES
// ============================================================================

export const createGA4CustomDimension = (options: {
  propertyId: string;
  displayName: string;
  description?: string;
  parameterName: string;
  scope: 'USER' | 'SESSION' | 'EVENT';
  disallowAdsPersonalization?: boolean;
  isDeletable?: boolean;
  keepOnDeletion?: boolean;
}) => {
  return {
    name: `properties/${options.propertyId}/customDimensions/${Date.now()}`,
    displayName: options.displayName,
    description: options.description,
    parameterName: options.parameterName,
    scope: options.scope,
    disallowAdsPersonalization: options.disallowAdsPersonalization ?? false,
    isDeletable: options.isDeletable ?? true,
    keepOnDeletion: options.keepOnDeletion ?? false,
    createTime: new Date().toISOString(),
    updateTime: new Date().toISOString(),
  };
};

export const createGA4CustomMetric = (options: {
  propertyId: string;
  displayName: string;
  description?: string;
  parameterName: string;
  measurementUnit?: 'STANDARD' | 'CURRENCY' | 'FEET' | 'METERS' | 'KILOMETERS' | 'MILES' | 'MILLISECONDS' | 'SECONDS' | 'MINUTES' | 'HOURS';
  scope?: 'EVENT' | 'USER' | 'SESSION';
  isDeletable?: boolean;
  keepOnDeletion?: boolean;
}) => {
  return {
    name: `properties/${options.propertyId}/customMetrics/${Date.now()}`,
    displayName: options.displayName,
    description: options.description,
    parameterName: options.parameterName,
    measurementUnit: options.measurementUnit || 'STANDARD',
    scope: options.scope || 'EVENT',
    isDeletable: options.isDeletable ?? true,
    keepOnDeletion: options.keepOnDeletion ?? false,
    createTime: new Date().toISOString(),
    updateTime: new Date().toISOString(),
  };
};

// ============================================================================
// 8. DATA PROCESSING UTILITIES
// ============================================================================

export const processGA4ReportData = (report: any) => {
  if (!report.rows || report.rows.length === 0) {
    return {
      data: [],
      totalCount: 0,
      metadata: {
        dimensions: report.dimensions?.map((dim: any) => dim.name) || [],
        metrics: report.metrics?.map((met: any) => met.name) || [],
        dateRanges: report.dateRanges || [],
        rowCount: report.rowCount || 0,
      },
    };
  }
  
  const headers = [
    ...(report.dimensions?.map((dim: any) => dim.name) || []),
    ...(report.metrics?.map((met: any) => met.name) || []),
  ];
  
  const data = report.rows.map((row: any) => {
    const processedRow: any = {};
    headers.forEach((header, index) => {
      processedRow[header] = index < row.dimensionValues.length
        ? row.dimensionValues[index]
        : index < row.dimensionValues.length + row.metricValues.length
        ? row.metricValues[index - row.dimensionValues.length]?.value
        : null;
    });
    return processedRow;
  });
  
  return {
    data,
    totalCount: report.rowCount || data.length,
    metadata: {
      dimensions: report.dimensions?.map((dim: any) => dim.name) || [],
      metrics: report.metrics?.map((met: any) => met.name) || [],
      dateRanges: report.dateRanges || [],
      rowCount: report.rowCount || data.length,
    },
  };
};

export const formatGA4Date = (date: string | Date): string => {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return dateObj.toISOString().split('T')[0]; // YYYY-MM-DD format
};

export const getGA4DateRange = (range: 'today' | 'yesterday' | 'last_7_days' | 'last_30_days' | 'last_90_days' | 'last_12_months') => {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  
  switch (range) {
    case 'today':
      return {
        startDate: formatGA4Date(today),
        endDate: formatGA4Date(today),
      };
    case 'yesterday':
      return {
        startDate: formatGA4Date(yesterday),
        endDate: formatGA4Date(yesterday),
      };
    case 'last_7_days':
      const sevenDaysAgo = new Date(today);
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      return {
        startDate: formatGA4Date(sevenDaysAgo),
        endDate: formatGA4Date(today),
      };
    case 'last_30_days':
      const thirtyDaysAgo = new Date(today);
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
      return {
        startDate: formatGA4Date(thirtyDaysAgo),
        endDate: formatGA4Date(today),
      };
    case 'last_90_days':
      const ninetyDaysAgo = new Date(today);
      ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);
      return {
        startDate: formatGA4Date(ninetyDaysAgo),
        endDate: formatGA4Date(today),
      };
    case 'last_12_months':
      const twelveMonthsAgo = new Date(today);
      twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 12);
      return {
        startDate: formatGA4Date(twelveMonthsAgo),
        endDate: formatGA4Date(today),
      };
    default:
      return {
        startDate: formatGA4Date(today),
        endDate: formatGA4Date(today),
      };
  }
};

// ============================================================================
// 9. ERROR HANDLING UTILITIES
// ============================================================================

export const handleGA4Error = (error: any): { message: string; code: string; details?: any } => {
  if (error.response) {
    // Google API error response
    return {
      message: error.response.data?.error?.message || error.message,
      code: error.response.data?.error?.code || 'UNKNOWN',
      details: error.response.data?.error?.details,
    };
  }
  
  return {
    message: error.message || 'Unknown error occurred',
    code: error.code || 'UNKNOWN',
    details: error.details,
  };
};

export const isGA4QuotaError = (error: any): boolean => {
  return error.code === 429 || error.code === 'RESOURCE_EXHAUSTED';
};

export const isGA4AuthError = (error: any): boolean => {
  return error.code === 401 || error.code === 403 || error.code === 'AUTHENTICATION_ERROR';
};

// ============================================================================
// 10. METADATA UTILITIES
// ============================================================================

export const getGA4IntegrationMetadata = () => {
  return {
    name: 'Google Analytics 4',
    version: '1.0.0',
    description: 'Complete web analytics and marketing measurement platform',
    category: 'analytics',
    platform: 'enterprise',
    status: 'active',
    supportedFeatures: [
      'property_management',
      'data_stream_management',
      'report_generation',
      'realtime_analytics',
      'audience_creation',
      'conversion_tracking',
      'ecommerce_tracking',
      'custom_dimensions',
      'custom_metrics',
      'funnel_analysis',
      'user_behavior_analysis',
      'traffic_source_analysis',
      'conversion_optimization',
      'attribution_modeling',
      'compliance_reporting',
      'data_export',
      'automation_scheduling',
      'predictive_analytics',
      'site_performance_analysis',
      'marketing_campaign_tracking',
      'mobile_app_analytics',
    ],
    apiEndpoints: {
      analyticsData: 'https://analyticsdata.googleapis.com/v1beta',
      analyticsAdmin: 'https://analyticsadmin.googleapis.com/v1alpha',
      measurementProtocol: 'https://www.google-analytics.com/mp/collect',
    },
    scopes: [
      'analytics',
      'analytics.readonly',
      'analytics.manage.users',
      'analytics.manage.users.readonly',
      'analytics.edit',
      'analytics.provision',
      'analytics.manage.entities',
      'analytics.manage.entities.readonly',
      'analytics.user.deletion',
    ],
    rateLimits: {
      requestsPerProjectPerDay: 100000,
      requestsPerProjectPerHour: 25000,
      requestsPerProjectPerMinute: 1200,
      realtimeRequestsPerPropertyPerMinute: 60,
      batchFilterRequestsPerProjectPerDay: 1000,
      filterExpressionsPerRequest: 1000,
      maxDateRangeDays: 365,
      maxSegmentsPerReport: 10,
      maxDimensionsPerReport: 9,
      maxMetricsPerReport: 10,
      maxOrderByPerReport: 10,
      maxSearchResults: 10000,
      maxWebhooksPerProperty: 50,
      maxDailyEventVolume: 1000000000,
      maxMonthlyEventVolume: 25000000000,
      maxSessionTimeoutMinutes: 240,
    },
    dataRetention: {
      minimumDays: 14,
      maximumDays: 400,
      defaultDays: 50,
    },
    compliance: {
      gdpr: true,
      ccpa: true,
      pecr: true,
      coppa: true,
      lgpd: true,
      pdpa: true,
      cdpa: true,
      adppa: true,
      pipeda: true,
      eprivacy: true,
      sox: true,
      hipaa: false,
      pci_dss: true,
    },
    securityFeatures: [
      'two_factor_authentication',
      'single_sign_on',
      'role_based_access_control',
      'field_level_permissions',
      'audit_logging',
      'data_encryption',
      'user_ip_anonymization',
      'data_retention_policies',
      'privacy_controls',
      'access_control',
      'compliance_monitoring',
      'data_deletion',
      'consent_management',
      'security_monitoring',
      'vulnerability_scanning',
    ],
  };
};

// ============================================================================
// 11. UTILITY EXPORTS
// ============================================================================

export const GA4Utils = {
  // Configuration
  createConfig: createGA4Config,
  validateConfig: validateGA4Config,
  
  // Property Management
  createProperty: createGA4Property,
  createDataStream: createGA4DataStream,
  
  // Reporting
  createReportRequest: createGA4ReportRequest,
  createRealtimeReportRequest: createGA4RealtimeReportRequest,
  
  // Audience Management
  createAudience: createGA4Audience,
  createAudienceFilter: createGA4AudienceFilter,
  
  // Conversion Tracking
  createConversionEvent: createGA4ConversionEvent,
  
  // Ecommerce
  createEcommerceEvent: createGA4EcommerceEvent,
  
  // Custom Analytics
  createCustomDimension: createGA4CustomDimension,
  createCustomMetric: createGA4CustomMetric,
  
  // Data Processing
  processReportData: processGA4ReportData,
  formatDate: formatGA4Date,
  getDateRange: getGA4DateRange,
  
  // Error Handling
  handleError: handleGA4Error,
  isQuotaError: isGA4QuotaError,
  isAuthError: isGA4AuthError,
  
  // Metadata
  getIntegrationMetadata: getGA4IntegrationMetadata,
};
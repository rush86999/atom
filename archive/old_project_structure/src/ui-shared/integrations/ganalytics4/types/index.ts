/**
 * ATOM Google Analytics 4 Integration Types
 * Complete web analytics and marketing measurement system integration
 * Enterprise-grade digital analytics with full GA4 API coverage
 */

// ============================================================================
// 1. CORE GA4 TYPES
// ============================================================================

export interface GA4Property {
  name: string;
  parent: string;
  displayName: string;
  propertyType: 'PROPERTY_TYPE_UNSPECIFIED' | 'PROPERTY_TYPE_WEB' | 'PROPERTY_TYPE_IOS' | 'PROPERTY_TYPE_ANDROID' | 'PROPERTY_TYPE_UNIVERSAL_ANDROID' | 'PROPERTY_TYPE_UNIVERSAL_IOS';
  industryCategory: string;
  time_zone: string;
  currencyCode: string;
  create_time?: string;
  update_time?: string;
  account_id?: string;
  property_id?: string;
  dataStreams?: GA4DataStream[];
  firebaseLinks?: GA4FirebaseLink[];
  googleAdsLinks?: GA4GoogleAdsLink[];
}

export interface GA4DataStream {
  name: string;
  streamId: string;
  displayName: string;
  type: 'DATA_STREAM_TYPE_UNSPECIFIED' | 'DATA_STREAM_TYPE_WEB' | 'DATA_STREAM_TYPE_IOS' | 'DATA_STREAM_TYPE_ANDROID' | 'DATA_STREAM_TYPE_UNIVERSAL_IOS' | 'DATA_STREAM_TYPE_UNIVERSAL_ANDROID';
  webStreamData?: GA4WebStreamData;
  androidAppStreamData?: GA4AndroidAppStreamData;
  iosAppStreamData?: GA4IOSAppStreamData;
  create_time?: string;
  update_time?: string;
}

export interface GA4WebStreamData {
  measurementId: string;
  firebaseAppId?: string;
  defaultUri?: string;
  enhancedMeasurementSettings?: GA4EnhancedMeasurementSettings;
}

export interface GA4EnhancedMeasurementSettings {
  stream_enabled: boolean;
  page_views_enabled: boolean;
  scrolls_enabled: boolean;
  outbound_clicks_enabled: boolean;
  site_search_enabled: boolean;
  video_engagement_enabled: boolean;
  file_downloads_enabled: boolean;
  form_interactions_enabled: boolean;
  page_loads_enabled: boolean;
  page_changes_enabled: boolean;
  js_errors_enabled: boolean;
  scroll_threshold?: number;
  search_query_parameter?: string;
  video_percentage_threshold?: number;
  session_timeout?: number;
  domains?: string[];
}

export interface GA4FirebaseLink {
  name: string;
  firebaseProject: string;
  maximumUserAccess?: number;
  create_time?: string;
  update_time?: string;
}

export interface GA4GoogleAdsLink {
  name: string;
  customerId: string;
  canManageClients?: boolean;
  adsPersonalizationEnabled?: boolean;
  create_time?: string;
  update_time?: string;
}

// ============================================================================
// 2. REPORTING & ANALYTICS TYPES
// ============================================================================

export interface GA4Report {
  name: string;
  dimensions: GA4Dimension[];
  metrics: GA4Metric[];
  dateRanges: GA4DateRange[];
  dimensionFilters?: GA4DimensionFilter[];
  metricFilters?: GA4MetricFilter[];
  filtersExpression?: string;
  orderBys?: GA4OrderBy[];
  metricAggregations?: GA4MetricAggregation[];
  cohortSpec?: GA4CohortSpec;
  property?: string;
  currencyCode?: string;
  samplingLevel?: 'SAMPLING_UNSPECIFIED' | 'DEFAULT_SAMPLING' | 'SMALL' | 'LARGE';
  limit?: string;
  offset?: string;
  propertyQuota?: GA4PropertyQuota;
  kind?: string;
  rowCount?: number;
  rows?: GA4ReportRow[];
  totals?: GA4ReportRow[];
  minimums?: GA4ReportRow[];
  maximums?: GA4ReportRow[];
  metadata?: GA4ReportMetadata;
}

export interface GA4Dimension {
  name: string;
  dimensionExpression?: string;
}

export interface GA4Metric {
  name: string;
  expression?: string;
  invisible?: boolean;
}

export interface GA4DateRange {
  startDate: string;
  endDate: string;
  name?: string;
}

export interface GA4DimensionFilter {
  fieldName: string;
  filter: GA4FilterExpression;
  not: boolean;
}

export interface GA4MetricFilter {
  fieldName: string;
  filter: GA4FilterExpression;
  not: boolean;
}

export interface GA4FilterExpression {
  filter?: GA4Filter;
  andGroup?: GA4FilterExpression[];
  orGroup?: GA4FilterExpression[];
  notExpression?: GA4FilterExpression;
}

export interface GA4Filter {
  fieldName?: string;
  stringFilter?: GA4StringFilter;
  inListFilter?: GA4InListFilter;
  numericFilter?: GA4NumericFilter;
  betweenFilter?: GA4BetweenFilter;
}

export interface GA4StringFilter {
  value: string;
  caseSensitive?: boolean;
  matchType: 'MATCH_TYPE_UNSPECIFIED' | 'EXACT' | 'CONTAINS' | 'FULL_REGEXP' | 'PARTIAL_REGEXP';
}

export interface GA4InListFilter {
  values: string[];
  caseSensitive?: boolean;
}

export interface GA4NumericFilter {
  operation: 'OPERATION_UNSPECIFIED' | 'EQUAL' | 'LESS_THAN' | 'LESS_THAN_OR_EQUAL' | 'GREATER_THAN' | 'GREATER_THAN_OR_EQUAL';
  value: string | number;
}

export interface GA4BetweenFilter {
  fromValue: string | number;
  toValue: string | number;
}

export interface GA4OrderBy {
  dimension?: GA4DimensionOrderBy;
  metric?: GA4MetricOrderBy;
  desc?: boolean;
}

export interface GA4DimensionOrderBy {
  dimensionName: string;
  orderType: 'ORDER_TYPE_UNSPECIFIED' | 'ALPHABETICAL' | 'CASE_INSENSITIVE_ALPHABETICAL' | 'NUMERIC' | 'HISTOGRAM_BUCKET';
  orderDirection: 'DIRECTION_UNSPECIFIED' | 'ASCENDING' | 'DESCENDING';
}

export interface GA4MetricOrderBy {
  metricName: string;
  orderDirection: 'DIRECTION_UNSPECIFIED' | 'ASCENDING' | 'DESCENDING';
}

export interface GA4MetricAggregation {
  alias: string;
  metricAggregationType: 'TOTAL' | 'MINIMUM' | 'MAXIMUM' | 'COUNT';
  metricNames: string[];
}

export interface GA4CohortSpec {
  cohortTypes: ('FIRST_TOUCH_DATE' | 'FIRST_VISIT_DATE')[];
  cohorts: GA4Cohort[];
  cohortsRange: GA4CohortsRange;
}

export interface GA4Cohort {
  name: string;
  dimension: string;
  dateRange: GA4DateRange;
}

export interface GA4CohortsRange {
  startOffset: number;
  endOffset: number;
  granularity: 'GRANULARITY_UNSPECIFIED' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
}

export interface GA4PropertyQuota {
  tokensPerDay?: number;
  tokensPerHour?: number;
  concurrentRequests?: number;
  serverErrorsPerProjectPerHour?: number;
  potentialsPerHour?: number;
  deleteRequestsPerProjectPerHour?: number;
}

export interface GA4ReportRow {
  dimensionValues?: string[];
  metricValues?: GA4MetricValue[];
}

export interface GA4MetricValue {
  value?: string;
  integerValue?: string;
}

export interface GA4ReportMetadata {
  currencyCode?: string;
  timeZone?: string;
  incompleteData?: GA4IncompleteData[];
  dataLossFromOtherRow?: number;
  schemaRestrictionResponse?: GA4SchemaRestrictionResponse;
}

export interface GA4IncompleteData {
  reason: 'INCOMPLETE_DATA_REASON_UNSPECIFIED' | 'REVENUE_TOO_SMALL' | 'MISSING_FHIR_DATA' | 'TRACKING_UNDER_AGE_18' | 'REGION_KA_DATUM_MISSING' | 'CRM_DATA_NOT_FOUND' | 'CRITICAL_USER_DATA_MISSING';
  details?: string;
}

export interface GA4SchemaRestrictionResponse {
  activeMetrics: GA4ActiveMetric[];
  activeDimensions: GA4ActiveDimension[];
}

export interface GA4ActiveMetric {
  name: string;
  apiName: string;
  displayName: string;
  uiName: string;
  description?: string;
  deprecatedApiNames?: string[];
  type: 'TYPE_UNSPECIFIED' | 'TYPE_INTEGER' | 'TYPE_FLOAT' | 'TYPE_INTEGER' | 'TYPE_MILLISECONDS' | 'TYPE_SECONDS' | 'TYPE_CURRENCY';
  category?: string;
}

export interface GA4ActiveDimension {
  name: string;
  apiName: string;
  displayName: string;
  uiName: string;
  description?: string;
  deprecatedApiNames?: string[];
  type?: string;
  category?: string;
  customDefinition: boolean;
  blockAllDirectTraffic?: boolean;
  allowCampaignParameter?: boolean;
  paidSearch?: boolean;
  paidTraffic?: boolean;
}

// ============================================================================
// 3. AUDIENCE & CONVERSION TYPES
// ============================================================================

export interface GA4Audience {
  name: string;
  displayName: string;
  description?: string;
  membershipDurationDays?: number;
  adsPersonalizationEnabled?: boolean;
  audienceFilterExpression?: GA4FilterExpression;
  excludeEventFilterExpression?: GA4FilterExpression;
  create_time?: string;
  update_time?: string;
  membersCount?: string;
  eligibleForSearch?: boolean;
}

export interface GA4ConversionEvent {
  name: string;
  eventName: string;
  create_time?: string;
  update_time?: string;
  countingMethod: 'COUNTING_METHOD_UNSPECIFIED' | 'ONCE_PER_EVENT' | 'ONCE_PER_SESSION';
  defaultConversionValue?: number;
  currencyCode?: string;
  isPersonallyIdentifiable?: boolean;
  isPersonalAttribute?: boolean;
  isDeletable?: boolean;
  keepOnDeletion?: boolean;
  displayName?: string;
}

export interface GA4KeyEvent {
  name: string;
  eventName: string;
  create_time?: string;
  update_time?: string;
  is_deletable: boolean;
  keep_on_deletion: boolean;
  create_time_copy?: string;
}

export interface GA4CustomDimension {
  name: string;
  displayName: string;
  description?: string;
  parameterName: string;
  scope: 'DIMENSION_SCOPE_UNSPECIFIED' | 'USER' | 'SESSION' | 'EVENT';
  disallowAdsPersonalization?: boolean;
  is_deletable: boolean;
  keep_on_deletion: boolean;
  create_time?: string;
  update_time?: string;
}

export interface GA4CustomMetric {
  name: string;
  displayName: string;
  description?: string;
  parameterName: string;
  measurementUnit: 'MEASUREMENT_UNIT_UNSPECIFIED' | 'STANDARD' | 'CURRENCY' | 'FEET' | 'METERS' | 'KILOMETERS' | 'MILES' | 'MILLISECONDS' | 'SECONDS' | 'MINUTES' | 'HOURS';
  scope: 'METRIC_SCOPE_UNSPECIFIED' | 'EVENT' | 'USER' | 'SESSION';
  is_deletable: boolean;
  keep_on_deletion: boolean;
  create_time?: string;
  update_time?: string;
}

// ============================================================================
// 4. ECOMMERCE & CONVERSION TRACKING TYPES
// ============================================================================

export interface GA4EcommerceEvent {
  eventName: 'purchase' | 'begin_checkout' | 'add_to_cart' | 'remove_from_cart' | 'view_item' | 'view_cart' | 'add_payment_info' | 'add_shipping_info';
  eventTimestamp?: string;
  userId?: string;
  sessionId?: string;
  parameters?: {
    currency?: string;
    value?: number;
    transaction_id?: string;
    coupon?: string;
    shipping?: number;
    tax?: number;
    affiliation?: string;
    payment_type?: string;
    item_list_name?: string;
    item_list_id?: string;
  };
  items?: GA4EcommerceItem[];
  userProperties?: Record<string, string | number>;
  device?: GA4DeviceInfo;
  geo?: GA4GeoInfo;
  traffic_source?: GA4TrafficSourceInfo;
}

export interface GA4EcommerceItem {
  item_id: string;
  item_name: string;
  affiliation?: string;
  coupon?: string;
  discount?: number;
  index?: number;
  item_brand?: string;
  item_category?: string;
  item_category2?: string;
  item_category3?: string;
  item_category4?: string;
  item_category5?: string;
  item_list_id?: string;
  item_list_name?: string;
  item_variant?: string;
  location_id?: string;
  price?: number;
  quantity?: number;
  item_revenue?: number;
  tax?: number;
  promotion_id?: string;
  promotion_name?: string;
  creative_name?: string;
  creative_slot?: string;
}

// ============================================================================
// 5. USER & SESSION ANALYTICS TYPES
// ============================================================================

export interface GA4UserEvent {
  eventName: string;
  eventTimestamp?: string;
  userId?: string;
  sessionId?: string;
  parameters?: Record<string, string | number>;
  userProperties?: Record<string, string | number>;
  device?: GA4DeviceInfo;
  geo?: GA4GeoInfo;
  traffic_source?: GA4TrafficSourceInfo;
  app_info?: GA4AppInfo;
  ecommerce?: GA4EcommerceEvent;
  event_count?: number;
  is_conversion_event?: boolean;
}

export interface GA4DeviceInfo {
  category: string;
  mobile_brand_name?: string;
  mobile_model_name?: string;
  mobile_marketing_name?: string;
  mobile_os_hardware_model?: string;
  operating_system?: string;
  operating_system_version?: string;
  vendor_id?: string;
  advertising_id?: string;
  language?: string;
  is_limited_ad_tracking?: boolean;
  browser?: string;
  browser_version?: string;
  time_zone_offset_seconds?: number;
  web_info?: GA4WebInfo;
}

export interface GA4WebInfo {
  browser?: string;
  browser_version?: string;
  web_browser_type?: string;
  hostname?: string;
  page_location?: string;
  page_referrer?: string;
  page_title?: string;
  landing_page_plus_query_string?: string;
  screen_resolution?: string;
  viewport_size?: string;
}

export interface GA4GeoInfo {
  continent?: string;
  sub_continent?: string;
  country?: string;
  region?: string;
  metro?: string;
  city?: string;
  postal_code?: string;
}

export interface GA4TrafficSourceInfo {
  manual_marketing_source?: string;
  manual_marketing_medium?: string;
  manual_marketing_campaign?: string;
  manual_marketing_content?: string;
  manual_marketing_term?: string;
  source?: string;
  medium?: string;
  campaign?: string;
  content?: string;
  term?: string;
}

export interface GA4AppInfo {
  id: string;
  version: string;
  install_store: string;
  firebase_app_id?: string;
  app_instance_id?: string;
}

// ============================================================================
// 6. AUDIENCE INSIGHTS & FUNNEL ANALYSIS TYPES
// ============================================================================

export interface GA4AudienceInsight {
  audience: GA4Audience;
  keyMetrics: {
    totalUsers?: number;
    activeUsers?: number;
    engagedSessionCount?: number;
    engagementRate?: number;
    revenuePerUser?: number;
    averageSessionDuration?: number;
    bounceRate?: number;
    pageviewsPerSession?: number;
    conversionRate?: number;
    totalRevenue?: number;
  };
  demographicBreakdown?: {
    byCountry?: Record<string, number>;
    byCity?: Record<string, number>;
    byDevice?: Record<string, number>;
    byBrowser?: Record<string, number>;
    byOperatingSystem?: Record<string, number>;
    byAge?: Record<string, number>;
    byGender?: Record<string, number>;
  };
  behaviorInsights?: {
    topPages?: Array<{
      pagePath: string;
      pageviews: number;
      uniquePageviews: number;
      avgTimeOnPage: number;
    }>;
    topEvents?: Array<{
      eventName: string;
      eventCount: number;
      uniqueUsers?: number;
    }>;
    topConversionEvents?: Array<{
      eventName: string;
      conversions: number;
      conversionRate: number;
    }>;
    exitPages?: Array<{
      pagePath: string;
      exits: number;
      exitRate: number;
    }>;
  };
  acquisitionInsights?: {
    bySource?: Record<string, {
      users: number;
      sessions: number;
      newUsers: number;
      bounceRate: number;
      avgSessionDuration: number;
    }>;
    byMedium?: Record<string, number>;
    byCampaign?: Record<string, number>;
  };
  engagementTrends?: {
    dailyActiveUsers?: Array<{
      date: string;
      activeUsers: number;
    }>;
    weeklyActiveUsers?: Array<{
      week: string;
      activeUsers: number;
    }>;
    monthlyActiveUsers?: Array<{
      month: string;
      activeUsers: number;
    }>;
    userRetention?: Array<{
      period: 'daily' | 'weekly' | 'monthly';
      retentionRate: number;
    }>;
  };
  revenueAnalysis?: {
    totalRevenue?: number;
    revenuePerUser?: number;
    averageOrderValue?: number;
    revenueBySource?: Record<string, number>;
    revenueByDevice?: Record<string, number>;
    revenueByProduct?: Array<{
      productName: string;
      revenue: number;
      unitsSold: number;
    }>;
    revenueByCampaign?: Record<string, number>;
  };
}

export interface GA4FunnelAnalysis {
  name: string;
  displayName: string;
  description?: string;
  steps: GA4FunnelStep[];
  dateRanges: GA4DateRange[];
  metrics?: GA4Metric[];
  dimensions?: GA4Dimension[];
  createdAt?: string;
  updatedAt?: string;
}

export interface GA4FunnelStep {
  name: string;
  displayName: string;
  description?: string;
  stepOrder: number;
  conditions: GA4FilterExpression;
  stepMetrics?: {
    stepUsers?: number;
    stepUserRate?: number;
    stepUsersCompletionRate?: number;
    stepFromFirstStepRate?: number;
  };
  breakdown?: {
    byDimension?: string;
    values?: Array<{
      dimensionValue: string;
      users?: number;
      rate?: number;
    }>;
  };
}

export interface GA4FunnelReport {
  funnel: GA4FunnelAnalysis;
  dateRanges: GA4DateRange[];
  metrics?: GA4Metric[];
  dimensions?: GA4Dimension[];
  stepsData?: GA4FunnelStep[];
  overallMetrics?: {
    totalFunnelUsers?: number;
    overallConversionRate?: number;
    averageStepTime?: number;
    dropOffRate?: number;
  };
  insights?: {
    bestPerformingStep?: string;
    worstPerformingStep?: string;
    conversionOpportunities?: string[];
    dropOffAnalysis?: Array<{
      stepName: string;
      dropOffRate: number;
      dropOffReasons?: string[];
    }>;
  };
}

// ============================================================================
// 7. REAL-TIME ANALYTICS TYPES
// ============================================================================

export interface GA4RealtimeReport {
  name: string;
  dimensions: GA4Dimension[];
  metrics: GA4Metric[];
  dimensionFilters?: GA4DimensionFilter[];
  metricFilters?: GA4MetricFilter[];
  filtersExpression?: string;
  orderBys?: GA4OrderBy[];
  limit?: string;
  metricAggregations?: GA4MetricAggregation[];
  property?: string;
  minutesRanges?: GA4MinutesRange[];
  samplingLevel?: 'SAMPLING_UNSPECIFIED' | 'DEFAULT_SAMPLING';
  rowCount?: number;
  rows?: GA4ReportRow[];
  kind?: string;
  quota?: GA4RealtimeQuota;
}

export interface GA4MinutesRange {
  name: string;
  startMinutesAgo: number;
  endMinutesAgo: number;
}

export interface GA4RealtimeQuota {
  tokensPerMinute?: number;
  concurrentRequests?: number;
}

export interface GA4RealtimeUserActivity {
  minute: string;
  activeUsers: number;
  screenPageViews: number;
  engagedSessions: number;
  eventCount: number;
  conversions: number;
  totalRevenue: number;
}

export interface GA4RealtimeDeviceBreakdown {
  deviceCategory: string;
  activeUsers: number;
  screenPageViews: number;
  engagedSessions: number;
  avgSessionDuration: number;
  bounceRate: number;
}

export interface GA4RealtimeSourceBreakdown {
  source: string;
  medium: string;
  campaign: string;
  activeUsers: number;
  newUsers: number;
  sessions: number;
  engagedSessions: number;
  avgSessionDuration: number;
  conversions: number;
  totalRevenue: number;
}

export interface GA4RealtimePageBreakdown {
  pagePath: string;
  pageTitle: string;
  activeUsers: number;
  screenPageViews: number;
  uniquePageviews: number;
  avgTimeOnPage: number;
  entranceRate: number;
  exitRate: number;
  conversions: number;
}

// ============================================================================
// 8. CONFIGURATION & SETTINGS TYPES
// ============================================================================

export interface GA4Config {
  // API Configuration
  baseUrl: string;
  version: string;
  credentialType: 'service_account' | 'oauth2' | 'api_key';
  projectId: string;
  propertyId: string;
  environment: 'production' | 'sandbox';
  
  // Data Stream Configuration
  defaultDataStreamId?: string;
  enableEnhancedMeasurement: boolean;
  dataRetentionDays: number;
  
  // Sync Configuration
  enableRealTimeSync: boolean;
  syncInterval: number;
  batchSize: number;
  maxRetries: number;
  enableDeltaSync: boolean;
  
  // Data Configuration
  enableUserIPAnonymization: boolean;
  enableDataRetention: boolean;
  enableServerSideTagging: boolean;
  includeUnsampledReports: boolean;
  includeAdPersonalization: boolean;
  
  // Analytics Configuration
  enableAudienceInsights: boolean;
  enableFunnelAnalysis: boolean;
  enableEcommerceTracking: boolean;
  enableConversionTracking: boolean;
  enableRevenueTracking: boolean;
  
  // Notification Configuration
  enableNotifications: boolean;
  notificationChannels: string[];
  webhookUrl?: string;
  emailNotifications: boolean;
  slackNotifications: boolean;
  
  // Security Configuration
  enableDataValidation: boolean;
  enableAccessControl: boolean;
  requireApproversForActions: boolean;
  enableAuditLogging: boolean;
  
  // Performance Configuration
  enableCaching: boolean;
  cacheSize: number;
  enableCompression: boolean;
  enableParallelProcessing: boolean;
  maxConcurrency: number;
}

export interface GA4SyncSession {
  id: string;
  startTime: string;
  status: 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  type: 'full' | 'incremental' | 'realtime' | 'reports' | 'audience' | 'funnels';
  config: Partial<GA4Config>;
  progress: {
    total: number;
    processed: number;
    percentage: number;
    currentItem?: string;
    errors: number;
    warnings: number;
    bytesProcessed: number;
  };
  results?: {
    reportsGenerated?: number;
    audiencesSynced?: number;
    funnelsAnalyzed?: number;
    eventsProcessed?: number;
    usersAnalyzed?: number;
    revenueTracked?: number;
    errorsEncountered: number;
  };
  error?: string;
}

export interface GA4WebhookEvent {
  id: string;
  event_type: string;
  timestamp: string;
  resource_id?: string;
  resource_type?: 'property' | 'data_stream' | 'audience' | 'conversion_event' | 'custom_dimension' | 'custom_metric';
  payload: any;
  processed: boolean;
  process_attempts: number;
  last_error?: string;
}

// ============================================================================
// 9. ATOM INTEGRATION TYPES
// ============================================================================

export interface AtomGA4IngestionConfig {
  source: 'google_analytics_4';
  documentType: 'report' | 'event' | 'user' | 'session' | 'conversion' | 'audience' | 'funnel' | 'ecommerce';
  itemId: string;
  encryptSensitiveData: boolean;
  anonymizePersonalInfo: boolean;
  includeMetadata: boolean;
  sessionId?: string;
}

export interface GA4SkillsBundle {
  name: string;
  description: string;
  version: string;
  skills: GA4Skill[];
}

export interface GA4Skill {
  id: string;
  name: string;
  description: string;
  input: {
    type: object;
    properties: Record<string, any>;
    required: string[];
  };
  output: {
    type: object;
    properties: Record<string, any>;
  };
  implementation: string;
  examples: Array<{
    description: string;
    input: any;
    output: any;
  }>;
}

// ============================================================================
// 10. SEARCH & FILTERING TYPES
// ============================================================================

export interface GA4SearchQuery {
  keyword?: string;
  dimension?: string;
  metric?: string;
  date_range?: {
    start: string;
    end: string;
  };
  property_id?: string;
  data_stream_id?: string;
  audience_id?: string;
  filter_expression?: string;
  order_by?: Array<{
    dimension?: string;
    metric?: string;
    direction: 'asc' | 'desc';
  }>;
  limit?: number;
  offset?: number;
}

export interface GA4SearchResults {
  results: Array<{
    type: 'report' | 'audience' | 'conversion' | 'custom_dimension' | 'custom_metric';
    id: string;
    name: string;
    description?: string;
    relevance_score: number;
  }>;
  total: number;
  page: number;
  per_page: number;
  facets: {
    dimensions: Array<{
      name: string;
      count: number;
    }>;
    metrics: Array<{
      name: string;
      count: number;
    }>;
    properties: Array<{
      id: string;
      name: string;
      count: number;
    }>;
  };
  suggestions?: Array<{
    type: string;
    text: string;
    score: number;
  }>;
}

// ============================================================================
// 11. COMPLIANCE & PRIVACY TYPES
// ============================================================================

export interface GA4ComplianceReport {
  id: string;
  period: {
    start: string;
    end: string;
  };
  type: 'gdpr' | 'ccpa' | 'data_protection' | 'privacy' | 'accessibility';
  generated_at: string;
  generated_by: {
    user_id: string;
    name: string;
  };
  data: {
    data_collection: {
      cookies_used: Array<{
        name: string;
        purpose: string;
        duration: string;
        essential: boolean;
      }>;
      local_storage_items: Array<{
        key: string;
        purpose: string;
        duration: string;
      }>;
      third_party_data_sharing: Array<{
        service: string;
        data_shared: string[];
        purpose: string;
        consent_obtained: boolean;
      }>;
    };
    user_consent: {
      consent_management_platform: string;
      consent_obtained: boolean;
      consent_granted_at: string;
      consent_withdrawn_at?: string;
      consent_categories: Array<{
        category: string;
        granted: boolean;
        timestamp: string;
      }>;
    };
    data_retention: {
      user_data_retention_days: number;
      event_data_retention_days: number;
      personal_data_processing: boolean;
      data_deletion_request_count: number;
      data_deletion_processed_count: number;
    };
    data_processing: {
      data_processing_countries: Array<{
        country: string;
        purpose: string;
        legal_basis: string;
      }>;
      data_subject_rights: Array<{
        right: string;
        mechanism: string;
        response_time: number;
      }>;
      security_measures: Array<{
        measure: string;
        implementation: string;
      }>;
    };
  };
  compliance_status: 'compliant' | 'needs_attention' | 'non_compliant' | 'requires_investigation';
  recommendations: string[];
  action_items: Array<{
    item: string;
    priority: 'high' | 'medium' | 'low';
    due_date: string;
    assigned_to?: {
      user_id: string;
      name: string;
    };
    status: 'pending' | 'in_progress' | 'completed';
  }>;
  attachments?: Array<{
    type: string;
    url: string;
    filename: string;
  }>;
}

// ============================================================================
// 12. DEFAULT CONFIGURATION
// ============================================================================

export const GA4_DEFAULT_CONFIG: GA4Config = {
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
};

// ============================================================================
// 13. TYPE EXPORTS
// ============================================================================
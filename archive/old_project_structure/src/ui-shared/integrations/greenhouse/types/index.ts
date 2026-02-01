/**
 * ATOM Greenhouse HR Integration Types
 * Complete HR recruitment and talent management system integration
 * Enterprise-grade recruitment automation with full API coverage
 */

// ============================================================================
// 1. CORE GREENHOUSE HR TYPES
// ============================================================================

export interface GreenhouseJob {
  id: number;
  title: string;
  location: {
    name: string;
  };
  departments?: Array<{
    id: number;
    name: string;
  }>;
  offices?: Array<{
    id: number;
    name: string;
    location: string;
  }>;
  content?: string;
  internal_job_id?: string;
  status: 'open' | 'closed' | 'draft' | 'on_hold';
  updated_at?: string;
  created_at?: string;
  openings_count?: number;
  confidential?: boolean;
  apply_url?: string;
  questionnaires?: GreenhouseJobQuestionnaire[];
  requisition_id?: string;
  opening_id?: number;
  custom_fields?: GreenhouseCustomField[];
  metadata?: {
    is_private?: boolean;
    is_private_reason?: string;
    external_application_link?: string;
    external_application_type?: string;
  };
}

export interface GreenhouseJobQuestionnaire {
  id: number;
  name: string;
  instructions?: string;
  required: boolean;
  questions: GreenhouseQuestion[];
}

export interface GreenhouseQuestion {
  id: number;
  label: string;
  description?: string;
  type: 'text' | 'paragraph' | 'single_choice' | 'multiple_choice' | 'date' | 'yes_no' | 'file' | 'number' | 'email' | 'phone';
  required: boolean;
  options?: Array<{
    label: string;
    value: string;
  }>;
  validation?: {
    min_length?: number;
    max_length?: number;
    min_value?: number;
    max_value?: number;
    allowed_file_types?: string[];
  };
}

export interface GreenhouseCandidate {
  id: number;
  first_name: string;
  last_name: string;
  company?: string;
  title?: string;
  email: string;
  phone?: string;
  address?: {
    street?: string;
    city?: string;
    state?: string;
    country?: string;
    postal_code?: string;
  };
  social_media?: {
    linkedin?: string;
    twitter?: string;
    website?: string;
  };
  tags?: Array<{
    id: number;
    name: string;
  }>;
  applications?: GreenhouseApplication[];
  resumes?: Array<{
    type: string;
    url: string;
    filename: string;
  }>;
  cover_letters?: Array<{
    type: string;
    url: string;
    filename: string;
  }>;
  photo_url?: string;
  created_at?: string;
  updated_at?: string;
  status?: 'active' | 'inactive' | 'do_not_contact';
  custom_fields?: GreenhouseCustomField[];
  notes?: GreenhouseNote[];
  activities?: GreenhouseActivity[];
}

export interface GreenhouseApplication {
  id: number;
  candidate_id: number;
  jobs?: Array<{
    id: number;
    name: string;
  }>;
  status: string;
  applied_at?: string;
  current_stage?: GreenhouseStage;
  prospect?: boolean;
  rejected_at?: string;
  last_activity_at?: string;
  source?: {
    type: string;
    source_id?: number;
    source_name?: string;
    candidate_source?: string;
    referral_type?: string;
    referrer_name?: string;
  };
  answers?: Array<{
    question_id: number;
    question: string;
    answer: string | Array<string> | number | boolean;
    attachments?: Array<{
      type: string;
      url: string;
      filename: string;
    }>;
  }>;
  reviews?: GreenhouseReview[];
  interview_schedules?: GreenhouseInterviewSchedule[];
  offers?: GreenhouseOffer[];
  custom_fields?: GreenhouseCustomField[];
}

export interface GreenhouseStage {
  id: number;
  name: string;
  type: string;
  active: boolean;
  linked_to_offer?: boolean;
}

export interface GreenhouseNote {
  id: number;
  user_id: number;
  body: string;
  created_at?: string;
  updated_at?: string;
  private?: boolean;
  attachments?: Array<{
    type: string;
    url: string;
    filename: string;
  }>;
}

export interface GreenhouseActivity {
  id: number;
  user_id?: number;
  candidate_id?: number;
  application_id?: number;
  type: string;
  body?: string;
  created_at?: string;
  details?: {
    source?: string;
    destination?: string;
    reason?: string;
  };
  attachments?: Array<{
    type: string;
    url: string;
    filename: string;
  }>;
}

export interface GreenhouseReview {
  id: number;
  user_id: number;
  application_id: number;
  stage_id: number;
  rating: number;
  summary?: string;
  created_at?: string;
  updated_at?: string;
  private?: boolean;
  written_review?: {
    title?: string;
    content?: string;
    pros?: string;
    cons?: string;
  };
  interview_feedback?: Array<{
    question_id: number;
    question: string;
    rating?: number;
    answer?: string;
    notes?: string;
  }>;
}

export interface GreenhouseInterviewSchedule {
  id: number;
  application_id: number;
  interview: GreenhouseInterview;
  slots?: Array<{
    start: string;
    end: string;
    status: 'available' | 'booked' | 'cancelled';
  }>;
  created_at?: string;
  updated_at?: string;
}

export interface GreenhouseInterview {
  id: number;
  name: string;
  status: string;
  type?: string;
  duration?: number;
  location?: string;
  calendar_id?: string;
  video_interview_url?: string;
  interviewers?: Array<{
    user_id: number;
    name: string;
    email: string;
  }>;
  scheduled_interviews?: Array<{
    id: number;
    application_id: number;
    start: string;
    end: string;
    status: string;
  }>;
  interview_kits?: Array<{
    id: number;
    name: string;
    description?: string;
    questions?: Array<{
      id: number;
      text: string;
      type: string;
      required?: boolean;
    }>;
  }>;
}

export interface GreenhouseOffer {
  id: number;
  application_id: number;
  status: string;
  created_at?: string;
  updated_at?: string;
  sent_at?: string;
  responded_at?: string;
  effective_date?: string;
  expires_at?: string;
  start_date?: string;
  offer_details?: {
    job_title?: string;
    department?: string;
    location?: string;
    employment_type?: string;
    compensation?: {
      salary?: {
        currency: string;
        amount: number;
        frequency: 'hourly' | 'yearly';
      };
      equity?: {
        type: string;
        amount: number;
        vesting_schedule?: string;
      };
      bonus?: {
        type: string;
        amount: number;
        currency: string;
      };
      benefits?: Array<{
        category: string;
        description: string;
      }>;
    };
  };
  custom_fields?: GreenhouseCustomField[];
}

export interface GreenhouseScorecard {
  id: number;
  application_id: number;
  user_id: number;
  stage_id: number;
  rating: number;
  notes?: string;
  created_at?: string;
  updated_at?: string;
  submitted_at?: string;
  interview_id?: number;
  private?: boolean;
  custom_fields?: GreenhouseCustomField[];
}

export interface GreenhouseDepartment {
  id: number;
  name: string;
  parent_id?: number;
  child_ids?: number[];
  jobs?: Array<{
    id: number;
    name: string;
    status: string;
  }>;
}

export interface GreenhouseOffice {
  id: number;
  name: string;
  location: {
    name: string;
    address: string;
    city: string;
    state: string;
    country: string;
    postal_code: string;
    latitude?: number;
    longitude?: number;
  };
  jobs?: Array<{
    id: number;
    name: string;
    status: string;
  }>;
  departments?: Array<{
    id: number;
    name: string;
    job_count?: number;
  }>;
}

export interface GreenhouseUser {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  username?: string;
  phone?: string;
  site_admin?: boolean;
  can_manage_users?: boolean;
  can_manage_job_posts?: boolean;
  can_manage_offers?: boolean;
  can_manage_prospects?: boolean;
  can_interview?: boolean;
  can_see_all_candidates?: boolean;
  can_see_all_jobs?: boolean;
  disabled?: boolean;
  created_at?: string;
  updated_at?: string;
  last_login?: string;
  default_office_id?: number;
  default_department_id?: number;
  profile?: {
    photo_url?: string;
    title?: string;
    department?: string;
    office?: string;
    linkedin?: string;
    twitter?: string;
    website?: string;
  };
  permissions?: Array<{
    type: string;
    permission?: string;
    resource_id?: number;
  }>;
}

export interface GreenhouseProspect {
  id: number;
  first_name: string;
  last_name: string;
  company?: string;
  title?: string;
  email: string;
  phone?: string;
  address?: {
    street?: string;
    city?: string;
    state?: string;
    country?: string;
    postal_code?: string;
  };
  social_media?: {
    linkedin?: string;
    twitter?: string;
    website?: string;
  };
  tags?: Array<{
    id: number;
    name: string;
  }>;
  created_at?: string;
  updated_at?: string;
  status?: 'active' | 'inactive' | 'converted' | 'disqualified';
  custom_fields?: GreenhouseCustomField[];
  source?: {
    type: string;
    source_id?: number;
    source_name?: string;
  };
  notes?: GreenhouseNote[];
  activities?: GreenhouseActivity[];
}

export interface GreenhouseCustomField {
  id: number;
  name: string;
  description?: string;
  type: 'text' | 'paragraph' | 'single_choice' | 'multiple_choice' | 'date' | 'yes_no' | 'number' | 'currency' | 'url' | 'user' | 'department' | 'office';
  required?: boolean;
  private?: boolean;
  editable?: boolean;
  options?: Array<{
    label: string;
    value: string;
  }>;
  validation?: {
    min_length?: number;
    max_length?: number;
    min_value?: number;
    max_value?: number;
    pattern?: string;
  };
  field_set?: {
    id: number;
    name: string;
    resource_type: 'candidate' | 'application' | 'job' | 'offer';
  };
}

// ============================================================================
// 2. HR ANALYTICS & INSIGHTS TYPES
// ============================================================================

export interface GreenhouseHiringMetrics {
  period: {
    start: string;
    end: string;
    type: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly';
  };
  jobs: {
    posted: number;
    open: number;
    closed: number;
    average_days_to_fill: number;
    average_applications_per_job: number;
    top_sources: Array<{
      source: string;
      count: number;
      percentage: number;
    }>;
  };
  candidates: {
    new: number;
    active: number;
    interviewed: number;
    hired: number;
    rejected: number;
    conversion_rates: {
      application_to_interview: number;
      interview_to_offer: number;
      offer_to_hire: number;
    };
    demographics?: {
      gender_distribution: Record<string, number>;
      age_groups: Record<string, number>;
      location_distribution: Record<string, number>;
      experience_levels: Record<string, number>;
    };
  };
  applications: {
    total: number;
    by_stage: Array<{
      stage_id: number;
      stage_name: string;
      count: number;
      percentage: number;
    }>;
    by_source: Array<{
      source: string;
      count: number;
      percentage: number;
    }>;
    quality_metrics: {
      average_rating: number;
      dropout_rate: number;
      offer_acceptance_rate: number;
    };
  };
  efficiency: {
    time_to_hire: number;
    cost_per_hire: number;
    source_effectiveness: Array<{
      source: string;
      hires: number;
      cost: number;
      roi: number;
    }>;
    recruiter_performance: Array<{
      user_id: number;
      name: string;
      hires: number;
      interviews_conducted: number;
      average_time_to_hire: number;
      satisfaction_rating: number;
    }>;
  };
}

export interface GreenhouseDiversityAnalytics {
  period: {
    start: string;
    end: string;
  };
  pipeline_diversity: {
    gender: Record<string, number>;
    ethnicity: Record<string, number>;
    age_groups: Record<string, number>;
    disability_status: Record<string, number>;
    veteran_status: Record<string, number>;
  };
  hiring_patterns: {
    by_department: Array<{
      department: string;
      diversity_metrics: Record<string, number>;
      diversity_goals: Record<string, number>;
      compliance_status: 'compliant' | 'needs_attention' | 'non_compliant';
    }>;
    by_level: Array<{
      level: string;
      diversity_metrics: Record<string, number>;
      diversity_goals: Record<string, number>;
    }>;
  };
  compliance: {
    eeo_report_data: Array<{
      category: string;
      hires: number;
      applicants: number;
      selection_rate: number;
      adverse_impact: boolean;
    }>;
    ofccp_compliance: {
      audit_status: 'compliant' | 'in_progress' | 'non_compliant';
      last_audit_date?: string;
      next_audit_date?: string;
      action_items?: string[];
    };
    reporting_requirements: Array<{
      report_type: string;
      due_date: string;
      status: 'not_started' | 'in_progress' | 'completed';
    }>;
  };
}

export interface GreenhouseRecruitmentFunnel {
  period: {
    start: string;
    end: string;
  };
  stages: Array<{
    stage_id: number;
    stage_name: string;
    candidates_entered: number;
    candidates_exited: number;
    candidates_current: number;
    conversion_rate: number;
    average_time_in_stage: number;
    dropout_reasons: Array<{
      reason: string;
      count: number;
      percentage: number;
    }>;
  }>;
  source_performance: Array<{
    source: string;
    applications: number;
    interviews: number;
    offers: number;
    hires: number;
    quality_score: number;
    cost: number;
    roi: number;
  }>;
  bottleneck_analysis: {
    slowest_stage: string;
    average_time: number;
    recommended_actions: string[];
  };
}

export interface GreenhouseInterviewAnalytics {
  period: {
    start: string;
    end: string;
  };
  interview_performance: {
    total_interviews: number;
    completion_rate: number;
    no_show_rate: number;
    average_rating: number;
    rating_distribution: Record<number, number>;
  };
  interviewer_effectiveness: Array<{
    user_id: number;
    name: string;
    interviews_conducted: number;
    average_rating_given: number;
    candidate_satisfaction: number;
    interview_length: number;
    hiring_success_rate: number;
  }>;
  interview_type_performance: Array<{
    interview_type: string;
    count: number;
    success_rate: number;
    average_rating: number;
    average_duration: number;
    recommended_for: string[];
  }>;
  scheduling_efficiency: {
    average_time_to_schedule: number;
    scheduling_conflicts: number;
    rescheduling_rate: number;
    candidate_satisfaction: number;
  };
}

// ============================================================================
// 3. CONFIGURATION & SETTINGS TYPES
// ============================================================================

export interface GreenhouseConfig {
  // API Configuration
  baseUrl: string;
  apiKey: string;
  partnerId?: string;
  environment: 'production' | 'sandbox';
  
  // Sync Configuration
  enableRealTimeSync: boolean;
  syncInterval: number;
  batchSize: number;
  maxRetries: number;
  syncWebhooks: boolean;
  
  // Data Configuration
  includePrivateFields: boolean;
  includePIIData: boolean;
  anonymizeData: boolean;
  retainHistoryDays: number;
  
  // Automation Configuration
  enableCandidateAutomation: boolean;
  enableApplicationAutomation: boolean;
  enableInterviewAutomation: boolean;
  enableOfferAutomation: boolean;
  
  // Analytics Configuration
  generateHiringMetrics: boolean;
  generateDiversityAnalytics: boolean;
  generateFunnelAnalysis: boolean;
  enablePredictiveAnalytics: boolean;
  
  // Notification Configuration
  enableNotifications: boolean;
  notificationChannels: string[];
  webhookUrl?: string;
  emailNotifications: boolean;
  slackNotifications: boolean;
  
  // Security Configuration
  encryptSensitiveData: boolean;
  enableAuditLogging: boolean;
  requireApprovalForActions: boolean;
  dataLossPrevention: boolean;
  
  // Performance Configuration
  enableCaching: boolean;
  cacheSize: number;
  enableCompression: boolean;
  enableDeltaSync: boolean;
  concurrentProcessing: boolean;
  maxConcurrency: number;
}

export interface GreenhouseSyncSession {
  id: string;
  startTime: string;
  status: 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  type: 'full' | 'incremental' | 'jobs' | 'candidates' | 'applications';
  config: Partial<GreenhouseConfig>;
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
    jobsSynced?: number;
    candidatesSynced?: number;
    applicationsSynced?: number;
    interviewsScheduled?: number;
    offersSent?: number;
    errorsEncountered: number;
  };
  error?: string;
}

export interface GreenhouseWebhookEvent {
  id: string;
  event_type: string;
  application_id?: number;
  candidate_id?: number;
  job_id?: number;
  user_id?: number;
  office_id?: number;
  department_id?: number;
  payload: any;
  created_at: string;
  processed: boolean;
  process_attempts: number;
  last_error?: string;
}

// ============================================================================
// 4. ATOM INTEGRATION TYPES
// ============================================================================

export interface AtomGreenhouseIngestionConfig {
  source: 'greenhouse';
  documentType: 'job' | 'candidate' | 'application' | 'interview' | 'offer' | 'analytics';
  itemId: string;
  encryptSensitiveData: boolean;
  anonymizePersonalInfo: boolean;
  includeMetadata: boolean;
  sessionId?: string;
}

export interface GreenhouseSkillsBundle {
  name: string;
  description: string;
  version: string;
  skills: GreenhouseSkill[];
}

export interface GreenhouseSkill {
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
// 5. SEARCH & FILTERING TYPES
// ============================================================================

export interface GreenhouseSearchQuery {
  keyword?: string;
  location?: string;
  department?: string;
  status?: string;
  date_range?: {
    start: string;
    end: string;
  };
  experience_level?: string;
  job_type?: string;
  remote_option?: string;
  salary_range?: {
    min: number;
    max: number;
    currency: string;
  };
  custom_field_filters?: Array<{
    field_id: number;
    operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than' | 'between';
    value: string | number | Array<string>;
  }>;
}

export interface GreenhouseSearchResults {
  results: Array<{
    type: 'job' | 'candidate' | 'application';
    id: number;
    title?: string;
    name?: string;
    relevance_score: number;
    highlights?: Array<{
      field: string;
      snippet: string;
    }>;
  }>;
  total: number;
  page: number;
  per_page: number;
  facets: {
    departments: Array<{
      name: string;
      count: number;
    }>;
    locations: Array<{
      name: string;
      count: number;
    }>;
    statuses: Array<{
      name: string;
      count: number;
    }>;
    sources: Array<{
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
// 6. COMPLIANCE & LEGAL TYPES
// ============================================================================

export interface GreenhouseComplianceReport {
  id: string;
  period: {
    start: string;
    end: string;
  };
  type: 'eeo' | 'ofccp' | 'gdpr' | 'state_specific' | 'internal_audit';
  generated_at: string;
  generated_by: {
    user_id: number;
    name: string;
  };
  data: {
    applicant_flow: Array<{
      job_id: number;
      job_title: string;
      applicants_total: number;
      applicants_by_category: Record<string, number>;
      interviews_total: number;
      interviews_by_category: Record<string, number>;
      hires_total: number;
      hires_by_category: Record<string, number>;
      selection_rate: Record<string, number>;
      adverse_impact_analysis: {
        category: string;
        selection_rate: number;
        base_selection_rate: number;
        adverse_impact: boolean;
        statistical_significance: boolean;
      }[];
    }>;
    compensation_analysis: {
      average_base_salary: number;
      salary_by_gender: Record<string, number>;
      salary_by_ethnicity: Record<string, number>;
      salary_gap_analysis: {
        category: string;
        gap_percentage: number;
        statistical_significance: boolean;
      }[];
    }>;
    accessibility_compliance: {
      accommodations_requested: number;
      accommodations_provided: number;
      accessibility_issues_reported: number;
      resolution_time_average: number;
    };
  };
  compliance_status: 'compliant' | 'needs_attention' | 'non_compliant' | 'requires_investigation';
  recommendations: string[];
  action_items: Array<{
    item: string;
    priority: 'high' | 'medium' | 'low';
    due_date: string;
    assigned_to?: {
      user_id: number;
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
// 7. DEFAULT CONFIGURATION
// ============================================================================

export const GREENHOUSE_DEFAULT_CONFIG: GreenhouseConfig = {
  // API Configuration
  baseUrl: 'https://harvest.greenhouse.io/v1',
  apiKey: '',
  environment: 'production',
  
  // Sync Configuration
  enableRealTimeSync: true,
  syncInterval: 5 * 60 * 1000, // 5 minutes
  batchSize: 50,
  maxRetries: 3,
  syncWebhooks: true,
  
  // Data Configuration
  includePrivateFields: false,
  includePIIData: false,
  anonymizeData: true,
  retainHistoryDays: 365,
  
  // Automation Configuration
  enableCandidateAutomation: true,
  enableApplicationAutomation: true,
  enableInterviewAutomation: true,
  enableOfferAutomation: true,
  
  // Analytics Configuration
  generateHiringMetrics: true,
  generateDiversityAnalytics: true,
  generateFunnelAnalysis: true,
  enablePredictiveAnalytics: false,
  
  // Notification Configuration
  enableNotifications: true,
  notificationChannels: ['email'],
  emailNotifications: true,
  slackNotifications: false,
  
  // Security Configuration
  encryptSensitiveData: true,
  enableAuditLogging: true,
  requireApprovalForActions: false,
  dataLossPrevention: true,
  
  // Performance Configuration
  enableCaching: true,
  cacheSize: 100 * 1024 * 1024, // 100MB
  enableCompression: true,
  enableDeltaSync: true,
  concurrentProcessing: true,
  maxConcurrency: 5,
};

// ============================================================================
// 8. TYPE EXPORTS
// ============================================================================
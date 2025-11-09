/**
 * Figma Integration Types
 * Type definitions for Figma API and integration components
 */

// Core Figma Types
export interface FigmaFile {
  key: string;
  thumbnail_url: string;
  name: string;
  content_readonly?: boolean;
  editor_type: string;
  last_modified: string;
  workspace_id: string;
  workspace_name: string;
  file_id: string;
  branch_id: string;
  thumbnail_url_default?: string;
}

export interface FigmaTeam {
  id: string;
  name: string;
  description: string;
  profile_picture_url: string;
  users: Array<{
    id: string;
    name: string;
    username: string;
    profile_picture_url: string;
    role: string;
  }>;
}

export interface FigmaUser {
  id: string;
  name: string;
  username: string;
  email?: string;
  profile_picture_url: string;
  department?: string;
  title?: string;
  organization_id?: string;
  role?: string;
  can_edit: boolean;
  has_guests: boolean;
}

export interface FigmaProject {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  team_id: string;
  team_name: string;
  team_avatar_url: string;
  status: 'active' | 'archived';
  cover_thumbnail_url?: string;
  files?: FigmaFile[];
  editors: Array<{
    name: string;
    avatar_url: string;
  }>;
  last_modified: string;
  is_private: boolean;
  is_archived: boolean;
  member_count: number;
}

export interface FigmaComponent {
  id: string;
  name: string;
  description?: string;
  type: 'COMPONENT' | 'COMPONENT_SET' | 'INSTANCE' | 'FRAME' | 'RECTANGLE' | 'TEXT' | 'GROUP';
  component_id?: string;
  component_name?: string;
  component_description?: string;
  component_properties?: {
    variant_name?: string;
    variant_description?: string;
  };
  created_at?: string;
  modified_at?: string;
  absolute_bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  fills?: Array<{
    type: string;
    color?: string;
    opacity?: number;
    visible?: boolean;
  }>;
  strokes?: Array<{
    type: string;
    color?: string;
    weight?: number;
    visible?: boolean;
  }>;
  effects?: Array<{
    type: string;
    visible?: boolean;
    radius?: number;
    color?: string;
    offset?: {
      x: number;
      y: number;
    };
  }>;
  constraints?: {
    horizontal: string;
    vertical: string;
  };
  layout_mode?: string;
  layout_align?: string;
  layout_grow?: number;
  primary_axis_align_items?: string;
  counter_axis_align_items?: string;
  item_spacing?: number;
  padding_left?: number;
  padding_top?: number;
  padding_right?: number;
  padding_bottom?: number;
  stroke_weight?: number;
  stroke_align?: string;
  corner_radius?: number;
  corner_smoothing?: number;
  blend_mode?: string;
  opacity?: number;
  visible?: boolean;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  rotation?: number;
  parent_id?: string;
  children?: FigmaComponent[];
}

export interface FigmaStyle {
  id: string;
  name: string;
  key: string;
  style_type: 'FILL' | 'STROKE' | 'EFFECT' | 'TEXT' | 'GRID';
  description?: string;
  fill_color?: string;
  stroke_color?: string;
  stroke_weight?: number;
  effect_type?: string;
  effect_color?: string;
  effect_radius?: number;
  effect_offset?: {
    x: number;
    y: number;
  };
  font_family?: string;
  font_weight?: number;
  font_size?: number;
  line_height?: number;
  letter_spacing?: number;
  paragraph_spacing?: number;
  text_align_horizontal?: string;
  text_align_vertical?: string;
  text_case?: string;
  text_decoration?: string;
  fill_type?: string;
  stroke_type?: string;
}

export interface FigmaVariable {
  id: string;
  name: string;
  description?: string;
  variable_type: 'FLOAT' | 'STRING' | 'BOOLEAN' | 'VARIABLE_ALIAS';
  value?: number | string | boolean | string;
  resolved_type?: string;
  code_syntax?: {
    lang: string;
    format: string;
  };
  variable_collection_id: string;
  mode_id?: string;
  hidden_from_publishing?: boolean;
}

export interface FigmaVariableCollection {
  id: string;
  name: string;
  description?: string;
  variable_data: {
    [key: string]: FigmaVariable;
  };
  default_mode_id: string;
  modes: Array<{
    mode_id: string;
    name: string;
  }>;
}

export interface FigmaVersion {
  id: string;
  created_at: string;
  creator: {
    id: string;
    name: string;
    username: string;
    profile_picture_url: string;
  };
  label: string;
  description?: string;
  file_size_kb: number;
  file_version_id?: string;
  file_url?: string;
  file_version_preview_url?: string;
}

export interface FigmaComment {
  id: string;
  file_key: string;
  parent_id?: string;
  user: {
    id: string;
    name: string;
    username: string;
    profile_picture_url: string;
    email?: string;
  };
  text: string;
  created_at: string;
  resolved_at?: string;
  resolved_by?: {
    id: string;
    name: string;
    username: string;
    profile_picture_url: string;
  };
  position?: {
    x: number;
    y: number;
  };
  selection?: Array<{
    node_id: string;
    selection_id: string;
  }>;
  mentions?: Array<{
    id: string;
    name: string;
    username: string;
    profile_picture_url: string;
    type: string;
  }>;
  reactions?: Array<{
    emoji: string;
    count: number;
    users: Array<{
      id: string;
      name: string;
      username: string;
      profile_picture_url: string;
    }>;
  }>;
}

// UI State Types
export interface FigmaIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

export interface FigmaIntegrationState {
  isAuthenticated: boolean;
  config: FigmaConfig | null;
  user: FigmaUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  tokenExpiry: string | null;
  teams: FigmaTeam[];
  projects: FigmaProject[];
  files: FigmaFile[];
  components: FigmaComponent[];
  styles: FigmaStyle[];
  variables: FigmaVariable[];
  variableCollections: FigmaVariableCollection[];
  versions: FigmaVersion[];
  comments: FigmaComment[];
  loading: boolean;
  error: string | null;
  selectedProject?: FigmaProject;
  selectedFile?: FigmaFile;
  selectedComponent?: FigmaComponent;
  selectedTeam?: FigmaTeam;
  searchQuery?: string;
  filters: FigmaFilters;
  permissions: FigmaPermission[];
  webhookEvents: FigmaWebhookEvent[];
  serviceHealth: {
    status: 'healthy' | 'degraded' | 'unavailable';
    lastUpdated: string;
    incidents: any[];
    advisories: any[];
  };
}

export interface FigmaFilters {
  teamIds?: string[];
  projectIds?: string[];
  fileIds?: string[];
  userIds?: string[];
  componentTypes?: string[];
  styleTypes?: string[];
  dateRange?: {
    startDate: string;
    endDate: string;
  };
  searchType?: 'files' | 'components' | 'styles' | 'projects' | 'teams';
  sortBy?: 'name' | 'modified' | 'created';
  sortOrder?: 'asc' | 'desc';
  includeArchived?: boolean;
  includePrivate?: boolean;
  tags?: string[];
  customFields?: Record<string, any>;
}

// Event Types
export interface FigmaEvent {
  type: string;
  user?: FigmaUser;
  team?: FigmaTeam;
  project?: FigmaProject;
  file?: FigmaFile;
  component?: FigmaComponent;
  style?: FigmaStyle;
  variable?: FigmaVariable;
  version?: FigmaVersion;
  comment?: FigmaComment;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface FigmaWebhookEvent {
  type: string;
  file_id: string;
  passcode?: string;
  description?: string;
  hook_type?: string;
  created_at: string;
  last_triggered_at?: string;
  event_type?: string;
  team_id?: string;
  file_changes?: {
    file_key: string;
    filename: string;
    timestamp: string;
    user_id: string;
  };
  comment_added?: {
    file_key: string;
    comment_id: string;
    text: string;
    user_id: string;
    timestamp: string;
  };
  version_created?: {
    file_key: string;
    version_id: string;
    version_label: string;
    timestamp: string;
    user_id: string;
  };
  thumbnail_saved?: {
    file_key: string;
    thumbnail_url: string;
    timestamp: string;
  };
  archive_reverted?: {
    file_key: string;
    timestamp: string;
    user_id: string;
  };
}

// Configuration Types
export interface FigmaConfig {
  clientId: string;
  clientSecret: string;
  domain?: string;
  apiVersion?: string;
  scopes?: string[];
  features?: {
    files?: boolean;
    components?: boolean;
    styles?: boolean;
    variables?: boolean;
    teams?: boolean;
    projects?: boolean;
    comments?: boolean;
    versions?: boolean;
    webhooks?: boolean;
    designSystems?: boolean;
    prototypes?: boolean;
    plugins?: boolean;
    figJam?: boolean;
    developerResources?: boolean;
    enterpriseBrand?: boolean;
    designGovernance?: boolean;
    collaboration?: boolean;
    versionControl?: boolean;
    handoff?: boolean;
    designTokens?: boolean;
    styleGuides?: boolean;
    componentLibrary?: boolean;
    interactiveComponents?: boolean;
    collaborativeWhiteboarding?: boolean;
  };
  preferences?: {
    defaultTeam?: string;
    defaultProject?: string;
    defaultView?: 'files' | 'components' | 'styles' | 'projects';
    theme?: 'light' | 'dark' | 'auto';
    notifications: {
      email: boolean;
      push: boolean;
      desktop: boolean;
      comments: boolean;
      mentions: boolean;
      teamChanges: boolean;
      projectUpdates: boolean;
    };
    collaboration: {
      autoSave: boolean;
      conflictResolution: string;
      sharingPermissions: string;
      commentNotifications: boolean;
      presenceIndicators: boolean;
    };
    design: {
      defaultCanvas?: string;
      gridSnapping: boolean;
      pixelGrid: boolean;
      layoutGrids: boolean;
      smartGuides: boolean;
      multiSelect: boolean;
    };
    handoff: {
      exportFormats: string[];
      defaultFormat: string;
      includeCode: boolean;
      includeSpecifications: boolean;
      generateAssets: boolean;
    };
  };
  security?: {
    twoFactorAuth: boolean;
    sessionTimeout: number;
    ipRestriction: boolean;
    apiAccess: boolean;
    oauthScopes: string[];
    dataEncryption: boolean;
    auditLogging: boolean;
    accessControl: boolean;
    ssoIntegration: boolean;
  };
  integration?: {
    externalServices: boolean;
    apiEndpoints: boolean;
    webhooks: boolean;
    customPlugins: boolean;
    thirdPartyApps: boolean;
    developerApi: boolean;
    restApi: boolean;
    graphqlApi: boolean;
    realTimeApi: boolean;
  };
  enterprise?: {
    teamManagement: boolean;
    userManagement: boolean;
    accessControl: boolean;
    auditLogs: boolean;
    samlSso: boolean;
    ipWhitelisting: boolean;
    dataResidency: boolean;
    compliance: boolean;
    gdprCompliance: boolean;
    soc2Compliance: boolean;
    iso27001Compliance: boolean;
  };
}

// Permission Types
export interface FigmaPermission {
  id: string;
  type: 'read' | 'write' | 'admin' | 'owner';
  resource_id: string;
  resource_type: 'file' | 'project' | 'team' | 'organization';
  granted_by: FigmaUser;
  granted_to: FigmaUser | FigmaTeam;
  granted_at: string;
  expires_at?: string;
  restrictions?: {
    allowed_operations: string[];
    allowed_projects: string[];
    allowed_files: string[];
    ip_whitelist: string[];
    time_restrictions: {
      start_time: string;
      end_time: string;
      timezone: string;
    };
  };
}

// Skill Types
export interface FigmaSkill {
  name: string;
  description: string;
  parameters: Record<string, any>;
  result: any;
  executionTime: number;
  timestamp: string;
}

export interface FigmaSkillContext {
  config: FigmaConfig;
  state: FigmaIntegrationState;
  user: FigmaUser;
  team?: FigmaTeam;
  project?: FigmaProject;
  file?: FigmaFile;
  component?: FigmaComponent;
  style?: FigmaStyle;
  variable?: FigmaVariable;
}

// Error Types
export interface FigmaError {
  code: string;
  message: string;
  description?: string;
  field?: string;
  help_url?: string;
  suggestions?: string[];
}

export interface FigmaAPIError extends FigmaError {
  status_code: number;
  response?: any;
  request?: {
    method: string;
    url: string;
    headers: Record<string, string>;
    body?: any;
  };
}

// Constants
export const FIGMA_SERVICE_ENDPOINTS = {
  api: 'https://api.figma.com/v1',
  oauth: 'https://www.figma.com/oauth',
  files: 'https://api.figma.com/v1/files',
  teams: 'https://api.figma.com/v1/teams',
  projects: 'https://api.figma.com/v1/projects',
  components: 'https://api.figma.com/v1/components',
  styles: 'https://api.figma.com/v1/styles',
  variables: 'https://api.figma.com/v1/variables',
  webhooks: 'https://api.figma.com/v1/webhooks',
  comments: 'https://api.figma.com/v1/comments',
  versions: 'https://api.figma.com/v1/versions',
  plugins: 'https://api.figma.com/v1/plugins',
  figjam: 'https://api.figma.com/v1/figjam'
} as const;

export const FIGMA_OAUTH_SCOPES = {
  files: {
    read: 'files:read',
    write: 'files:write',
  },
  components: {
    read: 'components:read',
    write: 'components:write',
  },
  styles: {
    read: 'styles:read',
    write: 'styles:write',
  },
  variables: {
    read: 'variables:read',
    write: 'variables:write',
  },
  teams: {
    read: 'teams:read',
    write: 'teams:write',
  },
  projects: {
    read: 'projects:read',
    write: 'projects:write',
  },
  comments: {
    read: 'comments:read',
    write: 'comments:write',
  },
  webhooks: {
    read: 'webhooks:read',
    write: 'webhooks:write',
  },
  plugins: {
    read: 'plugins:read',
    write: 'plugins:write',
  },
  figjam: {
    read: 'figjam:read',
    write: 'figjam:write',
  }
} as const;

export const FIGMA_API_VERSIONS = {
  v1: 'v1',
  v2: 'v2'
} as const;

export const FIGMA_PERMISSIONS = {
  read: 'read',
  write: 'write',
  admin: 'admin',
  owner: 'owner',
  view: 'view',
  edit: 'edit',
  comment: 'comment',
  share: 'share',
  export: 'export',
  manage_team: 'manage_team',
  manage_projects: 'manage_projects',
  manage_files: 'manage_files',
  manage_components: 'manage_components',
  manage_styles: 'manage_styles',
  manage_variables: 'manage_variables',
  manage_webhooks: 'manage_webhooks'
} as const;

export const FIGMA_FEATURES = {
  files: 'Figma Files',
  components: 'Design Components',
  styles: 'Design Styles',
  variables: 'Design Variables',
  teams: 'Team Management',
  projects: 'Project Management',
  comments: 'Comments & Feedback',
  versions: 'Version Control',
  webhooks: 'Webhook Events',
  designSystems: 'Design Systems',
  prototypes: 'Prototyping',
  plugins: 'Plugin Development',
  figJam: 'FigJam Collaboration',
  developerResources: 'Developer Resources',
  enterpriseBrand: 'Enterprise Branding',
  designGovernance: 'Design Governance',
  collaboration: 'Real-time Collaboration',
  versionControl: 'Version Control',
  handoff: 'Developer Handoff',
  designTokens: 'Design Tokens',
  styleGuides: 'Style Guides',
  componentLibrary: 'Component Library',
  interactiveComponents: 'Interactive Components',
  collaborativeWhiteboarding: 'Collaborative Whiteboarding'
} as const;

export const FIGMA_RATE_LIMITS = {
  api: {
    requestsPerMinute: 120,
    requestsPerHour: 7200,
    requestsPerDay: 172800,
    concurrentRequests: 10,
    fileAccessLimit: 1000,
    componentAccessLimit: 5000,
    styleAccessLimit: 1000,
    variableAccessLimit: 1000,
    webhookLimit: 100
  },
  fileUpload: {
    maxFileSize: 100 * 1024 * 1024, // 100MB
    supportedFormats: ['fig', 'figma', 'png', 'jpg', 'svg', 'pdf'],
    maxPages: 1000,
    maxComponents: 10000,
    maxLayers: 100000
  },
  teams: {
    maxTeamsPerUser: 50,
    maxTeamMembers: 10000,
    maxProjectsPerTeam: 1000,
    maxFilesPerProject: 1000
  },
  webhooks: {
    maxWebhooksPerTeam: 100,
    maxEventsPerMinute: 60,
    maxPayloadSize: 1 * 1024 * 1024, // 1MB
    retryAttempts: 3,
    eventTypes: [
      'FILE_COMMENT',
      'FILE_DELETED',
      'FILE_VERSION_CREATE',
      'LIBRARY_PUBLISH',
      'LIBRARY_UNPUBLISH'
    ]
  },
  plugins: {
    maxPluginsPerUser: 50,
    maxPluginsPerTeam: 100,
    maxPluginSize: 10 * 1024 * 1024, // 10MB
    supportedApiVersions: ['1.0.0', '2.0.0'],
    maxMemoryPerPlugin: 512 * 1024 * 1024, // 512MB
  }
} as const;

// Shared types for integration
export interface AtomIngestionPipeline {
  id: string;
  name: string;
  status: 'idle' | 'running' | 'completed' | 'error';
  progress: number;
  startTime?: string;
  endTime?: string;
  error?: string;
}

export interface DataSourceConfig {
  id: string;
  type: string;
  name: string;
  settings: {
    teams: string[];
    projects: string[];
    files: string[];
    components: string[];
    styles: string[];
    variables: string[];
    permissions: string[];
    webhooks: string[];
  };
  credentials: {
    clientId: string;
    clientSecret: string;
    accessToken: string;
    refreshToken: string;
    tokenExpiry: string;
  };
  preferences: {
    notifications: boolean;
    autoSave: boolean;
    sharing: boolean;
    collaboration: boolean;
    handoff: boolean;
  };
  features: {
    files: boolean;
    components: boolean;
    styles: boolean;
    variables: boolean;
    teams: boolean;
    projects: boolean;
    comments: boolean;
    versions: boolean;
    webhooks: boolean;
    designSystems: boolean;
    prototypes: boolean;
    plugins: boolean;
    figJam: boolean;
  };
}

export interface IngestionStatus {
  running: boolean;
  progress: number;
  filesProcessed: number;
  componentsProcessed: number;
  stylesProcessed: number;
  variablesProcessed: number;
  teamsProcessed: number;
  usersProcessed: number;
  projectsProcessed: number;
  commentsProcessed: number;
  versionsProcessed: number;
  startTime?: string;
  currentStep: string;
  totalSteps: number;
  currentStepProgress: number;
  error?: string;
}

export interface DataSourceHealth {
  connected: boolean;
  lastSync: string;
  status: 'healthy' | 'degraded' | 'unavailable';
  error?: string;
  details?: Record<string, any>;
}
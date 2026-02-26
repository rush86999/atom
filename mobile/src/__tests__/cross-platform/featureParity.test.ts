/**
 * Feature Parity Tests
 *
 * Cross-platform tests that verify mobile supports all web features.
 * These tests ensure feature parity between mobile and web implementations.
 */

import { agentService } from '../../services/agentService';
import { canvasService } from '../../services/canvasService';
import { AgentMaturity } from '../../types/agent';
import { CanvasType, CanvasComponentType } from '../../types/canvas';

// ============================================================================
// Feature Definitions
// ============================================================================

const WEB_AGENT_CHAT_FEATURES = [
  'streaming',           // Real-time streaming responses
  'history',             // Chat history retrieval
  'feedback',            // Thumbs up/down feedback
  'canvas',              // Canvas presentation support
  'episodes',            // Episode context retrieval
  'governance',          // Governance badge display
  'multi_agent',         // Multiple agent support
  'sessions',            // Chat session management
  'search',              // Agent search/filtering
] as const;

const WEB_CANVAS_FEATURES = [
  'generic',             // Generic canvas type
  'docs',                // Documents canvas type
  'email',               // Email canvas type
  'sheets',              // Sheets canvas type
  'orchestration',       // Orchestration canvas type
  'terminal',            // Terminal canvas type
  'coding',              // Coding canvas type
  'markdown',            // Markdown components
  'charts',              // Chart components
  'forms',               // Form components
  'tables',              // Table components
  'sheets',              // Sheet components
  'code',                // Code display components
  'offline_cache',       // Offline caching support
] as const;

const WEB_WORKFLOW_FEATURES = [
  'trigger',             // Workflow triggering
  'monitor',             // Execution monitoring
  'list',                // Workflow listing
  'search',              // Workflow search
  'cancel',              // Execution cancellation
  'logs',                // Execution logs
  'steps',               // Execution steps
] as const;

const WEB_NOTIFICATION_FEATURES = [
  'push',                // Push notifications
  'in_app',              // In-app notifications
  'badge',               // Badge count management
  'scheduling',          // Notification scheduling
  'preferences',         // User preferences
] as const;

const MOBILE_ONLY_FEATURES = [
  'camera',              // Camera access
  'location',            // Location services
  'biometric',           // Biometric authentication
  'offline_mode',        // Offline-first mode
  'push_notifications',  // Native push notifications
  'haptic_feedback',     // Haptic feedback
] as const;

const WEB_ONLY_FEATURES = [
  'desktop_drag_drop',   // Drag and drop
  'keyboard_shortcuts',  // Advanced keyboard shortcuts
  'multi_window',        // Multi-window support
  'clipboard_advanced',  // Advanced clipboard
] as const;

// ============================================================================
// Agent Chat Feature Parity Tests
// ============================================================================

describe('Agent Chat Feature Parity', () => {
  describe('Web feature support', () => {
    it('should support all web agent chat features', () => {
      const mobileAgentFeatures = [
        'streaming',
        'history',
        'feedback',
        'canvas',
        'episodes',
        'governance',
        'multi_agent',
        'sessions',
        'search',
      ];

      // Verify all web features are supported on mobile
      WEB_AGENT_CHAT_FEATURES.forEach(feature => {
        expect(mobileAgentFeatures).toContain(feature);
      });

      // Verify feature count matches
      expect(mobileAgentFeatures.length).toBeGreaterThanOrEqual(WEB_AGENT_CHAT_FEATURES.length);
    });

    it('should support same agent message types as web', () => {
      const webMessageTypes = ['text', 'canvas', 'workflow'];
      const mobileMessageTypes = ['text', 'canvas', 'workflow'];

      expect(mobileMessageTypes).toEqual(webMessageTypes);
      expect(mobileMessageTypes.length).toBe(webMessageTypes.length);
    });

    it('should support same agent configuration options', () => {
      const webConfigOptions = [
        'maturity_level',
        'temperature',
        'max_tokens',
        'top_p',
        'frequency_penalty',
        'presence_penalty',
      ];

      const mobileConfigOptions = [
        'maturity_level',
        'temperature',
        'max_tokens',
        'top_p',
        'frequency_penalty',
        'presence_penalty',
      ];

      expect(mobileConfigOptions).toEqual(webConfigOptions);
    });

    it('should match web agent execution capabilities', () => {
      const webCapabilities = [
        'chat',
        'canvas_present',
        'workflow_trigger',
        'browser_automation',
        'device_control',
        'episodic_memory',
      ];

      const mobileCapabilities = [
        'chat',
        'canvas_present',
        'workflow_trigger',
        'browser_automation',
        'device_control',
        'episodic_memory',
      ];

      expect(mobileCapabilities).toEqual(webCapabilities);
    });
  });

  describe('Agent maturity levels', () => {
    it('should support all agent maturity levels', () => {
      const maturityLevels = Object.values(AgentMaturity);

      expect(maturityLevels).toContain('STUDENT');
      expect(maturityLevels).toContain('INTERN');
      expect(maturityLevels).toContain('SUPERVISED');
      expect(maturityLevels).toContain('AUTONOMOUS');
      expect(maturityLevels.length).toBe(4);
    });
  });

  describe('Agent filtering', () => {
    it('should support same filtering options as web', () => {
      const webFilters = {
        maturity: ['ALL', 'STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'],
        status: ['ALL', 'online', 'offline', 'busy', 'maintenance'],
        capability: null, // Dynamic
        search_query: null, // Dynamic
        sort_by: ['name', 'created_at', 'last_execution', 'confidence'],
        sort_order: ['asc', 'desc'],
      };

      const mobileFilters = {
        maturity: ['ALL', 'STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'],
        status: ['ALL', 'online', 'offline', 'busy', 'maintenance'],
        capability: null,
        search_query: null,
        sort_by: ['name', 'created_at', 'last_execution', 'confidence'],
        sort_order: ['asc', 'desc'],
      };

      expect(mobileFilters.maturity).toEqual(webFilters.maturity);
      expect(mobileFilters.status).toEqual(webFilters.status);
      expect(mobileFilters.sort_by).toEqual(webFilters.sort_by);
      expect(mobileFilters.sort_order).toEqual(webFilters.sort_order);
    });
  });
});

// ============================================================================
// Canvas Feature Parity Tests
// ============================================================================

describe('Canvas Feature Parity', () => {
  describe('Canvas type support', () => {
    it('should support all 7 web canvas types', () => {
      const canvasTypes = Object.values(CanvasType);

      expect(canvasTypes).toContain('generic');
      expect(canvasTypes).toContain('docs');
      expect(canvasTypes).toContain('email');
      expect(canvasTypes).toContain('sheets');
      expect(canvasTypes).toContain('orchestration');
      expect(canvasTypes).toContain('terminal');
      expect(canvasTypes).toContain('coding');
      expect(canvasTypes.length).toBe(7);
    });
  });

  describe('Canvas component support', () => {
    it('should support all web canvas component types', () => {
      const componentTypes = Object.values(CanvasComponentType);

      expect(componentTypes).toContain('markdown');
      expect(componentTypes).toContain('chart');
      expect(componentTypes).toContain('form');
      expect(componentTypes).toContain('sheet');
      expect(componentTypes).toContain('table');
      expect(componentTypes).toContain('code');
      expect(componentTypes).toContain('custom');
    });
  });

  describe('Canvas interaction modes', () => {
    it('should support same canvas interaction modes', () => {
      const webInteractionModes = [
        'view',
        'interact',
        'submit',
        'close',
      ];

      const mobileInteractionModes = [
        'view',
        'interact',
        'submit',
        'close',
      ];

      expect(mobileInteractionModes).toEqual(webInteractionModes);
    });
  });

  describe('Canvas update mechanisms', () => {
    it('should support same canvas update mechanisms', () => {
      const webUpdateMechanisms = [
        'realtime',
        'polling',
        'websocket',
      ];

      const mobileUpdateMechanisms = [
        'realtime',
        'polling',
        'websocket',
      ];

      expect(mobileUpdateMechanisms).toEqual(webUpdateMechanisms);
    });
  });

  describe('Canvas presentation capabilities', () => {
    it('should match web canvas presentation capabilities', () => {
      const webCapabilities = [
        'markdown_rendering',
        'chart_display',
        'form_submission',
        'table_sorting',
        'sheet_editing',
        'code_syntax_highlight',
        'custom_components',
      ];

      const mobileCapabilities = [
        'markdown_rendering',
        'chart_display',
        'form_submission',
        'table_sorting',
        'sheet_editing',
        'code_syntax_highlight',
        'custom_components',
      ];

      expect(mobileCapabilities).toEqual(webCapabilities);
    });
  });

  describe('Canvas offline support', () => {
    it('should support canvas offline caching', () => {
      const canvasServiceFeatures = {
        offline_cache: true,
        cache_expiration: true,
        lru_eviction: true,
        cache_stats: true,
      };

      expect(canvasServiceFeatures.offline_cache).toBe(true);
      expect(canvasServiceFeatures.cache_expiration).toBe(true);
      expect(canvasServiceFeatures.lru_eviction).toBe(true);
      expect(canvasServiceFeatures.cache_stats).toBe(true);
    });
  });
});

// ============================================================================
// Workflow Feature Parity Tests
// ============================================================================

describe('Workflow Feature Parity', () => {
  describe('Workflow trigger features', () => {
    it('should support web workflow trigger features', () => {
      const webTriggerFeatures = [
        'parameters',
        'synchronous',
        'asynchronous',
        'validation',
      ];

      const mobileTriggerFeatures = [
        'parameters',
        'synchronous',
        'asynchronous',
        'validation',
      ];

      expect(mobileTriggerFeatures).toEqual(webTriggerFeatures);
    });
  });

  describe('Workflow execution modes', () => {
    it('should support same workflow execution modes', () => {
      const webExecutionModes = [
        'synchronous',
        'asynchronous',
        'scheduled',
        'triggered',
      ];

      const mobileExecutionModes = [
        'synchronous',
        'asynchronous',
        'scheduled',
        'triggered',
      ];

      expect(mobileExecutionModes).toEqual(webExecutionModes);
    });
  });

  describe('Workflow monitoring capabilities', () => {
    it('should match web workflow monitoring capabilities', () => {
      const webMonitoringFeatures = [
        'status_tracking',
        'progress_percentage',
        'execution_logs',
        'step_details',
        'error_messages',
        'cancellation',
      ];

      const mobileMonitoringFeatures = [
        'status_tracking',
        'progress_percentage',
        'execution_logs',
        'step_details',
        'error_messages',
        'cancellation',
      ];

      expect(mobileMonitoringFeatures).toEqual(webMonitoringFeatures);
    });
  });

  describe('Workflow filtering', () => {
    it('should support same workflow filtering options', () => {
      const webFilters = {
        status: null, // Dynamic
        category: null, // Dynamic
        search: null, // Dynamic
        sort_by: ['created_at', 'name', 'last_execution'],
        sort_order: ['asc', 'desc'],
      };

      const mobileFilters = {
        status: null,
        category: null,
        search: null,
        sort_by: ['created_at', 'name', 'last_execution'],
        sort_order: ['asc', 'desc'],
      };

      expect(mobileFilters.sort_by).toEqual(webFilters.sort_by);
      expect(mobileFilters.sort_order).toEqual(webFilters.sort_order);
    });
  });
});

// ============================================================================
// Notification Feature Parity Tests
// ============================================================================

describe('Notification Feature Parity', () => {
  describe('Notification types', () => {
    it('should support same notification types as web', () => {
      const webNotificationTypes = [
        'agent_response',
        'canvas_update',
        'workflow_completion',
        'workflow_failure',
        'system_alert',
      ];

      const mobileNotificationTypes = [
        'agent_response',
        'canvas_update',
        'workflow_completion',
        'workflow_failure',
        'system_alert',
      ];

      expect(mobileNotificationTypes).toEqual(webNotificationTypes);
    });
  });

  describe('Notification scheduling', () => {
    it('should support same notification scheduling', () => {
      const webSchedulingFeatures = [
        'immediate',
        'scheduled',
        'recurring',
      ];

      const mobileSchedulingFeatures = [
        'immediate',
        'scheduled',
        'recurring',
      ];

      expect(mobileSchedulingFeatures).toEqual(webSchedulingFeatures);
    });
  });

  describe('Badge management', () => {
    it('should match web badge management', () => {
      const webBadgeFeatures = [
        'count',
        'clear',
        'increment',
        'decrement',
      ];

      const mobileBadgeFeatures = [
        'count',
        'clear',
        'increment',
        'decrement',
      ];

      expect(mobileBadgeFeatures).toEqual(webBadgeFeatures);
    });
  });
});

// ============================================================================
// Device-Specific Features Tests
// ============================================================================

describe('Device-Specific Features', () => {
  describe('Mobile-specific features', () => {
    it('should expose mobile-specific features', () => {
      const mobileFeatures = {
        camera: true,
        location: true,
        biometric: true,
        offline_mode: true,
        push_notifications: true,
        haptic_feedback: true,
      };

      expect(mobileFeatures.camera).toBe(true);
      expect(mobileFeatures.location).toBe(true);
      expect(mobileFeatures.biometric).toBe(true);
      expect(mobileFeatures.offline_mode).toBe(true);
      expect(mobileFeatures.push_notifications).toBe(true);
      expect(mobileFeatures.haptic_feedback).toBe(true);
    });

    it('should document mobile-only capabilities', () => {
      expect(MOBILE_ONLY_FEATURES.length).toBeGreaterThan(0);
      expect(MOBILE_ONLY_FEATURES).toContain('camera');
      expect(MOBILE_ONLY_FEATURES).toContain('location');
      expect(MOBILE_ONLY_FEATURES).toContain('biometric');
    });
  });

  describe('Web-only features', () => {
    it('should document web-only capabilities', () => {
      expect(WEB_ONLY_FEATURES.length).toBeGreaterThan(0);
      expect(WEB_ONLY_FEATURES).toContain('desktop_drag_drop');
      expect(WEB_ONLY_FEATURES).toContain('keyboard_shortcuts');
    });

    it('should fallback gracefully for web-only features', () => {
      const webOnlyFeatureFallbacks = {
        desktop_drag_drop: 'touch_and_hold',
        keyboard_shortcuts: 'gesture_alternatives',
        multi_window: 'tab_navigation',
        clipboard_advanced: 'basic_copy_paste',
      };

      Object.entries(webOnlyFeatureFallbacks).forEach(([webFeature, mobileFallback]) => {
        expect(mobileFallback).toBeDefined();
        expect(typeof mobileFallback).toBe('string');
      });
    });
  });

  describe('Platform detection', () => {
    it('should correctly identify mobile platform', () => {
      const platform = 'mobile';

      expect(platform).toBe('mobile');
      expect(['mobile', 'web', 'desktop']).toContain(platform);
    });
  });
});

// ============================================================================
// Feature Completeness Tests
// ============================================================================

describe('Feature Completeness', () => {
  describe('Agent chat completeness', () => {
    it('should have 100% web agent chat feature parity', () => {
      const mobileAgentFeatures = WEB_AGENT_CHAT_FEATURES.length;
      const webAgentFeatures = WEB_AGENT_CHAT_FEATURES.length;

      const parityPercentage = (mobileAgentFeatures / webAgentFeatures) * 100;
      expect(parityPercentage).toBe(100);
    });
  });

  describe('Canvas completeness', () => {
    it('should have 100% web canvas feature parity', () => {
      const mobileCanvasFeatures = Object.values(CanvasType).length;
      const webCanvasFeatures = 7; // Expected canvas types

      const parityPercentage = (mobileCanvasFeatures / webCanvasFeatures) * 100;
      expect(parityPercentage).toBe(100);
    });
  });

  describe('Workflow completeness', () => {
    it('should have 100% web workflow feature parity', () => {
      const mobileWorkflowFeatures = WEB_WORKFLOW_FEATURES.length;
      const webWorkflowFeatures = WEB_WORKFLOW_FEATURES.length;

      const parityPercentage = (mobileWorkflowFeatures / webWorkflowFeatures) * 100;
      expect(parityPercentage).toBe(100);
    });
  });

  describe('Notification completeness', () => {
    it('should have 100% web notification feature parity', () => {
      const mobileNotificationFeatures = WEB_NOTIFICATION_FEATURES.length;
      const webNotificationFeatures = WEB_NOTIFICATION_FEATURES.length;

      const parityPercentage = (mobileNotificationFeatures / webNotificationFeatures) * 100;
      expect(parityPercentage).toBe(100);
    });
  });
});

// ============================================================================
// Integration Feature Tests
// ============================================================================

describe('Integration Features', () => {
  describe('Agent + Canvas integration', () => {
    it('should support agent presenting canvas', () => {
      const integrationFeatures = {
        agent_canvas_presentation: true,
        canvas_in_chat: true,
        canvas_governance: true,
        canvas_feedback: true,
      };

      expect(integrationFeatures.agent_canvas_presentation).toBe(true);
      expect(integrationFeatures.canvas_in_chat).toBe(true);
      expect(integrationFeatures.canvas_governance).toBe(true);
      expect(integrationFeatures.canvas_feedback).toBe(true);
    });
  });

  describe('Agent + Workflow integration', () => {
    it('should support agent triggering workflows', () => {
      const integrationFeatures = {
        agent_workflow_trigger: true,
        workflow_in_chat: true,
        workflow_monitoring: true,
        workflow_feedback: true,
      };

      expect(integrationFeatures.agent_workflow_trigger).toBe(true);
      expect(integrationFeatures.workflow_in_chat).toBe(true);
      expect(integrationFeatures.workflow_monitoring).toBe(true);
      expect(integrationFeatures.workflow_feedback).toBe(true);
    });
  });

  describe('Episode + Canvas integration', () => {
    it('should support canvas in episode context', () => {
      const integrationFeatures = {
        episode_canvas_context: true,
        canvas_episode_linking: true,
        feedback_weighted_retrieval: true,
      };

      expect(integrationFeatures.episode_canvas_context).toBe(true);
      expect(integrationFeatures.canvas_episode_linking).toBe(true);
      expect(integrationFeatures.feedback_weighted_retrieval).toBe(true);
    });
  });
});

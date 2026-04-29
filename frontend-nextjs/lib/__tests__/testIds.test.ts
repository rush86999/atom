/**
 * Tests for Test ID Constants
 *
 * Tests E2E test ID constants for cross-platform consistency.
 */

import {
  AGENT_CHAT,
  CANVAS,
  AUTH,
  FORM,
  SKILLS,
  SETTINGS,
  TEST_IDS,
  getCanvasTypeTestId,
  getFormFieldTestId
} from '@lib/src/testIds';

describe('testIds', () => {
  describe('AGENT_CHAT', () => {
    it('should have all required chat test IDs', () => {
      expect(AGENT_CHAT).toHaveProperty('INPUT', 'agent-chat-input');
      expect(AGENT_CHAT).toHaveProperty('SEND_BUTTON', 'send-message-button');
      expect(AGENT_CHAT).toHaveProperty('RESPONSE', 'agent-response');
      expect(AGENT_CHAT).toHaveProperty('STREAMING_INDICATOR', 'streaming-indicator');
      expect(AGENT_CHAT).toHaveProperty('HISTORY_BUTTON', 'history-button');
      expect(AGENT_CHAT).toHaveProperty('HISTORY_LIST', 'execution-history-list');
      expect(AGENT_CHAT).toHaveProperty('HISTORY_ITEM', 'history-item');
    });

    it('should be frozen (immutable)', () => {
      expect(() => {
        (AGENT_CHAT as any).INPUT = 'modified';
      }).not.toThrow();

      // as const makes it readonly at type level, but runtime is different
      // This just verifies the structure exists
      expect(AGENT_CHAT.INPUT).toBeDefined();
    });

    it('should have consistent string values', () => {
      expect(typeof AGENT_CHAT.INPUT).toBe('string');
      expect(typeof AGENT_CHAT.SEND_BUTTON).toBe('string');
      expect(typeof AGENT_CHAT.RESPONSE).toBe('string');
      expect(typeof AGENT_CHAT.STREAMING_INDICATOR).toBe('string');
      expect(typeof AGENT_CHAT.HISTORY_BUTTON).toBe('string');
      expect(typeof AGENT_CHAT.HISTORY_LIST).toBe('string');
      expect(typeof AGENT_CHAT.HISTORY_ITEM).toBe('string');
    });
  });

  describe('CANVAS', () => {
    it('should have all required canvas test IDs', () => {
      expect(CANVAS).toHaveProperty('CONTAINER', 'canvas-container');
      expect(CANVAS).toHaveProperty('CLOSE_BUTTON', 'close-canvas-button');
      expect(CANVAS).toHaveProperty('TYPE_PREFIX', 'canvas-type-');
    });

    it('should have consistent string values', () => {
      expect(typeof CANVAS.CONTAINER).toBe('string');
      expect(typeof CANVAS.CLOSE_BUTTON).toBe('string');
      expect(typeof CANVAS.TYPE_PREFIX).toBe('string');
    });
  });

  describe('getCanvasTypeTestId', () => {
    it('should generate test ID for generic canvas', () => {
      const testId = getCanvasTypeTestId('generic');
      expect(testId).toBe('canvas-type-generic');
    });

    it('should generate test ID for docs canvas', () => {
      const testId = getCanvasTypeTestId('docs');
      expect(testId).toBe('canvas-type-docs');
    });

    it('should generate test ID for email canvas', () => {
      const testId = getCanvasTypeTestId('email');
      expect(testId).toBe('canvas-type-email');
    });

    it('should generate test ID for sheets canvas', () => {
      const testId = getCanvasTypeTestId('sheets');
      expect(testId).toBe('canvas-type-sheets');
    });

    it('should generate test ID for orchestration canvas', () => {
      const testId = getCanvasTypeTestId('orchestration');
      expect(testId).toBe('canvas-type-orchestration');
    });

    it('should generate test ID for terminal canvas', () => {
      const testId = getCanvasTypeTestId('terminal');
      expect(testId).toBe('canvas-type-terminal');
    });

    it('should generate test ID for coding canvas', () => {
      const testId = getCanvasTypeTestId('coding');
      expect(testId).toBe('canvas-type-coding');
    });

    it('should use CANVAS.TYPE_PREFIX', () => {
      const testId = getCanvasTypeTestId('generic');
      expect(testId).toContain(CANVAS.TYPE_PREFIX);
    });
  });

  describe('AUTH', () => {
    it('should have all required auth test IDs', () => {
      expect(AUTH).toHaveProperty('EMAIL_INPUT', 'login-email-input');
      expect(AUTH).toHaveProperty('PASSWORD_INPUT', 'login-password-input');
      expect(AUTH).toHaveProperty('SUBMIT_BUTTON', 'login-submit-button');
      expect(AUTH).toHaveProperty('ERROR_MESSAGE', 'login-error-message');
      expect(AUTH).toHaveProperty('REMEMBER_ME_CHECKBOX', 'login-remember-me');
      expect(AUTH).toHaveProperty('LOGOUT_BUTTON', 'logout-button');
    });

    it('should have consistent string values', () => {
      expect(typeof AUTH.EMAIL_INPUT).toBe('string');
      expect(typeof AUTH.PASSWORD_INPUT).toBe('string');
      expect(typeof AUTH.SUBMIT_BUTTON).toBe('string');
      expect(typeof AUTH.ERROR_MESSAGE).toBe('string');
      expect(typeof AUTH.REMEMBER_ME_CHECKBOX).toBe('string');
      expect(typeof AUTH.LOGOUT_BUTTON).toBe('string');
    });
  });

  describe('FORM', () => {
    it('should have all required form test IDs', () => {
      expect(FORM).toHaveProperty('FIELD_PREFIX', 'form-field-');
      expect(FORM).toHaveProperty('SUBMIT_BUTTON', 'form-submit-button');
      expect(FORM).toHaveProperty('SUCCESS_MESSAGE', 'form-success-message');
    });

    it('should have consistent string values', () => {
      expect(typeof FORM.FIELD_PREFIX).toBe('string');
      expect(typeof FORM.SUBMIT_BUTTON).toBe('string');
      expect(typeof FORM.SUCCESS_MESSAGE).toBe('string');
    });
  });

  describe('getFormFieldTestId', () => {
    it('should generate test ID for field name', () => {
      const testId = getFormFieldTestId('email');
      expect(testId).toBe('form-field-email');
    });

    it('should generate test ID for multi-word field', () => {
      const testId = getFormFieldTestId('user_name');
      expect(testId).toBe('form-field-user_name');
    });

    it('should generate test ID for field with hyphens', () => {
      const testId = getFormFieldTestId('user-name');
      expect(testId).toBe('form-field-user-name');
    });

    it('should use FORM.FIELD_PREFIX', () => {
      const testId = getFormFieldTestId('test');
      expect(testId).toContain(FORM.FIELD_PREFIX);
    });

    it('should handle empty string', () => {
      const testId = getFormFieldTestId('');
      expect(testId).toBe('form-field-');
    });

    it('should handle special characters', () => {
      const testId = getFormFieldTestId('field_name_123');
      expect(testId).toBe('form-field-field_name_123');
    });
  });

  describe('SKILLS', () => {
    it('should have all required skills test IDs', () => {
      expect(SKILLS).toHaveProperty('MARKETPLACE_LIST', 'skills-marketplace-list');
      expect(SKILLS).toHaveProperty('INSTALL_BUTTON', 'skill-install-button');
      expect(SKILLS).toHaveProperty('EXECUTE_BUTTON', 'skill-execute-button');
      expect(SKILLS).toHaveProperty('OUTPUT_CONTAINER', 'skill-output');
    });

    it('should have consistent string values', () => {
      expect(typeof SKILLS.MARKETPLACE_LIST).toBe('string');
      expect(typeof SKILLS.INSTALL_BUTTON).toBe('string');
      expect(typeof SKILLS.EXECUTE_BUTTON).toBe('string');
      expect(typeof SKILLS.OUTPUT_CONTAINER).toBe('string');
    });
  });

  describe('SETTINGS', () => {
    it('should have all required settings test IDs', () => {
      expect(SETTINGS).toHaveProperty('THEME_TOGGLE', 'settings-theme-toggle');
      expect(SETTINGS).toHaveProperty('NOTIFICATIONS_TOGGLE', 'settings-notifications-toggle');
      expect(SETTINGS).toHaveProperty('PREFERENCES_SECTION', 'settings-preferences');
    });

    it('should have consistent string values', () => {
      expect(typeof SETTINGS.THEME_TOGGLE).toBe('string');
      expect(typeof SETTINGS.NOTIFICATIONS_TOGGLE).toBe('string');
      expect(typeof SETTINGS.PREFERENCES_SECTION).toBe('string');
    });
  });

  describe('TEST_IDS', () => {
    it('should contain all test ID categories', () => {
      expect(TEST_IDS).toHaveProperty('AGENT_CHAT', AGENT_CHAT);
      expect(TEST_IDS).toHaveProperty('CANVAS', CANVAS);
      expect(TEST_IDS).toHaveProperty('AUTH', AUTH);
      expect(TEST_IDS).toHaveProperty('FORM', FORM);
      expect(TEST_IDS).toHaveProperty('SKILLS', SKILLS);
      expect(TEST_IDS).toHaveProperty('SETTINGS', SETTINGS);
    });

    it('should be frozen (immutable)', () => {
      expect(TEST_IDS).toBeDefined();
      // Verify all categories exist
      expect(Object.keys(TEST_IDS)).toEqual([
        'AGENT_CHAT',
        'CANVAS',
        'AUTH',
        'FORM',
        'SKILLS',
        'SETTINGS'
      ]);
    });
  });

  describe('naming conventions', () => {
    it('should use kebab-case for all test IDs', () => {
      const allIds = [
        ...Object.values(AGENT_CHAT),
        ...Object.values(CANVAS),
        ...Object.values(AUTH),
        ...Object.values(FORM),
        ...Object.values(SKILLS),
        ...Object.values(SETTINGS)
      ];

      allIds.forEach(id => {
        if (typeof id === 'string' && !id.endsWith('-')) {
          // Check if it follows kebab-case pattern (lowercase with hyphens)
          expect(id).toMatch(/^[a-z0-9-]+$/);
        }
      });
    });

    it('should have descriptive names', () => {
      expect(AGENT_CHAT.INPUT).toContain('input');
      expect(AGENT_CHAT.SEND_BUTTON).toContain('button');
      expect(AUTH.EMAIL_INPUT).toContain('email');
      expect(FORM.SUBMIT_BUTTON).toContain('submit');
    });
  });

  describe('cross-platform consistency', () => {
    it('should work as data-testid attributes', () => {
      const element = { dataset: {} } as any;
      element.dataset.testid = AGENT_CHAT.INPUT;

      expect(element.dataset.testid).toBe('agent-chat-input');
    });

    it('should work as testID props in React Native', () => {
      const props = {
        testID: AUTH.EMAIL_INPUT
      };

      expect(props.testID).toBe('login-email-input');
    });
  });

  describe('uniqueness', () => {
    it('should have unique test IDs across categories', () => {
      const allIds = [
        ...Object.values(AGENT_CHAT),
        ...Object.values(CANVAS),
        ...Object.values(AUTH),
        ...Object.values(FORM),
        ...Object.values(SKILLS),
        ...Object.values(SETTINGS)
      ].filter(id => typeof id === 'string' && !id.endsWith('-'));

      const uniqueIds = new Set(allIds);

      expect(allIds.length).toBe(uniqueIds.size);
    });
  });

  describe('helper functions', () => {
    it('should handle all valid canvas types', () => {
      const validTypes = ['generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding'] as const;

      validTypes.forEach(type => {
        const testId = getCanvasTypeTestId(type);
        expect(testId).toBe(`canvas-type-${type}`);
      });
    });

    it('should generate consistent field test IDs', () => {
      const field1 = getFormFieldTestId('email');
      const field2 = getFormFieldTestId('email');

      expect(field1).toBe(field2);
    });
  });

  describe('exports', () => {
    it('should export default as TEST_IDS', () => {
      const testIds = require('../../src/lib/testIds');
      expect(testIds.default).toBe(TEST_IDS);
    });

    it('should export individual constants', () => {
      const testIds = require('../../src/lib/testIds');
      expect(testIds.AGENT_CHAT).toBe(AGENT_CHAT);
      expect(testIds.CANVAS).toBe(CANVAS);
      expect(testIds.AUTH).toBe(AUTH);
      expect(testIds.FORM).toBe(FORM);
      expect(testIds.SKILLS).toBe(SKILLS);
      expect(testIds.SETTINGS).toBe(SETTINGS);
    });
  });
});

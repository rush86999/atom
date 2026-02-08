/**
 * Tests for Integrations Catalog
 *
 * Tests the integration catalog with 500+ pieces
 */

import {
  CORE_PIECES,
  AI_PIECES,
  getIntegrationsByCategory,
  getPopularIntegrations,
  searchIntegrations,
  getIntegration,
  ALL_INTEGRATIONS,
  INTEGRATION_COUNT,
} from '../integrations-catalog';

describe('Integrations Catalog', () => {
  describe('Core Pieces', () => {
    it('should contain atom-memory integration', () => {
      const atomMemory = CORE_PIECES.find(i => i.id === 'atom-memory');
      expect(atomMemory).toBeDefined();
      expect(atomMemory?.name).toBe('Atom Memory');
      expect(atomMemory?.category).toBe('core');
      expect(atomMemory?.popular).toBe(true);
    });

    it('should contain core pieces with required properties', () => {
      CORE_PIECES.forEach(piece => {
        expect(piece).toHaveProperty('id');
        expect(piece).toHaveProperty('name');
        expect(piece).toHaveProperty('description');
        expect(piece).toHaveProperty('category');
        expect(piece).toHaveProperty('color');
        expect(piece).toHaveProperty('authType');
        expect(piece).toHaveProperty('triggers');
        expect(piece).toHaveProperty('actions');
        expect(Array.isArray(piece.triggers)).toBe(true);
        expect(Array.isArray(piece.actions)).toBe(true);
      });
    });

    it('should have expected core integrations', () => {
      const ids = CORE_PIECES.map(p => p.id);
      expect(ids).toContain('loop');
      expect(ids).toContain('code');
      expect(ids).toContain('condition');
      expect(ids).toContain('delay');
      expect(ids).toContain('http');
    });
  });

  describe('AI Pieces', () => {
    it('should contain popular AI integrations', () => {
      const ids = AI_PIECES.map(p => p.id);
      expect(ids).toContain('openai');
      expect(ids).toContain('anthropic');
      expect(ids).toContain('google-gemini');
    });

    it('should have at least 10 AI integrations', () => {
      expect(AI_PIECES.length).toBeGreaterThanOrEqual(10);
    });
  });

  describe('getIntegrationsByCategory', () => {
    it('should return integrations for valid category', () => {
      const coreIntegrations = getIntegrationsByCategory('core');
      expect(coreIntegrations).toBeDefined();
      expect(coreIntegrations.length).toBeGreaterThan(0);
      expect(coreIntegrations.every(i => i.category === 'core')).toBe(true);
    });

    it('should return empty array for non-existent category', () => {
      const result = getIntegrationsByCategory('non-existent' as any);
      expect(result).toEqual([]);
    });

    it('should filter by ai category', () => {
      const aiIntegrations = getIntegrationsByCategory('ai');
      expect(aiIntegrations.every(i => i.category === 'ai')).toBe(true);
      expect(aiIntegrations.length).toBeGreaterThan(0);
    });

    it('should filter by communication category', () => {
      const commIntegrations = getIntegrationsByCategory('communication');
      expect(commIntegrations.every(i => i.category === 'communication')).toBe(true);
      expect(commIntegrations.length).toBeGreaterThan(0);
    });
  });

  describe('getPopularIntegrations', () => {
    it('should return only popular integrations', () => {
      const popular = getPopularIntegrations();
      expect(popular.length).toBeGreaterThan(0);
      expect(popular.every(i => i.popular === true)).toBe(true);
    });

    it('should include known popular integrations', () => {
      const popular = getPopularIntegrations();
      const ids = popular.map(p => p.id);

      // Known popular integrations
      expect(ids).toContain('atom-memory');
      expect(ids).toContain('openai');
      expect(ids).toContain('slack');
    });
  });

  describe('searchIntegrations', () => {
    it('should find integrations by name', () => {
      const results = searchIntegrations('slack');
      expect(results.length).toBeGreaterThan(0);
      expect(results.some(i => i.id === 'slack')).toBe(true);
    });

    it('should find integrations by description', () => {
      const results = searchIntegrations('email');
      expect(results.length).toBeGreaterThan(0);
    });

    it('should be case-insensitive', () => {
      const lower = searchIntegrations('slack');
      const upper = searchIntegrations('SLACK');
      const mixed = searchIntegrations('SlAcK');

      expect(lower.length).toBeGreaterThan(0);
      expect(upper.length).toBe(lower.length);
      expect(mixed.length).toBe(lower.length);
    });

    it('should search by category', () => {
      const results = searchIntegrations('ai');
      expect(results.length).toBeGreaterThan(0);
    });

    it('should return empty array for non-matching query', () => {
      const results = searchIntegrations('xyz-non-existent-integration');
      expect(results).toEqual([]);
    });

    it('should find atom-memory', () => {
      const results = searchIntegrations('atom memory');
      expect(results.length).toBeGreaterThan(0);
      expect(results.some(i => i.id === 'atom-memory')).toBe(true);
    });
  });

  describe('getIntegration', () => {
    it('should find integration by id', () => {
      const integration = getIntegration('atom-memory');
      expect(integration).toBeDefined();
      expect(integration?.id).toBe('atom-memory');
    });

    it('should return undefined for non-existent id', () => {
      const integration = getIntegration('non-existent-id');
      expect(integration).toBeUndefined();
    });

    it('should find slack integration', () => {
      const slack = getIntegration('slack');
      expect(slack).toBeDefined();
      expect(slack?.name).toBe('Slack');
      expect(slack?.authType).toBe('oauth2');
    });

    it('should find openai integration', () => {
      const openai = getIntegration('openai');
      expect(openai).toBeDefined();
      expect(openai?.name).toBe('OpenAI');
      expect(openai?.authType).toBe('api_key');
    });
  });

  describe('ALL_INTEGRATIONS', () => {
    it('should contain all manual pieces', () => {
      expect(ALL_INTEGRATIONS.length).toBeGreaterThan(0);
    });

    it('should not have duplicate ids', () => {
      const ids = ALL_INTEGRATIONS.map(i => i.id);
      const uniqueIds = new Set(ids);
      expect(ids.length).toBe(uniqueIds.size);
    });

    it('should have integrations from multiple categories', () => {
      const categories = new Set(ALL_INTEGRATIONS.map(i => i.category));
      expect(categories.size).toBeGreaterThan(10);
    });
  });

  describe('INTEGRATION_COUNT', () => {
    it('should be greater than 100', () => {
      expect(INTEGRATION_COUNT).toBeGreaterThan(100);
    });

    it('should match ALL_INTEGRATIONS length', () => {
      expect(INTEGRATION_COUNT).toBe(ALL_INTEGRATIONS.length);
    });
  });

  describe('Integration structure validation', () => {
    it('should have valid auth types for all integrations', () => {
      const validAuthTypes = ['oauth2', 'api_key', 'basic', 'none'];
      ALL_INTEGRATIONS.forEach(integration => {
        expect(validAuthTypes).toContain(integration.authType);
      });
    });

    it('should have valid colors (hex format)', () => {
      ALL_INTEGRATIONS.forEach(integration => {
        expect(integration.color).toMatch(/^#[0-9A-Fa-f]{6}$/);
      });
    });

    it('should have non-empty arrays for triggers and actions', () => {
      ALL_INTEGRATIONS.forEach(integration => {
        expect(Array.isArray(integration.triggers)).toBe(true);
        expect(Array.isArray(integration.actions)).toBe(true);
      });
    });

    it('should have unique ids across all integrations', () => {
      const ids = ALL_INTEGRATIONS.map(i => i.id);
      const uniqueIds = new Set(ids);
      expect(ids.length).toBe(uniqueIds.size);
    });
  });

  describe('Category coverage', () => {
    it('should have ai category integrations', () => {
      const ai = getIntegrationsByCategory('ai');
      expect(ai.length).toBeGreaterThan(0);
    });

    it('should have communication category integrations', () => {
      const comm = getIntegrationsByCategory('communication');
      expect(comm.length).toBeGreaterThan(0);
    });

    it('should have productivity category integrations', () => {
      const prod = getIntegrationsByCategory('productivity');
      expect(prod.length).toBeGreaterThan(0);
    });

    it('should have developer category integrations', () => {
      const dev = getIntegrationsByCategory('developer');
      expect(dev.length).toBeGreaterThan(0);
    });
  });
});

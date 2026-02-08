/**
 * Tests for Constants
 *
 * Tests environment variable constants with fallback values
 */

import {
  googleClientIdAtomicWeb,
  googleClientSecretAtomicWeb,
  googleOAuthAtomicWebRedirectUrl,
  postgraphileAdminSecret,
  postgraphileGraphUrl,
  zoomIVForPass,
  zoomPassKey,
  zoomSaltForPass,
  SCHEDULER_API_URL,
  postgraphileDbUrl,
  postgraphileWSUrl,
  HASURA_GRAPHQL_URL,
  HASURA_ADMIN_SECRET,
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
} from '../constants';

describe('Constants', () => {
  describe('Google OAuth Constants', () => {
    it('should export googleClientIdAtomicWeb', () => {
      expect(googleClientIdAtomicWeb).toBeDefined();
      expect(typeof googleClientIdAtomicWeb).toBe('string');
    });

    it('should export googleClientSecretAtomicWeb', () => {
      expect(googleClientSecretAtomicWeb).toBeDefined();
      expect(typeof googleClientSecretAtomicWeb).toBe('string');
    });

    it('should export googleOAuthAtomicWebRedirectUrl', () => {
      expect(googleOAuthAtomicWebRedirectUrl).toBeDefined();
      expect(typeof googleOAuthAtomicWebRedirectUrl).toBe('string');
      expect(googleOAuthAtomicWebRedirectUrl).toMatch(/http/);
    });

    it('should use default redirect URL when env not set', () => {
      expect(googleOAuthAtomicWebRedirectUrl).toBe('http://localhost:3000/api/atom/auth/calendar/callback');
    });
  });

  describe('Postgraphile Constants', () => {
    it('should export postgraphileAdminSecret', () => {
      expect(postgraphileAdminSecret).toBeDefined();
      expect(typeof postgraphileAdminSecret).toBe('string');
      expect(postgraphileAdminSecret).toBe('postgraphile_admin_secret');
    });

    it('should export postgraphileGraphUrl', () => {
      expect(postgraphileGraphUrl).toBeDefined();
      expect(typeof postgraphileGraphUrl).toBe('string');
      expect(postgraphileGraphUrl).toContain('http');
    });

    it('should use default graph URL when env not set', () => {
      expect(postgraphileGraphUrl).toBe('http://localhost:3000/api/graphql');
    });
  });

  describe('Zoom Constants', () => {
    it('should export zoomIVForPass', () => {
      expect(zoomIVForPass).toBeDefined();
      expect(typeof zoomIVForPass).toBe('string');
      expect(zoomIVForPass).toBe('zoom_iv_for_pass');
    });

    it('should export zoomPassKey', () => {
      expect(zoomPassKey).toBeDefined();
      expect(typeof zoomPassKey).toBe('string');
      expect(zoomPassKey).toBe('zoom_pass_key');
    });

    it('should export zoomSaltForPass', () => {
      expect(zoomSaltForPass).toBeDefined();
      expect(typeof zoomSaltForPass).toBe('string');
      expect(zoomSaltForPass).toBe('zoom_salt_for_pass');
    });
  });

  describe('Scheduler API', () => {
    it('should export SCHEDULER_API_URL', () => {
      expect(SCHEDULER_API_URL).toBeDefined();
      expect(typeof SCHEDULER_API_URL).toBe('string');
      expect(SCHEDULER_API_URL).toContain('http');
    });

    it('should use default scheduler URL when env not set', () => {
      expect(SCHEDULER_API_URL).toBe('http://localhost:3001');
    });
  });

  describe('Apollo GraphQL Constants', () => {
    it('should export postgraphileDbUrl', () => {
      expect(postgraphileDbUrl).toBeDefined();
      expect(typeof postgraphileDbUrl).toBe('string');
      expect(postgraphileDbUrl).toContain('http');
    });

    it('should export postgraphileWSUrl', () => {
      expect(postgraphileWSUrl).toBeDefined();
      expect(typeof postgraphileWSUrl).toBe('string');
      expect(postgraphileWSUrl).toContain('ws://');
    });

    it('should export HASURA_GRAPHQL_URL', () => {
      expect(HASURA_GRAPHQL_URL).toBeDefined();
      expect(typeof HASURA_GRAPHQL_URL).toBe('string');
      expect(HASURA_GRAPHQL_URL).toContain('http');
    });

    it('should use default Hasura URL when env not set', () => {
      expect(HASURA_GRAPHQL_URL).toBe('http://localhost:8080/v1/graphql');
    });

    it('should export HASURA_ADMIN_SECRET', () => {
      expect(HASURA_ADMIN_SECRET).toBeDefined();
      expect(typeof HASURA_ADMIN_SECRET).toBe('string');
      expect(HASURA_ADMIN_SECRET).toBe('hasura_admin_secret');
    });
  });

  describe('Atom Google Calendar Constants', () => {
    it('should export ATOM_GOOGLE_CALENDAR_CLIENT_ID', () => {
      expect(ATOM_GOOGLE_CALENDAR_CLIENT_ID).toBeDefined();
      expect(typeof ATOM_GOOGLE_CALENDAR_CLIENT_ID).toBe('string');
    });

    it('should export ATOM_GOOGLE_CALENDAR_CLIENT_SECRET', () => {
      expect(ATOM_GOOGLE_CALENDAR_CLIENT_SECRET).toBeDefined();
      expect(typeof ATOM_GOOGLE_CALENDAR_CLIENT_SECRET).toBe('string');
    });
  });

  describe('Environment Variable Fallbacks', () => {
    it('should provide default values for all constants', () => {
      // Constants with empty string defaults
      expect(googleClientIdAtomicWeb).toBeDefined();
      expect(googleClientSecretAtomicWeb).toBeDefined();
      expect(ATOM_GOOGLE_CALENDAR_CLIENT_ID).toBeDefined();
      expect(ATOM_GOOGLE_CALENDAR_CLIENT_SECRET).toBeDefined();

      // Constants with non-empty defaults
      expect(googleOAuthAtomicWebRedirectUrl).toBeTruthy();
      expect(postgraphileAdminSecret).toBeTruthy();
      expect(postgraphileGraphUrl).toBeTruthy();
      expect(zoomIVForPass).toBeTruthy();
      expect(zoomPassKey).toBeTruthy();
      expect(zoomSaltForPass).toBeTruthy();
      expect(SCHEDULER_API_URL).toBeTruthy();
      expect(postgraphileDbUrl).toBeTruthy();
      expect(postgraphileWSUrl).toBeTruthy();
      expect(HASURA_GRAPHQL_URL).toBeTruthy();
      expect(HASURA_ADMIN_SECRET).toBeTruthy();
    });

    it('should have string type for all constants', () => {
      const constants = [
        googleClientIdAtomicWeb,
        googleClientSecretAtomicWeb,
        googleOAuthAtomicWebRedirectUrl,
        postgraphileAdminSecret,
        postgraphileGraphUrl,
        zoomIVForPass,
        zoomPassKey,
        zoomSaltForPass,
        SCHEDULER_API_URL,
        postgraphileDbUrl,
        postgraphileWSUrl,
        HASURA_GRAPHQL_URL,
        HASURA_ADMIN_SECRET,
        ATOM_GOOGLE_CALENDAR_CLIENT_ID,
        ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
      ];

      constants.forEach(constant => {
        expect(typeof constant).toBe('string');
      });
    });
  });

  describe('URL Format Validation', () => {
    it('should have valid HTTP/HTTPS URL formats for HTTP endpoints', () => {
      const urlConstants = [
        googleOAuthAtomicWebRedirectUrl,
        postgraphileGraphUrl,
        SCHEDULER_API_URL,
        postgraphileDbUrl,
        HASURA_GRAPHQL_URL,
      ];

      urlConstants.forEach(url => {
        expect(url).toMatch(/^https?:\/\//);
      });
    });

    it('should have valid WebSocket URL format for WS endpoints', () => {
      expect(postgraphileWSUrl).toMatch(/^wss?:\/\//);
    });
  });
});

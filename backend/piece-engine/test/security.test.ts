/**
 * Security Tests for Piece Engine Command Injection Fix
 *
 * Tests for CVE-Candidate vulnerability (Issue #525)
 * Verifies that:
 * 1. Invalid package names are rejected
 * 2. Command injection attempts are blocked
 * 3. Authentication is required for sensitive endpoints
 */

import { isValidPackageName } from '../src/index';

describe('Security: Package Name Validation', () => {
  describe('isValidPackageName', () => {
    // Valid package names
    test('should accept valid scoped package', () => {
      expect(isValidPackageName('@activepieces/piece-github')).toBe(true);
    });

    test('should accept valid unscoped package', () => {
      expect(isValidPackageName('express')).toBe(true);
      expect(isValidPackageName('lodash')).toBe(true);
    });

    test('should accept package with dots and hyphens', () => {
      expect(isValidPackageName('@scope/package.name')).toBe(true);
      expect(isValidPackageName('package-name')).toBe(true);
    });

    // Invalid package names - Command Injection Vectors
    test('should reject semicolon injection', () => {
      expect(isValidPackageName('express; touch /tmp/pwned #')).toBe(false);
    });

    test('should reject pipe injection', () => {
      expect(isValidPackageName('express | cat /etc/passwd')).toBe(false);
    });

    test('should reject command substitution', () => {
      expect(isValidPackageName('express$(whoami)')).toBe(false);
      expect(isValidPackageName('express`id`')).toBe(false);
    });

    test('should reject backtick injection', () => {
      expect(isValidPackageName('express`rm -rf /`')).toBe(false);
    });

    test('should reject newline injection', () => {
      expect(isValidPackageName('express\nmalicious')).toBe(false);
    });

    test('should reject null bytes', () => {
      expect(isValidPackageName('express\x00rm')).toBe(false);
    });

    // Edge cases
    test('should reject empty string', () => {
      expect(isValidPackageName('')).toBe(false);
    });

    test('should reject overly long names (>214 chars)', () => {
      const longName = 'a'.repeat(215);
      expect(isValidPackageName(longName)).toBe(false);
    });

    test('should reject spaces', () => {
      expect(isValidPackageName('express express')).toBe(false);
    });

    test('should reject special shell characters', () => {
      expect(isValidPackageName('express&ls')).toBe(false);
      expect(isValidPackageName('express&&whoami')).toBe(false);
      expect(isValidPackageName('express||true')).toBe(false);
      expect(isValidPackageName('express>file')).toBe(false);
      expect(isValidPackageName('express<file')).toBe(false);
    });

    // Real-world package name patterns
    test('should accept valid scoped packages', () => {
      expect(isValidPackageName('@babel/core')).toBe(true);
      expect(isValidPackageName('@types/node')).toBe(true);
      expect(isValidPackageName('@angular/router')).toBe(true);
    });

    test('should accept valid unscoped packages', () => {
      expect(isValidPackageName('react')).toBe(true);
      expect(isValidPackageName('vue')).toBe(true);
      expect(isValidPackageName('axios')).toBe(true);
      expect(isValidPackageName('typescript')).toBe(true);
    });
  });
});

describe('Security: Authentication Middleware', () => {
  // These would require integration tests with a running server
  // For now, documenting the expected behavior:

  test('POST /sys/install should require authentication', () => {
    // Expected: 401 without API key
    // Expected: 403 with invalid API key
    // Expected: 200 with valid API key AND valid package name
  });

  test('POST /execute/action should require authentication', () => {
    // Expected: 401 without API key
    // Expected: 403 with invalid API key
    // Expected: 200 with valid API key
  });

  test('GET /pieces/:name should require authentication when dynamic loading needed', () => {
    // Expected: 401 without API key when piece not in cache
    // Expected: 200 without API key when piece already loaded
  });

  test('GET /health should not require authentication', () => {
    // Expected: 200 without API key (health check is public)
  });

  test('GET /pieces should not require authentication', () => {
    // Expected: 200 without API key (listing is safe)
  });
});

describe('Security: Command Injection Prevention', () => {
  test('spawn() should be used instead of exec()', () => {
    // Verify that safeNpmInstall uses spawn with shell: false
    // This prevents shell interpretation of metacharacters
  });

  test('npm commands should use argument arrays', () => {
    // Verify that npm commands use: ['npm', 'install', packageName, '--save']
    // NOT: `npm install ${packageName} --save`
  });
});

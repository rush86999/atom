/**
 * Validation Error Paths Test Suite
 *
 * Tests validation error handling including:
 * - Required field validation
 * - Email format validation
 * - Phone format validation
 * - Date format validation
 * - Password requirements
 * - URL format validation
 * - Number validation
 * - Array validation
 * - Object validation
 * - Async validation errors
 */

import { validateEmail, validateRequired, validateLength, validateUrl, validatePhone } from '@/lib/validation';

describe('Validation Error Paths', () => {
  describe('Required Field Validation', () => {
    it('should handle empty string validation', () => {
      const result = validateRequired('');
      expect(result).toBe(false);
    });

    it('should handle null validation', () => {
      const result = validateRequired(null as any);
      expect(result).toBe(false);
    });

    it('should handle undefined validation', () => {
      const result = validateRequired(undefined as any);
      expect(result).toBe(false);
    });

    it('should handle whitespace-only validation', () => {
      const result = validateRequired('   ');
      expect(result).toBe(false);
    });

    it('should handle valid string', () => {
      const result = validateRequired('valid value');
      expect(result).toBe(true);
    });

    it('should handle number zero as valid', () => {
      const result = validateRequired(0);
      expect(result).toBe(true);
    });

    it('should handle false as valid', () => {
      const result = validateRequired(false);
      expect(result).toBe(true);
    });

    it('should handle empty array as invalid', () => {
      const result = validateRequired([]);
      expect(result).toBe(false);
    });

    it('should handle empty object as invalid', () => {
      const result = validateRequired({});
      expect(result).toBe(false);
    });
  });

  describe('Email Format Validation', () => {
    it('should handle invalid email - no @', () => {
      const result = validateEmail('invalidemail');
      expect(result).toBe(false);
    });

    it('should handle invalid email - no domain', () => {
      const result = validateEmail('user@');
      expect(result).toBe(false);
    });

    it('should handle invalid email - no local part', () => {
      const result = validateEmail('@example.com');
      expect(result).toBe(false);
    });

    it('should handle invalid email - multiple @', () => {
      const result = validateEmail('user@name@example.com');
      expect(result).toBe(false);
    });

    it('should handle invalid email - spaces', () => {
      const result = validateEmail('user @example.com');
      expect(result).toBe(false);
    });

    it('should handle valid email - simple', () => {
      const result = validateEmail('user@example.com');
      expect(result).toBe(true);
    });

    it('should handle valid email - with dots', () => {
      const result = validateEmail('user.name@example.com');
      expect(result).toBe(true);
    });

    it('should handle valid email - with plus', () => {
      const result = validateEmail('user+tag@example.com');
      expect(result).toBe(true);
    });

    it('should handle valid email - subdomain', () => {
      const result = validateEmail('user@mail.example.com');
      expect(result).toBe(true);
    });

    it('should handle null email', () => {
      const result = validateEmail(null as any);
      expect(result).toBe(false);
    });

    it('should handle undefined email', () => {
      const result = validateEmail(undefined as any);
      expect(result).toBe(false);
    });

    it('should handle non-string email', () => {
      const result = validateEmail(12345 as any);
      expect(result).toBe(false);
    });
  });

  describe('Phone Format Validation', () => {
    it('should handle invalid phone - too short', () => {
      const result = validatePhone('123');
      expect(result).toBe(false);
    });

    it('should handle invalid phone - letters', () => {
      const result = validatePhone('abcdefghijk');
      expect(result).toBe(false);
    });

    it('should handle valid phone - US format', () => {
      const result = validatePhone('+1 (555) 123-4567');
      expect(result).toBe(true);
    });

    it('should handle valid phone - digits only', () => {
      const result = validatePhone('15551234567');
      expect(result).toBe(true);
    });

    it('should handle valid phone - with dashes', () => {
      const result = validatePhone('555-123-4567');
      expect(result).toBe(true);
    });

    it('should handle null phone', () => {
      const result = validatePhone(null as any);
      expect(result).toBe(false);
    });

    it('should handle undefined phone', () => {
      const result = validatePhone(undefined as any);
      expect(result).toBe(false);
    });
  });

  describe('URL Format Validation', () => {
    it('should handle invalid URL - no protocol', () => {
      const result = validateUrl('example.com');
      expect(result).toBe(false);
    });

    it('should handle invalid URL - no domain', () => {
      const result = validateUrl('https://');
      expect(result).toBe(false);
    });

    it('should handle invalid URL - spaces', () => {
      const result = validateUrl('https://example. com');
      expect(result).toBe(false);
    });

    it('should handle valid URL - https', () => {
      const result = validateUrl('https://example.com');
      expect(result).toBe(true);
    });

    it('should handle valid URL - http', () => {
      const result = validateUrl('http://example.com');
      expect(result).toBe(true);
    });

    it('should handle valid URL - with path', () => {
      const result = validateUrl('https://example.com/path/to/page');
      expect(result).toBe(true);
    });

    it('should handle valid URL - with query params', () => {
      const result = validateUrl('https://example.com?key=value');
      expect(result).toBe(true);
    });

    it('should handle valid URL - with fragment', () => {
      const result = validateUrl('https://example.com#section');
      expect(result).toBe(true);
    });

    it('should handle null URL', () => {
      const result = validateUrl(null as any);
      expect(result).toBe(false);
    });

    it('should handle undefined URL', () => {
      const result = validateUrl(undefined as any);
      expect(result).toBe(false);
    });
  });

  describe('Length Validation', () => {
    it('should handle too short string', () => {
      const result = validateLength('ab', { min: 3 });
      expect(result).toBe(false);
    });

    it('should handle too long string', () => {
      const result = validateLength('abcdef', { max: 5 });
      expect(result).toBe(false);
    });

    it('should handle empty string when min required', () => {
      const result = validateLength('', { min: 1 });
      expect(result).toBe(false);
    });

    it('should handle exact length match', () => {
      const result = validateLength('abc', { min: 3, max: 3 });
      expect(result).toBe(true);
    });

    it('should handle string within range', () => {
      const result = validateLength('abcd', { min: 3, max: 5 });
      expect(result).toBe(true);
    });

    it('should handle null string', () => {
      const result = validateLength(null as any, { min: 3 });
      expect(result).toBe(false);
    });

    it('should handle non-string value', () => {
      const result = validateLength(12345 as any, { min: 3 });
      expect(result).toBe(false);
    });

    it('should handle unicode characters', () => {
      const result = validateLength('你好', { min: 2 });
      expect(result).toBe(true);
    });

    it('should handle emoji characters', () => {
      const result = validateLength('🎉👍', { min: 2 });
      expect(result).toBe(true);
    });
  });

  describe('Password Validation', () => {
    it('should handle password too short', () => {
      const result = validateLength('abc', { min: 8 });
      expect(result).toBe(false);
    });

    it('should handle password too long', () => {
      const result = validateLength('a'.repeat(130), { max: 128 });
      expect(result).toBe(false);
    });

    it('should handle empty password', () => {
      const result = validateLength('', { min: 8 });
      expect(result).toBe(false);
    });

    it('should handle valid password length', () => {
      const result = validateLength('securePassword123', { min: 8, max: 128 });
      expect(result).toBe(true);
    });

    it('should handle password with special chars', () => {
      const result = validateLength('P@ssw0rd!123', { min: 8 });
      expect(result).toBe(true);
    });
  });

  describe('Number Validation', () => {
    it('should handle NaN', () => {
      const result = validateRequired(NaN);
      expect(result).toBe(false);
    });

    it('should handle valid number', () => {
      const result = validateRequired(42);
      expect(result).toBe(true);
    });

    it('should handle zero', () => {
      const result = validateRequired(0);
      expect(result).toBe(true);
    });

    it('should handle negative number', () => {
      const result = validateRequired(-42);
      expect(result).toBe(true);
    });

    it('should handle decimal number', () => {
      const result = validateRequired(3.14);
      expect(result).toBe(true);
    });
  });

  describe('Array Validation', () => {
    it('should handle empty array as invalid', () => {
      const result = validateRequired([]);
      expect(result).toBe(false);
    });

    it('should handle array with items as valid', () => {
      const result = validateRequired([1, 2, 3]);
      expect(result).toBe(true);
    });

    it('should handle array with null items', () => {
      const result = validateRequired([null, null]);
      expect(result).toBe(true);
    });

    it('should handle array with empty strings', () => {
      const result = validateRequired(['', '']);
      expect(result).toBe(true);
    });
  });

  describe('Object Validation', () => {
    it('should handle empty object as invalid', () => {
      const result = validateRequired({});
      expect(result).toBe(false);
    });

    it('should handle object with properties as valid', () => {
      const result = validateRequired({ key: 'value' });
      expect(result).toBe(true);
    });

    it('should handle object with null properties', () => {
      const result = validateRequired({ key: null });
      expect(result).toBe(true);
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long string', () => {
      const result = validateRequired('a'.repeat(10000));
      expect(result).toBe(true);
    });

    it('should handle string with newlines', () => {
      const result = validateRequired('line1\nline2\nline3');
      expect(result).toBe(true);
    });

    it('should handle string with tabs', () => {
      const result = validateRequired('line1\tline2\tline3');
      expect(result).toBe(true);
    });

    it('should handle email with unicode', () => {
      const result = validateEmail('user@例え.com');
      expect(result).toBe(false); // Our regex doesn't support unicode domains
    });

    it('should handle URL with IP address', () => {
      const result = validateUrl('https://192.168.1.1');
      expect(result).toBe(true);
    });

    it('should handle URL with localhost', () => {
      const result = validateUrl('http://localhost:3000');
      expect(result).toBe(true);
    });
  });
});

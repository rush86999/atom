import {
  validateEmail,
  validateRequired,
  validateLength,
  validateUrl,
  validatePhone,
} from '../validation';

describe('Validation Utilities', () => {
  describe('validateEmail', () => {
    it('returns true for valid email addresses', () => {
      expect(validateEmail('test@example.com')).toBe(true);
      expect(validateEmail('user.name@example.com')).toBe(true);
      expect(validateEmail('user+tag@example.co.uk')).toBe(true);
      expect(validateEmail('user-name@sub.example.com')).toBe(true);
      expect(validateEmail('123@example.com')).toBe(true);
    });

    it('returns false for invalid email addresses', () => {
      expect(validateEmail('')).toBe(false);
      expect(validateEmail('invalid')).toBe(false);
      expect(validateEmail('@example.com')).toBe(false);
      expect(validateEmail('user@')).toBe(false);
      expect(validateEmail('user@.com')).toBe(false);
      expect(validateEmail('user..name@example.com')).toBe(false);
      expect(validateEmail('user@example..com')).toBe(false);
      expect(validateEmail('user name@example.com')).toBe(false);
      expect(validateEmail('user@example')).toBe(false);
    });

    it('returns false for non-string values', () => {
      expect(validateEmail(null as any)).toBe(false);
      expect(validateEmail(undefined as any)).toBe(false);
      expect(validateEmail(123 as any)).toBe(false);
      expect(validateEmail({} as any)).toBe(false);
      expect(validateEmail([] as any)).toBe(false);
      expect(validateEmail(true as any)).toBe(false);
    });

    it('handles edge cases', () => {
      expect(validateEmail(' ')).toBe(false);
      expect(validateEmail('test@localhost')).toBe(false); // No TLD
      expect(validateEmail('test@127.0.0.1')).toBe(false); // IP address
      expect(validateEmail('test@[IPv6]')).toBe(false);
    });
  });

  describe('validateRequired', () => {
    it('returns true for valid non-empty values', () => {
      // String values
      expect(validateRequired('hello')).toBe(true);
      expect(validateRequired('  text  ')).toBe(true); // Trimmed
      expect(validateRequired('0')).toBe(true);

      // Number values
      expect(validateRequired(0)).toBe(true);
      expect(validateRequired(123)).toBe(true);
      expect(validateRequired(-1)).toBe(true);
      expect(validateRequired(3.14)).toBe(true);

      // Boolean values
      expect(validateRequired(true)).toBe(true);
      expect(validateRequired(false)).toBe(true);

      // Array values
      expect(validateRequired([1, 2, 3])).toBe(true);
      expect(validateRequired(['item'])).toBe(true);

      // Object values
      expect(validateRequired({ key: 'value' })).toBe(true);
      expect(validateRequired({})).toBe(true); // Empty object is valid
    });

    it('returns false for empty values', () => {
      // Null and undefined
      expect(validateRequired(null)).toBe(false);
      expect(validateRequired(undefined)).toBe(false);

      // Empty string
      expect(validateRequired('')).toBe(false);
      expect(validateRequired('   ')).toBe(false); // Whitespace only

      // Empty array
      expect(validateRequired([])).toBe(false);

      // NaN number
      expect(validateRequired(NaN)).toBe(false);
    });

    it('handles edge cases', () => {
      expect(validateRequired('\t\n')).toBe(false); // Whitespace
      expect(validateRequired('\u00A0')).toBe(false); // Non-breaking space
      expect(validateRequired(Infinity)).toBe(true); // Infinity is valid number
    });
  });

  describe('validateLength', () => {
    it('validates minimum length', () => {
      expect(validateLength('hello', { min: 3 })).toBe(true);
      expect(validateLength('hello', { min: 5 })).toBe(true);
      expect(validateLength('hello', { min: 6 })).toBe(false);
      expect(validateLength('ab', { min: 3 })).toBe(false);
    });

    it('validates maximum length', () => {
      expect(validateLength('hello', { max: 10 })).toBe(true);
      expect(validateLength('hello', { max: 5 })).toBe(true);
      expect(validateLength('hello', { max: 4 })).toBe(false);
      expect(validateLength('very long text', { max: 5 })).toBe(false);
    });

    it('validates both min and max length', () => {
      expect(validateLength('hello', { min: 3, max: 10 })).toBe(true);
      expect(validateLength('hello', { min: 5, max: 5 })).toBe(true);
      expect(validateLength('hello', { min: 6, max: 10 })).toBe(false);
      expect(validateLength('hello', { min: 1, max: 4 })).toBe(false);
    });

    it('handles empty string', () => {
      expect(validateLength('', { min: 0 })).toBe(true);
      expect(validateLength('', { min: 1 })).toBe(false);
      expect(validateLength('', { max: 10 })).toBe(false);
    });

    it('handles non-string values', () => {
      expect(validateLength(null as any, { min: 1 })).toBe(false);
      expect(validateLength(undefined as any, { min: 1 })).toBe(false);
      expect(validateLength(123 as any, { min: 1 })).toBe(false);
      expect(validateLength({} as any, { min: 1 })).toBe(false);
    });

    it('handles unicode characters', () => {
      expect(validateLength('hello', { min: 5 })).toBe(true);
      expect(validateLength('hello世界', { min: 7 })).toBe(true); // 7 chars (2 emoji = 2 chars)
      expect(validateLength('🔥🔥🔥', { min: 3 })).toBe(true); // 3 emoji
    });

    it('handles edge cases', () => {
      // Zero min and max
      expect(validateLength('', { min: 0, max: 0 })).toBe(true);
      expect(validateLength('a', { min: 0, max: 0 })).toBe(false);

      // Large values
      const longString = 'a'.repeat(10000);
      expect(validateLength(longString, { min: 10000 })).toBe(true);
      expect(validateLength(longString, { max: 10000 })).toBe(true);
      expect(validateLength(longString, { max: 9999 })).toBe(false);
    });
  });

  describe('validateUrl', () => {
    it('returns true for valid URLs', () => {
      expect(validateUrl('http://example.com')).toBe(true);
      expect(validateUrl('https://example.com')).toBe(true);
      expect(validateUrl('https://www.example.com')).toBe(true);
      expect(validateUrl('https://example.com/path')).toBe(true);
      expect(validateUrl('https://example.com/path?query=value')).toBe(true);
      expect(validateUrl('https://example.com/path#hash')).toBe(true);
      expect(validateUrl('https://user:pass@example.com')).toBe(true);
      expect(validateUrl('https://example.com:8080')).toBe(true);
      expect(validateUrl('ftp://example.com')).toBe(true);
      expect(validateUrl('file:///path/to/file')).toBe(true);
    });

    it('returns false for invalid URLs', () => {
      expect(validateUrl('')).toBe(false);
      expect(validateUrl('not a url')).toBe(false);
      expect(validateUrl('example.com')).toBe(false); // Missing protocol
      expect(validateUrl('http://')).toBe(false); // Missing domain
      expect(validateUrl('https://')).toBe(false); // Missing domain
      expect(validateUrl('://example.com')).toBe(false); // Missing protocol
      expect(validateUrl('http:///path')).toBe(false); // Missing domain
    });

    it('returns false for non-string values', () => {
      expect(validateUrl(null as any)).toBe(false);
      expect(validateUrl(undefined as any)).toBe(false);
      expect(validateUrl(123 as any)).toBe(false);
      expect(validateUrl({} as any)).toBe(false);
      expect(validateUrl([] as any)).toBe(false);
      expect(validateUrl(true as any)).toBe(false);
    });

    it('handles edge cases', () => {
      expect(validateUrl(' ')).toBe(false);
      expect(validateUrl('https://example.com/with spaces')).toBe(true); // URL encoding handles this
      expect(validateUrl('https://example.com/?query=value&other=test')).toBe(true);
      expect(validateUrl('https://example.com/#fragment-with-dashes')).toBe(true);
    });

    it('handles international URLs', () => {
      expect(validateUrl('https://example.中国')).toBe(true);
      expect(validateUrl('https://example.ru/path')).toBe(true);
      expect(validateUrl('https://xn--example-6q4b.com')).toBe(true); // Punycode
    });

    it('handles localhost and IP addresses', () => {
      expect(validateUrl('http://localhost')).toBe(true);
      expect(validateUrl('http://localhost:3000')).toBe(true);
      expect(validateUrl('http://127.0.0.1')).toBe(true);
      expect(validateUrl('http://192.168.1.1:8080')).toBe(true);
      expect(validateUrl('https://[::1]')).toBe(true); // IPv6
    });
  });

  describe('validatePhone', () => {
    it('returns true for valid phone numbers', () => {
      // US formats
      expect(validatePhone('1234567890')).toBe(true);
      expect(validatePhone('(123) 456-7890')).toBe(true);
      expect(validatePhone('123-456-7890')).toBe(true);
      expect(validatePhone('+1 123 456 7890')).toBe(true);

      // International formats
      expect(validatePhone('+44 20 1234 5678')).toBe(true);
      expect(validatePhone('+91 98765 43210')).toBe(true);
      expect(validatePhone('+86 138 1234 5678')).toBe(true);

      // Simple formats
      expect(validatePhone('1234567890123')).toBe(true); // >10 digits
      expect(validatePhone('123 456 7890')).toBe(true);
      expect(validatePhone('123.456.7890')).toBe(true);
    });

    it('returns false for invalid phone numbers', () => {
      // Too short
      expect(validatePhone('123')).toBe(false);
      expect(validatePhone('123456789')).toBe(false); // <10 digits

      // Invalid characters
      expect(validatePhone('abc')).toBe(false);
      expect(validatePhone('123-456-789a')).toBe(false);
      expect(validatePhone('phone')).toBe(false);

      // Empty or whitespace
      expect(validatePhone('')).toBe(false);
      expect(validatePhone('   ')).toBe(false);
    });

    it('returns false for non-string values', () => {
      expect(validatePhone(null as any)).toBe(false);
      expect(validatePhone(undefined as any)).toBe(false);
      expect(validatePhone(1234567890 as any)).toBe(false);
      expect(validatePhone({} as any)).toBe(false);
      expect(validatePhone([] as any)).toBe(false);
      expect(validatePhone(true as any)).toBe(false);
    });

    it('handles edge cases', () => {
      // Exactly 10 digits (minimum)
      expect(validatePhone('1234567890')).toBe(true);

      // Extensions
      expect(validatePhone('123-456-7890 x123')).toBe(false); // 'x' not allowed

      // Special characters
      expect(validatePhone('+1 (123) 456-7890')).toBe(true);

      // Mixed separators
      expect(validatePhone('123.456.7890')).toBe(true);
      expect(validatePhone('123 456 7890')).toBe(true);
    });

    it('handles international formats with country codes', () => {
      expect(validatePhone('+1 1234567890')).toBe(true);
      expect(validatePhone('+44 1234567890')).toBe(true);
      expect(validatePhone('+91 1234567890')).toBe(true);
      expect(validatePhone('+86 12345678901')).toBe(true);
    });

    it('handles phone numbers with various separators', () => {
      expect(validatePhone('123-456-7890')).toBe(true);
      expect(validatePhone('123.456.7890')).toBe(true);
      expect(validatePhone('123 456 7890')).toBe(true);
      expect(validatePhone('(123) 456-7890')).toBe(true);
      expect(validatePhone('(123)456-7890')).toBe(true);
    });
  });

  describe('Combined Validation', () => {
    it('can chain multiple validators', () => {
      const email = 'test@example.com';

      const isValid = validateRequired(email) &&
                     validateEmail(email) &&
                     validateLength(email, { min: 5, max: 100 });

      expect(isValid).toBe(true);
    });

    it('can validate complex forms', () => {
      const formData = {
        name: 'John Doe',
        email: 'john@example.com',
        phone: '+1 123-456-7890',
        website: 'https://example.com',
      };

      const isNameValid = validateRequired(formData.name) && validateLength(formData.name, { min: 2, max: 50 });
      const isEmailValid = validateRequired(formData.email) && validateEmail(formData.email);
      const isPhoneValid = validatePhone(formData.phone);
      const isWebsiteValid = validateUrl(formData.website);

      expect(isNameValid).toBe(true);
      expect(isEmailValid).toBe(true);
      expect(isPhoneValid).toBe(true);
      expect(isWebsiteValid).toBe(true);
    });

    it('handles partial validation', () => {
      const formData = {
        email: 'invalid-email',
        phone: '123',
      };

      const isEmailValid = validateRequired(formData.email) && validateEmail(formData.email);
      const isPhoneValid = validatePhone(formData.phone);

      expect(isEmailValid).toBe(false);
      expect(isPhoneValid).toBe(false);
    });
  });

  describe('Performance', () => {
    it('validates emails efficiently', () => {
      const start = Date.now();
      for (let i = 0; i < 10000; i++) {
        validateEmail('test@example.com');
      }
      const duration = Date.now() - start;
      expect(duration).toBeLessThan(100); // Should be very fast
    });

    it('validates URLs efficiently', () => {
      const start = Date.now();
      for (let i = 0; i < 10000; i++) {
        validateUrl('https://example.com');
      }
      const duration = Date.now() - start;
      expect(duration).toBeLessThan(100);
    });
  });

  describe('Edge Cases and Special Scenarios', () => {
    it('handles XSS attempts in email validation', () => {
      expect(validateEmail('<script>alert("xss")</script>@example.com')).toBe(false);
      expect(validateEmail('test@example.com"><script>alert("xss")</script>')).toBe(false);
    });

    it('handles SQL injection attempts', () => {
      expect(validateEmail("'; DROP TABLE users; --@example.com")).toBe(false);
      expect(validateUrl("'; DROP TABLE users; --")).toBe(false);
    });

    it('handles very long strings', () => {
      const longString = 'a'.repeat(1000000);
      expect(validateLength(longString, { min: 1000000 })).toBe(true);
      expect(validateLength(longString, { max: 999999 })).toBe(false);
    });

    it('handles null byte characters', () => {
      expect(validateEmail('test\0@example.com')).toBe(false);
      expect(validateUrl('https://example.com/\0path')).toBe(false);
    });

    it('handles newline and tab characters', () => {
      expect(validateEmail('test\n@example.com')).toBe(false);
      expect(validateEmail('test\r@example.com')).toBe(false);
      expect(validateEmail('test\t@example.com')).toBe(false);
    });
  });
});

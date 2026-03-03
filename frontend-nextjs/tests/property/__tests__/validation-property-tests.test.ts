/**
 * FastCheck Property Tests for Validation Utility Functions
 *
 * Tests CRITICAL validation utility invariants from @/lib/validation.ts:
 * - validateEmail: Email format validation invariants
 * - validateRequired: Empty/non-empty detection invariants
 * - validateLength: String length boundary invariants
 * - validateUrl: URL format validation invariants
 * - validatePhone: Phone number format invariants
 * - validateRange: Numeric range boundary invariants
 * - validatePattern: Regex pattern matching invariants
 * - validatePasswordStrength: Password complexity invariants
 *
 * Patterned after Phase 108 property tests:
 * @frontend-nextjs/tests/property/__tests__/chat-state-machine.test.ts
 * @frontend-nextjs/tests/property/__tests__/state-transition-validation.test.ts
 *
 * Using actual validation utilities from codebase:
 * - @/lib/validation.ts (validation utility functions)
 *
 * TDD GREEN phase: Tests validate actual validation behavior without requiring code changes.
 * Focus on validation invariants that hold true across randomly generated inputs.
 */

import fc from 'fast-check';
import {
  validateEmail,
  validateRequired,
  validateLength,
  validateUrl,
  validatePhone,
  validatePasswordStrength,
  validateRange,
  validatePattern
} from '@/lib/validation';

describe('Validation Utilities - validateEmail', () => {

  test('email validation rejects strings without @', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('test', 'example.com', 'noreply', '@example.com', 'test@'),
        (email) => {
          const result = validateEmail(email);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25101 }
    );
  });

  test('email validation rejects non-string values', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(null, undefined, 123, true, {}, []),
        (email) => {
          const result = validateEmail(email as any);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25102 }
    );
  });

  test('email validation accepts valid formats', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(
          'test@example.com',
          'user.name@domain.co.uk',
          'a@b.c',
          'test123@test-domain.com'
        ),
        (email) => {
          const result = validateEmail(email);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25103 }
    );
  });
});

describe('Validation Utilities - validateRequired', () => {

  test('required validation rejects empty values', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('', null, undefined, []),
        (value) => {
          const result = validateRequired(value);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25104 }
    );
  });

  test('required validation accepts non-empty string', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1 }),
        (value) => {
          const result = validateRequired(value);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25105 }
    );
  });

  test('required validation accepts numbers (including 0)', () => {
    fc.assert(
      fc.property(
        fc.float(),
        (value) => {
          if (!isNaN(value)) {
            const result = validateRequired(value);
            expect(result).toBe(true);
          }
          return true;
        }
      ),
      { numRuns: 20, seed: 25106 }
    );
  });

  test('required validation accepts booleans', () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        (value) => {
          const result = validateRequired(value);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25107 }
    );
  });

  test('required validation accepts non-empty arrays', () => {
    fc.assert(
      fc.property(
        fc.array(fc.anything(), { minLength: 1 }),
        (value) => {
          const result = validateRequired(value);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25108 }
    );
  });
});

describe('Validation Utilities - validateLength', () => {

  test('length validation rejects strings shorter than min', () => {
    fc.assert(
      fc.property(
        fc.string({ maxLength: 4 }), fc.integer(5, 20),
        (value, minLen) => {
          if (value.length > 0 && value.length < minLen) {
            const result = validateLength(value, { min: minLen });
            expect(result).toBe(false);
          }
          return true;
        }
      ),
      { numRuns: 20, seed: 25109 }
    );
  });

  test('length validation rejects strings longer than max', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 15 }), fc.integer(5, 10),
        (value, maxLen) => {
          if (value.length > maxLen) {
            const result = validateLength(value, { max: maxLen });
            expect(result).toBe(false);
          }
          return true;
        }
      ),
      { numRuns: 20, seed: 25110 }
    );
  });

  test('length validation rejects empty strings', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(''),
        (value) => {
          const result = validateLength(value, { min: 1, max: 10 });
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25111 }
    );
  });

  test('length validation accepts strings within bounds', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 5, maxLength: 10 }),
        (value) => {
          const result = validateLength(value, { min: 5, max: 10 });
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25112 }
    );
  });
});

describe('Validation Utilities - validateUrl', () => {

  test('url validation rejects strings without :// separator', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('example.com', 'http', 'https', 'www.test.com'),
        (url) => {
          const result = validateUrl(url);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25113 }
    );
  });

  test('url validation rejects empty strings', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(''),
        (url) => {
          const result = validateUrl(url);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25114 }
    );
  });

  test('url validation accepts valid URLs with protocols', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(
          'http://example.com',
          'https://example.com',
          'ftp://example.com',
          'http://localhost:3000',
          'https://sub.domain.co.uk/path?query=value'
        ),
        (url) => {
          const result = validateUrl(url);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25115 }
    );
  });
});

describe('Validation Utilities - validatePhone', () => {

  test('phone validation rejects strings with letters', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('abc', '123abc456', 'phone', 'test123'),
        (phone) => {
          const result = validatePhone(phone);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25116 }
    );
  });

  test('phone validation rejects strings shorter than 10 digits', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('123', '123456', '123456789', '12 34 56'),
        (phone) => {
          const result = validatePhone(phone);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25117 }
    );
  });

  test('phone validation accepts valid phone numbers', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(
          '1234567890',
          '(123) 456-7890',
          '123-456-7890',
          '+1 123 456 7890',
          '123 456 7890'
        ),
        (phone) => {
          const result = validatePhone(phone);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25118 }
    );
  });
});

describe('Validation Utilities - validatePasswordStrength', () => {

  test('password validation rejects short passwords', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('Pass1', 'Abc123', 'Test', '1234567'),
        (password) => {
          const result = validatePasswordStrength(password);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25119 }
    );
  });

  test('password validation rejects passwords without uppercase', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('password123', 'test12345', 'lowercase1'),
        (password) => {
          const result = validatePasswordStrength(password);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25120 }
    );
  });

  test('password validation rejects passwords without lowercase', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('PASSWORD123', 'TEST12345', 'UPPERCASE1'),
        (password) => {
          const result = validatePasswordStrength(password);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25121 }
    );
  });

  test('password validation rejects passwords without numbers', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('PasswordTest', 'TestPassword', 'MyPassword'),
        (password) => {
          const result = validatePasswordStrength(password);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25122 }
    );
  });

  test('password validation accepts strong passwords', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(
          'Password1',
          'Test1234',
          'MyPass123',
          'Secure99',
          'ValidPass1'
        ),
        (password) => {
          const result = validatePasswordStrength(password);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25123 }
    );
  });
});

describe('Validation Utilities - validateRange', () => {

  test('range validation rejects values below min', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(-1, -5, -10, -50, -100),
        (value) => {
          const min = 0;
          const result = validateRange(value, { min });
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25124 }
    );
  });

  test('range validation rejects values above max', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(101, 150, 200, 500, 1000),
        (value) => {
          const max = 100;
          const result = validateRange(value, { max });
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25125 }
    );
  });

  test('range validation rejects NaN', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(NaN),
        (value) => {
          const result = validateRange(value, { min: 0, max: 100 });
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25126 }
    );
  });

  test('range validation accepts values within bounds', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(10, 25, 50, 75, 90),
        (value) => {
          const min = 0;
          const max = 100;
          const result = validateRange(value, { min, max });
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25127 }
    );
  });

  test('range validation accepts boundary values', () => {
    fc.assert(
      fc.property(
        fc.integer(0, 100),
        (min) => {
          const max = min + 100;
          const minResult = validateRange(min, { min, max });
          const maxResult = validateRange(max, { min, max });
          expect(minResult).toBe(true);
          expect(maxResult).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25128 }
    );
  });
});

describe('Validation Utilities - validatePattern', () => {

  test('pattern validation accepts matching strings', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('test', 'abc123', 'TEST', 'value'),
        (value) => {
          const pattern = /^[a-zA-Z0-9]+$/;
          const result = validatePattern(value, pattern);
          expect(result).toBe(true);
          return true;
        }
      ),
      { numRuns: 20, seed: 25129 }
    );
  });

  test('pattern validation rejects non-matching strings', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('test@123', 'hello world', 'test-value', 'test.value'),
        (value) => {
          const pattern = /^[a-zA-Z0-9]+$/;
          const result = validatePattern(value, pattern);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25130 }
    );
  });

  test('pattern validation rejects non-strings', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(null, undefined, 123, true, []),
        (value) => {
          const pattern = /^[a-z]+$/;
          const result = validatePattern(value as any, pattern);
          expect(result).toBe(false);
          return true;
        }
      ),
      { numRuns: 20, seed: 25131 }
    );
  });

  test('pattern validation matches regex correctly', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('abc', 'def', 'ghi', 'test'),
        (value) => {
          const pattern = /^[a-z]+$/;
          const result = validatePattern(value, pattern);
          const matches = pattern.test(value);
          expect(result).toBe(matches);
          return true;
        }
      ),
      { numRuns: 20, seed: 25132 }
    );
  });
});

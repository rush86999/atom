/**
 * Property-Based Tests for Password Validator
 *
 * Tests password validation rules and strength calculation
 */

import fc from 'fast-check';
import { validatePassword, getPasswordStrengthLabel, getPasswordStrengthColor, getPasswordStrengthBarColor } from '../password-validator';

describe('Password Validator - Property-Based Tests', () => {
  // Property 1: Score bounds
  // Score should always be in range [0, 4]
  it('should always return score in range [0, 4]', () => {
    fc.assert(
      fc.property(fc.string(), (password) => {
        const result = validatePassword(password);
        return result.score >= 0 && result.score <= 4;
      }),
      { numRuns: 200 }
    );
  });

  // Property 2: Minimum length requirement
  // Password with length < 12 should fail minLength requirement
  it('should fail minLength for passwords shorter than 12 characters', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 11 }),
        (password) => {
          const result = validatePassword(password);
          return !result.requirements.minLength;
        }
      ),
      { numRuns: 100 }
    );
  });

  // Property 3: Minimum length requirement pass
  // Password with length >= 12 should pass minLength requirement
  it('should pass minLength for passwords with 12+ characters', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 12, maxLength: 100 }),
        (password) => {
          const result = validatePassword(password);
          return result.requirements.minLength;
        }
      ),
      { numRuns: 100 }
    );
  });

  // Property 4: Uppercase detection
  // Password with only lowercase should fail hasUppercase
  it('should fail hasUppercase for lowercase-only passwords', () => {
    const lowerCaseChars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...lowerCaseChars.split('')), { minLength: 12 }),
        (chars) => {
          const password = chars.join('');
          const result = validatePassword(password);
          return !result.requirements.hasUppercase;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 5: Uppercase detection pass
  // Password containing at least one uppercase should pass hasUppercase
  it('should pass hasUppercase for passwords with uppercase letters', () => {
    const upperCaseChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    const otherChars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';

    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...upperCaseChars.split('')), { minLength: 1, maxLength: 5 }),
        fc.array(fc.constantFrom(...otherChars.split('')), { minLength: 11 }),
        (uppercase, rest) => {
          const password = uppercase.join('') + rest.join('');
          const result = validatePassword(password);
          return result.requirements.hasUppercase;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 6: Number detection
  // Password with only letters should fail hasNumber
  it('should fail hasNumber for letters-only passwords', () => {
    const letterChars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*';
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...letterChars.split('')), { minLength: 12 }),
        (chars) => {
          const password = chars.join('');
          const result = validatePassword(password);
          return !result.requirements.hasNumber;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 7: Number detection pass
  // Password containing at least one number should pass hasNumber
  it('should pass hasNumber for passwords with numbers', () => {
    const letterChars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*';
    const numbers = '0123456789';

    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...letterChars.split('')), { minLength: 11 }),
        fc.constantFrom(...numbers.split('')),
        (letters, number) => {
          const password = letters.join('') + number;
          const result = validatePassword(password);
          return result.requirements.hasNumber;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 8: Valid password implies all requirements met
  // If isValid is true, all requirements should be true
  it('should have all requirements true when password is valid', () => {
    fc.assert(
      fc.property(fc.string(), (password) => {
        const result = validatePassword(password);
        if (result.isValid) {
          return Object.values(result.requirements).every((req) => req === true);
        }
        return true; // Invalid passwords can have any requirements state
      }),
      { numRuns: 100 }
    );
  });

  // Property 9: Score monotonicity with requirements
  // More requirements met should generally lead to higher score
  it('should have non-negative correlation between requirements met and score', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 12, maxLength: 20 }),
        fc.string({ minLength: 12, maxLength: 20 }),
        (password1, password2) => {
          const result1 = validatePassword(password1);
          const result2 = validatePassword(password2);

          const reqs1 = Object.values(result1.requirements).filter(Boolean).length;
          const reqs2 = Object.values(result2.requirements).filter(Boolean).length;

          // If password1 meets more requirements, it should have >= score
          if (reqs1 > reqs2) {
            return result1.score >= result2.score;
          }
          return true;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 10: Strength label domain
  // Score in range [0, 4] should always produce a valid label
  it('should always return valid strength label for scores 0-4', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 4 }), (score) => {
        const label = getPasswordStrengthLabel(score);
        return ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'].includes(label);
      }),
      { numRuns: 100 }
    );
  });

  // Property 11: Strength color domain
  // Score in range [0, 4] should always produce a valid color class
  it('should always return valid strength color for scores 0-4', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 4 }), (score) => {
        const color = getPasswordStrengthColor(score);
        return color.startsWith('text-') && color.length > 5;
      }),
      { numRuns: 100 }
    );
  });

  // Property 12: Strength bar color domain
  // Score in range [0, 4] should always produce a valid bar color class
  it('should always return valid bar color for scores 0-4', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 4 }), (score) => {
        const color = getPasswordStrengthBarColor(score);
        return color.startsWith('bg-') && color.length > 4;
      }),
      { numRuns: 100 }
    );
  });

  // Property 13: Deterministic label generation
  // Same score should always produce same label
  it('should be deterministic: same score produces same label', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 4 }), (score) => {
        const label1 = getPasswordStrengthLabel(score);
        const label2 = getPasswordStrengthLabel(score);
        return label1 === label2;
      }),
      { numRuns: 100 }
    );
  });

  // Property 14: Deterministic color generation
  // Same score should always produce same color
  it('should be deterministic: same score produces same color', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 4 }), (score) => {
        const color1 = getPasswordStrengthColor(score);
        const color2 = getPasswordStrengthColor(score);
        return color1 === color2;
      }),
      { numRuns: 100 }
    );
  });

  // Property 15: Common password detection
  // Known common passwords should be detected
  it('should detect common passwords', () => {
    const commonPasswords = ['password', 'password123', '12345678', 'qwerty', 'abc123'];
    commonPasswords.forEach((password) => {
      const result = validatePassword(password);
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });
  });
});

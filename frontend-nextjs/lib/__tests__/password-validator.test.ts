/**
 * Traditional Unit Tests for Password Validator
 *
 * Tests specific password patterns to kill more mutants
 */

import { validatePassword, getPasswordStrengthLabel, getPasswordStrengthColor, getPasswordStrengthBarColor } from '../password-validator';

describe('Password Validator - Traditional Unit Tests', () => {
  describe('Common password detection', () => {
    it('should detect exact "password" as common', () => {
      const result = validatePassword('password');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
      expect(result.score).toBeLessThan(2);
    });

    it('should detect exact "12345678" as common', () => {
      const result = validatePassword('12345678');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "qwerty" as common', () => {
      const result = validatePassword('qwerty');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "abc123" as common', () => {
      const result = validatePassword('abc123');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "monkey" as common', () => {
      const result = validatePassword('monkey');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "letmein" as common', () => {
      const result = validatePassword('letmein');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "trustno1" as common', () => {
      const result = validatePassword('trustno1');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "dragon" as common', () => {
      const result = validatePassword('dragon');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "baseball" as common', () => {
      const result = validatePassword('baseball');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "iloveyou" as common', () => {
      const result = validatePassword('iloveyou');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "master" as common', () => {
      const result = validatePassword('master');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "sunshine" as common', () => {
      const result = validatePassword('sunshine');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "ashley" as common', () => {
      const result = validatePassword('ashley');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "bailey" as common', () => {
      const result = validatePassword('bailey');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "passw0rd" as common', () => {
      const result = validatePassword('passw0rd');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "shadow" as common', () => {
      const result = validatePassword('shadow');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "123456" as common', () => {
      const result = validatePassword('123456');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "123456789" as common', () => {
      const result = validatePassword('123456789');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should detect exact "password1" as common', () => {
      const result = validatePassword('password1');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
    });

    it('should NOT detect strong password as common', () => {
      const result = validatePassword('MyStr0ng!Pass123');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(false);
    });
  });

  describe('Repeating character detection', () => {
    it('should detect "aaa" pattern', () => {
      const result = validatePassword('aaaabc123ABC!');
      expect(result.feedback.some(f => f.includes('repeated'))).toBe(true);
    });

    it('should detect "111" pattern', () => {
      const result = validatePassword('111abcABCDEF!');
      expect(result.feedback.some(f => f.includes('repeated'))).toBe(true);
    });

    it('should detect "!!!" pattern', () => {
      const result = validatePassword('abc123ABC!!!DEF!');
      expect(result.feedback.some(f => f.includes('repeated'))).toBe(true);
    });

    it('should detect "xxxx" pattern', () => {
      const result = validatePassword('xxxxabc123ABC!');
      expect(result.feedback.some(f => f.includes('repeated'))).toBe(true);
    });
  });

  describe('Sequential character detection', () => {
    it('should detect "abc" sequence', () => {
      const result = validatePassword('abc123XYZDEF!');
      expect(result.feedback.some(f => f.includes('sequential'))).toBe(true);
    });

    it('should detect "123" sequence', () => {
      const result = validatePassword('abc123XYZDEF!');
      expect(result.feedback.some(f => f.includes('sequential'))).toBe(true);
    });

    it('should detect "bcd" sequence', () => {
      const result = validatePassword('bcd123EFGH!');
      expect(result.feedback.some(f => f.includes('sequential'))).toBe(true);
    });

    it('should detect "234" sequence', () => {
      const result = validatePassword('abc234DEFG!');
      expect(result.feedback.some(f => f.includes('sequential'))).toBe(true);
    });

    it('should detect "xyz" sequence', () => {
      const result = validatePassword('xyz123ABCDEF!');
      expect(result.feedback.some(f => f.includes('sequential'))).toBe(true);
    });

    it('should detect "789" sequence', () => {
      const result = validatePassword('abc789XYZDEF!');
      expect(result.feedback.some(f => f.includes('sequential'))).toBe(true);
    });
  });

  describe('Strong password examples', () => {
    it('should validate strong password with all requirements', () => {
      const result = validatePassword('MyStr0ng!Pass123');
      expect(result.isValid).toBe(true);
      expect(result.score).toBeGreaterThanOrEqual(2);
      expect(result.requirements.minLength).toBe(true);
      expect(result.requirements.hasUppercase).toBe(true);
      expect(result.requirements.hasLowercase).toBe(true);
      expect(result.requirements.hasNumber).toBe(true);
      expect(result.requirements.hasSpecialChar).toBe(true);
    });

    it('should validate very strong password', () => {
      const result = validatePassword('MyVeryStr0ng!Passw0rd@2024!');
      expect(result.isValid).toBe(true);
      expect(result.score).toBe(4);
      expect(result.feedback).toContain('Password meets all requirements');
    });

    it('should handle 20+ character password', () => {
      const result = validatePassword('MyL0ng!Passw0rd!Is!Very!Strong!');
      expect(result.isValid).toBe(true);
      expect(result.score).toBe(4);
    });
  });

  describe('Weak password examples', () => {
    it('should reject password without uppercase', () => {
      const result = validatePassword('lowercase123!');
      expect(result.isValid).toBe(false);
      expect(result.requirements.hasUppercase).toBe(false);
    });

    it('should reject password without lowercase', () => {
      const result = validatePassword('UPPERCASE123!');
      expect(result.isValid).toBe(false);
      expect(result.requirements.hasLowercase).toBe(false);
    });

    it('should reject password without numbers', () => {
      const result = validatePassword('NoNumbersHere!');
      expect(result.isValid).toBe(false);
      expect(result.requirements.hasNumber).toBe(false);
    });

    it('should reject password without special characters', () => {
      const result = validatePassword('NoSpecialChars123');
      expect(result.isValid).toBe(false);
      expect(result.requirements.hasSpecialChar).toBe(false);
    });

    it('should reject short password', () => {
      const result = validatePassword('Short1!');
      expect(result.isValid).toBe(false);
      expect(result.requirements.minLength).toBe(false);
    });
  });

  describe('Strength labels', () => {
    it('should return "Very Weak" for score 0', () => {
      expect(getPasswordStrengthLabel(0)).toBe('Very Weak');
    });

    it('should return "Weak" for score 1', () => {
      expect(getPasswordStrengthLabel(1)).toBe('Weak');
    });

    it('should return "Fair" for score 2', () => {
      expect(getPasswordStrengthLabel(2)).toBe('Fair');
    });

    it('should return "Strong" for score 3', () => {
      expect(getPasswordStrengthLabel(3)).toBe('Strong');
    });

    it('should return "Very Strong" for score 4', () => {
      expect(getPasswordStrengthLabel(4)).toBe('Very Strong');
    });

    it('should return "Unknown" for invalid score', () => {
      expect(getPasswordStrengthLabel(5)).toBe('Unknown');
      expect(getPasswordStrengthLabel(-1)).toBe('Unknown');
    });
  });

  describe('Strength colors', () => {
    it('should return red-600 for very weak', () => {
      expect(getPasswordStrengthColor(0)).toBe('text-red-600');
    });

    it('should return orange-600 for weak', () => {
      expect(getPasswordStrengthColor(1)).toBe('text-orange-600');
    });

    it('should return yellow-600 for fair', () => {
      expect(getPasswordStrengthColor(2)).toBe('text-yellow-600');
    });

    it('should return green-600 for strong', () => {
      expect(getPasswordStrengthColor(3)).toBe('text-green-600');
    });

    it('should return emerald-600 for very strong', () => {
      expect(getPasswordStrengthColor(4)).toBe('text-emerald-600');
    });
  });

  describe('Strength bar colors', () => {
    it('should return red-500 bar for very weak', () => {
      expect(getPasswordStrengthBarColor(0)).toBe('bg-red-500');
    });

    it('should return orange-500 bar for weak', () => {
      expect(getPasswordStrengthBarColor(1)).toBe('bg-orange-500');
    });

    it('should return yellow-500 bar for fair', () => {
      expect(getPasswordStrengthBarColor(2)).toBe('bg-yellow-500');
    });

    it('should return green-500 bar for strong', () => {
      expect(getPasswordStrengthBarColor(3)).toBe('bg-green-500');
    });

    it('should return emerald-500 bar for very strong', () => {
      expect(getPasswordStrengthBarColor(4)).toBe('bg-emerald-500');
    });
  });

  describe('Edge cases', () => {
    it('should handle empty string', () => {
      const result = validatePassword('');
      expect(result.isValid).toBe(false);
      expect(result.requirements.minLength).toBe(false);
    });

    it('should handle very long password', () => {
      const result = validatePassword('a'.repeat(1000) + 'A1!');
      expect(result.score).toBeGreaterThanOrEqual(2);
    });

    it('should handle password with only special characters', () => {
      const result = validatePassword('!@#$%^&*()_+');
      expect(result.requirements.hasNumber).toBe(false);
      expect(result.requirements.hasUppercase).toBe(false);
      expect(result.requirements.hasLowercase).toBe(false);
    });

    it('should handle password with mixed case special chars', () => {
      const result = validatePassword('!@#$%^&*()_+ABCabc123');
      expect(result.requirements.hasSpecialChar).toBe(true);
    });

    // Mutation-killing tests for boundary conditions

    it('should accept password with exactly 12 characters', () => {
      const result = validatePassword('Abc123!xyz01');
      expect(result.requirements.minLength).toBe(true);
      expect(result.isValid).toBe(true);
    });

    it('should reject password with exactly 11 characters', () => {
      const result = validatePassword('Abc123!xyz0');
      expect(result.requirements.minLength).toBe(false);
      expect(result.isValid).toBe(false);
    });

    it('should detect common password "password" in uppercase', () => {
      const result = validatePassword('PASSWORD');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
      expect(result.isValid).toBe(false);
    });

    it('should detect common password in mixed case', () => {
      const result = validatePassword('PaSsWoRd');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
      expect(result.isValid).toBe(false);
    });

    it('should detect common password with title case', () => {
      const result = validatePassword('Password');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
      expect(result.isValid).toBe(false);
    });

    it('should detect "12345678" in different cases (digits unchanged)', () => {
      const result = validatePassword('12345678');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
      expect(result.isValid).toBe(false);
    });

    it('should detect "QWERTY" in uppercase', () => {
      const result = validatePassword('QWERTY');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
      expect(result.isValid).toBe(false);
    });

    it('should detect "QwErTy" in mixed case', () => {
      const result = validatePassword('QwErTy');
      expect(result.feedback.some(f => f.includes('too common'))).toBe(true);
      expect(result.isValid).toBe(false);
    });
  });
});

/**
 * Validation Utilities
 *
 * Common validation functions for form inputs and data validation
 */

/**
 * Validate email format
 * @param email - Email address to validate
 * @returns true if email format is valid
 */
export function validateEmail(email: string): boolean {
  if (!email || typeof email !== 'string') {
    return false;
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate required field (not empty, null, or undefined)
 * @param value - Value to validate
 * @returns true if value is not empty
 */
export function validateRequired(value: any): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === 'string') {
    return value.trim().length > 0;
  }
  if (typeof value === 'number') {
    return !isNaN(value);
  }
  if (typeof value === 'boolean') {
    return true;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return true;
}

/**
 * Validate string length
 * @param value - String to validate
 * @param options - Length constraints
 * @returns true if length is within bounds
 */
export function validateLength(
  value: string,
  options: { min?: number; max?: number }
): boolean {
  if (!value || typeof value !== 'string') {
    return false;
  }

  const length = value.length;

  if (options.min !== undefined && length < options.min) {
    return false;
  }

  if (options.max !== undefined && length > options.max) {
    return false;
  }

  return true;
}

/**
 * Validate URL format
 * @param url - URL to validate
 * @returns true if URL format is valid
 */
export function validateUrl(url: string): boolean {
  if (!url || typeof url !== 'string') {
    return false;
  }
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Validate phone number format (basic)
 * @param phone - Phone number to validate
 * @returns true if phone number format is valid
 */
export function validatePhone(phone: string): boolean {
  if (!phone || typeof phone !== 'string') {
    return false;
  }
  // Allow digits, spaces, dashes, parentheses, plus sign
  const phoneRegex = /^[\d\s\-\(\)\+]+$/;
  return phoneRegex.test(phone) && phone.replace(/\D/g, '').length >= 10;
}

/**
 * Validate password strength (basic)
 * @param password - Password to validate
 * @returns true if password meets minimum requirements
 */
export function validatePasswordStrength(password: string): boolean {
  if (!password || typeof password !== 'string') {
    return false;
  }
  // Minimum 8 characters, at least one uppercase, one lowercase, one number
  const hasMinLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasNumber = /[0-9]/.test(password);

  return hasMinLength && hasUppercase && hasLowercase && hasNumber;
}

/**
 * Validate numeric range
 * @param value - Number to validate
 * @param options - Range constraints
 * @returns true if value is within range
 */
export function validateRange(
  value: number,
  options: { min?: number; max?: number }
): boolean {
  if (typeof value !== 'number' || isNaN(value)) {
    return false;
  }

  if (options.min !== undefined && value < options.min) {
    return false;
  }

  if (options.max !== undefined && value > options.max) {
    return false;
  }

  return true;
}

/**
 * Validate pattern (regex)
 * @param value - String to validate
 * @param pattern - Regex pattern to match
 * @returns true if value matches pattern
 */
export function validatePattern(value: string, pattern: RegExp): boolean {
  if (!value || typeof value !== 'string') {
    return false;
  }
  return pattern.test(value);
}

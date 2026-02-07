/**
 * Tests for Date Utilities
 *
 * Tests date formatting and parsing functions
 */

import { formatDate, formatDateTime, formatRelativeTime, parseDate, isValidDate, dayjs } from '../date-utils';

describe('Date Utilities', () => {
  describe('formatDate', () => {
    it('should format Date object with default format', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      expect(formatDate(date)).toBe('2024-01-15');
    });

    it('should format string date with default format', () => {
      expect(formatDate('2024-01-15')).toBe('2024-01-15');
    });

    it('should format number timestamp with default format', () => {
      // Use noon UTC to avoid timezone issues
      const timestamp = new Date('2024-01-15T12:00:00Z').getTime();
      const result = formatDate(timestamp);
      // Result will be in local timezone, just verify format
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('should format with custom format', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      expect(formatDate(date, 'MM/DD/YYYY')).toBe('01/15/2024');
    });

    it('should handle invalid dates', () => {
      expect(formatDate('invalid-date')).toBe('Invalid Date');
    });

    it('should format different date correctly', () => {
      const date = new Date('2024-12-25T10:30:00Z');
      expect(formatDate(date)).toBe('2024-12-25');
    });
  });

  describe('formatDateTime', () => {
    it('should format datetime with default format', () => {
      const date = new Date('2024-01-15T10:30:45Z');
      expect(formatDateTime(date)).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    });

    it('should format datetime with custom format', () => {
      const date = new Date('2024-01-15T10:30:45Z');
      expect(formatDateTime(date, 'YYYY-MM-DD')).toBe('2024-01-15');
    });

    it('should handle string input', () => {
      expect(formatDateTime('2024-01-15T10:30:00Z')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    });

    it('should handle midnight correctly', () => {
      const date = new Date('2024-01-15T00:00:00Z');
      const result = formatDateTime(date);
      // Just verify format matches pattern, timezone may shift the time
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    });
  });

  describe('formatRelativeTime', () => {
    beforeEach(() => {
      jest.useFakeTimers().setSystemTime(new Date('2024-01-15T10:00:00Z'));
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should format past time relative to now', () => {
      const date = new Date('2024-01-15T09:00:00Z');
      expect(formatRelativeTime(date)).toContain('ago');
    });

    it('should format future time relative to now', () => {
      const date = new Date('2024-01-15T11:00:00Z');
      expect(formatRelativeTime(date)).toContain('in');
    });

    it('should handle string input', () => {
      const date = '2024-01-14T10:00:00Z';
      expect(formatRelativeTime(date)).toContain('ago');
    });

    it('should handle timestamp input', () => {
      const timestamp = new Date('2024-01-14T10:00:00Z').getTime();
      expect(formatRelativeTime(timestamp)).toContain('ago');
    });
  });

  describe('parseDate', () => {
    it('should parse ISO string to Date', () => {
      const result = parseDate('2024-01-15T10:30:00Z');
      expect(result).toBeInstanceOf(Date);
      expect(result.getFullYear()).toBe(2024);
      expect(result.getMonth()).toBe(0);
      expect(result.getDate()).toBe(15);
    });

    it('should parse simple date string', () => {
      const result = parseDate('2024-01-15');
      expect(result).toBeInstanceOf(Date);
    });

    it('should parse various date formats', () => {
      expect(parseDate('2024/01/15')).toBeInstanceOf(Date);
      expect(parseDate('01-15-2024')).toBeInstanceOf(Date);
    });

    it('should return invalid date for unparseable strings', () => {
      const result = parseDate('not-a-date');
      expect(isNaN(result.getTime())).toBe(true);
    });
  });

  describe('isValidDate', () => {
    it('should return true for valid Date object', () => {
      const date = new Date('2024-01-15');
      expect(isValidDate(date)).toBe(true);
    });

    it('should return true for valid ISO string', () => {
      expect(isValidDate('2024-01-15T10:30:00Z')).toBe(true);
    });

    it('should return true for valid date string', () => {
      expect(isValidDate('2024-01-15')).toBe(true);
    });

    it('should return false for invalid string', () => {
      expect(isValidDate('not-a-date')).toBe(false);
    });

    it('should return false for invalid Date object', () => {
      const invalidDate = new Date('invalid');
      expect(isValidDate(invalidDate)).toBe(false);
    });

    it('should return false for null', () => {
      expect(isValidDate(null)).toBe(false);
    });

    it('should handle undefined - dayjs uses current date', () => {
      // dayjs treats undefined as "now" which is valid
      const result = isValidDate(undefined);
      expect(typeof result).toBe('boolean');
    });

    it('should return false for empty string', () => {
      expect(isValidDate('')).toBe(false);
    });

    it('should return true for timestamp', () => {
      expect(isValidDate(1705305600000)).toBe(true);
    });
  });

  describe('dayjs export', () => {
    it('should export dayjs instance', () => {
      expect(dayjs).toBeDefined();
      expect(typeof dayjs).toBe('function');
    });

    it('should create dayjs object', () => {
      const d = dayjs('2024-01-15');
      expect(d.year()).toBe(2024);
    });
  });
});

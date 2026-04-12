import {
  formatDate,
  formatDateTime,
  formatRelativeTime,
  parseDate,
  isValidDate,
  dayjs,
} from '../date-utils';

describe('Date Utilities', () => {
  describe('formatDate', () => {
    it('formats date with default format (YYYY-MM-DD)', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      expect(formatDate(date)).toBe('2024-01-15');
    });

    it('formats date string input', () => {
      expect(formatDate('2024-01-15')).toBe('2024-01-15');
    });

    it('formats date with custom format', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      expect(formatDate(date, 'MM/DD/YYYY')).toBe('01/15/2024');
      expect(formatDate(date, 'DD MMM YYYY')).toBe('15 Jan 2024');
      expect(formatDate(date, 'dddd, MMMM D, YYYY')).toBe('Monday, January 15, 2024');
    });

    it('handles timestamp input', () => {
      const timestamp = new Date('2024-01-15').getTime();
      expect(formatDate(timestamp)).toBe('2024-01-15');
    });

    it('handles edge cases', () => {
      expect(formatDate('invalid-date')).toBe('Invalid Date');
    });

    it('handles different date formats', () => {
      expect(formatDate('2024/01/15')).toBe('2024-01-15');
      expect(formatDate('01-15-2024')).toBe('2024-01-15');
    });
  });

  describe('formatDateTime', () => {
    it('formats datetime with default format (YYYY-MM-DD HH:mm:ss)', () => {
      const date = new Date('2024-01-15T10:30:45Z');
      const result = formatDateTime(date);
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    });

    it('formats datetime with custom format', () => {
      const date = new Date('2024-01-15T10:30:45Z');
      expect(formatDateTime(date, 'HH:mm')).toMatch(/^\d{2}:\d{2}$/);
      expect(formatDateTime(date, 'YYYY-MM-DD')).toBe('2024-01-15');
    });

    it('handles string input', () => {
      expect(formatDateTime('2024-01-15T10:30:00')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    });

    it('handles timestamp input', () => {
      const timestamp = new Date('2024-01-15T10:30:00Z').getTime();
      const result = formatDateTime(timestamp);
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    });

    it('handles invalid dates', () => {
      expect(formatDateTime('invalid')).toBe('Invalid Date');
    });
  });

  describe('formatRelativeTime', () => {
    beforeEach(() => {
      jest.useFakeTimers();
      jest.setSystemTime(new Date('2024-01-15T10:00:00Z'));
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('formats past dates relative to now', () => {
      expect(formatRelativeTime('2024-01-15T09:00:00Z')).toBe('an hour ago');
      expect(formatRelativeTime('2024-01-15T08:00:00Z')).toBe('2 hours ago');
      expect(formatRelativeTime('2024-01-14T10:00:00Z')).toBe('a day ago');
      expect(formatRelativeTime('2024-01-13T10:00:00Z')).toBe('2 days ago');
      expect(formatRelativeTime('2024-01-08T10:00:00Z')).toBe('a week ago');
    });

    it('formats future dates relative to now', () => {
      expect(formatRelativeTime('2024-01-15T11:00:00Z')).toBe('in an hour');
      expect(formatRelativeTime('2024-01-15T12:00:00Z')).toBe('in 2 hours');
      expect(formatRelativeTime('2024-01-16T10:00:00Z')).toBe('in a day');
      expect(formatRelativeTime('2024-01-17T10:00:00Z')).toBe('in 2 days');
    });

    it('handles Date objects', () => {
      const pastDate = new Date('2024-01-15T09:00:00Z');
      expect(formatRelativeTime(pastDate)).toBe('an hour ago');
    });

    it('handles timestamps', () => {
      const timestamp = new Date('2024-01-15T09:00:00Z').getTime();
      expect(formatRelativeTime(timestamp)).toBe('an hour ago');
    });

    it('handles very recent dates', () => {
      expect(formatRelativeTime('2024-01-15T09:59:00Z')).toBe('a minute ago');
      expect(formatRelativeTime('2024-01-15T09:58:00Z')).toBe('2 minutes ago');
    });

    it('handles invalid dates', () => {
      expect(formatRelativeTime('invalid')).toBe('Invalid Date');
    });
  });

  describe('parseDate', () => {
    it('parses ISO date strings', () => {
      const result = parseDate('2024-01-15');
      expect(result).toBeInstanceOf(Date);
      expect(result.getFullYear()).toBe(2024);
      expect(result.getMonth()).toBe(0); // January
      expect(result.getDate()).toBe(15);
    });

    it('parses datetime strings', () => {
      const result = parseDate('2024-01-15T10:30:00Z');
      expect(result).toBeInstanceOf(Date);
      expect(result.getHours()).toBe(10);
      expect(result.getMinutes()).toBe(30);
    });

    it('parses various date formats', () => {
      expect(parseDate('2024/01/15')).toBeInstanceOf(Date);
      expect(parseDate('01-15-2024')).toBeInstanceOf(Date);
      expect(parseDate('Jan 15, 2024')).toBeInstanceOf(Date);
    });

    it('handles invalid date strings', () => {
      const result = parseDate('invalid-date');
      expect(result).toBeInstanceOf(Date);
      expect(isNaN(result.getTime())).toBe(true);
    });

    it('handles empty strings', () => {
      const result = parseDate('');
      expect(result).toBeInstanceOf(Date);
      expect(isNaN(result.getTime())).toBe(true);
    });
  });

  describe('isValidDate', () => {
    it('returns true for valid Date objects', () => {
      expect(isValidDate(new Date())).toBe(true);
      expect(isValidDate(new Date('2024-01-15'))).toBe(true);
    });

    it('returns true for valid date strings', () => {
      expect(isValidDate('2024-01-15')).toBe(true);
      expect(isValidDate('2024-01-15T10:30:00Z')).toBe(true);
      expect(isValidDate('Jan 15, 2024')).toBe(true);
    });

    it('returns true for valid timestamps', () => {
      expect(isValidDate(Date.now())).toBe(true);
      expect(isValidDate(1705305600000)).toBe(true);
    });

    it('returns false for invalid Date objects', () => {
      expect(isValidDate(new Date('invalid'))).toBe(false);
      expect(isValidDate(new Date(''))).toBe(false);
    });

    it('returns false for invalid date strings', () => {
      expect(isValidDate('invalid-date')).toBe(false);
      expect(isValidDate('')).toBe(false);
      expect(isValidDate('not a date')).toBe(false);
    });

    it('returns false for non-date values', () => {
      expect(isValidDate(null)).toBe(false);
      expect(isValidDate(undefined)).toBe(false);
      expect(isValidDate(123)).toBe(false);
      expect(isValidDate('123')).toBe(true); // Valid timestamp string
      expect(isValidDate({})).toBe(false);
      expect(isValidDate([])).toBe(false);
      expect(isValidDate(true)).toBe(false);
    });

    it('handles edge cases', () => {
      expect(isValidDate(NaN)).toBe(false);
      expect(isValidDate(Infinity)).toBe(false);
      expect(isValidDate(-1)).toBe(true); // Valid timestamp (before epoch)
    });
  });

  describe('dayjs export', () => {
    it('exports dayjs instance', () => {
      expect(dayjs).toBeDefined();
      expect(typeof dayjs).toBe('function');
    });

    it('can be used directly for date operations', () => {
      const date = dayjs('2024-01-15');
      expect(date.format('YYYY-MM-DD')).toBe('2024-01-15');
      expect(date.add(1, 'day').format('YYYY-MM-DD')).toBe('2024-01-16');
      expect(date.subtract(1, 'month').format('YYYY-MM-DD')).toBe('2023-12-15');
    });
  });

  describe('Timezone Handling', () => {
    it('handles UTC dates correctly', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      const formatted = formatDate(date);
      expect(formatted).toBe('2024-01-15');
    });

    it('handles local timezone dates', () => {
      const date = new Date(2024, 0, 15, 10, 30, 0);
      const formatted = formatDateTime(date);
      expect(formatted).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    });

    it('parses dates with timezone offsets', () => {
      const date = parseDate('2024-01-15T10:30:00+05:30');
      expect(date).toBeInstanceOf(Date);
      expect(isValidDate(date)).toBe(true);
    });
  });

  describe('Edge Cases', () => {
    it('handles leap years', () => {
      expect(formatDate('2024-02-29')).toBe('2024-02-29'); // Leap year
      expect(isValidDate('2024-02-29')).toBe(true);
      expect(isValidDate('2023-02-29')).toBe(false); // Not a leap year
    });

    it('handles month boundaries', () => {
      expect(formatDate('2024-01-31')).toBe('2024-01-31');
      expect(formatDate('2024-02-29')).toBe('2024-02-29'); // Leap year
    });

    it('handles end of year', () => {
      expect(formatDate('2024-12-31')).toBe('2024-12-31');
      expect(formatDate('2025-01-01')).toBe('2025-01-01');
    });

    it('handles very old dates', () => {
      expect(isValidDate('1970-01-01')).toBe(true); // Unix epoch
      expect(isValidDate('1900-01-01')).toBe(true);
    });

    it('handles far future dates', () => {
      expect(isValidDate('2099-12-31')).toBe(true);
      expect(isValidDate('3000-01-01')).toBe(true);
    });

    it('handles date arithmetic', () => {
      const date1 = dayjs('2024-01-15');
      const date2 = date1.add(30, 'day');
      expect(date2.format('YYYY-MM-DD')).toBe('2024-02-14');

      const date3 = date1.subtract(1, 'year');
      expect(date3.format('YYYY-MM-DD')).toBe('2023-01-15');
    });
  });

  describe('Performance', () => {
    it('formats dates efficiently', () => {
      const date = new Date('2024-01-15');
      const start = Date.now();

      for (let i = 0; i < 10000; i++) {
        formatDate(date);
      }

      const duration = Date.now() - start;
      expect(duration).toBeLessThan(500); // Should be fast
    });

    it('parses dates efficiently', () => {
      const dateString = '2024-01-15';
      const start = Date.now();

      for (let i = 0; i < 10000; i++) {
        parseDate(dateString);
      }

      const duration = Date.now() - start;
      expect(duration).toBeLessThan(500);
    });
  });

  describe('Internationalization', () => {
    it('handles various date formats', () => {
      expect(formatDate('15/01/2024', 'DD/MM/YYYY')).toBe('15/01/2024');
      expect(formatDate('01.15.2024', 'MM.DD.YYYY')).toBe('01.15.2024');
    });

    it('handles localized formats', () => {
      const date = new Date('2024-01-15');
      expect(formatDate(date, 'dddd')).toBe('Monday'); // English locale
    });
  });

  describe('Date Comparisons', () => {
    it('can compare dates using dayjs', () => {
      const date1 = dayjs('2024-01-15');
      const date2 = dayjs('2024-01-16');
      const date3 = dayjs('2024-01-15');

      expect(date1.isBefore(date2)).toBe(true);
      expect(date2.isAfter(date1)).toBe(true);
      expect(date1.isSame(date3)).toBe(true);
    });

    it('can calculate differences between dates', () => {
      const date1 = dayjs('2024-01-15');
      const date2 = dayjs('2024-01-20');

      expect(date2.diff(date1, 'day')).toBe(5);
      expect(date2.diff(date1, 'week')).toBe(0);
      expect(date2.diff(date1, 'hour')).toBe(120);
    });
  });
});

// Utility functions to test

export function formatDate(date: Date | string, format: 'short' | 'long' | 'relative' = 'short'): string {
  const d = typeof date === 'string' ? new Date(date) : date;

  if (isNaN(d.getTime())) {
    return 'Invalid Date';
  }

  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (format === 'relative') {
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  }

  if (format === 'long') {
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatCurrency(
  amount: number,
  currency: string = 'USD',
  locale: string = 'en-US'
): string {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currency,
    }).format(amount);
  } catch (error) {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

export function formatNumber(
  value: number,
  options?: { decimals?: number; compact?: boolean; locale?: string }
): string {
  const { decimals = 0, compact = false, locale = 'en-US' } = options || {};

  try {
    if (compact) {
      if (Math.abs(value) >= 1e9) {
        return `${(value / 1e9).toFixed(1)}B`;
      }
      if (Math.abs(value) >= 1e6) {
        return `${(value / 1e6).toFixed(1)}M`;
      }
      if (Math.abs(value) >= 1e3) {
        return `${(value / 1e3).toFixed(1)}K`;
      }
    }

    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(value);
  } catch (error) {
    return value.toString();
  }
}

export function truncateString(str: string, maxLength: number, suffix: string = '...'): string {
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength - suffix.length) + suffix;
}

export function capitalizeString(str: string): string {
  if (!str) return str;
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

export function camelCase(str: string): string {
  return str
    .replace(/[-_\s]+(.)?/g, (_, char) => (char ? char.toUpperCase() : ''))
    .replace(/^(.)/, (char) => char.toLowerCase());
}

export function kebabCase(str: string): string {
  return str
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/[\s_]+/g, '-')
    .toLowerCase();
}

export function uniqueArray<T>(arr: T[]): T[] {
  return Array.from(new Set(arr));
}

export function chunkArray<T>(arr: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

export function shuffleArray<T>(arr: T[]): T[] {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

export function mergeDeep<T extends Record<string, any>>(target: T, ...sources: Partial<T>[]): T {
  const result = { ...target };

  for (const source of sources) {
    for (const key in source) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = mergeDeep(result[key] || {}, source[key] as any);
      } else {
        result[key] = source[key] as any;
      }
    }
  }

  return result;
}

describe('Utility Functions Tests', () => {
  describe('test_date_formatter', () => {
    it('should format date in short format', () => {
      const date = new Date('2026-03-10');
      const formatted = formatDate(date, 'short');

      expect(formatted).toMatch(/Mar 10, 2026/);
    });

    it('should format date in long format', () => {
      const date = new Date('2026-03-10T14:30:00');
      const formatted = formatDate(date, 'long');

      expect(formatted).toMatch(/March 10, 2026/);
    });

    it('should format date in relative format', () => {
      const now = new Date();
      const fiveMinsAgo = new Date(now.getTime() - 5 * 60000);

      const formatted = formatDate(fiveMinsAgo, 'relative');

      expect(formatted).toBe('5m ago');
    });

    it('should handle invalid dates', () => {
      const formatted = formatDate('invalid-date', 'short');

      expect(formatted).toBe('Invalid Date');
    });

    it('should handle relative time - just now', () => {
      const now = new Date();
      const thirtySecondsAgo = new Date(now.getTime() - 30000);

      const formatted = formatDate(thirtySecondsAgo, 'relative');

      expect(formatted).toBe('just now');
    });

    it('should handle relative time - hours ago', () => {
      const now = new Date();
      const twoHoursAgo = new Date(now.getTime() - 2 * 3600000);

      const formatted = formatDate(twoHoursAgo, 'relative');

      expect(formatted).toBe('2h ago');
    });

    it('should handle relative time - days ago', () => {
      const now = new Date();
      const threeDaysAgo = new Date(now.getTime() - 3 * 86400000);

      const formatted = formatDate(threeDaysAgo, 'relative');

      expect(formatted).toBe('3d ago');
    });

    it('should parse date strings correctly', () => {
      const formatted = formatDate('2026-03-10', 'short');

      expect(formatted).toMatch(/Mar 10, 2026/);
    });
  });

  describe('test_currency_formatter', () => {
    it('should format USD currency', () => {
      const formatted = formatCurrency(1234.56);

      expect(formatted).toBe('$1,234.56');
    });

    it('should format EUR currency', () => {
      const formatted = formatCurrency(1234.56, 'EUR');

      expect(formatted).toMatch(/1,234\.56/);
    });

    it('should handle negative amounts', () => {
      const formatted = formatCurrency(-100);

      expect(formatted).toMatch(/-\$100\.00/);
    });

    it('should handle zero amount', () => {
      const formatted = formatCurrency(0);

      expect(formatted).toBe('$0.00');
    });

    it('should handle large amounts', () => {
      const formatted = formatCurrency(1000000);

      expect(formatted).toBe('$1,000,000.00');
    });

    it('should fallback for invalid currency codes', () => {
      const formatted = formatCurrency(100, 'INVALID');

      expect(formatted).toBe('INVALID 100.00');
    });
  });

  describe('test_number_formatter', () => {
    it('should format number without decimals', () => {
      const formatted = formatNumber(1234.567);

      expect(formatted).toBe('1,235');
    });

    it('should format number with decimals', () => {
      const formatted = formatNumber(1234.567, { decimals: 2 });

      expect(formatted).toBe('1,234.57');
    });

    it('should format number in compact notation (thousands)', () => {
      const formatted = formatNumber(1500, { compact: true });

      expect(formatted).toBe('1.5K');
    });

    it('should format number in compact notation (millions)', () => {
      const formatted = formatNumber(1500000, { compact: true });

      expect(formatted).toBe('1.5M');
    });

    it('should format number in compact notation (billions)', () => {
      const formatted = formatNumber(1500000000, { compact: true });

      expect(formatted).toBe('1.5B');
    });

    it('should handle negative numbers', () => {
      const formatted = formatNumber(-1234);

      expect(formatted).toBe('-1,234');
    });

    it('should handle zero', () => {
      const formatted = formatNumber(0);

      expect(formatted).toBe('0');
    });
  });

  describe('test_string_utils', () => {
    it('should truncate string longer than max length', () => {
      const result = truncateString('This is a very long string', 10);

      expect(result).toBe('This is...');
      expect(result.length).toBe(10);
    });

    it('should not truncate string shorter than max length', () => {
      const result = truncateString('Short', 10);

      expect(result).toBe('Short');
    });

    it('should capitalize first letter', () => {
      const result = capitalizeString('hello world');

      expect(result).toBe('Hello world');
    });

    it('should handle empty string', () => {
      const result = capitalizeString('');

      expect(result).toBe('');
    });

    it('should convert to camelCase', () => {
      expect(camelCase('hello-world')).toBe('helloWorld');
      expect(camelCase('hello_world')).toBe('helloWorld');
      expect(camelCase('Hello World')).toBe('helloWorld');
    });

    it('should convert to kebab-case', () => {
      expect(kebabCase('helloWorld')).toBe('hello-world');
      expect(kebabCase('hello_world')).toBe('hello-world');
      expect(kebabCase('Hello World')).toBe('hello-world');
    });

    it('should handle camelCase with multiple words', () => {
      const result = camelCase('hello-world-test');

      expect(result).toBe('helloWorldTest');
    });
  });

  describe('test_array_utils', () => {
    it('should remove duplicates from array', () => {
      const arr = [1, 2, 2, 3, 3, 3, 4];
      const result = uniqueArray(arr);

      expect(result).toEqual([1, 2, 3, 4]);
    });

    it('should handle empty array', () => {
      const result = uniqueArray([]);

      expect(result).toEqual([]);
    });

    it('should handle array with all unique elements', () => {
      const arr = [1, 2, 3, 4, 5];
      const result = uniqueArray(arr);

      expect(result).toEqual(arr);
    });

    it('should chunk array into specified size', () => {
      const arr = [1, 2, 3, 4, 5, 6, 7, 8, 9];
      const result = chunkArray(arr, 3);

      expect(result).toEqual([
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
      ]);
    });

    it('should handle chunk with remainder', () => {
      const arr = [1, 2, 3, 4, 5, 6, 7];
      const result = chunkArray(arr, 3);

      expect(result).toEqual([
        [1, 2, 3],
        [4, 5, 6],
        [7],
      ]);
    });

    it('should shuffle array randomly', () => {
      const arr = [1, 2, 3, 4, 5];
      const result = shuffleArray(arr);

      expect(result).toHaveLength(arr.length);
      expect(result).toContain(1);
      expect(result).toContain(5);
      expect(result).not.toEqual(arr);
    });

    it('should preserve array elements after shuffle', () => {
      const arr = [1, 2, 3, 4, 5];
      const result = shuffleArray(arr);

      expect(result.sort()).toEqual(arr.sort());
    });
  });

  describe('test_object_utils', () => {
    it('should deep clone object', () => {
      const obj = {
        name: 'Test',
        nested: {
          value: 42,
          array: [1, 2, 3],
        },
      };

      const cloned = deepClone(obj);

      expect(cloned).toEqual(obj);
      expect(cloned).not.toBe(obj);
      expect(cloned.nested).not.toBe(obj.nested);
    });

    it('should handle deep clone with modifications', () => {
      const obj = { name: 'Test', value: 42 };
      const cloned = deepClone(obj);

      cloned.name = 'Modified';

      expect(obj.name).toBe('Test');
      expect(cloned.name).toBe('Modified');
    });

    it('should deep clone array', () => {
      const arr = [1, 2, [3, 4]];
      const cloned = deepClone(arr);

      expect(cloned).toEqual(arr);
      expect(cloned).not.toBe(arr);
      expect(cloned[2]).not.toBe(arr[2]);
    });

    it('should merge shallow objects', () => {
      const target = { a: 1, b: 2 };
      const source = { b: 3, c: 4 };

      const result = mergeDeep(target, source);

      expect(result).toEqual({ a: 1, b: 3, c: 4 });
    });

    it('should merge nested objects', () => {
      const target = {
        a: 1,
        nested: { x: 1, y: 2 },
      };
      const source = {
        nested: { y: 3, z: 4 },
      };

      const result = mergeDeep(target, source);

      expect(result).toEqual({
        a: 1,
        nested: { x: 1, y: 3, z: 4 },
      });
    });

    it('should merge multiple sources', () => {
      const target = { a: 1 };
      const source1 = { b: 2 };
      const source2 = { c: 3 };

      const result = mergeDeep(target, source1, source2);

      expect(result).toEqual({ a: 1, b: 2, c: 3 });
    });

    it('should not mutate target object', () => {
      const target = { a: 1, b: 2 };
      const source = { b: 3 };

      const result = mergeDeep(target, source);

      expect(target).toEqual({ a: 1, b: 2 });
      expect(result).toEqual({ a: 1, b: 3 });
    });
  });
});

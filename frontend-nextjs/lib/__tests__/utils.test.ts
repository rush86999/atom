/**
 * Tests for Utility Functions
 *
 * Tests the cn() utility function for merging Tailwind classes
 */

import { cn } from '../utils';

describe('cn (class name utility)', () => {
  it('should merge class names correctly', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1');
  });

  it('should handle empty strings', () => {
    expect(cn('')).toBe('');
  });

  it('should handle undefined and null values', () => {
    expect(cn(undefined, null, 'px-2')).toBe('px-2');
  });

  it('should handle conditional classes', () => {
    expect(cn('px-2', false && 'hidden', 'py-1')).toBe('px-2 py-1');
  });

  it('should override conflicting Tailwind classes', () => {
    // twMerge should handle conflicts - later classes win
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });

  it('should handle arrays of classes', () => {
    expect(cn(['px-2', 'py-1'], 'bg-white')).toBe('px-2 py-1 bg-white');
  });

  it('should handle objects with boolean values', () => {
    expect(cn({ 'px-2': true, 'hidden': false, 'py-1': true })).toBe('px-2 py-1');
  });

  it('should handle mixed input types', () => {
    expect(cn('base-class', ['array-class'], { 'conditional': true }, null)).toBe(
      'base-class array-class conditional'
    );
  });

  it('should return empty string when all inputs are falsy', () => {
    expect(cn(false, null, undefined, '')).toBe('');
  });

  it('should handle complex Tailwind conflicts', () => {
    // Later classes should override earlier ones for same property
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });

  it('should preserve non-conflicting classes', () => {
    expect(cn('px-2', 'py-1', 'bg-white')).toBe('px-2 py-1 bg-white');
  });
});

/**
 * Tests for lib/utils.ts
 *
 * Testing utility functions for classnames merging
 */

import { cn } from '../utils';

describe('cn() - classnames utility', () => {
  describe('basic merging', () => {
    it('should merge class strings correctly', () => {
      expect(cn('foo', 'bar')).toBe('foo bar');
    });

    it('should handle single class', () => {
      expect(cn('foo')).toBe('foo');
    });

    it('should handle empty strings', () => {
      expect(cn('foo', '', 'bar')).toBe('foo bar');
    });

    it('should handle no arguments', () => {
      expect(cn()).toBe('');
    });

    it('should handle null and undefined', () => {
      expect(cn(null, undefined, 'foo')).toBe('foo');
      expect(cn('foo', null, 'bar')).toBe('foo bar');
    });
  });

  describe('Tailwind conflict resolution', () => {
    it('should resolve conflicting Tailwind classes', () => {
      // Later classes should override earlier ones
      expect(cn('px-2', 'px-4')).toBe('px-4');
    });

    it('should handle multiple conflicting classes', () => {
      expect(cn('p-4 bg-red-500', 'p-2 bg-blue-500')).toBe('p-2 bg-blue-500');
    });

    it('should preserve non-conflicting classes', () => {
      expect(cn('px-4', 'py-2')).toBe('px-4 py-2');
    });

    it('should handle complex class combinations', () => {
      expect(cn('flex items-center justify-between', 'flex-col')).toBe('flex items-center justify-between flex-col');
    });
  });

  describe('conditional classes', () => {
    it('should handle conditional classes with clsx', () => {
      const isActive = true;
      expect(cn('base-class', isActive && 'active-class')).toBe('base-class active-class');
    });

    it('should exclude falsy conditional classes', () => {
      const isActive = false;
      expect(cn('base-class', isActive && 'active-class')).toBe('base-class');
    });

    it('should handle ternary operators', () => {
      const isActive = true;
      expect(cn('base-class', isActive ? 'active' : 'inactive')).toBe('base-class active');
    });

    it('should handle multiple conditions', () => {
      const isActive = true;
      const isDisabled = false;
      expect(
        cn('base-class', isActive && 'active', isDisabled && 'disabled')
      ).toBe('base-class active');
    });
  });

  describe('array inputs', () => {
    it('should handle array of strings', () => {
      expect(cn(['foo', 'bar'])).toBe('foo bar');
    });

    it('should handle nested arrays', () => {
      expect(cn(['foo', ['bar', 'baz']])).toBe('foo bar baz');
    });

    it('should flatten arrays', () => {
      expect(cn([['foo', 'bar'], 'baz'])).toBe('foo bar baz');
    });
  });

  describe('object inputs', () => {
    it('should handle object with boolean values', () => {
      expect(cn({ foo: true, bar: false, baz: true })).toBe('foo baz');
    });

    it('should handle mixed inputs', () => {
      expect(cn('foo', { bar: true, baz: false }, 'qux')).toBe('foo bar qux');
    });
  });

  describe('edge cases', () => {
    it('should handle very long class strings', () => {
      const longClass = 'a'.repeat(1000);
      expect(cn('foo', longClass)).toContain('foo');
    });

    it('should handle duplicate classes', () => {
      // cn() doesn't deduplicate non-conflicting classes
      expect(cn('foo', 'bar', 'foo')).toBe('foo bar foo');
    });

    it('should handle classes with numbers', () => {
      expect(cn('col-span-1', 'col-span-2')).toBe('col-span-2');
    });

    it('should handle responsive variants', () => {
      expect(cn('md:px-4', 'lg:px-8')).toBe('md:px-4 lg:px-8');
    });

    it('should handle pseudo-classes', () => {
      expect(cn('hover:bg-blue-500', 'focus:bg-red-500')).toBe('hover:bg-blue-500 focus:bg-red-500');
    });
  });

  describe('real-world use cases', () => {
    it('should handle button component classes', () => {
      const variant = 'primary';
      const size = 'lg';
      const className = 'custom-class';

      const result = cn(
        'base-button',
        variant === 'primary' && 'bg-blue-500 text-white',
        variant === 'secondary' && 'bg-gray-500 text-black',
        size === 'lg' && 'px-8 py-4',
        size === 'sm' && 'px-4 py-2',
        className
      );

      expect(result).toBe('base-button bg-blue-500 text-white px-8 py-4 custom-class');
    });

    it('should handle card component classes', () => {
      const isHighlighted = true;
      const isDisabled = false;

      const result = cn(
        'card',
        isHighlighted && 'border-2 border-yellow-500',
        isDisabled && 'opacity-50 cursor-not-allowed',
        'p-4 rounded-lg shadow-md'
      );

      expect(result).toBe('card border-2 border-yellow-500 p-4 rounded-lg shadow-md');
    });

    it('should handle layout classes', () => {
      const isVertical = true;
      const result = cn(
        'flex',
        isVertical ? 'flex-col' : 'flex-row',
        'items-center',
        'gap-4'
      );

      expect(result).toBe('flex flex-col items-center gap-4');
    });
  });
});

import { cn } from '../utils';

describe('Utils (cn function)', () => {
  describe('Basic Functionality', () => {
    it('merges class names correctly', () => {
      expect(cn('class1', 'class2')).toBe('class1 class2');
      expect(cn('class1 class2', 'class3')).toBe('class1 class2 class3');
    });

    it('handles empty inputs', () => {
      expect(cn()).toBe('');
      expect(cn('')).toBe('');
      expect(cn('', '')).toBe('');
    });

    it('handles single class name', () => {
      expect(cn('class1')).toBe('class1');
    });

    it('handles multiple class names', () => {
      expect(cn('class1', 'class2', 'class3')).toBe('class1 class2 class3');
      expect(cn('class1 class2', 'class3 class4')).toBe('class1 class2 class3 class4');
    });

    it('handles arrays of class names', () => {
      expect(cn(['class1', 'class2'])).toBe('class1 class2');
      expect(cn(['class1 class2'], 'class3')).toBe('class1 class2 class3');
      expect(cn('class1', ['class2', 'class3'])).toBe('class1 class2 class3');
    });

    it('handles objects with boolean values', () => {
      expect(cn({ class1: true, class2: true })).toBe('class1 class2');
      expect(cn({ class1: true, class2: false })).toBe('class1');
      expect(cn({ class1: false, class2: false })).toBe('');
    });

    it('handles mixed inputs', () => {
      expect(cn('class1', { class2: true }, ['class3'])).toBe('class1 class2 class3');
      expect(cn('class1 class2', { class3: false, class4: true }, 'class5')).toBe('class1 class2 class4 class5');
    });
  });

  describe('Tailwind CSS Specific Behavior', () => {
    it('removes conflicting Tailwind classes', () => {
      expect(cn('p-4', 'p-2')).toBe('p-2'); // Later class wins
      expect(cn('bg-red-500', 'bg-blue-500')).toBe('bg-blue-500');
      expect(cn('text-sm', 'text-lg')).toBe('text-lg');
    });

    it('handles complex Tailwind conflicts', () => {
      expect(cn('p-4 m-4', 'p-2 m-2')).toBe('m-2 p-2'); // Sorted alphabetically
      expect(cn('flex items-center', 'grid justify-start')).toBe('grid justify-start items-center');
    });

    it('preserves non-conflicting Tailwind classes', () => {
      expect(cn('p-4', 'm-4')).toBe('p-4 m-4');
      expect(cn('bg-red-500', 'text-white')).toBe('bg-red-500 text-white');
    });

    it('handles responsive variants', () => {
      expect(cn('p-4', 'md:p-2')).toBe('md:p-2 p-4'); // Different breakpoints
      expect(cn('sm:p-4', 'md:p-2')).toBe('sm:p-4 md:p-2');
    });

    it('handles state variants', () => {
      expect(cn('bg-white', 'hover:bg-gray-100')).toBe('bg-white hover:bg-gray-100');
      expect(cn('text-black', 'focus:text-blue-500')).toBe('text-black focus:text-blue-500');
    });

    it('handles arbitrary values', () => {
      expect(cn('p-[10px]', 'm-[20px]')).toBe('m-[20px] p-[10px]');
      expect(cn('bg-[#123456]', 'text-[#789abc]')).toBe('bg-[#123456] text-[#789abc]');
    });
  });

  describe('Conditional Classes', () => {
    it('handles truthy conditions', () => {
      expect(cn('class1', true && 'class2')).toBe('class1 class2');
      expect(cn('class1', 'class2' && 'class3')).toBe('class1 class3');
    });

    it('handles falsy conditions', () => {
      expect(cn('class1', false && 'class2')).toBe('class1');
      expect(cn('class1', null && 'class2')).toBe('class1');
      expect(cn('class1', undefined && 'class2')).toBe('class1');
      expect(cn('class1', 0 && 'class2')).toBe('class1');
    });

    it('handles ternary operators', () => {
      const condition = true;
      expect(cn(condition ? 'class1' : 'class2')).toBe('class1');
      expect(cn(!condition ? 'class1' : 'class2')).toBe('class2');
    });

    it('handles logical AND operators', () => {
      const isActive = true;
      const isVisible = false;
      expect(cn(isActive && 'active')).toBe('active');
      expect(cn(isVisible && 'visible')).toBe('');
    });

    it('handles template literals', () => {
      const prefix = 'bg';
      const color = 'red';
      expect(cn(`${prefix}-${color}-500`)).toBe('bg-red-500');
    });
  });

  describe('Edge Cases', () => {
    it('handles duplicate classes', () => {
      expect(cn('class1', 'class1')).toBe('class1'); // Deduplicated
      expect(cn('class1 class2', 'class1')).toBe('class1 class2');
    });

    it('handles whitespace variations', () => {
      expect(cn('  class1  class2  ')).toBe('class1 class2'); // Trimmed
      expect(cn('class1  ', '  class2')).toBe('class1 class2');
    });

    it('handles empty strings in arrays', () => {
      expect(cn(['', 'class1', '', 'class2', ''])).toBe('class1 class2');
    });

    it('handles numbers', () => {
      expect(cn(0)).toBe('');
      expect(cn(1)).toBe('1'); // Converted to string
    });

    it('handles special characters', () => {
      expect(cn('class-1', 'class_2', 'class.3')).toBe('class-1 class_2 class.3');
      expect(cn('class@1', 'class#2', 'class$3')).toBe('class@1 class#2 class$3');
    });

    it('handles very long class names', () => {
      const longClass = 'a'.repeat(1000);
      expect(cn(longClass)).toBe(longClass);
    });

    it('handles unicode characters', () => {
      expect(cn('class-😀', 'class-测试')).toBe('class-😀 class-测试');
    });
  });

  describe('Real-World Scenarios', () => {
    it('handles button variant classes', () => {
      const variant = 'primary';
      const size = 'lg';
      const classes = cn(
        'base-class',
        variant === 'primary' && 'bg-blue-500 text-white',
        variant === 'secondary' && 'bg-gray-500 text-black',
        size === 'lg' && 'px-6 py-3',
        size === 'sm' && 'px-3 py-1'
      );
      expect(classes).toBe('base-class bg-blue-500 text-white px-6 py-3');
    });

    it('handles conditional styling based on state', () => {
      const isActive = true;
      const isDisabled = false;
      const classes = cn(
        'base',
        isActive && 'active',
        isDisabled && 'disabled',
        'other-class'
      );
      expect(classes).toBe('active base other-class');
    });

    it('handles responsive design classes', () => {
      const classes = cn(
        'p-4',
        'sm:p-6',
        'md:p-8',
        'lg:p-10',
        'xl:p-12'
      );
      expect(classes).toBe('p-4 sm:p-6 md:p-8 lg:p-10 xl:p-12');
    });

    it('handles form validation states', () => {
      const hasError = true;
      const isSuccess = false;
      const classes = cn(
        'input-base',
        hasError && 'border-red-500 focus:border-red-500',
        isSuccess && 'border-green-500 focus:border-green-500'
      );
      expect(classes).toBe('border-red-500 focus:border-red-500 input-base');
    });

    it('handles component composition', () => {
      const baseClasses = 'flex items-center justify-center';
      const variantClasses = 'bg-white text-black';
      const sizeClasses = 'w-10 h-10';
      const classes = cn(baseClasses, variantClasses, sizeClasses);
      expect(classes).toBe('flex items-center justify-center bg-white text-black w-10 h-10');
    });
  });

  describe('Performance', () => {
    it('handles large inputs efficiently', () => {
      const start = Date.now();
      const classes = Array.from({ length: 1000 }, (_, i) => `class-${i}`);
      cn(...classes);
      const duration = Date.now() - start;
      expect(duration).toBeLessThan(100); // Should be fast
    });

    it('handles complex conditional logic', () => {
      const start = Date.now();
      const conditions = Array.from({ length: 100 }, (_, i) => ({
        class: `class-${i}`,
        active: i % 2 === 0,
      }));
      const classes = cn(...conditions.map(c => c.active && c.class));
      const duration = Date.now() - start;
      expect(duration).toBeLessThan(50);
    });
  });

  describe('Integration with clsx', () => {
    it('works like clsx for basic merging', () => {
      expect(cn('class1', 'class2')).toBe('class1 class2');
    });

    it('works like clsx for conditional classes', () => {
      expect(cn({ class1: true, class2: false })).toBe('class1');
      expect(cn(['class1', false, 'class2'])).toBe('class1 class2');
    });

    it('adds tailwind-merge behavior on top of clsx', () => {
      // clsx would keep both, but cn removes conflicts
      expect(cn('p-4', 'p-2')).toBe('p-2'); // Conflict resolved
    });
  });

  describe('Common Patterns', () => {
    it('handles dynamic component props', () => {
      const props = {
        className: 'prop-class',
        variant: 'danger',
      };
      const classes = cn(
        'base-class',
        props.className,
        props.variant === 'danger' && 'text-red-500'
      );
      expect(classes).toBe('base-class prop-class text-red-500');
    });

    it('handles extending base classes', () => {
      const base = 'flex flex-col gap-4';
      const extension = 'items-center justify-center';
      const classes = cn(base, extension);
      expect(classes).toBe('flex flex-col gap-4 items-center justify-center');
    });

    it('handles overriding specific classes', () => {
      const base = 'p-4 m-4 bg-white';
      const override = 'p-2 m-2 bg-black';
      const classes = cn(base, override);
      expect(classes).toBe('m-2 p-2 bg-black'); // All overridden
    });

    it('handles optional classes', () => {
      const options = {
        padding: true,
        margin: false,
        color: 'red',
      };
      const classes = cn(
        options.padding && 'p-4',
        options.margin && 'm-4',
        options.color && `text-${options.color}-500`
      );
      expect(classes).toBe('p-4 text-red-500');
    });
  });

  describe('TypeScript Type Safety', () => {
    it('accepts ClassValue type inputs', () => {
      // These should all compile without errors
      const stringInput: ClassValue = 'class';
      const arrayInput: ClassValue = ['class1', 'class2'];
      const objectInput: ClassValue = { class1: true, class2: false };
      const booleanInput: ClassValue = true && 'class';
      const numberInput: ClassValue = 123;

      expect(cn(stringInput, arrayInput, objectInput, booleanInput, numberInput)).toBeDefined();
    });
  });
});

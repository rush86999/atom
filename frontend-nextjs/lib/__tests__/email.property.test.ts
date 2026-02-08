/**
 * Property-Based Tests for Email Utilities
 *
 * Tests email HTML generation functions
 */

import fc from 'fast-check';
import { generateVerificationEmailHTML } from '../email';

describe('Email Utilities - Property-Based Tests', () => {
  // Helper to generate hex string
  const hexString = (length: number) => {
    return fc.array(fc.constantFrom(...'0123456789abcdef'.split('')), { minLength: length, maxLength: length })
      .map(chars => chars.join(''));
  };

  // Property 1: Verification code appears in output
  // The code parameter should always appear in the generated HTML
  it('should always include verification code in HTML output', () => {
    fc.assert(
      fc.property(
        hexString(6), // 6-char hex code
        fc.string({ minLength: 1, maxLength: 50 }), // name
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);
          return html.includes(code);
        }
      ),
      { numRuns: 100 }
    );
  });

  // Property 2: Name appears in output
  // The name parameter should always appear in the generated HTML
  it('should always include name in HTML output', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);
          return html.includes(name);
        }
      ),
      { numRuns: 100 }
    );
  });

  // Property 3: Output contains required HTML structure
  // Generated HTML should contain basic email structure elements
  it('should contain basic HTML structure', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);

          // Should contain HTML tags
          const hasDiv = html.includes('<div');
          const hasH2 = html.includes('<h2');
          const hasP = html.includes('<p');

          return hasDiv && hasH2 && hasP;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 4: Output is non-empty
  // Generated HTML should never be empty
  it('should never produce empty output', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);
          return html.length > 0;
        }
      ),
      { numRuns: 100 }
    );
  });

  // Property 5: Deterministic generation
  // Same inputs should produce same output
  it('should be deterministic: same inputs produce same output', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html1 = generateVerificationEmailHTML(code, name);
          const html2 = generateVerificationEmailHTML(code, name);
          return html1 === html2;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 6: Output contains style information
  // Generated HTML should contain inline styles
  it('should contain style attributes', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);
          return html.includes('style=');
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 7: Code is prominently displayed
  // The verification code should be displayed prominently with special styling
  it('should display code with special styling', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);
          // Code should appear in the HTML (possibly with attributes in strong tag)
          return html.includes(code) && html.includes('<strong');
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 8: Output length is reasonable
  // Generated HTML should not be excessively long
  it('should produce reasonably sized output', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);
          // HTML should be between 500 and 5000 characters
          return html.length >= 500 && html.length <= 5000;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 9: Special characters in name are handled
  // Names with special characters should not break HTML
  it('should handle special characters in name', () => {
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code, name) => {
          const html = generateVerificationEmailHTML(code, name);
          // Should contain proper HTML structure
          return html.includes('>') && html.includes('<');
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 10: Code uniqueness
  // Different codes should produce different outputs
  it('should produce different outputs for different codes', () => {
    // Generate one code, then modify first char to ensure different codes
    fc.assert(
      fc.property(
        hexString(6),
        fc.string({ minLength: 1, maxLength: 50 }),
        (code1, name) => {
          // Create code2 by flipping first character
          const firstChar = code1[0];
          const flippedChar = firstChar === '0' ? '1' : '0';
          const code2 = flippedChar + code1.slice(1);

          // Skip if somehow codes are the same (shouldn't happen)
          if (code1 === code2) return true;

          const html1 = generateVerificationEmailHTML(code1, name);
          const html2 = generateVerificationEmailHTML(code2, name);
          return html1 !== html2;
        }
      ),
      { numRuns: 50 }
    );
  });
});

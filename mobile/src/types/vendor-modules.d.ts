/**
 * Minimal type surface for runtime-only vendor modules that do not ship
 * TypeScript declarations.
 */

declare module 'react-native-syntax-highlighter' {
  import type { ComponentType, ReactNode } from 'react';
  import type { StyleProp, TextStyle } from 'react-native';

  export interface SyntaxHighlighterProps {
    language?: string;
    style?: Record<string, unknown>;
    customStyle?: StyleProp<TextStyle>;
    fontSize?: number;
    fontFamily?: string;
    highlighter?: string;
    children?: ReactNode;
  }

  export const Prism: ComponentType<SyntaxHighlighterProps>;
  export const SyntaxHighlighter: ComponentType<SyntaxHighlighterProps>;
}

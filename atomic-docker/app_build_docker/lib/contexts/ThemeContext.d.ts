import React, { ReactNode } from 'react';
type Theme = 'light' | 'dark';
interface ThemeContextProps {
    theme: Theme;
    toggleTheme: () => void;
}
export declare const ThemeProvider: React.FC<{
    children: ReactNode;
}>;
export declare const useTheme: () => ThemeContextProps;
export {};

atom/src/ui-shared/design-system.ts
// Black Metallic Design System
// Dual theme (dark/light) for Atom application
// Shared between NextJS frontend and Desktop app

export interface ThemeColors {
  // Core colors
  primary: string;
  secondary: string;
  accent: string;

  // Background colors
  background: string;
  surface: string;
  card: string;

  // Text colors
  text: string;
  textSecondary: string;
  textMuted: string;

  // Border and divider colors
  border: string;
  divider: string;

  // Status colors
  success: string;
  warning: string;
  error: string;
  info: string;

  // Interactive states
  hover: string;
  active: string;
  disabled: string;

  // Metallic accents
  metallicPrimary: string;
  metallicSecondary: string;
  metallicAccent: string;
}

export interface DesignSystem {
  colors: {
    dark: ThemeColors;
    light: ThemeColors;
  };
  typography: {
    fontFamily: string;
    fontWeights: {
      light: number;
      regular: number;
      medium: number;
      semibold: number;
      bold: number;
    };
    fontSizes: {
      xs: string;
      sm: string;
      base: string;
      lg: string;
      xl: string;
      '2xl': string;
      '3xl': string;
      '4xl': string;
    };
    lineHeights: {
      tight: string;
      normal: string;
      relaxed: string;
    };
  };
  spacing: {
    px: string;
    0: string;
    0.5: string;
    1: string;
    1.5: string;
    2: string;
    2.5: string;
    3: string;
    3.5: string;
    4: string;
    5: string;
    6: string;
    8: string;
    10: string;
    12: string;
    16: string;
    20: string;
    24: string;
    32: string;
    40: string;
    48: string;
    56: string;
    64: string;
  };
  borderRadius: {
    none: string;
    sm: string;
    base: string;
    md: string;
    lg: string;
    xl: string;
    '2xl': string;
    full: string;
  };
  shadows: {
    sm: string;
    base: string;
    md: string;
    lg: string;
    xl: string;
    '2xl': string;
    inner: string;
    none: string;
  };
  breakpoints: {
    sm: string;
    md: string;
    lg: string;
    xl: string;
    '2xl': string;
  };
  zIndex: {
    hide: number;
    auto: number;
    base: number;
    docked: number;
    dropdown: number;
    sticky: number;
    banner: number;
    overlay: number;
    modal: number;
    popover: number;
    skipLink: number;
    toast: number;
    tooltip: number;
  };
}

// Black Metallic Color Palette
const BLACK_METALLIC_COLORS = {
  // Core metallic colors
  metallicBlack: '#0a0a0f',
  gunmetal: '#1a1a2e',
  charcoal: '#2d2d3a',
  darkSteel: '#3a3a4a',
  steel: '#4a4a5a',
  lightSteel: '#5a5a6a',
  silver: '#8a8a9a',
  chrome: '#c0c0d0',
  platinum: '#e0e0f0',
  whiteGold: '#f8f8ff',

  // Accent colors
  electricBlue: '#0066ff',
  neonBlue: '#00aaff',
  cyberBlue: '#0088ff',
  deepBlue: '#0044aa',

  // Metallic gradients
  chromeGradient: 'linear-gradient(135deg, #c0c0d0 0%, #e0e0f0 50%, #c0c0d0 100%)',
  steelGradient: 'linear-gradient(135deg, #4a4a5a 0%, #5a5a6a 50%, #4a4a5a 100%)',
  gunmetalGradient: 'linear-gradient(135deg, #1a1a2e 0%, #2d2d3a 50%, #1a1a2e 100%)',

  // Status colors
  success: '#00cc88',
  warning: '#ffaa00',
  error: '#ff4466',
  info: '#0088ff',
};

export const designSystem: DesignSystem = {
  colors: {
    dark: {
      // Core colors
      primary: BLACK_METALLIC_COLORS.electricBlue,
      secondary: BLACK_METALLIC_COLORS.gunmetal,
      accent: BLACK_METALLIC_COLORS.neonBlue,

      // Background colors
      background: BLACK_METALLIC_COLORS.metallicBlack,
      surface: BLACK_METALLIC_COLORS.gunmetal,
      card: BLACK_METALLIC_COLORS.charcoal,

      // Text colors
      text: BLACK_METALLIC_COLORS.whiteGold,
      textSecondary: BLACK_METALLIC_COLORS.chrome,
      textMuted: BLACK_METALLIC_COLORS.silver,

      // Border and divider colors
      border: BLACK_METALLIC_COLORS.darkSteel,
      divider: BLACK_METALLIC_COLORS.steel,

      // Status colors
      success: BLACK_METALLIC_COLORS.success,
      warning: BLACK_METALLIC_COLORS.warning,
      error: BLACK_METALLIC_COLORS.error,
      info: BLACK_METALLIC_COLORS.info,

      // Interactive states
      hover: BLACK_METALLIC_COLORS.cyberBlue + '20',
      active: BLACK_METALLIC_COLORS.cyberBlue + '40',
      disabled: BLACK_METALLIC_COLORS.steel + '60',

      // Metallic accents
      metallicPrimary: BLACK_METALLIC_COLORS.chromeGradient,
      metallicSecondary: BLACK_METALLIC_COLORS.steelGradient,
      metallicAccent: BLACK_METALLIC_COLORS.gunmetalGradient,
    },
    light: {
      // Core colors
      primary: BLACK_METALLIC_COLORS.deepBlue,
      secondary: BLACK_METALLIC_COLORS.platinum,
      accent: BLACK_METALLIC_COLORS.cyberBlue,

      // Background colors
      background: BLACK_METALLIC_COLORS.whiteGold,
      surface: BLACK_METALLIC_COLORS.platinum,
      card: BLACK_METALLIC_COLORS.chrome,

      // Text colors
      text: BLACK_METALLIC_COLORS.metallicBlack,
      textSecondary: BLACK_METALLIC_COLORS.charcoal,
      textMuted: BLACK_METALLIC_COLORS.steel,

      // Border and divider colors
      border: BLACK_METALLIC_COLORS.silver,
      divider: BLACK_METALLIC_COLORS.lightSteel,

      // Status colors
      success: BLACK_METALLIC_COLORS.success,
      warning: BLACK_METALLIC_COLORS.warning,
      error: BLACK_METALLIC_COLORS.error,
      info: BLACK_METALLIC_COLORS.info,

      // Interactive states
      hover: BLACK_METALLIC_COLORS.cyberBlue + '15',
      active: BLACK_METALLIC_COLORS.cyberBlue + '25',
      disabled: BLACK_METALLIC_COLORS.silver + '40',

      // Metallic accents
      metallicPrimary: BLACK_METALLIC_COLORS.chromeGradient,
      metallicSecondary: `linear-gradient(135deg, ${BLACK_METALLIC_COLORS.silver} 0%, ${BLACK_METALLIC_COLORS.chrome} 50%, ${BLACK_METALLIC_COLORS.silver} 100%)`,
      metallicAccent: `linear-gradient(135deg, ${BLACK_METALLIC_COLORS.platinum} 0%, ${BLACK_METALLIC_COLORS.whiteGold} 50%, ${BLACK_METALLIC_COLORS.platinum} 100%)`,
    },
  },
  typography: {
    fontFamily: '"Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontWeights: {
      light: 300,
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    fontSizes: {
      xs: '0.75rem',
      sm: '0.875rem',
      base: '1rem',
      lg: '1.125rem',
      xl: '1.25rem',
      '2xl': '1.5rem',
      '3xl': '1.875rem',
      '4xl': '2.25rem',
    },
    lineHeights: {
      tight: '1.25',
      normal: '1.5',
      relaxed: '1.75',
    },
  },
  spacing: {
    px: '1px',
    0: '0px',
    0.5: '0.125rem',
    1: '0.25rem',
    1.5: '0.375rem',
    2: '0.5rem',
    2.5: '0.625rem',
    3: '0.75rem',
    3.5: '0.875rem',
    4: '1rem',
    5: '1.25rem',
    6: '1.5rem',
    8: '2rem',
    10: '2.5rem',
    12: '3rem',
    16: '4rem',
    20: '5rem',
    24: '6rem',
    32: '8rem',
    40: '10rem',
    48: '12rem',
    56: '14rem',
    64: '16rem',
  },
  borderRadius: {
    none: '0px',
    sm: '0.125rem',
    base: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
    xl: '0.75rem',
    '2xl': '1rem',
    full: '9999px',
  },
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
    none: 'none',
  },
  breakpoints: {
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
  },
  zIndex: {
    hide: -1,
    auto: 'auto',
    base: 0,
    docked: 10,
    dropdown: 1000,
    sticky: 1100,
    banner: 1200,
    overlay: 1300,
    modal: 1400,
    popover: 1500,
    skipLink: 1600,
    toast: 1700,
    tooltip: 1800,
  },
};

// Utility functions for theme usage
export const getThemeColors = (theme: 'dark' | 'light' = 'dark'): ThemeColors => {
  return designSystem.colors[theme];
};

export const createThemeVars = (theme: 'dark' | 'light' = 'dark'): Record<string, string> => {
  const colors = getThemeColors(theme);
  return Object.entries(colors).reduce((acc, [key, value]) => {
    acc[`--color-${key}`] = value;
    return acc;
  }, {} as Record<string, string>);
};

// CSS utility classes generator
export const generateThemeClasses = (theme: 'dark' | 'light' = 'dark') => {
  const colors = getThemeColors(theme);
  const classes: Record<string, string> = {};

  // Generate color utility classes
  Object.entries(colors).forEach(([key, value]) => {
    classes[`.text-${key}`] = `color: ${value};`;
    classes[`.bg-${key}`] = `background-color: ${value};`;
    classes[`.border-${key}`] = `border-color: ${value};`;
  });

  return classes;
};

// React hook for theme management (for UI components)
export interface ThemeContextType {
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  setTheme: (theme: 'dark' | 'light') => void;
}

// Default export
export default designSystem;

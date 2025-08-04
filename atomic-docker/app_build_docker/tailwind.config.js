const theme = require('./config/theme.json');

let font_base = Number(theme.fonts.font_size.base.replace('px', ''));
let font_scale = Number(theme.fonts.font_size.scale);
let h6 = font_base / font_base;
let h5 = h6 * font_scale;
let h4 = h5 * font_scale;
let h3 = h4 * font_scale;
let h2 = h3 * font_scale;
let h1 = h2 * font_scale;
let fontPrimary, fontPrimaryType, fontSecondary, fontSecondaryType;
if (theme.fonts.font_family.primary) {
  fontPrimary = theme.fonts.font_family.primary
    .replace(/\+/g, ' ')
    .replace(/:[ital,]*[ital@]*[wght@]*[0-9,;]+/gi, '');
  fontPrimaryType = theme.fonts.font_family.primary_type;
}
if (theme.fonts.font_family.secondary) {
  fontSecondary = theme.fonts.font_family.secondary
    .replace(/\+/g, ' ')
    .replace(/:[ital,]*[ital@]*[wght@]*[0-9,;]+/gi, '');
  fontSecondaryType = theme.fonts.font_family.secondary_type;
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx}',
    './layouts/**/*.{js,ts,jsx,tsx}',
    './content/**/*.{md,mdx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    screens: {
      sm: '540px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1536px',
    },
    container: {
      center: true,
      padding: '2rem',
    },
    extend: {
      colors: {
        text: theme.colors.default.text_color.default,
        light: theme.colors.default.text_color.light,
        dark: theme.colors.default.text_color.dark,
        primary: theme.colors.default.theme_color.primary,
        secondary: theme.colors.default.theme_color.secondary,
        body: theme.colors.default.theme_color.body,
        border: theme.colors.default.theme_color.border,
        'theme-light': theme.colors.default.theme_color.theme_light,
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
      },
      fontSize: {
        base: font_base + 'px',
        h1: h1 + 'rem',
        'h1-sm': h1 * 0.8 + 'rem',
        h2: h2 + 'rem',
        'h2-sm': h2 * 0.8 + 'rem',
        h3: h3 + 'rem',
        'h3-sm': h3 * 0.8 + 'rem',
        h4: h4 + 'rem',
        h5: h5 + 'rem',
        h6: h6 + 'rem',
      },
      fontFamily: {
        primary: [fontPrimary, fontPrimaryType],
        secondary: [fontSecondary, fontSecondaryType],
      },
      borderRadius: {
        lg: `var(--radius)`,
        md: `calc(var(--radius) - 2px)`,
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'slide-from-left': {
          '0%': {
            transform: 'translateX(-100%)',
          },
          '100%': {
            transform: 'translateX(0)',
          },
        },
        'slide-to-left': {
          '0%': {
            transform: 'translateX(0)',
          },
          '100%': {
            transform: 'translateX(-100%)',
          },
        },
      },
      animation: {
        'slide-from-left':
          'slide-from-left 0.3s cubic-bezier(0.82, 0.085, 0.395, 0.895)',
        'slide-to-left':
          'slide-to-left 0.25s cubic-bezier(0.82, 0.085, 0.395, 0.895)',
      },
    },
  },
  daisyui: {
    themes: [
      {
        light: {
          ...require('daisyui/src/colors/themes')['[data-theme=light]'],
          primary: theme.colors.default.theme_color.primary,
          secondary: theme.colors.default.theme_color.secondary,
          'primary-focus': theme.colors.default.theme_color.primary_focus,
          'secondary-focus': theme.colors.default.theme_color.secondary_focus,
        },
        dark: {
          ...require('daisyui/src/colors/themes')['[data-theme=dark]'],
          primary: theme.colors.default.theme_color.secondary,
          secondary: theme.colors.default.theme_color.primary,
          'primary-focus': theme.colors.default.theme_color.secondary_focus,
          'secondary-focus': theme.colors.default.theme_color.primary_focus,
        },
      },
    ],
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('tailwind-bootstrap-grid')({ generateContainer: false }),
    require('daisyui'),
    require('flowbite/plugin'),
    require('tailwindcss-animate'),
  ],
  // important: true,
};

import esbuild from 'esbuild';

const config = {
  entryPoints: ['src/main.tsx'],
  bundle: true,
  outfile: 'dist/main.js',
  platform: 'browser',
  format: 'esm',
  external: [
    '@chakra-ui/react',
    '@chakra-ui/icons',
    '@emotion/react',
    '@emotion/styled',
    'framer-motion',
    'react',
    'react-dom'
  ],
  loader: {
    '.ts': 'ts',
    '.tsx': 'tsx',
    '.js': 'js',
    '.jsx': 'jsx'
  },
  resolveExtensions: ['.tsx', '.ts', '.jsx', '.js'],
  jsx: 'automatic',
  sourcemap: true,
  minify: false,
  target: 'es2020'
};

export default config;

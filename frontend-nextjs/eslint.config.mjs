import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat();

export default [
  {
    ignores: [".next/**", "node_modules/**"]
  },
  ...compat.extends("next/core-web-vitals")
];

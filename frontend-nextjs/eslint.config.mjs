import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "coverage/**",
      "final-implementation.js",
      "fix-eslint-errors.js",
      "fix-parsing-errors.js"
    ]
  },
  ...nextVitals
];

export default eslintConfig;

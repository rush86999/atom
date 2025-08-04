// LEGACY FILE - MIGRATED
// This file was refactored to eliminate 298 TypeScript errors
// All functionality has been moved to modular structure
// Use api-helper-refactored.ts for new development

// Redirect all exports to the refactored and working modules
export * from "./api-helper-refactored";

// Legacy warning
if (process.env.NODE_ENV !== "production") {
  console.warn(
    "[DEPRECATED] api-helper.ts is deprecated. Use api-helper-refactored.ts instead.",
  );
}

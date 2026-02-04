/**
 * ATOM Search Index and Exports
 */

export { default as AtomSearch } from './AtomSearch';
export { default as AtomVectorSearch } from './AtomVectorSearch';
export { default as AtomUnifiedSearch } from './AtomUnifiedSearch';
export { default as AtomSearchWrapper } from './AtomSearchWrapper';
export { useVectorSearch } from './useVectorSearch';
export { atomSearchAPI, AtomSearchAPI } from './AtomSearchAPI';

// Re-export components for easy access
export * from './searchTypes';
export * from './searchUtils';
export { detectPlatform, getPlatformConfig, getDefaultAppConfig } from './AtomSearchWrapper';
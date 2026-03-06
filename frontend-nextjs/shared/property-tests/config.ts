/**
 * FastCheck Configuration for Property Tests
 *
 * Shared configuration for property-based testing across all platforms.
 * Supports reproducible runs via seed configuration and environment variables.
 *
 * @module property-tests/config
 */

import { PropertyTestConfig } from './types';

/**
 * Default property test configuration.
 *
 * These settings balance thoroughness with execution time:
 * - numRuns: 100 test cases per property (catches most bugs)
 * - timeout: 10 seconds per test case (prevents hangs)
 * - seed: undefined (random by default, use environment for reproducibility)
 *
 * @example
 * ```ts
 * fc.assert(canvasStateMachineProperty, PROPERTY_TEST_CONFIG);
 * ```
 */
export const PROPERTY_TEST_CONFIG: PropertyTestConfig = {
  numRuns: 100,
  timeout: 10000,
  seed: undefined,
};

/**
 * Environment variable names for configuration.
 *
 * These environment variables allow overriding defaults without code changes:
 * - FASTCHECK_SEED: Random seed for reproducible runs
 * - FASTCHECK_NUM_RUNS: Number of test cases to generate
 * - FASTCHECK_TIMEOUT: Timeout per test case in milliseconds
 *
 * @example
 * ```bash
 * # Reproducible run
 * FASTCHECK_SEED=12345 npm test
 *
 * # Quick local testing (fewer runs)
 * FASTCHECK_NUM_RUNS=10 npm test
 *
 * # CI/CD with longer timeout
 * FASTCHECK_TIMEOUT=30000 npm test
 * ```
 */
export const ENV_VARS = {
  SEED: 'FASTCHECK_SEED',
  NUM_RUNS: 'FASTCHECK_NUM_RUNS',
  TIMEOUT: 'FASTCHECK_TIMEOUT',
} as const;

/**
 * Parse environment variable with type conversion.
 *
 * @param name - Environment variable name
 * @param defaultValue - Default value if not set or invalid
 * @returns Parsed value or default
 *
 * @example
 * ```ts
 * const runs = parseEnvVar(ENV_VARS.NUM_RUNS, 100); // 100 or env value
 * ```
 */
function parseEnvVar<T extends string | number>(
  name: string,
  defaultValue: T
): T {
  const value = process.env[name];

  if (value === undefined || value === '') {
    return defaultValue;
  }

  // Number parsing
  if (typeof defaultValue === 'number') {
    const parsed = parseInt(value, 10);
    return isNaN(parsed) ? defaultValue : (parsed as T);
  }

  // String parsing
  return value as T;
}

/**
 * Get property test configuration with environment overrides.
 *
 * Merges default configuration with environment variables, allowing
 * reproducible runs and local debugging without code changes.
 *
 * Priority: Environment variables > defaults
 *
 * @example
 * ```ts
 * // Local development with fewer runs
 * FASTCHECK_NUM_RUNS=10 npm test
 *
 * // Reproducible CI/CD run
 * FASTCHECK_SEED=12345 FASTCHECK_NUM_RUNS=1000 npm test
 *
 * // Debug slow test with longer timeout
 * FASTCHECK_TIMEOUT=60000 npm test
 * ```
 *
 * @returns Merged configuration
 */
export function getTestConfig(): PropertyTestConfig {
  return {
    numRuns: parseEnvVar(ENV_VARS.NUM_RUNS, PROPERTY_TEST_CONFIG.numRuns),
    timeout: parseEnvVar(ENV_VARS.TIMEOUT, PROPERTY_TEST_CONFIG.timeout),
    seed: parseEnvVar<number>(ENV_VARS.SEED, PROPERTY_TEST_CONFIG.seed ?? Date.now()),
  };
}

/**
 * Get FastCheck-compatible parameters from configuration.
 *
 * Converts PropertyTestConfig to FastCheck parameter object.
 *
 * @example
 * ```ts
 * const config = getTestConfig();
 * const params = toFastCheckParams(config);
 * fc.assert(property, params);
 * ```
 *
 * @param config - Property test configuration
 * @returns FastCheck parameters
 */
export function toFastCheckParams(config: PropertyTestConfig) {
  return {
    numRuns: config.numRuns,
    timeout: config.timeout,
    seed: config.seed,
  };
}

/**
 * Validate configuration values.
 *
 * Ensures configuration is within acceptable ranges.
 *
 * @example
 * ```ts
 * const config = { numRuns: 0, timeout: 10000, seed: 123 };
 * const valid = validateConfig(config); // false (numRuns must be >= 1)
 * ```
 *
 * @param config - Configuration to validate
 * @returns true if valid, false otherwise
 */
export function validateConfig(config: PropertyTestConfig): boolean {
  const { numRuns, timeout, seed } = config;

  // numRuns must be positive
  if (numRuns < 1) {
    return false;
  }

  // timeout must be positive (milliseconds)
  if (timeout < 1) {
    return false;
  }

  // seed must be positive integer or undefined
  if (seed !== undefined && (seed < 0 || !Number.isInteger(seed))) {
    return false;
  }

  return true;
}

/**
 * Preset configurations for different scenarios.
 *
 * Common configurations for development, CI/CD, and debugging.
 *
 * @example
 * ```ts
 * // Quick local testing
 * fc.assert(property, toFastCheckParams(PRESETS.quick));
 *
 * // Standard CI/CD
 * fc.assert(property, toFastCheckParams(PRESETS.standard));
 *
 * // Deep testing (nightly builds)
 * fc.assert(property, toFastCheckParams(PRESETS.thorough));
 * ```
 */
export const PRESETS = {
  /** Quick testing: 10 runs, 5s timeout (local development) */
  quick: {
    numRuns: 10,
    timeout: 5000,
    seed: undefined,
  } satisfies PropertyTestConfig,

  /** Standard testing: 100 runs, 10s timeout (CI/CD default) */
  standard: PROPERTY_TEST_CONFIG,

  /** Thorough testing: 1000 runs, 30s timeout (nightly builds) */
  thorough: {
    numRuns: 1000,
    timeout: 30000,
    seed: undefined,
  } satisfies PropertyTestConfig,

  /** Reproducible: Fixed seed for debugging */
  reproducible: {
    ...PROPERTY_TEST_CONFIG,
    seed: 12345,
  } satisfies PropertyTestConfig,
} as const;

/**
 * Ambient declarations for globals attached by test suites.
 *
 * `global.mockFetch` is a shared alias installed by several suites so tests
 * can swap/inspect the fetch implementation without re-importing it
 * (round 80 tsc-noise cleanup: this single declaration removed 365 TS7017
 * implicit-any errors).
 */
declare global {
  // eslint-disable-next-line no-var
  var mockFetch: any;
}

export {};

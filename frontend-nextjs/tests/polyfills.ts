/**
 * Polyfills for Node.js test environment
 *
 * This file runs before any tests to set up necessary browser APIs
 * that aren't available in Node.js but are required by MSW and other libraries.
 *
 * Phase 299-07: Added fetch polyfill for MSW interceptor compatibility
 */

// Polyfill fetch-related globals for MSW
import nodeFetch, { Request as NodeRequest, Response as NodeResponse, Headers as NodeHeaders } from 'node-fetch';

// Polyfill fetch function (required for MSW 1.x interception)
global.fetch = nodeFetch as any;
global.Response = NodeResponse as any;
global.Request = NodeRequest as any;
global.Headers = NodeHeaders as any;

// Add TextEncoder/TextDecoder if not available
if (typeof TextEncoder === 'undefined') {
  const { TextEncoder } = require('util');
  (global as any).TextEncoder = TextEncoder;
}
if (typeof TextDecoder === 'undefined') {
  const { TextDecoder } = require('util');
  (global as any).TextDecoder = TextDecoder;
}

// Add AbortController if not available (Node.js 15+ has it natively)
if (typeof AbortController === 'undefined') {
  const { AbortController } = require('abort-controller');
  (global as any).AbortController = AbortController;
}


/**
 * Polyfills for Node.js test environment
 *
 * This file runs before any tests to set up necessary browser APIs
 * that aren't available in Node.js but are required by MSW and other libraries.
 */

// Polyfill fetch-related globals for MSW
import { Request as NodeRequest, Response as NodeResponse, Headers as NodeHeaders } from 'node-fetch';

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

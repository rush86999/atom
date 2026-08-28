/**
 * Logger Utilities Tests
 *
 * Tests verify Pino logger configuration, flexible log methods,
 * and child logger creation.
 *
 * Source: lib/logger.ts (68 lines)
 */

import { logger, appServiceLogger } from '../logger';

// Mock @opentelemetry/api so we can simulate an active trace span (the
// log formatter must stamp traceId/spanId/traceFlags onto the log object).
jest.mock('@opentelemetry/api', () => ({
  trace: {
    getSpan: jest.fn(),
  },
  context: {
    active: jest.fn(),
  },
}));

import { trace } from '@opentelemetry/api';

// Mock pino so it never instantiates the "pino-pretty" dev transport (not an
// installed dependency). The logger unit tests only verify the wrapper API,
// so a stubbed pino instance is sufficient. jest.mock is hoisted to the top
// of the module by ts-jest regardless of position.
//
// resetMocks: true (jest.config.js) wipes jest.fn() implementations before
// each test, so the child() implementation is re-established in beforeEach
// via jest.requireMock. We cannot use a module-scope mock* variable here:
// the import of '../logger' (which requires pino) is hoisted above the const,
// so the factory would read it before initialization (TDZ). We use `var`
// instead: it is hoisted AND initialized (to undefined), so the factory can
// capture the pino constructor config without hitting the TDZ.
// Note: child() is a plain function (not jest.fn) so it is NOT wiped by
// resetMocks between tests — the appServiceLogger.child wrapper always gets a
// real child object back.
var mockPinoConfig: any;

jest.mock('pino', () => {
  const createHandler = () => ({
    level: 'info',
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn(),
    fatal: jest.fn(),
    trace: jest.fn(),
  });
  return {
    __esModule: true,
    default: jest.fn((config: any) => {
      mockPinoConfig = config;
      return {
        level: 'info',
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
        debug: jest.fn(),
        fatal: jest.fn(),
        trace: jest.fn(),
        child: createHandler,
      };
    }),
  };
});

describe('logger.ts - Logger Configuration', () => {

  // Test 1: logger is exported
  test('logger should be exported', () => {
    expect(logger).toBeDefined();
    expect(appServiceLogger).toBeDefined();
  });

  // Test 2: logger has all required log methods
  test('logger should have info, warn, error, debug, fatal, and trace methods', () => {
    expect(typeof logger.info).toBe('function');
    expect(typeof logger.warn).toBe('function');
    expect(typeof logger.error).toBe('function');
    expect(typeof logger.debug).toBe('function');
    expect(typeof logger.fatal).toBe('function');
    expect(typeof logger.trace).toBe('function');
  });

  // Test 3: logger has child method and level property
  test('logger should have child method and level property', () => {
    expect(typeof logger.child).toBe('function');
    expect(logger.level).toBeDefined();
  });

  // Test 4: logger.info accepts string message
  test('logger.info should accept string message', () => {
    expect(() => logger.info('Test info message')).not.toThrow();
  });

  // Test 5: logger.info accepts object with message
  test('logger.info should accept object with message', () => {
    const testObj = { userId: '123', action: 'login' };
    expect(() => logger.info('User action', testObj)).not.toThrow();
  });

  // Test 6: logger.info accepts object as first parameter
  test('logger.info should accept object as first parameter', () => {
    const testObj = { event: 'test', data: 'value' };
    expect(() => logger.info(testObj)).not.toThrow();
  });

  // Test 7: logger.warn accepts string message
  test('logger.warn should accept string message', () => {
    expect(() => logger.warn('Test warning message')).not.toThrow();
  });

  // Test 8: logger.error accepts error object
  test('logger.error should accept error object', () => {
    const error = new Error('Test error');
    expect(() => logger.error('Error occurred', error)).not.toThrow();
  });

  // Test 9: logger.debug accepts message
  test('logger.debug should accept message', () => {
    expect(() => logger.debug('Debug message')).not.toThrow();
  });

  // Test 10: logger.fatal accepts message
  test('logger.fatal should accept message', () => {
    expect(() => logger.fatal('Fatal error')).not.toThrow();
  });

  // Test 11: logger.trace accepts message
  test('logger.trace should accept message', () => {
    expect(() => logger.trace('Trace message')).not.toThrow();
  });

  // Test 12: logger.child creates child logger
  test('logger.child should create child logger with bindings', () => {
    const bindings = { component: 'test-component', userId: '123' };
    const childLogger = logger.child(bindings);

    expect(childLogger).toBeDefined();
  });

  // Test 13: logger has default level
  test('logger should have default log level', () => {
    expect(logger.level).toBeDefined();
    expect(['info', 'debug', 'warn', 'error', 'fatal', 'trace']).toContain(logger.level);
  });

  // Test 14: logger.info with complex object
  test('logger.info should handle complex objects', () => {
    const complexObj = {
      user: { id: '123', name: 'Test User' },
      metadata: { timestamp: Date.now(), correlationId: 'abc-123' },
      events: ['login', 'view', 'logout'],
    };
    expect(() => logger.info('Complex event', complexObj)).not.toThrow();
  });

  // Test 15: logger.error with error and context
  test('logger.error should handle error with context', () => {
    const error = new Error('Database connection failed');
    const context = { host: 'localhost', port: 5432, database: 'test_db' };
    expect(() => (logger.error as any)('DB Error', error, context)).not.toThrow();
  });

  // Test 16: multiple log calls in sequence
  test('logger should handle multiple sequential log calls', () => {
    expect(() => {
      logger.info('Step 1');
      logger.debug('Step 2');
      logger.warn('Step 3');
      logger.error('Step 4');
    }).not.toThrow();
  });

  // Test 17: logger with null/undefined values
  test('logger should handle null and undefined values gracefully', () => {
    expect(() => logger.info('Null value', null)).not.toThrow();
    expect(() => logger.info('Undefined value', undefined)).not.toThrow();
  });

  // Test 18: child logger inherits methods
  test('child logger should have all logging methods', () => {
    const childLogger = logger.child({ component: 'test' });

    expect(typeof childLogger.info).toBe('function');
    expect(typeof childLogger.warn).toBe('function');
    expect(typeof childLogger.error).toBe('function');
    expect(typeof childLogger.debug).toBe('function');
    expect(typeof childLogger.fatal).toBe('function');
    expect(typeof childLogger.trace).toBe('function');
  });

  // Test 19: child logger can log messages
  test('child logger should be able to log messages', () => {
    const childLogger = logger.child({ component: 'test-component' });
    expect(() => childLogger.info('Child logger message')).not.toThrow();
  });

  // Test 20: appServiceLogger is same as logger
  test('appServiceLogger should be the same as logger', () => {
    expect(appServiceLogger).toBe(logger);
  });

  // Test 21: level formatter uppercases the level label
  test('level formatter should uppercase the level label', () => {
    expect(mockPinoConfig.formatters.level('info')).toEqual({ level: 'INFO' });
    expect(mockPinoConfig.formatters.level('error')).toEqual({ level: 'ERROR' });
  });

  // Test 22: log formatter passes objects through unchanged without a span
  test('log formatter should leave object unchanged when no active span', () => {
    (trace.getSpan as jest.Mock).mockReturnValueOnce(undefined);
    const obj = { message: 'hello', userId: 42 };
    expect(mockPinoConfig.formatters.log(obj)).toBe(obj);
  });

  // Test 23: log formatter stamps trace context when a span is active
  test('log formatter should stamp traceId/spanId/traceFlags from active span', () => {
    (trace.getSpan as jest.Mock).mockReturnValueOnce({
      spanContext: () => ({
        traceId: 'trace-abc',
        spanId: 'span-xyz',
        traceFlags: 1,
      }),
    });
    const obj: Record<string, any> = { message: 'traced' };
    const result = mockPinoConfig.formatters.log(obj);
    expect(result.traceId).toBe('trace-abc');
    expect(result.spanId).toBe('span-xyz');
    expect(result.traceFlags).toBe(1);
  });

  // Test 24: timestamp formatter produces an ISO timestamp string
  test('timestamp formatter should produce an ISO timestamp string', () => {
    const ts = mockPinoConfig.timestamp();
    expect(typeof ts).toBe('string');
    expect(ts).toMatch(/,"timestamp":"\d{4}-\d{2}-\d{2}T/);
  });

  // Test 25: base service/version come from environment or defaults
  test('base service and version should be configured', () => {
    expect(mockPinoConfig.base).toBeDefined();
    expect(typeof mockPinoConfig.base.service).toBe('string');
    expect(typeof mockPinoConfig.base.version).toBe('string');
  });

  // Test 26: dev (non-production) environment enables pino-pretty transport
  test('non-production environment should use pino-pretty transport', () => {
    // NODE_ENV defaults to 'test' here, so the pretty transport is configured.
    expect(mockPinoConfig.transport).toBeDefined();
    expect(mockPinoConfig.transport.target).toBe('pino-pretty');
  });

  // Test 27: production environment disables the pretty transport
  test('production environment should not use pino-pretty transport', () => {
    // resetMocks: true wipes the pino mock implementation before each test;
    // re-establish it so the isolated require gets a real (mocked) pino.
    const mockPinoDefault = (jest.requireMock('pino') as any).default;
    mockPinoDefault.mockImplementation((config: any) => {
      mockPinoConfig = config;
      return {
        level: 'info',
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
        debug: jest.fn(),
        fatal: jest.fn(),
        trace: jest.fn(),
        child: () => ({
          level: 'info',
          info: jest.fn(),
          warn: jest.fn(),
          error: jest.fn(),
          debug: jest.fn(),
          fatal: jest.fn(),
          trace: jest.fn(),
        }),
      };
    });
    const previousNodeEnv = process.env.NODE_ENV;
    (process.env as any).NODE_ENV = 'production';
    try {
      jest.isolateModules(() => {
        require('../logger');
      });
      expect(mockPinoConfig.transport).toBeUndefined();
    } finally {
      (process.env as any).NODE_ENV = previousNodeEnv;
    }
  });

  // Test 28: all four flexible-argument calling conventions reach pino
  test('flexible log method supports all four argument conventions', () => {
    // (string) → pino.info(message)
    expect(() => logger.info('just a message')).not.toThrow();
    // (string, object) → pino.info(object, message)
    expect(() => logger.warn('context message', { userId: 1 })).not.toThrow();
    // (object, string) → pino.info(object, message)
    expect(() => logger.error({ event: 'x' }, 'message after object')).not.toThrow();
    // (object) → pino.info(object)
    expect(() => logger.debug({ event: 'y' })).not.toThrow();
    // (object, object) → pino.info(object)
    expect(() => logger.trace({ a: 1 }, { b: 2 })).not.toThrow();
  });
});

/**
 * Logger Utilities Tests
 *
 * Tests verify Pino logger configuration, flexible log methods,
 * and child logger creation.
 *
 * Source: lib/logger.ts (68 lines)
 */

import { logger, appServiceLogger } from '../logger';

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
    expect(() => logger.error('DB Error', error, context)).not.toThrow();
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
});

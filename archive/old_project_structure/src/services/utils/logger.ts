/**
 * ATOM Logger - Shared logging utility
 */

import { LOG_LEVELS, DEFAULT_LOG_LEVEL } from './constants';

export type LogLevel = typeof LOG_LEVELS[keyof typeof LOG_LEVELS];

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: any;
  service?: string;
}

class Logger {
  private service: string;
  private logLevel: LogLevel;

  constructor(service: string = 'ATOM') {
    this.service = service;
    this.logLevel = (process.env.LOG_LEVEL as LogLevel) || DEFAULT_LOG_LEVEL;
  }

  private shouldLog(level: LogLevel): boolean {
    const levels = [LOG_LEVELS.ERROR, LOG_LEVELS.WARN, LOG_LEVELS.INFO, LOG_LEVELS.DEBUG];
    const currentLevelIndex = levels.indexOf(this.logLevel);
    const messageLevelIndex = levels.indexOf(level);
    return messageLevelIndex <= currentLevelIndex;
  }

  private formatMessage(level: LogLevel, message: string, context?: any): LogEntry {
    return {
      timestamp: new Date().toISOString(),
      level,
      message,
      context,
      service: this.service,
    };
  }

  private output(entry: LogEntry): void {
    if (!this.shouldLog(entry.level)) return;

    const logString = `[${entry.timestamp}] [${entry.level.toUpperCase()}] [${entry.service}] ${entry.message}`;
    
    switch (entry.level) {
      case LOG_LEVELS.ERROR:
        console.error(logString, entry.context || '');
        break;
      case LOG_LEVELS.WARN:
        console.warn(logString, entry.context || '');
        break;
      case LOG_LEVELS.INFO:
        console.info(logString, entry.context || '');
        break;
      case LOG_LEVELS.DEBUG:
        console.debug(logString, entry.context || '');
        break;
      default:
        console.log(logString, entry.context || '');
    }
  }

  error(message: string, context?: any): void {
    this.output(this.formatMessage(LOG_LEVELS.ERROR, message, context));
  }

  warn(message: string, context?: any): void {
    this.output(this.formatMessage(LOG_LEVELS.WARN, message, context));
  }

  info(message: string, context?: any): void {
    this.output(this.formatMessage(LOG_LEVELS.INFO, message, context));
  }

  debug(message: string, context?: any): void {
    this.output(this.formatMessage(LOG_LEVELS.DEBUG, message, context));
  }

  // Static method for creating service-specific loggers
  static create(service: string): Logger {
    return new Logger(service);
  }
}

// Export a default logger instance
export const logger = new Logger('ATOM');

// Export the class for custom loggers
export { Logger };
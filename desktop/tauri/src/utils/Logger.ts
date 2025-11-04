/**
 * Logger Utility
 */

export class Logger {
  private context: string;

  constructor(context: string) {
    this.context = context;
  }

  info(message: string, data?: any): void {
    console.log(`[${this.context}] ${message}`, data || '');
  }

  warn(message: string, data?: any): void {
    console.warn(`[${this.context}] ${message}`, data || '');
  }

  error(message: string, error?: any): void {
    console.error(`[${this.context}] ${message}`, error || '');
  }

  debug(message: string, data?: any): void {
    console.debug(`[${this.context}] ${message}`, data || '');
  }
}
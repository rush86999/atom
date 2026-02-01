export class Logger {
  constructor(private serviceName: string) {}

  info(message: string, ...args: any[]): void {
    console.log(`[${this.serviceName}] ${message}`, ...args);
  }

  error(message: string, error?: any): void {
    console.error(`[${this.serviceName}] ${message}`, error);
  }

  warn(message: string, ...args: any[]): void {
    console.warn(`[${this.serviceName}] ${message}`, ...args);
  }

  debug(message: string, ...args: any[]): void {
    console.debug(`[${this.serviceName}] ${message}`, ...args);
  }
}
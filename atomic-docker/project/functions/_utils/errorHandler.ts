import { logger } from './logger';

export function handleError(error: any, defaultMessage: string): string {
  logger.error(error);
  return defaultMessage;
}

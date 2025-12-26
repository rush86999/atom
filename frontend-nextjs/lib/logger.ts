import pino, { Logger } from "pino";
import { trace, context as otelContext } from "@opentelemetry/api";

const serviceName = process.env.OTEL_SERVICE_NAME || "app-service";
const serviceVersion = process.env.OTEL_SERVICE_VERSION || "1.0.0";

const basePinoLogger = pino({
  level: "info",
  formatters: {
    level: (label) => ({ level: label.toUpperCase() }),
    log: (object: Record<string, any>) => {
      const span = trace.getSpan(otelContext.active());
      if (span) {
        const spanContext = span.spanContext();
        object.traceId = spanContext.traceId;
        object.spanId = spanContext.spanId;
        object.traceFlags = spanContext.traceFlags;
      }
      return object;
    },
  },
  timestamp: () => `,"timestamp":"${new Date(Date.now()).toISOString()}"`,
  base: {
    service: serviceName,
    version: serviceVersion,
  },
  transport:
    process.env.NODE_ENV !== "production"
      ? { target: "pino-pretty" }
      : undefined,
});

// Create a flexible logger wrapper that accepts (message, object?) or (object, message)
function createFlexibleLogMethod(level: 'info' | 'warn' | 'error' | 'debug' | 'fatal' | 'trace') {
  return (msgOrObj: string | object, objOrMsg?: string | object) => {
    if (typeof msgOrObj === 'string') {
      // Called as logger.info(message) or logger.info(message, object)
      if (objOrMsg && typeof objOrMsg === 'object') {
        (basePinoLogger[level] as any)(objOrMsg, msgOrObj);
      } else {
        (basePinoLogger[level] as any)(msgOrObj);
      }
    } else {
      // Called as logger.info(object, message)
      if (typeof objOrMsg === 'string') {
        (basePinoLogger[level] as any)(msgOrObj, objOrMsg);
      } else {
        (basePinoLogger[level] as any)(msgOrObj);
      }
    }
  };
}

const appServiceLogger = {
  info: createFlexibleLogMethod('info'),
  warn: createFlexibleLogMethod('warn'),
  error: createFlexibleLogMethod('error'),
  debug: createFlexibleLogMethod('debug'),
  fatal: createFlexibleLogMethod('fatal'),
  trace: createFlexibleLogMethod('trace'),
  child: (bindings: object) => basePinoLogger.child(bindings),
  level: basePinoLogger.level,
};

export const logger = appServiceLogger;
export { appServiceLogger };
export default appServiceLogger;

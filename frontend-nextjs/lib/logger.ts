import pino from "pino";
import { trace, context as otelContext } from "@opentelemetry/api";

const serviceName = process.env.OTEL_SERVICE_NAME || "app-service";
const serviceVersion = process.env.OTEL_SERVICE_VERSION || "1.0.0";

const appServiceLogger = pino({
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

export const logger = appServiceLogger;
export { appServiceLogger };
export default appServiceLogger;

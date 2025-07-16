import pino from 'pino';
import { trace, context as otelContext } from '@opentelemetry/api';

const serviceName = process.env.OTEL_SERVICE_NAME || 'functions-service'; // Or a more specific name if preferred
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';

const functionsServiceLogger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label.toUpperCase() }),
    log: (object: Record<string, any>) => { // Explicitly type 'object'
      // Ensure object is not undefined and is an object
      if (object && typeof object === 'object') {
        object.service_name = serviceName;
        object.version = serviceVersion;
        // Add OpenTelemetry trace and span IDs if available
        const currentSpan = trace.getSpan(otelContext.active());
        if (currentSpan) {
          const spanContext = currentSpan.spanContext();
          if (spanContext && spanContext.traceId) {
            object.trace_id = spanContext.traceId;
            object.span_id = spanContext.spanId;
          }
        }
      }
      return object;
    },
  },
  timestamp: () => `,"timestamp":"${new Date(Date.now()).toISOString()}"`,
  // Pretty print for local development can be achieved by piping output, e.g., `| pino-pretty`
  // Or by conditionally adding pino-pretty transport if not in production:
  // transport: process.env.NODE_ENV !== 'production' ? { target: 'pino-pretty' } : undefined,
});

export default functionsServiceLogger;

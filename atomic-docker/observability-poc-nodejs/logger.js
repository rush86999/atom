const pino = require('pino');
const { trace, context } = require('@opentelemetry/api');

const serviceName = process.env.OTEL_SERVICE_NAME || 'observability-poc-nodejs';
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';

// Basic pino logger configuration
const loggerConfig = {
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => {
      return { level: label.toUpperCase() };
    },
    log: (object) => {
      // Add service name and version
      object.service_name = serviceName;
      object.version = serviceVersion;

      // Add trace_id and span_id if available from OpenTelemetry
      const currentSpan = trace.getSpan(context.active());
      if (currentSpan) {
        const spanContext = currentSpan.spanContext();
        if (spanContext && spanContext.traceId) {
          object.trace_id = spanContext.traceId;
          object.span_id = spanContext.spanId;
        }
      }
      return object;
    },
  },
  timestamp: () => `,"timestamp":"${new Date(Date.now()).toISOString()}"`,
};

// Use pino-pretty for local development if not in production
const transport =
  process.env.NODE_ENV !== 'production'
    ? pino.transport({
        target: 'pino-pretty',
        options: {
          colorize: true,
          translateTime: 'SYS:standard',
          ignore: 'pid,hostname,service_name,version,trace_id,span_id', // pino-pretty will show its own time
          messageFormat:
            '{service_name}@{version} {if trace_id}(trace_id:{trace_id} span_id:{span_id}){end} {msg}',
        },
      })
    : undefined;

const logger = pino(loggerConfig, transport);

module.exports = logger;

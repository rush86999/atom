// OpenTelemetry SDK setup for Tracing and Metrics
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { alibabaCloudEcsDetector } from '@opentelemetry/resource-detector-alibaba-cloud';
import {
  awsEc2Detector,
  awsEksDetector, // awsEcsDetector is part of sdk-node by default
} from '@opentelemetry/resource-detector-aws';
import { gcpDetector } from '@opentelemetry/resource-detector-gcp';
import {
  envDetector,
  processDetector,
  osDetector,
  hostDetector,
} from '@opentelemetry/resources';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';
import { WinstonInstrumentation } from '@opentelemetry/instrumentation-winston'; // If using Winston

// For troubleshooting, set the log level to DiagLogLevel.DEBUG
// diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.INFO); // Default to INFO

const serviceName = process.env.OTEL_SERVICE_NAME || 'functions-service';
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';

// Configure OTLP Exporters
const otlpTraceExporter = new OTLPTraceExporter({
  url:
    process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT ||
    'http://localhost:4318/v1/traces',
});

const otlpMetricExporter = new OTLPMetricExporter({
  url:
    process.env.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT ||
    'http://localhost:4318/v1/metrics',
});

const metricReader = new PeriodicExportingMetricReader({
  exporter: otlpMetricExporter,
  exportIntervalMillis: process.env.OTEL_METRIC_EXPORT_INTERVAL
    ? parseInt(process.env.OTEL_METRIC_EXPORT_INTERVAL)
    : 10000,
});

const sdk = new NodeSDK({
  serviceName: serviceName,
  serviceVersion: serviceVersion,
  traceExporter: otlpTraceExporter,
  metricReader: metricReader,
  instrumentations: [
    getNodeAutoInstrumentations({
      // Example: configure an instrumentation
      '@opentelemetry/instrumentation-http': {
        applyCustomAttributesOnSpan: (span, request, response) => {
          span.setAttribute(
            'http.request.headers',
            JSON.stringify(request.headers)
          ); // Example: add request headers
          // Be careful with sensitive data in headers
        },
      },
      '@opentelemetry/instrumentation-aws-sdk': {
        suppressInternalInstrumentation: true, // Suppress traces from internal SDK operations if too verbose
      },
      // WinstonInstrumentation is added explicitly below to ensure it's configured
    }),
    // Add WinstonInstrumentation. It needs to be instantiated.
    new WinstonInstrumentation({
      // Enabled by default, just need to instantiate if not using the meta-package for winston specifically.
      // The logHook is useful for adding custom attributes to logs based on span.
      logHook: (span, record) => {
        if (span) {
          const spanContext = span.spanContext();
          record.trace_id = spanContext.traceId;
          record.span_id = spanContext.spanId;
          // record.service_name = serviceName; // Already part of resource, but can be explicit
          // record.service_version = serviceVersion;
        }
      },
    }),
  ],
  resourceDetectors: [
    alibabaCloudEcsDetector,
    awsEc2Detector,
    awsEksDetector, // awsEcsDetector is included by default in recent sdk-node versions
    gcpDetector,
    envDetector,
    processDetector,
    osDetector,
    hostDetector,
  ],
  // autoDetectResources: true, // This is true by default
});

// Graceful shutdown
process.on('SIGTERM', () => {
  sdk
    .shutdown()
    .then(() => console.log('OpenTelemetry SDK terminated successfully'))
    .catch((error) =>
      console.error('Error shutting down OpenTelemetry SDK', error)
    )
    .finally(() => process.exit(0));
});

process.on('SIGINT', () => {
  sdk
    .shutdown()
    .then(() =>
      console.log('OpenTelemetry SDK terminated successfully (SIGINT)')
    )
    .catch((error) =>
      console.error('Error shutting down OpenTelemetry SDK (SIGINT)', error)
    )
    .finally(() => process.exit(0));
});

// Start the SDK and load all configured instrumentations
try {
  sdk.start();
  console.log(
    `OpenTelemetry SDK started for service: ${serviceName}@${serviceVersion}`
  );
  console.log(`OTLP Trace Exporter configured for: ${otlpTraceExporter.url}`);
  console.log(`OTLP Metric Exporter configured for: ${otlpMetricExporter.url}`);
} catch (error) {
  console.error('Error starting OpenTelemetry SDK:', error);
}

// Export an initialized Meter for custom metrics
import { metrics } from '@opentelemetry/api';
const meter = metrics.getMeterProvider().getMeter(serviceName, serviceVersion);

// Define and export common metrics
const httpServerRequestsTotal = meter.createCounter(
  'http_server_requests_total',
  {
    description: 'Total number of HTTP requests handled.',
    unit: '1',
  }
);

const httpServerRequestDurationSeconds = meter.createHistogram(
  'http_server_request_duration_seconds',
  {
    description: 'Duration of HTTP server requests.',
    unit: 's',
  }
);

const activeWebsocketConnections = meter.createUpDownCounter(
  'websocket_connections_active',
  {
    description: 'Number of active WebSocket connections.',
    unit: '1',
  }
);

const websocketMessagesReceivedTotal = meter.createCounter(
  'websocket_messages_received_total',
  {
    description: 'Total number of messages received over WebSockets.',
    unit: '1',
  }
);

export {
  httpServerRequestsTotal,
  httpServerRequestDurationSeconds,
  activeWebsocketConnections,
  websocketMessagesReceivedTotal,
  // tracer: sdk.getTracer(serviceName, serviceVersion) // Export tracer if manual tracing is needed beyond auto-instrumentation
};

// For this service, we primarily rely on auto-instrumentation and the NODE_OPTIONS pre-load.
// If manual instrumentation is needed extensively, exporting tracer/meter would be useful.
// The `NODE_OPTIONS="--require ./opentelemetry.js"` in CDK handles preloading this file.
// Ensure this file doesn't have side effects that break the server if it's imported multiple times,
// though the SDK itself handles singleton instances.
// The `sdk.start()` should only be called once. This file being required by NODE_OPTIONS ensures it runs early.

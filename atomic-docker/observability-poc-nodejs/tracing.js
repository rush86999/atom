const { NodeSDK } = require('@opentelemetry/sdk-node');
const {
  OTLPTraceExporter,
} = require('@opentelemetry/exporter-trace-otlp-http');
const {
  OTLPMetricExporter,
} = require('@opentelemetry/exporter-metrics-otlp-http');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const {
  alibabaCloudEcsDetector,
} = require('@opentelemetry/resource-detector-alibaba-cloud');
const {
  awsEc2Detector,
  awsEksDetector,
} = require('@opentelemetry/resource-detector-aws');
const { gcpDetector } = require('@opentelemetry/resource-detector-gcp');
const {
  envDetector,
  processDetector,
  osDetector,
  hostDetector,
} = require('@opentelemetry/resources');
const {
  getNodeAutoInstrumentations,
} = require('@opentelemetry/auto-instrumentations-node');
const { diag, DiagConsoleLogger, DiagLogLevel } = require('@opentelemetry/api');

// For troubleshooting, set the log level to DiagLogLevel.DEBUG
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.INFO);

const serviceName = process.env.OTEL_SERVICE_NAME || 'observability-poc-nodejs';
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';

// Configure OTLP Exporters (default to localhost for easy local collector setup)
// Traces
const otlpTraceExporter = new OTLPTraceExporter({
  url:
    process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT ||
    'http://localhost:4318/v1/traces',
  // headers: {}, // Optional headers
});

// Metrics
const otlpMetricExporter = new OTLPMetricExporter({
  url:
    process.env.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT ||
    'http://localhost:4318/v1/metrics',
  // headers: {}, // Optional headers
});

const metricReader = new PeriodicExportingMetricReader({
  exporter: otlpMetricExporter,
  exportIntervalMillis: 10000, // Export metrics every 10 seconds
});

const sdk = new NodeSDK({
  serviceName: serviceName,
  serviceVersion: serviceVersion,
  traceExporter: otlpTraceExporter,
  metricReader: metricReader,
  instrumentations: [
    getNodeAutoInstrumentations({
      // Example: disable an instrumentation
      // '@opentelemetry/instrumentation-fs': { enabled: false },
    }),
  ],
  resourceDetectors: [
    // Order matters, first detected resource is used.
    alibabaCloudEcsDetector,
    awsEc2Detector,
    awsEksDetector,
    gcpDetector,
    // Standard resource detectors
    envDetector,
    processDetector,
    osDetector,
    hostDetector,
  ],
});

// Graceful shutdown
process.on('SIGTERM', () => {
  sdk
    .shutdown()
    .then(() => console.log('Tracing and Metrics terminated'))
    .catch((error) =>
      console.error('Error shutting down tracing and metrics', error)
    )
    .finally(() => process.exit(0));
});

// Start the SDK and load all configured instrumentations
sdk.start();
console.log('OpenTelemetry SDK started...');

// Initialize Metrics (example)
const { metrics } = require('@opentelemetry/api');
const meter = metrics.getMeterProvider().getMeter(serviceName);

const requestCounter = meter.createCounter('app_request_count', {
  description: 'Counts total requests by endpoint and status code',
});

const activeRequestsGauge = meter.createUpDownCounter('app_active_requests', {
  description: 'Gauge for active requests',
});

const requestLatencyHistogram = meter.createHistogram(
  'app_request_latency_seconds',
  {
    description: 'Request latency in seconds',
    unit: 's',
  }
);

const itemsProcessedCounter = meter.createCounter('app_items_processed_total', {
  description: 'Counts items processed',
});

module.exports = {
  requestCounter,
  activeRequestsGauge,
  requestLatencyHistogram,
  itemsProcessedCounter,
  tracer: sdk.getTracer(serviceName), // Export a tracer for custom spans
};

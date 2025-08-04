/*
// instrumentation.node.js - For Next.js server-side OpenTelemetry
// This file should be in the root of your Next.js project.
// Next.js (version 12.2.0 and newer) will automatically load this file
// if the `instrumentationHook` experimental feature is enabled in next.config.js,
// or by default in newer versions.
// Alternatively, for older Next.js or non-standard setups, you might need to
// require this file at the very top of your custom server if you use one,
// or ensure NODE_OPTIONS preloads it as done for other services.
// Given we set NODE_OPTIONS in CDK for AppService, this will serve as the preload.

import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { alibabaCloudEcsDetector } from '@opentelemetry/resource-detector-alibaba-cloud';
import { awsEc2Detector, awsEksDetector } from '@opentelemetry/resource-detector-aws';
import { gcpDetector } from '@opentelemetry/resource-detector-gcp';
import { envDetector, processDetector, osDetector, hostDetector } from '@opentelemetry/resources';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';
// Placeholder for Winston or other logger instrumentation if used in API routes
// import { WinstonInstrumentation } from '@opentelemetry/instrumentation-winston';

// Set to DiagLogLevel.DEBUG for verbose OpenTelemetry diagnostic logging
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.INFO);

const serviceName = process.env.OTEL_SERVICE_NAME || 'app-service'; // As per CDK
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';

let sdkInstance = null;

export async function register() {
  // This function is called by Next.js during initialization if using the instrumentation hook.
  // If preloaded via NODE_OPTIONS, this specific export might not be directly used by Next.js
  // but the SDK initialization below will still run.

  if (process.env.NEXT_RUNTIME === 'nodejs') { // Ensure this runs only for server-side
    console.log(`Initializing OpenTelemetry for AppService (Node.js runtime)...`);

    const otlpTraceExporter = new OTLPTraceExporter({
      url: process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT || 'http://localhost:4318/v1/traces',
    });

    const otlpMetricExporter = new OTLPMetricExporter({
      url: process.env.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT || 'http://localhost:4318/v1/metrics',
    });

    const metricReader = new PeriodicExportingMetricReader({
      exporter: otlpMetricExporter,
      exportIntervalMillis: process.env.OTEL_METRIC_EXPORT_INTERVAL ? parseInt(process.env.OTEL_METRIC_EXPORT_INTERVAL) : 10000,
    });

    sdkInstance = new NodeSDK({
      serviceName: serviceName,
      serviceVersion: serviceVersion,
      traceExporter: otlpTraceExporter,
      metricReader: metricReader,
      instrumentations: [
        getNodeAutoInstrumentations({
          // Consider using '@opentelemetry/instrumentation-nextjs' for more specific Next.js integration
          // if it provides better context or covers edge cases not handled by general HTTP/Express.
          '@opentelemetry/instrumentation-http': {
            // Config for HTTP instrumentation if needed
          },
          '@opentelemetry/instrumentation-aws-sdk': {
            suppressInternalInstrumentation: true,
          },
          // Add WinstonInstrumentation if used in API routes and it's not auto-detected well.
          // Example:
          // new WinstonInstrumentation({ /* config */ }),
        }),
      ],
      resourceDetectors: [
        alibabaCloudEcsDetector,
        awsEc2Detector,
        awsEksDetector,
        gcpDetector,
        envDetector,
        processDetector,
        osDetector,
        hostDetector,
      ],
    });

    try {
      await sdkInstance.start();
      console.log(`OpenTelemetry SDK started for AppService: ${serviceName}@${serviceVersion}`);
      console.log(`AppService OTLP Trace Exporter configured for: ${otlpTraceExporter.url}`);
      console.log(`AppService OTLP Metric Exporter configured for: ${otlpMetricExporter.url}`);
    } catch (error) {
      console.error('Error starting OpenTelemetry SDK for AppService:', error);
    }

    // Graceful shutdown (might be handled by Next.js or need manual hook-in for custom servers)
    // For Next.js managed server, direct process.on might not be the best.
    // However, if NODE_OPTIONS preloads this, these hooks are global.
    const shutdown = async (signal) => {
      console.log(`Received ${signal}, shutting down AppService OpenTelemetry SDK...`);
      try {
        await sdkInstance?.shutdown();
        console.log('AppService OpenTelemetry SDK terminated successfully.');
      } catch (err) {
        console.error('Error shutting down AppService OpenTelemetry SDK:', err);
      }
      process.exit(0); // Should this be here or let Next.js handle exit?
    };
    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT', () => shutdown('SIGINT'));

  } else {
    console.log("OpenTelemetry for AppService: Not a Node.js runtime, skipping SDK initialization.");
  }
}


// If not using Next.js's instrumentationHook, and relying solely on NODE_OPTIONS --require,
// the SDK start needs to happen unconditionally when the file is loaded for server-side.
// The `register` function is specific to Next.js's hook.
if (process.env.NODE_ENV !== 'production' || process.env.NEXT_RUNTIME === 'nodejs') {
    // Simplified auto-start for non-Next.js hook scenarios or if preloaded.
    // This might conflict if Next.js also calls register().
    // A check for `sdkInstance` can prevent double initialization.
    if (!sdkInstance && process.env.NEXT_RUNTIME === 'nodejs') { // Ensure it's server-side
        // Minimal setup for direct require, assuming register() might not be called by Next.js in all contexts.
        // This logic is tricky with Next.js's evolving instrumentation.
        // For now, let's assume NODE_OPTIONS will make `register()` effectively run or the below.
        // The `register` export is the cleaner Next.js way.
        // The CDK uses NODE_OPTIONS, so this file will be required.
        // The `register` function itself won't be auto-called unless `instrumentationHook` is true.
        // However, newer Next.js versions might call it by default.
        // For safety with NODE_OPTIONS, we can just run the core logic.

        // Re-evaluating: If NODE_OPTIONS requires this, the code outside `export async function register()`
        // will run. The SDK initialization should be outside the `register` function
        // if we rely on NODE_OPTIONS rather than the explicit Next.js instrumentation hook.

        // Let's simplify: the SDK setup logic will run when this file is required.
        // The `register` export is for Next.js if it uses its hook.
        // If `NODE_OPTIONS` loads it, the top-level code (imports and SDK init) runs.

        // The previous version of this file for `functions-service` had sdk.start() at top level.
        // Let's ensure that for AppService too if relying on NODE_OPTIONS.
        // The `register()` function is more for when Next.js itself controls the loading via its hook.

        // The code below is a duplication of what's in `register()`.
        // This needs to be structured so it initializes once.
        // A common pattern:
        // if (process.env.NEXT_RUNTIME === 'nodejs' && !sdkInstance) { /* init */ }
        // The `register` function becomes the main entry point for Next.js hook.
        // If required by NODE_OPTIONS, the same logic needs to run.
        // The current structure with register() is fine if Next.js calls it.
        // If NODE_OPTIONS is the only mechanism, the content of register() should be at the top level.
        // Given NODE_OPTIONS is set in CDK, let's ensure top-level execution.
    }
}

// Export metrics and tracer for use in API routes or server-side components
import { metrics, trace } from '@opentelemetry/api';

// Ensure meter is created only after SDK is potentially started by register() or top-level exec.
// This is a bit tricky with Next.js. Await sdk.start() if possible, or get meter on first use.
// For now, assume SDK is started when this module is fully processed.
const getMeter = () => {
    if (!sdkInstance && process.env.NEXT_RUNTIME === 'nodejs') {
        // This indicates SDK didn't initialize via register() and wasn't started at top-level.
        // This state shouldn't ideally happen if NODE_OPTIONS is used and top-level start is there.
        // For robustness, could try a lazy init of SDK here, but that's complex.
        // Best to ensure SDK is started when this module loads if not using Next.js hook.
        // The POC had sdk.start() at top level.
        // For Next.js with NODE_OPTIONS, it's better if the main SDK init runs when required.
        // Let's assume `register()` is called or the init logic runs due to NODE_OPTIONS.
    }
    return metrics.getMeterProvider().getMeter(serviceName, serviceVersion);
};

// Example metrics - these would be used in your API routes
const apiRequestCounter = getMeter().createCounter('app_api_request_count', {
  description: 'Counts API requests handled by AppService',
});

const apiRequestLatencyHistogram = getMeter().createHistogram('app_api_request_latency_seconds', {
  description: 'API request latency in AppService',
  unit: 's',
});

export {
  apiRequestCounter,
  apiRequestLatencyHistogram,
  // getTracer: () => trace.getTracer(serviceName, serviceVersion), // For manual spans
};

// If NODE_OPTIONS is used, the `register` function might not be called by Next.js.
// The SDK initialization logic should be runnable when the file is simply required.
// The current structure relies on `register` being called.
// To make it work robustly with `NODE_OPTIONS="--require"`, the core SDK setup
// from `register()` should be moved to the top level of this file, guarded by
// `if (process.env.NEXT_RUNTIME === 'nodejs' && !sdkInstance)`.

// Corrected structure for NODE_OPTIONS --require:
function initializeOtel() {
    if (sdkInstance) return sdkInstance; // Already initialized

    if (process.env.NEXT_RUNTIME === 'nodejs') {
        diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.INFO);
        console.log(`Initializing OpenTelemetry for AppService (Node.js runtime via direct require)...`);

        const otlpTraceExporter = new OTLPTraceExporter({
            url: process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT || 'http://localhost:4318/v1/traces',
        });
        const otlpMetricExporter = new OTLPMetricExporter({
            url: process.env.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT || 'http://localhost:4318/v1/metrics',
        });
        const metricReader = new PeriodicExportingMetricReader({
            exporter: otlpMetricExporter,
            exportIntervalMillis: process.env.OTEL_METRIC_EXPORT_INTERVAL ? parseInt(process.env.OTEL_METRIC_EXPORT_INTERVAL) : 10000,
        });

        sdkInstance = new NodeSDK({
            serviceName: serviceName,
            serviceVersion: serviceVersion,
            traceExporter: otlpTraceExporter,
            metricReader: metricReader,
            instrumentations: [getNodeAutoInstrumentations({
                '@opentelemetry/instrumentation-http': {},
                '@opentelemetry/instrumentation-aws-sdk': { suppressInternalInstrumentation: true },
            })],
            resourceDetectors: [alibabaCloudEcsDetector, awsEc2Detector, awsEksDetector, gcpDetector, envDetector, processDetector, osDetector, hostDetector],
        });

        try {
            sdkInstance.start();
            console.log(`OpenTelemetry SDK started for AppService: ${serviceName}@${serviceVersion} (direct require)`);
        } catch (error) {
            console.error('Error starting OpenTelemetry SDK for AppService (direct require):', error);
        }

        process.on('SIGTERM', () => sdkInstance?.shutdown().then(() => console.log('OTel SDK shutdown (SIGTERM)')) .catch(e => console.error('OTel SDK shutdown error (SIGTERM)', e)));
        process.on('SIGINT', () => sdkInstance?.shutdown().then(() => console.log('OTel SDK shutdown (SIGINT)')) .catch(e => console.error('OTel SDK shutdown error (SIGINT)', e)));

        return sdkInstance;
    }
    return null;
}

// Initialize if this file is required (e.g., by NODE_OPTIONS) and it's server-side
initializeOtel();
*/

```

// IMPORTANT: Initialize tracing and metrics BEFORE other imports, especially Express
const {
  requestCounter,
  activeRequestsGauge,
  requestLatencyHistogram,
  itemsProcessedCounter,
  tracer,
} = require('./tracing');
const { trace, context, SpanStatusCode } = require('@opentelemetry/api');

const express = require('express');
const logger = require('./logger'); // Import the logger
const pinoHttp = require('pino-http');

const app = express();
const port = process.env.PORT || 3000;

// Middleware for HTTP request logging
// This is now correctly placed *after* tracing is initialized.
// Pino-http will automatically pick up trace_id from OpenTelemetry context if available.
const httpLogger = pinoHttp({
  logger: logger,
  customSuccessMessage: function (req, res) {
    if (res.statusCode === 404) {
      return 'Resource not found';
    }
    return `${req.method} ${req.originalUrl || req.url} completed ${res.statusCode}`;
  },
  customErrorMessage: function (req, res, err) {
    return `${req.method} ${req.originalUrl || req.url} errored ${res.statusCode} with ${err.message}`;
  },
  serializers: {
    req: (req) => ({
      method: req.method,
      url: req.originalUrl || req.url, // Use originalUrl for Express
      id: req.id,
    }),
    res: (res) => ({
      statusCode: res.statusCode,
    }),
    err: pinoHttp.stdSerializers.err,
  },
  customProps: function (req, res) {
    const currentSpan = trace.getSpan(context.active());
    let traceId, spanId;
    if (currentSpan) {
      const spanContext = currentSpan.spanContext();
      if (spanContext && spanContext.traceId) {
        traceId = spanContext.traceId;
        spanId = spanContext.spanId;
      }
    }
    return {
      operation_name: `${req.method} ${req.originalUrl || req.url}`,
      trace_id: traceId, // Explicitly add trace_id from OTEL context
      span_id: spanId, // Explicitly add span_id from OTEL context
      // user_id: req.user ? req.user.id : undefined,
    };
  },
});
app.use(httpLogger);

// Middleware to track active requests
app.use((req, res, next) => {
  activeRequestsGauge.add(1, { remote_address: req.ip });
  res.on('finish', () => {
    activeRequestsGauge.add(-1, { remote_address: req.ip });
    // Record latency
    const startTime = req._startTime || process.hrtime(); // pino-http might add _startTime
    const duration = process.hrtime(startTime);
    const durationInSeconds = duration[0] + duration[1] / 1e9;
    requestLatencyHistogram.record(durationInSeconds, {
      http_method: req.method,
      http_route: req.route ? req.route.path : req.path, // req.route might not be available for all requests
      status_code: res.statusCode,
    });
    requestCounter.add(1, {
      http_method: req.method,
      http_route: req.route ? req.route.path : req.path,
      status_code: res.statusCode,
    });
  });
  next();
});

// Middleware to parse JSON bodies
app.use(express.json());

// Example endpoint
app.get('/', (req, res) => {
  logger.info(
    { operation_name: 'GetRoot', custom_field: 'root_details', success: true },
    'Root endpoint hit successfully'
  );
  itemsProcessedCounter.add(1, { item_type: 'root_access' });
  res.status(200).send({ message: 'Hello from Observability POC!' });
});

// Another example endpoint that simulates some work
app.post('/process', async (req, res) => {
  const { data } = req.body;
  const operation_name = 'ProcessData'; // For logging

  // Start a custom span for "processing_data_logic"
  await tracer.startActiveSpan('processing_data_logic', async (span) => {
    try {
      if (!data) {
        logger.warn(
          {
            operation_name,
            success: false,
            error_code: 'VALIDATION_001',
            request_body: req.body,
          },
          'Missing data in /process request body'
        );
        span.setStatus({ code: SpanStatusCode.ERROR, message: 'Missing data' });
        span.recordException(new Error('Missing data in request body'));
        itemsProcessedCounter.add(1, {
          item_type: 'process_validation_failed',
        });
        return res.status(400).send({ error: 'Missing data in request body' });
      }

      logger.info(
        { operation_name, data_received_length: data.length },
        'Processing data request started'
      );
      span.setAttribute('app.data.size', data.length);

      // Simulate some processing time
      const processingTimeMs = Math.random() * 100 + 50; // 50-150ms
      await new Promise((resolve) => setTimeout(resolve, processingTimeMs));

      span.setAttribute('app.processing.time_ms', processingTimeMs);
      itemsProcessedCounter.add(1, { item_type: 'process_success' });
      logger.info(
        {
          operation_name,
          success: true,
          duration_ms: parseFloat(processingTimeMs.toFixed(2)),
        },
        'Data processed successfully'
      );
      span.setStatus({ code: SpanStatusCode.OK });
      res
        .status(200)
        .send({
          message: `Data processed successfully in ${processingTimeMs.toFixed(2)} ms`,
          processedData: `Processed: ${data}`,
        });
    } catch (e) {
      logger.error(
        {
          operation_name,
          success: false,
          error_message: e.message,
          stack_trace: e.stack,
        },
        'Error during /process'
      );
      span.setStatus({ code: SpanStatusCode.ERROR, message: e.message });
      span.recordException(e);
      itemsProcessedCounter.add(1, { item_type: 'process_error' });
      if (!res.headersSent) {
        res.status(500).send({ error: 'Failed to process data' });
      }
    } finally {
      span.end();
    }
  });
});

// Simulate an error endpoint
app.get('/error', (req, res) => {
  const operation_name = 'GetError';
  try {
    const err = new Error('This is a simulated error!');
    err.customProperty = 'some_value'; // Example custom property on error
    throw err;
  } catch (error) {
    // Auto-instrumentation for express should capture this error on the active span.
    // Forcing it here for clarity if needed, or if not using express instrumentation fully.
    const currentSpan = trace.getSpan(context.active());
    if (currentSpan) {
      currentSpan.recordException(error);
      currentSpan.setStatus({
        code: SpanStatusCode.ERROR,
        message: error.message,
      });
      currentSpan.setAttributes({
        'app.error.custom_property': error.customProperty,
        'app.error.type': 'simulated_known_error',
      });
    }
    logger.error(
      {
        operation_name,
        success: false,
        error_message: error.message,
        exception_type: error.name,
        stack_trace: error.stack,
        custom_prop: error.customProperty,
      },
      'Simulated error caught in /error endpoint'
    );
    res
      .status(500)
      .send({
        error: 'Simulated Internal Server Error',
        message: error.message,
      });
  }
});

app.listen(port, () => {
  logger.info(
    `POC App listening on port ${port}. NODE_ENV: ${process.env.NODE_ENV || 'development'}`
  );
});

# Observability POC - Node.js

This application serves as a Proof-of-Concept (POC) demonstrating integrated observability practices for Node.js services, including:

1.  **Structured Logging:** Using Pino, with logs formatted as JSON, including trace context.
2.  **Metrics:** Using OpenTelemetry Metrics SDK, exporting via OTLP/HTTP.
3.  **Distributed Tracing:** Using OpenTelemetry Tracing SDK with auto-instrumentation for Express/HTTP, exporting via OTLP/HTTP.

This POC aligns with the guidelines outlined in the main `atomic-docker/docs/OPERABILITY_GUIDE.md`.

## Prerequisites

*   Node.js (v18 or higher recommended)
*   Docker (if running as a container)
*   An OpenTelemetry Collector (e.g., ADOT Collector, plain OTel Collector, or Jaeger/Prometheus directly if they support OTLP HTTP) to receive traces and metrics. This POC defaults to exporting to `http://localhost:4318`.

## Project Structure

```
.
├── Dockerfile            # For containerizing the POC
├── index.js              # Main application logic (Express routes)
├── logger.js             # Pino logger setup
├── package.json          # Project dependencies and scripts
├── README.md             # This file
└── tracing.js            # OpenTelemetry SDK setup for tracing and metrics
```

## Setup & Running Locally (without Docker)

1.  **Clone the repository (if you haven't already).**
2.  **Navigate to this directory:**
    ```bash
    cd atomic-docker/observability-poc-nodejs
    ```
3.  **Install dependencies:**
    ```bash
    npm install
    ```
4.  **Set up an OpenTelemetry Collector:**
    *   Ensure an OTel collector is running and configured to receive OTLP HTTP on `http://localhost:4318` (or update the endpoints in `tracing.js` or via environment variables).
    *   Example: A simple local OTel Collector configuration (`otel-collector-config.yaml`):
        ```yaml
        receivers:
          otlp:
            protocols:
              http: # Port 4318 by default

        exporters:
          logging: # Logs telemetry to the console
            loglevel: debug
          # jaeger: # Example: export traces to Jaeger
          #   endpoint: "jaeger-all-in-one:14250" # If Jaeger is running in Docker
          #   tls:
          #     insecure: true
          # prometheus: # Example: export metrics to Prometheus
          #   endpoint: "0.0.0.0:8889"

        service:
          pipelines:
            traces:
              receivers: [otlp]
              exporters: [logging] # or [jaeger, logging]
            metrics:
              receivers: [otlp]
              exporters: [logging] # or [prometheus, logging]
        ```
    *   Run the collector: `otelcol --config otel-collector-config.yaml` (Download `otelcol` from OpenTelemetry releases).

5.  **Run the application:**
    *   For development (with `nodemon` and pretty logs):
        ```bash
        npm run dev
        ```
    *   For production-like (JSON logs):
        ```bash
        npm start
        ```
    The application will start on `http://localhost:3000` by default.

## Building & Running with Docker

1.  **Navigate to this directory.**
2.  **Build the Docker image:**
    ```bash
    docker build -t observability-poc-nodejs .
    ```
3.  **Run the Docker container:**
    *   **If your OTel collector is running on your host machine:**
        ```bash
        docker run -p 3000:3000 \
          -e OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://host.docker.internal:4318/v1/traces" \
          -e OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="http://host.docker.internal:4318/v1/metrics" \
          -e NODE_ENV="production" \
          observability-poc-nodejs
        ```
        *(Note: `host.docker.internal` works on Docker Desktop for Mac/Windows. For Linux, you might need to use `--network="host"` or find the host IP).*
    *   **If your OTel collector is another Docker container on a shared network (e.g., named `otel-collector`):**
        First, create a Docker network: `docker network create obs-net`
        Run collector on this network: `docker run --name otel-collector --network obs-net ... <collector-image>`
        Then run the POC app:
        ```bash
        docker run --network obs-net -p 3000:3000 \
          -e OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://otel-collector:4318/v1/traces" \
          -e OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="http://otel-collector:4318/v1/metrics" \
          -e NODE_ENV="production" \
          observability-poc-nodejs
        ```

## Endpoints

*   `GET /`: Returns a simple hello message.
*   `POST /process`: Expects a JSON body like `{"data": "some string"}`. Simulates data processing with a random delay.
*   `GET /error`: Intentionally throws an error to demonstrate error logging and tracing.

## What to Observe

1.  **Structured Logs:**
    *   When running with `npm start` or in Docker (with `NODE_ENV=production`), logs will be in JSON format.
    *   Notice fields like `timestamp`, `level`, `service_name`, `version`, `message`.
    *   Crucially, when traces are active, you should see `trace_id` and `span_id` in the logs, allowing correlation.
    *   The `pino-http` middleware automatically logs request start and end.
    *   Example JSON log line (may vary slightly):
        ```json
        {"level":"INFO","timestamp":"2023-10-29T12:00:00.123Z","service_name":"observability-poc-nodejs","version":"1.0.0","trace_id":"abcdef123456...","span_id":"fedcba9876...","message":"Root endpoint hit successfully","operation_name":"GetRoot","custom_field":"root_details","success":true}
        ```
    *   When running with `npm run dev`, logs will be pretty-printed to the console for easier reading during development.

2.  **Metrics:**
    *   If your OTel collector is configured to export metrics (e.g., to Prometheus or a logging exporter), you should see metrics like:
        *   `app_request_count`: Counter for total requests.
        *   `app_active_requests`: UpDownCounter for active requests.
        *   `app_request_latency_seconds`: Histogram for request latencies.
        *   `app_items_processed_total`: Custom counter.
    *   Check your collector's output or the configured metrics backend (e.g., Prometheus dashboard).
    *   Attributes (labels) like `http_method`, `http_route`, `status_code` will be attached to relevant metrics.

3.  **Distributed Traces:**
    *   If your OTel collector is configured to export traces (e.g., to Jaeger or a logging exporter), you should see traces for requests to the application.
    *   **Service Name:** Traces will be associated with `observability-poc-nodejs` (or as configured by `OTEL_SERVICE_NAME`).
    *   **Spans:**
        *   Express auto-instrumentation will create spans for incoming requests and route handling.
        *   HTTP client auto-instrumentation would create spans if this app made outgoing HTTP calls (not in this simple POC).
        *   The `/process` endpoint includes a **custom span** named `processing_data_logic` which demonstrates manual span creation. This span will have attributes like `app.data.size` and `app.processing.time_ms`.
        *   Errors (like in `/error` or if `POST /process` fails) should be recorded on the spans, and their status set to error.
    *   Check your collector's output or Jaeger/Zipkin UI. You'll see the trace structure, timing for each span, and attributes.

## Environment Variables

*   `PORT`: Port the application listens on (default: `3000`).
*   `LOG_LEVEL`: Log level for Pino (default: `info`).
*   `NODE_ENV`: Set to `production` for JSON logs, otherwise pretty logs (default: `development` via `npm run dev`).
*   `OTEL_SERVICE_NAME`: OpenTelemetry service name (default: `observability-poc-nodejs`).
*   `OTEL_SERVICE_VERSION`: OpenTelemetry service version (default: `1.0.0`).
*   `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`: OTLP endpoint for traces (default: `http://localhost:4318/v1/traces`).
*   `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`: OTLP endpoint for metrics (default: `http://localhost:4318/v1/metrics`).

This POC provides a foundational example. Real-world applications would expand on these concepts with more detailed custom instrumentation, error handling, and configuration management.
```

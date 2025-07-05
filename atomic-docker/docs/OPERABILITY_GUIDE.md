# Atom Agent Observability Guide for Application Teams

## 1. Introduction

This guide provides application development teams with essential information and strategies for enhancing the observability of the Atom Agent services. Observability is key to building reliable, maintainable, and performant applications. By implementing consistent practices for logging, metrics, and tracing, we can collectively improve our ability to:

*   Monitor system health and performance.
*   Quickly diagnose and debug issues.
*   Understand system behavior and identify bottlenecks.
*   Make data-driven decisions for improvements and scaling.

This guide consolidates strategies and guidelines for:

*   **Structured Logging:** How to format and emit logs effectively.
*   **Application Metrics:** What key metrics to track and how.
*   **Distributed Tracing:** How to implement and leverage AWS X-Ray for end-to-end request tracing.

These practices apply to services deployed both in Docker Compose (for local development and some environments) and AWS (via ECS Fargate).

## 2. Structured Logging

**Goal:** Ensure all logs are consistent, machine-readable, and provide rich contextual information.

**Key Document:** [**Structured Logging Guidelines**](./STRUCTURED_LOGGING_GUIDELINES.md)

**Summary of Guidelines:**

*   **Format:** All logs MUST be in **JSON format**.
*   **Output:** Logs MUST be written to `stdout`/`stderr` for containerized environments.
*   **Standard Fields (MUST HAVE):**
    *   `timestamp`: ISO 8601 format (e.g., `2023-10-28T14:35:12.123Z`).
    *   `level`: `INFO`, `WARN`, `ERROR`, `DEBUG`, `TRACE` (uppercase).
    *   `service_name`: Name of your service (e.g., `functions-service`).
    *   `version`: Service version.
    *   `message`: Human-readable log message.
*   **Contextual Fields (SHOULD HAVE where applicable):**
    *   **Tracing:** `trace_id`, `span_id` (critical for correlating with X-Ray).
    *   **Request/Operation:** `request_id`, `user_id` (PII considerations), `operation_name`, `duration_ms`, `http_method`, `http_path`, `http_status_code`, `success`.
    *   **Errors:** `error_code` (application-specific), `error_message`, `exception_type`, `stack_trace`.
    *   **Service-Specific:** Any other relevant fields (e.g., `entity_id`, `queue_name`).
*   **Log Levels:** Use standard levels appropriately. Default production level should be `INFO`.
*   **Libraries:** Use logging libraries that support structured JSON output and allow easy addition of custom fields (e.g., Winston/Pino for Node.js, standard `logging` with JSON formatter for Python).
*   **Sensitive Information:** AVOID logging raw sensitive data. Use masking or redaction.
*   **Integration with Tracing:** Ensure `trace_id` and `span_id` from X-Ray/OpenTelemetry are automatically included in log entries.

**Action for Teams:**
1.  Review the full [Structured Logging Guidelines](./STRUCTURED_LOGGING_GUIDELINES.md).
2.  Ensure your service's logging setup complies with these guidelines.
3.  Update logging configurations and code as necessary.

## 3. Application-Level Metrics

**Goal:** Collect key performance indicators (KPIs) and operational metrics from services to monitor health, performance, and usage patterns.

**Key Document:** [**Application-Level Metrics Proposal**](./APPLICATION_METRICS_PROPOSAL.md)

**Summary of Proposal:**

The document lists a comprehensive set of potential metrics. Teams should prioritize and implement those most relevant to their services.

*   **General API/Service Metrics (Highly Recommended):**
    *   `RequestLatencySeconds` (Histogram): Latency per endpoint.
    *   `RequestCount` (Counter): Request volume per endpoint/status code.
    *   `ErrorCount` (Counter): Error volume per endpoint/error type.
*   **Language/Framework Specifics:**
    *   **Node.js:** Use libraries like `prom-client` for Prometheus-compatible metrics if deploying to an environment scraped by Prometheus, or the OpenTelemetry Metrics SDK for exporting to CloudWatch (via ADOT Collector) or other backends.
    *   **Python:** Use `prometheus_client` or the OpenTelemetry Metrics SDK.
    *   **Java/Quarkus:** Micrometer (for Prometheus) or OpenTelemetry Metrics SDK.
*   **Key Metric Categories Proposed:**
    *   Task Management (Notion Backend)
    *   Smart Scheduling & Calendar Management
    *   Integrated Note-Taking & Research
    *   Live Meeting Attendance
    *   External Integrations (Gmail, Slack, etc.)
    *   Message Queue Metrics (Kafka)
    *   AI Model Interaction Metrics (OpenAI)
*   **CloudWatch:** For AWS deployments, custom metrics should be published to CloudWatch under a common namespace (e.g., `AtomicApp` or `AtomAgent`) with dimensions like `ServiceName`, `OperationName`, `Environment`. The ADOT Collector can be configured to convert OpenTelemetry metrics to CloudWatch metrics.
*   **Docker Compose/Prometheus:** For local or Docker Compose based setups using the Prometheus stack, ensure your service exposes a `/metrics` endpoint in Prometheus format.

**Action for Teams:**
1.  Review the [Application-Level Metrics Proposal](./APPLICATION_METRICS_PROPOSAL.md).
2.  Identify and prioritize the top 3-5 most critical metrics for your service's health and performance.
3.  Instrument your service to collect and expose/publish these metrics.
    *   For AWS: Plan to use OpenTelemetry Metrics SDK -> ADOT Collector -> CloudWatch.
    *   For Docker Compose (if Prometheus is used): Expose a Prometheus metrics endpoint.
4.  Consult with the platform/ops team on naming conventions and target monitoring systems.

## 4. Distributed Tracing (AWS X-Ray)

**Goal:** Implement end-to-end request tracing to visualize request flows, identify performance bottlenecks across services, and simplify debugging of distributed operations.

**Key Document:** [**AWS X-Ray Integration Strategy**](./XRAY_INTEGRATION_STRATEGY.md)

**Summary of Strategy:**

*   **Technology:** AWS X-Ray, primarily using **AWS Distro for OpenTelemetry (ADOT)** for application instrumentation.
*   **ADOT Collector:** Will be deployed as a sidecar container in ECS Fargate tasks. Applications send trace data to this local collector via OpenTelemetry Protocol (OTLP).
*   **Application Instrumentation (OpenTelemetry SDKs):**
    *   **Node.js:** `@opentelemetry/sdk-node`, auto-instrumentations (`@opentelemetry/auto-instrumentations-node`), OTLP exporter.
    *   **Python:** `opentelemetry-sdk`, auto-instrumentations (e.g., `opentelemetry-instrumentation-fastapi`), OTLP exporter.
    *   **Java/Quarkus:** Quarkus has native OpenTelemetry support; configure OTLP exporter.
    *   A central `tracing` setup module in each service is recommended.
*   **What to Trace:**
    *   **Automatic:** Incoming/outgoing HTTP calls, AWS SDK calls (via auto-instrumentation).
    *   **Manual:** Key business logic functions, calls to external non-HTTP services, specific internal operations. Create custom spans with descriptive names.
*   **Attributes (Annotations/Metadata):** Add relevant attributes to spans (e.g., `userId`, `entityId`, `operationName`).
*   **Error Handling:** Ensure exceptions are recorded on spans.
*   **Log Correlation:** **Crucially, ensure `trace_id` and `span_id` are included in your structured logs** (see Logging section).
*   **Context Propagation:**
    *   Handled automatically for HTTP by OpenTelemetry SDKs.
    *   For asynchronous flows (e.g., Kafka), manual propagation of trace context (e.g., `traceparent` header) in messages is required.
*   **Local Development:** Test by sending traces to a local ADOT collector, which can then forward to Jaeger/Zipkin or the console.
*   **Sampling:** AWS X-Ray default sampling is 1 req/sec + 5% of additional. Higher rates for dev/staging can be configured.

**Action for Teams:**
1.  Review the full [AWS X-Ray Integration Strategy](./XRAY_INTEGRATION_STRATEGY.md).
2.  Familiarize yourself with OpenTelemetry for your language.
3.  **CDK Changes:** Be aware that ECS Task Definitions will be updated to include the ADOT Collector sidecar.
4.  **Implementation:**
    *   Add OpenTelemetry SDK and OTLP exporter to your service.
    *   Implement the tracing initialization module.
    *   Start with auto-instrumentation for HTTP and AWS SDK calls.
    *   Identify 1-2 critical business operations in your service and add custom spans for them.
    *   Ensure `trace_id` is logged.
5.  Test tracing locally and then in dev/staging environments.

## 5. General Recommendations

*   **Consistency is Key:** Adhering to these guidelines across all services will maximize the benefits of our observability efforts.
*   **Start Small, Iterate:** If full instrumentation seems daunting, start with the basics (e.g., standard log fields, request latency/error metrics, basic X-Ray auto-instrumentation) and iterate to add more detail.
*   **Dashboarding:** The collected logs and metrics will feed into CloudWatch Dashboards (like the 'System Health Overview' and upcoming 'Application Performance Deep Dive' dashboards) and potentially Grafana for Docker Compose environments. Well-structured data is essential for useful dashboards.
*   **Alerting:** Granular alarms are being set up based on infrastructure metrics and will be expanded to use application-specific metrics as they become available.
*   **Documentation:** Document any service-specific observability configurations or custom metrics within your service's own documentation.
*   **Collaboration:** Share learnings and best practices with other teams. If you develop a useful utility for logging, metrics, or tracing, consider making it a shared library.

By embracing these observability practices, we can build a more robust and understandable Atom Agent platform. Please refer to the linked detailed documents for more in-depth information. If you have questions, reach out to the platform engineering or observability subject matter experts.

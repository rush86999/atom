# AWS X-Ray Integration Strategy for Atom Agent

## 1. Introduction

This document outlines the strategy for integrating AWS X-Ray into the Atom Agent services to enable distributed tracing. Distributed tracing provides end-to-end visibility of requests as they flow through various microservices and components of our system. This is crucial for debugging issues, identifying performance bottlenecks, understanding service dependencies, and improving overall system reliability.

This strategy builds upon the foundational X-Ray infrastructure already established (ALB X-Ray tracing enabled, ECS Task Role IAM permissions for X-Ray) as detailed in the `deployment/aws/OPERABILITY_DESIGN.md` document. We will primarily use the **AWS Distro for OpenTelemetry (ADOT)** for application instrumentation, as it offers a flexible and vendor-neutral approach.

## 2. Goals

*   Trace requests across key microservices (e.g., `frontend-app`'s backend, `functions-service`, `atomic-scheduler`, `python-api-service`, `gpt-service`, etc.).
*   Capture timing information for critical operations and external calls within each service.
*   Correlate traces with logs using the X-Ray Trace ID, enhancing debuggability.
*   Provide clear guidance and tools for developers to easily instrument their services.
*   Minimize the performance overhead associated with tracing.
*   Visualize service maps and trace details in the AWS X-Ray console.

## 3. Core Components & Setup

### 3.1. AWS Distro for OpenTelemetry (ADOT) Collector

*   **Strategy:** Deploy the **ADOT Collector** as a sidecar container within each ECS Fargate task definition for services that will be instrumented.
*   **Reasoning:**
    *   **Flexibility:** ADOT can receive trace data in OpenTelemetry Protocol (OTLP) format, which is supported by modern OpenTelemetry SDKs across various languages.
    *   **Vendor Agnostic:** While we're targeting X-Ray, ADOT allows for potential future integration with other observability backends.
    *   **Extensibility:** Can be configured to handle metrics and logs in the future via the same collector.
*   **Configuration:**
    *   The ADOT Collector sidecar will be configured with an OTLP receiver (e.g., listening on `localhost:4317` for gRPC or `localhost:4318` for HTTP/protobuf) and an `awsxrayexporter`.
    *   ECS Task Definitions in the AWS CDK (`aws-stack.ts`) will be updated to include the ADOT Collector container, with appropriate CPU/memory allocation and environment variables for configuration (e.g., AWS region).
    *   Application containers will send OTLP trace data to this local ADOT Collector endpoint.
*   **CDK Implementation:** The `aws-stack.ts` will be enhanced to optionally (or by default for new services) include the ADOT Collector sidecar in Fargate service definitions. This includes defining the container, port mappings, and necessary configurations.

### 3.2. Application Instrumentation with OpenTelemetry SDKs

Services will be instrumented using language-specific OpenTelemetry SDKs, configured to export traces to the local ADOT Collector sidecar via OTLP.

*   **Node.js Services** (e.g., `functions-service`, `app_build_docker`'s BFF):
    *   **SDK:** `@opentelemetry/sdk-node`.
    *   **Auto-Instrumentation:** Leverage packages like `@opentelemetry/auto-instrumentations-node` to automatically instrument common modules (HTTP, Express.js, AWS SDK, gRPC, Knex.js, etc.).
    *   **Exporter:** Use `@opentelemetry/exporter-trace-otlp-grpc` or `@opentelemetry/exporter-trace-otlp-http` to send to the ADOT sidecar.
    *   **Initialization:** A centralized `tracing.js` (or similar) module within each service will configure the SDK, resource attributes (like `service.name`, `service.version`), register instrumentations, and set up the OTLP exporter. This module should be imported and initialized at the application's entry point.
*   **Python Services** (e.g., `python-api-service`, `live-meeting-worker`, `ingestion-pipeline-service`):
    *   **SDK:** `opentelemetry-sdk`.
    *   **Auto-Instrumentation:** Utilize packages like `opentelemetry-instrumentation` and specific instrumentors (e.g., `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-requests`, `opentelemetry-instrumentation-boto3`).
    *   **Exporter:** Use `opentelemetry-exporter-otlp-proto-grpc` or `opentelemetry-exporter-otlp-proto-http`.
    *   **Initialization:** A central `tracing.py` module for setup, similar to Node.js.
*   **Java/Quarkus Services** (e.g., `optaplanner_build_docker`):
    *   **Quarkus:** Natively supports OpenTelemetry. Configure via `application.properties` to enable tracing, set service name, and specify the OTLP exporter endpoint (e.g., `quarkus.opentelemetry.tracer.exporter.otlp.endpoint=http://localhost:4317`).
    *   **Plain Java:** Use the OpenTelemetry Java SDK with the OpenTelemetry Java Agent for auto-instrumentation or manual SDK configuration.

### 3.3. Trace Context Propagation

*   **Incoming Requests (from ALB):**
    *   The Application Load Balancer is already configured to generate an X-Ray trace ID and add the `X-Amzn-Trace-Id` header to requests.
    *   OpenTelemetry SDKs (with HTTP server instrumentation) will automatically recognize this header and use it to continue the trace, ensuring the trace context from ALB is linked.
*   **Inter-Service Communication (Synchronous):**
    *   **HTTP:** When an instrumented service makes an HTTP request to another service, the OpenTelemetry SDK's HTTP client instrumentation will automatically inject W3C Trace Context headers (`traceparent`, `tracestate`). The receiving service's SDK will then pick these up to continue the trace.
    *   **gRPC:** Similar automatic propagation occurs with gRPC instrumentation.
*   **Asynchronous Processes (e.g., Kafka):**
    *   **Kafka:** For messages published to Kafka that trigger processing in another service, trace context must be manually propagated.
        *   **Producer:** Before sending a message, extract the current trace context and inject it into the Kafka message headers (e.g., as `traceparent` and `tracestate`). OpenTelemetry provides utilities for this (e.g., `TextMapPropagator`).
        *   **Consumer:** Before processing a message, extract the trace context from the Kafka message headers and use it to start a new span that is linked to the producer's trace.
    *   This ensures that asynchronous workflows are correctly represented in the trace.

## 4. Instrumentation Strategy - What and How to Trace

*   **Automatic Instrumentation:** Prioritize using auto-instrumentation libraries for common frameworks and protocols (HTTP, gRPC, database clients, AWS SDK) as they cover many standard interaction points with minimal code changes.
*   **Custom Spans for Key Business Logic:**
    *   Manually create custom spans around significant operations, critical business logic functions, or sections of code that are important for performance analysis or debugging.
    *   Use descriptive names for these spans (e.g., `ProcessPayment`, `GenerateReport`, `CallOpenAI_SummarizeText`).
    *   **Example (Python):**
        ```python
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("my_custom_operation") as span:
            # ... your business logic ...
            span.set_attribute("app.feature.flag", "on")
            # ...
        ```
*   **Annotations and Metadata (Attributes):**
    *   Add relevant attributes (key-value pairs) to spans for richer context. In X-Ray, attributes indexed for filtering are called "Annotations," while non-indexed ones are "Metadata." OpenTelemetry uses the generic term "Attributes."
    *   **Good Attributes:** `userId`, `tenantId`, `entityId` (e.g., `orderId`, `taskId`), `operationName`, `requestId`, feature flags, input parameters (avoid PII or keep it very limited and anonymized).
    *   These attributes help in filtering traces and understanding the specifics of a request.
*   **Error Handling:**
    *   When exceptions occur, ensure they are recorded on the relevant span. Most auto-instrumentations handle this, but for custom spans, you might need to explicitly record the exception and set the span status to error.
    *   **Example (Python):**
        ```python
        try:
            # ... risky operation ...
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, "Operation failed"))
            raise
        ```

## 5. Linking Logs with Traces

*   **Inject Trace ID into Logs:** This is critical for correlating specific log messages with a distributed trace.
    *   Configure logging libraries in each service to automatically capture and include the current `trace_id` and `span_id` in every log entry.
    *   The `STRUCTURED_LOGGING_GUIDELINES.md` already recommends fields like `trace_id` and `span_id`.
    *   OpenTelemetry SDKs often provide integrations or utilities to make the current trace context available to logging libraries (e.g., via LogContext).
*   **CloudWatch Log Insights:** Use the `trace_id` in Log Insights queries to find all logs related to a specific trace, significantly speeding up debugging.
    *   Example query snippet: `| filter trace_id = "1-5f9babc0-1234567890abcdef12345678"`

## 6. Development Workflow & Best Practices

*   **Boilerplate/Examples:** Provide clear, copy-pasteable examples or template modules for initializing OpenTelemetry and the ADOT exporter in Node.js and Python services within the Atom Agent codebase. This will lower the barrier to entry for developers.
*   **Documentation:** Maintain concise documentation on how to add custom spans, set attributes, and best practices for instrumentation within the Atom Agent context.
*   **Local Development & Testing:**
    *   Developers should be able to run and test tracing locally.
    *   Configure the OTLP exporter in services to point to a local ADOT Collector instance (run via Docker). This local collector can be configured to:
        *   Export to the AWS X-Ray console (if AWS credentials are configured).
        *   Export to a local Jaeger or Zipkin instance (also run via Docker) for quick trace visualization without AWS dependency.
        *   Use a `loggingexporter` in the ADOT collector to print traces to the console for simple debugging.
*   **Sampling Strategy:**
    *   **Default:** AWS X-Ray samples the first request each second, and 5% of additional requests. This is a good starting point for production to manage costs and performance.
    *   **Development/Staging:** Consider a higher sampling rate (e.g., 100% or a fixed rate like 10-20%) in pre-production environments for more thorough testing. This can be configured in the OpenTelemetry SDKs or via the ADOT Collector.
    *   The ADOT Collector can also be configured for probabilistic or rate-limiting sampling.
*   **Performance Considerations:** While OpenTelemetry SDKs are designed to be efficient, excessive custom span creation or very high attribute cardinality can add overhead. Encourage mindful instrumentation.

## 7. Phased Rollout Plan

1.  **Phase 1: Foundational Setup & Core Services POC**
    *   **CDK:** Implement ADOT Collector sidecar integration into `aws-stack.ts` for ECS Fargate services.
    *   **Services:** Target `functions-service` (Node.js) and `python-api-service` (Python) as initial candidates.
    *   **Tasks:**
        *   Develop OpenTelemetry initialization boilerplate for Node.js and Python.
        *   Instrument these services: auto-instrument HTTP, AWS SDK calls. Add a few key custom spans.
        *   Ensure Trace IDs are logged.
        *   Deploy and verify traces in the AWS X-Ray console. Document findings.
2.  **Phase 2: Expand to Other Key Backend Services**
    *   **Services:** `atomic-scheduler`, `gpt-service`, other backend microservices.
    *   **Tasks:** Apply the instrumentation patterns established in Phase 1.
3.  **Phase 3: Asynchronous Flows & Deeper Instrumentation**
    *   **Focus:** Instrument Kafka message flows (producer and consumer side) for trace context propagation.
    *   **Tasks:** Add more granular custom spans in critical code paths identified through initial tracing or performance analysis.
4.  **Phase 4: Frontend Tracing (Future Consideration)**
    *   Explore instrumenting the React frontend application using OpenTelemetry JS for browser (`@opentelemetry/sdk-trace-web`) to capture frontend performance metrics and link them to backend traces for full end-to-end visibility.

## 8. Next Steps for Application Teams

1.  Familiarize yourselves with the OpenTelemetry documentation for your respective language.
2.  Look out for the boilerplate/example modules for OpenTelemetry initialization that will be provided.
3.  Start by instrumenting incoming/outgoing HTTP calls (often handled by auto-instrumentation) and then identify 2-3 critical business logic functions in your service to wrap with custom spans.
4.  Ensure your structured logs include `trace_id` and `span_id`.
5.  Test tracing locally by exporting to a console or a local Jaeger instance before deploying to AWS.

This strategy provides a comprehensive roadmap for implementing distributed tracing. Its successful execution will significantly enhance our ability to monitor, debug, and maintain the Atom Agent system.
---
All three supporting documents have been recreated. I will now proceed to create the main `OPERABILITY_GUIDE.md`.

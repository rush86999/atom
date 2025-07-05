# Structured Logging Guidelines for Atom Agent

## 1. Introduction

Effective logging is crucial for monitoring, debugging, and understanding the behavior of the Atom Agent application. Structured logging, as opposed to plain text logging, provides a consistent and machine-readable format for log entries. This allows for easier searching, filtering, and analysis of logs, especially when using centralized logging solutions like Grafana Loki (for Docker Compose context) or CloudWatch Logs (for AWS context).

These guidelines outline the recommended practices for implementing structured logging across all services and components of the Atom Agent. Adherence to these guidelines will improve our ability to diagnose issues, monitor system health, and gain operational insights.

## 2. Log Format

All log entries SHOULD be in **JSON format**. This is widely supported by logging libraries and log management systems.

## 3. Standard Log Fields

The following fields SHOULD be present in every log entry, where applicable:

*   **`timestamp`**: (String) ISO 8601 formatted timestamp with millisecond precision (e.g., `2023-10-28T14:35:12.123Z`). Most logging libraries can add this automatically.
*   **`level`**: (String) Log level (e.g., `INFO`, `WARN`, `ERROR`, `DEBUG`, `TRACE`). Use uppercase.
*   **`service_name`**: (String) Name of the microservice or component generating the log (e.g., `atomic-scheduler`, `gmail-integration`, `frontend-app`, `functions-service`). This should be configurable and ideally set via environment variables (e.g., `OTEL_SERVICE_NAME` or a custom one).
*   **`version`**: (String) Version of the service generating the log (e.g., `1.2.5`). This helps in correlating logs with specific code versions. Can be injected at build time or via environment variable.
*   **`message`**: (String) A clear, human-readable description of the log event.

## 4. Contextual Log Fields

In addition to the standard fields, include context-specific information relevant to the log event. This is where the real power of structured logging comes in.

### 4.1. Request/Operation Specific Fields:

For logs related to processing requests or specific operations:

*   **`trace_id`**: (String) The distributed tracing ID (e.g., from AWS X-Ray or OpenTelemetry). Essential for correlating logs across multiple services for a single request flow.
*   **`span_id`**: (String) The ID of the current span within a trace, if applicable.
*   **`request_id`**: (String) A unique identifier for a single incoming request to a service, if different from `trace_id` or if `trace_id` is not yet available (e.g., at the very edge).
*   **`user_id`**: (String) Identifier for the user associated with the request, if applicable. Be mindful of PII and anonymize or hash if necessary according to privacy policies.
*   **`operation_name`**: (String) A specific name for the operation, function, or use case being executed (e.g., `CreateCalendarEvent`, `ProcessIncomingEmail`, `UserLogin`, `HandleMeetingRequestCommand`).
*   **`duration_ms`**: (Number) Duration of the operation in milliseconds. Useful for performance monitoring.
*   **`http_method`**: (String) HTTP method if the log is related to an HTTP request (e.g., `GET`, `POST`).
*   **`http_path`**: (String) Path of the HTTP request.
*   **`http_status_code`**: (Number) HTTP status code for API responses.
*   **`status_code`**: (String/Number) An internal status code for non-HTTP operations (e.g., `SUCCESS`, `FAILURE_DEPENDENCY`, `INVALID_INPUT`).
*   **`success`**: (Boolean) `true` if the operation was successful, `false` otherwise.

### 4.2. Error Specific Fields:

For logs at `ERROR` or `WARN` levels:

*   **`error_code`**: (String) A specific application-defined error code (e.g., `AUTHN_001`, `DB_CONN_503`, `VALIDATION_002`).
*   **`error_message`**: (String) Detailed error message, often from an exception.
*   **`error_details`**: (Object/String) Any additional structured information about the error (e.g., invalid input parameters that caused the error).
*   **`exception_type`**: (String) The type or class name of the exception that occurred (e.g., `NullPointerException`, `ValueError`).
*   **`stack_trace`**: (String) Stack trace, if available. Be cautious about verbosity; consider logging only in `DEBUG` or specific error scenarios, or truncating long stack traces in production `INFO` logs. For production `ERROR` logs, a full stack trace is often valuable.

### 4.3. Application/Service Specific Fields:

Include any other fields that provide valuable context for a particular service or module. Examples:

*   `queue_name`: For services interacting with message queues.
*   `topic_name`: For Kafka consumers/producers.
*   `database_query_name`: A logical name for a database query (avoid logging actual query strings with parameters if sensitive).
*   `external_service_name`: When calling an external API (e.g., `OpenAI`, `GoogleCalendar`).
*   `feature_flag_name`: When a log is related to a feature flag.
*   `entity_id`: Identifier for a key business entity involved (e.g., `eventId`, `taskId`).

## 5. Log Levels

Use standard log levels appropriately:

*   **`TRACE`**: Extremely detailed diagnostic information, typically for deep debugging. Usually disabled in production.
*   **`DEBUG`**: Fine-grained information useful for debugging specific parts of the application flow. Can be enabled temporarily in production for troubleshooting.
*   **`INFO`**: General information about the application's operation, such as service startup/shutdown, request processing milestones, significant state changes. This is the default level for most production logging.
*   **`WARN`**: Potential issues or unexpected situations that do not necessarily stop the application but might lead to problems or indicate suboptimal behavior. These should be investigated.
*   **`ERROR`**: Critical errors that prevent normal operation for a specific request/operation or indicate a significant failure within a component. These usually require attention.
*   **`FATAL`**: (Use sparingly, if at all, as `ERROR` often suffices) Severe errors that might lead to application termination.

**Default Production Log Level:** `INFO`. `DEBUG` and `TRACE` should be configurable at runtime if possible.

## 6. Logging Libraries and Implementation

*   **Choose a suitable logging library** for your programming language/framework that supports structured logging (e.g., Winston or Pino for Node.js, structlog or standard `logging` with a JSON formatter for Python, Logback/Log4j2 with JSON layout for Java/Quarkus).
*   **Configure the library** to output logs in the defined JSON format with the standard fields.
*   **Centralize logging configuration** within each service.
*   **Avoid logging sensitive information** directly (e.g., passwords, API keys, raw PII unless explicitly required and secured). Use redaction, masking, or tokenization if necessary. Adhere to data privacy and security policies.
*   **Ensure logs are written to `stdout`/`stderr`** when running in containerized environments (like Docker/ECS). Log collection agents (like Promtail for Docker Compose, or CloudWatch Agent/FluentBit for ECS) will pick them up from there.
*   **Integrate with Tracing:** Ensure the `trace_id` and `span_id` (from X-Ray or OpenTelemetry) are automatically included in log entries. Most modern OpenTelemetry SDKs offer logging instrumentations or ways to access the current trace context.

## 7. Example Log Entries

**Successful INFO Log (HTTP Request):**
```json
{
  "timestamp": "2023-10-28T14:40:15.123Z",
  "level": "INFO",
  "service_name": "functions-service",
  "version": "1.3.0",
  "message": "Successfully processed create meeting request.",
  "trace_id": "1-5f9babc0-1234567890abcdef12345678",
  "span_id": "abcdef1234567890",
  "request_id": "req-789-abc",
  "user_id": "user-12345",
  "operation_name": "CreateMeeting",
  "duration_ms": 250,
  "http_method": "POST",
  "http_path": "/api/meetings",
  "http_status_code": 201,
  "success": true,
  "entity_id": "meeting-xyz789"
}
```

**ERROR Log (Dependency Failure):**
```json
{
  "timestamp": "2023-10-28T14:42:05.489Z",
  "level": "ERROR",
  "service_name": "gmail-integration-service",
  "version": "0.9.1",
  "message": "Failed to fetch new emails due to external API error.",
  "trace_id": "1-5f9babc1-abcdef1234567890abcdef12",
  "span_id": "fedcba0987654321",
  "request_id": "req-abc-123",
  "user_id": "user-67890",
  "operation_name": "FetchNewEmails",
  "duration_ms": 5500,
  "success": false,
  "status_code": "FAILURE_DEPENDENCY",
  "error_code": "GMAIL_API_TIMEOUT",
  "error_message": "Connection to Google Gmail API timed out after 5000ms",
  "exception_type": "TimeoutError",
  "external_service_name": "Google Gmail API",
  "stack_trace": "TimeoutError: Connection timed out...\n    at Timeout._onTimeout (/app/node_modules/google-auth-library/build/src/transporters.js:154:21)\n    ..."
}
```

## 8. Review and Iteration

These guidelines should be reviewed periodically and updated as the application evolves and new logging requirements emerge. Feedback from development and operations teams is crucial for maintaining effective logging practices. Consistency across services is key.
---
First recreated file is done. Now, I'll recreate `APPLICATION_METRICS_PROPOSAL.md`.

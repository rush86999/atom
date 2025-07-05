import logging
import os

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPTraceExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, get_aggregated_resources
from opentelemetry.semconv.resource import ResourceAttributes

# Auto-instrumentation
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor # Example, if using Boto3 SQS
# from opentelemetry.instrumentation.flask import FlaskInstrumentor # If using Flask
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Configure logger for OpenTelemetry diagnostics
# logging.basicConfig(level=logging.DEBUG) # Uncomment for OTel diagnostic logs
# otel_logger = logging.getLogger("opentelemetry")
# otel_logger.setLevel(logging.DEBUG)


# Service name and version can be set via environment variables
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "PythonAgentService")
SERVICE_VERSION = os.environ.get("OTEL_SERVICE_VERSION", "1.0.0")

# OTLP Exporter Endpoints (defaults to localhost for sidecar)
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = os.environ.get(
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4318/v1/traces"
)
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT = os.environ.get(
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://localhost:4318/v1/metrics"
)
OTEL_METRIC_EXPORT_INTERVAL = int(os.environ.get("OTEL_METRIC_EXPORT_INTERVAL", "10000"))


def initialize_otel():
    """Initializes OpenTelemetry Tracing and Metrics."""

    # --- Resource ---
    # Identifies the service emitting telemetry
    resource = get_aggregated_resources(
        [
            Resource.create(
                {
                    ResourceAttributes.SERVICE_NAME: SERVICE_NAME,
                    ResourceAttributes.SERVICE_VERSION: SERVICE_VERSION,
                }
            ),
            # Add other resource detectors if needed, e.g., for AWS ECS
            # from opentelemetry.sdk.extension.aws.resource.ecs import AwsEcsResourceDetector
            # AwsEcsResourceDetector(),
        ]
    )

    # --- Tracing ---
    tracer_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPTraceExporter(endpoint=OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ---
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=OTEL_EXPORTER_OTLP_METRICS_ENDPOINT),
        export_interval_millis=OTEL_METRIC_EXPORT_INTERVAL,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # --- Auto-instrumentation ---
    RequestsInstrumentor().instrument()  # Instrument HTTP requests
    Boto3SQSInstrumentor().instrument() # Instrument Boto3 SQS (example, ensure boto3 is used with SQS)
    # FlaskInstrumentor().instrument() # Uncomment if Flask is used by the agent

    # --- Logging Instrumentation ---
    # This will ensure that trace_id and span_id are automatically added to log records
    # when logging is done within the context of a span.
    # It works with Python's standard logging module.
    LoggingInstrumentor().instrument(set_logging_format=False) # Set to True to use OTel's default format
                                                              # False allows custom formatter to handle OTel fields

    print(f"OpenTelemetry initialized for service: {SERVICE_NAME}@{SERVICE_VERSION}")
    print(f"OTLP Trace Exporter configured for: {OTEL_EXPORTER_OTLP_TRACES_ENDPOINT}")
    print(f"OTLP Metric Exporter configured for: {OTEL_EXPORTER_OTLP_METRICS_ENDPOINT}")


def get_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    Configures and returns a logger that is OTel-aware and outputs JSON.
    This should be called *after* initialize_otel() and LoggingInstrumentor.instrument().
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicate logs if this is called multiple times
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create a handler that outputs to console
    console_handler = logging.StreamHandler()

    # Custom JSON Formatter
    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord):
            log_entry = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "service_name": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "message": record.getMessage(),
                "module": record.module,
                "funcName": record.funcName,
                "lineno": record.lineno,
            }
            if hasattr(record, 'otelSpanID'): # Added by LoggingInstrumentor
                log_entry['span_id'] = record.otelSpanID
            if hasattr(record, 'otelTraceID'): # Added by LoggingInstrumentor
                log_entry['trace_id'] = record.otelTraceID
            if hasattr(record, 'otelServiceName'): # Added by LoggingInstrumentor
                 # Could be useful if different from global SERVICE_NAME
                log_entry['otel_service_name'] = record.otelServiceName

            # Add exception info if present
            if record.exc_info:
                log_entry['exception_type'] = record.exc_info[0].__name__
                log_entry['exception_message'] = str(record.exc_info[1])
                # log_entry['stack_trace'] = self.formatException(record.exc_info) # Can be very verbose

            # Add any extra fields passed to the logger
            # Standard LogRecord attributes: asctime, created, exc_info, filename, funcName, levelname, levelno,
            # lineno, message, module, msecs, msg, name, pathname, process, processName, relativeCreated,
            # stack_info, thread, threadName
            # Custom extras can be passed like: logger.info("message", extra={"custom_key": "value"})
            # These are automatically merged by some formatters or need specific handling.
            # For simplicity, we'll rely on standard fields and OTel context for now.
            # If 'extra' dict is found on record, merge it.
            if hasattr(record, 'extra_props') and isinstance(record.extra_props, dict):
                log_entry.update(record.extra_props)

            return super().format(log_entry) # Use parent to convert dict to JSON string effectively
            # Correction: logging.Formatter is not JSON native. Need json.dumps.

    # Redefined JsonFormatter to correctly output JSON
    class JsonFormatterCorrected(logging.Formatter):
        def format(self, record: logging.LogRecord):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "service_name": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "message": record.getMessage(),
                "logger_name": record.name,
                "module": record.module,
                "funcName": record.funcName,
                "lineno": record.lineno,
            }
            # Add OTel context if available (these should be automatically injected by LoggingInstrumentor)
            if hasattr(record, "otelSpanID"):
                log_record["span_id"] = record.otelSpanID
            if hasattr(record, "otelTraceID"):
                log_record["trace_id"] = record.otelTraceID
            # if hasattr(record, "otelResource"): # This can be very verbose
            #    log_record["otel_resource"] = {k: v for k, v in record.otelResource.items()}


            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
                log_record["exception_type"] = record.exc_info[0].__name__
                log_record["exception_message"] = str(record.exc_info[1])


            # Merge any extra fields passed to logger.info("msg", extra={'key': 'val'})
            # Standard attributes to exclude from 'extra'
            standard_attrs = {
                'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
                'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'message', 'msg', 'name', 'pathname', 'process', 'processName',
                'relativeCreated', 'stack_info', 'thread', 'threadName',
                'otelSpanID', 'otelTraceID', 'otelResource' # OTel specific
            }
            extra_attrs = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}
            if extra_attrs:
                log_record.update(extra_attrs)

            import json
            return json.dumps(log_record)

    formatter = JsonFormatterCorrected(fmt='%(asctime)s %(levelname)s [%(name)s] [%(module)s.%(funcName)s:%(lineno)d] %(message)s',
                                     datefmt='%Y-%m-%dT%H:%M:%S.%sZ') # datefmt for timestamp field
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

# --- Exports for application use ---
# Call initialize_otel() once when your application starts.
# Example:
# if __name__ == "__main__":
#    initialize_otel()
#    main_logger = get_logger(__name__)
#    main_logger.info("Application starting with OTel.")
#    # ... rest of your application ...

# For manual tracing and metrics:
# tracer = trace.get_tracer(SERVICE_NAME, SERVICE_VERSION)
# meter = metrics.get_meter(SERVICE_NAME, SERVICE_VERSION)

# Example custom metrics (can be defined here or in the main app)
# Example: items_processed_counter = meter.create_counter(
#     "app_items_processed_total",
#     description="Counts items processed by the agent",
#     unit="1"
# )
```

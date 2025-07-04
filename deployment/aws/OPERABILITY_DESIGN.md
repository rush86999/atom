# AWS Operability Enhancement Design (Phase 2)

This document outlines the design for enhancing operability of the Atomic project deployed on AWS, focusing on centralized logging, advanced monitoring and dashboarding, granular alarming, and distributed tracing.

## 1. Centralized Logging Strategy

The goal is to ensure all application and service logs are centrally collected, easily searchable, and retained appropriately.

**1.1. CloudWatch Logs Configuration (CDK Enhancements)**

*   **Log Groups:** Each ECS Fargate service logs to a dedicated CloudWatch Log Group (e.g., `/aws/ecs/<CLUSTER_NAME>/<SERVICE_NAME>`).
*   **Log Retention (Implemented):**
    *   All ECS service log groups in `aws-stack.ts` are now configured with a default retention period (e.g., `logs.RetentionDays.ONE_MONTH`).
*   **Log Group Removal Policy (Implemented):**
    *   The `removalPolicy` for ECS service log groups in `aws-stack.ts` is now conditionally set based on the `DeploymentStage` CloudFormation parameter:
        *   `cdk.RemovalPolicy.RETAIN` for production (`prod` stage).
        *   `cdk.RemovalPolicy.DESTROY` for non-production stages (`dev`, `staging`).
*   **Application Log Formatting (Guidance):**
    *   **Recommendation:** Applications running within containers should be configured to output logs in a **structured JSON format**. This significantly enhances searchability and analysis in CloudWatch Log Insights and other tools.
    *   **Example JSON Structure:**
        ```json
        {
          "timestamp": "YYYY-MM-DDTHH:mm:ss.sssZ",
          "level": "INFO", // ERROR, DEBUG, WARN
          "service": "service-name",
          "correlationId": "unique-trace-id",
          "userId": "user-identifier",
          "requestId": "specific-request-id",
          "module": "component-name",
          "message": "Log message content.",
          "durationMs": 123, // Optional: for operations
          "exceptionType": "ExceptionName", // Optional: for errors
          "stackTrace": "...", // Optional: for errors
          "details": { /* Other contextual key-value pairs */ }
        }
        ```

**1.2. Log Analysis with CloudWatch Log Insights**

*   CloudWatch Log Insights will be the primary tool for ad-hoc log analysis and querying.
*   **Documentation & Example Queries:** A set of example Log Insights queries should be maintained (e.g., in the main AWS README or an operations runbook) to help developers and operators. Examples:
    *   **Find all errors for a specific service (assuming JSON logs with `level` and `service` fields):**
        ```logs
        fields @timestamp, @message, level, service, exceptionType, stackTrace
        | filter level = 'ERROR' and service = 'functions-service'
        | sort @timestamp desc
        | limit 100
        ```
    *   **Trace requests using a correlation ID (assuming JSON logs with `correlationId` field):**
        ```logs
        fields @timestamp, @message, service, level, correlationId
        | filter correlationId = 'abc-123-xyz-789' # Replace with actual ID
        | sort @timestamp asc
        ```
    *   Counting errors by type or analyzing request durations would require specific fields like `exceptionType` or `durationMs` to be present in the structured logs.

**1.3. OpenSearch Service Integration (Future Consideration)**

*   **Evaluation:** Integration with Amazon OpenSearch Service (for more advanced log analytics, dashboarding via OpenSearch Dashboards, and complex log-based alerting) was considered.
*   **Recommendation:** Defer implementation for the current phase. CloudWatch Logs + Log Insights, combined with structured application logging, should provide sufficient capabilities initially. Re-evaluate if more advanced needs arise.
*   **Future Outline (if pursued):** Involves provisioning an OpenSearch domain, streaming logs from CloudWatch via Kinesis Data Firehose, and setting up appropriate security.

## 2. Advanced Monitoring & Dashboarding Strategy

Building on basic CloudWatch metrics and alarms.

**2.1. Key Performance Indicators (KPIs) & Custom Metrics**

*   **ALB:** `HTTPCode_Target_ELB_5XX_Count`, `TargetResponseTime` (Avg, P90, P95), `RequestCount`, `UnHealthyHostCount`.
*   **ECS Services:** `CPUUtilization`, `MemoryUtilization`, `RunningTaskCount` vs `DesiredTaskCount`.
*   **RDS Database:** `CPUUtilization`, `FreeStorageSpace`, `FreeableMemory`, `DatabaseConnections`, `Read/WriteIOPS`, `Read/WriteLatency`.
*   **Application-Specific Custom Metrics (Guidance for Developers):**
    *   Services should publish custom metrics to CloudWatch (namespace: `AtomicApp`) for critical operations.
    *   Examples: Application error rates (e.g., `FailedOrderCreations`), request latencies (application-level), throughput (e.g., `SuccessfulLogins`), queue depths (if internal queues are used).
    *   Dimensions for custom metrics: `ServiceName`, `OperationName`, `Environment`.

**2.2. CloudWatch Dashboards (CDK Implementation Recommended)**

Two primary dashboards will be designed and implemented via CDK (`aws-cloudwatch.Dashboard`):

*   **Dashboard 1: System Health Overview**
    *   **Purpose:** At-a-glance view of overall system health.
    *   **Widgets:**
        *   ALB: Overall 5XX rate, P90 latency, unhealthy host summary.
        *   ECS Services: Summary for each key service (running/desired tasks, CPU/Mem utilization, error rate indicator from custom metrics).
        *   RDS: CPU, Free Storage, Freeable Memory, DB Connections.
        *   Key Alarms Status widget.
*   **Dashboard 2: Application Performance Deep Dive (e.g., for AppService)**
    *   **Purpose:** Detailed troubleshooting for a critical service.
    *   **Widgets:**
        *   ALB (specific target group): Request count, P50/P90/P99 latency, 5XX errors, healthy/unhealthy hosts.
        *   ECS (specific service): CPU & Memory graphs, running tasks graph.
        *   Custom Metrics (specific service): Key operation latencies, error rates, throughput.
        *   Dependency Metrics: Key metrics from downstream services it calls.
        *   Embedded Log Insights query widget for recent errors of the service.

## 3. Granular CloudWatch Alarms Strategy

Extending the basic alarms with more specific and application-aware alerts. All alarms will notify the existing SNS topic (`AlarmTopic`).

*   **ALB Alarms:**
    *   Per-Target Group High 5XX Error Rate: `HTTPCode_Target_5XX_Count` (Sum >= N in 5 min).
    *   Per-Target Group High Target Latency: `TargetResponseTime` (e.g., p90 > X seconds for Y minutes).
*   **ECS Service Alarms:**
    *   (Requires Custom Metrics) Application-Specific Error Rate Alarms: Based on custom metrics like `MyApp/FailedOperationCount` or `MyApp/ErrorRate`.
*   **RDS Instance Alarms:**
    *   `DatabaseConnections` approaching instance maximum (e.g., >80% of max for 15-30 minutes).

## 4. Distributed Tracing with AWS X-Ray (Evaluation & Phased Approach)

*   **Value:** X-Ray is highly beneficial for tracing requests across the microservices, aiding in debugging and performance analysis.
*   **Infrastructure Setup (CDK - Future Implementation or Phased):**
    *   Enable X-Ray tracing on the Application Load Balancer.
    *   Add IAM permissions (`xray:PutTraceSegments`, `xray:PutTelemetryRecords`) to the `ecsTaskRole`.
    *   Plan for adding the AWS X-Ray daemon (or ADOT Collector) as a sidecar container to ECS Fargate task definitions for services that will be instrumented.
*   **Application Instrumentation (Development Task - Guidance):**
    *   **Recommendation:** Key services (especially `FunctionsService`, `AppService`, and other backend services involved in request chains) should be instrumented using the AWS X-Ray SDK for their respective languages (Node.js, Python, Java/Quarkus).
    *   The SDK will be used to create segments, subsegments, propagate trace context, and add annotations/metadata.
*   **Phased Rollout:**
    *   Initial CDK changes can include ALB X-Ray enablement and IAM permissions.
    *   Full sidecar integration into task definitions can occur as application teams adopt X-Ray SDK instrumentation.

This design document provides a roadmap for significant operability improvements. Implementation will be iterative.

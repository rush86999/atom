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

**1.3. Log Analysis Tools**

*   **CloudWatch Log Insights:** The primary tool for ad-hoc log analysis and querying.
*   **OpenSearch Service:** Integration with Amazon OpenSearch Service was considered but has been deferred. The current logging strategy provides sufficient capabilities for the project's needs.

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

Two primary dashboards are planned. The first one has been implemented:

*   **Dashboard 1: System Health Overview (Implemented)**
    *   **Purpose:** Provides an at-a-glance view of the overall health of the entire system. Intended for quick checks and identifying major outages.
    *   **CDK Implementation:** Created as `<StackName>-SystemHealthOverview` in `aws-stack.ts`. A CfnOutput `SystemHealthDashboardUrl` provides direct access.
    *   **Key Widgets Included:**
        *   Status of critical alarms.
        *   ALB: Overall 5XX errors, P90 latency for the App target group.
        *   ALB: Unhealthy host counts for each key service target group.
        *   ECS Services (App, Functions, PostGraphile, Supertokens, Optaplanner): CPU and Memory utilization graphs.
        *   RDS: CPU utilization, free storage space, freeable memory, and database connections graphs.
*   **Dashboard 2: Application Performance Deep Dive (e.g., for AppService) (Future Implementation)**
    *   **Purpose:** Detailed troubleshooting for a critical service.
    *   **Widgets:**
        *   ALB (specific target group): Request count, P50/P90/P99 latency, 5XX errors, healthy/unhealthy hosts.
        *   ECS (specific service): CPU & Memory graphs, running tasks graph.
        *   Custom Metrics (specific service): Key operation latencies, error rates, throughput.
        *   Dependency Metrics: Key metrics from downstream services it calls.
        *   Embedded Log Insights query widget for recent errors of the service.

## 3. Granular CloudWatch Alarms Strategy (Now Implemented)

The following granular alarms, extending the basic set, have been implemented in `aws-stack.ts`. They all notify the existing SNS topic (`AlarmTopic`).

*   **ALB Alarms (Per Target Group):**
    *   **High Target 5XX Error Rate:** Monitors `HTTPCode_Target_5XX_Count` (Sum). Triggers if >= 3 errors in 5 minutes for each key service target group.
    *   **High Target Latency:** Monitors `TargetResponseTime` (P90). Triggers if latency > 1 second (or 2s for Optaplanner) for 15 minutes for each key service target group.
*   **ECS Service Alarms:**
    *   *(Placeholder for future)* Application-Specific Error Rate Alarms: To be implemented once services publish relevant custom metrics (e.g., `MyApp/FailedOperationCount` or `MyApp/ErrorRate`).
*   **RDS Instance Alarms:**
    *   **High Database Connections:** Monitors `DatabaseConnections` (Average). Triggers if > 150 connections for 15 minutes (initial threshold for `db.t3.small`, subject to tuning).

## 4. Distributed Tracing with AWS X-Ray (Evaluation & Phased Approach)

*   **Value:** X-Ray is highly beneficial for tracing requests across the microservices, aiding in debugging and performance analysis.
*   **Infrastructure Setup (CDK - Foundational Steps Implemented):**
    *   **ALB X-Ray Tracing Enabled (Implemented):** X-Ray tracing is now enabled on the Application Load Balancer in `aws-stack.ts`. The ALB will add trace ID headers to requests.
    *   **ECS Task Role Permissions for X-Ray (Implemented):** The `ecsTaskRole` in `aws-stack.ts` now includes `xray:PutTraceSegments` and `xray:PutTelemetryRecords` permissions, allowing ECS tasks (with the X-Ray SDK/daemon) to send trace data to AWS X-Ray.
    *   **X-Ray Daemon/ADOT Collector Sidecar (Future Implementation):** Planning for adding the AWS X-Ray daemon or ADOT Collector as a sidecar container to ECS Fargate task definitions for services that will be instrumented remains a future step, to be done when applications integrate the X-Ray SDK.
*   **Application Instrumentation (Development Task - Guidance):**
    *   **Recommendation:** Key services (especially `FunctionsService`, `AppService`, and other backend services involved in request chains) should be instrumented using the AWS X-Ray SDK for their respective languages (Node.js, Python, Java/Quarkus).
    *   The SDK will be used to create segments, subsegments, propagate trace context, and add annotations/metadata.
*   **Phased Rollout:**
    *   Initial CDK changes can include ALB X-Ray enablement and IAM permissions.
    *   Full sidecar integration into task definitions can occur as application teams adopt X-Ray SDK instrumentation.

This design document provides a roadmap for significant operability improvements. Implementation will be iterative.

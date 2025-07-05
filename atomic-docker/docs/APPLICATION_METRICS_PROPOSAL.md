# Application-Level Metrics Proposal for Atom Agent

## 1. Introduction

This document proposes a set of key application-level metrics for the Atom Agent. These metrics are intended to provide insights into the performance, reliability, and usage of critical system components, enabling effective monitoring, dashboarding (e.g., 'Application Performance Deep Dive' on CloudWatch), and alerting.

Metrics should generally be published to a consistent namespace in the monitoring system (e.g., `AtomicApp` or `AtomAgent` for CloudWatch, or using appropriate naming conventions for Prometheus). Common dimensions should include `ServiceName`, `OperationName`, `Environment`, and others as specified.

This proposal is a starting point and should be reviewed and refined by the development teams responsible for each service.

## 2. General API & Service Metrics

These metrics are broadly applicable to most backend services and should ideally be captured by common middleware or request handlers.

*   **`RequestLatencySeconds` (Histogram/Summary)**:
    *   Description: Time taken to process an incoming request, in seconds.
    *   Dimensions: `ServiceName`, `ApiEndpoint` (e.g., `/schedule-event`, `/task/create`), `HttpMethod` (e.g., `POST`, `GET`), `StatusCode` (e.g., `200`, `400`, `500`).
    *   Statistics: Average, P50, P90, P95, P99, Sum, Count.
    *   Importance: Core indicator of API performance and user experience.
*   **`RequestCount` (Counter)**:
    *   Description: Number of requests received.
    *   Dimensions: `ServiceName`, `ApiEndpoint`, `HttpMethod`, `StatusCode`.
    *   Importance: Measures traffic and is a basis for calculating error rates.
*   **`ErrorCount` (Counter)**:
    *   Description: Number of requests resulting in errors (e.g., HTTP 5xx, or specific application errors).
    *   Dimensions: `ServiceName`, `ApiEndpoint`, `HttpMethod`, `ErrorCode` (application-specific), `ErrorType` (e.g., `ApiClientError`, `ApiServerError`, `DependencyError`).
    *   Importance: Critical for understanding service reliability. (ErrorRate can be calculated: ErrorCount / RequestCount).
*   **`ActiveConnections` (Gauge)** (If applicable, e.g., for WebSocket services):
    *   Description: Number of currently active connections.
    *   Dimensions: `ServiceName`.
    *   Importance: Helps understand current load and capacity.

## 3. Task Management Metrics (Notion Backend)

Service: `atom-agent` or a dedicated `task-service`.

*   **`TaskOperationDurationSeconds` (Histogram/Summary)**:
    *   Description: Time taken for a task operation (create, query, update) with Notion.
    *   Dimensions: `OperationName` (e.g., `CreateTask`, `QueryTasks`, `UpdateTask`), `Success` (true/false).
    *   Importance: Monitors Notion integration performance for tasks.
*   **`TaskOperationCount` (Counter)**:
    *   Description: Number of task operations.
    *   Dimensions: `OperationName`, `Success` (true/false), `NotionApiError` (if applicable).
    *   Importance: Tracks usage and reliability of task features.
*   **`TaskNluProcessingDurationSeconds` (Histogram/Summary)** (From `atom-agent`):
    *   Description: Time taken for NLU processing of a task-related command.
    *   Dimensions: `CommandType` (e.g., `Create`, `QueryDate`, `UpdateStatus`).
    *   Importance: Performance of the NLU component for tasks.

## 4. Smart Scheduling & Calendar Management Metrics

Services: `atomic-scheduler` (OptaPlanner), `functions-service` (calendar backend), `atom-agent` (NLU).

*   **`SchedulingJobDurationSeconds` (Histogram/Summary)** (From `atomic-scheduler`):
    *   Description: Time for OptaPlanner to solve a scheduling problem.
    *   Dimensions: `HostId` (or tenant/user proxy), `ProblemSizeEvents` (bucketed count of events), `ProblemSizeUsers` (bucketed count of users).
    *   Importance: Core scheduler performance.
*   **`SchedulingCallbackDeliveryDurationSeconds` (Histogram/Summary)**:
    *   Description: Time from scheduler completion to callback acknowledgement.
    *   Dimensions: `CallbackUrlHost`.
    *   Importance: Ensures timely result delivery.
*   **`CalendarProviderApiDurationSeconds` (Histogram/Summary)** (From calendar backend):
    *   Description: Latency of operations against external calendar providers.
    *   Dimensions: `Provider` (e.g., `GoogleCalendar`, `MSTeamsCalendar`), `ApiCall` (e.g., `CreateEvent`, `ListEvents`), `Success` (true/false).
    *   Importance: Monitors external calendar dependencies.
*   **`CalendarNluProcessingDurationSeconds` (Histogram/Summary)** (From `atom-agent`):
    *   Description: Time for NLU processing of calendar commands.
    *   Dimensions: `CommandType` (e.g., `CreateEvent`, `QueryAvailability`).
    *   Importance: Performance of NLU for calendar.
*   **`AutopilotRunDurationSeconds` (Histogram/Summary)**:
    *   Description: Time for an Autopilot planning cycle.
    *   Dimensions: `UserId`.
    *   Importance: Performance of proactive scheduling.
*   **`AutopilotEventsProcessedCount` (Counter)**:
    *   Description: Number of events processed/updated by Autopilot.
    *   Dimensions: `UserId`, `ActionTaken` (e.g., `TemplateApplied`, `NoChange`, `Error`).
    *   Importance: Tracks Autopilot activity.

## 5. Integrated Note-Taking & Research Metrics

Services: `atom-agent`, `python-api-service` (or specific note/research service).

*   **`NoteCreationEndToEndDurationSeconds` (Histogram/Summary)**:
    *   Description: Total time for note creation (transcription, summary, save to Notion).
    *   Dimensions: `NoteType` (e.g., `Audio`, `Text`, `MeetingAudioNote`), `Source` (e.g., `AgentCommand`, `ManualUI`).
    *   Importance: User experience for note-taking.
*   **`AudioTranscriptionDurationSeconds` (Histogram/Summary)**:
    *   Description: Time for STT service (e.g., Deepgram) to transcribe audio.
    *   Dimensions: `AudioSource`, `AudioDurationMinutes` (bucketed).
    *   Importance: STT service performance.
*   **`AiSummaryGenerationDurationSeconds` (Histogram/Summary)**:
    *   Description: Time for LLM (e.g., OpenAI) to generate a summary.
    *   Dimensions: `ContentType` (e.g., `Transcript`, `ResearchLog`), `TextLength` (bucketed).
    *   Importance: LLM summarization performance.
*   **`SemanticSearchQueryDurationSeconds` (Histogram/Summary)** (Searchable Meeting Archive):
    *   Description: Latency for a semantic search query against LanceDB.
    *   Dimensions: `UserId` (if applicable).
    *   Importance: Meeting search feature performance.
*   **`IngestionPipelineRunDurationSeconds` (Histogram/Summary)** (LanceDB Ingestion):
    *   Description: Time for one run of the Notion to LanceDB ingestion pipeline.
    *   Dimensions: `ProcessingMode` (`full`, `incremental`), `PagesProcessedCount` (bucketed).
    *   Importance: Data pipeline performance for semantic search.
*   **`IngestionEmbeddingsGeneratedCount` (Counter)** (LanceDB Ingestion):
    *   Description: Number of text chunks embedded by the pipeline.
    *   Dimensions: `ProcessingMode`.
    *   Importance: Volume of work by ingestion pipeline.

## 6. Live Meeting Attendance Metrics (Experimental)

Service: `live-meeting-worker`, `atom-agent`.

*   **`LiveMeetingConnectionSetupDurationSeconds` (Histogram/Summary)**:
    *   Description: Time to establish connection and start "attending".
    *   Dimensions: `MeetingPlatform`.
    *   Importance: User experience for starting live attendance.
*   **`LiveMeetingWorkerErrorCount` (Counter)**:
    *   Description: Errors in `live-meeting-worker`.
    *   Dimensions: `ErrorType` (e.g., `AudioCaptureFailed`, `ProcessingFailed`).
    *   Importance: Reliability of live attendance.

## 7. External Integration Metrics (Gmail, Slack, MS Teams, etc.)

Services: `atom-agent`, or dedicated integration services.

*   **`ExternalApiCallDurationSeconds` (Histogram/Summary)** (Specific, critical calls):
    *   Description: Latency of key calls to third-party APIs.
    *   Dimensions: `IntegrationName` (e.g., `Gmail`, `Slack`), `ApiName` (e.g., `GmailSearchMessages`, `SlackPostMessage`), `Success` (true/false).
    *   Importance: Monitors key external dependencies.
*   **`ExternalApiCallCount` (Counter)**:
    *   Description: Number of calls to specific external APIs.
    *   Dimensions: `IntegrationName`, `ApiName`, `Success` (true/false), `ExternalErrorCode`.
    *   Importance: Tracks usage and reliability of integrations.
*   **`IntegrationNluQueryDurationSeconds` (Histogram/Summary)** (e.g., for Gmail/Slack search):
    *   Description: Time for NLU to process user queries for integrations.
    *   Dimensions: `IntegrationName`.
    *   Importance: Performance of AI-powered search for integrations.
*   **`IntegrationInfoExtractionDurationSeconds` (Histogram/Summary)** (e.g., for Gmail/Slack info extraction):
    *   Description: Time for LLM to extract info from messages/emails.
    *   Dimensions: `IntegrationName`, `InformationType`.
    *   Importance: Performance of AI-powered data extraction.

## 8. Message Queue Metrics (e.g., Kafka)

If used extensively between services.

*   **`QueueDepth` (Gauge)**:
    *   Description: Number of messages in a queue/topic.
    *   Dimensions: `QueueName` (or `KafkaTopic`).
    *   Importance: Indicates backlogs and potential processing delays.
*   **`MessageProcessingLagSeconds` (Histogram/Summary)**:
    *   Description: Time difference between message production and consumption.
    *   Dimensions: `QueueName`, `ConsumerGroup` (or `ConsumerService`).
    *   Importance: Consumer processing efficiency.
*   **`MessageProcessingDurationSeconds` (Histogram/Summary)**:
    *   Description: Time taken for a consumer to process a message.
    *   Dimensions: `QueueName`, `ConsumerGroup` (or `ConsumerService`).
    *   Importance: Consumer performance.
*   **`DeadLetterQueueSize` (Gauge)**:
    *   Description: Number of messages in the DLQ.
    *   Dimensions: `OriginalQueueName`.
    *   Importance: Indicates messages that failed processing repeatedly.

## 9. AI Model Interaction Metrics (e.g., OpenAI)

*   **`AiModelRequestDurationSeconds` (Histogram/Summary)**:
    *   Description: Latency of requests to AI models (e.g., OpenAI API calls).
    *   Dimensions: `ModelName` (e.g., `gpt-3.5-turbo`, `text-embedding-ada-002`), `OperationType` (e.g., `Completion`, `Embedding`).
    *   Importance: Performance of critical AI dependencies.
*   **`AiModelRequestTokenCount` (Histogram/Summary)**:
    *   Description: Number of tokens used per request (prompt and completion).
    *   Dimensions: `ModelName`, `OperationType`, `TokenType` (`Prompt`, `Completion`, `Total`).
    *   Importance: Cost monitoring and understanding model usage patterns.
*   **`AiModelErrorCount` (Counter)**:
    *   Description: Errors received from AI model APIs.
    *   Dimensions: `ModelName`, `OperationType`, `ApiErrorCode`.
    *   Importance: Reliability of AI model interactions.

## 10. Next Steps

1.  **Review and Refine:** Development teams should review this list for their respective services, adding, removing, or modifying metrics based on specific needs and technical feasibility.
2.  **Prioritize Implementation:** Identify a subset of these metrics for initial implementation, focusing on the most critical areas for performance and reliability monitoring.
3.  **Instrumentation Strategy:** Plan how and where each service will be instrumented to emit these metrics (e.g., using OpenTelemetry SDKs for custom metrics, or specific CloudWatch SDK calls).
4.  **Dashboard Design:** Once metrics are flowing, these will inform the design of the 'Application Performance Deep Dive' dashboard and other relevant monitoring views.

This proposal aims to establish a comprehensive and actionable set of application-level metrics to enhance the operability of the Atom Agent.
---
Second recreated file is done. Now, I'll recreate `XRAY_INTEGRATION_STRATEGY.md`.

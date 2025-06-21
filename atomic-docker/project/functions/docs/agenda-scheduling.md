# Agent Task Scheduling with Agenda

This document outlines the agent's capability to schedule tasks for future execution using the `Agenda` library.

## Overview

The system uses `Agenda`, a Node.js job scheduling library, to manage and execute tasks at specified times or on recurring schedules. This allows the agent to perform actions based on user requests for future or repeated execution.

## Key Components

1.  **`agendaService.ts` (`atomic-docker/project/functions/agendaService.ts`)**
    *   **Initialization**: Initializes and configures the `Agenda` instance.
    *   **MongoDB Connection**: Connects to a MongoDB database to persist job definitions. The MongoDB connection string is provided via the `MONGODB_URI` environment variable. Jobs are stored in a collection named `agentScheduledTasks` (or as configured in the service).
    *   **Job Definition**: Defines a primary job processor named `EXECUTE_AGENT_ACTION`.
    *   **Lifecycle Management**: Includes `startAgenda()` and `stopAgenda()` functions for managing Agenda's lifecycle, typically called during application startup and shutdown.
    *   **Event Logging**: Logs various Agenda events for monitoring and debugging.

2.  **`schedulingSkills.ts` (`atomic-docker/project/functions/atom-agent/skills/schedulingSkills.ts`)**
    *   **`scheduleTask` Skill**: Provides the core function for the agent to schedule tasks.
        *   It takes parameters like the task to execute (`originalUserIntent`, `entities`), scheduling details (`when`, `isRecurring`, `repeatInterval`), and user context.
        *   It interacts with `agendaService` to create new jobs in Agenda (using `agenda.schedule()` for one-time tasks and `agenda.every()` for recurring tasks).
    *   **`cancelTask` Skill**: Allows for cancellation of scheduled tasks based on provided criteria, using `agenda.cancel()`.

3.  **Job Processing (`EXECUTE_AGENT_ACTION`)**
    *   When a scheduled job is due, `Agenda` triggers the `EXECUTE_AGENT_ACTION` processor defined in `agendaService.ts`.
    *   This processor constructs a payload containing the original task details (intent, entities, user ID).
    *   It then makes an HTTP POST request to an internal agent endpoint (configured via `AGENT_INTERNAL_INVOKE_URL` environment variable, e.g., `http://localhost:7071/api/agentMessageHandler`).
    *   This simulates the agent receiving a direct command, allowing the scheduled task to be executed by the agent's standard command handling logic.

## Configuration

*   **`MONGODB_URI`**: Environment variable for the MongoDB connection string (e.g., `mongodb://localhost:27017/atomicAgentJobs`).
*   **`AGENT_INTERNAL_INVOKE_URL`**: Environment variable for the internal HTTP endpoint of the agent that the job processor calls (e.g., `http://localhost:7071/api/agentMessageHandler`). This endpoint should be configured to accept the job payload and trigger the appropriate agent logic.

## Workflow

1.  User requests the agent to schedule a task (e.g., "Schedule an email to John for tomorrow at 10 AM").
2.  The agent's NLU processes this, identifying the intent to schedule, the actual task to be done (e.g., send email), entities for that task, and the scheduling parameters.
3.  The agent's command handler (`handler.ts`) invokes the `scheduleTask` skill with these details.
4.  `scheduleTask` uses `agendaService` to create a new job in Agenda, persisting it to MongoDB.
5.  At the scheduled time, `Agenda` picks up the job.
6.  The `EXECUTE_AGENT_ACTION` job processor in `agendaService.ts` is triggered.
7.  The processor sends the task details via an internal HTTP POST to the agent's handler endpoint.
8.  The agent executes the original task (e.g., sends the email).

## Local Development

*   Ensure a MongoDB instance is running and accessible.
*   Set the `MONGODB_URI` and `AGENT_INTERNAL_INVOKE_URL` environment variables for the `functions` service.
*   The `agendaService.ts` needs to be started (e.g. `startAgenda()`) as part of the application's bootstrap process to begin processing jobs.

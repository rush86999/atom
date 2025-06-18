# Atomic Scheduler - REST API Integration Guide

This guide provides instructions for external applications to interact with the Atomic Scheduler's REST API to submit scheduling problems and receive solutions.

## Overview

The scheduler uses OptaPlanner to solve complex scheduling problems. The primary interaction involves:
1.  Sending a detailed scheduling problem (including timeslots, users with their availability/preferences, and events to be scheduled) to a dedicated endpoint.
2.  The scheduler processes this request asynchronously.
3.  Once a solution is found (or a timeout is reached), the scheduler POSTs the solution back to a callback URL provided by your application.

All data is exchanged in JSON format.

## Key REST Endpoints

The following are the primary endpoints for interacting with the scheduler. Replace `YOUR_SCHEDULER_HOST` with the actual host and port of the deployed scheduler application.

### 1. Submit Scheduling Job

*   **Endpoint**: `POST YOUR_SCHEDULER_HOST/timeTable/user/solve-day`
    *   An admin version also exists: `POST YOUR_SCHEDULER_HOST/timeTable/admin/solve-day` (requires "admin" role).
*   **Purpose**: Submits a new scheduling problem to the solver. This is an asynchronous operation.
*   **Request Body**: `PostTableRequestBody` (JSON object). See "Input Data Structure" below for details.
*   **Response**:
    *   Typically an HTTP `200 OK` or `202 Accepted` if the request is well-formed and accepted for processing.
    *   The actual scheduling solution is delivered later via the callback URL.

### 2. Receive Scheduling Solution (Callback)

*   **Endpoint**: This is a URL hosted by **your application** that you provide in the `callBackUrl` field of the `PostTableRequestBody`.
*   **Method**: `POST`
*   **Purpose**: The scheduler will POST the solution to this URL once processing is complete (or the specified delay has passed).
*   **Request Body**: `TimeTableSolutionDto` (JSON object). See "Output Data Structure" below for details.

### 3. Get Current TimeTable by ID (Optional Polling)

*   **Endpoint**: `GET YOUR_SCHEDULER_HOST/timeTable/user/byId/{singletonId}/{hostId}`
    *   Admin version: `GET YOUR_SCHEDULER_HOST/timeTable/admin/byId/{singletonId}/{hostId}`
*   **Purpose**: Retrieves the current state of the `TimeTable` solution for a given `singletonId` (from your original request) and `hostId`. This can be used for polling, though the callback is the primary mechanism for receiving the final solution.
*   **Response**: `TimeTable` domain object (JSON).

### 4. Stop an Ongoing Solve Process

*   **Endpoint**: `POST YOUR_SCHEDULER_HOST/timeTable/user/stopSolving`
    *   Admin version: `POST YOUR_SCHEDULER_HOST/timeTable/admin/stopSolving`
*   **Purpose**: Prematurely terminates an ongoing solving process.
*   **Request Body**: JSON object: `{ "singletonId": "your-solve-request-uuid" }`

### 5. Delete Scheduling Data for a Host

*   **Endpoint**: `DELETE YOUR_SCHEDULER_HOST/timeTable/user/delete/{hostId}`
    *   Admin version: `DELETE YOUR_SCHEDULER_HOST/timeTable/admin/delete/{hostId}`
*   **Purpose**: Deletes all scheduling data (timeslots, users, events, etc.) associated with the specified `hostId`. Note that submitting a new job to `/solve-day` also clears previous data for that `hostId`.

## Input Data Structure (`PostTableRequestBody`)

When calling the `/solve-day` endpoint, your application must send a JSON object with the following structure:

```json
{
  "singletonId": "string (UUID format)",    // Required: Your unique ID for this solve request
  "hostId": "string (UUID format)",         // Required: ID for the user/tenant
  "timeslots": [ /* Array of Timeslot objects */ ], // Required
  "userList": [ /* Array of User objects */ ],       // Required
  "eventParts": [ /* Array of EventPart objects */ ], // Required
  "fileKey": "string",                      // Required: Your tracking identifier
  "delay": "number (long integer, ms)",     // Required: Delay before callback
  "callBackUrl": "string (URL)"             // Required: Your endpoint for the solution
}
```

### Key Nested Object Summaries for Input:

*   **`Timeslot`**: Defines an available time interval.
    *   Fields: `hostId` (string UUID), `dayOfWeek` (string, e.g., "MONDAY"), `startTime` (string "HH:MM:SS"), `endTime` (string "HH:MM:SS"), `monthDay` (string "--MM-DD"), `date` (string "YYYY-MM-DD"). All are generally required.
*   **`User`**: Represents a user.
    *   Fields: `id` (string UUID), `hostId` (string UUID), `workTimes` (array of `WorkTime`), preferences (e.g., `maxWorkLoadPercent`). `id`, `hostId`, `workTimes` are required.
*   **`WorkTime`** (nested in `User`): Defines working periods.
    *   Fields: `userId` (string UUID), `hostId` (string UUID), `dayOfWeek`, `startTime`, `endTime`. All required.
*   **`EventPart`**: The core schedulable entity.
    *   Fields: `groupId` (string), `eventId` (string), `part` (int), `lastPart` (int), `startDate` (string ISO DateTime), `endDate` (string ISO DateTime), `userId` (string UUID), `hostId` (string UUID), `user` (full User object), `event` (full Event object), and various optional preference/deadline fields. `groupId`, `eventId`, `part`, `lastPart`, `startDate`, `endDate`, `userId`, `hostId`, `user`, `event` are required.
*   **`Event`** (nested in `EventPart`): The parent event.
    *   Fields: `id` (string), `userId` (string UUID), `hostId` (string UUID), `eventType` (string: "TASK", "ONE_ON_ONE_MEETING", "GROUP_MEETING", "EVENT"), `preferredTimeRanges` (array of `PreferredTimeRange` or null). All but `preferredTimeRanges` are required.
*   **`PreferredTimeRange`** (nested in `Event`):
    *   Fields: `eventId`, `userId`, `hostId`, `startTime`, `endTime`. `dayOfWeek` is optional.

**Data Formatting Notes for Input:**
*   **UUIDs**: Send as standard string representation (e.g., "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").
*   **Enums**: `DayOfWeek` and `EventType` as uppercase strings (e.g., "MONDAY", "TASK").
*   **Date/Time**:
    *   `LocalTime`: "HH:MM:SS"
    *   `LocalDate`: "YYYY-MM-DD"
    *   `LocalDateTime`: "YYYY-MM-DDTHH:MM:SS"
    *   `MonthDay`: String format like "--MM-DD" (e.g., "--03-25" for March 25th).

## Output Data Structure (`TimeTableSolutionDto` - via Callback)

Your `callBackUrl` will receive a POST request with a JSON body matching this structure:

```json
{
  "timeslotList": [ /* Array of TimeslotDto objects */ ],
  "userList": [ /* Array of UserDto objects */ ],
  "eventPartList": [ /* Array of EventPartDto objects */ ], // Main result
  "score": "string (e.g., 0hard/-10medium/-200soft) or null",
  "fileKey": "string or null",    // Your original fileKey
  "hostId": "string (UUID format) or null" // Your original hostId
}
```

### Key Nested Object Summaries for Output (DTOs):

*   **`EventPartDto`**: This is the most important part of the response. Each object in the `eventPartList` represents a scheduled (or unscheduled) event part.
    *   **`timeslot` (nested `TimeslotDto` or null)**: If the `EventPartDto` was successfully scheduled, this field will contain the details of the `TimeslotDto` it was assigned to. This is the primary piece of information you'll use.
    *   Other fields generally mirror the input `EventPart` but are often stringified or nullable. Contains nested `EventDto` and `UserDto`.
*   **`TimeslotDto`, `UserDto`, `EventDto`, `WorkTimeDto`, `PreferredTimeRangeDto`**: These are Data Transfer Objects that represent the state of your input data, potentially with some transformations (e.g., all date/time info as strings).

**Important Notes on Output DTOs:**
*   The DTOs used in the callback might have some differences from the internal domain models (e.g., some fields might be missing or have slightly different types). Specifically, `EventDto` currently misses `eventType`, `TimeslotDto` misses `date`, and `WorkTimeDto` misses `dayOfWeek`. Some ID fields in DTOs are typed as `UUID?` while their domain counterparts are `Long?` or `String`. Your callback handler should be prepared for the structure as defined by the DTOs in `TimeTableResource.kt`.

## Interaction Flow Summary

1.  **Client**: `POST /timeTable/user/solve-day` with `PostTableRequestBody` (containing problem data and `callBackUrl`).
2.  **Scheduler**: Acknowledges request, starts solving asynchronously.
3.  **Scheduler**: After configured `delay`, POSTs `TimeTableSolutionDto` (containing the schedule) to client's `callBackUrl`.
4.  **Client**: Receives and processes the solution from the callback.

## Authentication

*   Admin-specific endpoints (e.g., `/admin/solve-day`) are protected and require an "admin" role. The mechanism for acquiring/presenting this role is not detailed in this API guide but would typically involve standard authentication practices (e.g., JWT tokens).
*   The scheduler itself uses Basic Auth for some of its own outbound calls (e.g., to the `callBackUrl` if it were secured), but this is not directly relevant for an external application calling into the scheduler, unless the `callBackUrl` itself requires authentication from the scheduler.

This guide should help you get started with integrating your application with the Atomic Scheduler.

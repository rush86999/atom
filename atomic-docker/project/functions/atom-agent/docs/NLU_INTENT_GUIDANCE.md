# NLU Intent Guidance for New Productivity Skills

This document provides guidance for configuring the Natural Language Understanding (NLU) service (specifically the LLM used within `nluService.ts`) to recognize intents and extract entities for the new productivity skills: Smart Meeting Preparation, Automated Weekly Digest, and Intelligent Follow-up Suggester.

The NLU service is expected to parse user messages and return a JSON object with an `intent` and an `entities` object. The following sections detail the required additions to the NLU's system prompt or training data.

## 1. Smart Meeting Preparation

*   **Intent Name:** `PrepareForMeeting`
*   **Purpose:** Allows users to request a consolidated briefing for an upcoming meeting, including related documents, emails, and tasks.
*   **Entities to Extract:**
    *   `meeting_identifier` (Type: String, Optional): Captures the user's reference to a specific meeting (e.g., "Q3 Marketing Strategy," "call with Jane Doe," "my next meeting").
    *   `meeting_date_time` (Type: String, Optional): Captures temporal information about the meeting's timing (e.g., "tomorrow," "next Monday at 3pm," "on July 26th"). If not provided, the skill defaults to the soonest relevant meeting.
*   **Example User Utterances & Expected NLU JSON Output:**

    *   User: "Prepare me for my meeting about 'Q3 Marketing Strategy'."
        ```json
        {
          "intent": "PrepareForMeeting",
          "entities": {
            "meeting_identifier": "Q3 Marketing Strategy"
          }
        }
        ```
    *   User: "Get me ready for the call with Jane Doe tomorrow afternoon."
        ```json
        {
          "intent": "PrepareForMeeting",
          "entities": {
            "meeting_identifier": "call with Jane Doe",
            "meeting_date_time": "tomorrow afternoon"
          }
        }
        ```
    *   User: "What do I need to know for my next meeting?"
        ```json
        {
          "intent": "PrepareForMeeting",
          "entities": {
            "meeting_identifier": "my next meeting"
          }
        }
        ```
    *   User: "Prep for the budget review meeting."
        ```json
        {
          "intent": "PrepareForMeeting",
          "entities": {
            "meeting_identifier": "budget review"
          }
        }
        ```

## 2. Automated Weekly Digest

*   **Intent Name:** `GenerateWeeklyDigest`
*   **Purpose:** Provides users with a summary of their past week's accomplishments and a preview of critical items for the upcoming week.
*   **Entities to Extract:**
    *   `time_period` (Type: String, Optional): Specifies the period for the digest (e.g., "this week," "last week"). Defaults to "this week" if not provided.
*   **Example User Utterances & Expected NLU JSON Output:**

    *   User: "What's my weekly digest?"
        ```json
        {
          "intent": "GenerateWeeklyDigest",
          "entities": {}
        }
        ```
    *   User: "Generate my summary for this week."
        ```json
        {
          "intent": "GenerateWeeklyDigest",
          "entities": {
            "time_period": "this week"
          }
        }
        ```
    *   User: "Show me last week's digest."
        ```json
        {
          "intent": "GenerateWeeklyDigest",
          "entities": {
            "time_period": "last week"
          }
        }
        ```
    *   User: "Atom, give me the weekly digest."
        ```json
        {
          "intent": "GenerateWeeklyDigest",
          "entities": {}
        }
        ```

## 3. Intelligent Follow-up Suggester

*   **Intent Name:** `SuggestFollowUps`
*   **Purpose:** Analyzes meeting notes, transcripts, or project documents to identify and suggest potential action items, key decisions, and unresolved questions.
*   **Entities to Extract:**
    *   `context_identifier` (Type: String, Mandatory): The specific meeting, project, or document to analyze (e.g., "Project Phoenix Q1 review meeting," "the client onboarding project," "my last call with Sarah").
    *   `context_type` (Type: String, Optional, Enum-like: "meeting," "project," "document"): Helps the skill narrow down how to search for the context. If absent, the skill may infer or perform a broader search.
*   **Example User Utterances & Expected NLU JSON Output:**

    *   User: "What follow-ups should I consider for the 'Project Phoenix Q1 review' meeting?"
        ```json
        {
          "intent": "SuggestFollowUps",
          "entities": {
            "context_identifier": "Project Phoenix Q1 review",
            "context_type": "meeting"
          }
        }
        ```
    *   User: "Suggest next steps for my 'Client Onboarding' project."
        ```json
        {
          "intent": "SuggestFollowUps",
          "entities": {
            "context_identifier": "Client Onboarding",
            "context_type": "project"
          }
        }
        ```
    *   User: "Any follow-ups needed after my last meeting?"
        ```json
        {
          "intent": "SuggestFollowUps",
          "entities": {
            "context_identifier": "my last meeting",
            "context_type": "meeting"
          }
        }
        ```
        *(Note: The skill will need to resolve "my last meeting" to a specific event).*
    *   User: "Atom, analyze the 'Q1 Review transcript' for action items."
        ```json
        {
          "intent": "SuggestFollowUps",
          "entities": {
            "context_identifier": "Q1 Review transcript"
          }
        }
        ```

## General NLU Prompting Considerations:

*   The main `SYSTEM_PROMPT` in `nluService.ts` should be updated to include these new intents, their entity definitions, and a few illustrative examples for each, similar to how existing intents are defined.
*   The LLM should be instructed to strictly adhere to providing only a single valid JSON object in its response.
*   Emphasize that if an intent is not clearly matched, it should return `{"intent": null, "entities": {}}`.
*   The existing `NeedsClarification` and `ComplexTask` intents can still be used by the NLU if appropriate for these new commands when input is ambiguous or multi-step.

This guidance should be used to update the prompt for the LLM within `nluService.ts` to enable recognition of these new capabilities. Iterative testing and refinement of the main NLU prompt will be necessary to achieve high accuracy.

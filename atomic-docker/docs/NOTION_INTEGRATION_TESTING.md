# Notion Integration - Manual Testing Plan

This document outlines the steps for manually testing the Notion integration for the Atom Agent.

## 1. Setup

1.  **Create a Notion Integration:**
    *   Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations) and create a new integration.
    *   Copy the "Internal Integration Token".

2.  **Create Notion Databases:**
    *   Create two new databases in your Notion workspace:
        *   A "Tasks" database with the following properties:
            *   `Task Description` (Title)
            *   `Due Date` (Date)
            *   `Status` (Select: "To Do", "In Progress", "Done")
            *   `Priority` (Select: "High", "Medium", "Low")
            *   `List Name` (Text)
        *   A "Notes" database with the following properties:
            *   `Title` (Title)
            *   `Content` (Text)

3.  **Share Databases with Integration:**
    *   Share both the "Tasks" and "Notes" databases with the integration you created.

4.  **Configure Environment Variables:**
    *   In your `docker-compose.local.yaml` file, set the following environment variables for the `functions` and `python-agent` services:
        *   `NOTION_API_TOKEN`: The Internal Integration Token you copied.
        *   `ATOM_NOTION_TASKS_DATABASE_ID`: The ID of your "Tasks" database.
        *   `NOTION_NOTES_DATABASE_ID`: The ID of your "Notes" database.

5.  **Run the Application:**
    *   From the root of the `atomic-docker` directory, run the application using Docker Compose:
        ```bash
        docker-compose -f project/docker-compose.local.yaml up --build
        ```
    *   The application should be accessible at `http://localhost:3000`.

## 2. Testing Notion Skills via Chat

1.  **Navigate to the Chat Interface:**
    *   Go to the chat interface (e.g., `/Calendar/Chat/UserViewChat`).

2.  **Create a Task:**
    *   **Action:** Type `create task "Buy milk" due tomorrow with high priority` and send.
    *   **Expected Result:** Atom should confirm that the task was created. You should then be able to see this task in your "Tasks" database in Notion.

3.  **Query Tasks:**
    *   **Action:** Type `list my tasks` and send.
    *   **Expected Result:** Atom should respond with a list of tasks from your "Tasks" database.

4.  **Update a Task:**
    *   **Action:** Type `update task "Buy milk" to status "Done"` and send.
    *   **Expected Result:** Atom should confirm that the task was updated. The status of the "Buy milk" task in your "Tasks" database should be updated to "Done".

5.  **Create a Note:**
    *   **Action:** Type `create note "Meeting Summary" with content "This was a good meeting."` and send.
    *   **Expected Result:** Atom should confirm that the note was created. You should then be able to see this note in your "Notes" database in Notion.

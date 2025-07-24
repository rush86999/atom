# Web Research Integration - Manual Testing Plan

This document outlines the steps for manually testing the web research integration for the Atom Agent.

## 1. Setup

1.  **Run the Application:**
    *   From the root of the `atomic-docker` directory, run the application using Docker Compose:
        ```bash
        docker-compose -f project/docker-compose.local.yaml up --build
        ```
    *   The application should be accessible at `http://localhost:3000`.

## 2. Testing the Web Research Skill via Chat

1.  **Navigate to the Chat Interface:**
    *   Go to the chat interface (e.g., `/Calendar/Chat/UserViewChat`).

2.  **Perform a Search:**
    *   **Action:** Type `search web what is the capital of France` and send.
    *   **Expected Result:** Atom should respond with a list of search results, including titles, links, and snippets. The results should be relevant to the query.

3.  **Perform a Search with No Results:**
    *   **Action:** Type `search web ajsdflkajsdflkajsdflkajsdf` and send.
    *   **Expected Result:** Atom should respond with a message indicating that no results were found.

4.  **Perform a Search with an Empty Query:**
    *   **Action:** Type `search web` and send.
    *   **Expected Result:** Atom should respond with an error message indicating that a search query is required.

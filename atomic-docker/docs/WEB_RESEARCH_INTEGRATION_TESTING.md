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

## 3. Testing the Canva Integration via Chat

1.  **Connect Canva Account:**
    *   Before you can create a design, you need to connect your Canva account. To do this, you will need to manually trigger the OAuth flow.
    *   Navigate to `http://localhost:3000/v1/functions/mcp-service/canva-auth` in your browser. This should redirect you to Canva to authorize the application.
    *   After authorizing, you should be redirected back to the application.

2.  **Create a Canva Design:**
    *   **Action:** Type `create canva design with title "My Awesome Design"` and send.
    *   **Expected Result:** Atom should respond with a message indicating that the design was created successfully. The response should include the design ID and a link to the design on Canva.

3.  **Create a Canva Design with a Different Title:**
    *   **Action:** Type `create canva design with title "My Other Awesome Design"` and send.
    *   **Expected Result:** Atom should respond with a message indicating that the design was created successfully. The response should include the design ID and a link to the design on Canva.

4.  **Attempt to Create a Design without a Title:**
    *   **Action:** Type `create canva design with title ""` and send.
    *   **Expected Result:** Atom should respond with an error message indicating that a title is required.

5.  **Attempt to Create a Design without Connecting a Canva Account:**
    *   **Action:** Ensure you have not connected a Canva account. Type `create canva design with title "My Awesome Design"` and send.
    *   **Expected Result:** Atom should respond with an error message indicating that the user has not connected their Canva account.

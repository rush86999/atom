# Setting Up a Zoom SDK App for Atom

To enable Atom to interact with Zoom meetings using the Zoom SDK (for features like direct audio/video access via the `NewZoomSdkAgent`), you need to create an SDK App on the Zoom Marketplace and configure its credentials within Atom.

## Overview

A Zoom SDK App provides your application (Atom) with the necessary credentials (SDK Key and SDK Secret) to authenticate and interface with the Zoom platform at a deeper level than standard API calls might allow. This is often used for embedding Zoom functionality or accessing raw meeting data streams.

## Steps to Create a Zoom SDK App

The specific UI and naming on the Zoom Marketplace can change, but the general process is as follows:

1.  **Navigate to Zoom Marketplace:**
    *   Open your web browser and go to [https://marketplace.zoom.us/](https://marketplace.zoom.us/).

2.  **Sign In / Sign Up:**
    *   Sign in with your Zoom account credentials. If you don't have one, you might need to create a Zoom account. Ensure this account has the appropriate permissions if you are part of an organization (developer access might be needed).

3.  **Access Developer Dashboard:**
    *   Once logged in, look for a "Develop" dropdown or a "Manage Apps" / "Build App" section. Click on it.
    *   You might need to agree to developer terms and conditions if it's your first time.

4.  **Create a New App:**
    *   Find an option like "Create App" or "Build App."
    *   You will be presented with different app types. **Choose "SDK"** as the app type. (It might be listed as "Meeting SDK," "Video SDK," or a similar name. Select the one that corresponds to integrating Zoom client functionalities directly into an application).

5.  **App Configuration:**
    *   **App Name:** Provide a descriptive name for your app, e.g., "Atom Assistant SDK Integration."
    *   **App Type:** Ensure it's set to SDK.
    *   **Account Type:** You might be asked if it's an account-level app or a user-managed app. For server-side integrations like Atom's worker, an account-level app (if available and appropriate for your Zoom plan) or a user-managed app tied to a dedicated service account can be options. Consult Zoom's documentation for the best fit for an automated agent.
    *   **Company Name & Developer Contact:** Fill in your details.
    *   **Redirect URL / Whitelist URLs:** While often more critical for OAuth apps, provide any required URLs. For an SDK used by a backend service, these might be less emphasized or could be placeholders like `http://localhost`.
    *   **Scopes/Permissions:** Review available scopes. For accessing raw meeting data or controlling aspects of a meeting, the SDK app itself is usually granted broad permissions by virtue of being an SDK app. However, if specific scopes related to meeting control, recording, or user data access are listed, enable those that seem relevant to Atom's intended functionality (e.g., `meeting:read`, `meeting:write`, access to user information if needed for context). *The exact scopes needed will depend on the capabilities implemented in the `NewZoomSdkAgent`.*
    *   **Event Subscriptions (Optional):** If the agent needs to react to Zoom events (e.g., meeting started, participant joined), you might configure event subscriptions here or later. This is not typically required for initial SDK authentication.

6.  **View App Credentials:**
    *   After the app is created, navigate to its configuration page or a dedicated "App Credentials" tab.
    *   Here you will find the **SDK Key** and **SDK Secret**.
        *   These might also be labeled as "Client ID" and "Client Secret" respectively (especially for the SDK context).
    *   Copy these values securely. They are sensitive.

## Credential Storage and Configuration for Atom

The Zoom SDK Key and Secret need to be made available to the Atom system. Specifically, the `attend_live_meeting` API handler (which receives the initial request to join a meeting) is responsible for sourcing these credentials and passing them along to the `live_meeting_worker` via the Kafka message payload.

1.  **Set Environment Variables for the `attend_live_meeting` Handler:**
    *   The service running the `attend_live_meeting/handler.py` script (e.g., a Flask server, a Lambda function, or a container running this handler) must have the following environment variables set:
        *   `ZOOM_SDK_KEY`: Set this to the SDK Key (or Client ID) obtained from the Zoom Marketplace.
        *   `ZOOM_SDK_SECRET`: Set this to the SDK Secret (or Client Secret) obtained from the Zoom Marketplace.

    *   **Example (Conceptual for a Dockerized Handler Service):**
        If `attend_live_meeting/handler.py` runs in its own Docker container or as part of a general API backend service, you would set these environment variables for that service:
        ```yaml
        # Example for a hypothetical docker-compose.yml for the API handler service
        services:
          api_handler_service: # Or whatever service runs attend_live_meeting/handler.py
            image: your_api_handler_image
            environment:
              - ZOOM_SDK_KEY=your_sdk_key_here
              - ZOOM_SDK_SECRET=your_sdk_secret_here
              # ... other environment variables for the handler ...
        ```
    *   If deploying to a cloud environment (e.g., AWS Lambda for the handler), configure these environment variables directly in the Lambda function's settings.

2.  **How Credentials Reach the Worker:**
    *   The `attend_live_meeting/handler.py` script reads these environment variables (`ZOOM_SDK_KEY`, `ZOOM_SDK_SECRET`).
    *   When a request to join a Zoom meeting is processed, the handler includes these keys within the `apiKeys` dictionary of the message payload sent to Kafka.
    *   The `live_meeting_worker` (specifically `NewZoomSdkAgent`) then retrieves these keys from the Kafka message.

3.  **Restart Services:**
    *   After setting these environment variables for the `attend_live_meeting` handler service, ensure that service is restarted for the changes to take effect. The `live_meeting_worker` does not need a direct restart for credential changes if the handler is updated and restarted correctly.

## Important Considerations

*   **Security:** Treat your SDK Secret like a password. Do not embed it directly in your code or commit it to version control. Use environment variables or a secure secrets management system.
*   **Rate Limits:** Be aware of any API rate limits associated with your Zoom SDK App type and usage.
*   **Terms of Service:** Adhere to Zoom's Developer Terms of Service and API License and an Agreement when using the SDK.
*   **Scopes Updates:** If the `NewZoomSdkAgent` later requires additional permissions, you may need to revisit the Zoom Marketplace, update your SDK App's scope configuration, and potentially re-authorize or re-configure if necessary.

By following these steps, you will have successfully created a Zoom SDK App and configured Atom to use its credentials, paving the way for enhanced Zoom integration features.

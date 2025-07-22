# Atom Desktop: Local-First Deployment

This guide explains how to run the entire Atom stack on your local machine for development and offline use. This setup uses Docker Compose to orchestrate the necessary services.

## Prerequisites

*   [Docker](https://docs.docker.com/get-docker/) installed on your system.
*   [Docker Compose](https://docs.docker.com/compose/install/) installed on your system.
*   A `.env.local` file in the `atomic-docker/project` directory. You can copy the provided `.env.local-example` and fill in the required API keys.

## Running Atom Locally

1.  **Navigate to the project directory:**
    ```bash
    cd atomic-docker/project
    ```

2.  **Create your `.env.local` file:**
    Copy the `.env.local-example` to `.env.local` and fill in the required API keys and secrets.
    ```bash
    cp .env.local-example .env.local
    ```

3.  **Start the application:**
    ```bash
    docker-compose -f docker-compose.local.yaml --env-file .env.local up -d
    ```

4.  **Access the application:**
    Once all the services are running, you can access the Atom application by opening your web browser and navigating to `http://localhost:3000`.

## Services

This local-first deployment includes the following services:

*   **app:** The Next.js frontend.
*   **functions:** The main backend service.
*   **postgres:** PostgreSQL database.
*   **mongo:** MongoDB database.
*   **supertokens:** Authentication service.
*   **postgraphile:** GraphQL API for the PostgreSQL database.
*   **python-agent:** Python service for various tasks.
*   **live-meeting-worker:** Worker for live meeting features.
*   **ingestion-pipeline-service:** Service for ingesting data.
*   **optaplanner:** Scheduling service.
*   **handshake:** Service for meeting invites.
*   **oauth:** OAuth service.
*   **minio:** S3-compatible object storage.
*   **traefik:** Reverse proxy.

## Stopping the Application

To stop the application, run the following command:
```bash
docker-compose -f docker-compose.local.yaml down
```

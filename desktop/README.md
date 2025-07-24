# Atom Desktop

This guide explains how to run the Atom Desktop application.

## Prerequisites

*   [Docker](https://docs.docker.com/get-docker/) installed on your system.
*   [Docker Compose](https://docs.docker.com/compose/install/) installed on your system.
*   [Node.js](https://nodejs.org/en/) installed on your system.
*   [Rust](https://www.rust-lang.org/tools/install) installed on your system.

## Running Atom Desktop with a Local Backend

1.  **Start the backend services:**
    ```bash
    cd atomic-docker/project
    docker-compose -f docker-compose.local-only.yaml --env-file .env.local-only up -d
    ```

2.  **Run the desktop app:**
    ```bash
    cd ../../desktop/tauri
    npm install
    npm run tauri dev
    ```

## Running Atom Desktop with a Cloud-Hosted Backend

1.  **Run the desktop app:**
    ```bash
    cd desktop/tauri
    npm install
    npm run tauri dev
    ```

## Stopping the Local Backend

To stop the backend services, run the following command:
```bash
cd atomic-docker/project
docker-compose -f docker-compose.local-only.yaml down
```

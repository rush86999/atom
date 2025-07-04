# Running the Application with Docker Compose

This directory contains configurations for running the Atomic project and its associated observability stack (logging and monitoring) using Docker Compose.

## Prerequisites

*   Docker and Docker Compose installed.
*   The main application's `docker-compose.yml` (assumed to be in the parent directory or a known location).
*   Application Docker images built and available locally or in a registry accessible by Docker.

## Observability Stack

We provide configurations for a centralized logging and monitoring stack to enhance operability:

*   **Logging:** Uses Grafana Loki, Promtail, and Grafana. Detailed setup and usage in [LOGGING_GUIDE.md](./LOGGING_GUIDE.md).
*   **Monitoring:** Uses Prometheus, cAdvisor, Alertmanager, and Grafana. Detailed setup and usage in [MONITORING_GUIDE.md](./MONITORING_GUIDE.md).

## How to Run

You can run the application services along with the observability stack using multiple Docker Compose files.

1.  **Navigate to the root directory of the `docker-compose.yml` for the main application.**
    (The paths below assume your main `docker-compose.yml` is one level up from the `deployment/docker-compose/` directory, adjust as necessary if it's co-located or elsewhere).

2.  **To run the application with centralized logging:**
    ```bash
    docker-compose -f ../../docker-compose.yml -f deployment/docker-compose/docker-compose.logging.yml up -d
    ```
    *(Adjust path to `../../docker-compose.yml` based on your project structure relative to this README's location).*

3.  **To run the application with both centralized logging and monitoring:**
    ```bash
    docker-compose -f ../../docker-compose.yml \
                   -f deployment/docker-compose/docker-compose.logging.yml \
                   -f deployment/docker-compose/docker-compose.monitoring.yml \
                   up -d
    ```
    *(Adjust paths as needed).*

4.  **Accessing Grafana (for Logs and Metrics Dashboards):**
    *   Open your web browser and go to: `http://localhost:3000`
    *   Default credentials: `admin` / `admin`.
    *   **IMPORTANT:** Change the default Grafana admin credentials immediately after your first login, especially if Grafana is exposed on a public network.
    *   The Loki datasource for logs should be auto-configured.
    *   For Prometheus metrics, you may need to add it as a datasource in Grafana (URL: `http://prometheus:9090`). Refer to [MONITORING_GUIDE.md](./MONITORING_GUIDE.md).

5.  **Accessing Other UIs:**
    *   **Prometheus UI:** `http://localhost:9090`
    *   **Alertmanager UI:** `http://localhost:9093`
    *   **Loki API (not a UI):** `http://localhost:3100`

## Application Logging Best Practices

*   **Structured JSON Logging:** For best results with centralized logging, configure your application services to log messages in a structured JSON format to `stdout`/`stderr`.
*   See [LOGGING_GUIDE.md](./LOGGING_GUIDE.md) for more details.

## Stopping the Services

To stop all services (application and observability stack):
```bash
# If you started with logging only:
docker-compose -f ../../docker-compose.yml -f deployment/docker-compose/docker-compose.logging.yml down

# If you started with logging and monitoring:
docker-compose -f ../../docker-compose.yml \
               -f deployment/docker-compose/docker-compose.logging.yml \
               -f deployment/docker-compose/docker-compose.monitoring.yml \
               down
```

Refer to the specific guides for logging and monitoring for more detailed configuration and usage instructions.

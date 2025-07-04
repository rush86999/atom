# Centralized Logging for Docker Compose with Grafana Loki

This guide outlines how to set up and use a centralized logging solution for the Atomic project when deployed using Docker Compose. The recommended stack is Grafana Loki, which provides an efficient and relatively lightweight logging system.

## 1. Overview and Chosen Stack: Grafana Loki

For self-hosted Docker Compose deployments, especially on resource-constrained environments like a VPS, a lightweight yet powerful logging solution is essential. We recommend the **Grafana Loki stack**, which includes:

*   **Loki:** The log aggregation system. It indexes metadata (labels) about logs rather than the full log content, making it storage-efficient.
*   **Promtail:** The log collection agent. It discovers log sources (like Docker container logs), attaches labels, and ships them to Loki.
*   **Grafana:** Used for querying (with LogQL) and visualizing logs from Loki. It can also be used for metrics visualization if Prometheus is added.

**Rationale for Choosing Grafana Loki:**

*   **Resource Efficiency:** Significantly lower CPU, memory, and disk usage compared to alternatives like ELK/EFK.
*   **Ease of Setup & Operation:** Simpler to configure and manage within Docker Compose.
*   **Cost-Effectiveness:** Lower resource usage means lower hosting costs.
*   **Good Querying/Visualization:** LogQL is powerful for label-based queries and content filtering. Grafana provides excellent visualization.
*   **Integration with Grafana Ecosystem:** Fits well if Grafana is used for other observability tasks (e.g., metrics with Prometheus).

## 2. Docker Compose Integration

The logging stack components can be added to your existing `docker-compose.yml` or, for better modularity, placed in a separate `docker-compose.logging.yml` file. If using a separate file, you would typically run `docker-compose -f docker-compose.yml -f docker-compose.logging.yml up -d`.

**Example `docker-compose.logging.yml`:**

```yaml
version: '3.8'

volumes:
  loki_data: {}
  grafana_data: {}
  promtail_positions: {}

networks:
  logging_net: # Ensures logging components can communicate
    driver: bridge

services:
  loki:
    image: grafana/loki:2.9.2 # Or latest stable
    container_name: loki
    ports:
      - "3100:3100" # Loki API
    volumes:
      - loki_data:/loki
      # Optional: Mount a custom loki-config.yml if needed
      # - ./config/loki-config.yml:/etc/loki/config.yml
    command: -config.file=/etc/loki/config.yml # Uses default config path
    networks:
      - logging_net
    restart: unless-stopped

  promtail:
    image: grafana/promtail:2.9.2 # Or latest stable
    container_name: promtail
    volumes:
      # Mount Docker socket and container logs directory to allow Promtail to discover and read them
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - promtail_positions:/var/promtail/positions # For persisting log read positions
      - ./config/promtail-config.yml:/etc/promtail/config.yml # Crucial Promtail configuration
    command: -config.file=/etc/promtail/config.yml
    networks: # Needs to reach Loki
      - logging_net
    depends_on:
      - loki
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.2.0 # Or latest stable
    container_name: grafana
    ports:
      - "3000:3000" # Grafana UI
    volumes:
      - grafana_data:/var/lib/grafana
      # Optional: For provisioning datasources/dashboards automatically
      # - ./config/grafana/provisioning/:/etc/grafana/provisioning/
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin # IMPORTANT: Change this for any non-local setup!
      # Auto-configure Loki datasource (example)
      - GF_DATASOURCES_DEFAULT_NAME=Loki
      - GF_DATASOURCES_DEFAULT_TYPE=loki
      - GF_DATASOURCES_DEFAULT_URL=http://loki:3100 # Refers to Loki service name
      - GF_DATASOURCES_DEFAULT_ACCESS=proxy
      - GF_DATASOURCES_DEFAULT_IS_DEFAULT=true
    networks:
      - logging_net
    depends_on:
      - loki
    restart: unless-stopped
```

**Required Configuration Files:**

You'll need a `config` directory alongside your `docker-compose.logging.yml`. It's recommended to also include a basic `loki-config.yml` if you want to control retention or other specific Loki settings beyond defaults.

```
deployment/docker-compose/
├── config/
│   ├── loki-config.yml
│   └── promtail-config.yml
└── docker-compose.logging.yml
```

**Example `config/loki-config.yml` (Basic for Filesystem Storage & Retention):**

```yaml
auth_enabled: false # Default, can be changed for production

server:
  http_listen_port: 3100
  grpc_listen_port: 9096 # Loki 2.0+ uses gRPC for some communications

common:
  path_prefix: /loki # Data directory within the container volume
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1 # For single node setup
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper # Recommended for single node
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

# Configures how Loki chunks are stored and retention policies
ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  # Controls how long chunks are kept in memory before flushing
  chunk_idle_period: 1h       # Any chunk not receiving new logs in 1 hour will be flushed
  chunk_target_size: 1048576  # 1MB target size
  max_chunk_age: 1h           # Chunks are flushed if they reach this age, regardless of size
  chunk_retain_period: 1m     # How long to keep chunks in memory after they're flushed (for potential replay)

# Configures retention and compaction
compactor:
  working_directory: /loki/compactor # Must be a directory Loki can write to
  shared_store: filesystem
  compaction_interval: 10m # How often to run compaction
  retention_enabled: true    # Enable retention
  retention_delete_delay: 2h # How long after a chunk is marked for deletion until it's actually deleted
  retention_delete_worker_count: 150

table_manager:
  retention_deletes_enabled: true
  retention_period: 720h # 30 days (30d * 24h/d = 720h)
```
**Note:** This `loki-config.yml` is a starting point. You would mount it into the Loki service in `docker-compose.logging.yml` like so:
```yaml
# In loki service definition:
# volumes:
#   - loki_data:/loki
#   - ./config/loki-config.yml:/etc/loki/config.yml # Mount the config
```


**Example `config/promtail-config.yml` (Basic):**

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/promtail/positions/positions.yml # Path inside Promtail container

clients:
  - url: http://loki:3100/loki/api/v1/push # Address of the Loki service

scrape_configs:
  - job_name: docker_services
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
        # Optionally, filter which containers Promtail scrapes:
        # filters:
        #   - name: label
        #     values: ["logging=true"] # Only scrape containers with this Docker label
    relabel_configs:
      # Add the 'compose_service' label from Docker Compose service name
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: 'compose_service'
      # Add the 'container_name' label (often includes project prefix)
      - source_labels: ['__meta_docker_container_name']
        regex: '/?(.*)' # Strip leading slash
        target_label: 'container_name'
      # Keep the original filename (log source) as a label
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: 'logstream'
      - source_labels: ['__meta_docker_container_id']
        target_label: 'container_id'
```

**Application Service Configuration (in your main `docker-compose.yml`):**

*   **Log to `stdout`/`stderr`:** Ensure your application services are configured to log to standard output and standard error. This is Docker best practice.
*   **Docker Logging Driver:** The default `json-file` driver is usually sufficient, as Promtail can access these files. No specific driver change is typically needed for Promtail's Docker service discovery.
*   **Add Docker Labels (Recommended):** Add descriptive labels to your application services in `docker-compose.yml` for better filtering in Loki/Grafana. Example:
    ```yaml
    services:
      my-app-service:
        image: myapp:latest
        labels:
          - "app.name=atomic"
          - "app.component=backend" # Or 'frontend', 'database-proxy', etc.
          # - "logging=true" # If using filters in promtail_sd_config
    ```
    Promtail can then use these labels via `__meta_docker_container_label_app_name`, etc., in `relabel_configs`.

## 3. Log Formatting, Parsing, and Retention

*   **Application Log Formatting (Crucial):**
    *   **Use Structured JSON:** Applications should log in JSON format. This allows Grafana to display logs nicely and enables filtering on JSON fields in LogQL.
    *   Include fields like `timestamp`, `level` (INFO, ERROR, etc.), `service_name` (can also be a label), `correlation_id`, and a clear `message`.
*   **Promtail Parsing:**
    *   Promtail primarily focuses on attaching labels based on metadata.
    *   It *can* parse log lines (e.g., JSON or regex via `pipeline_stages`) to extract additional labels, but this should be used judiciously. Avoid creating labels with very high cardinality (e.g., user IDs, trace IDs) as it impacts Loki performance. Filter on these within LogQL instead.
*   **Loki Indexing:** Loki indexes the *labels*. Log content is compressed and stored.
*   **Log Retention:**
    *   **Loki:** Configure retention in a custom `loki-config.yml` (mounted into the Loki container). This involves settings under `table_manager` and ensuring the `compactor` is enabled. Example for 30 days:
        ```yaml
        # Inside loki-config.yml
        table_manager:
          retention_deletes_enabled: true
          retention_period: 720h # 30 days
        compactor:
          working_directory: /loki/compactor # Ensure this path is writable in the volume
          shared_store: filesystem
          compaction_interval: 10m
          retention_enabled: true
        ```
    *   **Docker Host:** Configure Docker daemon log rotation (e.g., in `/etc/docker/daemon.json`) for container logs as a safety net:
        ```json
        {
          "log-driver": "json-file",
          "log-opts": {
            "max-size": "10m",
            "max-file": "3"
          }
        }
        ```
    *   Monitor disk space on the host for the `loki_data` volume.

## 4. Basic Usage: Accessing Logs & Example Queries

1.  **Access Grafana:** Navigate to `http://<your_vps_ip_or_domain>:3000`. Log in (default: `admin`/`admin` - **CHANGE THIS!**).
2.  **Explore View:** Go to "Explore" (compass icon).
3.  **Select Datasource:** Choose "Loki" (should be auto-provisioned if using the environment variables in `docker-compose.logging.yml`).
4.  **Query Logs:**
    *   Use the "Log browser" to select labels like `compose_service` or `container_name`.
    *   Write LogQL queries:
        *   Logs for a service: `{compose_service="my-app-service"}`
        *   Error logs for a service (assuming JSON field `level`): `{compose_service="my-app-service"} |= "\"level\":\"ERROR\""`
        *   Error logs (using JSON parser): `{compose_service="my-app-service"} | json | level="ERROR"`
        *   Logs containing specific text: `{compose_service="my-app-service"} |= "keyword"`
        *   Case-insensitive regex search: `{compose_service="my-app-service"} |~ "(?i)keyword"`

Remember to consult the official Grafana Loki and Promtail documentation for more advanced configurations and query capabilities.

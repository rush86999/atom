# Monitoring & Alerting for Docker Compose with Prometheus

This guide outlines how to set up and use a monitoring and alerting solution for the Atomic project when deployed using Docker Compose. The recommended stack is based on Prometheus.

## 1. Overview and Chosen Stack: Prometheus Ecosystem

For robust monitoring of a self-hosted Docker Compose deployment, the **Prometheus ecosystem** is recommended. This includes:

*   **Prometheus:** A time-series database for collecting and storing metrics, with a powerful query language (PromQL).
*   **cAdvisor (Container Advisor):** An agent that discovers and exports resource usage metrics from running Docker containers.
*   **node_exporter (Optional but Recommended):** An exporter for collecting hardware and OS metrics from the host machine (VPS).
*   **Alertmanager:** Handles alerts defined in Prometheus, managing deduplication, grouping, silencing, and routing to notification channels.
*   **Grafana:** For visualizing metrics in dashboards (this guide assumes Grafana is also used for Loki log visualization, providing a unified interface).

**Rationale:**

*   **Comprehensive Monitoring:** Provides insights into both container-level and (optionally) host-level performance.
*   **Industry Standard:** Widely adopted, especially for containerized environments.
*   **Powerful Querying & Alerting:** PromQL and Alertmanager offer flexible and robust capabilities.
*   **Grafana Integration:** Seamlessly integrates with Grafana for rich dashboarding alongside logs.
*   **Extensible:** Can be easily extended to include custom application metrics.

## 2. Docker Compose Integration

The monitoring components can be defined in a separate `docker-compose.monitoring.yml` file, used alongside your main application `docker-compose.yml` and `docker-compose.logging.yml`.

**Example `docker-compose.monitoring.yml`:**

```yaml
version: '3.8'

volumes:
  prometheus_data: {}
  alertmanager_data: {}
  # grafana_data is typically defined in docker-compose.logging.yml

networks:
  # Ensure this network allows Prometheus to scrape other services (apps, cadvisor, node_exporter)
  # and allows Grafana to reach Prometheus.
  # This might be your main application network or a shared observability network.
  app_net:
    external: true # If defined in your main docker-compose.yml
    # driver: bridge # Or define it here

services:
  prometheus:
    image: prom/prometheus:v2.47.2
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./config/prometheus/rules/:/etc/prometheus/rules/
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d' # Example: 30-day retention
    # deploy: # Optional: Resource limits
    #   resources:
    #     limits:
    #       cpus: '1.0'
    #       memory: '1G'
    networks:
      - app_net
    restart: unless-stopped
    depends_on:
      - cadvisor
      - alertmanager # Optional, but good for Prometheus to know its Alertmanager

  alertmanager:
    image: prom/alertmanager:v0.26.0
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./config/alertmanager/alertmanager.yml:/etc/alertmanager/config.yml
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/config.yml'
      - '--storage.path=/alertmanager'
    # deploy: # Optional: Resource limits
    #   resources:
    #     limits:
    #       cpus: '0.5'
    #       memory: '256M'
    networks:
      - app_net
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    container_name: cadvisor
    # UI is on 8080, usually not exposed if Prometheus scrapes it.
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      # For cgroup v2 systems:
      # - /sys/fs/cgroup:/sys/fs/cgroup:ro
    privileged: true # Often needed for full access
    devices:
      - /dev/kmsg:/dev/kmsg # Optional
    # deploy: # Optional: Resource limits
    #   resources:
    #     limits:
    #       cpus: '0.5'
    #       memory: '512M'
    networks:
      - app_net
    restart: unless-stopped

  # node_exporter (Optional):
  # node_exporter:
  #   image: prom/node-exporter:v1.6.1
  #   container_name: node_exporter
  #   ports: ["9100:9100"]
  #   volumes:
  #     - /proc:/host/proc:ro
  #     - /sys:/host/sys:ro
  #     - /:/rootfs:ro
  #   command:
  #     - '--path.procfs=/host/proc'
  #     - '--path.sysfs=/host/sys'
  #     - '--path.rootfs=/rootfs'
  #     - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc|rootfs/var/lib/docker/containers|rootfs/var/lib/docker/overlay2|rootfs/run/docker/netns|rootfs/var/lib/docker/aufs)($$|/)'
  #   pid: host
  #   networks:
  #     - app_net
  #   restart: unless-stopped
```

**Required Configuration File Structure (Example):**
```
deployment/docker-compose/
├── config/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── rules/
│   │       ├── container_alerts.rules.yml
│   │       └── host_alerts.rules.yml # If using node_exporter
│   ├── alertmanager/
│   │   └── alertmanager.yml
│   # ... (loki, promtail, grafana configs from LOGGING_GUIDE.md) ...
├── docker-compose.logging.yml
├── docker-compose.monitoring.yml
└── (your main docker-compose.yml)
```

**Example `config/prometheus/prometheus.yml`:**
```yaml
global:
  scrape_interval: 30s # How frequently to scrape targets
  evaluation_interval: 30s # How frequently to evaluate rules

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080'] # Service name from docker-compose

  # - job_name: 'node_exporter' # Uncomment if using node_exporter
  #   static_configs:
  #     - targets: ['node_exporter:9100']

  - job_name: 'alertmanager'
    static_configs:
      - targets: ['alertmanager:9093']

  # Add scrape configs for your application services if they expose /metrics
  # - job_name: 'my-app-service'
  #   static_configs:
  #     - targets: ['my-app-service-container:port'] # Adjust target

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - "/etc/prometheus/rules/*.rules.yml"
```

**Example `config/alertmanager/alertmanager.yml` (Basic):**
```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'default-receiver'
  group_by: ['alertname', 'compose_service', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 1h

receivers:
  - name: 'default-receiver'
    # Replace with your desired notification methods (email, Slack, etc.)
    # Example: Log to stdout via a webhook to a simple logger or a testing endpoint
    webhook_configs:
      - url: 'http://host.docker.internal:5001/' # Example: dummy logger, replace
        send_resolved: true
  # - name: 'email-alerts'
  #   email_configs:
  #   - to: 'alert-recipient@example.com'
  #     from: 'alertmanager@yourdomain.com'
  #     smarthost: 'smtp.yourprovider.com:587'
  #     auth_username: 'smtp_user'
  #     auth_password: 'smtp_password'
```

## 3. Key Metrics, Dashboards, and Alerts

### Key Metrics to Monitor:

*   **From `cAdvisor` (Per Container):**
    *   CPU Usage: `rate(container_cpu_usage_seconds_total[1m])`
    *   Memory Usage: `container_memory_working_set_bytes`
    *   Memory Usage (% of limit): `(container_memory_working_set_bytes / container_spec_memory_limit_bytes) * 100` (if limits are set)
    *   Network I/O: `rate(container_network_receive_bytes_total[1m])`, `rate(container_network_transmit_bytes_total[1m])`
    *   Restarts: `container_restarts_total` (use `increase()` or `changes()` to detect recent restarts)
*   **From `node_exporter` (Host Metrics - if used):**
    *   Host CPU, Memory, Disk Space (`node_filesystem_avail_bytes`), Network traffic, System Load.
*   **From Prometheus/Alertmanager:** `up` (scrape health), alert states.

### Dashboarding in Grafana:

*   **"Docker Host & Container Overview" Dashboard:**
    *   **Adding Prometheus Datasource:** If Grafana was set up with the logging stack, you'll need to add Prometheus as a new datasource. Go to Grafana UI -> Configuration (gear icon) -> Data Sources -> Add data source. Select "Prometheus". Set the HTTP URL to `http://prometheus:9090` (using the service name from Docker Compose). Click "Save & Test".
    *   **Import Community Dashboards:** Start by importing pre-built dashboards from Grafana Labs Dashboards (grafana.com/grafana/dashboards/). Search for "Docker cAdvisor", "Node Exporter Full", or "Prometheus". Common IDs include `893` (Docker and System Monitoring) or `193` (Node Exporter Full).
    *   **Customize:** Adapt imported dashboards or build your own to show:
        *   Host resource usage (CPU, Mem, Disk, Network from node_exporter).
        *   Container counts, top N containers by CPU/Memory.
        *   Per-service graphs for CPU, Memory, Network I/O from cAdvisor.
        *   Container restart counts.

### Basic Alerting Rules (Example `config/prometheus/rules/container_alerts.rules.yml`):

```yaml
groups:
- name: container_resource_alerts
  rules:
  - alert: ContainerCPUHigh
    expr: (sum(rate(container_cpu_usage_seconds_total{image!=""}[5m])) by (compose_service, name) / sum(container_spec_cpu_quota{image!=""}/container_spec_cpu_period{image!=""}) by (compose_service, name) * 100) > 85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Container CPU high on {{ $labels.compose_service }}/{{ $labels.name }}"
      description: "{{ $labels.compose_service }} container {{ $labels.name }} CPU is at {{ $value | printf \"%.2f\" }}% for 5m."

  - alert: ContainerMemoryHigh
    expr: (container_memory_working_set_bytes{image!=""} / container_spec_memory_limit_bytes{image!=""} * 100) > 85
    # Assumes memory limits are set. If not, alert on absolute usage:
    # expr: container_memory_working_set_bytes{image!="", name=~".+"} > (1.5*1024*1024*1024) # Example: > 1.5GiB
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Container Memory high on {{ $labels.compose_service }}/{{ $labels.name }}"
      description: "{{ $labels.compose_service }} container {{ $labels.name }} Memory is at {{ $value | printf \"%.2f\" }}% for 5m."

  - alert: ContainerRestarting
    expr: changes(container_restarts_total{image!="", name=~".+"}[15m]) >= 2
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Container restarting: {{ $labels.compose_service }}/{{ $labels.name }}"
      description: "{{ $labels.compose_service }} container {{ $labels.name }} has restarted {{ $value }} times in the last 15m."

- name: prometheus_self_monitoring
  rules:
  - alert: PrometheusTargetMissing
    expr: up == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Prometheus target missing: {{ $labels.job }} instance {{ $labels.instance }}"
      description: "Target {{ $labels.job }} ({{ $labels.instance }}) has been down for 5 minutes."
```

## 4. Future Enhancements

*   Instrument application services to expose custom metrics (e.g., API latencies, error counts, business KPIs) via a `/metrics` endpoint for Prometheus to scrape.
*   Create more detailed application-specific dashboards in Grafana.
*   Configure more sophisticated alerting rules in Prometheus and routing in Alertmanager (e.g., different receivers for different severities or services).
*   Integrate `node_exporter` for comprehensive host monitoring if not done initially.

This setup provides a solid foundation for monitoring your Docker Compose deployed application. Remember to secure endpoints and change default credentials if exposing Grafana or other UIs publicly.

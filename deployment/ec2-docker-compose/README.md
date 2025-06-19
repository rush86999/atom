# Deploying Atomic Calendar on a Single EC2 Instance with Docker Compose

This guide outlines how to deploy the Atomic Calendar application on a single AWS EC2 instance using Docker Compose. This method is suitable for a single user or for development/testing environments where cost-effectiveness is a priority.

## Prerequisites

1.  **AWS Account:** You'll need an AWS account.
2.  **EC2 Instance:**
    *   Recommended Type: `t4g.small` (ARM64) or `t3.small` (x86_64).
    *   OS: Amazon Linux 2 or Ubuntu Server.
    *   Storage: 30-50GB General Purpose SSD (gp3).
    *   Security Group: Ensure ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) are open to your IP for access and to the world for web traffic.
3.  **Domain Name (Optional):** If you want to use SSL with a custom domain, have one ready and be able. to update its DNS records.
4.  **Software to install on EC2:**
    *   Git
    *   Docker
    *   Docker Compose

## Setup and Installation

1.  **Launch and Connect to EC2 Instance:**
    *   Launch your chosen EC2 instance type.
    *   Connect to your instance via SSH.

2.  **Install Docker and Docker Compose:**

    *For Amazon Linux 2:*
    ```bash
    sudo yum update -y
    sudo amazon-linux-extras install docker -y
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -a -G docker ec2-user
    # Log out and log back in to apply group changes
    # Install docker-compose
    sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    docker-compose --version
    ```

    *For Ubuntu Server:*
    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install git docker.io docker-compose -y
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -a -G docker $USER
    # Log out and log back in to apply group changes
    docker-compose --version
    ```

3.  **Clone the Repository:**
    ```bash
    git clone <your_repository_url>
    cd <repository_directory>/atomic-docker/project
    ```

4.  **Configure Environment Variables:**
    *   Create a `.env` file by copying from an example if available, or create a new one.
        ```bash
        cp .env.example .env
        # Or, if no example:
        # nano .env
        ```
    *   Populate the `.env` file with necessary configurations. Key variables to set:
        *   `HOST_NAME`: Your EC2 public DNS or your custom domain (e.g., `app.yourdomain.com`).
        *   `POSTGRES_PASSWORD`: A strong password for the database.
        *   `POSTGRES_USERNAME`: (e.g., `postgres`)
        *   `SUPERTOKENS_POSTGRESQL_CONNECTION_URI`: `postgresql://<POSTGRES_USERNAME>:<POSTGRES_PASSWORD>@postgres:5432/postgres` (replace placeholders)
        *   `HASURA_GRAPHQL_DATABASE_URL`: `postgres://<POSTGRES_USERNAME>:<POSTGRES_PASSWORD>@postgres:5432/postgres`
        *   `HASURA_GRAPHQL_ADMIN_SECRET`: A strong secret for Hasura.
        *   `HASURA_GRAPHQL_JWT_SECRET`: A JSON structure with a strong key, e.g., `{"type":"HS256","key":"your-very-long-and-secure-secret-key-at-least-32-chars","issuer":"supertokens"}`.
        *   `API_TOKEN`: A strong API token for internal service communication.
        *   `S3_ENDPOINT`: `http://minio:8484`
        *   `STORAGE_ACCESS_KEY`: Access key for Minio (e.g., `minioadmin`)
        *   `STORAGE_SECRET_KEY`: Secret key for Minio (e.g., `minioadmin`)
        *   `OPTAPLANNER_USERNAME`, `OPTAPLANNER_PASSWORD` (if using OptaPlanner)
        *   Fill in other external service API keys as needed (OpenAI, Google, Zoom, etc.).
        *   **Important for Traefik SSL:** If using a domain, ensure `TRAEFIK_USER` and `TRAEFIK_PASSWORD` are set for basic auth on Traefik dashboard (optional) and `LETSENCRYPT_EMAIL` is set for Let's Encrypt.

5.  **Customize `docker-compose.yaml` (Optional for Cost Saving):**
    *   It's recommended to create a specific version for single-user deployment:
        ```bash
        cp docker-compose.yaml docker-compose.single-user.yaml
        ```
    *   Edit `docker-compose.single-user.yaml` (e.g., `nano docker-compose.single-user.yaml`):
        *   **Remove non-essential services:**
            *   `whoami`
            *   `mailhog`
        *   **Consider removing resource-intensive services if not core to your use:**
            *   `zookeeper` and `kafka1`: Removing these significantly reduces resource usage. Check if the `functions` service can operate without them or if their tasks are non-critical for your needs. If removed, you might need to adjust `functions` service configuration or error handling.
            *   `optaplanner`: Remove if advanced scheduling features are not required.
        *   **Verify Volume Mappings for Persistence:**
            *   Ensure volumes for `postgres` (`./postgres/data`), `minio` (`./data/minio`), and `traefik` (`./letsencrypt`) are correctly mapped to host paths to persist data across container restarts. These are usually configured correctly in the provided `docker-compose.yaml`.
            *   For `python-agent` (if it uses LanceDB locally): Add a volume like `- ./data/lancedb:/mnt/lancedb_data` if it needs to persist LanceDB data on the host.

6.  **Build and Run Application:**
    *   If you created `docker-compose.single-user.yaml`:
        ```bash
        docker-compose -f docker-compose.single-user.yaml up --build -d
        ```
    *   If you modified the default `docker-compose.yaml`:
        ```bash
        docker-compose up --build -d
        ```
    *   The `--build` flag rebuilds images if their Dockerfiles or contexts have changed.
    *   `-d` runs containers in detached mode.

7.  **Accessing the Application:**
    *   If you configured a domain for `HOST_NAME` and your DNS records point to the EC2 instance's IP, Traefik should automatically obtain SSL certificates. You can then access the app at `https://<your_HOST_NAME>`.
    *   If using the EC2 public DNS, SSL will likely not be valid unless you manually configure it or use a self-signed certificate (not recommended for general use). Access might be via `http://<EC2_public_DNS>`.
    *   Check container logs for any issues: `docker-compose -f docker-compose.single-user.yaml logs -f <service_name>` or `docker-compose logs -f <service_name>`.

## Managing the Application

*   **Stopping:** `docker-compose -f docker-compose.single-user.yaml down`
*   **Starting:** `docker-compose -f docker-compose.single-user.yaml up -d`
*   **Viewing Logs:** `docker-compose -f docker-compose.single-user.yaml logs <service_name>`
*   **Updating:**
    1.  `git pull` (to get latest code changes)
    2.  `docker-compose -f docker-compose.single-user.yaml up --build -d` (to rebuild images and restart services)

## Data Persistence and Backups

*   **PostgreSQL Data:** Stored in the `./postgres/data` directory on your EC2 host (relative to where you run `docker-compose`).
*   **Minio Data:** Stored in the `./data/minio` directory.
*   **Traefik Certificates:** Stored in the `./letsencrypt` directory.
*   **.env file:** Contains critical secrets.
*   **Backup Strategy:**
    *   Regularly back up these directories and your `.env` file.
    *   Use `cron` jobs to automate backups to a secure location (e.g., AWS S3 using `aws s3 sync`).
    *   Example cron job snippet (conceptual):
        ```cron
        0 2 * * * /usr/local/bin/aws s3 sync /path/to/atomic-docker/project/postgres/data s3://your-backup-bucket/postgres/ --delete
        0 2 * * * /usr/local/bin/aws s3 sync /path/to/atomic-docker/project/data/minio s3://your-backup-bucket/minio/ --delete
        0 2 * * * /usr/local/bin/aws s3 cp /path/to/atomic-docker/project/.env s3://your-backup-bucket/env_backup/.env.$(date +%Y%m%d%H%M%S)
        ```

## Security

*   Keep your EC2 instance updated: `sudo yum update -y` or `sudo apt update && sudo apt upgrade -y`.
*   Use strong, unique passwords and secrets in your `.env` file.
*   Restrict security group inbound rules to only necessary ports (SSH 22 from your IP, HTTP 80 and HTTPS 443 from anywhere).
*   Consider tools like `fail2ban` to protect SSH access.

This setup provides a cost-effective way to run the full application suite for a single user.

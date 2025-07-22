# Self hosted docker solution

## Tech Stack

The self-hosted Docker solution for Atom is composed of several key services:

*   **Traefik:** A modern reverse proxy and load balancer that handles incoming traffic and automatically manages SSL certificates using Let's Encrypt.
*   **PostgreSQL:** The primary relational database for storing application data.
*   **PostGraphile:** A tool that automatically creates a GraphQL API from your PostgreSQL schema, serving as the core of the backend.
*   **Supertokens:** An open-source authentication service that handles user login, session management, and JWT generation.
*   **Optaplanner:** A solver that tackles complex scheduling and optimization problems, used for calendar event planning.
*   **LanceDB:** A vector database for high-performance similarity search, used for semantic search on notes and transcripts.
*   **Kafka & MongoDB:** Used by `agenda` for scheduling and managing asynchronous background jobs.
*   **Application Services:**
    *   **App (Next.js):** The main frontend application.
    *   **Functions (Node.js/Express):** Backend service for handling business logic and integrating with other services.
    *   **Python Agent:** A Python service for AI-powered features, including note-taking, research, and interaction with LanceDB.
    *   **Handshake & OAuth (Next.js):** Services dedicated to handling meeting handshakes and OAuth flows for integrations.
  
## Setup and Configuration

Follow these steps to get your self-hosted Atom instance up and running.

### 1. Prerequisites

*   **A server or local machine:** With Docker and Docker Compose installed.
*   **A custom domain name:** (Recommended for production) Pointing to your server's public IP address.
*   **Open firewall ports:** Ensure ports 80 and 443 are open on your server's firewall to allow Traefik to perform the Let's Encrypt HTTP challenge and serve HTTPS traffic.

### 2. Configure Environment Variables

1.  Navigate to the `project` directory:
    ```bash
    cd atomic-docker/project
    ```
2.  Create your `.env` file from the example:
    ```bash
    cp .env.example .env
    ```
3.  **Edit the `.env` file** and fill in all the required values. This is the most critical step. Pay close attention to:
    *   `HOST_NAME`: Your custom domain name (e.g., `atom.yourcompany.com`).
    *   `LETSENCRYPT_EMAIL`: Your email address for SSL certificate notifications.
    *   `POSTGRES_PASSWORD`: A strong, unique password for the database.
    *   `API_TOKEN`: A secret token for securing internal API communication.
    *   **External Service APIs:** `OPENAI_API_KEY`, `NOTION_API_KEY`, `DEEPGRAM_API_KEY`, etc.
    *   **Google OAuth Credentials:** See the section below for instructions on how to obtain these.

### 3. Obtain Google OAuth Credentials

To enable Google Calendar and other Google integrations, you need to create OAuth 2.0 credentials in the Google Cloud Console.

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/apis) and create a new project.
2.  Enable the **Google Calendar API**.
3.  Go to **Credentials**, click **Create credentials**, and select **OAuth client ID**.
4.  Choose **Web application** as the application type.
5.  Add the following **Authorized redirect URIs**:
    *   `https://${HOST_NAME}/v1/oauth/api/google-calendar-handshake/oauth2callback`
    *   `https://${HOST_NAME}/api/google/oauth-callback`
6.  Click **Create**. Copy the **Client ID** and **Client Secret**.
7.  Add the copied credentials to your `.env` file for the corresponding `GOOGLE_*` variables.

### 4. (Optional) Supertokens and PostGraphile JWT Integration

By default, the system is configured for Supertokens to provide JWTs that PostGraphile can consume. The `PGRAPHILE_JWT_SECRET` should match the secret Supertokens uses to sign JWTs, which is handled via environment variables in the `docker-compose.yaml` file. No manual changes are typically needed unless you are customizing the authentication flow.

### 5. (Deprecated) OpenSearch Configuration

The system has been migrated from OpenSearch to **LanceDB** for vector search. All steps related to generating OpenSearch certificates and configuring users are no longer necessary. You can safely ignore or remove any `opensearch` related configurations.

### 6. OptaPlanner Credentials

The username and password for OptaPlanner are set via the `OPTAPLANNER_USERNAME` and `OPTAPLANNER_PASSWORD` environment variables. These are automatically synchronized with the `admin_user` table in the database via the `initdb.d/optaplanner-create-schema.sql` script. Ensure the credentials in your `.env` file are secure.
### 7. Running the Application

Once your `.env` file is fully configured, you can start the application.

1.  **Navigate to the `project` directory** (if you're not already there):
    ```bash
    cd atomic-docker/project
    ```
2.  **Start the services using Docker Compose:**
    ```bash
    docker-compose up -d
    ```

This command will download the necessary Docker images, build the application services, and start everything in detached mode (`-d`).

It may take a few minutes for all services to start up and become healthy. You can monitor the status of the containers by running:
```bash
docker-compose ps
```

Once all services are running, you can access your Atom instance by navigating to `https://${HOST_NAME}` in your web browser.

### Security Best Practices

*   **Secure your `.env` file:** This file contains sensitive credentials. Set strict file permissions (`chmod 600 .env`) and never commit it to version control.
*   **Use strong, unique passwords:** Replace all placeholder values in your `.env` file with strong, unique secrets.
*   **Regularly rotate secrets:** Periodically review and rotate the credentials stored in your `.env` file.

### Updating Your Instance

To update your self-hosted Atom instance to the latest version:

1.  **Backup your data:** Before any update, it is crucial to back up your PostgreSQL database. See the "Database Backup and Restore" section for detailed instructions.
2.  **Pull the latest changes:** If you are running the application from a Git repository, pull the latest changes from your main branch.
    ```bash
    git pull origin main
    ```
3.  **Pull the latest Docker images:**
    ```bash
    docker-compose pull
    ```
4.  **Rebuild local images:**
    ```bash
    docker-compose build
    ```
5.  **Restart the services:**
    ```bash
    docker-compose up -d --remove-orphans
    ```
6.  **Verify the update:** Check that all services are running correctly (`docker-compose ps`) and test the application's functionality.

### Monitoring and Health Checks

To ensure your Atom instance is running smoothly, use these basic monitoring commands:

*   **Check container status:**
    ```bash
    docker-compose ps
    ```
    Look for a `(healthy)` status for all services. If a service is `(unhealthy)` or constantly restarting, check its logs.
*   **View service logs:**
    ```bash
    docker-compose logs <service_name>
    ```
    For example, to check the logs of the `app` service, run `docker-compose logs app`. To follow the logs in real-time, use the `-f` flag.
*   **Monitor host resources:** Keep an eye on your server's CPU, memory, and disk space using tools like `htop` and `df -h`.

For more advanced monitoring, consider setting up an external uptime monitor and alerts for resource usage.

### Database Backup and Restore (PostgreSQL)

Regularly backing up your PostgreSQL database is crucial for data protection and recovery in case of hardware failure, data corruption, or accidental deletion. This section outlines how to perform backups and restores for the PostgreSQL container running in this Docker Compose setup.

**1. Performing Backups**

We will use the `pg_dump` utility to create a logical backup of your database. This command should be run on the host machine where Docker is running.

*   **Identify your PostgreSQL container name:** By default, it's `postgres` as defined in `docker-compose.yaml` (inside the `project` directory, the full name might be `project-postgres-1` or similar if `docker-compose` adds project prefixes. Use `docker ps` to confirm the running container name). For the commands below, we'll assume the service name `postgres` can be used with `docker-compose exec`.
*   **Database Name:** The default database name used by Hasura and other services is typically `postgres`. Confirm this from your `HASURA_GRAPHQL_DATABASE_URL` in the `.env` file if unsure (it's the part after the last `/`).
*   **PostgreSQL Username:** This is defined by `POSTGRES_USERNAME` in your `.env` file (default is `postgres`).

**Command to create a backup:**

```bash
# Ensure you are in the atomic-docker/project directory where your docker-compose.yaml is
# Replace YOUR_BACKUP_PATH with the desired path on your host machine to store the backup
# Example: /srv/backups/atomic-postgres/
YOUR_BACKUP_PATH="/path/to/your/backups/"
DB_USER="${POSTGRES_USERNAME:-postgres}" # Use default from .env.example if not set
DB_NAME="postgres" # Default database name
BACKUP_FILE="${YOUR_BACKUP_PATH}atomic_db_backup_$(date +%Y%m%d_%H%M%S).sql"

# Create the backup directory if it doesn't exist
mkdir -p "${YOUR_BACKUP_PATH}"

# Execute pg_dump inside the container
docker-compose exec -T postgres pg_dump -U "${DB_USER}" -d "${DB_NAME}" > "${BACKUP_FILE}"

echo "Database backup created at ${BACKUP_FILE}"
# Optional: Compress the backup
# gzip "${BACKUP_FILE}"
# echo "Backup compressed: ${BACKUP_FILE}.gz"
```

**Important Considerations for Backups:**
- **Permissions:** Ensure the directory specified by `YOUR_BACKUP_PATH` is writable by the user running the `docker-compose exec` command.
- **Database Activity:** `pg_dump` creates a consistent snapshot. However, for very busy databases, consider performing backups during off-peak hours.
- **Security of Backup Files:** Backup files contain all your data. Store them in a secure location with restricted access. Encrypt them if necessary, especially if storing off-site.

**2. Automating Backups (using cron)**

You can automate the backup process using a cron job on your host machine.

Create a shell script (e.g., `backup_atomic_db.sh`) with the backup command:
```bash
#!/bin/bash

# Path to your atomic-docker/project directory
PROJECT_DIR="/path/to/your/atomic-docker/project" # ADJUST THIS PATH
BACKUP_DIR="/srv/backups/atomic-postgres/" # ADJUST THIS PATH
DB_USER="${POSTGRES_USERNAME:-postgres}" # Ensure POSTGRES_USERNAME is available in this script's env or hardcode
DB_NAME="postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}atomic_db_backup_${TIMESTAMP}.sql"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Navigate to project directory to use docker-compose
cd "${PROJECT_DIR}" || exit 1

# Execute pg_dump
docker-compose exec -T postgres pg_dump -U "${DB_USER}" -d "${DB_NAME}" > "${BACKUP_FILE}"

# Optional: Compress the backup
gzip "${BACKUP_FILE}"
echo "Database backup created and compressed: ${BACKUP_FILE}.gz"

# Optional: Prune old backups (e.g., keep last 7 days)
# find "${BACKUP_DIR}" -name "atomic_db_backup_*.sql.gz" -mtime +7 -exec rm {} \;
```
Make the script executable: `chmod +x backup_atomic_db.sh`.

Then, add a cron job. Edit your crontab using `crontab -e` and add a line like this to run the backup daily at 2 AM:
```cron
0 2 * * * /path/to/your/backup_atomic_db.sh >> /var/log/atomic_backup.log 2>&1
```
Adjust the script path and schedule as needed. Ensure the `POSTGRES_USERNAME` variable is correctly sourced by the cron job or hardcode it in the script if necessary.

**3. Backup Storage and Retention**

- **Off-Host Storage:** **Crucially important.** Do not rely solely on backups stored on the same server as your Docker host. Regularly transfer your backups to a remote, secure location (e.g., another server, cloud storage like AWS S3, Backblaze B2, Google Cloud Storage, or even a separate physical drive stored securely).
- **Retention Policy:** Define how long you need to keep backups. A common strategy is:
    - Daily backups for the last 7 days.
    - Weekly backups for the last 4 weeks.
    - Monthly backups for the last 6-12 months.
  Implement this policy by regularly deleting older backups that are no longer needed, either manually or via scripting in your backup storage solution.

**4. Restoring Backups**

Restoring a database backup typically involves dropping the existing database (if it exists and you want a clean restore) and then recreating it and importing the data.

**CAUTION: Restoring a backup will overwrite the current data in the target database. Ensure you are restoring to the correct environment and have taken necessary precautions (like backing up the current state if needed).**

*   **Command to restore a backup (assuming an uncompressed .sql file):**
    ```bash
    # Ensure you are in the atomic-docker/project directory
    YOUR_BACKUP_FILE="/path/to/your/backups/atomic_db_backup_YYYYMMDD_HHMMSS.sql" # Path to your .sql backup file
    # If compressed, decompress first: gunzip "${YOUR_BACKUP_FILE}.gz"

    DB_USER="${POSTGRES_USERNAME:-postgres}"
    DB_NAME="postgres"

    # 1. Optional: Stop services that use the database (e.g., hasura, functions, app)
    # docker-compose stop hasura functions app supertokens optaplanner python-agent
    # This is to prevent connections while restoring.

    # 2. Drop and recreate the database (if you want a clean slate)
    # docker-compose exec -T postgres psql -U "${DB_USER}" -c "DROP DATABASE IF EXISTS ${DB_NAME};"
    # docker-compose exec -T postgres psql -U "${DB_USER}" -c "CREATE DATABASE ${DB_NAME};"
    # Note: Dropping the 'postgres' database itself can be problematic if other system-level
    #       objects depend on it or if it's the default connection DB for psql.
    #       A safer approach for a full restore might be to restore into a new, temporary database,
    #       verify, and then rename, or to drop all tables within the existing database.
    #       For simplicity here, we assume restoring into the existing (potentially empty or to-be-overwritten) DB.

    # 3. Restore the database from the .sql file
    cat "${YOUR_BACKUP_FILE}" | docker-compose exec -T postgres psql -U "${DB_USER}" -d "${DB_NAME}"

    echo "Database restore from ${YOUR_BACKUP_FILE} attempted."

    # 4. Optional: Restart services if stopped
    # docker-compose start postgraphile functions app supertokens optaplanner python-agent
    ```
*   **For compressed backups (`.sql.gz`):**
    ```bash
    # Decompress and pipe to psql
    gunzip < "${YOUR_BACKUP_FILE}.gz" | docker-compose exec -T postgres psql -U "${DB_USER}" -d "${DB_NAME}"
    ```
*   **Using `pg_restore` (for custom format or directory format backups):** If you used `pg_dump` with `-Fc` (custom format) or `-Fd` (directory format), you would use `pg_restore`. For plain SQL dumps (`.sql`), `psql` is used as shown above.

**5. Testing Your Backups**
Regularly test your backup and restore process in a non-production environment to ensure your backups are valid and you know how to perform a restore when needed. This is a critical step often overlooked.

**6. Point-In-Time Recovery (PITR) - Advanced**
For more stringent RPO (Recovery Point Objective) requirements, PostgreSQL supports Point-In-Time Recovery by continuously archiving Write-Ahead Log (WAL) files. Setting up PITR is more complex and involves configuring `archive_command` in PostgreSQL and managing WAL archives. This is beyond a basic backup strategy but provides finer-grained recovery capabilities.



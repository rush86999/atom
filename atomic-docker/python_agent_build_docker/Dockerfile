# Use python:3.9-slim as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the local project directory (relative to build context) into /app/project in the image
# Build context for docker-compose will be 'python_agent_build_docker'.
# So, '../project' refers to 'atomic-docker/project/'.
COPY ../project /app/project

# Install Python dependencies
RUN pip install --no-cache-dir notion-client deepgram-sdk requests httpx

# Set PYTHONPATH. With this, Python will look for /app/project/...
# For imports like `from project.functions...` this is correct.
ENV PYTHONPATH="/app"

# Create __init__.py files to ensure Python treats directories as packages.
# These paths are relative to WORKDIR /app.
RUN touch /app/project/__init__.py && \
    touch /app/project/functions/__init__.py && \
    touch /app/project/functions/atom-agent/__init__.py

# Command to keep the container running (useful for exec-ing into it, can be overridden)
CMD ["tail", "-f", "/dev/null"]

# Dockerfile for the Atom Ingestion Pipeline Service

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app/ingestion_pipeline

# Install system dependencies that might be required by Python packages (e.g., for lancedb or other libraries)
# Example: build-essential for C extensions, other libs as needed.
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#  && rm -rf /var/lib/apt/lists/*
# For now, assuming basic dependencies are sufficient. Add more if build errors occur.

# Copy the requirements file into the container at /app/ingestion_pipeline
COPY ./requirements.txt /app/ingestion_pipeline/requirements.txt

# Install any needed packages specified in requirements.txt
# It's good practice to install requirements before copying the rest of the app code
# to leverage Docker layer caching if requirements don't change.
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app/ingestion_pipeline
# This includes notion_extractor.py, text_processor.py, lancedb_handler.py, pipeline_orchestrator.py, main.py
COPY . /app/ingestion_pipeline/

# Make port 8002 available to the world outside this container (if uvicorn runs on 8002)
# This is the port the FastAPI application will run on.
EXPOSE 8002

# Define environment variables (defaults can be set here, but usually overridden by docker-compose or runtime)
# ENV NAME="World" # Example

# Command to run the application using Uvicorn
# This will execute when the container launches.
# Ensure main.py can be found and `app` is the FastAPI instance.
# The path to main:app might need adjustment if your file structure is different inside the container.
# If pipeline_orchestrator.py is meant to be run directly as a script for cron jobs,
# the CMD would be different, e.g., ["python", "pipeline_orchestrator.py"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

# Dockerfile for the Atom Workflows Service

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app/workflows

# Copy the requirements file into the container at /app/workflows
COPY ./requirements.txt /app/workflows/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app/workflows
COPY . /app/workflows/

# Make port 8003 available to the world outside this container
EXPOSE 8003

# Command to run the application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]

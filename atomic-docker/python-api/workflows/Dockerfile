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

# Copy the start script and make it executable
COPY ./start.sh /app/workflows/start.sh
RUN chmod +x /app/workflows/start.sh

# Run the start script
CMD ["/app/workflows/start.sh"]

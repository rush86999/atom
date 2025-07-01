# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies that might be needed by sounddevice or other libraries
# For sounddevice, portaudio is often a dependency.
# libasound2-dev is for ALSA, which is common on Linux.
# libportaudiocpp0 and libportaudio2 might be needed.
# Check sounddevice documentation for minimal dependencies on Debian/Slim.
# For now, let's add common ones; can be refined if image size is critical or issues arise.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    libportaudiocpp0 \
    # python3-pyaudio # This would be if we installed pyaudio via apt, but we use pip.
    # alsa-utils # For ALSA utilities, might not be strictly needed by the app itself
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install pip dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8001

# Define the command to run the application
# Using 0.0.0.0 to bind to all interfaces, making it accessible from outside the container (within Docker network)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

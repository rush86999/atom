# Use an official Node.js runtime as a parent image
FROM node:18-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install app dependencies
RUN npm install
# If you were using yarn:
# RUN yarn install --frozen-lockfile

# Bundle app source
COPY . .

# Set environment variables (can be overridden at runtime)
ENV NODE_ENV="production"
ENV PORT="3000"
ENV LOG_LEVEL="info"
# OTEL_SERVICE_NAME and OTEL_SERVICE_VERSION can be set here or at runtime
# ENV OTEL_SERVICE_NAME="observability-poc-nodejs"
# ENV OTEL_SERVICE_VERSION="1.0.0"
# OTLP Exporter endpoints (defaults to localhost in tracing.js, override if needed for containerized collector)
# For example, if collector is on host machine:
# ENV OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://host.docker.internal:4318/v1/traces"
# ENV OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="http://host.docker.internal:4318/v1/metrics"
# Or if collector is another container in the same docker network (e.g., named 'otel-collector'):
# ENV OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://otel-collector:4318/v1/traces"
# ENV OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="http://otel-collector:4318/v1/metrics"


# Expose port 3000
EXPOSE 3000

# Define the command to run your app
CMD [ "node", "index.js" ]

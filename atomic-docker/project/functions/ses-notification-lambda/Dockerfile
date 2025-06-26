# Use the official AWS Lambda Node.js 18 base image
# This image includes the Lambda Runtime Interface Emulator (RIE) for local testing.
FROM public.ecr.aws/lambda/nodejs:18

# Set the working directory in the Lambda container.
# ${LAMBDA_TASK_ROOT} is a standard environment variable in AWS Lambda.
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy the bundled application code.
# It's assumed that a build step (e.g., using 'serverless-esbuild' or a custom script)
# has already compiled TypeScript to JavaScript and placed the output (e.g., index.js and index.js.map)
# at the root of the context that Docker uses for this COPY operation.
# When Serverless Framework builds an image, it typically prepares a context with these files.
COPY index.js ${LAMBDA_TASK_ROOT}/
COPY index.js.map ${LAMBDA_TASK_ROOT}/

# If your project has production node_modules that were NOT bundled by esbuild
# (e.g., native modules marked as external, or if you explicitly chose not to bundle node_modules):
# 1. Ensure your esbuild configuration (e.g., in serverless.yml via serverless-esbuild)
#    marks these dependencies as external.
# 2. Copy package.json and package-lock.json (or yarn.lock).
# COPY package.json package-lock.json* ./
# # COPY yarn.lock ./ # If using Yarn
#
# 3. Install *only* production dependencies using the appropriate lock file.
# RUN npm ci --only=production
# # RUN yarn install --production --frozen-lockfile # If using Yarn
#
# This will create a node_modules folder in your image.
# For many common use cases with serverless-esbuild, dependencies are bundled,
# and this explicit npm/yarn install step in the Dockerfile is not needed.

# The CMD instruction in a Dockerfile for an AWS Lambda base image specifies the handler.
# However, this is often overridden by the 'Handler' property in the Lambda function's
# configuration (e.g., in serverless.yml or SAM template).
# The AWS Lambda Runtime Interface Client (included in the base image) will use the
# handler specified in the Lambda configuration.
# If CMD is set, it might serve as a default if no handler is configured, or for local testing.
# For example: CMD [ "index.handler" ]
# For this setup, we'll rely on the handler being set in serverless.yml.
# The base image's ENTRYPOINT will start the Lambda Runtime Interface Client.

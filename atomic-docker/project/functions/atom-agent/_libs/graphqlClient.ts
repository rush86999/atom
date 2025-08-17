import axios, { AxiosError } from "axios";

/**
 * Represents a generic error from the GraphQL client.
 */
class GraphQLError extends Error {
  constructor(
    message: string,
    public code?: string,
    public details?: any,
  ) {
    super(message);
    this.name = "GraphQLError";
  }
}

/**
 * Default Postgraphile GraphQL endpoint - configured via environment
 */
const DEFAULT_POSTGRAPHILE_URL =
  process.env.POSTGRAPHILE_URL || "http://localhost:5000/graphql";
const AUTH_BEARER_TOKEN =
  process.env.AUTH_BEARER_TOKEN || process.env.JWT_SECRET || "";

/**
 * Executes a GraphQL query through Postgraphile
 *
 * @param query The GraphQL query string.
 * @param variables An object containing variables for the query.
 * @param operationName The name of the GraphQL operation.
 * @param userId Optional user ID for context, used if bearer token requires user context
 * @returns A Promise that resolves with the `data` part of the GraphQL response.
 * @throws {GraphQLError} If there's a network error, HTTP error, or GraphQL errors are present in the response.
 */
export async function executeGraphQLQuery<T = any>(
  query: string,
  variables: Record<string, any>,
  operationName: string,
  userId?: string,
): Promise<T> {
  if (!DEFAULT_POSTGRAPHILE_URL) {
    throw new GraphQLError(
      "Postgraphile GraphQL URL is not configured. Please set POSTGRAPHILE_URL environment variable.",
      "CONFIG_ERROR",
    );
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  // Add bearer token for Postgraphile authentication if provided
  if (AUTH_BEARER_TOKEN) {
    headers["Authorization"] = `Bearer ${AUTH_BEARER_TOKEN}`;
  }

  const MAX_RETRIES = 3;
  const INITIAL_TIMEOUT_MS = 15000;
  let attempt = 0;
  let lastError: any = null;

  while (attempt < MAX_RETRIES) {
    try {
      const response = await axios.post(
        DEFAULT_POSTGRAPHILE_URL,
        {
          query,
          variables,
          operationName,
        },
        {
          headers,
          timeout: INITIAL_TIMEOUT_MS,
        },
      );

      if (response.data.errors) {
        lastError = new GraphQLError(
          `GraphQL error executing operation '${operationName}'.`,
          "GRAPHQL_EXECUTION_ERROR",
          response.data.errors,
        );
        throw lastError;
      }

      return response.data.data as T;
    } catch (error) {
      lastError = error;

      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<any>;
        if (axiosError.response) {
          const status = axiosError.response.status;
          if (status >= 500 || status === 429) {
            // Retry on server errors or rate limiting
          } else {
            lastError = new GraphQLError(
              `HTTP error ${status} executing operation '${operationName}'. Not retrying.`,
              `HTTP_${status}`,
              axiosError.response.data,
            );
            break;
          }
        } else if (axiosError.request) {
          if (axiosError.code === "ECONNABORTED") {
            lastError = new GraphQLError(
              `GraphQL operation '${operationName}' timed out after ${INITIAL_TIMEOUT_MS}ms.`,
              "TIMEOUT_ERROR",
              axiosError.config,
            );
          }
        } else {
          lastError = new GraphQLError(
            `Axios setup error for operation '${operationName}': ${axiosError.message}. Not retrying.`,
            "AXIOS_SETUP_ERROR",
            axiosError.config,
          );
          break;
        }
      } else if (
        error instanceof GraphQLError &&
        error.code === "GRAPHQL_EXECUTION_ERROR"
      ) {
        // GraphQL execution error
      } else {
        break;
      }
    }

    attempt++;
    if (attempt < MAX_RETRIES) {
      const delay = Math.pow(2, attempt - 1) * 1000;
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  const finalMessage = `Failed GraphQL operation '${operationName}' after ${attempt} attempts.`;
  console.error(finalMessage, {
    code: (lastError as any)?.code,
    message: lastError?.message,
    details: (lastError as any)?.details || lastError,
  });

  if (lastError instanceof GraphQLError) {
    throw lastError;
  }

  throw new GraphQLError(
    `${finalMessage}: ${(lastError as Error)?.message || "Unknown error"}`,
    (lastError as any)?.code || "ALL_RETRIES_FAILED",
    lastError as any,
  );
}

/**
 * Executes a GraphQL mutation through Postgraphile
 *
 * @param mutation The GraphQL mutation string.
 * @param variables An object containing variables for the mutation.
 * @param operationName The name of the GraphQL operation.
 * @param userId Optional user ID for context, used if bearer token requires user context
 * @returns A Promise that resolves with the `data` part of the GraphQL response.
 * @throws {GraphQLError} If there's a network error, HTTP error, or GraphQL errors are present in the response.
 */
export async function executeGraphQLMutation<T = any>(
  mutation: string,
  variables: Record<string, any>,
  operationName: string,
  userId?: string,
): Promise<T> {
  // The implementation is identical to executeGraphQLQuery,
  // as Postgraphile uses the same endpoint and request structure for queries and mutations.
  return executeGraphQLQuery<T>(mutation, variables, operationName, userId);
}

import { HASURA_ADMIN_SECRET, HASURA_GRAPHQL_URL } from "./constants";

interface GraphQLResponse<T = any> {
  data?: T;
  errors?: Array<{ message: string }>;
}

export async function executeGraphQLQuery<T = any>(
  query: string,
  variables?: Record<string, any>,
  operationName?: string,
): Promise<GraphQLResponse<T>> {
  try {
    const response = await fetch(HASURA_GRAPHQL_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-hasura-admin-secret": HASURA_ADMIN_SECRET,
      },
      body: JSON.stringify({
        query,
        variables,
        operationName,
      }),
    });

    if (!response.ok) {
      throw new Error(
        `GraphQL request failed: ${response.status} ${response.statusText}`,
      );
    }

    return await response.json();
  } catch (error) {
    console.error("GraphQL query error:", error);
    return { errors: [{ message: "Failed to execute GraphQL query" }] };
  }
}

export async function executeGraphQLMutation<T = any>(
  mutation: string,
  variables?: Record<string, any>,
  operationName?: string,
): Promise<GraphQLResponse<T>> {
  return executeGraphQLQuery(mutation, variables, operationName);
}

export async function executeGraphQLSubscription<T = any>(
  query: string,
  variables?: Record<string, any>,
  operationName?: string,
): Promise<AsyncIterable<T>> {
  // This is a placeholder for subscription implementation
  // In a real implementation, you would use WebSocket or SSE
  throw new Error("GraphQL subscriptions not implemented");
}

export function createGraphQLClient(options?: {
  headers?: Record<string, string>;
}) {
  const defaultHeaders = {
    "Content-Type": "application/json",
    "x-hasura-admin-secret": HASURA_ADMIN_SECRET,
  };

  const headers = {
    ...defaultHeaders,
    ...options?.headers,
  };

  return {
    query: async <T = any>(
      query: string,
      variables?: Record<string, any>,
      operationName?: string,
    ): Promise<GraphQLResponse<T>> => {
      const response = await fetch(HASURA_GRAPHQL_URL, {
        method: "POST",
        headers,
        body: JSON.stringify({ query, variables, operationName }),
      });

      if (!response.ok) {
        throw new Error(
          `GraphQL query failed: ${response.status} ${response.statusText}`,
        );
      }

      return response.json();
    },

    mutate: async <T = any>(
      mutation: string,
      variables?: Record<string, any>,
      operationName?: string,
    ): Promise<GraphQLResponse<T>> => {
      return executeGraphQLMutation(mutation, variables, operationName);
    },
  };
}

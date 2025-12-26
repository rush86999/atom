import { HASURA_ADMIN_SECRET, HASURA_GRAPHQL_URL } from "./constants";

interface GraphQLResponse<T = any> {
  data?: T;
  errors?: Array<{ message: string }>;
}

export async function executeGraphQLQuery<T = any>(
  query: string,
  variables?: Record<string, any>,
  operationName?: string,
  _userId?: string, // Optional userId for logging/context
): Promise<T> {
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

    const result: GraphQLResponse<T> = await response.json();

    if (result.errors && result.errors.length > 0) {
      throw new Error(result.errors.map(e => e.message).join(', '));
    }

    return result.data as T;
  } catch (error) {
    console.error("GraphQL query error:", error);
    throw error;
  }
}

export async function executeGraphQLMutation<T = any>(
  mutation: string,
  variables?: Record<string, any>,
  operationName?: string,
  userId?: string,
): Promise<T> {
  return executeGraphQLQuery<T>(mutation, variables, operationName, userId);
}

export async function executeGraphQLSubscription<T = any>(
  query: string,
  variables?: Record<string, any>,
  operationName?: string,
): Promise<AsyncIterable<T>> {
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
    ): Promise<T> => {
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

      const result: GraphQLResponse<T> = await response.json();

      if (result.errors && result.errors.length > 0) {
        throw new Error(result.errors.map(e => e.message).join(', '));
      }

      return result.data as T;
    },

    mutate: async <T = any>(
      mutation: string,
      variables?: Record<string, any>,
      operationName?: string,
    ): Promise<T> => {
      return executeGraphQLMutation<T>(mutation, variables, operationName);
    },
  };
}

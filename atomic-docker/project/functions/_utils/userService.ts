import { createAdminGraphQLClient } from './dbService';

const GET_USER_LLM_MODEL_QUERY = `
query GetUserLlmModel($userId: uuid!) {
  users_by_pk(id: $userId) {
    llm_model
  }
}
`;

const UPDATE_USER_LLM_MODEL_MUTATION = `
mutation UpdateUserLlmModel($userId: uuid!, $llmModel: String!) {
  update_users_by_pk(pk_columns: {id: $userId}, _set: {llm_model: $llmModel}) {
    id
  }
}
`;

export async function getUserLlmModel(userId: string): Promise<string | null> {
  const adminGraphQLClient = createAdminGraphQLClient();
  const response = await adminGraphQLClient.request(GET_USER_LLM_MODEL_QUERY, {
    userId,
  });
  return response.users_by_pk?.llm_model;
}

export async function updateUserLlmModel(userId: string, llmModel: string) {
  const adminGraphQLClient = createAdminGraphQLClient();
  await adminGraphQLClient.request(UPDATE_USER_LLM_MODEL_MUTATION, {
    userId,
    llmModel,
  });
}

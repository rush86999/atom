import got from 'got';
import { hasuraAdminSecret, hasuraGraphUrl } from './constants';

export async function executeGraphQLMutation<T>(
  mutation: string,
  variables: any,
  operationName: string,
  userId: string
): Promise<T> {
  const response = await got
    .post(hasuraGraphUrl, {
      json: {
        query: mutation,
        variables,
        operationName,
      },
      headers: {
        'X-Hasura-Admin-Secret': hasuraAdminSecret,
        'Content-Type': 'application/json',
        'X-Hasura-Role': 'user',
        'X-Hasura-User-Id': userId,
      },
    })
    .json();
  return response as T;
}

import { createNotionPage } from './notionAndResearchSkills';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import PocketAPI from 'pocket-api';

async function getPocketToken(userId: string): Promise<string | null> {
  const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                access_token
            }
        }
    `;
  const variables = {
    userId,
    service: 'pocket',
  };
  const response = await executeGraphQLQuery<{
    user_tokens: { access_token: string }[];
  }>(query, variables, 'GetUserToken', userId);
  if (response.user_tokens && response.user_tokens.length > 0) {
    return decrypt(response.user_tokens[0].access_token);
  }
  return null;
}

async function getPocketArticles(userId: string): Promise<any[]> {
  const accessToken = await getPocketToken(userId);
  if (!accessToken) {
    throw new Error('Pocket token not configured for this user.');
  }

  const pocket = new PocketAPI({
    consumer_key: process.env.POCKET_CONSUMER_KEY,
    access_token: accessToken,
  });

  return new Promise((resolve, reject) => {
    pocket.get({ count: 10, detailType: 'complete' }, (err, data) => {
      if (err) {
        return reject(err);
      }
      resolve(Object.values(data.list));
    });
  });
}

export async function generateLearningPlan(
  userId: string,
  notionDatabaseId: string
): Promise<void> {
  const articles = await getPocketArticles(userId);

  const articleTitles = articles
    .map((article) => article.resolved_title)
    .join('\n');

  const learningPlan = `
        Here is a personalized learning plan based on your recent articles:

        ${articleTitles}
    `;

  await createNotionPage(userId, {
    parent: { database_id: notionDatabaseId },
    properties: {
      title: {
        title: [
          {
            text: {
              content: 'Personalized Learning Plan',
            },
          },
        ],
      },
    },
    children: [
      {
        object: 'block',
        type: 'paragraph',
        paragraph: {
          rich_text: [
            {
              type: 'text',
              text: {
                content: learningPlan,
              },
            },
          ],
        },
      },
    ],
  });
}

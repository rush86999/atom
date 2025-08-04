import { SkillResponse } from '../../types';
import { decrypt } from '../../_libs/crypto';
import { executeGraphQLQuery } from '../../_libs/graphqlClient';
import { handleError } from '../../_utils/errorHandler';
import { TrelloClient } from 'trello.ts';

async function getTrelloCredentials(
  userId: string
): Promise<{ apiKey: string; apiToken: string } | null> {
  const query = `
        query GetUserCredentials($userId: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_in: ["trello_api_key", "trello_api_token"]}}) {
                service_name
                encrypted_secret
            }
        }
    `;
  const variables = {
    userId,
  };
  const response = await executeGraphQLQuery<{
    user_credentials: { service_name: string; encrypted_secret: string }[];
  }>(query, variables, 'GetUserCredentials', userId);
  if (response.user_credentials && response.user_credentials.length === 2) {
    const credentials: any = {};
    for (const cred of response.user_credentials) {
      credentials[cred.service_name] = decrypt(cred.encrypted_secret);
    }
    return {
      apiKey: credentials.trello_api_key,
      apiToken: credentials.trello_api_token,
    };
  }
  return null;
}

export async function handleCreateTrelloCard(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const credentials = await getTrelloCredentials(userId);
    if (!credentials) {
      return 'Trello credentials not configured for this user.';
    }
    const client = new TrelloClient({
      apiKey: credentials.apiKey,
      token: credentials.apiToken,
    });

    const { card_name, list_id } = entities;

    if (!card_name || typeof card_name !== 'string') {
      return 'Card name is required to create a Trello card.';
    }

    if (!list_id || typeof list_id !== 'string') {
      return 'List ID is required to create a Trello card.';
    }

    const card = await client.cards.create({
      name: card_name,
      idList: list_id,
    });

    return `Trello card created: ${card.name}`;
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't create the Trello card due to an error."
    );
  }
}

export async function handleQueryTrelloCards(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const credentials = await getTrelloCredentials(userId);
    if (!credentials) {
      return 'Trello credentials not configured for this user.';
    }
    const client = new TrelloClient({
      apiKey: credentials.apiKey,
      token: credentials.apiToken,
    });

    const { list_id } = entities;

    if (!list_id || typeof list_id !== 'string') {
      return 'List ID is required to query Trello cards.';
    }

    const cards = await client.lists.getCards(list_id);

    if (!cards.length) {
      return 'No cards found in the specified Trello list.';
    }

    let cardList = 'Here are the cards in the specified Trello list:\n';
    for (const card of cards) {
      cardList += `- ${card.name}\n`;
    }

    return cardList;
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't query the Trello cards due to an error."
    );
  }
}

export async function handleUpdateTrelloCard(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const credentials = await getTrelloCredentials(userId);
    if (!credentials) {
      return 'Trello credentials not configured for this user.';
    }
    const client = new TrelloClient({
      apiKey: credentials.apiKey,
      token: credentials.apiToken,
    });

    const { card_id, card_name } = entities;

    if (!card_id || typeof card_id !== 'string') {
      return 'Card ID is required to update a Trello card.';
    }

    if (!card_name || typeof card_name !== 'string') {
      return 'Card name is required to update a Trello card.';
    }

    const card = await client.cards.update(card_id, {
      name: card_name,
    });

    return `Trello card updated: ${card.name}`;
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't update the Trello card due to an error."
    );
  }
}

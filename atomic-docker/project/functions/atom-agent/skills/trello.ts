import { SkillResponse } from '../../types';
import { TRELLO_API_KEY, TRELLO_API_SECRET, TRELLO_TOKEN } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';
import { TrelloClient } from 'trello.ts';

const client = new TrelloClient({
    apiKey: TRELLO_API_KEY,
    apiSecret: TRELLO_API_SECRET,
    token: TRELLO_TOKEN,
});

export async function handleCreateTrelloCard(userId: string, entities: any): Promise<string> {
    try {
        const { card_name, list_id } = entities;

        if (!card_name || typeof card_name !== 'string') {
            return "Card name is required to create a Trello card.";
        }

        if (!list_id || typeof list_id !== 'string') {
            return "List ID is required to create a Trello card.";
        }

        const card = await client.cards.create({
            name: card_name,
            idList: list_id,
        });

        return `Trello card created: ${card.name}`;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't create the Trello card due to an error.");
    }
}

export async function handleQueryTrelloCards(userId: string, entities: any): Promise<string> {
    try {
        const { list_id } = entities;

        if (!list_id || typeof list_id !== 'string') {
            return "List ID is required to query Trello cards.";
        }

        const cards = await client.lists.getCards(list_id);

        if (!cards.length) {
            return "No cards found in the specified Trello list.";
        }

        let cardList = "Here are the cards in the specified Trello list:\n";
        for (const card of cards) {
            cardList += `- ${card.name}\n`;
        }

        return cardList;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't query the Trello cards due to an error.");
    }
}

export async function handleUpdateTrelloCard(userId: string, entities: any): Promise<string> {
    try {
        const { card_id, card_name } = entities;

        if (!card_id || typeof card_id !== 'string') {
            return "Card ID is required to update a Trello card.";
        }

        if (!card_name || typeof card_name !== 'string') {
            return "Card name is required to update a Trello card.";
        }

        const card = await client.cards.update(card_id, {
            name: card_name,
        });

        return `Trello card updated: ${card.name}`;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't update the Trello card due to an error.");
    }
}

import { decrypt } from '../../_libs/crypto';
import { executeGraphQLQuery } from '../../_libs/graphqlClient';
import { handleError } from '../../_utils/errorHandler';
import { TrelloClient } from 'trello.ts';
async function getTrelloCredentials(userId) {
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
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredentials', userId);
    if (response.user_credentials && response.user_credentials.length === 2) {
        const credentials = {};
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
export async function handleCreateTrelloCard(userId, entities) {
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
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't create the Trello card due to an error.");
    }
}
export async function handleQueryTrelloCards(userId, entities) {
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
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't query the Trello cards due to an error.");
    }
}
export async function handleUpdateTrelloCard(userId, entities) {
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
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't update the Trello card due to an error.");
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidHJlbGxvLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidHJlbGxvLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxPQUFPLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUM3QyxPQUFPLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQztBQUNoRSxPQUFPLEVBQUUsV0FBVyxFQUFFLE1BQU0sMkJBQTJCLENBQUM7QUFDeEQsT0FBTyxFQUFFLFlBQVksRUFBRSxNQUFNLFdBQVcsQ0FBQztBQUV6QyxLQUFLLFVBQVUsb0JBQW9CLENBQ2pDLE1BQWM7SUFFZCxNQUFNLEtBQUssR0FBRzs7Ozs7OztLQU9YLENBQUM7SUFDSixNQUFNLFNBQVMsR0FBRztRQUNoQixNQUFNO0tBQ1AsQ0FBQztJQUNGLE1BQU0sUUFBUSxHQUFHLE1BQU0sbUJBQW1CLENBRXZDLEtBQUssRUFBRSxTQUFTLEVBQUUsb0JBQW9CLEVBQUUsTUFBTSxDQUFDLENBQUM7SUFDbkQsSUFBSSxRQUFRLENBQUMsZ0JBQWdCLElBQUksUUFBUSxDQUFDLGdCQUFnQixDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQUUsQ0FBQztRQUN4RSxNQUFNLFdBQVcsR0FBUSxFQUFFLENBQUM7UUFDNUIsS0FBSyxNQUFNLElBQUksSUFBSSxRQUFRLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztZQUM3QyxXQUFXLENBQUMsSUFBSSxDQUFDLFlBQVksQ0FBQyxHQUFHLE9BQU8sQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztRQUNsRSxDQUFDO1FBQ0QsT0FBTztZQUNMLE1BQU0sRUFBRSxXQUFXLENBQUMsY0FBYztZQUNsQyxRQUFRLEVBQUUsV0FBVyxDQUFDLGdCQUFnQjtTQUN2QyxDQUFDO0lBQ0osQ0FBQztJQUNELE9BQU8sSUFBSSxDQUFDO0FBQ2QsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsc0JBQXNCLENBQzFDLE1BQWMsRUFDZCxRQUFhO0lBRWIsSUFB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LE1BQU07WUFDMUIsS0FBSyxFQUFFLFdBQVcsQ0FBQyxRQUFRO1NBQzVCLENBQUMsQ0FBQztRQUVILE1BQU0sRUFBRSxPQUFPLEVBQUUsU0FBUyxFQUFFLEdBQUcsUUFBUSxDQUFDO1FBRXhDLElBQUksQ0FBQyxPQUFPLElBQUksT0FBTyxPQUFPLEtBQUssUUFBUSxFQUFFLENBQUM7WUFDNUMsT0FBTyw4Q0FBOEMsQ0FBQztRQUN4RCxDQUFDO1FBRUQsSUFBSSxDQUFDLFNBQVMsSUFBSSxPQUFPLFNBQVMsS0FBSyxRQUFRLEVBQUUsQ0FBQztZQUNoRCxPQUFPLGdEQUFnRCxDQUFDO1FBQzFELENBQUM7UUFFRCxNQUFNLElBQUksR0FBRyxNQUFNLE1BQU0sQ0FBQyxLQUFLLENBQUMsTUFBTSxDQUFDLE9BQU8sRUFBRTtZQUM5QyxJQUFJLEVBQUUsU0FBUztTQUNoQixDQUFDLENBQUM7UUFFSCxPQUFPLHdCQUF3QixJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFDN0MsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxXQUFXLENBQ2hCLEtBQUssRUFDTCwyREFBMkQsQ0FDNUQsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgU2tpbGxSZXNwb25zZSB9IGZyb20gJy4uLy4uL3R5cGVzJztcbmltcG9ydCB7IGRlY3J5cHQgfSBmcm9tICcuLi8uLi9fbGlicy9jcnlwdG8nO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSB9IGZyb20gJy4uLy4uL19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IHsgaGFuZGxlRXJyb3IgfSBmcm9tICcuLi8uLi9fdXRpbHMvZXJyb3JIYW5kbGVyJztcbmltcG9ydCB7IFRyZWxsb0NsaWVudCB9IGZyb20gJ3RyZWxsby50cyc7XG5cbmFzeW5jIGZ1bmN0aW9uIGdldFRyZWxsb0NyZWRlbnRpYWxzKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTx7IGFwaUtleTogc3RyaW5nOyBhcGlUb2tlbjogc3RyaW5nIH0gfCBudWxsPiB7XG4gIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICBxdWVyeSBHZXRVc2VyQ3JlZGVudGlhbHMoJHVzZXJJZDogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl9jcmVkZW50aWFscyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBzZXJ2aWNlX25hbWU6IHtfaW46IFtcInRyZWxsb19hcGlfa2V5XCIsIFwidHJlbGxvX2FwaV90b2tlblwiXX19KSB7XG4gICAgICAgICAgICAgICAgc2VydmljZV9uYW1lXG4gICAgICAgICAgICAgICAgZW5jcnlwdGVkX3NlY3JldFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgIHVzZXJJZCxcbiAgfTtcbiAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICB1c2VyX2NyZWRlbnRpYWxzOiB7IHNlcnZpY2VfbmFtZTogc3RyaW5nOyBlbmNyeXB0ZWRfc2VjcmV0OiBzdHJpbmcgfVtdO1xuICB9PihxdWVyeSwgdmFyaWFibGVzLCAnR2V0VXNlckNyZWRlbnRpYWxzJywgdXNlcklkKTtcbiAgaWYgKHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMgJiYgcmVzcG9uc2UudXNlcl9jcmVkZW50aWFscy5sZW5ndGggPT09IDIpIHtcbiAgICBjb25zdCBjcmVkZW50aWFsczogYW55ID0ge307XG4gICAgZm9yIChjb25zdCBjcmVkIG9mIHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMpIHtcbiAgICAgIGNyZWRlbnRpYWxzW2NyZWQuc2VydmljZV9uYW1lXSA9IGRlY3J5cHQoY3JlZC5lbmNyeXB0ZWRfc2VjcmV0KTtcbiAgICB9XG4gICAgcmV0dXJuIHtcbiAgICAgIGFwaUtleTogY3JlZGVudGlhbHMudHJlbGxvX2FwaV9rZXksXG4gICAgICBhcGlUb2tlbjogY3JlZGVudGlhbHMudHJlbGxvX2FwaV90b2tlbixcbiAgICB9O1xuICB9XG4gIHJldHVybiBudWxsO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlQ3JlYXRlVHJlbGxvQ2FyZChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBhbnlcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY3JlZGVudGlhbHMgPSBhd2FpdCBnZXRUcmVsbG9DcmVkZW50aWFscyh1c2VySWQpO1xuICAgIGlmICghY3JlZGVudGlhbHMpIHtcbiAgICAgIHJldHVybiAnVHJlbGxvIGNyZWRlbnRpYWxzIG5vdCBjb25maWd1cmVkIGZvciB0aGlzIHVzZXIuJztcbiAgICB9XG4gICAgY29uc3QgY2xpZW50ID0gbmV3IFRyZWxsb0NsaWVudCh7XG4gICAgICBhcGlLZXk6IGNyZWRlbnRpYWxzLmFwaUtleSxcbiAgICAgIHRva2VuOiBjcmVkZW50aWFscy5hcGlUb2tlbixcbiAgICB9KTtcblxuICAgIGNvbnN0IHsgY2FyZF9uYW1lLCBsaXN0X2lkIH0gPSBlbnRpdGllcztcblxuICAgIGlmICghY2FyZF9uYW1lIHx8IHR5cGVvZiBjYXJkX25hbWUgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gJ0NhcmQgbmFtZSBpcyByZXF1aXJlZCB0byBjcmVhdGUgYSBUcmVsbG8gY2FyZC4nO1xuICAgIH1cblxuICAgIGlmICghbGlzdF9pZCB8fCB0eXBlb2YgbGlzdF9pZCAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnTGlzdCBJRCBpcyByZXF1aXJlZCB0byBjcmVhdGUgYSBUcmVsbG8gY2FyZC4nO1xuICAgIH1cblxuICAgIGNvbnN0IGNhcmQgPSBhd2FpdCBjbGllbnQuY2FyZHMuY3JlYXRlKHtcbiAgICAgIG5hbWU6IGNhcmRfbmFtZSxcbiAgICAgIGlkTGlzdDogbGlzdF9pZCxcbiAgICB9KTtcblxuICAgIHJldHVybiBgVHJlbGxvIGNhcmQgY3JlYXRlZDogJHtjYXJkLm5hbWV9YDtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBjcmVhdGUgdGhlIFRyZWxsbyBjYXJkIGR1ZSB0byBhbiBlcnJvci5cIlxuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVF1ZXJ5VHJlbGxvQ2FyZHMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55XG4pOiBQcm9taXNlPHN0cmluZz4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNyZWRlbnRpYWxzID0gYXdhaXQgZ2V0VHJlbGxvQ3JlZGVudGlhbHModXNlcklkKTtcbiAgICBpZiAoIWNyZWRlbnRpYWxzKSB7XG4gICAgICByZXR1cm4gJ1RyZWxsbyBjcmVkZW50aWFscyBub3QgY29uZmlndXJlZCBmb3IgdGhpcyB1c2VyLic7XG4gICAgfVxuICAgIGNvbnN0IGNsaWVudCA9IG5ldyBUcmVsbG9DbGllbnQoe1xuICAgICAgYXBpS2V5OiBjcmVkZW50aWFscy5hcGlLZXksXG4gICAgICB0b2tlbjogY3JlZGVudGlhbHMuYXBpVG9rZW4sXG4gICAgfSk7XG5cbiAgICBjb25zdCB7IGxpc3RfaWQgfSA9IGVudGl0aWVzO1xuXG4gICAgaWYgKCFsaXN0X2lkIHx8IHR5cGVvZiBsaXN0X2lkICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdMaXN0IElEIGlzIHJlcXVpcmVkIHRvIHF1ZXJ5IFRyZWxsbyBjYXJkcy4nO1xuICAgIH1cblxuICAgIGNvbnN0IGNhcmRzID0gYXdhaXQgY2xpZW50Lmxpc3RzLmdldENhcmRzKGxpc3RfaWQpO1xuXG4gICAgaWYgKCFjYXJkcy5sZW5ndGgpIHtcbiAgICAgIHJldHVybiAnTm8gY2FyZHMgZm91bmQgaW4gdGhlIHNwZWNpZmllZCBUcmVsbG8gbGlzdC4nO1xuICAgIH1cblxuICAgIGxldCBjYXJkTGlzdCA9ICdIZXJlIGFyZSB0aGUgY2FyZHMgaW4gdGhlIHNwZWNpZmllZCBUcmVsbG8gbGlzdDpcXG4nO1xuICAgIGZvciAoY29uc3QgY2FyZCBvZiBjYXJkcykge1xuICAgICAgY2FyZExpc3QgKz0gYC0gJHtjYXJkLm5hbWV9XFxuYDtcbiAgICB9XG5cbiAgICByZXR1cm4gY2FyZExpc3Q7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICByZXR1cm4gaGFuZGxlRXJyb3IoXG4gICAgICBlcnJvcixcbiAgICAgIFwiU29ycnksIEkgY291bGRuJ3QgcXVlcnkgdGhlIFRyZWxsbyBjYXJkcyBkdWUgdG8gYW4gZXJyb3IuXCJcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVVcGRhdGVUcmVsbG9DYXJkKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjcmVkZW50aWFscyA9IGF3YWl0IGdldFRyZWxsb0NyZWRlbnRpYWxzKHVzZXJJZCk7XG4gICAgaWYgKCFjcmVkZW50aWFscykge1xuICAgICAgcmV0dXJuICdUcmVsbG8gY3JlZGVudGlhbHMgbm90IGNvbmZpZ3VyZWQgZm9yIHRoaXMgdXNlci4nO1xuICAgIH1cbiAgICBjb25zdCBjbGllbnQgPSBuZXcgVHJlbGxvQ2xpZW50KHtcbiAgICAgIGFwaUtleTogY3JlZGVudGlhbHMuYXBpS2V5LFxuICAgICAgdG9rZW46IGNyZWRlbnRpYWxzLmFwaVRva2VuLFxuICAgIH0pO1xuXG4gICAgY29uc3QgeyBjYXJkX2lkLCBjYXJkX25hbWUgfSA9IGVudGl0aWVzO1xuXG4gICAgaWYgKCFjYXJkX2lkIHx8IHR5cGVvZiBjYXJkX2lkICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdDYXJkIElEIGlzIHJlcXVpcmVkIHRvIHVwZGF0ZSBhIFRyZWxsbyBjYXJkLic7XG4gICAgfVxuXG4gICAgaWYgKCFjYXJkX25hbWUgfHwgdHlwZW9mIGNhcmRfbmFtZSAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnQ2FyZCBuYW1lIGlzIHJlcXVpcmVkIHRvIHVwZGF0ZSBhIFRyZWxsbyBjYXJkLic7XG4gICAgfVxuXG4gICAgY29uc3QgY2FyZCA9IGF3YWl0IGNsaWVudC5jYXJkcy51cGRhdGUoY2FyZF9pZCwge1xuICAgICAgbmFtZTogY2FyZF9uYW1lLFxuICAgIH0pO1xuXG4gICAgcmV0dXJuIGBUcmVsbG8gY2FyZCB1cGRhdGVkOiAke2NhcmQubmFtZX1gO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICBcIlNvcnJ5LCBJIGNvdWxkbid0IHVwZGF0ZSB0aGUgVHJlbGxvIGNhcmQgZHVlIHRvIGFuIGVycm9yLlwiXG4gICAgKTtcbiAgfVxufVxuIl19
import { getStickyNotesFromFrame } from '../skills/miroSkills';
import { handleCreateTrelloCard } from 'atomic-docker/project/functions/atom-agent/skills/trello';

interface MiroToTrelloResult {
    success: boolean;
    message: string;
    cardsCreated: number;
    stickyNotesProcessed: number;
    errors: string[];
}

export async function runMiroToTrello(
    userId: string,
    boardId: string,
    frameId: string,
    trelloListId: string
): Promise<MiroToTrelloResult> {
    console.log(`[MiroToTrelloOrchestrator] Starting Miro to Trello process for user ${userId}.`);

    const result: MiroToTrelloResult = {
        success: false,
        message: '',
        cardsCreated: 0,
        stickyNotesProcessed: 0,
        errors: [],
    };

    // 1. Get sticky notes from Miro
    const stickyNotesResponse = await getStickyNotesFromFrame(userId, boardId, frameId);
    if (!stickyNotesResponse.ok || !stickyNotesResponse.data) {
        const errorMsg = `Failed to retrieve sticky notes from Miro: ${stickyNotesResponse.error?.message}`;
        console.error(`[MiroToTrelloOrchestrator] ${errorMsg}`);
        result.message = errorMsg;
        return result;
    }

    const stickyNotes = stickyNotesResponse.data;
    if (stickyNotes.length === 0) {
        const successMsg = 'No sticky notes found in the specified Miro frame. No cards to create.';
        console.log(`[MiroToTrelloOrchestrator] ${successMsg}`);
        result.success = true;
        result.message = successMsg;
        return result;
    }

    console.log(`[MiroToTrelloOrchestrator] Found ${stickyNotes.length} sticky notes to process.`);

    // 2. Iterate through sticky notes and create Trello cards
    for (const stickyNote of stickyNotes) {
        result.stickyNotesProcessed++;
        const cardName = stickyNote.data.content;

        if (!cardName) {
            const errorMsg = `Skipping sticky note ID ${stickyNote.id} due to missing content.`;
            console.warn(`[MiroToTrelloOrchestrator] ${errorMsg}`);
            result.errors.push(errorMsg);
            continue;
        }

        const entities = {
            card_name: cardName,
            list_id: trelloListId,
        };

        const trelloResponse = await handleCreateTrelloCard(userId, entities);
        if (trelloResponse.startsWith('Trello card created:')) {
            console.log(`[MiroToTrelloOrchestrator] Successfully created Trello card for sticky note ${stickyNote.id}`);
            result.cardsCreated++;
        } else {
            const errorMsg = `Failed to create Trello card for sticky note ${stickyNote.id}: ${trelloResponse}`;
            console.error(`[MiroToTrelloOrchestrator] ${errorMsg}`);
            result.errors.push(errorMsg);
        }
    }

    result.success = result.errors.length === 0;
    result.message = `Miro to Trello process completed. Created ${result.cardsCreated} cards for ${result.stickyNotesProcessed} sticky notes.`;
    if (result.errors.length > 0) {
        result.message += ` Encountered ${result.errors.length} errors.`;
    }

    console.log(`[MiroToTrelloOrchestrator] ${result.message}`);
    return result;
}

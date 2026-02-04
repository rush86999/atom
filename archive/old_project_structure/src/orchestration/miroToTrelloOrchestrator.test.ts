import { runMiroToTrello } from './miroToTrelloOrchestrator';
import * as miroSkills from '../skills/miroSkills';
import * as trello from 'atomic-docker/project/functions/atom-agent/skills/trello';

// Mock the dependencies
jest.mock('../skills/miroSkills');
jest.mock('atomic-docker/project/functions/atom-agent/skills/trello');

const mockedMiroSkills = miroSkills as jest.Mocked<typeof miroSkills>;
const mockedTrello = trello as jest.Mocked<typeof trello>;

describe('runMiroToTrello', () => {
    const userId = 'test-user';
    const boardId = 'test-board';
    const frameId = 'test-frame';
    const trelloListId = 'test-list';

    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('should run successfully and create Trello cards for sticky notes', async () => {
        const mockStickyNotes = [
            { id: '1', data: { content: 'Sticky note 1' }, type: 'sticky_note' },
            { id: '2', data: { content: 'Sticky note 2' }, type: 'sticky_note' },
        ];

        mockedMiroSkills.getStickyNotesFromFrame.mockResolvedValue({ ok: true, data: mockStickyNotes } as any);
        mockedTrello.handleCreateTrelloCard.mockResolvedValue('Trello card created: Sticky note 1');

        const result = await runMiroToTrello(userId, boardId, frameId, trelloListId);

        expect(result.success).toBe(true);
        expect(result.stickyNotesProcessed).toBe(2);
        expect(result.cardsCreated).toBe(2);
        expect(result.errors.length).toBe(0);
        expect(mockedMiroSkills.getStickyNotesFromFrame).toHaveBeenCalledTimes(1);
        expect(mockedTrello.handleCreateTrelloCard).toHaveBeenCalledTimes(2);
    });

    it('should handle the case where there are no sticky notes', async () => {
        mockedMiroSkills.getStickyNotesFromFrame.mockResolvedValue({ ok: true, data: [] } as any);

        const result = await runMiroToTrello(userId, boardId, frameId, trelloListId);

        expect(result.success).toBe(true);
        expect(result.message).toContain('No sticky notes found');
        expect(result.stickyNotesProcessed).toBe(0);
        expect(result.cardsCreated).toBe(0);
        expect(mockedTrello.handleCreateTrelloCard).not.toHaveBeenCalled();
    });

    it('should handle errors from the Miro API', async () => {
        mockedMiroSkills.getStickyNotesFromFrame.mockResolvedValue({ ok: false, error: { message: 'Miro API error' } } as any);

        const result = await runMiroToTrello(userId, boardId, frameId, trelloListId);

        expect(result.success).toBe(false);
        expect(result.message).toContain('Failed to retrieve sticky notes from Miro');
    });

    it('should handle errors from the Trello API', async () => {
        const mockStickyNotes = [
            { id: '1', data: { content: 'Sticky note 1' }, type: 'sticky_note' },
        ];
        mockedMiroSkills.getStickyNotesFromFrame.mockResolvedValue({ ok: true, data: mockStickyNotes } as any);
        mockedTrello.handleCreateTrelloCard.mockResolvedValue('Trello API error');

        const result = await runMiroToTrello(userId, boardId, frameId, trelloListId);

        expect(result.success).toBe(false);
        expect(result.errors.length).toBe(1);
        expect(result.errors[0]).toContain('Failed to create Trello card');
        expect(result.cardsCreated).toBe(0);
    });

    it('should skip sticky notes with no content', async () => {
        const mockStickyNotes = [
            { id: '1', data: { content: '' }, type: 'sticky_note' },
        ];
        mockedMiroSkills.getStickyNotesFromFrame.mockResolvedValue({ ok: true, data: mockStickyNotes } as any);

        const result = await runMiroToTrello(userId, boardId, frameId, trelloListId);

        expect(result.success).toBe(false);
        expect(result.errors.length).toBe(1);
        expect(result.errors[0]).toContain('Skipping sticky note ID 1 due to missing content');
        expect(result.stickyNotesProcessed).toBe(1);
        expect(result.cardsCreated).toBe(0);
        expect(mockedTrello.handleCreateTrelloCard).not.toHaveBeenCalled();
    });
});

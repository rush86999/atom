// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, beforeEach, describe, it, expect } from 'vitest';
import { BrowserCanvas } from '../BrowserCanvas';

// Mock hooks
vi.mock('@/hooks/useCanvasGuidance', () => ({
    useCanvasGuidance: () => ({
        currentAction: null,
        actionHistory: [],
        wsConnected: true,
        handleApprove: vi.fn(),
        handleEdit: vi.fn(),
        handleSkip: vi.fn(),
        handleCancel: vi.fn(),
        handleGuidance: vi.fn()
    })
}));

vi.mock('@/hooks/use-media-query', () => ({
    useMediaQuery: () => false
}));

// Mock sonner toast
vi.mock('sonner', () => ({
    toast: { success: vi.fn(), error: vi.fn() }
}));

describe('BrowserCanvas', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders browser control panel', () => {
        render(<BrowserCanvas canvasId="test-canvas" />);
        expect(screen.getByText('No browser session')).toBeInTheDocument();
    });

    it('has create session button', () => {
        render(<BrowserCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Create Browser Session')).toBeInTheDocument();
    });

    it('shows execution mode selector', () => {
        render(<BrowserCanvas canvasId="test-canvas" />);
        expect(screen.getByText(/cloud/i)).toBeInTheDocument();
    });

    describe('with active session', () => {
        beforeEach(() => {
            // Mock successful fetch for session creation
            

=> ({
                    session_id: 'test-session',
                    current_url: 'https://example.com',
                    page_title: 'Example',
                    screenshot: null
                })
            }) as any;
        });

        it('shows navigation controls after creating session', async () => {
            render(<BrowserCanvas canvasId="test-canvas" />);

            // Click create session button
            const createButton = screen.getByText('Create Browser Session');
            fireEvent.click(createButton);

            // Wait for state updates and navigation elements to appear
            await waitFor(() => {
                expect(screen.getByPlaceholderText(/enter url/i)).toBeInTheDocument();
            });
        });

        it('has navigation buttons after session creation', async () => {
            render(<BrowserCanvas canvasId="test-canvas" />);

            const createButton = screen.getByText('Create Browser Session');
            fireEvent.click(createButton);

            await waitFor(() => {
                const buttons = screen.getAllByRole('button');
                expect(buttons.length).toBeGreaterThan(0);
            });
        });

        it('has go button after session creation', async () => {
            render(<BrowserCanvas canvasId="test-canvas" />);

            const createButton = screen.getByText('Create Browser Session');
            fireEvent.click(createButton);

            await waitFor(() => {
                expect(screen.getByRole('button', { name: 'Go' })).toBeInTheDocument();
            });
        });
    });
});

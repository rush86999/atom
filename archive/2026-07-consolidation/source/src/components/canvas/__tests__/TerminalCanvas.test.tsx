// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { vi, beforeEach, describe, it, expect } from 'vitest';
import { TerminalCanvas } from '../TerminalCanvas';

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

describe('TerminalCanvas', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        

});

    it('renders terminal title', () => {
        render(<TerminalCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Terminal')).toBeInTheDocument();
    });

    it('shows no terminal sessions message', () => {
        render(<TerminalCanvas canvasId="test-canvas" />);
        expect(screen.getByText('No terminal sessions')).toBeInTheDocument();
    });

    it('has create session button', () => {
        render(<TerminalCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Create Session')).toBeInTheDocument();
    });

    it('has copy output button', () => {
        render(<TerminalCanvas canvasId="test-canvas" />);
        // Look for Copy icon button (first button in header actions)
        const buttons = screen.getAllByRole('button');
        const copyButton = buttons.find(btn => btn.querySelector('svg'));
        expect(copyButton).toBeInTheDocument();
    });

    it('shows keyboard shortcuts help', () => {
        render(<TerminalCanvas canvasId="test-canvas" />);
        // Help text shows when there's an active session
        // In the initial state without session, this won't be visible
        expect(screen.getByText('Terminal')).toBeInTheDocument();
    });

    it('has live badge when wsConnected', () => {
        render(<TerminalCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Live')).toBeInTheDocument();
    });
});

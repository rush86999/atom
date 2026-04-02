// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { vi, beforeEach, describe, it, expect } from 'vitest';
import { DesktopCanvas } from '../DesktopCanvas';

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

// Mock sonner toast
vi.mock('sonner', () => ({
    toast: { success: vi.fn(), error: vi.fn() }
}));

// Mock fetch

as any;

describe('DesktopCanvas', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders desktop canvas title', () => {
        render(<DesktopCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Desktop Canvas')).toBeInTheDocument();
    });

    it('shows no desktop connected message', () => {
        render(<DesktopCanvas canvasId="test-canvas" />);
        expect(screen.getByText('No desktop connected')).toBeInTheDocument();
    });

    it('shows connect desktop button', () => {
        render(<DesktopCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Connect Desktop')).toBeInTheDocument();
    });

    it('has refresh button', () => {
        render(<DesktopCanvas canvasId="test-canvas" />);
        // Look for button with title "Test Connection"
        const buttons = screen.getAllByRole('button');
        const refreshButton = buttons.find(btn => btn.getAttribute('title') === 'Test Connection');
        expect(refreshButton).toBeInTheDocument();
    });

    it('displays connection status', () => {
        render(<DesktopCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    it('has command input', () => {
        render(<DesktopCanvas canvasId="test-canvas" />);
        expect(screen.getByPlaceholderText(/connect to a desktop first/i)).toBeInTheDocument();
    });

    it('shows desktop sessions section', () => {
        render(<DesktopCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Desktop Sessions')).toBeInTheDocument();
    });
});

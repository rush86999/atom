// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { vi, beforeEach, describe, it, expect } from 'vitest';
import { AppCanvas } from '../AppCanvas';

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

describe('AppCanvas', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders configuration form when not configured', () => {
        render(<AppCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Configure Application')).toBeInTheDocument();
    });

    it('has URL input field', () => {
        render(<AppCanvas canvasId="test-canvas" />);
        expect(screen.getByPlaceholderText('https://example.com')).toBeInTheDocument();
    });

    it('has name input field', () => {
        render(<AppCanvas canvasId="test-canvas" />);
        expect(screen.getByLabelText('App Name')).toBeInTheDocument();
    });

    it('has load button', () => {
        render(<AppCanvas canvasId="test-canvas" />);
        expect(screen.getByText('Load Application')).toBeInTheDocument();
    });
});

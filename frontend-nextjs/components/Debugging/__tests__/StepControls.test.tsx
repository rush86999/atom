/**
 * StepControls Component Tests
 *
 * Tests verify the REAL StepControls component
 * (components/Debugging/StepControls.tsx, a NAMED export):
 * - Renders the five step actions (Step Over/Into/Out, Continue, Pause)
 * - Disables everything when no session exists or disabled prop is set
 * - POSTs { session_id, action } to /api/workflows/debug/step
 * - Calls onStep(action) after a successful step
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import StepControls from '../StepControls';

const ACTIONS = ['step_over', 'step_into', 'step_out', 'continue', 'pause'];

describe('StepControls', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: async () => ({ success: true }) })
    // The mocked response is a partial fetch Response; cast to satisfy the fetch signature.
    ) as unknown as typeof global.fetch;
  });

  // Test 1: renders all five step action buttons with their labels
  test('renders all five step control buttons', () => {
    render(<StepControls sessionId="ses-1" />);

    expect(screen.getByRole('button', { name: /step over/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /step into/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /step out/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /step controls/i })).toBeInTheDocument();
  });

  // Test 2: no session → all buttons disabled + hint shown
  test('disables all controls and shows a hint when no session is active', () => {
    render(<StepControls sessionId={null} />);

    for (const action of ACTIONS) {
      const label = action.replace('_', ' ');
      expect(screen.getByRole('button', { name: new RegExp(label, 'i') })).toBeDisabled();
    }
    expect(
      screen.getByText(/start a debug session to enable step controls/i)
    ).toBeInTheDocument();
  });

  // Test 3: disabled prop disables every button even with a session
  test('disabled prop disables all controls', () => {
    render(<StepControls sessionId="ses-1" disabled />);

    for (const action of ACTIONS) {
      const label = action.replace('_', ' ');
      expect(screen.getByRole('button', { name: new RegExp(label, 'i') })).toBeDisabled();
    }
  });

  // Test 4: posts the action and session id to the step endpoint
  test('posts { session_id, action } when a step button is clicked', async () => {
    render(<StepControls sessionId="ses-1" />);

    fireEvent.click(screen.getByRole('button', { name: /step over/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/step',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: 'ses-1', action: 'step_over' }),
        })
      );
    });
  });

  // Test 5: onStep callback fires with the executed action
  test('calls onStep with the action after a successful step', async () => {
    const onStep = jest.fn();
    render(<StepControls sessionId="ses-1" onStep={onStep} />);

    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    await waitFor(() => {
      expect(onStep).toHaveBeenCalledWith('continue');
    });
  });

  // Test 6: every action posts its own action name
  test('each action posts its distinct action name', async () => {
    render(<StepControls sessionId="ses-1" />);

    fireEvent.click(screen.getByRole('button', { name: /pause/i }));
    fireEvent.click(screen.getByRole('button', { name: /step into/i }));

    await waitFor(() => {
      const bodies = (global.fetch as jest.Mock).mock.calls.map(
        ([, init]: [string, RequestInit]) => JSON.parse(String(init.body))
      );
      expect(bodies).toEqual(
        expect.arrayContaining([
          { session_id: 'ses-1', action: 'pause' },
          { session_id: 'ses-1', action: 'step_into' },
        ])
      );
    });
  });
});

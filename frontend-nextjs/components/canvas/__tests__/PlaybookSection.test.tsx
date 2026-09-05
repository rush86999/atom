/**
 * PlaybookSection tests (Training tab review queue — Playbook Journey P1+P4)
 *
 * Mocks lib/playbook-api and verifies the supervisor contract: segmented
 * queue driven by approval_state, draft-count reporting for the Training tab
 * badge, one-click approve (eval-gate failures surface as errors, drafts
 * stay), the "new rules from your corrections" learned-draft banner, and the
 * new-playbook mini-wizard's field parsing.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockApi = {
  listPlaybooks: jest.fn(),
  createPlaybook: jest.fn(),
  updatePlaybook: jest.fn(),
  approvePlaybook: jest.fn(),
  retirePlaybook: jest.fn(),
};

jest.mock('@/lib/playbook-api', () => ({
  __esModule: true,
  ...mockApi,
}));

import { PlaybookSection } from '../PlaybookSection';
import type { Playbook } from '@/lib/playbook-api';

function makePlaybook(overrides: Partial<Playbook> = {}): Playbook {
  return {
    id: 'pb-1',
    name: '[grounding] "in stock"',
    description: 'Drafted by correction reflection on canvas 8f3a…',
    trigger_canvas_type: 'email',
    trigger_keywords: ['stock'],
    steps: ['Grounding: do not state "in stock" as established fact.'],
    template_questions: [],
    source: 'learned',
    approval_state: 'draft',
    version: 4,
    ...overrides,
  };
}

beforeEach(() => {
  jest.resetAllMocks();
  window.localStorage.clear();
  mockApi.listPlaybooks.mockResolvedValue([]);
});

describe('PlaybookSection', () => {
  test('renders drafts by default and reports the draft count for the tab badge', async () => {
    const onDraftsCountChange = jest.fn();
    mockApi.listPlaybooks.mockResolvedValue([
      makePlaybook(),
      makePlaybook({ id: 'pb-2', name: 'Quote process', source: 'authored', approval_state: 'approved', version: 1 }),
    ]);
    render(<PlaybookSection isSupervisor onDraftsCountChange={onDraftsCountChange} />);

    await waitFor(() => expect(screen.getByTestId('playbook-name')).toBeInTheDocument());
    expect(onDraftsCountChange).toHaveBeenCalledWith(1);
    expect(screen.getByTestId('playbook-seen')).toHaveTextContent('seen 4×');
    expect(screen.getByTestId('playbook-segment-approved')).toHaveTextContent('Active (1)');
  });

  test('approve promotes the draft and reloads the queue', async () => {
    mockApi.listPlaybooks
      .mockResolvedValueOnce([makePlaybook()])
      .mockResolvedValueOnce([makePlaybook({ approval_state: 'approved' })]);
    mockApi.approvePlaybook.mockResolvedValue(undefined);
    render(<PlaybookSection isSupervisor />);

    await waitFor(() => screen.getByTestId('playbook-approve'));
    fireEvent.click(screen.getByTestId('playbook-approve'));

    await waitFor(() => expect(mockApi.approvePlaybook).toHaveBeenCalledWith('pb-1'));
    await waitFor(() => expect(mockApi.listPlaybooks).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText(/now active/)).toBeInTheDocument());
  });

  test('an eval-gate block surfaces as an error and keeps the draft queued', async () => {
    mockApi.listPlaybooks.mockResolvedValue([makePlaybook()]);
    mockApi.approvePlaybook.mockRejectedValue(
      new Error('Blocked by the eval gate: 1 originating eval(s) regressed.')
    );
    render(<PlaybookSection isSupervisor />);

    await waitFor(() => screen.getByTestId('playbook-approve'));
    fireEvent.click(screen.getByTestId('playbook-approve'));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/eval gate/i)
    );
    // The draft is still on the review queue.
    expect(screen.getByTestId('playbook-card')).toBeInTheDocument();
  });

  test('first-time learned drafts trigger the corrections banner', async () => {
    mockApi.listPlaybooks.mockResolvedValue([makePlaybook()]);
    render(<PlaybookSection isSupervisor />);

    await waitFor(() =>
      expect(screen.getByTestId('playbook-new-learned')).toHaveTextContent(
        /1 new rule drafted from your corrections/
      )
    );
    // Dismissed state persists for the same draft id.
    fireEvent.click(screen.getByTestId('playbook-notice-dismiss'));
    expect(screen.queryByTestId('playbook-new-learned')).not.toBeInTheDocument();
  });

  test('non-supervisors see the queue but get no action buttons or wizard', async () => {
    mockApi.listPlaybooks.mockResolvedValue([makePlaybook()]);
    render(<PlaybookSection isSupervisor={false} />);

    await waitFor(() => screen.getByTestId('playbook-card'));
    expect(screen.queryByTestId('playbook-approve')).not.toBeInTheDocument();
    expect(screen.queryByTestId('playbook-wizard-toggle')).not.toBeInTheDocument();
  });

  test('learned drafts show autonomy-latch progress (Journey §6)', async () => {
    mockApi.listPlaybooks.mockResolvedValue([
      makePlaybook({ id: 'pb-streak', auto_latch: { passes: 2, threshold: 3 } }),
      makePlaybook({
        id: 'pb-held',
        name: '[grounding] "ships free"',
        trigger_canvas_type: 'email',
        auto_latch: { passes: 1, threshold: 3, blocked: 'Send email is human_always — external blast radius keeps the approval gate.' },
      }),
    ]);
    render(<PlaybookSection isSupervisor />);

    await waitFor(() => screen.getByTestId('playbook-latch'));
    expect(screen.getByTestId('playbook-latch')).toHaveTextContent('auto-latch 2/3');
    const paused = screen.getByTestId('playbook-latch-paused');
    expect(paused).toHaveTextContent('auto-approve paused');
    expect(paused).toHaveAttribute('title', expect.stringContaining('human_always'));
  });

  test('the mini-wizard creates an authored playbook with parsed fields (P4)', async () => {
    mockApi.createPlaybook.mockResolvedValue('approved');
    render(<PlaybookSection isSupervisor />);

    await waitFor(() => screen.getByTestId('playbook-wizard-toggle'));
    fireEvent.click(screen.getByTestId('playbook-wizard-toggle'));
    fireEvent.change(screen.getByTestId('playbook-wizard-name'), {
      target: { value: 'Data discovery → quote' },
    });
    fireEvent.change(screen.getByTestId('playbook-wizard-canvas-type'), {
      target: { value: 'spreadsheet' },
    });
    fireEvent.change(screen.getByTestId('playbook-wizard-keywords'), {
      target: { value: 'ROI, quote' },
    });
    fireEvent.change(screen.getByTestId('playbook-wizard-steps'), {
      target: { value: 'Query the CRM for open opportunities\nCross-check the price list' },
    });
    fireEvent.change(screen.getByTestId('playbook-wizard-questions'), {
      target: { value: 'Which quarter?\n' },
    });
    fireEvent.click(screen.getByTestId('playbook-wizard-submit'));

    await waitFor(() =>
      expect(mockApi.createPlaybook).toHaveBeenCalledWith({
        name: 'Data discovery → quote',
        trigger_canvas_type: 'spreadsheet',
        trigger_keywords: ['roi', 'quote'],
        steps: ['Query the CRM for open opportunities', 'Cross-check the price list'],
        template_questions: ['Which quarter?'],
      })
    );
    await waitFor(() => expect(screen.getByText(/created and active/)).toBeInTheDocument());
  });
});

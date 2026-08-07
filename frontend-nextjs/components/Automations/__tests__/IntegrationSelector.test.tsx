/**
 * IntegrationSelector Component Tests
 *
 * Tests verify the real IntegrationSelector component
 * (components/Automations/IntegrationSelector.tsx, a DEFAULT export):
 * - Loading state ("Checking connections...")
 * - Health check per integration (GET /api/integrations/:id/health)
 * - Connected integrations are clickable → onSelect(id)
 * - Disconnected integrations are not selectable and show Connect button
 * - Connect button opens /integrations/:id in a new tab
 * - Selected integration styling when selectedIntegrationId is provided
 *
 * Uses the shared MSW server (tests/mocks/server.ts).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import IntegrationSelector from '../IntegrationSelector';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const CONNECTED_IDS = ['gmail', 'slack', 'github'];
const DISCONNECTED_IDS = ['outlook', 'salesforce', 'hubspot'];

function useHealthHandlers() {
  server.use(
    ...CONNECTED_IDS.map((id) =>
      rest.get(`/api/integrations/${id}/health`, (req, res, ctx) => res(ctx.status(200)))
    ),
    ...DISCONNECTED_IDS.map((id) =>
      rest.get(`/api/integrations/${id}/health`, (req, res, ctx) => res(ctx.status(500)))
    )
  );
}

describe('IntegrationSelector', () => {
  const mockOnSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    useHealthHandlers();
  });

  it('shows the loading state while health checks run', () => {
    render(<IntegrationSelector onSelect={mockOnSelect} />);
    expect(screen.getByText('Checking connections...')).toBeInTheDocument();
  });

  it('renders all supported integrations after health checks resolve', async () => {
    render(<IntegrationSelector onSelect={mockOnSelect} />);

    await waitFor(() => {
      expect(screen.getByText('Gmail')).toBeInTheDocument();
      expect(screen.getByText('Slack')).toBeInTheDocument();
      expect(screen.getByText('GitHub')).toBeInTheDocument();
      expect(screen.getByText('Outlook')).toBeInTheDocument();
      expect(screen.getByText('Salesforce')).toBeInTheDocument();
      expect(screen.getByText('HubSpot')).toBeInTheDocument();
    });
  });

  it('calls onSelect with the integration id for a connected integration', async () => {
    const user = userEvent.setup();
    render(<IntegrationSelector onSelect={mockOnSelect} />);

    await user.click(await screen.findByText('Gmail'));
    expect(mockOnSelect).toHaveBeenCalledTimes(1);
    expect(mockOnSelect).toHaveBeenCalledWith('gmail');
  });

  it('does not call onSelect for a disconnected integration', async () => {
    const user = userEvent.setup();
    render(<IntegrationSelector onSelect={mockOnSelect} />);

    await user.click(await screen.findByText('HubSpot'));
    expect(mockOnSelect).not.toHaveBeenCalled();
  });

  it('opens the connect page when the Connect button is clicked', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    const user = userEvent.setup();
    render(<IntegrationSelector onSelect={mockOnSelect} />);

    // Connect buttons render for disconnected integrations in list order:
    // outlook (0), salesforce (1), hubspot (2)
    await user.click((await screen.findAllByRole('button', { name: /connect/i }))[2]);
    expect(openSpy).toHaveBeenCalledWith('/integrations/hubspot', '_blank');
    expect(mockOnSelect).not.toHaveBeenCalled();
    openSpy.mockRestore();
  });

  it('shows a Connect button for disconnected and none for connected integrations', async () => {
    render(<IntegrationSelector onSelect={mockOnSelect} />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /connect/i })).toHaveLength(3);
    });
    // Connected integrations have no Connect button inside their card
    expect(screen.queryByText('Gmail')?.closest('div')?.querySelector('button')).toBeNull();
  });

  it('applies selected styling when selectedIntegrationId matches', async () => {
    const { container } = render(
      <IntegrationSelector onSelect={mockOnSelect} selectedIntegrationId="slack" />
    );

    await waitFor(() => {
      expect(screen.getByText('Slack')).toBeInTheDocument();
    });

    const cards = Array.from(container.querySelectorAll('[class*="border-2"]'));
    const selected = cards.find((card) => card.textContent?.includes('Slack'));
    expect(selected?.className).toContain('border-blue-500');
  });
});

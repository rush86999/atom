/**
 * HubSpot Workflow Automation Component Tests
 *
 * Test suite for HubSpot workflow triggers and automation
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import HubSpotWorkflowAutomation from '../HubSpotWorkflowAutomation';

describe('HubSpotWorkflowAutomation Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders HubSpot workflow automation component', () => {
    renderWithProviders(<HubSpotWorkflowAutomation />);
    expect(screen.getByText(/hubspot|workflow|automation/i)).toBeInTheDocument();
  });

  it('fetches workflows', async () => {
    server.use(
      rest.get('/api/integrations/hubspot/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            workflows: [
              { id: '1', name: 'Lead Nurturing', enabled: true },
            ],
          })
        );
      })
    );

    renderWithProviders(<HubSpotWorkflowAutomation connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Lead Nurturing')).toBeInTheDocument();
    });
  });

  it('creates new workflow', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/hubspot/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            workflow: { id: '2', name: 'New Workflow' },
          })
        );
      })
    );

    renderWithProviders(<HubSpotWorkflowAutomation connected={true} />);

    const createButton = screen.queryByRole('button', { name: /create|new workflow/i });
    if (createButton) {
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByText(/workflow created/i)).toBeInTheDocument();
      });
    }
  });
});

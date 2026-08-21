/**
 * IntegrationsSection Component Tests
 *
 * Round 80: mobile had zero integration visibility. This section surfaces
 * read-only connection status from /api/v1/integrations/health.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react-native';

import { IntegrationsSection } from '../../../components/settings/IntegrationsSection';
import {
  getIntegrationHealth,
} from '../../../services/integrationService';

jest.mock('../../../services/integrationService');

const mockedGetHealth = getIntegrationHealth as jest.Mock;

const healthyFixture = {
  total_integrations: 3,
  healthy_integrations: 2,
  configured_integrations: 3,
  enabled_integrations: 3,
  overall_health_percentage: 66.7,
  integration_status: [
    { service_name: 'slack', status: 'healthy', enabled: true, configured: true },
    { service_name: 'xero', status: 'healthy', enabled: true, configured: true },
    { service_name: 'zoom', status: 'unhealthy', enabled: true, configured: false, error_message: 'not configured' },
  ],
};

describe('IntegrationsSection', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows the summary line once health resolves', async () => {
    mockedGetHealth.mockResolvedValue(healthyFixture);

    render(<IntegrationsSection />);

    await waitFor(() =>
      expect(screen.getByText('2 of 3 healthy')).toBeTruthy()
    );
  });

  it('lists per-service rows with status when expanded', async () => {
    mockedGetHealth.mockResolvedValue(healthyFixture);

    render(<IntegrationsSection expanded />);

    await waitFor(() => {
      expect(screen.getByTestId('integration-row-slack')).toBeTruthy();
    });
    expect(screen.getByTestId('integration-row-xero')).toBeTruthy();
    expect(screen.getByTestId('integration-row-zoom')).toBeTruthy();
    expect(screen.getAllByText(/healthy/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/unhealthy/i)).toBeTruthy();
  });

  it('shows an error message when the fetch fails', async () => {
    mockedGetHealth.mockRejectedValue(new Error('backend down'));

    render(<IntegrationsSection />);

    await waitFor(() =>
      expect(screen.getByText(/backend down/i)).toBeTruthy()
    );
  });

  it('toggle press invokes onToggle (expand/collapse)', async () => {
    mockedGetHealth.mockResolvedValue(healthyFixture);
    const onToggle = jest.fn();

    render(<IntegrationsSection onToggle={onToggle} />);
    await waitFor(() => expect(screen.getByTestId('integrations-section-header')).toBeTruthy());

    fireEvent.press(screen.getByTestId('integrations-section-header'));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});

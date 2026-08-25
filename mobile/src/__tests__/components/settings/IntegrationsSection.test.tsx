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
  getOAuthAuthorizeUrl,
  disconnectIntegration,
} from '../../../services/integrationService';

jest.mock('../../../services/integrationService');
jest.mock('react-native/Libraries/AppState/AppState', () => ({
  addEventListener: jest.fn(() => ({ remove: jest.fn() })),
}));

const mockedGetHealth = getIntegrationHealth as jest.Mock;
const mockedDisconnect = disconnectIntegration as jest.Mock;
const mockedGetUrl = getOAuthAuthorizeUrl as jest.Mock;

const healthyFixture = {
  total_integrations: 3,
  healthy_integrations: 2,
  configured_integrations: 3,
  enabled_integrations: 3,
  overall_health_percentage: 66.7,
  integration_status: [
    { service_name: 'slack', status: 'healthy', enabled: true, configured: true },
    { service_name: 'notion', status: 'healthy', enabled: true, configured: true },
    { service_name: 'dropbox', status: 'unhealthy', enabled: true, configured: false, error_message: 'not configured' },
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
    expect(screen.getByTestId('integration-row-notion')).toBeTruthy();
    expect(screen.getByTestId('integration-row-dropbox')).toBeTruthy();
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

describe('IntegrationsSection disconnect (v1.5)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedGetHealth.mockResolvedValue(healthyFixture);
    mockedDisconnect.mockResolvedValue({ disconnected: true, message: 'ok' });
  });

  it('offers Disconnect only for known oauth providers that are healthy', async () => {
    render(<IntegrationsSection expanded />);
    await waitFor(() =>
      expect(screen.getByTestId('disconnect-notion')).toBeTruthy()
    );
    // slack is in the allowlist too
    expect(screen.getByTestId('disconnect-slack')).toBeTruthy();
    // zoom unhealthy + not an oauth provider -> no button
    expect(screen.queryByTestId('disconnect-dropbox')).toBeNull();
  });

  it('revokes via the service and reloads health after disconnect', async () => {
    render(<IntegrationsSection expanded />);
    const btn = await screen.findByTestId('disconnect-notion');
    fireEvent.press(btn);
    await waitFor(() => expect(mockedDisconnect).toHaveBeenCalledWith('notion'));
    await waitFor(() => expect(mockedGetHealth.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('surfaces errors when disconnect fails', async () => {
    mockedDisconnect.mockRejectedValue(new Error('revoke denied'));
    render(<IntegrationsSection expanded />);
    const btn = await screen.findByTestId('disconnect-notion');
    fireEvent.press(btn);
    await waitFor(() => expect(screen.getByText(/revoke denied/i)).toBeTruthy());
  });
});

describe('IntegrationsSection connect (v2)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedGetHealth.mockResolvedValue(healthyFixture);
    mockedGetUrl.mockResolvedValue('https://provider.example/oauth/authorize');
    const { Linking } = require('react-native');
    jest.spyOn(Linking, 'openURL').mockResolvedValue(undefined);
  });

  it('offers Connect for unhealthy allowlisted providers', async () => {
    render(<IntegrationsSection expanded />);
    await waitFor(() =>
      expect(screen.getByTestId('connect-dropbox')).toBeTruthy()
    );
    // healthy ones get Disconnect, not Connect
    expect(screen.queryByTestId('connect-notion')).toBeNull();
  });

  it('opens the resolved OAuth URL via the system browser', async () => {
    const { Linking } = require('react-native');
    render(<IntegrationsSection expanded />);
    fireEvent.press(await screen.findByTestId('connect-dropbox'));
    await waitFor(() =>
      expect(Linking.openURL).toHaveBeenCalledWith(
        'https://provider.example/oauth/authorize'
      )
    );
    expect(mockedGetUrl).toHaveBeenCalledWith('dropbox');
  });

  it('surfaces errors when the authorize URL cannot be fetched', async () => {
    mockedGetUrl.mockRejectedValue(new Error('oauth not configured'));
    render(<IntegrationsSection expanded />);
    fireEvent.press(await screen.findByTestId('connect-dropbox'));
    await waitFor(() =>
      expect(screen.getByText(/oauth not configured/i)).toBeTruthy()
    );
  });
});

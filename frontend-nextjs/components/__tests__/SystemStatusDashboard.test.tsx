/**
 * SystemStatusDashboard Component Tests
 *
 * Tests verify the real SystemStatusDashboard component
 * (components/SystemStatusDashboard.tsx):
 * - loading state ("Loading system status...") before the API resolves
 * - overall status badge, uptime, CPU/memory/disk cards, services cards,
 *   registered services / AI providers badges, system information, feature
 *   status cards
 * - non-healthy overall status renders the destructive alert
 * - refresh button re-fetches all four APIs
 * - API failure toasts "Failed to fetch system status"
 *
 * APIs (via @/lib/api, mocked): systemAPI.getSystemStatus,
 * serviceRegistryAPI.getServices, byokAPI.getProviders,
 * workflowAPI.getTemplates
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mockGetSystemStatus = jest.fn();
const mockGetServices = jest.fn();
const mockGetProviders = jest.fn();
const mockGetTemplates = jest.fn();
jest.mock('@/lib/api', () => ({
  systemAPI: { getSystemStatus: mockGetSystemStatus },
  serviceRegistryAPI: { getServices: mockGetServices },
  byokAPI: { getProviders: mockGetProviders },
  workflowAPI: { getTemplates: mockGetTemplates },
}));

import SystemStatusDashboard from '../SystemStatusDashboard';

const systemStatusPayload = {
  timestamp: '2026-08-07T10:00:00.000Z',
  overall_status: 'degraded',
  system: {
    platform: { system: 'Darwin', node: 'macbook.local' },
    python: { version: '3.11.4 (main)' },
    process: { pid: 12345 },
  },
  resources: {
    cpu: { percent: 38.25 },
    memory: { system_used_percent: 55.5, rss_mb: 410 },
    disk: { percent: 61.25, free_gb: 120 },
  },
  services: {
    api: { name: 'API Server', status: 'healthy', response_time_ms: 12 },
    worker: { name: 'Worker', status: 'unreachable', error: 'Connection refused' },
  },
  features: {
    voice: { status: 'operational', description: 'Voice interface', providers: 2 },
    canvas: { status: 'degraded', description: 'Canvas editor', templates_available: 5 },
  },
  uptime: { system_seconds: 90061, process_seconds: 3661 },
  version: '1.2.3',
};

const servicesPayload = {
  services: [
    { id: 'svc-1', name: 'email-service' },
    { id: 'svc-2', name: 'calendar-service' },
  ],
};

const providersPayload = {
  providers: [
    { id: 'openai', name: 'OpenAI' },
    { id: 'anthropic', name: 'Anthropic' },
  ],
};

const templatesPayload = {
  templates: [{ id: 'tpl-1', name: 'Daily Report' }],
};

describe('SystemStatusDashboard', () => {
  let statusFetches: number;

  beforeEach(() => {
    jest.clearAllMocks();
    statusFetches = 0;

    mockGetSystemStatus.mockImplementation(() => {
      statusFetches += 1;
      return Promise.resolve({ data: systemStatusPayload });
    });
    mockGetServices.mockResolvedValue({ data: servicesPayload });
    mockGetProviders.mockResolvedValue({ data: providersPayload });
    mockGetTemplates.mockResolvedValue({ data: templatesPayload });
  });

  it('shows the loading state before the APIs resolve', () => {
    mockGetSystemStatus.mockReturnValue(new Promise(() => {}));
    render(<SystemStatusDashboard />);
    expect(screen.getByText('Loading system status...')).toBeInTheDocument();
  });

  it('renders the header, status badge and resource cards', async () => {
    render(<SystemStatusDashboard />);

    expect(await screen.findByText('System Status Dashboard')).toBeInTheDocument();
    expect(screen.getByText('DEGRADED')).toBeInTheDocument();
    expect(screen.getByText('1d 1h 1m')).toBeInTheDocument();
    expect(screen.getByText(/Process: 1h 1m/)).toBeInTheDocument();
    expect(screen.getByText('38.3%')).toBeInTheDocument();
    expect(screen.getByText('55.5%')).toBeInTheDocument();
    expect(screen.getByText('410 MB used')).toBeInTheDocument();
    expect(screen.getByText('61.3%')).toBeInTheDocument();
    expect(screen.getByText('120 GB free')).toBeInTheDocument();
  });

  it('renders service cards with status, response time and error', async () => {
    render(<SystemStatusDashboard />);

    expect(await screen.findByText('Services Status')).toBeInTheDocument();
    expect(screen.getByText('API Server')).toBeInTheDocument();
    expect(screen.getByText('Worker')).toBeInTheDocument();
    expect(screen.getByText('12ms')).toBeInTheDocument();
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });

  it('renders registered services, AI providers and system information', async () => {
    render(<SystemStatusDashboard />);

    expect(await screen.findByText('Services & AI Providers')).toBeInTheDocument();
    expect(screen.getByText('Registered Services (2)')).toBeInTheDocument();
    expect(screen.getByText('email-service')).toBeInTheDocument();
    expect(screen.getByText('calendar-service')).toBeInTheDocument();
    expect(screen.getByText('AI Providers (2)')).toBeInTheDocument();
    expect(screen.getByText('OpenAI')).toBeInTheDocument();
    expect(screen.getByText('Anthropic')).toBeInTheDocument();
    expect(screen.getByText('System Information')).toBeInTheDocument();
    expect(screen.getByText('Darwin')).toBeInTheDocument();
    expect(screen.getByText('macbook.local')).toBeInTheDocument();
    expect(screen.getByText('3.11.4')).toBeInTheDocument();
    expect(screen.getByText('12345')).toBeInTheDocument();
  });

  it('renders feature status cards', async () => {
    render(<SystemStatusDashboard />);

    expect(await screen.findByText('Feature Status')).toBeInTheDocument();
    expect(screen.getByText('Voice interface')).toBeInTheDocument();
    expect(screen.getByText('2 providers')).toBeInTheDocument();
    expect(screen.getByText('Canvas editor')).toBeInTheDocument();
    expect(screen.getByText('5 templates')).toBeInTheDocument();
  });

  it('shows the destructive alert when the overall status is not healthy', async () => {
    render(<SystemStatusDashboard />);

    expect(await screen.findByText('System Status: DEGRADED')).toBeInTheDocument();
    expect(
      screen.getByText('Some services may be experiencing issues. Check the services status above for details.')
    ).toBeInTheDocument();
  });

  it('does not show the alert when the overall status is healthy', async () => {
    mockGetSystemStatus.mockResolvedValue({
      data: { ...systemStatusPayload, overall_status: 'healthy' },
    });

    render(<SystemStatusDashboard />);

    expect(await screen.findByText('HEALTHY')).toBeInTheDocument();
    expect(screen.queryByText(/Some services may be experiencing issues/)).not.toBeInTheDocument();
  });

  it('re-fetches all APIs when the refresh button is clicked', async () => {
    render(<SystemStatusDashboard />);
    await screen.findByText('System Status Dashboard');
    const fetchesBefore = statusFetches;
    const servicesBefore = mockGetServices.mock.calls.length;

    fireEvent.click(screen.getByTitle('Refresh status'));

    await waitFor(() => expect(statusFetches).toBeGreaterThan(fetchesBefore));
    await waitFor(() => {
      expect(mockGetServices.mock.calls.length).toBeGreaterThan(servicesBefore);
    });
    expect(mockGetProviders.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(mockGetTemplates.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('toasts an error when fetching system data fails', async () => {
    mockGetSystemStatus.mockRejectedValue(new Error('network down'));

    render(<SystemStatusDashboard />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to fetch system status' })
      );
    });
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
  });
});

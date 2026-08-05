/**
 * AzureIntegration Component Tests
 *
 * Tests verify the real Azure integration component
 * (components/AzureIntegration.tsx):
 * - Connection status check (GET /api/integrations/azure/health)
 * - Disconnected / connect state
 * - Subscriptions + Azure resource loading (resource groups, virtual
 *   machines, storage accounts, app services)
 * - VM search filtering and create-resource dialogs
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AzureIntegration from '@/components/AzureIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const subscriptions = [
  {
    id: 'sub1',
    subscriptionId: 'sub-111',
    displayName: 'Pay-As-You-Go',
    state: 'Enabled',
    tenantId: 'tenant-1',
  },
];

const resourceGroups = [
  {
    id: 'rg1',
    name: 'prod-rg',
    location: 'East US',
    tags: { env: 'prod' },
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'rg2',
    name: 'dev-rg',
    location: 'West US',
    tags: {},
    created_at: '2026-02-01T00:00:00Z',
  },
];

const virtualMachines = [
  {
    id: 'vm1',
    name: 'web-server-01',
    location: 'East US',
    size: 'Standard_B2s',
    status: 'running',
    os_type: 'Linux',
    admin_username: 'azureuser',
    public_ip: '1.2.3.4',
    created_at: '2026-01-01T00:00:00Z',
    resource_group: 'prod-rg',
  },
  {
    id: 'vm2',
    name: 'db-server-01',
    location: 'East US',
    size: 'Standard_D2s_v3',
    status: 'running',
    os_type: 'Windows',
    admin_username: 'admin',
    public_ip: '',
    created_at: '2026-01-02T00:00:00Z',
    resource_group: 'prod-rg',
  },
];

const storageAccounts = [
  {
    id: 'sa1',
    name: 'web-storage-01',
    location: 'East US',
    type: 'Microsoft.Storage/storageAccounts',
    tier: 'Standard',
    replication: 'LRS',
    access_tier: 'Hot',
    blob_endpoint: 'https://blob.example.com',
    file_endpoint: 'https://file.example.com',
    created_at: '2026-01-01T00:00:00Z',
    resource_group: 'prod-rg',
  },
];

const appServices = [
  {
    id: 'app1',
    name: 'web-app-01',
    location: 'East US',
    state: 'Running',
    host_names: ['web-app-01.example.com'],
    app_service_plan: 'asp-basic',
    runtime: 'NODE',
    https_only: true,
    created_at: '2026-01-01T00:00:00Z',
    resource_group: 'prod-rg',
  },
];

const azureHandlers = [
  rest.get('/api/integrations/azure/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/azure/subscriptions', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { subscriptions } }));
  }),

  rest.post('/api/integrations/azure/resource-groups', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { resourceGroups } }));
  }),

  rest.post('/api/integrations/azure/virtual-machines', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { virtualMachines } }));
  }),

  rest.post('/api/integrations/azure/storage-accounts', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { storageAccounts } }));
  }),

  rest.post('/api/integrations/azure/app-services', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { appServices } }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/integrations/azure/health', (req, res, ctx) => {
      return res(ctx.status(500), ctx.json({ error: 'not connected' }));
    })
  );
};

describe('AzureIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...azureHandlers);
  });

  // Test 1: shows the connect screen when not connected
  test('shows connect screen when not connected', async () => {
    setNotConnected();

    render(<AzureIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect azure/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /connect azure account/i })
      ).toBeInTheDocument();
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });
  });

  // Test 2: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<AzureIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect azure account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 3: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<AzureIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /microsoft azure integration/i })
      ).toBeInTheDocument();
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 4: displays the subscription selector
  test('displays subscription selector', async () => {
    render(<AzureIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/pay-as-you-go/i)).toBeInTheDocument();
    });
  });

  // Test 5: displays overview cards with running counts
  test('displays overview cards', async () => {
    render(<AzureIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Storage Accounts')).toBeInTheDocument();
      expect(screen.getByText('2 running')).toBeInTheDocument();
      expect(screen.getByText('1 running')).toBeInTheDocument();
    });
  });

  // Test 6: displays virtual machines in the default tab
  test('displays virtual machines in the default tab', async () => {
    render(<AzureIntegration />);

    await waitFor(() => {
      expect(screen.getByText('web-server-01')).toBeInTheDocument();
      expect(screen.getByText('db-server-01')).toBeInTheDocument();
    });
  });

  // Test 7: displays storage accounts on the Storage tab
  test('displays storage accounts', async () => {
    render(<AzureIntegration />);

    await screen.findByText('web-server-01');

    fireEvent.click(screen.getByRole('button', { name: 'Storage' }));

    await waitFor(() => {
      expect(screen.getByText('web-storage-01')).toBeInTheDocument();
    });
  });

  // Test 8: displays app services on the App Services tab
  test('displays app services', async () => {
    render(<AzureIntegration />);

    await screen.findByText('web-server-01');

    fireEvent.click(screen.getByRole('button', { name: 'App Services' }));

    await waitFor(() => {
      expect(screen.getByText('web-app-01')).toBeInTheDocument();
      expect(screen.getByText('web-app-01.example.com')).toBeInTheDocument();
    });
  });

  // Test 9: displays resource groups on the Resource Groups tab
  test('displays resource groups', async () => {
    render(<AzureIntegration />);

    await screen.findByText('web-server-01');

    fireEvent.click(screen.getByRole('button', { name: 'Resource Groups' }));

    await waitFor(() => {
      expect(screen.getByText('prod-rg')).toBeInTheDocument();
      expect(screen.getByText('dev-rg')).toBeInTheDocument();
    });
  });

  // Test 10: filters virtual machines by search query
  test('filters virtual machines by search query', async () => {
    render(<AzureIntegration />);

    await screen.findByText('web-server-01');

    const searchInput = screen.getByPlaceholderText('Search VMs...');
    fireEvent.change(searchInput, { target: { value: 'web' } });

    expect(screen.getByText('web-server-01')).toBeInTheDocument();
    expect(screen.queryByText('db-server-01')).not.toBeInTheDocument();
  });

  // Test 11: Create VM button opens the create dialog
  test('opens create VM dialog', async () => {
    render(<AzureIntegration />);

    await screen.findByText('web-server-01');

    fireEvent.click(screen.getByRole('button', { name: /create vm/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /create virtual machine/i })
      ).toBeInTheDocument();
    });
  });

  // Test 12: shows refresh status button
  test('shows refresh status button', async () => {
    render(<AzureIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /refresh status/i })
      ).toBeInTheDocument();
    });
  });

  // Test 13: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/azure/health', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    render(<AzureIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect azure account/i })
      ).toBeInTheDocument();
    });
  });
});

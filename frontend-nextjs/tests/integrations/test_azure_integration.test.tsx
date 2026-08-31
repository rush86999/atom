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
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

/**
 * Opens a Radix Select (jsdom lacks PointerEvent support, so the trigger is
 * opened via keyboard) and picks the option with the given label.
 */
const pickSelectOption = async (trigger: Element, label: string) => {
  fireEvent.keyDown(trigger, { key: 'ArrowDown' });
  const item = await waitFor(() => {
    const found = Array.from(document.querySelectorAll('[role="option"]')).find(
      (i) => i.textContent === label
    );
    if (!found) throw new Error(`option "${label}" not found`);
    return found as HTMLElement;
  });
  fireEvent.click(item);
};

const clickFooterButton = (dialog: HTMLElement, label: RegExp) => {
  const buttons = Array.from(dialog.querySelectorAll('button')).filter((b) =>
    label.test(b.textContent || '')
  );
  fireEvent.click(buttons[buttons.length - 1]);
};

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
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { azure: { connected: true, source: 'user_connection' } } }));
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { azure: { connected: true, source: 'user_connection' } } }));
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
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
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
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
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

// ---------------------------------------------------------------------------
// Extended coverage: resource status variants, create flows, and error paths
// ---------------------------------------------------------------------------
describe('AzureIntegration (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const richVMs = [
    ...virtualMachines,
    {
      id: 'vm3',
      name: 'stopped-vm',
      location: 'West US',
      size: 'Standard_B1s',
      status: 'stopped',
      os_type: 'Linux',
      admin_username: 'u',
      public_ip: '5.6.7.8',
      created_at: '2026-01-03T00:00:00Z',
      resource_group: 'dev-rg',
    },
    {
      id: 'vm4',
      name: 'starting-vm',
      location: 'West US',
      size: 'Standard_B1s',
      status: 'starting',
      os_type: 'Linux',
      admin_username: 'u',
      public_ip: '',
      created_at: '2026-01-03T00:00:00Z',
      resource_group: 'dev-rg',
    },
    {
      id: 'vm5',
      name: 'stopping-vm',
      location: 'West US',
      size: 'Standard_B1s',
      status: 'stopping',
      os_type: 'Linux',
      admin_username: 'u',
      public_ip: '',
      created_at: '2026-01-03T00:00:00Z',
      resource_group: 'dev-rg',
    },
    {
      id: 'vm6',
      name: 'creating-vm',
      location: 'West US',
      size: 'Standard_B1s',
      status: 'creating',
      os_type: 'Linux',
      admin_username: 'u',
      public_ip: '',
      created_at: '2026-01-03T00:00:00Z',
      resource_group: 'dev-rg',
    },
    {
      id: 'vm7',
      name: 'deleting-vm',
      location: 'West US',
      size: 'Standard_B1s',
      status: 'deleting',
      os_type: 'Linux',
      admin_username: 'u',
      public_ip: '',
      created_at: '2026-01-03T00:00:00Z',
      resource_group: 'dev-rg',
    },
    {
      id: 'vm8',
      name: 'unknown-vm',
      location: 'West US',
      size: 'Standard_B1s',
      status: 'deallocated',
      os_type: 'Linux',
      admin_username: 'u',
      public_ip: '',
      created_at: '2026-01-03T00:00:00Z',
      resource_group: 'dev-rg',
    },
  ];

  const richStorage = [
    ...storageAccounts,
    {
      id: 'sa2',
      name: 'premium-storage-02',
      location: 'West US',
      type: 'Microsoft.Storage/storageAccounts',
      tier: 'Premium',
      replication: 'ZRS',
      access_tier: 'Hot',
      created_at: '2026-01-01T00:00:00Z',
      resource_group: 'dev-rg',
    },
    {
      id: 'sa3',
      name: 'basic-storage-03',
      location: 'West US',
      type: 'Microsoft.Storage/storageAccounts',
      tier: 'Basic',
      replication: 'GRS',
      access_tier: 'Cool',
      created_at: '2026-01-01T00:00:00Z',
      resource_group: 'dev-rg',
    },
    {
      id: 'sa4',
      name: 'odd-storage-04',
      location: 'West US',
      type: 'Microsoft.Storage/storageAccounts',
      tier: 'Unknown',
      replication: 'LRS',
      access_tier: 'Hot',
      created_at: '2026-01-01T00:00:00Z',
      resource_group: 'dev-rg',
    },
  ];

  const richApps = [
    ...appServices,
    {
      id: 'app2',
      name: 'api-app-02',
      location: 'West US',
      state: 'Stopped',
      host_names: ['api-app-02.example.com'],
      app_service_plan: 'asp-free',
      runtime: 'PYTHON',
      https_only: false,
      created_at: '2026-01-01T00:00:00Z',
      resource_group: 'dev-rg',
    },
  ];

  // NOTE: MSW resolves handlers in the order passed to server.use(), so the
  // data-rich overrides must come BEFORE the base azureHandlers.
  const richHandlers = [
    rest.post('/api/integrations/azure/virtual-machines', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { virtualMachines: richVMs } }));
    }),
    rest.post('/api/integrations/azure/storage-accounts', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { storageAccounts: richStorage } }));
    }),
    rest.post('/api/integrations/azure/app-services', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { appServices: richApps } }));
    }),
    rest.post('/api/integrations/azure/virtual-machines/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { vm: { id: 'vm999' } } }));
    }),
    rest.post('/api/integrations/azure/app-services/deploy', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { app: { id: 'app999' } } }));
    }),
    rest.post('/api/integrations/azure/storage-accounts/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { storage: { id: 'sa999' } } }));
    }),
    ...azureHandlers,
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...richHandlers);
  });

  const settle = async (text: RegExp | string) => {
    await screen.findByText(text);
    await new Promise((r) => setTimeout(r, 50));
  };

  test('renders VMs with all status badge variants', async () => {
    render(<AzureIntegration />);

    await settle('stopped-vm');
    for (const name of ['starting-vm', 'stopping-vm', 'creating-vm', 'deleting-vm', 'unknown-vm']) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
    expect(screen.getByText('stopped')).toBeInTheDocument();
    expect(screen.getByText('starting')).toBeInTheDocument();
    expect(screen.getByText('stopping')).toBeInTheDocument();
    expect(screen.getByText('creating')).toBeInTheDocument();
    expect(screen.getByText('deleting')).toBeInTheDocument();
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0);
  });

  test('renders storage tiers and app service states', async () => {
    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: 'Storage' }));
    expect(await screen.findByText('premium-storage-02')).toBeInTheDocument();
    expect(screen.getByText('Premium')).toBeInTheDocument();
    expect(screen.getByText('Basic')).toBeInTheDocument();
    expect(screen.getByText('Unknown')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'App Services' }));
    expect(await screen.findByText('api-app-02')).toBeInTheDocument();
    expect(screen.getByText('Stopped')).toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
  });

  test('Open button on app service row opens the site url', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: 'App Services' }));
    const openButtons = await screen.findAllByRole('button', { name: /open/i });
    fireEvent.click(openButtons[0]);

    expect(openSpy).toHaveBeenCalledWith('https://web-app-01.example.com', '_blank');
  });

  test('filters apps, storage and resource groups by search', async () => {
    render(<AzureIntegration />);
    await settle('stopped-vm');

    // apps
    fireEvent.click(screen.getByRole('button', { name: 'App Services' }));
    expect(await screen.findByText('api-app-02')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Search apps...'), {
      target: { value: 'api-app' },
    });
    expect(screen.getByText('api-app-02')).toBeInTheDocument();
    expect(screen.queryByText('web-app-01')).not.toBeInTheDocument();

    // storage (searchQuery persists across tabs, so set it right after switching)
    fireEvent.click(screen.getByRole('button', { name: 'Storage' }));
    fireEvent.change(screen.getByPlaceholderText('Search storage...'), {
      target: { value: 'premium' },
    });
    await waitFor(() => {
      expect(screen.getByText('premium-storage-02')).toBeInTheDocument();
    });
    expect(screen.queryByText('web-storage-01')).not.toBeInTheDocument();

    // resource groups
    fireEvent.click(screen.getByRole('button', { name: 'Resource Groups' }));
    fireEvent.change(screen.getByPlaceholderText('Search resource groups...'), {
      target: { value: 'dev' },
    });
    await waitFor(() => {
      expect(screen.getByText('dev-rg')).toBeInTheDocument();
    });
    expect(screen.queryByText('prod-rg')).not.toBeInTheDocument();
  });

  test('creates a virtual machine through the dialog', async () => {
    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: /create vm/i }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.querySelectorAll('button[role="combobox"]').length).toBe(3);

    // Pick the resource group from the first Select
    await pickSelectOption(dialog.querySelectorAll('button[role="combobox"]')[0], 'prod-rg');

    fireEvent.change(screen.getByPlaceholderText('my-vm'), {
      target: { value: 'test-vm-01' },
    });
    fireEvent.change(screen.getByPlaceholderText('azureuser'), {
      target: { value: 'testadmin' },
    });
    fireEvent.change(screen.getByPlaceholderText('SecurePassword123!'), {
      target: { value: 'Password123!' },
    });

    clickFooterButton(dialog, /create vm/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Virtual machine creation initiated',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when VM creation fails', async () => {
    server.use(
      rest.post('/api/integrations/azure/virtual-machines/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: /create vm/i }));
    const dialog = await screen.findByRole('dialog');
    await pickSelectOption(dialog.querySelectorAll('button[role="combobox"]')[0], 'prod-rg');
    fireEvent.change(screen.getByPlaceholderText('my-vm'), { target: { value: 'bad-vm' } });
    fireEvent.change(screen.getByPlaceholderText('azureuser'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText('SecurePassword123!'), {
      target: { value: 'Password123!' },
    });
    clickFooterButton(dialog, /create vm/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to create virtual machine',
        })
      );
    });
  });

  test('deploys an app service through the dialog', async () => {
    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: 'App Services' }));
    fireEvent.click(screen.getAllByRole('button', { name: /deploy app/i })[0]);
    const dialog = await screen.findByRole('dialog');

    await pickSelectOption(dialog.querySelectorAll('button[role="combobox"]')[0], 'prod-rg');
    fireEvent.change(screen.getByPlaceholderText('my-app'), {
      target: { value: 'test-app-01' },
    });
    // toggle HTTPS Only checkbox off
    fireEvent.click(dialog.querySelector('input#https_only') as HTMLElement);

    clickFooterButton(dialog, /deploy app/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'App service deployment initiated',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when app deployment fails', async () => {
    server.use(
      rest.post('/api/integrations/azure/app-services/deploy', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: 'App Services' }));
    fireEvent.click(screen.getAllByRole('button', { name: /deploy app/i })[0]);
    const dialog = await screen.findByRole('dialog');

    await pickSelectOption(dialog.querySelectorAll('button[role="combobox"]')[0], 'prod-rg');
    fireEvent.change(screen.getByPlaceholderText('my-app'), { target: { value: 'bad-app' } });
    clickFooterButton(dialog, /deploy app/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to deploy app service',
        })
      );
    });
  });

  test('creates a storage account through the dialog', async () => {
    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: 'Storage' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create storage/i })[0]);
    const dialog = await screen.findByRole('dialog');

    await pickSelectOption(dialog.querySelectorAll('button[role="combobox"]')[0], 'prod-rg');
    fireEvent.change(screen.getByPlaceholderText('mystorageaccount'), {
      target: { value: 'teststorage01' },
    });

    clickFooterButton(dialog, /create storage/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Storage account creation initiated',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when storage creation fails', async () => {
    server.use(
      rest.post('/api/integrations/azure/storage-accounts/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: 'Storage' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create storage/i })[0]);
    const dialog = await screen.findByRole('dialog');

    await pickSelectOption(dialog.querySelectorAll('button[role="combobox"]')[0], 'prod-rg');
    fireEvent.change(screen.getByPlaceholderText('mystorageaccount'), {
      target: { value: 'badstorage' },
    });
    clickFooterButton(dialog, /create storage/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to create storage account',
        })
      );
    });
  });

  test('logs an error when the subscriptions load fails', async () => {
    server.use(
      rest.post('/api/integrations/azure/subscriptions', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<AzureIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to load subscriptions:',
        expect.anything()
      );
    });
  });

  test('logs errors when resource loads fail', async () => {
    // NOTE: subscriptions must succeed, otherwise selectedSubscription stays
    // empty and the other resource loads are never triggered.
    const netFail = (path: string) => rest.post(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/azure/resource-groups'),
      netFail('/api/integrations/azure/virtual-machines'),
      netFail('/api/integrations/azure/storage-accounts'),
      netFail('/api/integrations/azure/app-services')
    );

    render(<AzureIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to load resource groups:',
        expect.anything()
      );
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to load virtual machines:',
        expect.anything()
      );
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to load storage accounts:',
        expect.anything()
      );
      expect(errorSpy).toHaveBeenCalledWith('Failed to load app services:', expect.anything());
    });
  });

  test('treats health check network failure as disconnected', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res) => res.networkError('boom'))
    );

    render(<AzureIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
      expect(
        screen.getByRole('button', { name: /connect azure account/i })
      ).toBeInTheDocument();
    });
  });

  test('clicking Refresh Status re-runs the health check', async () => {
    render(<AzureIntegration />);
    await settle('stopped-vm');

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });
});

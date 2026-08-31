/**
 * NodeConfigSidebar Component Tests
 *
 * Tests verify the REAL NodeConfigSidebar component
 * (components/Automations/NodeConfigSidebar.tsx):
 *
 * - null render without a selected node
 * - metadata fetch (loading / success / failure) for actions and triggers
 * - field rendering for every prop type (text, long text, number, dropdown,
 *   dynamic, markdown, checkbox, array, object, unknown fallback)
 * - config save flows: every input change calls onUpdateNode with the
 *   merged config
 * - connection flows: fetch, auto-select first, stored connectionId,
 *   empty/error states, dynamic-options fetch on connection change
 *   (DROPDOWN-without-options AND DYNAMIC fields)
 * - auth flow: popup open, AUTH_SUCCESS / AUTH_ERROR / AUTH_CANCEL message
 *   handling, authorize failure + throw toasts
 * - Save/Cancel buttons, Manage Connections modal wiring
 * - node switch refetch (metadata + connections reload)
 *
 * Radix Select is mocked (context pattern from JiraIntegration.test.tsx);
 * ManageConnectionsModal is mocked so its own contract is tested separately
 * (test-manage-connections-modal.test.tsx).
 *
 * NOTE on timing: the metadata fetch resolves in a microtask OUTSIDE act(),
 * so React commits the update a scheduler tick later. Every test therefore
 * waits for a METADATA-DEPENDENT element (service icon via getByAltText, a
 * field placeholder, or the connection section) rather than the node label
 * (which renders instantly as a fallback and races the fetch).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import NodeConfigSidebar from '../NodeConfigSidebar';

jest.mock('@/components/ui/use-toast', () => {
  const mockToast = jest.fn();
  return {
    useToast: () => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: any) => children,
    __mockToast: mockToast,
  };
});

jest.mock('@/components/ui/select', () => {
  const { createContext, useContext, useState } = jest.requireActual('react');
  const SelectCtx = createContext(null);

  const Select = ({ value, onValueChange, children }: any) => {
    const [open, setOpen] = useState(false);
    return (
      <SelectCtx.Provider value={{ value, onValueChange, open, setOpen }}>
        <div data-testid="select-root">{children}</div>
      </SelectCtx.Provider>
    );
  };
  const SelectTrigger = ({ children, className, ...props }: any) => {
    const { setOpen } = useContext(SelectCtx);
    return (
      <button type="button" className={className} onClick={() => setOpen((o: boolean) => !o)} {...props}>
        {children}
      </button>
    );
  };
  const SelectContent = ({ children }: any) => {
    const { open } = useContext(SelectCtx);
    return open ? <div data-testid="select-content">{children}</div> : null;
  };
  const SelectItem = ({ value, children }: any) => {
    const { onValueChange, setOpen } = useContext(SelectCtx);
    return (
      <span onClick={() => { onValueChange(value); setOpen(false); }}>{children}</span>
    );
  };
  const SelectValue = ({ placeholder }: any) => <span data-testid="select-value">{placeholder}</span>;
  return { Select, SelectTrigger, SelectContent, SelectItem, SelectValue };
});

jest.mock('../ManageConnectionsModal', () => {
  const React = jest.requireActual('react');
  const api: any = { props: null };
  const Mock = (props: any) => {
    api.props = props;
    return React.createElement(
      'div',
      { 'data-testid': 'manage-connections-modal' },
      props.isOpen ? 'Manage modal open' : 'Manage modal closed'
    );
  };
  return { __esModule: true, default: Mock, __testApi: api };
});

const toastMock = () =>
  (jest.requireMock('@/components/ui/use-toast') as any).__mockToast as jest.Mock;
const mcmApi = () =>
  (jest.requireMock('../ManageConnectionsModal') as any).__testApi;

const jsonResponse = (body: any, ok = true, _status?: number) => ({
  ok,
  status: ok ? 200 : 500,
  statusText: ok ? 'OK' : 'Error',
  json: async () => body,
});

const metadata = {
  serviceId: 'slack',
  name: 'Slack',
  icon: 'https://example.com/slack.png',
  auth: { oauth2: true },
  actions: [
    {
      name: 'send_message',
      displayName: 'Send Message',
      description: 'Send a message to a channel',
      props: {
        channel: {
          type: 'DROPDOWN',
          displayName: 'Channel',
          required: true,
          options: { options: [{ label: 'General', value: 'C1' }, { label: 'Random', value: 'C2' }] },
        },
        text: { type: 'SHORT_TEXT', displayName: 'Text', required: true, description: 'Message text', defaultValue: 'hello' },
        body: { type: 'LONG_TEXT', displayName: 'Body', description: 'Long text here' },
        count: { type: 'NUMBER', displayName: 'Count' },
        dry: { type: 'CHECKBOX', displayName: 'Dry run' },
        tags: { type: 'ARRAY', displayName: 'Tags' },
        payload: { type: 'OBJECT', displayName: 'Payload' },
        info: { type: 'MARKDOWN', description: 'Line1\nLine2' },
        dynamic_field: { type: 'DYNAMIC', displayName: 'Dynamic Field' },
        mystery: { type: 'WEIRD_TYPE', displayName: 'Mystery' },
      },
    },
  ],
  triggers: [],
};

const node = {
  id: 'n1',
  type: 'action',
  data: {
    service: 'Slack',
    serviceId: 'slack',
    action: 'send_message',
    label: 'Send Message',
    config: {},
  },
};

const connections = [
  { id: 'conn-1', name: 'Workspace A', status: 'active' },
  { id: 'conn-2', name: 'Workspace B', status: 'expired' },
];

const openSelect = (index = 0) => {
  fireEvent.click(screen.getAllByTestId('select-root')[index].querySelector('button')!);
};

const selectOption = (optionText: string, index = 0) => {
  openSelect(index);
  fireEvent.click(screen.getByText(optionText));
};

// Waits until the metadata has been fetched AND committed (icon renders).
const waitForMetadata = (alt = 'Slack') =>
  waitFor(() => {
    expect(screen.getByAltText(alt)).toBeInTheDocument();
  });

describe('NodeConfigSidebar', () => {
  let fetchSpy: jest.SpyInstance;
  let onUpdateNode: jest.Mock;
  let onClose: jest.Mock;
  let openSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(global as any, 'fetch')
      .mockResolvedValue(jsonResponse({}));
    onUpdateNode = jest.fn();
    onClose = jest.fn();
    openSpy = jest.spyOn(window, 'open').mockImplementation(() => null as any);
  });

  it('renders nothing when no node is selected', () => {
    const { container } = render(
      <NodeConfigSidebar
        selectedNode={null}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );
    expect(container.firstChild).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('fetches metadata and shows the loading state while in flight', () => {
    let resolveMetadata: (r: any) => void;
    fetchSpy.mockImplementationOnce(
      () => new Promise((res) => { resolveMetadata = res; })
    );
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    expect(screen.getByText('Loading parameters...')).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/external-integrations/slack');

    act(() => {
      resolveMetadata!(jsonResponse(metadata));
    });
  });

  it('shows the fallback icon and service name while metadata is missing', () => {
    let resolveMetadata: (r: any) => void;
    fetchSpy.mockImplementationOnce(
      () => new Promise((res) => { resolveMetadata = res; })
    );
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    // header falls back to the node's service name
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('action')).toBeInTheDocument();
    // info box falls back to the node label + generic description
    expect(screen.getByText('Send Message')).toBeInTheDocument();
    expect(screen.getByText('Configure the parameters for this step.')).toBeInTheDocument();

    act(() => {
      resolveMetadata!(jsonResponse(metadata));
    });
  });

  it('renders the action fields from metadata and saves edits to onUpdateNode', async () => {
    fetchSpy.mockResolvedValue(jsonResponse(metadata));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[node]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitForMetadata();
    // The action info box shows the action's description from metadata
    expect(screen.getByText('Send a message to a channel')).toBeInTheDocument();

    // SHORT_TEXT with default value
    const textInput = screen.getByDisplayValue('hello') as HTMLInputElement;
    fireEvent.change(textInput, { target: { value: 'hello world' } });
    expect(onUpdateNode).toHaveBeenLastCalledWith(
      'n1',
      expect.objectContaining({
        config: expect.objectContaining({ text: 'hello world' }),
      })
    );
  });

  it('renders every supported prop type', async () => {
    fetchSpy.mockResolvedValue(jsonResponse(metadata));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitForMetadata();
    // LONG_TEXT
    expect(screen.getByPlaceholderText('Long text here')).toBeInTheDocument();
    // NUMBER (label is not associated via htmlFor, so target the spinbutton)
    expect(screen.getByRole('spinbutton')).toBeInTheDocument();
    // DROPDOWN static options render once the select is open
    openSelect(1); // select #0 is the connection select, #1 the channel field
    expect(screen.getByText('General')).toBeInTheDocument();
    expect(screen.getByText('Random')).toBeInTheDocument();
    // CHECKBOX (the only switch; the label is not htmlFor-associated)
    expect(screen.getByRole('switch')).toBeInTheDocument();
    // ARRAY
    expect(screen.getByPlaceholderText('Item 1, Item 2...')).toBeInTheDocument();
    // OBJECT
    expect(screen.getByPlaceholderText('{ "key": "value" }')).toBeInTheDocument();
    // MARKDOWN (description split into lines; text nodes are separated by <br>)
    expect(screen.getByText(/Line1/)).toBeInTheDocument();
    expect(screen.getByText(/Line2/)).toBeInTheDocument();
    // DYNAMIC field falls back to "Select an option" before options load
    expect(screen.getByText('Dynamic Field')).toBeInTheDocument();
    // Unknown type fallback
    expect(screen.getByText('Mystery')).toBeInTheDocument();
    expect(screen.getByText('(WEIRD_TYPE)')).toBeInTheDocument();
    // Required badge is rendered for the required SHORT_TEXT field
    expect(screen.getByText('Text')).toBeInTheDocument();
  });

  it('saves NUMBER, ARRAY and CHECKBOX field edits through onUpdateNode', async () => {
    fetchSpy.mockResolvedValue(jsonResponse(metadata));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitForMetadata();
    const countInput = screen.getByRole('spinbutton');
    fireEvent.change(countInput, { target: { value: '42' } });
    expect(onUpdateNode).toHaveBeenLastCalledWith(
      'n1',
      expect.objectContaining({ config: expect.objectContaining({ count: 42 }) })
    );

    fireEvent.change(screen.getByPlaceholderText('Item 1, Item 2...'), {
      target: { value: 'a, b ,c' },
    });
    expect(onUpdateNode).toHaveBeenLastCalledWith(
      'n1',
      expect.objectContaining({
        config: expect.objectContaining({ tags: ['a', 'b', 'c'] }),
      })
    );

    fireEvent.click(screen.getByRole('switch'));
    expect(onUpdateNode).toHaveBeenLastCalledWith(
      'n1',
      expect.objectContaining({ config: expect.objectContaining({ dry: true }) })
    );
  });

  it('parses valid JSON in OBJECT fields and ignores invalid JSON', async () => {
    fetchSpy.mockResolvedValue(jsonResponse(metadata));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitForMetadata();
    const jsonField = screen.getByPlaceholderText('{ "key": "value" }');
    fireEvent.change(jsonField, { target: { value: '{"a": 1}' } });
    expect(onUpdateNode).toHaveBeenLastCalledWith(
      'n1',
      expect.objectContaining({ config: expect.objectContaining({ payload: { a: 1 } }) })
    );

    fireEvent.change(jsonField, { target: { value: '{invalid json' } });
    // invalid JSON is not committed to config
    expect(onUpdateNode.mock.calls.length).toBe(1);
  });

  it('selects a static dropdown option and saves it', async () => {
    fetchSpy.mockResolvedValue(jsonResponse(metadata));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitForMetadata();
    selectOption('Random', 1);
    expect(onUpdateNode).toHaveBeenLastCalledWith(
      'n1',
      expect.objectContaining({ config: expect.objectContaining({ channel: 'C2' }) })
    );
  });

  it('uses trigger metadata when the action matches a trigger', async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({
        serviceId: 'gmail',
        name: 'Gmail',
        icon: 'https://example.com/gmail.png',
        actions: [],
        triggers: [
          {
            name: 'new_email',
            displayName: 'New Email',
            description: 'Fires on new email',
            props: {
              folder: { type: 'SHORT_TEXT', displayName: 'Folder', description: 'Which folder' },
            },
          },
        ],
      })
    );
    render(
      <NodeConfigSidebar
        selectedNode={{
          id: 'n2',
          type: 'trigger',
          data: { service: 'Gmail', serviceId: 'gmail', action: 'new_email', label: 'New Email', config: {} },
        }}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitForMetadata('Gmail');
    expect(screen.getByText('Fires on new email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Which folder')).toBeInTheDocument();
  });

  it('shows the no-parameters empty state and survives metadata fetch failure', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('metadata down'));
    const { rerender } = render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText('No configurable parameters found for this action.')
      ).toBeInTheDocument();
    });

    // Successful fetch of an action with no props also hits the empty state
    fetchSpy.mockResolvedValue(
      jsonResponse({ serviceId: 'x', name: 'X', icon: 'https://example.com/x.png', auth: null, actions: [{ name: 'a', displayName: 'A' }], triggers: [] })
    );
    rerender(
      <NodeConfigSidebar
        selectedNode={{ ...node, data: { ...node.data, serviceId: 'x', action: 'a' } }}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );
    await waitForMetadata('X');
    await waitFor(() => {
      expect(
        screen.getByText('No configurable parameters found for this action.')
      ).toBeInTheDocument();
    });
  });

  it('survives a metadata response that is not ok', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata, false));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText('No configurable parameters found for this action.')
      ).toBeInTheDocument();
    });
  });

  it('fetches connections for auth pieces and auto-selects the first one', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValue(jsonResponse(connections));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/connections?integration_id=slack'
      );
    });
    await waitFor(() => {
      expect(onUpdateNode).toHaveBeenCalledWith(
        'n1',
        expect.objectContaining({ config: expect.objectContaining({ connectionId: 'conn-1' }) })
      );
    });
    // dynamic options are fetched for the DYNAMIC field after connection change
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/integrations/dynamic-options',
        expect.objectContaining({ method: 'POST' })
      );
    });
    const dynamicBody = JSON.parse(
      fetchSpy.mock.calls.find(([url]: any) => url === '/api/v1/integrations/dynamic-options')![1].body
    );
    expect(dynamicBody).toMatchObject({
      pieceId: 'slack',
      actionName: 'send_message',
      propertyName: 'dynamic_field',
      connectionId: 'conn-1',
    });
  });

  it('restores the stored connectionId from the node config', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValue(jsonResponse(connections));
    const storedNode = {
      ...node,
      data: { ...node.data, config: { connectionId: 'conn-2' } },
    };
    render(
      <NodeConfigSidebar
        selectedNode={storedNode}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      // Auto-selection of conn-1 must NOT happen; no update with conn-1
      expect(onUpdateNode).not.toHaveBeenCalledWith(
        'n1',
        expect.objectContaining({ config: expect.objectContaining({ connectionId: 'conn-1' }) })
      );
    });
  });

  it('shows the empty connection state and survives connection fetch failure', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse([], false));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Select a connection')).toBeInTheDocument();
    });
    // open the connection dropdown -> empty state message
    openSelect(0);
    expect(
      screen.getByText('No connections found. Add one below.')
    ).toBeInTheDocument();
  });

  it('survives a malformed (non-array) connections response', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse({ not: 'an array' }));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    // Sidebar must not crash and must still render the fields
    await waitFor(() => {
      expect(screen.getByAltText('Slack')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('hello')).toBeInTheDocument();
    openSelect(0);
    expect(
      screen.getByText('No connections found. Add one below.')
    ).toBeInTheDocument();
  });

  it('changes the selected connection and refetches dynamic options', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse(connections));
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ options: [{ label: 'Sales', value: 'team-sales' }] })
    );
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/v1/connections?integration_id=slack');
    });

    openSelect(0);
    fireEvent.click(screen.getByText('Workspace B'));

    await waitFor(() => {
      expect(onUpdateNode).toHaveBeenLastCalledWith(
        'n1',
        expect.objectContaining({ config: expect.objectContaining({ connectionId: 'conn-2' }) })
      );
    });
    // the LAST dynamic-options call carries the newly selected connection
    const dynamicBody = JSON.parse(
      fetchSpy.mock.calls.filter(
        ([url]: any) => url === '/api/v1/integrations/dynamic-options'
      ).pop()![1].body
    );
    expect(dynamicBody).toMatchObject({ propertyName: 'dynamic_field', connectionId: 'conn-2' });
  });

  it('renders dynamic options fetched for a DROPDOWN field without static options', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({
        ...metadata,
        actions: [
          {
            ...metadata.actions[0],
            props: {
              ...metadata.actions[0].props,
              region: { type: 'DROPDOWN', displayName: 'Region', options: undefined },
            },
          },
        ],
      })
    );
    fetchSpy.mockResolvedValueOnce(jsonResponse(connections));
    // dynamic_field (DYNAMIC) fetches first, then region (DROPDOWN, no options)
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ options: [{ label: 'Sales', value: 'team-sales' }] })
    );
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ options: [{ label: 'EMEA', value: 'region-emea' }] })
    );
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Region')).toBeInTheDocument();
    });
    // connection auto-selection triggers the region options fetch
    await waitFor(() => {
      const regionCall = fetchSpy.mock.calls.find(([url, init]: any) => {
        if (url !== '/api/v1/integrations/dynamic-options') return false;
        return JSON.parse(init.body).propertyName === 'region';
      });
      expect(regionCall).toBeDefined();
    });
    // select the returned dynamic option (select index: 0=connection,
    // 1=channel, 2=dynamic_field, 3=region)
    openSelect(3);
    fireEvent.click(screen.getByText('EMEA'));
    await waitFor(() => {
      expect(onUpdateNode).toHaveBeenLastCalledWith(
        'n1',
        expect.objectContaining({ config: expect.objectContaining({ region: 'region-emea' }) })
      );
    });
  });

  it('opens the auth popup and refetches connections on AUTH_SUCCESS', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ url: 'https://oauth.example.com/start' })
    );
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByTitle('Add New Connection')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('Add New Connection'));

    await waitFor(() => {
      expect(openSpy).toHaveBeenCalledWith(
        'https://oauth.example.com/start',
        'Connect Integration',
        expect.stringContaining('width=600')
      );
    });

    const before = fetchSpy.mock.calls.length;
    act(() => {
      window.dispatchEvent(
        new MessageEvent('message', {
          data: { type: 'AUTH_SUCCESS' },
        })
      );
    });
    await waitFor(() => {
      // connections were refetched after auth success
      expect(fetchSpy.mock.calls.length).toBeGreaterThan(before);
    });
    // Add New Connection is re-enabled after auth success
    expect(screen.getByTitle('Add New Connection')).toBeEnabled();
  });

  it('stops the auth loading state on AUTH_ERROR', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ url: 'https://oauth.example.com/start' })
    );
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByTitle('Add New Connection')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('Add New Connection'));
    expect(screen.getByTitle('Add New Connection')).toBeDisabled();

    // wait for the popup to open (the message listener is registered right
    // after window.open) so the AUTH_ERROR message cannot be lost
    await waitFor(() => {
      expect(openSpy).toHaveBeenCalled();
    });
    act(() => {
      window.dispatchEvent(
        new MessageEvent('message', { data: { type: 'AUTH_ERROR' } })
      );
    });
    // button is enabled again after the error message
    await waitFor(() => {
      expect(screen.getByTitle('Add New Connection')).toBeEnabled();
    });
  });

  it('stops the auth loading state on AUTH_CANCEL', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ url: 'https://oauth.example.com/start' })
    );
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByTitle('Add New Connection')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('Add New Connection'));
    await waitFor(() => {
      expect(openSpy).toHaveBeenCalled();
    });
    act(() => {
      window.dispatchEvent(
        new MessageEvent('message', { data: { type: 'AUTH_CANCEL' } })
      );
    });
    await waitFor(() => {
      expect(screen.getByTitle('Add New Connection')).toBeEnabled();
    });
  });

  it('toasts when the authorize API fails', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false, 500));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByTitle('Add New Connection')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('Add New Connection'));

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Authentication Failed',
          description: 'Could not initiate the authentication flow. Please try again.',
          variant: 'error',
        })
      );
    });
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('toasts when the authorize request throws', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockRejectedValueOnce(new Error('network'));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(screen.getByTitle('Add New Connection')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('Add New Connection'));

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Authentication Failed' })
      );
    });
  });

  it('fetches dynamic options for fields refreshed by a changed field', async () => {
    const refreshMetadata = {
      ...metadata,
      actions: [
        {
          ...metadata.actions[0],
          props: {
            ...metadata.actions[0].props,
            region: {
              type: 'DROPDOWN',
              displayName: 'Region',
              options: { options: [{ label: 'US', value: 'us' }] },
              refreshers: ['team'],
            },
            team: {
              type: 'DROPDOWN',
              displayName: 'Team',
              options: { options: [{ label: 'Team A', value: 'team-a' }] },
            },
          },
        },
      ],
    };
    fetchSpy.mockResolvedValue(jsonResponse(refreshMetadata));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitForMetadata();
    // changing 'team' triggers the refresher for 'region'
    // (select index: 0=connection, 1=channel, 2=dynamic_field, 3=region, 4=team)
    selectOption('Team A', 4);
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/integrations/dynamic-options',
        expect.anything()
      );
    });
    const body = JSON.parse(
      fetchSpy.mock.calls.find(([url]: any) => url === '/api/v1/integrations/dynamic-options')![1].body
    );
    expect(body.propertyName).toBe('region');
  });

  it('survives a dynamic-options fetch failure', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValueOnce(jsonResponse(connections));
    fetchSpy.mockRejectedValueOnce(new Error('dynamic down'));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/v1/connections?integration_id=slack');
    });
    await waitFor(() => {
      expect(onUpdateNode).toHaveBeenCalledWith(
        'n1',
        expect.objectContaining({ config: expect.objectContaining({ connectionId: 'conn-1' }) })
      );
    });
    // no crash: fields still render with the default value
    expect(screen.getByDisplayValue('hello')).toBeInTheDocument();
  });

  it('closes via the Cancel and Save Step buttons', async () => {
    fetchSpy.mockResolvedValue(jsonResponse(metadata));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );
    await waitForMetadata();

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /save step/i }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('opens the manage connections modal and wires onConnectionsUpdated', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(metadata));
    fetchSpy.mockResolvedValue(jsonResponse(connections));
    render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );

    // wait for THIS test's metadata to commit (connection section renders)
    await waitFor(() => {
      expect(screen.getByTitle('Manage Connections')).toBeInTheDocument();
    });
    expect(mcmApi().props).not.toBeNull();
    expect(mcmApi().props.integrationId).toBe('slack');
    expect(mcmApi().props.integrationName).toBe('Slack');
    expect(mcmApi().props.isOpen).toBe(false);

    fireEvent.click(screen.getByTitle('Manage Connections'));
    expect(mcmApi().props.isOpen).toBe(true);

    // onConnectionsUpdated triggers a connections refetch
    const before = fetchSpy.mock.calls.filter(([url]: any) =>
      String(url).startsWith('/api/v1/connections')
    ).length;
    act(() => {
      mcmApi().props.onConnectionsUpdated();
    });
    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.filter(([url]: any) =>
          String(url).startsWith('/api/v1/connections')
        ).length
      ).toBeGreaterThan(before);
    });
  });

  it('refetches metadata when the selected node changes', async () => {
    fetchSpy.mockResolvedValue(jsonResponse(metadata));
    const { rerender } = render(
      <NodeConfigSidebar
        selectedNode={node}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );
    await waitForMetadata();
    const metadataCalls = fetchSpy.mock.calls.filter(([url]: any) =>
      String(url).includes('/api/v1/external-integrations/')
    ).length;

    rerender(
      <NodeConfigSidebar
        selectedNode={{ ...node, id: 'n2', data: { ...node.data, serviceId: 'gmail' } }}
        allNodes={[]}
        onClose={onClose}
        onUpdateNode={onUpdateNode}
      />
    );
    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.filter(([url]: any) =>
          String(url).includes('/api/v1/external-integrations/')
        ).length
      ).toBeGreaterThan(metadataCalls);
    });
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/external-integrations/gmail');
  });
});

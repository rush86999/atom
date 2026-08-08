/**
 * EntityTypeGraphView Component Tests
 *
 * Covers the REAL EntityTypeGraphView (components/entity/EntityTypeGraphView.tsx):
 * - Fetches /api/entity-types on mount with workspace_id + include_system params
 * - Loading overlay ("Building Graph...") while the fetch is in flight
 * - Legend renders System Type / Custom Type badges
 * - $ref relationship detection: properties referencing another type's slug
 *   produce force links
 * - Clicking a rendered node opens the Type Details panel (name, slug, version,
 *   property count) and the close button dismisses it
 * - Empty entity list renders without crashing (no simulation setup)
 * - Failed fetch degrades to an empty graph without crashing
 *
 * d3 is ESM-only and cannot be loaded by jest, so the entire module is mocked
 * with chainable selection objects; handlers are captured on the mock module
 * so tests can drive the real component logic.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { EntityTypeGraphView } from '../EntityTypeGraphView';

jest.mock('d3', () => {
  const handlers: Record<string, any> = {};

  const makeChain = (): any => ({
    append: jest.fn(() => makeChain()),
    selectAll: jest.fn(() => makeChain()),
    data: jest.fn(() => makeChain()),
    join: jest.fn(() => makeChain()),
    attr: jest.fn(() => makeChain()),
    style: jest.fn(() => makeChain()),
    text: jest.fn(() => makeChain()),
    remove: jest.fn(() => makeChain()),
    call: jest.fn(() => makeChain()),
    on: jest.fn((evt: string, cb: any) => {
      handlers[evt] = cb;
      return makeChain();
    }),
  });

  const makeSimulation = () => ({
    force: jest.fn().mockReturnThis(),
    alphaTarget: jest.fn().mockReturnThis(),
    restart: jest.fn(),
    stop: jest.fn(),
    on: jest.fn((evt: string, cb: any) => {
      handlers[evt] = cb;
      return makeSimulation();
    }),
  });

  // resetMocks (jest config) clears factory mock implementations before every
  // test, so the api exposes __makeChain/__makeSimulation for beforeEach
  // re-stubbing.
  return {
    __handlers: handlers,
    __makeChain: makeChain,
    __makeSimulation: makeSimulation,
    select: jest.fn(() => makeChain()),
    zoom: jest.fn(() => ({
      scaleExtent: jest.fn().mockReturnThis(),
      on: jest.fn().mockReturnThis(),
    })),
    drag: jest.fn(() => ({ on: jest.fn().mockReturnThis() })),
    forceSimulation: jest.fn(() => makeSimulation()),
    forceLink: jest.fn(() => ({ id: jest.fn().mockReturnThis(), distance: jest.fn().mockReturnThis() })),
    forceManyBody: jest.fn(() => ({ strength: jest.fn().mockReturnThis() })),
    forceCenter: jest.fn(),
    forceCollide: jest.fn(() => ({ radius: jest.fn().mockReturnThis() })),
  };
});

jest.mock('axios', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

const axiosMock = require('axios').default as {
  get: jest.Mock;
  post: jest.Mock;
  put: jest.Mock;
  delete: jest.Mock;
};

const entityTypes = [
  {
    id: 'et-1',
    slug: 'customer',
    display_name: 'Customer',
    description: 'A customer record',
    is_system: true,
    version: 2,
    json_schema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        email: { type: 'string' },
        contact: { $ref: '#/definitions/contact' },
      },
    },
  },
  {
    id: 'et-2',
    slug: 'contact',
    display_name: 'Contact',
    description: 'A contact person',
    is_system: false,
    version: 1,
    json_schema: {
      type: 'object',
      properties: {
        phone: { type: 'string' },
      },
    },
  },
];

const linkedTypes = [
  { ...entityTypes[0], json_schema: { type: 'object', properties: { owner: { $ref: 'contact' } } } },
  entityTypes[1],
];

describe('EntityTypeGraphView', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // resetMocks cleared the factory implementations — re-stub the d3 api
    const d3Mock = require('d3') as any;
    for (const key of Object.keys(d3Mock.__handlers)) delete d3Mock.__handlers[key];
    d3Mock.select.mockImplementation(() => d3Mock.__makeChain());
    d3Mock.forceSimulation.mockImplementation(() => d3Mock.__makeSimulation());
    d3Mock.zoom.mockImplementation(() => ({
      scaleExtent: jest.fn().mockReturnThis(),
      on: jest.fn().mockReturnThis(),
    }));
    d3Mock.drag.mockImplementation(() => ({ on: jest.fn().mockReturnThis() }));
    d3Mock.forceLink.mockImplementation(() => ({ id: jest.fn().mockReturnThis(), distance: jest.fn().mockReturnThis() }));
    d3Mock.forceManyBody.mockImplementation(() => ({ strength: jest.fn().mockReturnThis() }));
    d3Mock.forceCollide.mockImplementation(() => ({ radius: jest.fn().mockReturnThis() }));

    axiosMock.get.mockResolvedValue({ data: { success: true, data: entityTypes } });
  });

  test('fetches entity types on mount with the workspace and system params', async () => {
    render(<EntityTypeGraphView workspaceId="ws-1" />);

    await waitFor(() => {
      expect(axiosMock.get).toHaveBeenCalledWith('/api/entity-types', {
        params: { workspace_id: 'ws-1', include_system: true },
      });
    });
  });

  test('shows the loading overlay while fetching', () => {
    let resolveFetch: (v: unknown) => void = () => {};
    axiosMock.get.mockReturnValue(new Promise((res) => { resolveFetch = res; }));

    render(<EntityTypeGraphView workspaceId="ws-1" />);
    expect(screen.getByText('Building Graph...')).toBeInTheDocument();

    resolveFetch({ data: { success: true, data: entityTypes } });
  });

  test('renders the legend and an svg canvas after data loads', async () => {
    const { container } = render(<EntityTypeGraphView workspaceId="ws-1" />);

    expect(await screen.findByText('System Type')).toBeInTheDocument();
    expect(screen.getByText('Custom Type')).toBeInTheDocument();
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(screen.queryByText('Building Graph...')).not.toBeInTheDocument();
  });

  test('detects $ref relationships and feeds them to the force link', async () => {
    axiosMock.get.mockResolvedValue({ data: { success: true, data: linkedTypes } });

    const d3Mock = require('d3') as any;
    const forceLink = d3Mock.forceLink as jest.Mock;

    render(<EntityTypeGraphView workspaceId="ws-1" />);
    await screen.findByText('System Type');

    await waitFor(() => {
      expect(forceLink).toHaveBeenCalled();
    });
    // The call receives the links derived from $ref properties
    const linksArg = forceLink.mock.calls[forceLink.mock.calls.length - 1][0] as any[];
    expect(linksArg).toEqual([{ source: 'customer', target: 'contact' }]);
  });

  test('clicking a node opens the details panel with type info', async () => {
    render(<EntityTypeGraphView workspaceId="ws-1" />);

    const d3Mock = require('d3') as any;
    await waitFor(() => {
      expect(typeof d3Mock.__handlers.click).toBe('function');
    });

    d3Mock.__handlers.click({ stopPropagation: jest.fn() }, { slug: 'customer' });

    expect(await screen.findByText('Type Details')).toBeInTheDocument();
    expect(screen.getByText('Customer')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
    expect(screen.getByText('customer')).toBeInTheDocument();
    expect(screen.getByText('name')).toBeInTheDocument();
    expect(screen.getByText('email')).toBeInTheDocument();
    expect(screen.getByText('contact')).toBeInTheDocument();
    expect(screen.getByText(/Properties \(3\)/)).toBeInTheDocument();
    // description is quoted in the panel
    expect(screen.getByText(/A customer record/)).toBeInTheDocument();
  });

  test('closing the details panel hides it', async () => {
    render(<EntityTypeGraphView workspaceId="ws-1" />);

    const d3Mock = require('d3') as any;
    await waitFor(() => {
      expect(typeof d3Mock.__handlers.click).toBe('function');
    });
    d3Mock.__handlers.click({ stopPropagation: jest.fn() }, { slug: 'customer' });
    expect(await screen.findByText('Type Details')).toBeInTheDocument();

    // The panel's only button is the X close button
    fireEvent.click(screen.getAllByRole('button')[0]);
    expect(screen.queryByText('Type Details')).not.toBeInTheDocument();
  });

  test('renders an empty graph without crashing when the API returns no types', async () => {
    axiosMock.get.mockResolvedValue({ data: { success: true, data: [] } });

    const { container } = render(<EntityTypeGraphView workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.queryByText('Building Graph...')).not.toBeInTheDocument();
    });
    expect(screen.getByText('System Type')).toBeInTheDocument();
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(screen.queryByText('Type Details')).not.toBeInTheDocument();
  });

  test('degrades gracefully when the fetch fails', async () => {
    axiosMock.get.mockRejectedValue(new Error('network down'));

    const { container } = render(<EntityTypeGraphView workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.queryByText('Building Graph...')).not.toBeInTheDocument();
    });
    expect(screen.getByText('System Type')).toBeInTheDocument();
    expect(container.querySelector('svg')).toBeInTheDocument();
  });
});

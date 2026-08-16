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
  const attrCallbacks: any[][] = [];

  const makeChain = (): any => ({
    append: jest.fn(() => makeChain()),
    selectAll: jest.fn(() => makeChain()),
    data: jest.fn(() => makeChain()),
    join: jest.fn(() => makeChain()),
    attr: jest.fn((...args: any[]) => {
      // record function-valued attr callbacks so tests can drive them
      if (typeof args[1] === 'function') attrCallbacks.push(args);
      return makeChain();
    }),
    style: jest.fn(() => makeChain()),
    text: jest.fn((...args: any[]) => {
      if (typeof args[0] === 'function') attrCallbacks.push(args);
      return makeChain();
    }),
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

  return {
    __handlers: handlers,
    __attrCallbacks: attrCallbacks,
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

// resetMocks (jest config) clears the factory mock implementations before
// every test — re-stub the d3 api with handler/attr recording.
const restubD3 = () => {
  const d3Mock = require('d3') as any;
  for (const key of Object.keys(d3Mock.__handlers)) delete d3Mock.__handlers[key];
  d3Mock.__attrCallbacks.length = 0;
  d3Mock.select.mockImplementation(() => d3Mock.__makeChain());
  d3Mock.forceSimulation.mockImplementation(() => d3Mock.__makeSimulation());
  d3Mock.zoom.mockImplementation(() => ({
    scaleExtent: jest.fn().mockReturnThis(),
    on: jest.fn((evt: string, cb: any) => {
      d3Mock.__handlers['zoom:' + evt] = cb;
      return undefined;
    }),
  }));
  d3Mock.drag.mockImplementation(() => {
    const dragBehavior: any = {
      on: jest.fn((evt: string, cb: any) => {
        d3Mock.__handlers['drag:' + evt] = cb;
        return dragBehavior;
      }),
    };
    return dragBehavior;
  });
  d3Mock.forceLink.mockImplementation(() => ({
    id: jest.fn((cb: any) => {
      d3Mock.__handlers['linkId'] = cb;
      return { distance: jest.fn().mockReturnThis() };
    }),
    distance: jest.fn().mockReturnThis(),
  }));
  d3Mock.forceManyBody.mockImplementation(() => ({ strength: jest.fn().mockReturnThis() }));
  d3Mock.forceCollide.mockImplementation(() => ({ radius: jest.fn().mockReturnThis() }));
  return d3Mock;
};

describe('EntityTypeGraphView', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    restubD3();
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

// ---------------------------------------------------------------------------
// Extended coverage: zoom, drag, tick and node attr callbacks
// ---------------------------------------------------------------------------
describe('EntityTypeGraphView (extended coverage)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    restubD3();
    axiosMock.get.mockResolvedValue({ data: { success: true, data: entityTypes } });
  });

  const waitForGraph = async () => {
    render(<EntityTypeGraphView workspaceId="ws-1" />);
    await screen.findByText('System Type');
    const d3Mock = require('d3') as any;
    await waitFor(() => {
      expect(typeof d3Mock.__handlers.click).toBe('function');
    });
    return d3Mock;
  };

  test('zoom handler applies the event transform to the container', async () => {
    const d3Mock = await waitForGraph();
    expect(typeof d3Mock.__handlers['zoom:zoom']).toBe('function');
    // container.attr('transform', ...) is a recorded attr call; invoking the
    // zoom handler must not throw and exercises event.transform usage
    expect(() =>
      d3Mock.__handlers['zoom:zoom']({ transform: 'translate(10,10) scale(2)' })
    ).not.toThrow();
  });

  test('forceLink id callback resolves node ids', async () => {
    const d3Mock = await waitForGraph();
    expect(typeof d3Mock.__handlers.linkId).toBe('function');
    expect(d3Mock.__handlers.linkId({ id: 'customer' })).toBe('customer');
  });

  test('drag start, drag and end handlers mutate node fixation', async () => {
    const d3Mock = await waitForGraph();
    const sim = d3Mock.forceSimulation.mock.results[0].value;
    const node = { x: 5, y: 6, fx: undefined as any, fy: undefined as any };

    d3Mock.__handlers['drag:start']({ active: false }, node);
    expect(sim.alphaTarget).toHaveBeenCalledWith(0.3);
    expect(sim.restart).toHaveBeenCalled();
    expect(node.fx).toBe(5);
    expect(node.fy).toBe(6);

    d3Mock.__handlers['drag:drag']({}, node);
    // event.x/event.y undefined -> fx/fy become undefined (no crash)
    expect(node).toBeTruthy();

    d3Mock.__handlers['drag:end']({ active: false }, node);
    expect(sim.alphaTarget).toHaveBeenCalledWith(0);
    expect(node.fx).toBeNull();
    expect(node.fy).toBeNull();
  });

  test('tick handler updates link endpoints and node transforms', async () => {
    const d3Mock = await waitForGraph();
    expect(typeof d3Mock.__handlers.tick).toBe('function');
    expect(() => d3Mock.__handlers.tick()).not.toThrow();

    // the tick handler registers x1/y1/x2/y2 attr callbacks — drive them with
    // a resolved link datum (source/target replaced by Node objects)
    const linkDatum = { source: { x: 1, y: 2 }, target: { x: 3, y: 4 } };
    for (const key of ['x1', 'y1', 'x2', 'y2']) {
      const cb = d3Mock.__attrCallbacks.find((a: any[]) => a[0] === key)![1];
      expect(() => cb(linkDatum)).not.toThrow();
    }
    expect(d3Mock.__attrCallbacks.find((a: any[]) => a[0] === 'x1')![1](linkDatum)).toBe(1);
    expect(d3Mock.__attrCallbacks.find((a: any[]) => a[0] === 'y2')![1](linkDatum)).toBe(4);
  });

  test('node circle radius, fill and label callbacks compute per-datum values', async () => {
    const d3Mock = await waitForGraph();
    await waitFor(() => {
      expect(d3Mock.__attrCallbacks.length).toBeGreaterThan(0);
    });

    const datum = { property_count: 9, is_system: true, display_name: 'Customer' };
    const rCb = d3Mock.__attrCallbacks.find((a) => a[0] === 'r')![1];
    const fillCb = d3Mock.__attrCallbacks.find((a) => a[0] === 'fill')![1];
    const dyCb = d3Mock.__attrCallbacks.find((a) => a[0] === 'dy')![1];
    const textCb = d3Mock.__attrCallbacks.find((a) => a.length === 1)![0];

    expect(rCb(datum)).toBe(15 + 3 * 2);
    expect(fillCb(datum)).toBe('#8b5cf6');
    expect(fillCb({ ...datum, is_system: false })).toBe('#10b981');
    expect(dyCb(datum)).toBe(25 + 3 * 2);
    expect(textCb(datum)).toBe('Customer');
  });

  test('unwraps non-enveloped and entity_types-wrapped API payloads', async () => {
    axiosMock.get.mockResolvedValue({ data: entityTypes });
    const { rerender } = render(<EntityTypeGraphView workspaceId="ws-1" />);
    await screen.findByText('System Type');

    axiosMock.get.mockResolvedValue({
      data: { success: false, entity_types: entityTypes },
    });
    rerender(<EntityTypeGraphView workspaceId="ws-2" />);
    await waitFor(() => {
      expect(axiosMock.get).toHaveBeenCalledWith('/api/entity-types', {
        params: { workspace_id: 'ws-2', include_system: true },
      });
    });
    // graph rebuilt from the entity_types-wrapped payload without crashing
    await screen.findByText('System Type');
  });

  test('properties without $ref and unknown $ref targets produce no links', async () => {
    const noLinks = [
      { ...entityTypes[0], json_schema: { properties: {
        plain: { type: 'string' },
        selfRef: { $ref: '#/customer' },
        other: { $ref: 'does-not-exist' },
      } } },
      entityTypes[1],
    ];
    axiosMock.get.mockResolvedValue({ data: { success: true, data: noLinks } });

    const d3Mock = require('d3') as any;
    render(<EntityTypeGraphView workspaceId="ws-1" />);
    await screen.findByText('System Type');

    await waitFor(() => expect(d3Mock.forceLink).toHaveBeenCalled());
    const linksArg = d3Mock.forceLink.mock.calls[d3Mock.forceLink.mock.calls.length - 1][0];
    expect(linksArg).toEqual([]);
  });

  test('details panel falls back to "any" for untyped properties', async () => {
    const untyped = [
      { ...entityTypes[0], json_schema: { properties: { mystery: {} } } },
    ];
    axiosMock.get.mockResolvedValue({ data: { success: true, data: untyped } });

    render(<EntityTypeGraphView workspaceId="ws-1" />);
    const d3Mock = require('d3') as any;
    await waitFor(() => {
      expect(typeof d3Mock.__handlers.click).toBe('function');
    });
    d3Mock.__handlers.click({ stopPropagation: jest.fn() }, { slug: 'customer' });

    expect(await screen.findByText('Type Details')).toBeInTheDocument();
    expect(screen.getByText('any')).toBeInTheDocument();
  });
});

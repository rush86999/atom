/**
 * AddStepEdge tests (components/Automations/AddStepEdge.tsx)
 *
 * Custom reactflow edge that renders an "Add step here" button at the
 * edge label position. Covers:
 * - the add-step button renders with the expected title
 * - clicking it calls data.onAddStep with the edge id
 * - clicking is safe when no onAddStep callback is provided
 *
 * BaseEdge/EdgeLabelRenderer are stubbed (they depend on reactflow
 * render context); getBezierPath is the real implementation.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import AddStepEdge from '@/components/Automations/AddStepEdge';

jest.mock('reactflow', () => {
  const actual = jest.requireActual('reactflow');
  return {
    ...actual,
    BaseEdge: ({ path }: { path: string }) => (
      <div data-testid="base-edge" data-path={path} />
    ),
    EdgeLabelRenderer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="edge-label-renderer">{children}</div>
    ),
  };
});

// AddStepEdge only reads id/data in these tests (BaseEdge/EdgeLabelRenderer
// are stubbed), so the required edge source/target node ids are satisfied via
// a cast instead of inventing node ids.
const baseProps = {
  id: 'edge-1',
  sourceX: 0,
  sourceY: 0,
  targetX: 100,
  targetY: 100,
  sourcePosition: 'right' as const,
  targetPosition: 'left' as const,
} as unknown as React.ComponentProps<typeof AddStepEdge>;

describe('AddStepEdge', () => {
  it('renders the edge path, label renderer and add-step button', () => {
    render(<AddStepEdge {...baseProps} />);

    const baseEdge = screen.getByTestId('base-edge');
    expect(baseEdge.getAttribute('data-path')).toContain('C');
    expect(screen.getByTestId('edge-label-renderer')).toBeInTheDocument();

    const button = screen.getByRole('button', { name: /add step here/i });
    expect(button).toBeInTheDocument();
    // The positioned label wrapper carries the reactflow nodrag/nopan classes
    expect(
      button.closest('div[class*="nodrag"]')!.className
    ).toContain('nopan');
  });

  it('calls data.onAddStep with the edge id when clicked', () => {
    const onAddStep = jest.fn();
    render(<AddStepEdge {...baseProps} data={{ onAddStep }} />);

    fireEvent.click(screen.getByRole('button', { name: /add step here/i }));

    expect(onAddStep).toHaveBeenCalledTimes(1);
    expect(onAddStep).toHaveBeenCalledWith('edge-1');
  });

  it('does not throw when data.onAddStep is missing', () => {
    render(<AddStepEdge {...baseProps} data={{}} />);

    expect(() =>
      fireEvent.click(screen.getByRole('button', { name: /add step here/i }))
    ).not.toThrow();
  });
});

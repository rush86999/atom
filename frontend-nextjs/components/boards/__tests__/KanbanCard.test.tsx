import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

jest.mock('@dnd-kit/sortable', () => ({
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: () => {},
    setActivatorNodeRef: () => {},
    transform: null,
    transition: null,
    isDragging: false,
  }),
}));
jest.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } },
}));

import { KanbanCard } from '../KanbanCard';
import { type BoardTask } from '../../../lib/boards-api';

const baseTask: BoardTask = {
  id: 'task-1',
  board_id: 'b-1',
  column_id: 'c-1',
  title: 'Sample task',
  description: 'A description',
  status: 'todo',
  priority: 'normal',
  assignee_user_id: null,
  assignee_agent_id: null,
  parent_task_id: null,
  root_task_id: null,
  sort_order: 0,
  due_at: null,
  labels: [],
  metadata_json: {},
  created_by_user_id: null,
  canvas_id: null,
  version_id: 1,
  created_at: '2026-06-28T00:00:00Z',
  updated_at: '2026-06-28T00:00:00Z',
  canvas: null,
};

describe('KanbanCard', () => {
  it('renders the task title', () => {
    render(<KanbanCard task={baseTask} />);
    expect(screen.getByLabelText('Open task: Sample task')).toBeDefined();
    expect(screen.getByText('Sample task')).toBeDefined();
  });

  it('opens the task from a normal click on the card row', () => {
    const onClick = jest.fn();
    render(<KanbanCard task={baseTask} onClick={onClick} />);

    fireEvent.click(screen.getByRole('button', { name: 'Open task: Sample task' }));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledWith(baseTask);
  });

  it('does not open the task when the drag handle is clicked', () => {
    const onClick = jest.fn();
    render(<KanbanCard task={baseTask} onClick={onClick} />);

    fireEvent.click(screen.getByRole('button', { name: 'Drag task' }));

    expect(onClick).not.toHaveBeenCalled();
  });

  it('keeps open and drag affordances as separate non-nested controls', () => {
    render(<KanbanCard task={baseTask} onClick={() => {}} />);

    const openTarget = screen.getByRole('button', { name: 'Open task: Sample task' });
    const dragTarget = screen.getByRole('button', { name: 'Drag task' });

    expect(openTarget).not.toBe(dragTarget);
    expect(openTarget.contains(dragTarget)).toBe(false);
    expect(dragTarget.contains(openTarget)).toBe(false);
    expect(openTarget.querySelector('button')).toBeNull();
    expect(dragTarget.querySelector('button')).toBeNull();

    // The drag affordance is a small bounded target, not a full-card overlay.
    expect(dragTarget.className).toContain('absolute');
    expect(dragTarget.className).toContain('h-7');
    expect(dragTarget.className).toContain('w-7');
    expect(dragTarget.className).not.toContain('inset-0');

    // Both affordances are native buttons, so Enter/Space activation works.
    expect(openTarget.tagName).toBe('BUTTON');
    expect(dragTarget.tagName).toBe('BUTTON');
    expect(dragTarget.tabIndex).toBe(0);
  });

  it('uses only phrasing elements inside the native open button', () => {
    render(<KanbanCard task={baseTask} />);

    const openTarget = screen.getByRole('button', { name: 'Open task: Sample task' });

    expect(openTarget.querySelector('div, p, h1, h2, h3, h4, h5, h6')).toBeNull();
    expect(openTarget.querySelectorAll('span').length).toBeGreaterThan(0);
  });

  it('keeps the drag grip discoverable on touch without hover', () => {
    render(<KanbanCard task={baseTask} />);

    const dragTarget = screen.getByRole('button', { name: 'Drag task' });

    expect(dragTarget.className).toContain('[@media(hover:none)]:opacity-100');
    expect(dragTarget.className).toContain('[@media(pointer:coarse)]:opacity-100');
  });

  it('renders the description when present', () => {
    render(<KanbanCard task={baseTask} />);
    expect(screen.getByText('A description')).toBeDefined();
  });

  it('renders blocked status badge', () => {
    render(<KanbanCard task={{ ...baseTask, status: 'blocked' }} />);
    expect(screen.getByText('Blocked')).toBeDefined();
  });

  it('shows artifact count when task has a canvas', () => {
    render(
      <KanbanCard
        task={{
          ...baseTask,
          canvas_id: 'cv-1',
          canvas: {
            canvas_id: 'cv-1',
            name: 'Task: X',
            status: 'active',
            artifact_count: 3,
            presence_count: 1,
          },
        }}
      />
    );
    expect(screen.getByText('3')).toBeDefined();
  });

  it('renders Untitled when title is empty', () => {
    render(<KanbanCard task={{ ...baseTask, title: '' }} />);
    expect(screen.getByText('Untitled')).toBeDefined();
  });
});

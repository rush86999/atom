import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('@dnd-kit/sortable', () => ({
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: () => {},
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
    expect(screen.getByLabelText('Task: Sample task')).toBeDefined();
    expect(screen.getByText('Sample task')).toBeDefined();
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

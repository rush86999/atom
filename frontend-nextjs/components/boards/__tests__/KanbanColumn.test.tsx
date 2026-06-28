import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('@dnd-kit/core', () => ({
  useDroppable: () => ({
    setNodeRef: () => {},
    isOver: false,
  }),
}));
jest.mock('@dnd-kit/sortable', () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  verticalListSortingStrategy: {},
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

import { KanbanColumn } from '../KanbanColumn';
import { type BoardColumn, type BoardTask } from '../../../lib/boards-api';

const column: BoardColumn = {
  id: 'col-1',
  board_id: 'b-1',
  name: 'To Do',
  position: 0,
  wip_limit: null,
  version_id: 1,
  task_count: 0,
};

const task: BoardTask = {
  id: 'task-1',
  board_id: 'b-1',
  column_id: 'col-1',
  title: 'Sample',
  description: null,
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
  created_at: '',
  updated_at: '',
  canvas: null,
};

describe('KanbanColumn', () => {
  it('renders the column name and task count', () => {
    render(<KanbanColumn column={column} tasks={[task]} />);
    expect(screen.getByText('To Do')).toBeDefined();
    expect(screen.getByText('1')).toBeDefined();
  });

  it('shows empty hint when column has no tasks', () => {
    render(<KanbanColumn column={column} tasks={[]} />);
    expect(screen.getByText('Drop tasks here')).toBeDefined();
  });

  it('shows over-WIP warning when count exceeds limit', () => {
    render(
      <KanbanColumn
        column={{ ...column, wip_limit: 1 }}
        tasks={[task, { ...task, id: 'task-2' }]}
      />
    );
    expect(screen.getByText('Over WIP limit')).toBeDefined();
  });

  it('hides WIP warning when under limit', () => {
    render(
      <KanbanColumn
        column={{ ...column, wip_limit: 5 }}
        tasks={[task]}
      />
    );
    expect(screen.queryByText('Over WIP limit')).toBeNull();
  });

  it('renders the add button', () => {
    const onAddTask = jest.fn();
    render(<KanbanColumn column={column} tasks={[]} onAddTask={onAddTask} />);
    const addBtn = screen.getByLabelText('Add task to To Do');
    expect(addBtn).toBeDefined();
  });
});

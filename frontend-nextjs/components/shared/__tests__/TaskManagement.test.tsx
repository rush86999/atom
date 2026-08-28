/**
 * Shared TaskManagement Component Tests
 *
 * Real-behavior tests for components/shared/TaskManagement.tsx:
 * - board rendering with per-status column counts and priority badges
 * - create task via dialog (callback payload, board update, toast)
 * - project assignment from the form select; "No Project" clears the field
 * - edit task via dialog (prefilled values, callback, board update)
 * - status transitions via the board check button (column moves)
 * - delete via the Upcoming Tasks trash button
 * - create/edit project via dialog; project card opens the edit dialog
 * - board ↔ list view switching
 * - status filter narrows the board and task count
 * - sort order (due date asc) in board and Upcoming sections
 * - compact view and hidden navigation
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TaskManagement, { Task, Project } from '../TaskManagement';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const DAY = 24 * 60 * 60 * 1000;
const future = (days: number) => new Date(Date.now() + days * DAY);

const makeTask = (overrides: Partial<Task> = {}): Task => ({
  id: 't-1',
  title: 'Write launch post',
  description: 'Draft the announcement',
  dueDate: future(5),
  priority: 'high',
  status: 'in-progress',
  project: 'proj-1',
  tags: ['marketing'],
  assignee: 'Ada',
  estimatedHours: 4,
  platform: 'local',
  color: '#3182CE',
  createdAt: new Date('2026-08-01'),
  updatedAt: new Date('2026-08-01'),
  ...overrides,
});

const makeProject = (overrides: Partial<Project> = {}): Project => ({
  id: 'proj-1',
  name: 'Website Launch',
  description: 'Marketing site',
  color: '#3182CE',
  tasks: [],
  progress: 40,
  ...overrides,
});

describe('TaskManagement (shared)', () => {
  const defaultProps = {
    onTaskCreate: jest.fn(),
    onTaskUpdate: jest.fn(),
    onTaskDelete: jest.fn(),
    onProjectCreate: jest.fn(),
    onProjectUpdate: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  const submitTaskForm = async (title: string) => {
    fireEvent.click(screen.getByTestId('new-task-btn'));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByTestId('task-title'), { target: { value: title } });
    fireEvent.change(document.querySelector('input[type="date"]') as HTMLInputElement, {
      target: { value: '2026-12-01' },
    });
    fireEvent.click(screen.getByTestId('task-submit'));
  };

  it('renders an empty board without crashing and shows zero counts', () => {
    render(<TaskManagement {...defaultProps} />);

    expect(screen.getByText('Task Management')).toBeInTheDocument();
    expect(screen.getByText('0 tasks')).toBeInTheDocument();
    expect(screen.getByText('TODO (0)')).toBeInTheDocument();
    expect(screen.getByText('IN PROGRESS (0)')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED (0)')).toBeInTheDocument();
    expect(screen.getByText('BLOCKED (0)')).toBeInTheDocument();
    expect(screen.getByText('Upcoming Tasks')).toBeInTheDocument();
  });

  it('buckets tasks into board columns with counts and priority badges', () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[
          makeTask({ id: 't-1', status: 'todo', priority: 'low', title: 'Fix typo' }),
          makeTask({ id: 't-2', status: 'completed', title: 'Deploy v1' }),
        ]}
      />,
    );

    expect(screen.getByText('2 tasks')).toBeInTheDocument();
    expect(screen.getByText('TODO (1)')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED (1)')).toBeInTheDocument();
    expect(screen.getByText('IN PROGRESS (0)')).toBeInTheDocument();

    const todoColumn = screen.getByText('TODO (1)').parentElement as HTMLElement;
    expect(within(todoColumn).getByText('Fix typo')).toBeInTheDocument();
    expect(within(todoColumn).getByText('low')).toBeInTheDocument();
  });

  it('lists only non-completed future tasks in Upcoming, sorted by due date', () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[
          makeTask({ id: 't-1', status: 'todo', title: 'Launch soon', dueDate: future(5) }),
          makeTask({ id: 't-2', status: 'todo', title: 'Ship later', dueDate: future(10) }),
          makeTask({ id: 't-3', status: 'completed', title: 'Already done', dueDate: future(2) }),
          makeTask({ id: 't-4', status: 'todo', title: 'Overdue task', dueDate: new Date(Date.now() - DAY) }),
        ]}
      />,
    );

    // Completed + overdue tasks appear in the board but NOT in Upcoming.
    expect(screen.getAllByText('Already done')).toHaveLength(1);
    expect(screen.getAllByText('Overdue task')).toHaveLength(1);

    const first = screen.getAllByText('Launch soon')[0];
    const second = screen.getAllByText('Ship later')[0];
    expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('creates a task through the dialog and appends it to the board', async () => {
    const onTaskCreate = jest.fn();
    render(<TaskManagement {...defaultProps} onTaskCreate={onTaskCreate} />);

    await submitTaskForm('Ship docs');

    await waitFor(() => expect(onTaskCreate).toHaveBeenCalledTimes(1));
    const created = onTaskCreate.mock.calls[0][0] as Task;
    expect(created.title).toBe('Ship docs');
    expect(created.id).toBeTruthy();
    expect(created.createdAt).toBeInstanceOf(Date);
    expect(created.updatedAt).toBeInstanceOf(Date);
    expect(created.status).toBe('todo');
    expect(created.priority).toBe('medium');
    expect(created.platform).toBe('local');

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Task created' }),
    );
    await waitFor(() => {
      expect(screen.getAllByText('Ship docs').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('1 tasks')).toBeInTheDocument();
  });

  it('assigns a project to a new task from the form select', async () => {
    const onTaskCreate = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onTaskCreate={onTaskCreate}
        initialProjects={[makeProject()]}
      />,
    );

    fireEvent.click(screen.getByTestId('new-task-btn'));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Assigned task' } });
    fireEvent.change(document.querySelector('input[type="date"]') as HTMLInputElement, {
      target: { value: '2026-12-01' },
    });

    const user = userEvent.setup();
    const projectTrigger = screen
      .getAllByText('No Project')[0]
      .closest('[role="combobox"]') as HTMLElement;
    await user.click(projectTrigger); // opens the project select
    await user.click(await screen.findByRole('option', { name: 'Website Launch' }));
    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => expect(onTaskCreate).toHaveBeenCalledTimes(1));
    expect(onTaskCreate.mock.calls[0][0].project).toBe('proj-1');
  });

  it('clears the project assignment when "No Project" is selected', async () => {
    const onTaskCreate = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onTaskCreate={onTaskCreate}
        initialProjects={[makeProject()]}
      />,
    );

    fireEvent.click(screen.getByTestId('new-task-btn'));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Standalone' } });
    fireEvent.change(document.querySelector('input[type="date"]') as HTMLInputElement, {
      target: { value: '2026-12-01' },
    });

    const user = userEvent.setup();
    const projectTrigger = screen
      .getAllByText('No Project')[0]
      .closest('[role="combobox"]') as HTMLElement;
    await user.click(projectTrigger);
    await user.click(await screen.findByRole('option', { name: 'No Project' }));
    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => expect(onTaskCreate).toHaveBeenCalledTimes(1));
    // Selecting "No Project" must NOT set the sentinel literal as the project.
    expect(onTaskCreate.mock.calls[0][0].project).toBeUndefined();
  });

  it('edits a task via the dialog with prefilled values', async () => {
    const onTaskUpdate = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onTaskUpdate={onTaskUpdate}
        initialTasks={[makeTask()]}
        initialProjects={[makeProject()]}
      />,
    );

    fireEvent.click(screen.getAllByText('Write launch post')[0]);
    await screen.findByRole('dialog');
    expect(screen.getByText('Edit Task')).toBeInTheDocument();
    expect((screen.getByTestId('task-title') as HTMLInputElement).value).toBe('Write launch post');

    fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Write launch post v2' } });
    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => expect(onTaskUpdate).toHaveBeenCalledTimes(1));
    expect(onTaskUpdate.mock.calls[0][0]).toBe('t-1');
    expect(onTaskUpdate.mock.calls[0][1]).toEqual(
      expect.objectContaining({ title: 'Write launch post v2' }),
    );
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Task updated' }),
    );
    expect(await screen.findAllByText('Write launch post v2')).toHaveLength(2);
  });

  it('moves a task between columns when marked complete via the check button', async () => {
    const onTaskUpdate = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onTaskUpdate={onTaskUpdate}
        initialTasks={[makeTask({ id: 't-1', status: 'in-progress', title: 'In flight' })]}
      />,
    );

    const inProgressCol = screen.getByText('IN PROGRESS (1)').parentElement as HTMLElement;
    const checkBtn = within(inProgressCol).getByRole('button');
    fireEvent.click(checkBtn);

    await waitFor(() => expect(onTaskUpdate).toHaveBeenCalledWith('t-1', { status: 'completed' }));
    expect(screen.getByText('IN PROGRESS (0)')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED (1)')).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Task updated' }),
    );
  });

  it('deletes a task from the Upcoming list via the trash button', async () => {
    const onTaskDelete = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onTaskDelete={onTaskDelete}
        initialTasks={[makeTask({ id: 't-1', title: 'Doomed task' })]}
      />,
    );

    const row = screen
      .getAllByText('Doomed task')
      .map((el) => el.closest('.flex.justify-between'))
      .find((el) => el && el.querySelector('svg.lucide-trash')) as HTMLElement;
    const trashBtn = row.querySelector('button svg.lucide-trash')?.closest('button');
    fireEvent.click(trashBtn as HTMLElement);

    await waitFor(() => expect(onTaskDelete).toHaveBeenCalledWith('t-1'));
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Task deleted' }),
    );
    expect(screen.queryByText('Doomed task')).not.toBeInTheDocument();
    expect(screen.getByText('0 tasks')).toBeInTheDocument();
  });

  it('creates a project through the dialog', async () => {
    const onProjectCreate = jest.fn();
    render(<TaskManagement {...defaultProps} onProjectCreate={onProjectCreate} />);

    fireEvent.click(screen.getByRole('button', { name: /new project/i }));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByPlaceholderText('Project name'), { target: { value: 'Q4 Rebrand' } });
    fireEvent.change(screen.getByPlaceholderText('Project description'), {
      target: { value: 'Brand refresh' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Project' }));

    await waitFor(() => expect(onProjectCreate).toHaveBeenCalledTimes(1));
    const created = onProjectCreate.mock.calls[0][0] as Project;
    expect(created.name).toBe('Q4 Rebrand');
    expect(created.id).toBeTruthy();
    expect(created.tasks).toEqual([]);
    expect(created.progress).toBe(0);

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Project created' }),
    );
    expect(await screen.findByText('Q4 Rebrand')).toBeInTheDocument();
    expect(screen.getByText(/0 tasks • 0% complete/)).toBeInTheDocument();
  });

  it('opens the edit dialog when a project card is clicked and saves updates', async () => {
    const onProjectUpdate = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onProjectUpdate={onProjectUpdate}
        initialProjects={[makeProject()]}
      />,
    );

    const card = screen.getByText('Website Launch').closest('.cursor-pointer') as HTMLElement;
    fireEvent.click(card);
    await screen.findByRole('dialog');
    expect(screen.getByText('Edit Project')).toBeInTheDocument();
    expect((screen.getByPlaceholderText('Project name') as HTMLInputElement).value).toBe(
      'Website Launch',
    );

    fireEvent.change(screen.getByPlaceholderText('Project name'), { target: { value: 'Rebrand 2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Update Project' }));

    await waitFor(() => expect(onProjectUpdate).toHaveBeenCalledTimes(1));
    expect(onProjectUpdate.mock.calls[0][0]).toBe('proj-1');
    expect(onProjectUpdate.mock.calls[0][1]).toEqual(
      expect.objectContaining({ name: 'Rebrand 2026' }),
    );
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Project updated' }),
    );
    expect(await screen.findByText('Rebrand 2026')).toBeInTheDocument();
  });

  it('switches between board and list views', async () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[makeTask({ id: 't-1', status: 'todo', title: 'View me' })]}
      />,
    );

    expect(screen.getByText('Task Board')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /list/i }));
    expect(screen.queryByText('Task Board')).not.toBeInTheDocument();
    expect(screen.getByText('Task List')).toBeInTheDocument();
    expect(screen.getAllByText('View me').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('todo').length).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole('button', { name: /board/i }));
    expect(screen.getByText('Task Board')).toBeInTheDocument();
    expect(screen.queryByText('Task List')).not.toBeInTheDocument();
  });

  it('filters the board by status via the filter select', async () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[
          makeTask({ id: 't-1', status: 'todo', title: 'Todo task' }),
          makeTask({ id: 't-2', status: 'in-progress', title: 'Wip task' }),
        ]}
      />,
    );

    expect(screen.getByText('2 tasks')).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByTestId('status-filter'));
    await user.click(await screen.findByRole('option', { name: 'To Do' }));

    expect(screen.getByText('1 tasks')).toBeInTheDocument();
    expect(screen.getAllByText('Todo task').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryAllByText('Wip task')).toHaveLength(0);
    expect(screen.getByText('TODO (1)')).toBeInTheDocument();
    expect(screen.getByText('IN PROGRESS (0)')).toBeInTheDocument();

    await user.click(screen.getByTestId('status-filter'));
    await user.click(await screen.findByRole('option', { name: 'All statuses' }));

    expect(screen.getByText('2 tasks')).toBeInTheDocument();
  });

  it('filters the board by priority via the priority filter select', async () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[
          makeTask({ id: 't-1', priority: 'high', title: 'Urgent task' }),
          makeTask({ id: 't-2', priority: 'low', title: 'Chill task' }),
        ]}
      />,
    );

    expect(screen.getByText('2 tasks')).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByTestId('priority-filter'));
    await user.click(await screen.findByRole('option', { name: 'High' }));

    expect(screen.getByText('1 tasks')).toBeInTheDocument();
    expect(screen.getAllByText('Urgent task').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryAllByText('Chill task')).toHaveLength(0);

    await user.click(screen.getByTestId('priority-filter'));
    await user.click(await screen.findByRole('option', { name: 'All priorities' }));

    expect(screen.getByText('2 tasks')).toBeInTheDocument();
  });

  it('sorts tasks by priority and title via the sort select', async () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[
          makeTask({ id: 't-1', priority: 'low', title: 'Banana', status: 'todo' }),
          makeTask({ id: 't-2', priority: 'high', title: 'Cherry', status: 'todo' }),
          makeTask({ id: 't-3', priority: 'low', title: 'Apple', status: 'todo' }),
        ]}
      />,
    );

    const user = userEvent.setup();
    await user.click(screen.getByTestId('sort-select'));
    await user.click(await screen.findByRole('option', { name: 'Priority ↓' }));

    // High-priority task first in the board column
    const todoColumn = (screen.getByText('TODO (3)').closest('div') as HTMLElement).parentElement!;
    const titles = within(todoColumn as HTMLElement)
      .getAllByText(/^(Banana|Cherry|Apple)$/)
      .map((el) => el.textContent);
    expect(titles[0]).toBe('Cherry');

    await user.click(screen.getByTestId('sort-select'));
    await user.click(await screen.findByRole('option', { name: 'Title A-Z' }));

    const sortedTitles = within((screen.getByText('TODO (3)').closest('div') as HTMLElement).parentElement as HTMLElement)
      .getAllByText(/^(Banana|Cherry|Apple)$/)
      .map((el) => el.textContent);
    expect(sortedTitles).toEqual(['Apple', 'Banana', 'Cherry']);
  });

  it('opens the edit dialog when an Upcoming row is clicked', async () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[makeTask({ id: 't-1', title: 'Row target' })]}
      />,
    );

    const row = screen
      .getAllByText('Row target')
      .map((el) => el.closest('.flex.justify-between'))
      .find((el) => el && el.querySelector('svg.lucide-trash')) as HTMLElement;
    fireEvent.click(row);

    await screen.findByRole('dialog');
    expect(screen.getByText('Edit Task')).toBeInTheDocument();
    expect((screen.getByTestId('task-title') as HTMLInputElement).value).toBe('Row target');
  });

  it('opens the edit dialog from the Upcoming edit button', async () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[makeTask({ id: 't-1', title: 'Edit me' })]}
      />,
    );

    const row = screen
      .getAllByText('Edit me')
      .map((el) => el.closest('.flex.justify-between'))
      .find((el) => el && el.querySelector('svg.lucide-square-pen')) as HTMLElement;
    const editBtn = row.querySelector('button svg.lucide-square-pen')?.closest('button');
    fireEvent.click(editBtn as HTMLElement);

    await screen.findByRole('dialog');
    expect(screen.getByText('Edit Task')).toBeInTheDocument();
    expect((screen.getByTestId('task-title') as HTMLInputElement).value).toBe('Edit me');
  });

  it('captures priority, status, platform and color from the form controls', async () => {
    const onTaskCreate = jest.fn();
    render(<TaskManagement {...defaultProps} onTaskCreate={onTaskCreate} />);

    fireEvent.click(screen.getByTestId('new-task-btn'));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Configured task' } });
    fireEvent.change(document.querySelector('input[type="date"]') as HTMLInputElement, {
      target: { value: '2026-12-01' },
    });

    const user = userEvent.setup();

    const priorityTrigger = screen
      .getAllByText('Medium')[0]
      .closest('[role="combobox"]') as HTMLElement;
    await user.click(priorityTrigger);
    await user.click(await screen.findByRole('option', { name: 'High' }));

    const statusTrigger = screen
      .getAllByText('To Do')[0]
      .closest('[role="combobox"]') as HTMLElement;
    await user.click(statusTrigger);
    await user.click(await screen.findByRole('option', { name: 'In Progress' }));

    const platformTrigger = screen
      .getAllByText('Local')[0]
      .closest('[role="combobox"]') as HTMLElement;
    await user.click(platformTrigger);
    await user.click(await screen.findByRole('option', { name: 'Jira' }));

    fireEvent.change(document.querySelector('input[type="color"]') as HTMLInputElement, {
      target: { value: '#123456' },
    });

    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => expect(onTaskCreate).toHaveBeenCalledTimes(1));
    const created = onTaskCreate.mock.calls[0][0] as Task;
    expect(created.priority).toBe('high');
    expect(created.status).toBe('in-progress');
    expect(created.platform).toBe('jira');
    expect(created.color).toBe('#123456');
  });

  it('renders compact view', () => {
    const { container } = render(
      <TaskManagement {...defaultProps} compactView initialTasks={[makeTask()]} />,
    );

    expect(container.firstChild).toHaveClass('p-2');
    expect(screen.getByText('Task Management')).toBeInTheDocument();
  });

  it('hides the header and view controls when showNavigation is false', () => {
    render(
      <TaskManagement
        {...defaultProps}
        showNavigation={false}
        initialTasks={[makeTask({ id: 't-1', title: 'Still visible' })]}
      />,
    );

    expect(screen.queryByText('Task Management')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /new task/i })).not.toBeInTheDocument();
    expect(screen.getByText('Task Board')).toBeInTheDocument();
    expect(screen.getAllByText('Still visible').length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: full task form fields, list-row click, variant defaults
// ---------------------------------------------------------------------------
describe('TaskManagement (extended coverage)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const defaultProps = {
    onTaskCreate: jest.fn(),
    onTaskUpdate: jest.fn(),
    onTaskDelete: jest.fn(),
    onProjectCreate: jest.fn(),
    onProjectUpdate: jest.fn(),
  };

  it('fills estimated hours, tags, assignee, and color in the task dialog', async () => {
    const onTaskCreate = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onTaskCreate={onTaskCreate}
        initialProjects={[makeProject()]}
      />,
    );

    fireEvent.click(screen.getByTestId('new-task-btn'));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByTestId('task-title'), {
      target: { value: 'Full Form Task' },
    });
    fireEvent.change(
      document.querySelector('input[type="date"]') as HTMLInputElement,
      { target: { value: '2026-12-01' } },
    );
    fireEvent.change(dialog.querySelector('input[type="number"]') as HTMLInputElement, {
      target: { value: '8' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText(/backend, frontend, design/i), {
      target: { value: 'backend, infra' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText(/assignee name/i), {
      target: { value: 'Grace Hopper' },
    });
    const colorInput = dialog.querySelector('input[type="color"]') as HTMLInputElement;
    fireEvent.change(colorInput, { target: { value: '#E53E3E' } });

    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => {
      expect(onTaskCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Full Form Task',
          estimatedHours: 8,
          tags: ['backend', 'infra'],
          assignee: 'Grace Hopper',
          color: '#e53e3e',
        }),
      );
    });
  });

  it('opens the task dialog from a compact list-view row', async () => {
    render(
      <TaskManagement
        {...defaultProps}
        compactView
        initialTasks={[makeTask()]}
        initialProjects={[makeProject()]}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /list/i }));
    const titleEl = screen
      .getAllByText('Write launch post')
      .find((el) => el.closest('.cursor-pointer'));
    const row = titleEl!.closest('.cursor-pointer') as HTMLElement;
    fireEvent.click(row);

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('task-title')).toHaveValue('Write launch post');
  });

  it('renders default variants for unknown priorities and statuses in list view', () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[
          makeTask({ id: 't-1', status: 'completed', priority: 'medium' }),
          makeTask({ id: 't-2', status: 'blocked', priority: 'low' }),
          makeTask({ id: 't-3', status: 'archived', priority: 'urgent' } as any),
        ]}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /list/i }));

    // All rows render with their status badges; unknown statuses fall through
    // to the default badge variant without crashing.
    expect(screen.getAllByText('completed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('blocked').length).toBeGreaterThan(0);
    expect(screen.getAllByText('archived').length).toBeGreaterThan(0);
  });
});

describe('TaskManagement (extended coverage 2)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const defaultProps = {
    onTaskCreate: jest.fn(),
    onTaskUpdate: jest.fn(),
    onTaskDelete: jest.fn(),
    onProjectCreate: jest.fn(),
    onProjectUpdate: jest.fn(),
  };

  it('renders an unknown priority badge in the board', () => {
    render(
      <TaskManagement
        {...defaultProps}
        initialTasks={[
          makeTask({ id: 't-9', status: 'todo', priority: 'urgent' as any, title: 'Odd task' }),
        ]}
      />,
    );

    expect(screen.getByText('urgent')).toBeInTheDocument();
  });

  it('edits the task description and the project color', async () => {
    const onTaskUpdate = jest.fn();
    render(
      <TaskManagement
        {...defaultProps}
        onTaskUpdate={onTaskUpdate}
        initialTasks={[makeTask()]}
        initialProjects={[makeProject()]}
      />,
    );

    // Task dialog: change the description and save
    fireEvent.click(screen.getAllByText('Write launch post')[0]);
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByPlaceholderText(/task description/i), {
      target: { value: 'Updated description' },
    });
    fireEvent.click(screen.getByTestId('task-submit'));
    await waitFor(() => {
      expect(onTaskUpdate).toHaveBeenCalledWith(
        't-1',
        expect.objectContaining({ description: 'Updated description' }),
      );
    });

    // Project dialog: change the color and save
    fireEvent.click(screen.getByText('Website Launch'));
    const projectDialog = await screen.findByRole('dialog');
    const colorInput = projectDialog.querySelector(
      'input[type="color"]',
    ) as HTMLInputElement;
    fireEvent.change(colorInput, { target: { value: '#E53E3E' } });
    fireEvent.click(
      within(projectDialog).getByRole('button', { name: /update project/i }),
    );
    await waitFor(() => {
      expect(defaultProps.onProjectUpdate).toHaveBeenCalledWith(
        'proj-1',
        expect.objectContaining({ color: '#e53e3e' }),
      );
    });
  });
});

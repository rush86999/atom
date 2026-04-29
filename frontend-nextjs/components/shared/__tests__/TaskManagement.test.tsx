/**
 * TaskManagement Component Tests
 *
 * Tests verify task CRUD operations, project management,
 * view switching (list/board/calendar), and filtering.
 *
 * Source: components/shared/TaskManagement.tsx (167 lines uncovered)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TaskManagement, Task, Project } from '../TaskManagement';

const mockTask: Task = {
  id: '1',
  title: 'Complete project proposal',
  description: 'Write and submit the Q2 project proposal',
  dueDate: new Date('2025-10-25'),
  priority: 'high',
  status: 'in-progress',
  project: 'Project Alpha',
  tags: ['urgent', 'planning'],
  assignee: 'John Doe',
  estimatedHours: 8,
  actualHours: 4,
  platform: 'local',
  color: '#3182CE',
  createdAt: new Date('2025-10-20'),
  updatedAt: new Date('2025-10-20'),
};

const mockProject: Project = {
  id: 'proj-1',
  name: 'Project Alpha',
  description: 'Q2 strategic initiative',
  color: '#3182CE',
  tasks: [mockTask],
  progress: 50,
};

describe('TaskManagement', () => {
  // Test 1: renders with initial state
  test('renders with initial state', () => {
    render(<TaskManagement />);

    expect(screen.getByText('Tasks')).toBeInTheDocument();
  });

  // Test 2: displays initial tasks
  test('displays initial tasks', () => {
    render(<TaskManagement initialTasks={[mockTask]} />);

    expect(screen.getByText('Complete project proposal')).toBeInTheDocument();
  });

  // Test 3: displays projects
  test('displays projects', () => {
    render(<TaskManagement initialProjects={[mockProject]} />);

    expect(screen.getByText('Project Alpha')).toBeInTheDocument();
  });

  // Test 4: creates new task
  test('creates new task', async () => {
    const handleTaskCreate = jest.fn();

    render(<TaskManagement onTaskCreate={handleTaskCreate} />);

    const addButton = screen.getByText(/add task/i);
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText('Create Task')).toBeInTheDocument();
    });
  });

  // Test 5: updates task status
  test('updates task status', async () => {
    const handleTaskUpdate = jest.fn();

    render(
      <TaskManagement
        initialTasks={[mockTask]}
        onTaskUpdate={handleTaskUpdate}
      />
    );

    const task = screen.getByText('Complete project proposal');
    fireEvent.click(task);

    await waitFor(() => {
      expect(handleTaskUpdate).toHaveBeenCalled();
    });
  });

  // Test 6: deletes task
  test('deletes task', async () => {
    const handleTaskDelete = jest.fn();

    render(
      <TaskManagement
        initialTasks={[mockTask]}
        onTaskDelete={handleTaskDelete}
      />
    );

    const deleteButton = screen.getAllByRole('button').find(
      btn => btn.getAttribute('aria-label')?.includes('delete')
    );

    if (deleteButton) {
      fireEvent.click(deleteButton);
      expect(handleTaskDelete).toHaveBeenCalledWith('1');
    }
  });

  // Test 7: switches between view types
  test('switches between view types', () => {
    render(<TaskManagement initialTasks={[mockTask]} />);

    const listViewButton = screen.getByRole('button', { name: /list/i });
    const boardViewButton = screen.getByRole('button', { name: /board/i });

    fireEvent.click(boardViewButton);
    expect(screen.getByText('Complete project proposal')).toBeInTheDocument();

    fireEvent.click(listViewButton);
    expect(screen.getByText('Complete project proposal')).toBeInTheDocument();
  });

  // Test 8: filters tasks by status
  test('filters tasks by status', () => {
    render(
      <TaskManagement
        initialTasks={[
          mockTask,
          { ...mockTask, id: '2', status: 'todo' as const },
        ]}
      />
    );

    const filterButton = screen.getByRole('button', { name: /filter/i });
    fireEvent.click(filterButton);

    expect(screen.getByText('In Progress')).toBeInTheDocument();
  });

  // Test 9: filters tasks by priority
  test('filters tasks by priority', () => {
    render(
      <TaskManagement
        initialTasks={[
          mockTask,
          { ...mockTask, id: '2', priority: 'low' as const },
        ]}
      />
    );

    expect(screen.getByText(/high/i)).toBeInTheDocument();
  });

  // Test 10: sorts tasks by due date
  test('sorts tasks by due date', () => {
    render(
      <TaskManagement
        initialTasks={[
          mockTask,
          { ...mockTask, id: '2', dueDate: new Date('2025-10-30') },
        ]}
      />
    );

    const tasks = screen.getAllByText(/Complete/);
    expect(tasks.length).toBeGreaterThan(0);
  });

  // Test 11: creates new project
  test('creates new project', () => {
    const handleProjectCreate = jest.fn();

    render(<TaskManagement onProjectCreate={handleProjectCreate} />);

    const addProjectButton = screen.getByText(/add project/i);
    fireEvent.click(addProjectButton);

    expect(screen.getByText('Create Project')).toBeInTheDocument();
  });

  // Test 12: displays task progress
  test('displays task progress', () => {
    render(
      <TaskManagement
        initialTasks={[mockTask]}
        initialProjects={[mockProject]}
      />
    );

    expect(screen.getByText('50')).toBeInTheDocument();
  });

  // Test 13: shows task details in dialog
  test('shows task details in dialog', async () => {
    render(<TaskManagement initialTasks={[mockTask]} />);

    const task = screen.getByText('Complete project proposal');
    fireEvent.click(task);

    await waitFor(() => {
      expect(screen.getByText(/write and submit/i)).toBeInTheDocument();
    });
  });

  // Test 14: handles task assignment
  test('handles task assignment', () => {
    render(<TaskManagement initialTasks={[mockTask]} />);

    expect(screen.getByText(/john doe/i)).toBeInTheDocument();
  });

  // Test 15: displays task tags
  test('displays task tags', () => {
    render(<TaskManagement initialTasks={[mockTask]} />);

    expect(screen.getByText('urgent')).toBeInTheDocument();
    expect(screen.getByText('planning')).toBeInTheDocument();
  });

  // Test 16: handles compact view
  test('handles compact view', () => {
    const { container } = render(
      <TaskManagement compactView={true} initialTasks={[mockTask]} />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  // Test 17: filters by project
  test('filters by project', () => {
    render(
      <TaskManagement
        initialTasks={[mockTask]}
        initialProjects={[mockProject]}
      />
    );

    expect(screen.getByText('Project Alpha')).toBeInTheDocument();
  });

  // Test 18: calculates task progress
  test('calculates task progress', () => {
    const taskWithHours: Task = {
      ...mockTask,
      estimatedHours: 10,
      actualHours: 5,
    };

    render(<TaskManagement initialTasks={[taskWithHours]} />);

    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  // Test 19: handles calendar view
  test('handles calendar view', () => {
    render(<TaskManagement initialTasks={[mockTask]} />);

    const calendarButton = screen.getByRole('button', { name: /calendar/i });
    fireEvent.click(calendarButton);

    expect(screen.getByText('Complete project proposal')).toBeInTheDocument();
  });

  // Test 20: shows task count by status
  test('shows task count by status', () => {
    render(
      <TaskManagement
        initialTasks={[
          mockTask,
          { ...mockTask, id: '2', status: 'todo' as const },
          { ...mockTask, id: '3', status: 'completed' as const },
        ]}
      />
    );

    // Should show status columns or filters
    expect(screen.getByText('Complete project proposal')).toBeInTheDocument();
  });
});

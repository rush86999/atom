import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import TaskManagement, { Task } from '@/components/shared/TaskManagement';
const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({ useToast: () => ({ toast: mockToast }) }));
const task = (): Task => ({ id: 'server-task-id', title: 'Confirmed task', status: 'todo', priority: 'medium', platform: 'local', dueDate: new Date(Date.now() + 86400000), createdAt: new Date(), updatedAt: new Date() });
async function submit(title: string) {
  fireEvent.click(screen.getByTestId('new-task-btn'));
  await screen.findByRole('dialog');
  fireEvent.change(screen.getByTestId('task-title'), { target: { value: title } });
  const date = document.querySelector('input[type="date"]');
  if (!date) throw new Error('date input missing');
  fireEvent.change(date, { target: { value: '2026-12-01' } });
  fireEvent.click(screen.getByTestId('task-submit'));
}
beforeEach(() => mockToast.mockReset());
test('pending backend create has no visible completed record or success toast', async () => {
  const callback = jest.fn(() => new Promise<Task>(() => {}));
  render(<TaskManagement onTaskCreate={callback} />);
  await submit('Not confirmed yet');
  await waitFor(() => expect(callback).toHaveBeenCalledTimes(1));
  expect(screen.queryByText('Not confirmed yet')).not.toBeInTheDocument();
  expect(mockToast).not.toHaveBeenCalledWith(expect.objectContaining({ title: 'Task created' }));
});
test('later edits use the confirmed server create identity', async () => {
  const update = jest.fn();
  render(<TaskManagement onTaskCreate={jest.fn(async () => task())} onTaskUpdate={update} />);
  await submit('Confirmed task');
  await waitFor(() => expect(screen.getAllByText('Confirmed task').length).toBeGreaterThan(0));
  const column = screen.getByText('TODO (1)').parentElement;
  if (!column) throw new Error('column missing');
  fireEvent.click(within(column).getByRole('button'));
  await waitFor(() => expect(update).toHaveBeenCalledWith('server-task-id', { status: 'completed' }));
});
test('a refused backend deletion keeps the existing record and never toasts success', async () => {
  const rejection = Promise.reject(new Error('controlled refusal'));
  rejection.catch(() => {});
  const remove = jest.fn(() => rejection);
  render(<TaskManagement initialTasks={[task()]} onTaskDelete={remove} />);
  const row = screen.getAllByText('Confirmed task').map(el => el.closest('.flex.justify-between')).find(el => el?.querySelector('svg.lucide-trash'));
  const button = row?.querySelector('svg.lucide-trash')?.closest('button');
  if (!button) throw new Error('delete button missing');
  fireEvent.click(button);
  await waitFor(() => expect(remove).toHaveBeenCalledTimes(1));
  expect(screen.getAllByText('Confirmed task').length).toBeGreaterThan(0);
  expect(mockToast).not.toHaveBeenCalledWith(expect.objectContaining({ title: 'Task deleted' }));
});
test('an ordinary parent rerender preserves an unfinished task draft', async () => {
  const callback = jest.fn();
  const view = render(<TaskManagement onTaskCreate={callback} />);
  fireEvent.click(screen.getByTestId('new-task-btn'));
  await screen.findByRole('dialog');
  fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Keep this unfinished draft' } });
  view.rerender(<TaskManagement onTaskCreate={callback} />);
  expect(screen.getByTestId('task-title')).toHaveValue('Keep this unfinished draft');
});

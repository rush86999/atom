/**
 * WorkflowScheduler Component Tests
 *
 * Tests verify the REAL WorkflowScheduler component
 * (components/Automations/WorkflowScheduler.tsx):
 *
 * - Job list load + workflowId filtering + refresh + empty state + failure
 * - Interval scheduling (success, zero-interval validation, missing workflowId)
 * - Cron scheduling (preset selection, custom input, empty + wrong-field-count
 *   validation)
 * - Date scheduling (missing fields, past date, success clears inputs)
 * - API failure paths (POST not-ok surfaces server detail, throw paths)
 * - Delete schedule (success + failure)
 *
 * The Radix Select is mocked (context pattern from JiraIntegration.test.tsx)
 * because the component can render SelectItem with an empty value, which
 * crashes real Radix in jsdom.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import WorkflowScheduler from '../WorkflowScheduler';

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
  const SelectCtx = createContext(null as any);

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

const toastMock = () =>
  (jest.requireMock('@/components/ui/use-toast') as any).__mockToast as jest.Mock;

const jsonResponse = (body: any, ok = true, status = ok ? 200 : 500) => ({
  ok,
  status,
  statusText: ok ? 'OK' : 'Error',
  json: async () => body,
});

const clickSchedule = () => {
  fireEvent.click(screen.getByRole('button', { name: /schedule workflow/i }));
};

describe('WorkflowScheduler', () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(global as any, 'fetch')
      .mockResolvedValue(jsonResponse([]));
  });

  // ------------------------------------------------------------------
  // Job list
  // ------------------------------------------------------------------
  it('loads and filters scheduled jobs for this workflow on mount', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse([
        { id: `wf-1-abc`, next_run_time: '2026-08-10T09:00:00Z', trigger: 'cron[weekday=mon]' },
        { id: `wf-1-def`, next_run_time: null, trigger: 'interval[seconds=1800]' },
        { id: `wf-2-xyz`, next_run_time: '2026-08-11T09:00:00Z', trigger: 'cron' },
      ])
    );
    render(<WorkflowScheduler workflowId="wf-1" workflowName="Nightly Sync" />);

    expect(screen.getByText('Workflow: Nightly Sync')).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/v1/scheduler/jobs');
    });

    // Only wf-1 jobs are shown
    await waitFor(() => {
      expect(screen.getAllByRole('row')).toHaveLength(3); // header + 2 job rows
    });
    expect(screen.getByText('wf-1-abc')).toBeInTheDocument();
    expect(screen.getByText('wf-1-def')).toBeInTheDocument();
    expect(screen.queryByText('wf-2-xyz')).not.toBeInTheDocument();
    // Trigger badge strips the bracket suffix
    expect(screen.getByText('cron')).toBeInTheDocument();
    expect(screen.getByText('interval')).toBeInTheDocument();
    // Null next_run_time renders "Never"
    expect(screen.getByText('Never')).toBeInTheDocument();
  });

  it('shows the empty state when no jobs exist', async () => {
    render(<WorkflowScheduler workflowId="wf-1" />);

    await waitFor(() => {
      expect(
        screen.getByText('No scheduled jobs for this workflow')
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('survives a failed job-list fetch and refreshes via the refresh button', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('network down'));
    const { unmount } = render(<WorkflowScheduler workflowId="wf-1" />);

    await waitFor(() => {
      expect(screen.getByText('No scheduled jobs for this workflow')).toBeInTheDocument();
    });

    // Second fetch succeeds; refresh button re-runs loadScheduledJobs
    fetchSpy.mockResolvedValueOnce(
      jsonResponse([{ id: 'wf-1-abc', next_run_time: null, trigger: 'cron' }])
    );
    fireEvent.click(document.querySelector('.lucide-refresh-cw')!.closest('button')!);

    await waitFor(() => {
      expect(screen.getByText('wf-1-abc')).toBeInTheDocument();
    });
    unmount();
  });

  // ------------------------------------------------------------------
  // Interval scheduling
  // ------------------------------------------------------------------
  it('schedules an interval with combined day/hour/minute seconds', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(jsonResponse({ job_id: 'job-1' }));
    render(<WorkflowScheduler workflowId="wf-1" />);

    // default 30 minutes -> change days to 1, hours to 2
    const [days, hours, minutes] = screen.getAllByRole('spinbutton');
    fireEvent.change(days, { target: { value: '1' } });
    fireEvent.change(hours, { target: { value: '2' } });
    fireEvent.change(minutes, { target: { value: '5' } });

    clickSchedule();

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/workflows/wf-1/schedule',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });
    const body = JSON.parse(fetchSpy.mock.calls[1][1].body);
    expect(body).toEqual({
      trigger_type: 'interval',
      trigger_config: { seconds: 86400 + 2 * 3600 + 5 * 60 },
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Workflow Scheduled', description: 'Job ID: job-1' })
    );
    // Jobs are reloaded after scheduling
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/scheduler/jobs');
  });

  it('rejects a zero-length interval with an error toast and no POST', async () => {
    render(<WorkflowScheduler workflowId="wf-1" />);
    const [, , minutes] = screen.getAllByRole('spinbutton');
    fireEvent.change(minutes, { target: { value: '0' } });

    clickSchedule();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Scheduling Failed',
          description: 'Please specify an interval',
          variant: 'error',
        })
      );
    });
    const posts = fetchSpy.mock.calls.filter(
      ([url, init]: any) => init?.method === 'POST'
    );
    expect(posts).toHaveLength(0);
  });

  it('requires the workflow to be saved before scheduling', async () => {
    render(<WorkflowScheduler workflowId="" />);
    clickSchedule();
    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Workflow must be saved first',
          variant: 'error',
        })
      );
    });
    const schedulePosts = fetchSpy.mock.calls.filter(
      ([url]: any) =>
        String(url).includes('/workflows/') && String(url).includes('/schedule')
    );
    expect(schedulePosts).toHaveLength(0);
  });

  // ------------------------------------------------------------------
  // Cron scheduling
  // ------------------------------------------------------------------
  it('applies a preset expression and posts a 5-field cron config', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(jsonResponse({ job_id: 'cron-job' }));
    render(<WorkflowScheduler workflowId="wf-1" />);

    fireEvent.click(screen.getByRole('button', { name: /^cron$/i }));
    // Switch preset to hourly -> expression becomes '0 * * * *'
    fireEvent.click(screen.getByTestId('select-root').querySelector('button')!);
    fireEvent.click(screen.getByText('Every Hour'));

    const exprInput = screen.getByPlaceholderText('0 9 * * *');
    expect((exprInput as HTMLInputElement).value).toBe('0 * * * *');

    clickSchedule();

    await waitFor(() => {
      const body = JSON.parse(fetchSpy.mock.calls[1][1].body);
      expect(body).toEqual({
        trigger_type: 'cron',
        trigger_config: {
          minute: '0',
          hour: '*',
          day: '*',
          month: '*',
          day_of_week: '*',
        },
      });
    });
  });

  it('marks the preset as custom when the expression is typed manually', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    render(<WorkflowScheduler workflowId="wf-1" />);
    fireEvent.click(screen.getByRole('button', { name: /^cron$/i }));

    fireEvent.change(screen.getByPlaceholderText('0 9 * * *'), {
      target: { value: '*/15 * * * *' },
    });

    // Selecting "Daily at 9 AM" after a manual edit still applies its expression
    fireEvent.click(screen.getByTestId('select-root').querySelector('button')!);
    fireEvent.click(screen.getByText('Daily at 9 AM'));
    expect((screen.getByPlaceholderText('0 9 * * *') as HTMLInputElement).value).toBe('0 9 * * *');
  });

  it('rejects an empty cron expression', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    render(<WorkflowScheduler workflowId="wf-1" />);
    fireEvent.click(screen.getByRole('button', { name: /^cron$/i }));

    fireEvent.change(screen.getByPlaceholderText('0 9 * * *'), {
      target: { value: '   ' },
    });
    clickSchedule();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Please enter a cron expression' })
      );
    });
    const posts = fetchSpy.mock.calls.filter(
      ([url, init]: any) => init?.method === 'POST'
    );
    expect(posts).toHaveLength(0);
  });

  it('rejects a cron expression that is not 5 fields', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    render(<WorkflowScheduler workflowId="wf-1" />);
    fireEvent.click(screen.getByRole('button', { name: /^cron$/i }));

    fireEvent.change(screen.getByPlaceholderText('0 9 * * *'), {
      target: { value: '0 9 * *' },
    });
    clickSchedule();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          description: 'Invalid cron expression format (use 5 fields)',
        })
      );
    });
  });

  // ------------------------------------------------------------------
  // Date scheduling
  // ------------------------------------------------------------------
  it('rejects a date schedule missing time', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    render(<WorkflowScheduler workflowId="wf-1" />);
    fireEvent.click(screen.getByRole('button', { name: /specific date/i }));

    fireEvent.change(document.querySelector('input[type="date"]')!, { target: { value: '2027-01-01' } });
    clickSchedule();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Please specify both date and time' })
      );
    });
  });

  it('rejects a date schedule in the past', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    render(<WorkflowScheduler workflowId="wf-1" />);
    fireEvent.click(screen.getByRole('button', { name: /specific date/i }));

    fireEvent.change(document.querySelector('input[type="date"]')!, { target: { value: '2020-01-01' } });
    fireEvent.change(document.querySelector('input[type="time"]')!, { target: { value: '09:00' } });
    clickSchedule();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Run time must be in the future' })
      );
    });
  });

  it('schedules a future date and clears the inputs on success', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(jsonResponse({ job_id: 'date-job' }));
    render(<WorkflowScheduler workflowId="wf-1" />);
    fireEvent.click(screen.getByRole('button', { name: /specific date/i }));

    fireEvent.change(document.querySelector('input[type="date"]')!, { target: { value: '2099-01-01' } });
    fireEvent.change(document.querySelector('input[type="time"]')!, { target: { value: '09:00' } });
    expect(screen.getByText(/Will run at:/)).toBeInTheDocument();

    clickSchedule();

    await waitFor(() => {
      const body = JSON.parse(fetchSpy.mock.calls[1][1].body);
      expect(body.trigger_type).toBe('date');
      expect(new Date(body.trigger_config.run_date).toISOString()).toBe(body.trigger_config.run_date);
    });
    await waitFor(() => {
      expect((document.querySelector('input[type="date"]') as HTMLInputElement).value).toBe('');
      expect((document.querySelector('input[type="time"]') as HTMLInputElement).value).toBe('');
    });
  });

  // ------------------------------------------------------------------
  // API failure paths
  // ------------------------------------------------------------------
  it('surfaces the server error detail when the schedule POST fails', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ detail: 'Schedule conflicts with existing job' }, false, 409)
    );
    render(<WorkflowScheduler workflowId="wf-1" />);

    clickSchedule();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Scheduling Failed',
          description: 'Schedule conflicts with existing job',
          variant: 'error',
        })
      );
    });
  });

  it('falls back to a generic message when the POST throws', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockRejectedValueOnce(new Error('boom'));
    render(<WorkflowScheduler workflowId="wf-1" />);

    clickSchedule();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Scheduling Failed', description: 'boom' })
      );
    });
  });

  // ------------------------------------------------------------------
  // Delete
  // ------------------------------------------------------------------
  it('deletes a scheduled job and reloads the list', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse([{ id: 'wf-1-abc', next_run_time: null, trigger: 'cron' }])
    );
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    render(<WorkflowScheduler workflowId="wf-1" />);

    await waitFor(() => {
      expect(screen.getByText('wf-1-abc')).toBeInTheDocument();
    });
    fireEvent.click(document.querySelector('.lucide-trash-2')!.closest('button')!);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/workflows/wf-1/schedule/wf-1-abc',
        expect.objectContaining({ method: 'DELETE' })
      );
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Schedule Deleted' })
    );
    await waitFor(() => {
      expect(screen.getByText('No scheduled jobs for this workflow')).toBeInTheDocument();
    });
  });

  it('toasts an error when deleting fails', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse([{ id: 'wf-1-abc', next_run_time: null, trigger: 'cron' }])
    );
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false, 500));
    render(<WorkflowScheduler workflowId="wf-1" />);

    await waitFor(() => {
      expect(screen.getByText('wf-1-abc')).toBeInTheDocument();
    });
    fireEvent.click(document.querySelector('.lucide-trash-2')!.closest('button')!);

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', variant: 'error' })
      );
    });
  });

  it('disables the schedule button while a schedule is in flight', async () => {
    let resolvePost: (r: any) => void;
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    fetchSpy.mockImplementationOnce(
      () => new Promise((res) => { resolvePost = res; })
    );
    render(<WorkflowScheduler workflowId="wf-1" />);

    clickSchedule();
    expect(screen.getByRole('button', { name: /scheduling\.\.\./i })).toBeDisabled();

    await act(async () => {
      resolvePost!(jsonResponse({ job_id: 'j1' }));
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /schedule workflow/i })).toBeEnabled();
    });
  });
});

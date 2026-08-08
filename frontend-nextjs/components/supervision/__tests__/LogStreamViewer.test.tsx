/**
 * LogStreamViewer Component Tests
 *
 * Verifies the real LogStreamViewer (components/supervision/LogStreamViewer.tsx):
 * - empty state when no logs exist
 * - log entries render with level class, icon, formatted timestamp and message
 * - data payloads render inside a collapsible <details> block
 * - Copy writes the formatted log text to the clipboard
 * - Export triggers a blob download named after the executionId
 * - auto-scroll pins the container to the bottom when logs arrive
 * - new logs via the providedLogs prop are picked up
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import LogStreamViewer from '../LogStreamViewer';

const logs = [
  { timestamp: '2026-08-01T10:00:00.000Z', level: 'info' as const, message: 'Agent started' },
  { timestamp: '2026-08-01T10:01:00.000Z', level: 'warning' as const, message: 'Rate limit approaching' },
  { timestamp: '2026-08-01T10:02:00.000Z', level: 'error' as const, message: 'Tool call failed' },
];

describe('LogStreamViewer', () => {
  it('shows the waiting empty state when no logs exist', () => {
    render(<LogStreamViewer executionId="exec-1" />);
    expect(screen.getByText('Waiting for logs...')).toBeInTheDocument();
    expect(screen.queryByText('Agent started')).not.toBeInTheDocument();
  });

  it('renders log entries with level class, icon, timestamp and message', () => {
    const { container } = render(<LogStreamViewer executionId="exec-1" logs={logs} />);

    expect(screen.getByText('Agent started')).toBeInTheDocument();
    expect(screen.getByText('Rate limit approaching')).toBeInTheDocument();
    expect(screen.getByText('Tool call failed')).toBeInTheDocument();

    expect(container.querySelectorAll('.log-entry').length).toBe(3);
    expect(container.querySelector('.log-entry.log-info')).toBeInTheDocument();
    expect(container.querySelector('.log-entry.log-warning')).toBeInTheDocument();
    expect(container.querySelector('.log-entry.log-error')).toBeInTheDocument();

    // level icons
    expect(screen.getByText('ℹ')).toBeInTheDocument();
    expect(screen.getByText('⚠')).toBeInTheDocument();
    expect(screen.getByText('✕')).toBeInTheDocument();

    // timestamp formatted via toLocaleTimeString
    expect(screen.getByText(new Date(logs[0].timestamp).toLocaleTimeString())).toBeInTheDocument();
  });

  it('renders the data payload inside a collapsible details block', () => {
    render(
      <LogStreamViewer
        executionId="exec-1"
        logs={[
          {
            timestamp: '2026-08-01T10:00:00.000Z',
            level: 'info',
            message: 'context loaded',
            data: { items: [1, 2, 3] },
          },
        ]}
      />
    );

    const details = screen.getByText('Data').closest('details');
    expect(details).not.toBeNull();
    const preText = details!.querySelector('pre')?.textContent || '';
    expect(preText).toContain('"items"');
    // JSON.stringify(..., null, 2) renders the array across lines
    expect(preText).toMatch(/1,?\s*2,?\s*3/);
  });

  it('renders no details block for entries without data', () => {
    const { container } = render(<LogStreamViewer executionId="exec-1" logs={[logs[0]]} />);
    expect(container.querySelector('.log-data')).not.toBeInTheDocument();
  });

  it('copies the formatted log text to the clipboard', () => {
    render(<LogStreamViewer executionId="exec-1" logs={logs} />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      `[2026-08-01T10:00:00.000Z] [INFO] Agent started\n` +
        `[2026-08-01T10:01:00.000Z] [WARNING] Rate limit approaching\n` +
        `[2026-08-01T10:02:00.000Z] [ERROR] Tool call failed`
    );
  });

  it('exports logs to a downloadable text file named after the execution', () => {
    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const createObjectURL = jest.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url');

    render(<LogStreamViewer executionId="exec-42" logs={logs} />);
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));

    expect(createObjectURL).toHaveBeenCalled();
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe('text/plain');
    expect(clickSpy).toHaveBeenCalled();

    // download anchor uses the executionId in the filename
    const anchor = (HTMLAnchorElement.prototype.click as jest.Mock).mock.instances[0];
    expect(anchor.download).toBe('execution-exec-42-logs.txt');
  });

  it('auto-scrolls the container to the bottom when logs arrive', () => {
    const { container, rerender } = render(<LogStreamViewer executionId="exec-1" logs={[]} />);
    const logContainer = container.querySelector('.log-container') as HTMLDivElement;
    Object.defineProperty(logContainer, 'scrollHeight', { value: 500, configurable: true });

    rerender(<LogStreamViewer executionId="exec-1" logs={logs} />);

    expect(logContainer.scrollTop).toBe(500);
  });

  it('picks up new logs passed via the providedLogs prop', () => {
    const { rerender } = render(<LogStreamViewer executionId="exec-1" logs={logs} />);
    expect(screen.queryByText('New entry')).not.toBeInTheDocument();

    rerender(
      <LogStreamViewer
        executionId="exec-1"
        logs={[...logs, { timestamp: '2026-08-01T11:00:00.000Z', level: 'info', message: 'New entry' }]}
      />
    );

    expect(screen.getByText('New entry')).toBeInTheDocument();
    expect(screen.getAllByText('Agent started').length).toBeGreaterThan(0);
  });
});

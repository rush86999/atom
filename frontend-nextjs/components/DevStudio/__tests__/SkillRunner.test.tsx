/**
 * SkillRunner Component Tests
 *
 * Tests verify the real SkillRunner component
 * (components/DevStudio/SkillRunner.tsx):
 * - loading state ("Discovering skills...") before the Tauri invoke resolves
 * - skill list rendering (name, description, version badge) + search filter
 * - empty list state ("No skills found.")
 * - selecting a skill enables Run Skill; invoke('execute_command') with the
 *   skill's main.py path; success/failure/throw output lines in the console
 * - Tauri streaming listeners (cli-stdout/cli-stderr) append output lines
 * - discovery failure shows an error toast
 *
 * Tauri: invoke('list_local_skills'), invoke('execute_command', ...),
 *        listen('cli-stdout'|'cli-stderr', cb) — mocked via jest.mock
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mockInvoke = jest.fn();
const mockListen = jest.fn();
jest.mock('@tauri-apps/api', () => ({ invoke: mockInvoke }));
jest.mock('@tauri-apps/api/event', () => ({ listen: mockListen }));

import SkillRunner from '../SkillRunner';

const skills = [
  {
    id: 'web-scraper',
    name: 'Web Scraper',
    description: 'Extract structured data from web pages',
    path: '/skills/local/web-scraper',
    version: '1.2.0',
    author: 'atom',
  },
  {
    id: 'email-draft',
    name: 'Email Drafter',
    description: 'Draft professional emails',
    path: '/skills/local/email-draft',
  },
];

describe('SkillRunner', () => {
  let stdoutCb: ((event: any) => void) | null;
  let stderrCb: ((event: any) => void) | null;

  beforeEach(() => {
    jest.clearAllMocks();
    stdoutCb = null;
    stderrCb = null;

    mockInvoke.mockResolvedValue({ skills });
    mockListen.mockImplementation((eventName: string, cb: (event: any) => void) => {
      if (eventName === 'cli-stdout') stdoutCb = cb;
      if (eventName === 'cli-stderr') stderrCb = cb;
      return Promise.resolve(jest.fn());
    });
  });

  it('shows the discovering state before skills load', () => {
    mockInvoke.mockReturnValue(new Promise(() => {}));
    render(<SkillRunner />);
    expect(screen.getByText('Discovering skills...')).toBeInTheDocument();
  });

  it('renders the skill list from list_local_skills with version badges', async () => {
    render(<SkillRunner />);

    expect(await screen.findByText('Web Scraper')).toBeInTheDocument();
    expect(screen.getByText('Extract structured data from web pages')).toBeInTheDocument();
    expect(screen.getByText('1.2.0')).toBeInTheDocument();
    expect(screen.getByText('Email Drafter')).toBeInTheDocument();
    expect(mockInvoke).toHaveBeenCalledWith('list_local_skills');
  });

  it('subscribes to the Tauri cli-stdout/cli-stderr streaming events', async () => {
    render(<SkillRunner />);
    await screen.findByText('Web Scraper');

    expect(mockListen).toHaveBeenCalledWith('cli-stdout', expect.any(Function));
    expect(mockListen).toHaveBeenCalledWith('cli-stderr', expect.any(Function));
  });

  it('shows "No skills found." when the skill list is empty', async () => {
    mockInvoke.mockResolvedValue({ skills: [] });
    render(<SkillRunner />);

    await screen.findByText('No skills found.');
    expect(screen.getByText(/Check skills\/local\/ directory/)).toBeInTheDocument();
  });

  it('filters the skill list by the search query', async () => {
    render(<SkillRunner />);
    await screen.findByText('Web Scraper');

    fireEvent.change(screen.getByPlaceholderText('Search skills...'), {
      target: { value: 'email' },
    });

    expect(screen.queryByText('Web Scraper')).not.toBeInTheDocument();
    expect(screen.getByText('Email Drafter')).toBeInTheDocument();
  });

  it('shows "No skills found." when the search matches nothing', async () => {
    render(<SkillRunner />);
    await screen.findByText('Web Scraper');

    fireEvent.change(screen.getByPlaceholderText('Search skills...'), {
      target: { value: 'zzz-no-match' },
    });

    expect(screen.getByText('No skills found.')).toBeInTheDocument();
  });

  it('runs the selected skill and renders the success output', async () => {
    mockInvoke.mockImplementation((cmd: string) => {
      if (cmd === 'execute_command') return Promise.resolve({ success: true });
      return Promise.resolve({ skills });
    });

    render(<SkillRunner />);
    fireEvent.click(await screen.findByText('Web Scraper'));

    expect(screen.getByText('Executing: Web Scraper')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /run skill/i }));

    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith('execute_command', {
        command: 'python3',
        args: ['/skills/local/web-scraper/main.py'],
        workingDir: '/skills/local/web-scraper',
      });
    });
    expect(await screen.findByText(/✅ Skill execution completed successfully/)).toBeInTheDocument();
    expect(screen.getByText(/🚀 Starting skill: Web Scraper/)).toBeInTheDocument();
    expect(screen.queryByText(/Agent active/)).not.toBeInTheDocument();
  });

  it('renders the exit code line when the skill process fails', async () => {
    mockInvoke.mockImplementation((cmd: string) => {
      if (cmd === 'execute_command') return Promise.resolve({ success: false, exit_code: 2 });
      return Promise.resolve({ skills });
    });

    render(<SkillRunner />);
    fireEvent.click(await screen.findByText('Web Scraper'));
    fireEvent.click(screen.getByRole('button', { name: /run skill/i }));

    expect(await screen.findByText(/❌ Skill failed with exit code: 2/)).toBeInTheDocument();
  });

  it('renders the error line when invoke throws', async () => {
    mockInvoke.mockImplementation((cmd: string) => {
      if (cmd === 'execute_command') return Promise.reject(new Error('permission denied'));
      return Promise.resolve({ skills });
    });

    render(<SkillRunner />);
    fireEvent.click(await screen.findByText('Web Scraper'));
    fireEvent.click(screen.getByRole('button', { name: /run skill/i }));

    expect(await screen.findByText(/❌ Error: permission denied/)).toBeInTheDocument();
  });

  it('disables the Run Skill button while executing', async () => {
    mockInvoke.mockImplementation((cmd: string) => {
      if (cmd === 'execute_command') return new Promise(() => {});
      return Promise.resolve({ skills });
    });

    render(<SkillRunner />);
    fireEvent.click(await screen.findByText('Web Scraper'));
    fireEvent.click(screen.getByRole('button', { name: /run skill/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /run skill/i })).toBeDisabled();
    });
    expect(screen.getByText('Agent active... executing skill logic')).toBeInTheDocument();
  });

  it('appends streaming stdout/stderr lines from Tauri listeners', async () => {
    render(<SkillRunner />);
    await screen.findByText('Web Scraper');
    expect(screen.getByText('Waiting for skill execution...')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Web Scraper'));
    fireEvent.click(screen.getByRole('button', { name: /run skill/i }));

    await waitFor(() => {
      expect(stdoutCb).toBeTruthy();
      expect(stderrCb).toBeTruthy();
    });

    stdoutCb!({ payload: 'downloading corpus...' });
    stderrCb!({ payload: 'warn: retrying' });

    expect(await screen.findByText('downloading corpus...')).toBeInTheDocument();
    expect(screen.getByText('warn: retrying')).toBeInTheDocument();
    expect(screen.queryByText('Waiting for skill execution...')).not.toBeInTheDocument();
  });

  it('shows an error toast when skill discovery fails', async () => {
    mockInvoke.mockRejectedValue(new Error('tauri unavailable'));
    render(<SkillRunner />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Discovery Failed' })
      );
    });
    expect(screen.getByText('No skills found.')).toBeInTheDocument();
  });
});

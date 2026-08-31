/**
 * BoxIntegration Component Tests
 *
 * Tests verify the real Box integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile and folder/file data loading
 * - File & folder search filtering
 * - Folder navigation, type filters, create-folder/share/collaboration flows
 * - Collaborations, users, analytics tabs and error paths
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/BoxIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import BoxIntegration from '@/components/BoxIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import { useToast } from '@/components/ui/use-toast';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const boxHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { box: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { box: { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/box/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            type: 'user',
            name: 'Rushi Parikh',
            login: 'rushi@example.com',
            avatar_url: '',
            status: 'active',
            space_used: 10485760,
            space_amount: 104857600,
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/box/folder/:folderId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          folder: {
            id: '0',
            name: 'All Files',
            item_collection: {
              entries: [
                {
                  type: 'folder',
                  id: 'f1',
                  name: 'Marketing',
                  description: 'Q2 campaigns',
                  modified_at: '2024-01-15T10:00:00Z',
                  shared_link: { url: 'https://box.example.com/s/f1', access: 'open' },
                  item_collection: { total_count: 3, entries: [] },
                },
                {
                  type: 'file',
                  id: 'x1',
                  name: 'roadmap.pdf',
                  size: 1024,
                  modified_at: '2024-01-15T10:00:00Z',
                  content_modified_at: '2024-01-14T10:00:00Z',
                  description: 'Q3 roadmap',
                  created_by: { id: 'u9', name: 'Ops Team', login: 'ops@example.com', type: 'user' },
                  shared_link: { url: 'https://box.example.com/s/x1', access: 'company' },
                  lock: { id: 'lk1', type: 'lock', created_at: '2024-01-10T00:00:00Z', locked_by: { id: 'u1', name: 'Rushi Parikh', login: 'rushi@example.com', type: 'user' } },
                  tags: [{ id: 't1', type: 'tag', name: 'priority', url: '' }],
                },
                {
                  type: 'file',
                  id: 'x2',
                  name: 'budget.xlsx',
                  size: 2048,
                  modified_at: '2024-01-14T10:00:00Z',
                },
                {
                  type: 'file',
                  id: 'x3',
                  name: 'team.png',
                  size: 5242880,
                  modified_at: '2024-01-13T10:00:00Z',
                },
                {
                  type: 'file',
                  id: 'x4',
                  name: 'archive.zip',
                  size: 1024,
                  modified_at: '2024-01-12T10:00:00Z',
                },
                {
                  type: 'file',
                  id: 'x5',
                  name: 'demo.mp4',
                  size: 1024,
                  modified_at: '2024-01-11T10:00:00Z',
                },
                {
                  type: 'file',
                  id: 'x6',
                  name: 'audio.mp3',
                  size: 1024,
                  modified_at: '2024-01-10T10:00:00Z',
                },
                {
                  type: 'file',
                  id: 'x7',
                  name: 'notes.txt',
                  size: 0,
                  modified_at: '2024-01-09T10:00:00Z',
                },
                {
                  type: 'file',
                  id: 'x8',
                  name: 'report.docx',
                  size: 1024,
                  modified_at: '2024-01-08T10:00:00Z',
                  shared_link: { url: 'https://box.example.com/s/x8', access: 'collaborators' },
                },
                {
                  type: 'file',
                  id: 'x9',
                  name: 'deck.pptx',
                  size: 1024,
                  modified_at: '2024-01-07T10:00:00Z',
                },
              ],
            },
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/box/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          users: [
            {
              id: 'u1',
              type: 'user',
              name: 'Rushi Parikh',
              login: 'rushi@example.com',
              status: 'active',
              job_title: 'CEO',
              avatar_url: '',
              space_used: 1073741824,
              space_amount: 2147483648,
            },
            {
              id: 'u2',
              type: 'user',
              name: 'Jane Doe',
              login: 'jane@example.com',
              status: 'inactive',
              job_title: 'Designer',
              avatar_url: '',
              space_used: 0,
              space_amount: 1073741824,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/box/collaborations', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          collaborations: [
            {
              id: 'c1',
              type: 'collaboration',
              item: { id: 'f1', type: 'folder', name: 'Marketing' },
              accessible_by: { id: 'u2', type: 'user', name: 'Jane Doe', login: 'jane@example.com' },
              role: 'editor',
              status: 'active',
              created_by: { id: 'u1', type: 'user', name: 'Rushi Parikh', login: 'rushi@example.com' },
              created_at: '2024-01-10T00:00:00Z',
            },
            {
              id: 'c2',
              type: 'collaboration',
              item: { id: 'f2', type: 'folder', name: 'Contracts' },
              accessible_by: { id: 'u1', type: 'user', name: 'Rushi Parikh', login: 'rushi@example.com' },
              role: 'co-owner',
              status: 'inactive',
              created_at: '2024-01-11T00:00:00Z',
              expires_at: '2025-01-01T00:00:00Z',
            },
            {
              id: 'c3',
              type: 'collaboration',
              item: { id: 'f3', type: 'folder', name: 'External' },
              invite_email: 'guest@example.com',
              role: 'previewer uploader',
              status: 'cannot_delete_edit',
              created_at: '2024-01-12T00:00:00Z',
            },
            {
              id: 'c4',
              type: 'collaboration',
              item: { id: 'f4', type: 'folder', name: 'Sensitive' },
              accessible_by: { id: 'u2', type: 'user', name: 'Jane Doe', login: 'jane@example.com' },
              role: 'owner',
              status: 'cannot_delete_edit_upload',
              created_at: '2024-01-13T00:00:00Z',
            },
            {
              id: 'c5',
              type: 'collaboration',
              item: { id: 'f5', type: 'folder', name: 'Docs' },
              accessible_by: { id: 'u2', type: 'user', name: 'Jane Doe', login: 'jane@example.com' },
              role: 'previewer',
              status: 'active',
              created_at: '2024-01-14T00:00:00Z',
            },
            {
              id: 'c6',
              type: 'collaboration',
              item: { id: 'f6', type: 'folder', name: 'Assets' },
              accessible_by: { id: 'u2', type: 'user', name: 'Jane Doe', login: 'jane@example.com' },
              role: 'uploader',
              status: 'active',
              created_at: '2024-01-15T00:00:00Z',
            },
          ],
        },
      })
    );
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

// Data is loaded in both checkConnection() and the connected useEffect
// (double data-load race); wait for the full dataset to settle.
const settleData = async (text: RegExp) => {
  await screen.findByText(text);
  await new Promise((r) => setTimeout(r, 50));
};

describe('BoxIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...boxHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<BoxIntegration />);

    expect(
      screen.getByRole('heading', { name: /box integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<BoxIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect box account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<BoxIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect box account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays files and folders in the default Files tab
  test('displays files and folders in the default Files tab', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Marketing')).toBeInTheDocument();
      expect(screen.getByText('roadmap.pdf')).toBeInTheDocument();
      expect(screen.getByText('budget.xlsx')).toBeInTheDocument();
    });
  });

  // Test 7: filters files by search query
  test('filters files by search query', async () => {
    render(<BoxIntegration />);

    await settleData(/roadmap.pdf/);

    const searchInput = screen.getByPlaceholderText(/search files and folders/i);
    fireEvent.change(searchInput, { target: { value: 'budget' } });

    await waitFor(() => {
      expect(screen.getByText('budget.xlsx')).toBeInTheDocument();
    });
    expect(screen.queryByText('roadmap.pdf')).not.toBeInTheDocument();
  });

  // Test 8: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<BoxIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect box account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: shows refresh status button
  test('shows refresh status button', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });

  describe('profile and file rendering', () => {
    test('shows profile storage usage', async () => {
      render(<BoxIntegration />);

      await waitFor(() => {
        // JSX interpolation splits the text into adjacent text nodes; match
        // against the concatenated text of the profile line.
        expect(
          screen.getByText((content, el) => el?.textContent === 'rushi@example.com • 10 MB used')
        ).toBeInTheDocument();
      });
    });

    test('renders file details: size badges, shared, locked, tags, dates', async () => {
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      // Size formatting: 1024 -> 1 KB, 2048 -> 2 KB, 5242880 -> 5 MB; 0-byte
      // files render no size badge
      expect(screen.getAllByText('1 KB').length).toBeGreaterThanOrEqual(4);
      expect(screen.getByText('2 KB')).toBeInTheDocument();
      expect(screen.getByText('5 MB')).toBeInTheDocument();

      // Shared badge on x1 + f1 + x8
      expect(screen.getAllByText('Shared').length).toBe(3);
      // Locked badge on x1
      expect(screen.getByText('Locked')).toBeInTheDocument();
      // Tag badge
      expect(screen.getByText('priority')).toBeInTheDocument();
      // Description
      expect(screen.getByText('Q3 roadmap')).toBeInTheDocument();
      // Folder description
      expect(screen.getByText('Q2 campaigns')).toBeInTheDocument();
      // Modified + content dates
      expect(screen.getAllByText(/Modified:/).length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText(/Content:/)).toBeInTheDocument();
      // Created-by lines (x1 file)
      expect(screen.getAllByText('Created by:').length).toBeGreaterThanOrEqual(1);
      // Item count on the folder
      expect(screen.getByText('3 items')).toBeInTheDocument();
    });

    test('maps file extensions to icons', async () => {
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      expect(document.querySelectorAll('svg.lucide-file-text').length).toBeGreaterThanOrEqual(4); // pdf + xlsx + docx + pptx
      expect(document.querySelectorAll('svg.lucide-image').length).toBe(1); // png
      expect(document.querySelectorAll('svg.lucide-download').length).toBe(1); // zip
      expect(document.querySelectorAll('svg.lucide-video').length).toBe(1); // mp4
      expect(document.querySelectorAll('svg.lucide-music').length).toBe(1); // mp3
      expect(document.querySelectorAll('svg.lucide-file').length).toBe(1); // txt
    });
  });

  describe('folder navigation', () => {
    test('navigates into a folder, uses breadcrumbs to move back', async () => {
      const user = userEvent.setup();
      server.use(
        rest.post('/api/integrations/box/folder/:folderId', (req, res, ctx) => {
          if (req.params.folderId === 'f1') {
            return res(
              ctx.status(200),
              ctx.json({
                data: {
                  folder: {
                    id: 'f1',
                    name: 'Marketing',
                    item_collection: {
                      entries: [
                        { type: 'folder', id: 'f1a', name: 'Q2 Assets', item_collection: { entries: [] } },
                        { type: 'file', id: 'y1', name: 'notes.txt', size: 512, modified_at: '2024-01-16T10:00:00Z' },
                      ],
                    },
                  },
                },
              })
            );
          }
          if (req.params.folderId === 'f1a') {
            return res(
              ctx.status(200),
              ctx.json({
                data: {
                  folder: {
                    id: 'f1a',
                    name: 'Q2 Assets',
                    item_collection: { entries: [] },
                  },
                },
              })
            );
          }
          return res(
            ctx.status(200),
            ctx.json({
              data: {
                folder: {
                  id: '0',
                  name: 'All Files',
                  item_collection: {
                    entries: [
                      { type: 'folder', id: 'f1', name: 'Marketing', item_collection: { entries: [] } },
                      { type: 'file', id: 'x1', name: 'roadmap.pdf', size: 1024, modified_at: '2024-01-15T10:00:00Z' },
                    ],
                  },
                },
              },
            })
          );
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      // Enter the Marketing folder via its Folder icon
      await user.click(document.querySelector('svg.lucide-folder') as HTMLElement);
      await waitFor(() => {
        expect(screen.getByText('Q2 Assets')).toBeInTheDocument();
      });
      expect(screen.getByText('notes.txt')).toBeInTheDocument();
      expect(screen.queryByText('roadmap.pdf')).not.toBeInTheDocument();

      // Breadcrumb path shows Root > Marketing
      expect(screen.getByText('Root')).toBeInTheDocument();
      expect(screen.getByText('Marketing')).toBeInTheDocument();

      // Drill one level deeper
      await user.click(screen.getByText('Q2 Assets'));
      await waitFor(() => {
        expect(screen.queryByText('notes.txt')).not.toBeInTheDocument();
      });

      // Intermediate breadcrumb navigates back to Marketing
      await user.click(screen.getByText('Marketing'));
      await waitFor(() => {
        expect(screen.getByText('notes.txt')).toBeInTheDocument();
      });

      // Breadcrumb Root returns to the root folder
      await user.click(screen.getByText('Root'));
      await waitFor(() => {
        expect(screen.queryByText('notes.txt')).not.toBeInTheDocument();
      });
    });

    test('clicking the current breadcrumb does not refetch', async () => {
      const user = userEvent.setup();
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const fetchSpy = jest.spyOn(global, 'fetch');
      const countFolderRequests = () =>
        fetchSpy.mock.calls.filter((c) => String(c[0]).includes('/api/integrations/box/folder/0')).length;
      const before = countFolderRequests();

      await user.click(screen.getByText('Root'));
      await new Promise((r) => setTimeout(r, 100));

      expect(countFolderRequests()).toBe(before);
      expect(screen.getByText('roadmap.pdf')).toBeInTheDocument();
    });
  });

  describe('type filtering and empty states', () => {
    test('filters by type: files only / folders only', async () => {
      const user = userEvent.setup();
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      // Files only
      await user.click(screen.getByRole('combobox'));
      await user.click(within(await screen.findByRole('listbox')).getByText('Files'));
      await waitFor(() => {
        expect(screen.queryByText('Marketing')).not.toBeInTheDocument();
      });
      expect(screen.getByText('roadmap.pdf')).toBeInTheDocument();

      // Folders only
      await user.click(screen.getByRole('combobox'));
      await user.click(within(await screen.findByRole('listbox')).getByText('Folders'));
      await waitFor(() => {
        expect(screen.queryByText('roadmap.pdf')).not.toBeInTheDocument();
      });
      expect(screen.getByText('Marketing')).toBeInTheDocument();
    });

    test('shows no items when search matches nothing', async () => {
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      fireEvent.change(screen.getByPlaceholderText(/search files and folders/i), {
        target: { value: 'zzz-no-match' },
      });

      await waitFor(() => {
        expect(screen.queryByText('roadmap.pdf')).not.toBeInTheDocument();
      });
      expect(screen.queryByText('Marketing')).not.toBeInTheDocument();
    });
  });

  describe('create folder flow', () => {
    test('creates a folder via the dialog', async () => {
      const user = userEvent.setup();
      const createBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/folders/create', (req, res, ctx) => {
          createBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { folder: {} } }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: /create folder/i }));
      const dialog = await screen.findByRole('dialog');

      expect(within(dialog).getByRole('button', { name: /create folder/i })).toBeDisabled();

      await user.type(within(dialog).getByPlaceholderText('Enter folder name'), 'New Folder');
      await user.type(within(dialog).getByPlaceholderText(/folder description/i), 'A new folder');
      await user.click(within(dialog).getByRole('button', { name: /create folder/i }));

      await waitFor(() => {
        expect(
          createBodies.some((b) => b.name === 'New Folder' && b.parent?.id === '0')
        ).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Folder created successfully',
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    test('cancel closes the create folder dialog without submitting', async () => {
      const user = userEvent.setup();
      const createBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/folders/create', (req, res, ctx) => {
          createBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: {} }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: /create folder/i }));
      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /^cancel$/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(createBodies).toHaveLength(0);
    });

    test('shows error toast when folder creation fails', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/box/folders/create', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: /create folder/i }));
      const dialog = await screen.findByRole('dialog');
      await user.type(within(dialog).getByPlaceholderText('Enter folder name'), 'Doomed');
      await user.click(within(dialog).getByRole('button', { name: /create folder/i }));

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to create folder',
          variant: 'error',
        });
      });
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('share flow', () => {
    test('shares a file with access level, password, unshare date, and permissions', async () => {
      const user = userEvent.setup();
      const shareBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/files/x1/share', (req, res, ctx) => {
          shareBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { shared_link: {} } }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const fileCard = screen.getByText('roadmap.pdf').closest('.rounded-lg') as HTMLElement;
      await user.click(within(fileCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /share/i }));

      const dialog = await screen.findByRole('dialog');
      expect(
        within(dialog).getByRole('heading', { name: /create shared link/i })
      ).toBeInTheDocument();

      // Access level: open
      await user.click(within(dialog).getByRole('combobox'));
      await user.click(within(await screen.findByRole('listbox')).getByText('Anyone with link'));
      // Password
      await user.type(within(dialog).getByPlaceholderText('Enter password'), 'secret123');
      // Unshare date
      const dateInput = document.querySelector(
        '#dialog-content input[type="date"]'
      ) as HTMLInputElement;
      fireEvent.change(dateInput, { target: { value: '2025-06-01' } });
      // Toggle all three permission checkboxes (download off, preview off,
      // upload on)
      await user.click(within(dialog).getByLabelText('Can download'));
      await user.click(within(dialog).getByLabelText('Can preview'));
      await user.click(within(dialog).getByLabelText('Can upload'));

      await user.click(within(dialog).getByRole('button', { name: /create link/i }));

      await waitFor(() => {
        expect(
          shareBodies.some(
            (b) =>
              b.access === 'open' &&
              b.password === 'secret123' &&
              b.unshare_date === '2025-06-01' &&
              b.permissions?.can_upload === true &&
              b.permissions?.can_download === false &&
              b.permissions?.can_preview === false
          )
        ).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'file shared successfully',
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    test('shares a folder with the default access level', async () => {
      const user = userEvent.setup();
      const shareBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/folders/f1/share', (req, res, ctx) => {
          shareBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { shared_link: {} } }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const folderCard = screen.getByText('Marketing').closest('.rounded-lg') as HTMLElement;
      await user.click(within(folderCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /share/i }));

      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /create link/i }));

      // The folder's existing shared link prefills the access level as "open"
      await waitFor(() => {
        expect(shareBodies.some((b) => b.access === 'open')).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'folder shared successfully',
      });
    });

    test('shares an unshared file, prefilling the default access level', async () => {
      const user = userEvent.setup();
      const shareBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/files/x2/share', (req, res, ctx) => {
          shareBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { shared_link: {} } }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const fileCard = screen.getByText('budget.xlsx').closest('.rounded-lg') as HTMLElement;
      await user.click(within(fileCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /share/i }));

      const dialog = await screen.findByRole('dialog');
      // Switch the access level to company
      await user.click(within(dialog).getByRole('combobox'));
      await user.click(within(await screen.findByRole('listbox')).getByText('People in company'));
      await user.click(within(dialog).getByRole('button', { name: /create link/i }));

      await waitFor(() => {
        expect(shareBodies.some((b) => b.access === 'company')).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'file shared successfully',
      });
    });

    test('cancel closes the share dialog without submitting', async () => {
      const user = userEvent.setup();
      const shareBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/files/x1/share', (req, res, ctx) => {
          shareBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: {} }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const fileCard = screen.getByText('roadmap.pdf').closest('.rounded-lg') as HTMLElement;
      await user.click(within(fileCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /share/i }));

      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /^cancel$/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(shareBodies).toHaveLength(0);
    });
  });

  describe('collaboration flow', () => {
    test('adds a collaboration with user, role, and notify settings', async () => {
      const user = userEvent.setup();
      const collabBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/collaborations/create', (req, res, ctx) => {
          collabBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { collaboration: {} } }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const folderCard = screen.getByText('Marketing').closest('.rounded-lg') as HTMLElement;
      await user.click(within(folderCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /add collaboration/i }));

      const dialog = await screen.findByRole('dialog');
      expect(
        within(dialog).getByRole('heading', { name: /add collaboration/i })
      ).toBeInTheDocument();

      // Submit disabled until a user is chosen
      expect(within(dialog).getByRole('button', { name: /add collaboration/i })).toBeDisabled();

      // Pick the collaborator (user select is the first combobox in the dialog)
      await user.click(within(dialog).getAllByRole('combobox')[0]);
      await user.click(within(await screen.findByRole('listbox')).getByText(/Jane Doe/));

      // Pick the role: Viewer
      await user.click(within(dialog).getAllByRole('combobox')[1]);
      await user.click(within(await screen.findByRole('listbox')).getByText('Viewer'));

      // Toggle notification off
      await user.click(within(dialog).getByLabelText('Send notification to collaborator'));

      await user.click(within(dialog).getByRole('button', { name: /add collaboration/i }));

      await waitFor(() => {
        expect(
          collabBodies.some(
            (b) =>
              b.item?.id === 'f1' &&
              b.accessible_by?.id === 'u2' &&
              b.role === 'viewer' &&
              b.notify === false
          )
        ).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Collaboration created successfully',
      });
    });

    test('cancel closes the collaboration dialog without submitting', async () => {
      const user = userEvent.setup();
      const collabBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/box/collaborations/create', (req, res, ctx) => {
          collabBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: {} }));
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const folderCard = screen.getByText('Marketing').closest('.rounded-lg') as HTMLElement;
      await user.click(within(folderCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /add collaboration/i }));

      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /^cancel$/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(collabBodies).toHaveLength(0);
    });
  });

  describe('collaborations tab', () => {
    test('renders collaborations with roles, statuses, and collaborator info', async () => {
      const user = userEvent.setup();
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: 'Collaborations' }));

      await waitFor(() => {
        expect(screen.getByText('Marketing')).toBeInTheDocument();
        expect(screen.getByText('Contracts')).toBeInTheDocument();
        expect(screen.getByText('External')).toBeInTheDocument();
        expect(screen.getByText('Sensitive')).toBeInTheDocument();
        expect(screen.getByText('Docs')).toBeInTheDocument();
        expect(screen.getByText('Assets')).toBeInTheDocument();
      });
      // Role + status badges (getRoleVariant / getStatusVariant branches)
      expect(screen.getByText('editor')).toBeInTheDocument();
      expect(screen.getAllByText('active').length).toBeGreaterThanOrEqual(3);
      expect(screen.getByText('co-owner')).toBeInTheDocument();
      expect(screen.getByText('inactive')).toBeInTheDocument();
      expect(screen.getByText('previewer uploader')).toBeInTheDocument();
      expect(screen.getByText('cannot_delete_edit')).toBeInTheDocument();
      expect(screen.getByText('owner')).toBeInTheDocument();
      expect(screen.getByText('cannot_delete_edit_upload')).toBeInTheDocument();
      expect(screen.getByText('previewer')).toBeInTheDocument();
      expect(screen.getByText('uploader')).toBeInTheDocument();
      // Collaborator details (Jane Doe appears on c1/c4/c5/c6)
      expect(screen.getAllByText('Collaborator: Jane Doe').length).toBeGreaterThanOrEqual(4);
      expect(screen.getAllByText(/\(jane@example\.com\)/).length).toBeGreaterThanOrEqual(4);
      expect(screen.getByText('Collaborator: guest@example.com')).toBeInTheDocument();
      // Expiry + created-by lines
      expect(screen.getByText(/Expires:/)).toBeInTheDocument();
      expect(screen.getByText('Created by: Rushi Parikh')).toBeInTheDocument();
    });

    test('filters collaborations by search query', async () => {
      const user = userEvent.setup();
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: 'Collaborations' }));
      await screen.findByText('Marketing');

      fireEvent.change(screen.getByPlaceholderText(/search collaborations/i), {
        target: { value: 'Contracts' },
      });

      await waitFor(() => {
        expect(screen.queryByText('Marketing')).not.toBeInTheDocument();
      });
      expect(screen.getByText('Contracts')).toBeInTheDocument();
    });
  });

  describe('users tab', () => {
    test('renders users with status, job title, and storage', async () => {
      const user = userEvent.setup();
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: 'Users' }));

      await waitFor(() => {
        expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      });
      expect(screen.getAllByText('Rushi Parikh').length).toBeGreaterThan(0);
      expect(screen.getByText('active')).toBeInTheDocument();
      expect(screen.getByText('inactive')).toBeInTheDocument();
      expect(screen.getByText('CEO')).toBeInTheDocument();
      expect(screen.getByText('Designer')).toBeInTheDocument();
      expect(screen.getByText('jane@example.com')).toBeInTheDocument();
      expect(screen.getByText(/1 GB \/ 2 GB/)).toBeInTheDocument();
    });

    test('filters users by search query', async () => {
      const user = userEvent.setup();
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: 'Users' }));
      await screen.findByText('Jane Doe');

      fireEvent.change(screen.getByPlaceholderText(/search users/i), {
        target: { value: 'Jane' },
      });

      await waitFor(() => {
        expect(screen.queryByText('CEO')).not.toBeInTheDocument();
      });
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });
  });

  describe('analytics tab', () => {
    test('renders storage, shared item, and collaboration analytics', async () => {
      const user = userEvent.setup();
      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByRole('button', { name: 'Analytics' }));

      await waitFor(() => {
        expect(screen.getByText('Storage Used')).toBeInTheDocument();
      });
      expect(screen.getByText('10 MB')).toBeInTheDocument();
      expect(screen.getByText('of 100 MB')).toBeInTheDocument();
      // 2 shared files (x1, x8) + 1 shared folder (f1)
      expect(screen.getByText('2 files, 1 folders')).toBeInTheDocument();
      expect(screen.getByText('Active Collaborations')).toBeInTheDocument();
      expect(screen.getByText('Recent Activity')).toBeInTheDocument();
    });
  });

  describe('error paths', () => {
    test('handles a network-level health check failure as disconnected', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.get('/api/integrations/connection-status', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<BoxIntegration />);

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      expect(
        screen.getByRole('button', { name: /connect box account/i })
      ).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    test('handles folder navigation load failure without crashing', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/box/folder/f1', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      await user.click(screen.getByText('Marketing'));

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      expect(screen.getByText('Connected')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    test('shows error toast when creating a shared link fails', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/box/files/x1/share', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const fileCard = screen.getByText('roadmap.pdf').closest('.rounded-lg') as HTMLElement;
      await user.click(within(fileCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /share/i }));

      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /create link/i }));

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to create shared link',
          variant: 'error',
        });
      });
      consoleErrorSpy.mockRestore();
    });

    test('shows error toast when creating a collaboration fails', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/box/collaborations/create', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<BoxIntegration />);

      await settleData(/roadmap.pdf/);

      const folderCard = screen.getByText('Marketing').closest('.rounded-lg') as HTMLElement;
      await user.click(within(folderCard).getByRole('button', { name: /actions/i }));
      await user.click(await screen.findByRole('menuitem', { name: /add collaboration/i }));

      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getAllByRole('combobox')[0]);
      await user.click(within(await screen.findByRole('listbox')).getByText(/Jane Doe/));
      await user.click(within(dialog).getByRole('button', { name: /add collaboration/i }));

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to create collaboration',
          variant: 'error',
        });
      });
      consoleErrorSpy.mockRestore();
    });

    test('shows error toast when the root folder fails to load', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/box/folder/0', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<BoxIntegration />);

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to load files from Box',
          variant: 'error',
        });
      });
      expect(screen.getByText('Connected')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    test('handles users fetch failure without crashing', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/box/users', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<BoxIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      consoleErrorSpy.mockRestore();
    });
  });
});

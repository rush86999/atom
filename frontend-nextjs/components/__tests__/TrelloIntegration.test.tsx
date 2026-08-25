/**
 * TrelloIntegration Component Tests
 *
 * Tests verify the real Trello integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile and board data loading
 * - Board search filtering and create-board dialog
 * - Board/list/card CRUD flows, stats, team tab, and error paths
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/TrelloIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TrelloIntegration from '@/components/TrelloIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import { useToast } from '@/components/ui/use-toast';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const trelloHandlers = [
  rest.get('/api/integrations/trello/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/trello/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            fullName: 'Rushi Parikh',
            username: 'rushi',
            initials: 'RP',
            avatarUrl: '',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/trello/boards', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          boards: [
            {
              id: 'b1',
              name: 'Website Redesign',
              desc: 'Marketing site',
              closed: false,
              pinned: true,
              starred: false,
              url: 'https://trello.com/b/b1',
              dateLastActivity: '2024-01-10T00:00:00Z',
              prefs: { background: 'blue' },
              organization: { displayName: 'Acme Inc' },
            },
            {
              id: 'b2',
              name: 'Mobile App',
              desc: 'iOS and Android',
              closed: false,
              pinned: false,
              starred: true,
              url: 'https://trello.com/b/b2',
              dateLastActivity: '2024-01-09T00:00:00Z',
              prefs: { background: 'green' },
              organization: null,
            },
            {
              id: 'b3',
              name: 'Roadmap',
              desc: 'Q3 planning',
              closed: true,
              pinned: false,
              starred: false,
              url: 'https://trello.com/b/b3',
              dateLastActivity: '2024-01-08T00:00:00Z',
              prefs: { background: 'red' },
              organization: null,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/trello/lists', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          lists: [
            { id: 'l1', name: 'To Do', pos: 1, idBoard: 'b1', closed: false },
            { id: 'l2', name: 'Done', pos: 2, idBoard: 'b1', closed: false },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/trello/cards', (req, res, ctx) => {
    const makeBadges = (comments = 0, checked = 0, total = 0, attachments = 0) => ({
      attachments,
      attachmentsByType: {},
      location: 0,
      comments,
      description: false,
      dueComplete: false,
      due: false,
      fogbugz: '',
      checkItems: total,
      checkItemsChecked: checked,
      viewMemberVotes: 0,
      voting: 0,
    });
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          cards: [
            {
              id: 'c1',
              name: 'Fix login bug',
              desc: 'Auth crash on session refresh',
              closed: false,
              idBoard: 'b1',
              idList: 'l1',
              idMembers: ['m1'],
              idLabels: [],
              due: '2020-01-01T10:00:00Z',
              dueComplete: false,
              url: 'https://trello.com/c/c1',
              badges: makeBadges(7, 1, 2, 1),
            },
            {
              id: 'c2',
              name: 'Launch v2',
              desc: '',
              closed: false,
              idBoard: 'b1',
              idList: 'l1',
              idMembers: [],
              idLabels: [],
              due: '2030-01-01T10:00:00Z',
              dueComplete: true,
              url: 'https://trello.com/c/c2',
              badges: makeBadges(),
            },
            {
              id: 'c3',
              name: 'Send invoices',
              desc: '',
              closed: false,
              idBoard: 'b1',
              idList: 'l1',
              idMembers: [],
              idLabels: [],
              due: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
              dueComplete: false,
              url: 'https://trello.com/c/c3',
              badges: makeBadges(),
            },
            {
              id: 'c4',
              name: 'No due card',
              desc: '',
              closed: false,
              idBoard: 'b1',
              idList: 'l1',
              idMembers: [],
              idLabels: [],
              due: '',
              dueComplete: false,
              url: 'https://trello.com/c/c4',
              badges: makeBadges(),
            },
            {
              id: 'c5',
              name: 'Roadmap review',
              desc: 'Q3 items',
              closed: false,
              idBoard: 'b1',
              idList: 'l1',
              idMembers: [],
              idLabels: [],
              due: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
              dueComplete: false,
              url: 'https://trello.com/c/c5',
              badges: makeBadges(),
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/trello/members', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          members: [
            {
              id: 'm1',
              fullName: 'Alice Chen',
              username: 'alice',
              initials: 'AC',
              memberType: 'admin',
              confirmed: true,
              bio: 'Core maintainer',
              avatarUrl50: '',
            },
            {
              id: 'm2',
              fullName: 'Jane Doe',
              username: 'jane',
              initials: 'JD',
              memberType: 'normal',
              confirmed: false,
              bio: '',
              avatarUrl50: '',
            },
          ],
        },
      })
    );
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/trello/health', (req, res, ctx) => {
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

// Select board "Mobile App" + list "To Do" in the Cards tab via the Radix
// selects, then wait for the cards to render.
const selectBoardAndList = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(await screen.findByRole('button', { name: 'Cards' }));
  await user.click(screen.getAllByRole('combobox')[0]);
  await user.click(within(await screen.findByRole('listbox')).getByText('Mobile App'));
  await user.click(screen.getAllByRole('combobox')[1]);
  const listbox = await screen.findByRole('listbox');
  await user.click(await within(listbox).findByText('To Do'));
  await screen.findByText('Fix login bug');
};

describe('TrelloIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...trelloHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<TrelloIntegration />);

    expect(
      screen.getByRole('heading', { name: /trello integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect trello account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<TrelloIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect trello account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays boards in the default Boards tab
  test('displays boards in the default Boards tab', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Website Redesign')).toBeInTheDocument();
      expect(screen.getByText('Mobile App')).toBeInTheDocument();
    });
  });

  // Test 7: filters boards by search query
  test('filters boards by search query', async () => {
    render(<TrelloIntegration />);

    await settleData(/Website Redesign/);

    const searchInput = screen.getByPlaceholderText(/search boards/i);
    fireEvent.change(searchInput, { target: { value: 'Mobile' } });

    await waitFor(() => {
      expect(screen.getByText('Mobile App')).toBeInTheDocument();
    });
    expect(screen.queryByText('Website Redesign')).not.toBeInTheDocument();
  });

  // Test 8: opens create board dialog
  test('opens create board dialog', async () => {
    render(<TrelloIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create board/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 9: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/trello/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect trello account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 10: shows refresh status button
  test('shows refresh status button', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });

  describe('stats and board details', () => {
    test('renders overview stats computed from loaded data', async () => {
      const user = userEvent.setup();
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      // 3 boards total, 2 open (b3 is closed)
      expect(screen.getByText('2 open')).toBeInTheDocument();
      expect(screen.getByText('With deadlines')).toBeInTheDocument();
      expect(screen.getByText('Collaborators')).toBeInTheDocument();

      // Cards only load after a board+list is selected; then the overdue
      // count (c1 is past due) and total card count appear.
      await selectBoardAndList(user);
      await waitFor(() => {
        expect(screen.getByText('1 overdue')).toBeInTheDocument();
      });
    });

    test('renders pinned/starred badges and organization name', async () => {
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      expect(screen.getByText('Pinned')).toBeInTheDocument();
      expect(screen.getByText('Starred')).toBeInTheDocument();
      expect(screen.getByText('Organization: Acme Inc')).toBeInTheDocument();
      expect(screen.getAllByText(/Last activity:/).length).toBe(3);
    });

    test('opens board in Trello via the external link button', async () => {
      const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await userEvent.click(screen.getAllByRole('button', { name: /open in trello/i })[0]);
      expect(openSpy).toHaveBeenCalledWith('https://trello.com/b/b1', '_blank');
      openSpy.mockRestore();
    });

    test('maps board background colors per prefs.background', async () => {
      server.use(
        rest.post('/api/integrations/trello/boards', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              data: {
                boards: [
                  { id: 'b-y', name: 'Yellow Board', desc: '', closed: true, prefs: { background: 'yellow' } },
                  { id: 'b-p', name: 'Purple Board', desc: '', closed: true, prefs: { background: 'purple' } },
                  { id: 'b-k', name: 'Pink Board', desc: '', closed: true, prefs: { background: 'pink' } },
                  { id: 'b-s', name: 'Sky Board', desc: '', closed: true, prefs: { background: 'sky' } },
                  { id: 'b-l', name: 'Lime Board', desc: '', closed: true, prefs: { background: 'lime' } },
                  { id: 'b-x', name: 'Mystery Board', desc: '', closed: true, prefs: { background: 'chartreuse' } },
                ],
              },
            })
          );
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Yellow Board/);

      const getBgColor = (name: string) => {
        let el: HTMLElement | null = screen.getByText(name);
        while (el && !el.getAttribute('style')) {
          el = el.parentElement;
        }
        return el?.getAttribute('style') || '';
      };

      expect(getBgColor('Yellow Board')).toContain('rgb(179, 89, 0)'); // #B35900
      expect(getBgColor('Purple Board')).toContain('rgb(121, 101, 224)'); // #7965E0
      expect(getBgColor('Pink Board')).toContain('rgb(205, 90, 145)'); // #CD5A91
      expect(getBgColor('Sky Board')).toContain('rgb(0, 194, 224)'); // #00C2E0
      expect(getBgColor('Lime Board')).toContain('rgb(103, 185, 106)'); // #67B96A
      expect(getBgColor('Mystery Board')).toContain('rgb(0, 121, 191)'); // default #0079BF
    });

    test('search matches board descriptions too', async () => {
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      const searchInput = screen.getByPlaceholderText(/search boards/i);
      fireEvent.change(searchInput, { target: { value: 'Marketing site' } });

      await waitFor(() => {
        expect(screen.getByText('Website Redesign')).toBeInTheDocument();
      });
      expect(screen.queryByText('Mobile App')).not.toBeInTheDocument();
    });
  });

  describe('lists', () => {
    test('shows empty state until a board is selected', async () => {
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await userEvent.click(screen.getByRole('button', { name: 'Lists' }));
      expect(screen.getByText('Select a board to view lists')).toBeInTheDocument();
    });

    test('selecting a board loads its lists and renders them in the Lists tab', async () => {
      const listBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/trello/lists', (req, res, ctx) => {
          listBodies.push(req.body);
          return res(
            ctx.status(200),
            ctx.json({
              data: {
                lists: [
                  { id: 'l1', name: 'To Do', pos: 1, idBoard: 'b1', closed: false },
                  { id: 'l2', name: 'Done', pos: 2, idBoard: 'b1', closed: false },
                ],
              },
            })
          );
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      // Click the board card in the Boards tab to select it
      await userEvent.click(screen.getByText('Website Redesign'));
      await waitFor(() => {
        expect(listBodies.some((b) => b.board_id === 'b1')).toBe(true);
      });

      await userEvent.click(screen.getByRole('button', { name: 'Lists' }));

      await waitFor(() => {
        expect(screen.getByText('To Do')).toBeInTheDocument();
        expect(screen.getByText('Done')).toBeInTheDocument();
      });
      expect(screen.getByText('Position: 1')).toBeInTheDocument();
      expect(screen.getByText('Position: 2')).toBeInTheDocument();
    });

    test('handles lists load failure without crashing', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/trello/lists', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await userEvent.click(screen.getByText('Website Redesign'));
      await userEvent.click(screen.getByRole('button', { name: 'Lists' }));

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      expect(screen.queryByText('To Do')).not.toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('cards', () => {
    test('shows empty state until board and list are selected', async () => {
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await userEvent.click(screen.getByRole('button', { name: 'Cards' }));
      expect(screen.getByText('Select a board and list to view cards')).toBeInTheDocument();
    });

    test('renders cards with due badges, member avatars, and badge counts', async () => {
      const user = userEvent.setup();
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await selectBoardAndList(user);

      // Cards from the fixture render
      expect(screen.getByText('Fix login bug')).toBeInTheDocument();
      expect(screen.getByText('Launch v2')).toBeInTheDocument();
      expect(screen.getByText('No due card')).toBeInTheDocument();
      // Card description
      expect(screen.getByText('Auth crash on session refresh')).toBeInTheDocument();
      // Due badges: c1/c2/c3/c5 have due dates; c2 is completed
      expect(screen.getAllByText(/^Due: /).length).toBe(4);
      expect(screen.getByText('Complete')).toBeInTheDocument();
      // Badge counts (comments / checkItemsChecked-checkItems / attachments)
      expect(screen.getByText('1/2')).toBeInTheDocument();
      expect(screen.getByText('7')).toBeInTheDocument();
      // Member avatar initials for the assigned member (m1 = Alice Chen)
      expect(screen.getByText('AC')).toBeInTheDocument();
    });

    test('filters cards by search query', async () => {
      const user = userEvent.setup();
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await selectBoardAndList(user);

      fireEvent.change(screen.getByPlaceholderText(/search cards/i), { target: { value: 'login' } });

      await waitFor(() => {
        expect(screen.getByText('Fix login bug')).toBeInTheDocument();
      });
      expect(screen.queryByText('Launch v2')).not.toBeInTheDocument();
    });

    test('create card button is disabled until a list is selected', async () => {
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await userEvent.click(screen.getByRole('button', { name: 'Cards' }));

      const createCardButton = screen.getByRole('button', { name: /create card/i });
      expect(createCardButton).toBeDisabled();
    });

    test('creates a card via the dialog', async () => {
      const user = userEvent.setup();
      const createBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/trello/cards/create', (req, res, ctx) => {
          createBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { card: {} } }));
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await selectBoardAndList(user);

      await user.click(screen.getByRole('button', { name: /create card/i }));
      const dialog = await screen.findByRole('dialog');

      // Submit is disabled until title and list are provided
      expect(within(dialog).getByRole('button', { name: /^create card$/i })).toBeDisabled();

      await user.type(within(dialog).getByPlaceholderText('Enter card title'), 'Test card');
      await user.type(within(dialog).getByPlaceholderText(/card description/i), 'Details here');

      // Pick a list inside the dialog (list select is the first combobox there)
      await user.click(within(dialog).getAllByRole('combobox')[0]);
      await user.click(within(await screen.findByRole('listbox')).getByText('Done'));

      // Assign a member (members select is the second combobox)
      await user.click(within(dialog).getAllByRole('combobox')[1]);
      await user.click(within(await screen.findByRole('listbox')).getByText('Alice Chen'));

      // Set a due date
      const dueInput = document.querySelector(
        '#dialog-content input[type="datetime-local"]'
      ) as HTMLInputElement;
      fireEvent.change(dueInput, { target: { value: '2025-01-15T09:00' } });

      await user.click(within(dialog).getByRole('button', { name: /^create card$/i }));

      await waitFor(() => {
        expect(
          createBodies.some(
            (b) =>
              b.name === 'Test card' &&
              b.description === 'Details here' &&
              b.list_id === 'l2' &&
              b.due === '2025-01-15T09:00' &&
              Array.isArray(b.id_members) &&
              b.id_members.length > 0
          )
        ).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Card created successfully',
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    test('cancel closes the create card dialog without submitting', async () => {
      const user = userEvent.setup();
      const createBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/trello/cards/create', (req, res, ctx) => {
          createBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: {} }));
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await selectBoardAndList(user);

      await user.click(screen.getByRole('button', { name: /create card/i }));
      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /^cancel$/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(createBodies).toHaveLength(0);
    });

    test('shows error toast when card creation fails', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/trello/cards/create', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await selectBoardAndList(user);

      await user.click(screen.getByRole('button', { name: /create card/i }));
      const dialog = await screen.findByRole('dialog');
      await user.type(within(dialog).getByPlaceholderText('Enter card title'), 'Doomed card');
      await user.click(within(dialog).getAllByRole('combobox')[0]);
      await user.click(within(await screen.findByRole('listbox')).getByText('To Do'));
      await user.click(within(dialog).getByRole('button', { name: /^create card$/i }));

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to create card',
          variant: 'error',
        });
      });
      // Dialog stays open so the user can retry
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('create board flow', () => {
    test('creates a board with selected options via the dialog', async () => {
      const user = userEvent.setup();
      const createBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/trello/boards/create', (req, res, ctx) => {
          createBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { board: {} } }));
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await user.click(screen.getByRole('button', { name: /create board/i }));
      const dialog = await screen.findByRole('dialog');

      expect(within(dialog).getByRole('button', { name: /^create board$/i })).toBeDisabled();

      await user.type(within(dialog).getByPlaceholderText('Enter board name'), 'New Board');
      await user.type(within(dialog).getByPlaceholderText(/board description/i), 'A fresh board');
      // Toggle off Default Labels + Default Lists
      await user.click(within(dialog).getByLabelText('Default Labels'));
      await user.click(within(dialog).getByLabelText('Default Lists'));
      // Pick Public permission level
      await user.click(within(dialog).getByRole('combobox'));
      await user.click(within(await screen.findByRole('listbox')).getByText('Public'));

      await user.click(within(dialog).getByRole('button', { name: /^create board$/i }));

      await waitFor(() => {
        expect(
          createBodies.some(
            (b) =>
              b.name === 'New Board' &&
              b.description === 'A fresh board' &&
              b.default_labels === false &&
              b.default_lists === false &&
              b.permission_level === 'public'
          )
        ).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Board created successfully',
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    test('cancel closes the create board dialog without submitting', async () => {
      const user = userEvent.setup();
      const createBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/trello/boards/create', (req, res, ctx) => {
          createBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { board: {} } }));
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await user.click(screen.getByRole('button', { name: /create board/i }));
      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /^cancel$/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(createBodies).toHaveLength(0);
    });

    test('shows error toast when board creation fails and keeps dialog open', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/trello/boards/create', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await user.click(screen.getByRole('button', { name: /create board/i }));
      const dialog = await screen.findByRole('dialog');
      await user.type(within(dialog).getByPlaceholderText('Enter board name'), 'Doomed Board');
      await user.click(within(dialog).getByRole('button', { name: /^create board$/i }));

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to create board',
          variant: 'error',
        });
      });
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('team tab', () => {
    test('renders members and their details', async () => {
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await userEvent.click(screen.getByRole('button', { name: 'Team' }));

      await waitFor(() => {
        expect(screen.getByText('Alice Chen')).toBeInTheDocument();
        expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      });
      expect(screen.getByText('@alice')).toBeInTheDocument();
      expect(screen.getByText('admin')).toBeInTheDocument();
      expect(screen.getByText('normal')).toBeInTheDocument();
      expect(screen.getByText('Confirmed')).toBeInTheDocument();
      expect(screen.getByText('Unconfirmed')).toBeInTheDocument();
      expect(screen.getByText('Core maintainer')).toBeInTheDocument();
    });

    test('filters members by search query', async () => {
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      await userEvent.click(screen.getByRole('button', { name: 'Team' }));
      await screen.findByText('Alice Chen');

      fireEvent.change(screen.getByPlaceholderText(/search team members/i), {
        target: { value: 'Jane' },
      });

      await waitFor(() => {
        expect(screen.queryByText('@alice')).not.toBeInTheDocument();
      });
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });
  });

  describe('error paths', () => {
    test('handles a network-level health check failure as disconnected', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.get('/api/integrations/trello/health', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<TrelloIntegration />);

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      expect(
        screen.getByRole('button', { name: /connect trello account/i })
      ).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    test('handles cards load failure without crashing', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/trello/cards', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);

      // Select board + list manually (cards never load, so the shared
      // helper's final wait for a card would time out)
      await user.click(await screen.findByRole('button', { name: 'Cards' }));
      await user.click(screen.getAllByRole('combobox')[0]);
      await user.click(within(await screen.findByRole('listbox')).getByText('Mobile App'));
      await user.click(screen.getAllByRole('combobox')[1]);
      const listbox = await screen.findByRole('listbox');
      await user.click(await within(listbox).findByText('To Do'));

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      // No cards render despite a selected list
      expect(screen.queryByText('Fix login bug')).not.toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    test('shows error toast when boards fail to load', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/trello/boards', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<TrelloIntegration />);

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to load boards from Trello',
          variant: 'error',
        });
      });
      expect(screen.getByText('Connected')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    test('handles profile load failure without crashing', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/trello/profile', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      render(<TrelloIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      consoleErrorSpy.mockRestore();
    });

    test('refresh status re-runs the health check', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');
      render(<TrelloIntegration />);

      await settleData(/Website Redesign/);
      fetchSpy.mockClear();

      await userEvent.click(screen.getByRole('button', { name: /refresh status/i }));

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          '/api/integrations/trello/health',
          expect.anything()
        );
      });
    });
  });
});

/**
 * WorkflowVersioning Component Tests
 *
 * Tests verify the real WorkflowVersioning component
 * (components/Workflow/WorkflowVersioning.tsx, a DEFAULT export):
 * - Loads versions + branches on mount (GET /api/v1/workflows/:id/versions,
 *   GET /api/v1/workflows/:id/branches)
 * - Version history rendering (badges, commit message, author, branch)
 * - Version expansion loads metrics (GET .../versions/:version/metrics)
 * - Compare tab (GET .../versions/compare?from_version=..&to_version=..)
 * - Branches tab (protected/primary badges, merge dialog)
 * - Rollback dialog (POST /api/v1/workflows/:id/rollback)
 * - Create Branch dialog (POST /api/v1/workflows/:id/branches)
 * - Merge Branch dialog (POST /api/v1/workflows/:id/branches/merge)
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import WorkflowVersioning from '../WorkflowVersioning';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const versions = [
  {
    workflow_id: 'wf-1',
    version: 'v1.0.0',
    version_type: 'major',
    change_type: 'breaking_change',
    created_at: '2024-01-01T12:00:00Z',
    created_by: 'user1',
    commit_message: 'Initial version',
    tags: ['stable', 'production'],
    parent_version: undefined,
    branch_name: 'main',
    checksum: 'abc123def4567890',
    is_active: false,
  },
  {
    workflow_id: 'wf-1',
    version: 'v2.0.0',
    version_type: 'minor',
    change_type: 'execution',
    created_at: '2024-02-01T12:00:00Z',
    created_by: 'user2',
    commit_message: 'Second version',
    tags: ['beta'],
    parent_version: 'v1.0.0',
    branch_name: 'main',
    checksum: 'def456',
    is_active: true,
  },
];

const branches = [
  {
    branch_name: 'main',
    workflow_id: 'wf-1',
    base_version: 'v1.0.0',
    current_version: 'v2.0.0',
    created_at: '2024-01-01T12:00:00Z',
    created_by: 'user1',
    is_protected: true,
    merge_strategy: 'merge_commit',
  },
  {
    branch_name: 'feature-x',
    workflow_id: 'wf-1',
    base_version: 'v1.0.0',
    current_version: 'v1.0.0',
    created_at: '2024-01-05T12:00:00Z',
    created_by: 'user2',
    is_protected: false,
    merge_strategy: 'squash',
  },
];

const metrics = {
  execution_count: 42,
  success_rate: 92.5,
  avg_execution_time: 1200,
  error_count: 3,
  last_execution: '2024-01-02T12:00:00Z',
  performance_score: 87,
};

const diff = {
  workflow_id: 'wf-1',
  from_version: 'v1.0.0',
  to_version: 'v2.0.0',
  impact_level: 'high',
  added_steps_count: 2,
  removed_steps_count: 1,
  modified_steps_count: 3,
  structural_changes: ['Replaced step "send-email" with "send-notification"'],
  dependency_changes: [],
  parametric_changes: {},
  metadata_changes: {},
};

const defaultHandlers = [
  rest.get('/api/v1/workflows/wf-1/versions', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(versions));
  }),

  rest.get('/api/v1/workflows/wf-1/branches', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(branches));
  }),

  rest.get('/api/v1/workflows/wf-1/versions/v1.0.0/metrics', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ metrics }));
  }),

  rest.get('/api/v1/workflows/wf-1/versions/compare', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(diff));
  }),

  rest.post('/api/v1/workflows/wf-1/rollback', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/v1/workflows/wf-1/branches', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/v1/workflows/wf-1/branches/merge', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

describe('WorkflowVersioning', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...defaultHandlers);
  });

  // Test 1: renders heading and refresh button after data loads
  test('renders heading and refresh button', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /workflow versioning/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /refresh/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: displays versions in the history tab
  test('displays versions in the history tab', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    await waitFor(() => {
      expect(screen.getByText('v1.0.0')).toBeInTheDocument();
      expect(screen.getByText('v2.0.0')).toBeInTheDocument();
    });
    expect(screen.getByText('Initial version')).toBeInTheDocument();
    expect(screen.getByText('Second version')).toBeInTheDocument();
    expect(screen.getByText('user1')).toBeInTheDocument();
    expect(screen.getByText('user2')).toBeInTheDocument();
  });

  // Test 3: shows version badges (type, change type, tags)
  test('shows version type, change type, and tag badges', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    await waitFor(() => {
      expect(screen.getByText('major')).toBeInTheDocument();
      expect(screen.getByText('breaking_change')).toBeInTheDocument();
      expect(screen.getByText('minor')).toBeInTheDocument();
      expect(screen.getByText('stable')).toBeInTheDocument();
      expect(screen.getByText('production')).toBeInTheDocument();
    });
  });

  // Test 4: shows all four tab triggers
  test('shows all tab triggers', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /version history/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /compare/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /branches/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /metrics/i })
      ).toBeInTheDocument();
    });
  });

  // Test 5: expanding a version reveals detail actions
  test('expanding a version reveals detail actions', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    const version = await screen.findByText('v1.0.0');
    fireEvent.click(version);

    await waitFor(() => {
      expect(screen.getByText('View Details')).toBeInTheDocument();
      expect(screen.getByText('Create Branch')).toBeInTheDocument();
      expect(screen.getByText('Rollback')).toBeInTheDocument();
      expect(screen.getByText('Checksum')).toBeInTheDocument();
      expect(screen.getByText('Parent Version')).toBeInTheDocument();
    });
  });

  // Test 6: expanding a version loads its metrics
  test('expansion loads performance metrics for the version', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    const version = await screen.findByText('v1.0.0');
    fireEvent.click(version);

    await waitFor(() => {
      expect(screen.getByText('Executions')).toBeInTheDocument();
      expect(screen.getByText('92.5%')).toBeInTheDocument();
      expect(screen.getByText('Avg Time')).toBeInTheDocument();
      expect(screen.getByText('Performance')).toBeInTheDocument();
    });
  });

  // Test 7: compare tab fetches and shows a diff
  test('compare tab fetches and displays the version diff', async () => {
    const user = userEvent.setup();
    render(<WorkflowVersioning workflowId="wf-1" />);

    await screen.findByText('v1.0.0');

    fireEvent.click(screen.getByRole('button', { name: /compare/i }));

    await waitFor(() => {
      expect(screen.getByText('Version Comparison')).toBeInTheDocument();
    });

    // Radix Select triggers render with role="combobox" (not "button")
    const [fromSelect, toSelect] = screen.getAllByRole('combobox');
    await user.click(fromSelect);
    await user.click(await screen.findByText('v1.0.0 - Initial version'));

    await user.click(toSelect);
    await user.click(await screen.findByText('v2.0.0 - Second version'));

    fireEvent.click(
      screen.getByRole('button', { name: /compare versions/i })
    );

    await waitFor(() => {
      expect(screen.getByText('Comparison Results')).toBeInTheDocument();
      expect(screen.getByText('HIGH IMPACT')).toBeInTheDocument();
      expect(screen.getByText('Structural Changes')).toBeInTheDocument();
    });
  });

  // Test 8: branches tab shows table with protected and primary badges
  test('branches tab displays branch table with badges', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    await screen.findByText('v1.0.0');

    fireEvent.click(screen.getByRole('button', { name: /branches/i }));

    await waitFor(() => {
      expect(screen.getByRole('table')).toBeInTheDocument();
      expect(screen.getByText('Branch Management')).toBeInTheDocument();
      expect(screen.getByText('feature-x')).toBeInTheDocument();
      expect(screen.getByText('Primary')).toBeInTheDocument();
      expect(screen.getByText('Protected')).toBeInTheDocument();
    });
  });

  // Test 9: metrics tab shows metrics for expanded versions
  test('metrics tab displays loaded version metrics', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    const version = await screen.findByText('v1.0.0');
    fireEvent.click(version);

    fireEvent.click(screen.getByRole('button', { name: /metrics/i }));

    await waitFor(() => {
      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
      expect(screen.getByText('Total Executions')).toBeInTheDocument();
      expect(screen.getByText('92.5% Success')).toBeInTheDocument();
      expect(screen.getByText('Score: 87')).toBeInTheDocument();
    });
  });

  // Test 10: rollback button opens the rollback dialog
  test('rollback button opens the rollback dialog', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    const version = await screen.findByText('v1.0.0');
    fireEvent.click(version);

    fireEvent.click(screen.getByRole('button', { name: /rollback/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Rollback Workflow')).toBeInTheDocument();
    });
  });

  // Test 11: rollback submits POST with target version and reason
  test('rollback posts target version and reason', async () => {
    let rollbackBody: any = null;
    server.use(
      rest.post('/api/v1/workflows/wf-1/rollback', (req, res, ctx) => {
        // MSW pre-parses JSON request bodies into objects
        rollbackBody = req.body as any;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<WorkflowVersioning workflowId="wf-1" />);

    const version = await screen.findByText('v1.0.0');
    fireEvent.click(version);

    fireEvent.click(screen.getByRole('button', { name: /rollback/i }));
    await screen.findByRole('dialog');

    fireEvent.change(screen.getByLabelText(/reason for rollback/i), {
      target: { value: 'Critical bug' },
    });

    // Dialog submit button is the second "Rollback" button (action first)
    fireEvent.click(screen.getAllByRole('button', { name: /rollback/i })[1]);

    await waitFor(() => {
      expect(rollbackBody).toEqual(
        expect.objectContaining({
          target_version: 'v1.0.0',
          rollback_reason: 'Critical bug',
        })
      );
    });
  });

  // Test 12: create branch dialog posts branch name and base version
  test('create branch dialog posts the new branch', async () => {
    let branchBody: any = null;
    server.use(
      rest.post('/api/v1/workflows/wf-1/branches', (req, res, ctx) => {
        // MSW pre-parses JSON request bodies into objects
        branchBody = req.body as any;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<WorkflowVersioning workflowId="wf-1" />);

    const version = await screen.findByText('v1.0.0');
    fireEvent.click(version);

    fireEvent.click(screen.getByRole('button', { name: /create branch/i }));
    await screen.findByRole('dialog');

    fireEvent.change(screen.getByLabelText(/branch name/i), {
      target: { value: 'feature/test' },
    });

    // Dialog submit button is the second "Create Branch" button (action first)
    fireEvent.click(
      screen.getAllByRole('button', { name: /create branch/i })[1]
    );

    await waitFor(() => {
      expect(branchBody).toEqual(
        expect.objectContaining({
          branch_name: 'feature/test',
          base_version: 'v1.0.0',
        })
      );
    });
  });

  // Test 13: Merge Branches button opens the merge dialog
  test('merge branches button opens the merge dialog', async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);

    await screen.findByText('v1.0.0');

    fireEvent.click(screen.getByRole('button', { name: /branches/i }));
    fireEvent.click(screen.getByRole('button', { name: /merge branches/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      // Title is a heading; the dialog's submit button also says "Merge Branch"
      expect(
        screen.getByRole('heading', { name: /merge branch/i })
      ).toBeInTheDocument();
    });
  });

  // Test 14: renders the heading with no versions (empty state)
  test('renders empty state when there are no versions', async () => {
    server.use(
      rest.get('/api/v1/workflows/wf-1/versions', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json([]));
      }),
      rest.get('/api/v1/workflows/wf-1/branches', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json([]));
      })
    );

    render(<WorkflowVersioning workflowId="wf-1" />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /workflow versioning/i })
      ).toBeInTheDocument();
    });
    expect(screen.queryByText('v1.0.0')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: collapse/refresh, badge variants, parametric diff,
// merge flow, and network-error paths
// ---------------------------------------------------------------------------
describe('WorkflowVersioning (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  let logSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...defaultHandlers);
  });
  afterEach(() => {
    errorSpy.mockRestore();
    logSpy.mockRestore();
  });

  const renderAndSettle = async () => {
    render(<WorkflowVersioning workflowId="wf-1" />);
    await screen.findByText('v1.0.0');
    await new Promise((r) => setTimeout(r, 50));
  };

  const expand = (version: string) => {
    fireEvent.click(screen.getByText(version));
  };

  test('collapsing an expanded version hides the details', async () => {
    await renderAndSettle();

    expand('v1.0.0');
    await waitFor(() => {
      expect(screen.getByText('View Details')).toBeInTheDocument();
    });

    expand('v1.0.0');
    await waitFor(() => {
      expect(screen.queryByText('View Details')).not.toBeInTheDocument();
    });
  });

  test('Refresh button re-fetches workflow data', async () => {
    await renderAndSettle();

    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    });
  });

  test('View Details selects the version for rollback context', async () => {
    await renderAndSettle();

    // v2.0.0 is the active version, so its Rollback button is disabled;
    // use v1.0.0 for the dialog flow and cover View Details on it too.
    expand('v1.0.0');
    fireEvent.click((await screen.findAllByRole('button', { name: /view details/i }))[0]);
    fireEvent.click(screen.getByRole('button', { name: /rollback/i }));

    const dialog = await screen.findByRole('dialog');
    await waitFor(() => {
      expect(dialog.textContent).toContain('Rollback the workflow to version v1.0.0');
    });
  });

  test('renders all version-type and change-type badge variants', async () => {
    const variedVersions = [
      ...versions,
      {
        workflow_id: 'wf-1',
        version: 'v2.1.0',
        version_type: 'patch',
        change_type: 'dependency',
        created_at: '2024-03-01T12:00:00Z',
        created_by: 'user3',
        commit_message: 'Patch version',
        tags: [],
        parent_version: 'v2.0.0',
        branch_name: 'main',
        checksum: 'aaa',
        is_active: false,
      },
      {
        workflow_id: 'wf-1',
        version: 'v2.2.0',
        version_type: 'hotfix',
        change_type: 'parametric',
        created_at: '2024-04-01T12:00:00Z',
        created_by: 'user3',
        commit_message: 'Hotfix version',
        tags: [],
        parent_version: 'v2.1.0',
        branch_name: 'main',
        checksum: 'bbb',
        is_active: false,
      },
      {
        workflow_id: 'wf-1',
        version: 'v3.0.0-beta',
        version_type: 'beta',
        change_type: 'metadata',
        created_at: '2024-05-01T12:00:00Z',
        created_by: 'user3',
        commit_message: 'Beta version',
        tags: [],
        parent_version: 'v2.2.0',
        branch_name: 'main',
        checksum: 'ccc',
        is_active: false,
      },
      {
        workflow_id: 'wf-1',
        version: 'v3.0.0-alpha',
        version_type: 'alpha',
        change_type: 'structural',
        created_at: '2024-06-01T12:00:00Z',
        created_by: 'user3',
        commit_message: 'Alpha version',
        tags: [],
        parent_version: 'v3.0.0-beta',
        branch_name: 'main',
        checksum: 'ddd',
        is_active: false,
      },
    ];

    server.use(
      rest.get('/api/v1/workflows/wf-1/versions', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json(variedVersions));
      })
    );

    await renderAndSettle();

    for (const label of ['patch', 'hotfix', 'beta', 'alpha', 'major', 'minor']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    for (const label of ['dependency', 'parametric', 'metadata', 'structural']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  test('renders parametric change details in the compare tab', async () => {
    const user = userEvent.setup();
    server.use(
      rest.get('/api/v1/workflows/wf-1/versions/compare', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            ...diff,
            impact_level: 'critical',
            parametric_changes: {
              step_send_email: { to: 'new@example.com', retries: 3 },
            },
          })
        );
      })
    );

    render(<WorkflowVersioning workflowId="wf-1" />);
    await screen.findByText('v1.0.0');

    fireEvent.click(screen.getByRole('button', { name: /compare/i }));
    await screen.findByText('Version Comparison');

    const [fromSelect, toSelect] = screen.getAllByRole('combobox');
    await user.click(fromSelect);
    await user.click(await screen.findByText('v1.0.0 - Initial version'));
    await user.click(toSelect);
    await user.click(await screen.findByText('v2.0.0 - Second version'));
    fireEvent.click(screen.getByRole('button', { name: /compare versions/i }));

    expect(await screen.findByText(/CRITICAL IMPACT/i)).toBeInTheDocument();
    expect(screen.getByText('Parameter Changes')).toBeInTheDocument();
    expect(screen.getByText('Step: step_send_email')).toBeInTheDocument();
    expect(screen.getByText(/"retries": 3/)).toBeInTheDocument();
  });

  test('merges a branch from the branches tab pull-request action', async () => {
    let mergeBody: any = null;
    server.use(
      rest.post('/api/v1/workflows/wf-1/branches/merge', (req, res, ctx) => {
        mergeBody = req.body as any;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<WorkflowVersioning workflowId="wf-1" />);
    await screen.findByText('v1.0.0');

    fireEvent.click(screen.getByRole('button', { name: /branches/i }));
    // feature-x row's pull-request button presets source/target (it does NOT
    // open the dialog; the main-row button is disabled, so pick an enabled one)
    const prButton = Array.from(document.querySelectorAll('.lucide-git-pull-request'))
      .map((svg) => (svg as HTMLElement).closest('button'))
      .find((btn) => btn && !(btn as HTMLButtonElement).disabled) as HTMLElement;
    fireEvent.click(prButton);
    fireEvent.click(screen.getByRole('button', { name: /merge branches/i }));
    await screen.findByRole('dialog');

    const mergeButtons = screen.getAllByRole('button', { name: /merge branch/i });
    fireEvent.click(mergeButtons[mergeButtons.length - 1]);

    await waitFor(() => {
      expect(mergeBody).toEqual(
        expect.objectContaining({
          source_branch: 'feature-x',
          target_branch: 'main',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('logs fetch errors when the versions endpoint fails', async () => {
    server.use(
      rest.get('/api/v1/workflows/wf-1/versions', (req, res) => res.networkError('boom'))
    );

    render(<WorkflowVersioning workflowId="wf-1" />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Error fetching workflow data:', expect.anything());
    });
  });

  test('logs errors when metrics and diff fetches fail', async () => {
    const user = userEvent.setup();
    server.use(
      rest.get('/api/v1/workflows/wf-1/versions/v1.0.0/metrics', (req, res) =>
        res.networkError('boom')
      ),
      rest.get('/api/v1/workflows/wf-1/versions/compare', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<WorkflowVersioning workflowId="wf-1" />);
    await screen.findByText('v1.0.0');

    expand('v1.0.0');
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Error fetching version metrics:', expect.anything());
    });

    fireEvent.click(screen.getByRole('button', { name: /compare/i }));
    await screen.findByText('Version Comparison');
    const [fromSelect, toSelect] = screen.getAllByRole('combobox');
    await user.click(fromSelect);
    await user.click(await screen.findByText('v1.0.0 - Initial version'));
    await user.click(toSelect);
    await user.click(await screen.findByText('v2.0.0 - Second version'));
    fireEvent.click(screen.getByRole('button', { name: /compare versions/i }));

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Error fetching version diff:', expect.anything());
    });
  });

  test('logs errors when rollback, branch create and merge fail', async () => {
    server.use(
      rest.post('/api/v1/workflows/wf-1/rollback', (req, res) => res.networkError('boom')),
      rest.post('/api/v1/workflows/wf-1/branches', (req, res) => res.networkError('boom')),
      rest.post('/api/v1/workflows/wf-1/branches/merge', (req, res) => res.networkError('boom'))
    );

    render(<WorkflowVersioning workflowId="wf-1" />);
    await screen.findByText('v1.0.0');

    // rollback failure (the dialog stays open on failure — cancel it after)
    expand('v1.0.0');
    fireEvent.click(screen.getByRole('button', { name: /rollback/i }));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByLabelText(/reason for rollback/i), {
      target: { value: 'Because' },
    });
    fireEvent.click(screen.getAllByRole('button', { name: /rollback/i })[1]);
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Error during rollback:', expect.anything());
    });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // branch creation failure (the row is still expanded from above)
    fireEvent.click(screen.getByRole('button', { name: /create branch/i }));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByLabelText(/branch name/i), {
      target: { value: 'feature/fail' },
    });
    fireEvent.click(screen.getAllByRole('button', { name: /create branch/i })[1]);
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Error creating branch:', expect.anything());
    });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // merge failure
    fireEvent.click(screen.getByRole('button', { name: /branches/i }));
    const prBtn = Array.from(document.querySelectorAll('.lucide-git-pull-request'))
      .map((svg) => (svg as HTMLElement).closest('button'))
      .find((btn) => btn && !(btn as HTMLButtonElement).disabled) as HTMLElement;
    fireEvent.click(prBtn);
    fireEvent.click(screen.getByRole('button', { name: /merge branches/i }));
    await screen.findByRole('dialog');
    const mergeButtons = screen.getAllByRole('button', { name: /merge branch/i });
    fireEvent.click(mergeButtons[mergeButtons.length - 1]);
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Error during merge:', expect.anything());
    });
  });
});

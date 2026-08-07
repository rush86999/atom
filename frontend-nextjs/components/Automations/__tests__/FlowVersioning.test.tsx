/**
 * FlowVersioning Component Tests
 *
 * Tests verify the real FlowVersioning component
 * (components/Automations/FlowVersioning.tsx, a DEFAULT export):
 * - Renders version history timeline (static SAMPLE_VERSIONS)
 * - Flow name + version count in header
 * - "Current" badge on the current version
 * - Empty-state prompt before a version is selected
 * - Selecting a version shows details (changes summary + flow statistics)
 * - Compare mode banner + onCompareVersions callback
 * - View button invokes onViewVersion
 * - Restore button prompts via window.confirm, then onRestoreVersion
 * - Cancel compare button
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import FlowVersioning, { FlowVersion } from '../FlowVersioning';

describe('FlowVersioning', () => {
  const mockOnRestoreVersion = jest.fn();
  const mockOnViewVersion = jest.fn();
  const mockOnCompareVersions = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the header with flow name and version count', () => {
    render(
      <FlowVersioning flowName="My Sales Flow" onRestoreVersion={mockOnRestoreVersion} />
    );

    expect(screen.getByText('Version History')).toBeInTheDocument();
    expect(screen.getByText('My Sales Flow')).toBeInTheDocument();
    expect(screen.getByText('8 versions')).toBeInTheDocument();
  });

  it('renders every version in the timeline with messages and authors', () => {
    render(<FlowVersioning />);

    expect(screen.getByText('v2.3.0')).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('Added AI enrichment step and Slack notification')).toBeInTheDocument();
    expect(screen.getByText('Initial version')).toBeInTheDocument();
    expect(screen.getByText('Team Member')).toBeInTheDocument();
    // Change summaries
    expect(screen.getByText('+2 ~1 nodes')).toBeInTheDocument();
    expect(screen.getByText('+6 nodes')).toBeInTheDocument();
  });

  it('marks only the current version with a "Current" badge', () => {
    render(<FlowVersioning />);

    // Badge renders a div with the green "current" styling
    expect(screen.getByText('Current')).toHaveClass('bg-green-100');
  });

  it('shows the empty state prompt before a version is selected', () => {
    render(<FlowVersioning />);

    expect(screen.getByText('Select a Version')).toBeInTheDocument();
    expect(screen.getByText('Choose a version from the timeline to view details')).toBeInTheDocument();
  });

  it('shows version details after selecting a version from the timeline', async () => {
    const user = userEvent.setup();
    render(<FlowVersioning />);

    await user.click(screen.getAllByText('Initial version')[0]);

    // Detail panel header (list row + detail heading both show the version)
    expect(screen.getByRole('heading', { name: 'v1.0.0' })).toBeInTheDocument();
    // Changes summary cards
    expect(screen.getByText('Nodes Added')).toBeInTheDocument();
    expect(screen.getByText('+6')).toBeInTheDocument();
    expect(screen.getByText('Nodes Modified')).toBeInTheDocument();
    expect(screen.getByText('~0')).toBeInTheDocument();
    expect(screen.getByText('Nodes Removed')).toBeInTheDocument();
    expect(screen.getByText('-0')).toBeInTheDocument();
    // Flow statistics
    expect(screen.getByText('Flow Statistics')).toBeInTheDocument();
    expect(screen.getByText('Total Nodes')).toBeInTheDocument();
    expect(screen.getByText('Connections')).toBeInTheDocument();
  });

  it('shows the current version badge in details when the current version is selected', async () => {
    const user = userEvent.setup();
    render(<FlowVersioning />);

    await user.click(screen.getAllByText('Added AI enrichment step and Slack notification')[0]);

    expect(screen.getByText('Current Version')).toBeInTheDocument();
  });

  it('hides the Restore button for the current version', async () => {
    const user = userEvent.setup();
    render(<FlowVersioning />);

    await user.click(screen.getAllByText('Added AI enrichment step and Slack notification')[0]);
    expect(screen.queryByRole('button', { name: /restore/i })).not.toBeInTheDocument();

    await user.click(screen.getAllByText('Initial version')[0]);
    expect(screen.getByRole('button', { name: /restore/i })).toBeInTheDocument();
  });

  it('calls onViewVersion with the selected version', async () => {
    const user = userEvent.setup();
    render(<FlowVersioning onViewVersion={mockOnViewVersion} />);

    await user.click(screen.getAllByText('Initial version')[0]);
    await user.click(screen.getByRole('button', { name: /view/i }));

    expect(mockOnViewVersion).toHaveBeenCalledTimes(1);
    const version = mockOnViewVersion.mock.calls[0][0] as FlowVersion;
    expect(version.id).toBe('v1');
    expect(version.version).toBe('1.0.0');
  });

  it('prompts before restoring and calls onRestoreVersion when confirmed', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    render(<FlowVersioning onRestoreVersion={mockOnRestoreVersion} />);

    await user.click(screen.getAllByText('Initial version')[0]);
    await user.click(screen.getByRole('button', { name: /restore/i }));

    expect(confirmSpy).toHaveBeenCalledWith('Restore to version 1.0.0? This will create a new version.');
    expect(mockOnRestoreVersion).toHaveBeenCalledTimes(1);
    expect(mockOnRestoreVersion.mock.calls[0][0].id).toBe('v1');
    confirmSpy.mockRestore();
  });

  it('does not restore when the confirm dialog is cancelled', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup();
    render(<FlowVersioning onRestoreVersion={mockOnRestoreVersion} />);

    await user.click(screen.getAllByText('Initial version')[0]);
    await user.click(screen.getByRole('button', { name: /restore/i }));

    expect(mockOnRestoreVersion).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('enters compare mode and compares two versions', async () => {
    const user = userEvent.setup();
    render(<FlowVersioning onCompareVersions={mockOnCompareVersions} />);

    // Select a non-current version, then hit Compare
    await user.click(screen.getAllByText('Initial version')[0]);
    await user.click(screen.getByRole('button', { name: /compare/i }));

    // Banner tells us to pick the second version
    expect(screen.getByText(/select another version to compare with v1.0.0/i)).toBeInTheDocument();

    // Pick the current version from the timeline → comparison fires
    await user.click(screen.getAllByText('Added AI enrichment step and Slack notification')[0]);

    expect(mockOnCompareVersions).toHaveBeenCalledTimes(1);
    const [first, second] = mockOnCompareVersions.mock.calls[0] as [FlowVersion, FlowVersion];
    expect(first.id).toBe('v1');
    expect(second.id).toBe('v8');
  });

  it('cancels compare mode without firing the callback', async () => {
    const user = userEvent.setup();
    render(<FlowVersioning onCompareVersions={mockOnCompareVersions} />);

    await user.click(screen.getAllByText('Initial version')[0]);
    await user.click(screen.getByRole('button', { name: /compare/i }));
    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(screen.queryByText(/select another version to compare/i)).not.toBeInTheDocument();
    expect(mockOnCompareVersions).not.toHaveBeenCalled();
  });
});

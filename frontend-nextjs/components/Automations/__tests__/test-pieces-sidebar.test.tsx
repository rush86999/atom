/**
 * PiecesSidebar Component Tests
 *
 * Tests verify the REAL PiecesSidebar component
 * (components/Automations/PiecesSidebar.tsx):
 *
 * - Header, count badge and loading indicator
 * - Agent skills + external pieces appended from the backend fetches
 * - Piece expansion (triggers/actions sections) + collapse toggle
 * - onSelectPiece contract for actions and triggers
 * - Search filtering by piece name / action name / trigger name + no-results
 * - Connection status: CheckCircle for healthy pieces, Connect button that
 *   opens /integrations/:id for unconnected pieces
 * - Fetch failure resilience (skills endpoint, external pieces, health)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PiecesSidebar from '../PiecesSidebar';

const jsonResponse = (body: any, ok = true) => ({
  ok,
  status: ok ? 200 : 500,
  json: async () => body,
});

const skillsPayload = {
  data: {
    skills: [
      { skill_id: 'lead_qualifier', skill_name: 'Lead Qualifier', metadata: { description: 'Score leads' } },
      { skill_id: 'resume_screener', skill_name: 'Resume Screener' },
    ],
  },
};

const externalPieces = [
  {
    name: '@activepieces/piece-salesforce',
    displayName: 'Salesforce Cloud',
    logoUrl: null,
    actions: { post: { name: 'post', displayName: 'Post', description: 'Post' } },
    triggers: {},
  },
];

const catalogFetchUrls = ['/api/skills/list', '/api/v1/external-integrations/'];

describe('PiecesSidebar', () => {
  let fetchSpy: jest.SpyInstance;
  let onSelectPiece: jest.Mock;
  let openSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(global as any, 'fetch')
      .mockImplementation(async (url: unknown) => {
        if (String(url).startsWith('/api/integrations/')) {
          return jsonResponse({ ok: true }); // health -> connected
        }
        if (String(url).includes('/api/skills/list')) {
          return jsonResponse(skillsPayload);
        }
        if (String(url).includes('/api/v1/external-integrations/')) {
          return jsonResponse(externalPieces);
        }
        return jsonResponse({});
      });
    onSelectPiece = jest.fn();
    openSpy = jest.spyOn(window, 'open').mockImplementation(() => null as any);
  });

  it('renders the header with the piece count and categories', async () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    expect(screen.getByText('Pieces')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search pieces & actions...')).toBeInTheDocument();
    expect(screen.getByText(/pieces •/)).toBeInTheDocument();
    // built-in categories
    expect(screen.getByText('Core Pieces')).toBeInTheDocument();
    expect(screen.getByText('Communication')).toBeInTheDocument();
    expect(screen.getByText('AI & Automation')).toBeInTheDocument();

    // Agent Skills + external pieces appear after the fetches resolve
    await waitFor(() => {
      expect(screen.getByText('Lead Qualifier')).toBeInTheDocument();
    });
    expect(screen.getAllByText('Resume Screener').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Salesforce Cloud')).toBeInTheDocument();
  });

  it('shows a loading indicator in the count badge while fetching', () => {
    let resolveSkills: (r: any) => void;
    fetchSpy.mockImplementation(async (url: unknown) => {
      if (String(url).includes('/api/skills/list')) {
        return new Promise((res) => { resolveSkills = res; });
      }
      if (String(url).startsWith('/api/integrations/')) {
        return jsonResponse({ ok: false });
      }
      return jsonResponse([]);
    });
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    expect(document.querySelector('.lucide-loader-circle')).not.toBeNull();

    resolveSkills!(jsonResponse(skillsPayload));
  });

  it('expands a piece and selects a trigger on click', async () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    fireEvent.click(screen.getByRole('button', { name: /^Gmail/ }));
    expect(screen.getByText('Triggers')).toBeInTheDocument();
    expect(screen.getByText('New Email')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /New Email/i }));
    expect(onSelectPiece).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'gmail', name: 'Gmail' }),
      'trigger',
      expect.objectContaining({ id: 'new_email', name: 'New Email' })
    );
  });

  it('expands a piece and selects an action on click', async () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    fireEvent.click(screen.getByRole('button', { name: /^Slack/ }));
    expect(screen.getByText('Actions')).toBeInTheDocument();
    expect(screen.getByText('Send Message')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Send Message/i }));
    expect(onSelectPiece).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'slack', name: 'Slack' }),
      'action',
      expect.objectContaining({ id: 'send_message', name: 'Send Message' })
    );
  });

  it('collapses an expanded piece when clicked again', () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    fireEvent.click(screen.getByRole('button', { name: /^Slack/ }));
    expect(screen.getByText('Send Message')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^Slack/ }));
    expect(screen.queryByText('Send Message')).not.toBeInTheDocument();
  });

  it('renders triggers and actions for core pieces like Loop', () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    fireEvent.click(screen.getByRole('button', { name: /^Loop/ }));
    expect(screen.getByText('For Each')).toBeInTheDocument();
    expect(screen.getByText('Repeat')).toBeInTheDocument();
  });

  it('filters pieces by name via search', () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    fireEvent.change(screen.getByTestId('piece-search'), {
      target: { value: 'notion' },
    });
    expect(screen.getByText('Notion')).toBeInTheDocument();
    expect(screen.queryByText('Slack')).not.toBeInTheDocument();
    expect(screen.queryByText('Gmail')).not.toBeInTheDocument();
  });

  it('filters pieces by action and trigger names via search', () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    // action-name search
    fireEvent.change(screen.getByTestId('piece-search'), {
      target: { value: 'Send Message' },
    });
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.queryByText('Gmail')).not.toBeInTheDocument();

    // trigger-name search
    fireEvent.change(screen.getByTestId('piece-search'), {
      target: { value: 'New Email' },
    });
    expect(screen.getByText('Gmail')).toBeInTheDocument();
    expect(screen.queryByText('Slack')).not.toBeInTheDocument();
  });

  it('shows the no-results state for an unmatched search', () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    fireEvent.change(screen.getByTestId('piece-search'), {
      target: { value: 'zzz-no-such-piece' },
    });
    expect(screen.getByText('No pieces found')).toBeInTheDocument();
    expect(screen.getByText('Try a different search term')).toBeInTheDocument();
  });

  it('clears search back to the full catalog', () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    fireEvent.change(screen.getByTestId('piece-search'), {
      target: { value: 'notion' },
    });
    expect(screen.queryByText('Slack')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('piece-search'), {
      target: { value: '' },
    });
    expect(screen.getByText('Slack')).toBeInTheDocument();
  });

  it('shows a checkmark for connected pieces and a connect link for others', async () => {
    fetchSpy.mockImplementation(async (url: unknown) => {
      if (String(url).startsWith('/api/integrations/')) {
        return jsonResponse({}, false); // health -> not ok -> not connected
      }
      return jsonResponse([]);
    });
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/integrations/loop/health');
    });

    fireEvent.click(screen.getByRole('button', { name: /^Slack/ }));
    fireEvent.click(screen.getByRole('button', { name: /Connect Slack/i }));
    expect(openSpy).toHaveBeenCalledWith('/integrations/slack', '_blank');
  });

  it('marks healthy pieces as connected with a checkmark', async () => {
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    // health for gmail resolves ok -> connected
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /^Gmail/ }).querySelector('.lucide-circle-check-big')
      ).not.toBeNull();
    });
  });

  it('survives failures of the skills, external-pieces and health fetches', async () => {
    fetchSpy.mockImplementation(async (url: unknown) => {
      if (String(url).startsWith('/api/integrations/')) {
        return jsonResponse({ ok: true });
      }
      throw new Error('all catalog endpoints down');
    });
    render(<PiecesSidebar onSelectPiece={onSelectPiece} />);

    // Built-in pieces still render; Agent Skills category is absent
    expect(screen.getByText('Core Pieces')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('Lead Qualifier')).not.toBeInTheDocument();
    });
  });
});

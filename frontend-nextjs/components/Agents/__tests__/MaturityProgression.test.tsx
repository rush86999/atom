/**
 * MaturityProgression Component Tests
 *
 * Tests verify the real MaturityProgression component
 * (components/Agents/MaturityProgression.tsx, a NAMED export):
 * - Renders the "Career Maturity Path" header + all four tier labels
 * - Context card reflects the current tier (name + description)
 * - Works for every maturity level (student → autonomous)
 * - Tooltip content with tier description on hover
 *
 * framer-motion is mocked (animations are irrelevant to behavior).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { MaturityProgression, MaturityLevel } from '../MaturityProgression';

jest.mock('framer-motion', () => {
  const React = require('react');
  const make = (tag: string) =>
    React.forwardRef((props: any, ref: any) => {
      const { initial, animate, exit, transition, layoutId, ...rest } = props;
      return React.createElement(tag, { ...rest, ref });
    });
  return {
    motion: { div: make('div') },
    AnimatePresence: ({ children }: { children: any }) => children,
  };
});

const TIER_DESCRIPTIONS: Record<MaturityLevel, string> = {
  student: '100% Manual. Requires human approval for every atomic action.',
  intern: 'Propose & Verify. Agent proposes a full plan; you approve the start.',
  supervised: 'Threshold Guarded. Automated unless high-risk or low-confidence.',
  autonomous: 'Zero Friction. Fully authorized for production execution paths.',
};

describe('MaturityProgression', () => {
  it('renders the header and all four tier labels', () => {
    render(<MaturityProgression currentLevel="student" />);

    expect(screen.getByText('Career Maturity Path')).toBeInTheDocument();
    expect(
      screen.getByText('Governance escalation from Sandbox to Production.')
    ).toBeInTheDocument();

    expect(screen.getByText('Student')).toBeInTheDocument();
    expect(screen.getByText('Intern')).toBeInTheDocument();
    expect(screen.getByText('Supervised')).toBeInTheDocument();
    expect(screen.getByText('Autonomous')).toBeInTheDocument();
  });

  it.each<MaturityLevel>(['student', 'intern', 'supervised', 'autonomous'])(
    'shows the context card for the %s tier',
    (level) => {
      render(<MaturityProgression currentLevel={level} />);

      expect(
        screen.getByText(`Currently at ${level[0].toUpperCase()}${level.slice(1)} Tier`)
      ).toBeInTheDocument();
      expect(screen.getByText(TIER_DESCRIPTIONS[level])).toBeInTheDocument();
    }
  );

  it('shows the tier description in a tooltip on hover', async () => {
    const user = userEvent.setup();
    render(<MaturityProgression currentLevel="intern" />);

    await user.hover(screen.getByText('Supervised'));

    await waitFor(
      () => {
        expect(screen.getByText('Supervised Mode')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
    expect(screen.getByText(TIER_DESCRIPTIONS.supervised)).toBeInTheDocument();
  });
});

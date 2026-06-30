/* P3.1 — AgentCard tier badge + progress hint regression coverage. */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AgentCard, AgentInfo } from '../AgentCard';

const baseAgent: AgentInfo = {
    id: 'a-1',
    name: 'Demo Assistant',
    description: 'A helpful demo agent.',
    status: 'idle',
    category: 'system',
};

const noop = () => {};

describe('AgentCard tier badge (P3.1)', () => {
    it('renders a tier badge when maturity_level is provided', () => {
        render(
            <AgentCard
                agent={{ ...baseAgent, maturity_level: 'student' }}
                onRun={noop}
                onStop={noop}
                onChat={noop}
                onEdit={noop}
                onViewReasoning={noop}
            />
        );
        // Badge text is uppercase'd via CSS but the underlying text is the tier.
        expect(screen.getByText('student')).toBeInTheDocument();
    });

    it('shows "Max tier reached" for autonomous agents', () => {
        render(
            <AgentCard
                agent={{ ...baseAgent, maturity_level: 'autonomous' }}
                onRun={noop}
                onStop={noop}
                onChat={noop}
                onEdit={noop}
                onViewReasoning={noop}
            />
        );
        expect(screen.getByText(/Max tier reached/i)).toBeInTheDocument();
    });

    it('shows the next-tier episode target for student agents', () => {
        render(
            <AgentCard
                agent={{ ...baseAgent, maturity_level: 'student' }}
                onRun={noop}
                onStop={noop}
                onChat={noop}
                onEdit={noop}
                onViewReasoning={noop}
            />
        );
        // Student needs 10 episodes to reach Intern per the canonical thresholds.
        expect(screen.getByText(/10 episodes to next tier/i)).toBeInTheDocument();
    });

    it('omits the badge block when maturity_level is missing', () => {
        render(
            <AgentCard
                agent={baseAgent}
                onRun={noop}
                onStop={noop}
                onChat={noop}
                onEdit={noop}
                onViewReasoning={noop}
            />
        );
        expect(screen.queryByText(/episodes to next tier/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/Max tier reached/i)).not.toBeInTheDocument();
    });
});

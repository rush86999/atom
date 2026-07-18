import type { Meta, StoryObj } from '@storybook/react';
import { InternProposalReview } from './InternProposalReview';

const meta: Meta<typeof InternProposalReview> = {
  title: 'Canvas/Proposals/InternProposalReview',
  component: InternProposalReview,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof InternProposalReview>;

// Pending proposal (default state)
export const Pending: Story = {
  args: {
    proposalId: 'prop-pending-001',
    onApproved: (id) => console.log('Approved:', id),
    onRejected: (id) => console.log('Rejected:', id),
  },
};

// Approved proposal (simulated)
export const Approved: Story = {
  args: {
    proposalId: 'prop-approved-002',
    onApproved: (id) => console.log('Already approved:', id),
    onRejected: (id) => console.log('Rejected:', id),
  },
};

// Rejected proposal (simulated)
export const Rejected: Story = {
  args: {
    proposalId: 'prop-rejected-003',
    onApproved: (id) => console.log('Approved:', id),
    onRejected: (id) => console.log('Already rejected:', id),
  },
};

// Proposal with feedback
export const WithFeedback: Story = {
  args: {
    proposalId: 'prop-feedback-004',
    onApproved: (id) => {
      console.log('Approved with feedback:', id);
      alert('Proposal approved with feedback!');
    },
    onRejected: (id) => {
      console.log('Rejected with feedback:', id);
      alert('Proposal rejected with feedback!');
    },
  },
};

// Action type proposal
export const ActionProposal: Story = {
  args: {
    proposalId: 'prop-action-005',
    onApproved: (id) => console.log('Action approved:', id),
    onRejected: (id) => console.log('Action rejected:', id),
  },
};

// Workflow type proposal
export const WorkflowProposal: Story = {
  args: {
    proposalId: 'prop-workflow-006',
    onApproved: (id) => console.log('Workflow approved:', id),
    onRejected: (id) => console.log('Workflow rejected:', id),
  },
};

// Analysis type proposal
export const AnalysisProposal: Story = {
  args: {
    proposalId: 'prop-analysis-007',
    onApproved: (id) => console.log('Analysis approved:', id),
    onRejected: (id) => console.log('Analysis rejected:', id),
  },
};

// High confidence proposal
export const HighConfidence: Story = {
  args: {
    proposalId: 'prop-high-conf-008',
    onApproved: (id) => console.log('High confidence approved:', id),
    onRejected: (id) => console.log('High confidence rejected:', id),
  },
};

// Low confidence proposal
export const LowConfidence: Story = {
  args: {
    proposalId: 'prop-low-conf-009',
    onApproved: (id) => console.log('Low confidence approved:', id),
    onRejected: (id) => console.log('Low confidence rejected:', id),
  },
};

// Light theme
export const LightTheme: Story = {
  args: {
    proposalId: 'prop-light-010',
    onApproved: (id) => console.log('Approved:', id),
    onRejected: (id) => console.log('Rejected:', id),
  },
  globals: {
    theme: 'light',
  },
};

// Dark theme
export const DarkTheme: Story = {
  args: {
    proposalId: 'prop-dark-011',
    onApproved: (id) => console.log('Approved:', id),
    onRejected: (id) => console.log('Rejected:', id),
  },
  globals: {
    theme: 'dark',
  },
  parameters: {
    backgrounds: {
      default: 'dark',
    },
  },
};

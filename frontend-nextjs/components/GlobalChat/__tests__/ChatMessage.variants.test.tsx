/**
 * ChatMessage render-variant tests (non-error paths).
 *
 * Covers the REAL ChatMessage (components/GlobalChat/ChatMessage.tsx):
 * - user vs assistant alignment, avatars, timestamp + model badge
 * - workflowData block (steps badge, scheduled badge, name)
 * - action buttons render per type and invoke onActionClick
 * - reasoningTrace renders the ReasoningChain (collapsible)
 * - feedback controls: thumbs up/down, regenerate, comment flow
 * - variants: system message, empty actions, empty reasoning trace
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ChatMessage, ChatMessageData, ChatAction } from '../ChatMessage';

const baseMsg = (overrides: Partial<ChatMessageData> = {}): ChatMessageData => ({
  id: 'm1',
  type: 'assistant',
  content: 'Hello world',
  timestamp: new Date('2024-06-01T10:30:00'),
  ...overrides,
});

describe('ChatMessage user/assistant variants', () => {
  it('renders a user message right-aligned with a user avatar', () => {
    const { container } = render(
      <ChatMessage message={baseMsg({ type: 'user' })} onActionClick={jest.fn()} />
    );

    expect(screen.getByText('Hello world')).toBeInTheDocument();
    const row = container.querySelector('.justify-end');
    expect(row).toBeInTheDocument();
    // User avatar fallback icon (User) renders
    expect(row!.querySelector('svg.lucide-user')).toBeInTheDocument();
  });

  it('renders an assistant message left-aligned with a bot avatar and no user avatar', () => {
    const { container } = render(
      <ChatMessage message={baseMsg()} onActionClick={jest.fn()} />
    );

    const row = container.querySelector('.justify-start');
    expect(row).toBeInTheDocument();
    expect(row!.querySelector('svg.lucide-bot')).toBeInTheDocument();
    expect(row!.querySelector('svg.lucide-user')).not.toBeInTheDocument();
  });

  it('renders the formatted timestamp for Date and string timestamps', () => {
    const { rerender } = render(
      <ChatMessage message={baseMsg({ timestamp: '2024-06-01T10:30:00' })} onActionClick={jest.fn()} />
    );
    const expected = new Date('2024-06-01T10:30:00').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    expect(screen.getAllByText(expected).length).toBeGreaterThan(0);

    rerender(<ChatMessage message={baseMsg()} onActionClick={jest.fn()} />);
    expect(screen.getAllByText(expected).length).toBeGreaterThan(0);
  });

  it('shows the model badge only for assistant messages', () => {
    const { rerender } = render(
      <ChatMessage message={baseMsg({ model: 'gpt-4o' })} onActionClick={jest.fn()} />
    );
    expect(screen.getByText('gpt-4o')).toBeInTheDocument();

    rerender(
      <ChatMessage message={baseMsg({ type: 'user', model: 'gpt-4o' })} onActionClick={jest.fn()} />
    );
    expect(screen.queryByText('gpt-4o')).not.toBeInTheDocument();
  });

  it('treats system messages as non-user (left aligned)', () => {
    const { container } = render(
      <ChatMessage
        message={baseMsg({ type: 'system', content: 'System notice' })}
        onActionClick={jest.fn()}
        onFeedback={jest.fn()}
      />
    );
    expect(screen.getByText('System notice')).toBeInTheDocument();
    expect(container.querySelector('.justify-start')).toBeInTheDocument();
  });
});

describe('ChatMessage workflowData', () => {
  it('renders steps count, workflow name and scheduled badge', () => {
    render(
      <ChatMessage
        message={baseMsg({
          content: 'Workflow created',
          workflowData: {
            workflowId: 'wf-1',
            workflowName: 'Sales Pipeline',
            stepsCount: 5,
            isScheduled: true,
          },
        })}
        onActionClick={jest.fn()}
      />
    );

    expect(screen.getByText('5 steps')).toBeInTheDocument();
    expect(screen.getByText('Scheduled')).toBeInTheDocument();
    expect(screen.getByText('Sales Pipeline')).toBeInTheDocument();
  });

  it('does not render the scheduled badge when not scheduled', () => {
    render(
      <ChatMessage
        message={baseMsg({
          workflowData: { workflowId: 'wf-2', workflowName: 'Simple', stepsCount: 1 },
        })}
        onActionClick={jest.fn()}
      />
    );

    expect(screen.getByText('1 steps')).toBeInTheDocument();
    expect(screen.queryByText('Scheduled')).not.toBeInTheDocument();
  });

  it('hides workflow data entirely when absent', () => {
    render(<ChatMessage message={baseMsg()} onActionClick={jest.fn()} />);
    expect(screen.queryByText('steps')).not.toBeInTheDocument();
  });
});

describe('ChatMessage actions', () => {
  const actions: ChatAction[] = [
    { type: 'execute', label: 'Run Now', workflowId: 'wf-1' },
    { type: 'schedule', label: 'Schedule' },
    { type: 'send_email', label: 'Email it' },
    { type: 'confirm', label: 'Confirm' },
    { type: 'cancel', label: 'Cancel' },
    { type: 'edit', label: 'Edit' },
    { type: 'create_event', label: 'Add Event' },
    { type: 'view_inbox', label: 'Inbox' },
    { type: 'view_calendar', label: 'Calendar' },
    { type: 'view_template', label: 'Template' },
    { type: 'open_builder', label: 'Builder' },
    { type: 'mystery_type', label: 'Custom' } as any,
  ];

  it('renders an action button per action and invokes onActionClick', () => {
    const onActionClick = jest.fn();
    render(
      <ChatMessage message={baseMsg({ actions: [actions[0], actions[1]] })} onActionClick={onActionClick} />
    );

    fireEvent.click(screen.getByText('Run Now'));
    expect(onActionClick).toHaveBeenCalledWith(actions[0]);

    fireEvent.click(screen.getByText('Schedule'));
    expect(onActionClick).toHaveBeenCalledWith(actions[1]);
    expect(onActionClick).toHaveBeenCalledTimes(2);
  });

  it('renders all known action types without crashing (icon mapping)', () => {
    render(<ChatMessage message={baseMsg({ actions })} onActionClick={jest.fn()} />);
    for (const a of actions) {
      expect(screen.getByText(a.label)).toBeInTheDocument();
    }
  });

  it('renders no footer when actions is empty or undefined', () => {
    const { container, rerender } = render(
      <ChatMessage message={baseMsg({ actions: [] })} onActionClick={jest.fn()} />
    );
    expect(container.querySelector('footer')).toBeNull();

    rerender(<ChatMessage message={baseMsg()} onActionClick={jest.fn()} />);
    expect(container.querySelector('footer')).toBeNull();
  });

  it('does not render actions for error messages', () => {
    render(
      <ChatMessage
        message={baseMsg({ type: 'error', actions: [actions[0]] })}
        onActionClick={jest.fn()}
      />
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('Run Now')).not.toBeInTheDocument();
  });
});

describe('ChatMessage reasoning trace', () => {
  it('renders the ReasoningChain with a collapsed step list', () => {
    render(
      <ChatMessage
        message={baseMsg({
          reasoningTrace: [{ step: 1, thought: 'Analyzing the data' }],
        })}
        onActionClick={jest.fn()}
      />
    );

    expect(screen.getByText('Reasoning Process (1 steps)')).toBeInTheDocument();
    // Steps stay hidden until expanded
    expect(screen.queryByText(/Analyzing the data/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Reasoning Process (1 steps)'));
    expect(screen.getByText('Analyzing the data')).toBeInTheDocument();
    expect(screen.getByText('thought')).toBeInTheDocument();
  });

  it('renders nothing when reasoningTrace is empty', () => {
    render(
      <ChatMessage message={baseMsg({ reasoningTrace: [] })} onActionClick={jest.fn()} />
    );
    expect(screen.queryByText(/Reasoning Process/)).not.toBeInTheDocument();
  });
});

describe('ChatMessage feedback controls', () => {
  it('calls onFeedback thumbs up and thumbs down with the message id', () => {
    const onFeedback = jest.fn();
    render(
      <ChatMessage
        message={baseMsg()}
        onActionClick={jest.fn()}
        onFeedback={onFeedback}
      />
    );

    fireEvent.click(screen.getByLabelText('Thumbs up'));
    expect(onFeedback).toHaveBeenCalledWith('m1', 'thumbs_up');

    fireEvent.click(screen.getByLabelText('Thumbs down'));
    expect(onFeedback).toHaveBeenCalledWith('m1', 'thumbs_down');
  });

  it('calls onRegenerate with the message id', () => {
    const onRegenerate = jest.fn();
    render(
      <ChatMessage
        message={baseMsg()}
        onActionClick={jest.fn()}
        onRegenerate={onRegenerate}
      />
    );

    fireEvent.click(screen.getByLabelText('Regenerate response'));
    expect(onRegenerate).toHaveBeenCalledWith('m1');
  });

  it('submits a comment as thumbs_down feedback with the comment text', () => {
    const onFeedback = jest.fn();
    render(
      <ChatMessage
        message={baseMsg()}
        onActionClick={jest.fn()}
        onFeedback={onFeedback}
      />
    );

    fireEvent.click(screen.getByLabelText('Add comment'));
    const textarea = screen.getByPlaceholderText('What was wrong or how can I improve?');
    fireEvent.change(textarea, { target: { value: 'Too verbose' } });
    fireEvent.click(screen.getByText('Submit'));

    expect(onFeedback).toHaveBeenCalledWith('m1', 'thumbs_down', 'Too verbose');
  });

  it('disables submit while the comment is empty', () => {
    render(
      <ChatMessage
        message={baseMsg()}
        onActionClick={jest.fn()}
        onFeedback={jest.fn()}
      />
    );

    fireEvent.click(screen.getByLabelText('Add comment'));
    expect(screen.getByText('Submit')).toBeDisabled();

    fireEvent.change(
      screen.getByPlaceholderText('What was wrong or how can I improve?'),
      { target: { value: 'x' } }
    );
    expect(screen.getByText('Submit')).toBeEnabled();
  });

  it('cancel closes the comment box and clears the comment', () => {
    render(
      <ChatMessage
        message={baseMsg()}
        onActionClick={jest.fn()}
        onFeedback={jest.fn()}
      />
    );

    fireEvent.click(screen.getByLabelText('Add comment'));
    fireEvent.change(
      screen.getByPlaceholderText('What was wrong or how can I improve?'),
      { target: { value: 'draft' } }
    );
    fireEvent.click(screen.getByText('Cancel'));

    expect(screen.queryByPlaceholderText('What was wrong or how can I improve?')).not.toBeInTheDocument();

    // Re-open: the comment was cleared
    fireEvent.click(screen.getByLabelText('Add comment'));
    expect(screen.getByPlaceholderText('What was wrong or how can I improve?')).toHaveValue('');
  });

  it('renders no feedback controls when both callbacks are absent', () => {
    render(<ChatMessage message={baseMsg()} onActionClick={jest.fn()} />);
    expect(screen.queryByLabelText('Thumbs up')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Thumbs down')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Regenerate response')).not.toBeInTheDocument();
  });

  it('does not show feedback controls for user messages', () => {
    render(
      <ChatMessage
        message={baseMsg({ type: 'user' })}
        onActionClick={jest.fn()}
        onFeedback={jest.fn()}
      />
    );
    expect(screen.queryByLabelText('Thumbs up')).not.toBeInTheDocument();
  });
});

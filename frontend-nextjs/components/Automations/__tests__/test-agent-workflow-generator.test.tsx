/**
 * AgentWorkflowGenerator Component Tests
 *
 * Tests verify the REAL AgentWorkflowGenerator component
 * (components/Automations/AgentWorkflowGenerator.tsx, a DEFAULT export):
 *
 * - Agent list: loading state, governance fetch success (maturity badge,
 *   specialty), empty state, fetch-failure fallback
 * - Agent selection: header (name/description/confidence/capabilities),
 *   "Requires approval" indicator for non-direct-deploy agents
 * - Chat empty state + suggested prompt click filling the prompt input
 * - Generate flow: disabled button without input, POST payload, workflow
 *   preview card (name/description/steps/params), chat history append,
 *   reasoning steps, onWorkflowGenerated contract, input clear, Enter key,
 *   voice transcript input
 * - recurring_automation mode -> requiresApproval -> Submit for Approval UI
 * - Generation failure (non-ok + throw) -> "Generation Failed" toast
 * - Deploy flow: can_deploy direct (onDeployWorkflow + chat msg),
 *   approval path (submit-for-approval POST), catch-path fallbacks for
 *   direct and approval-required agents
 * - Reasoning feedback (thumbs up/down) -> toast + POST /api/reasoning/feedback
 * - Voice On/Off toggle (stops speech when speaking, flips isAutoRead)
 *
 * The VoiceInput and useTextToSpeech are mocked; ReasoningChain and the
 * UI primitives render for real.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import AgentWorkflowGenerator from '../AgentWorkflowGenerator';

jest.mock('@/components/ui/use-toast', () => {
  const mockToast = jest.fn();
  return {
    useToast: (): { toast: jest.Mock; dismiss: jest.Mock; toasts: unknown[] } => ({
      toast: mockToast,
      dismiss: jest.fn(),
      toasts: [],
    }),
    ToastProvider: ({ children }: any) => children,
    __mockToast: mockToast,
  };
});

jest.mock('@/hooks/useTextToSpeech', () => {
  const api: any = {
    speak: jest.fn(),
    stop: jest.fn(),
    isSpeaking: false,
  };
  return { useTextToSpeech: () => api, __testApi: api };
});

jest.mock('@/components/Voice/VoiceInput', () => {
  const React = jest.requireActual('react');
  const api: any = { props: null };
  const MockVoiceInput = (props: any) => {
    api.props = props;
    return React.createElement(
      'button',
      {
        type: 'button',
        'data-testid': 'voice-transcript',
        onClick: () => props.onTranscriptChange('automate my reporting via voice'),
      },
      'Voice'
    );
  };
  return { VoiceInput: MockVoiceInput, __testApi: api };
});

const toastMock = () =>
  (jest.requireMock('@/components/ui/use-toast') as any).__mockToast as jest.Mock;
const ttsApi = () => (jest.requireMock('@/hooks/useTextToSpeech') as any).__testApi;

const jsonResponse = (body: any, ok = true) => ({
  ok,
  status: ok ? 200 : 500,
  json: async () => body,
});

const governanceAgents = [
  {
    agent_id: 'agent-sales',
    name: 'Sales Agent',
    category: 'sales',
    description: 'Closes deals faster',
    maturity_level: 'intern',
    confidence_score: 0.72,
    can_deploy_directly: false,
  },
  {
    agent_id: 'agent-eng',
    name: 'Engineering Agent',
    category: 'engineering',
    description: 'Reviews code',
    maturity_level: 'autonomous',
    confidence_score: 0.96,
    can_deploy_directly: true,
  },
];

const generatedWorkflow = {
  workflow_id: 'wf-42',
  name: 'Lead Qualification Flow',
  description: 'Qualify inbound leads',
  execution_mode: 'manual',
  route_reasoning: 'sales outreach is common',
  nodes: [
    { id: 'n1', name: 'Lead Created', type: 'trigger', metadata: { service: 'crm' } },
    { id: 'n2', name: 'Score Lead', type: 'agent', metadata: { model: 'gpt-4' } },
    { id: 'n3', name: 'Slack Alert', type: 'skill', metadata: {} },
  ],
};

const generatedRecurringWorkflow = {
  ...generatedWorkflow,
  workflow_id: 'wf-43',
  name: 'Nightly Sync',
  execution_mode: 'recurring_automation',
};

describe('AgentWorkflowGenerator', () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(global as any, 'fetch')
      .mockResolvedValue(jsonResponse(governanceAgents));
    toastMock().mockClear();
    ttsApi().speak.mockClear();
    ttsApi().stop.mockClear();
    ttsApi().isSpeaking = false;
    // Agent voice is opt-in and persisted; start each test muted.
    window.localStorage.removeItem('atom_agent_autoread');
  });

  // ------------------------------------------------------------------
  // Agent list
  // ------------------------------------------------------------------
  it('shows the loading state while agents are fetched', () => {
    let resolveGovernance: (r: any) => void;
    fetchSpy.mockImplementationOnce(
      () => new Promise((res) => { resolveGovernance = res; })
    );
    render(<AgentWorkflowGenerator />);

    expect(screen.getByText('Loading agents...')).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith('/api/agent-governance/agents');

    act(() => {
      resolveGovernance!(jsonResponse(governanceAgents));
    });
  });

  it('renders agents with specialty and maturity badges after fetch', async () => {
    render(<AgentWorkflowGenerator />);

    await waitFor(() => {
      expect(screen.getByText('Sales Agent')).toBeInTheDocument();
    });
    expect(screen.getByText('Sales')).toBeInTheDocument(); // specialty
    expect(screen.getByText('Engineering Agent')).toBeInTheDocument();
    expect(screen.getByText('Engineering')).toBeInTheDocument();
    // maturity badges from MATURITY_CONFIG
    expect(screen.getByText('Intern')).toBeInTheDocument();
    expect(screen.getByText('Autonomous')).toBeInTheDocument();
    // the empty-state placeholder must not be present
    expect(screen.queryByText('No agents found.')).not.toBeInTheDocument();
  });

  it('shows the no-agents empty state when the governance fetch fails', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('governance down'));
    render(<AgentWorkflowGenerator />);

    await waitFor(() => {
      expect(screen.getByText('No agents found.')).toBeInTheDocument();
    });
  });

  it('shows the no-agents empty state for an empty governance list', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    render(<AgentWorkflowGenerator />);

    await waitFor(() => {
      expect(screen.getByText('No agents found.')).toBeInTheDocument();
    });
    // agent list badge: agents with an unknown category fall back to default
  });

  // ------------------------------------------------------------------
  // Agent selection header
  // ------------------------------------------------------------------
  it('renders the agent header after selection with confidence and capabilities', async () => {
    render(<AgentWorkflowGenerator />);
    await waitFor(() => {
      expect(screen.getByText('Sales Agent')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Sales Agent'));

    // header shows description + confidence
    expect(screen.getByText('Closes deals faster')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    // capabilities from CATEGORY_CONFIG.sales (first 5)
    expect(screen.getByText('Lead Scoring')).toBeInTheDocument();
    expect(screen.getByText('Email Outreach')).toBeInTheDocument();
    // non-direct-deploy agent shows the approval warning
    expect(screen.getByText('Requires approval')).toBeInTheDocument();
    // chat empty state
    expect(screen.getByText('Tell me what you want to automate')).toBeInTheDocument();
  });

  it('does not show the approval warning for direct-deploy agents', async () => {
    render(<AgentWorkflowGenerator />);
    await waitFor(() => {
      expect(screen.getByText('Engineering Agent')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Engineering Agent'));
    expect(screen.queryByText('Requires approval')).not.toBeInTheDocument();
    expect(screen.getByText('96%')).toBeInTheDocument();
  });

  it('shows the select-an-agent placeholder before any agent is chosen', async () => {
    render(<AgentWorkflowGenerator />);
    await waitFor(() => {
      expect(screen.getByText('Select an Agent')).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // Suggested prompts
  // ------------------------------------------------------------------
  it('fills the prompt input from a suggested prompt', async () => {
    render(<AgentWorkflowGenerator />);
    await waitFor(() => {
      expect(screen.getByText('Sales Agent')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Sales Agent'));

    fireEvent.click(screen.getByText('Qualify new leads'));
    expect(
      (screen.getByPlaceholderText('Describe the automation you want to create...') as HTMLInputElement).value
    ).toBe('Qualify new leads');
  });

  // ------------------------------------------------------------------
  // Generate workflow
  // ------------------------------------------------------------------
  const selectSalesAgent = async () => {
    await waitFor(() => {
      expect(screen.getByText('Sales Agent')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Sales Agent'));
  };

  const typePrompt = (text: string) => {
    fireEvent.change(
      screen.getByPlaceholderText('Describe the automation you want to create...'),
      { target: { value: text } }
    );
  };

  // The generate button is icon-only (lucide-sparkles), so it has no
  // accessible name; locate the icon that lives inside a button (the
  // empty-chat state also renders a decorative Sparkles icon).
  const getGenerateButton = () => {
    const btn = [...document.querySelectorAll('.lucide-sparkles')]
      .map((el) => el.closest('button'))
      .find(Boolean)!;
    return btn;
  };

  const clickGenerate = () => {
    fireEvent.click(getGenerateButton());
  };

  it('generates a workflow and renders the preview card with steps', async () => {
    const onWorkflowGenerated = jest.fn();
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    render(
      <AgentWorkflowGenerator onWorkflowGenerated={onWorkflowGenerated} />
    );
    await selectSalesAgent();

    typePrompt('qualify new leads');
    clickGenerate();

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/workflows/generate-from-agent',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ prompt: 'qualify new leads', tenant_id: 'default' }),
        })
      );
    });
    // workflow preview card
    await waitFor(() => {
      expect(screen.getByText('Lead Qualification Flow')).toBeInTheDocument();
    });
    expect(screen.getByText('Qualify inbound leads')).toBeInTheDocument();
    expect(screen.getByText('95% match')).toBeInTheDocument();
    // steps: action names + type labels
    expect(screen.getByText('Lead Created')).toBeInTheDocument();
    expect(screen.getByText('Score Lead')).toBeInTheDocument();
    expect(screen.getByText('Slack Alert')).toBeInTheDocument();
    expect(screen.getByText(/TRIGGER •/)).toBeInTheDocument();
    expect(screen.getByText(/AGENT •/)).toBeInTheDocument();
    // manual mode -> Deploy Workflow button
    expect(
      screen.getByRole('button', { name: /deploy workflow/i })
    ).toBeInTheDocument();
    // user + agent chat messages
    expect(screen.getByText('qualify new leads')).toBeInTheDocument();
    expect(screen.getByText(/I've analyzed your request/)).toBeInTheDocument();
    // reasoning steps from the mocked visual progress
    expect(screen.getByText('Agent Reasoning Process')).toBeInTheDocument();
    // ReasoningChain starts collapsed; expand to reveal the steps
    fireEvent.click(screen.getByText('Reasoning Process (5 steps)'));
    await waitFor(() => {
      expect(screen.getByText(/Routing: sales outreach is common/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Blueprint generated: Lead Qualification Flow/)).toBeInTheDocument();
    // input cleared after generation
    expect(
      (screen.getByPlaceholderText('Describe the automation you want to create...') as HTMLInputElement).value
    ).toBe('');
    expect(onWorkflowGenerated).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'wf-42',
        name: 'Lead Qualification Flow',
        steps: expect.arrayContaining([
          expect.objectContaining({ id: 'n1', action: 'Lead Created', type: 'trigger' }),
        ]),
      })
    );
  });

  it('speaks the agent response when auto-read is enabled', async () => {
    // Agent voice is opt-in: the persisted preference turns it on.
    window.localStorage.setItem('atom_agent_autoread', '1');
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    render(<AgentWorkflowGenerator />);
    await selectSalesAgent();
    typePrompt('qualify new leads');
    clickGenerate();

    await waitFor(() => {
      expect(ttsApi().speak).toHaveBeenCalledWith(
        expect.stringContaining('I\'ve analyzed your request')
      );
    });
  });

  it('treats recurring_automation workflows as requiring approval', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedRecurringWorkflow));
    render(<AgentWorkflowGenerator />);
    await selectSalesAgent();
    typePrompt('sync nightly');
    clickGenerate();

    await waitFor(() => {
      expect(screen.getByText('Nightly Sync')).toBeInTheDocument();
    });
    // approval UI instead of direct deploy
    expect(
      screen.getByRole('button', { name: /submit for approval/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/A team lead or admin must approve this workflow/)
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /deploy workflow/i })).not.toBeInTheDocument();
  });

  it('toasts Generation Failed when the generate API is not ok', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false));
    render(<AgentWorkflowGenerator />);
    await selectSalesAgent();
    typePrompt('do the thing');
    clickGenerate();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Generation Failed',
          description: 'Failed to generate workflow',
          variant: 'destructive',
        })
      );
    });
  });

  it('toasts Generation Failed when the generate request throws', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockRejectedValueOnce(new Error('network down'));
    render(<AgentWorkflowGenerator />);
    await selectSalesAgent();
    typePrompt('do the thing');
    clickGenerate();

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Generation Failed',
          description: 'network down',
          variant: 'destructive',
        })
      );
    });
  });

  it('ignores generate clicks without a prompt or agent', async () => {
    render(<AgentWorkflowGenerator />);
    await waitFor(() => {
      expect(screen.getByText('Select an Agent')).toBeInTheDocument();
    });
    // no generate button until an agent is selected
    expect(
      [...document.querySelectorAll('.lucide-sparkles')].some(
        (el) => el.closest('button') !== null
      )
    ).toBe(false);
    expect(fetchSpy).not.toHaveBeenCalledWith(
      '/api/v1/workflows/generate-from-agent',
      expect.anything()
    );

    // with an agent selected but an empty prompt, the button stays disabled
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    await selectSalesAgent();
    expect(getGenerateButton()).toBeDisabled();
    expect(fetchSpy).not.toHaveBeenCalledWith(
      '/api/v1/workflows/generate-from-agent',
      expect.anything()
    );
  });

  it('generates on Enter key and via the voice transcript', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    render(<AgentWorkflowGenerator />);
    await selectSalesAgent();

    // Enter key path
    typePrompt('via enter');
    fireEvent.keyDown(
      screen.getByPlaceholderText('Describe the automation you want to create...'),
      { key: 'Enter' }
    );
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/workflows/generate-from-agent',
        expect.anything()
      );
    });

    // voice transcript path sets the prompt from the VoiceInput mock
    fireEvent.click(screen.getByTestId('voice-transcript'));
    expect(
      (screen.getByPlaceholderText('Describe the automation you want to create...') as HTMLInputElement).value
    ).toBe('automate my reporting via voice');
  });

  // ------------------------------------------------------------------
  // Deploy flow
  // ------------------------------------------------------------------
  const generateWorkflow = async (agent: 'sales' | 'eng' = 'sales') => {
    if (agent === 'sales') {
      await selectSalesAgent();
    } else {
      await waitFor(() => {
        expect(screen.getByText('Engineering Agent')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText('Engineering Agent'));
    }
    typePrompt('build it');
    clickGenerate();
    await waitFor(() => {
      expect(screen.getByText('Lead Qualification Flow')).toBeInTheDocument();
    });
  };

  it('deploys directly when the backend approves', async () => {
    const onDeployWorkflow = jest.fn();
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    fetchSpy.mockResolvedValueOnce(jsonResponse({ can_deploy: true }));
    render(
      <AgentWorkflowGenerator onDeployWorkflow={onDeployWorkflow} />
    );
    await generateWorkflow('eng');

    fireEvent.click(screen.getByRole('button', { name: /deploy workflow/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/agent-governance/check-deployment',
        expect.objectContaining({ method: 'POST' })
      );
    });
    const deployBody = JSON.parse(
      fetchSpy.mock.calls.find(
        ([url]: any) => url === '/api/agent-governance/check-deployment'
      )![1].body
    );
    expect(deployBody).toMatchObject({
      agent_id: 'agent-eng',
      workflow_name: 'Lead Qualification Flow',
      workflow_definition: { id: 'wf-42', name: 'Lead Qualification Flow' },
      trigger_type: 'manual',
      actions: ['Lead Created', 'Score Lead', 'Slack Alert'],
      requested_by: 'current-user',
    });
    expect(onDeployWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'wf-42', name: 'Lead Qualification Flow' })
    );
    // chat message confirms the deployment
    await waitFor(() => {
      expect(screen.getByText(/I've deployed the workflow "Lead Qualification Flow"/)).toBeInTheDocument();
    });
  });

  it('submits for approval when the backend requires it', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    fetchSpy.mockResolvedValueOnce(jsonResponse({ can_deploy: false }));
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ message: 'Your request was queued.' })
    );
    render(<AgentWorkflowGenerator />);
    await generateWorkflow();

    fireEvent.click(screen.getByRole('button', { name: /deploy workflow/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/agent-governance/submit-for-approval',
        expect.objectContaining({ method: 'POST' })
      );
    });
    const submitBody = JSON.parse(
      fetchSpy.mock.calls.find(
        ([url]: any) => url === '/api/agent-governance/submit-for-approval'
      )![1].body
    );
    expect(submitBody).toMatchObject({
      agent_id: 'agent-sales',
      workflow_name: 'Lead Qualification Flow',
      trigger_type: 'manual',
      actions: ['Lead Created', 'Score Lead', 'Slack Alert'],
      requested_by: 'current-user',
    });
    await waitFor(() => {
      expect(screen.getByText(/submitted the workflow "Lead Qualification Flow" for approval. Your request was queued\./)).toBeInTheDocument();
    });
  });

  it('falls back to local deploy when the check-deployment request throws', async () => {
    const onDeployWorkflow = jest.fn();
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    fetchSpy.mockRejectedValueOnce(new Error('governance down'));
    render(
      <AgentWorkflowGenerator onDeployWorkflow={onDeployWorkflow} />
    );
    await generateWorkflow('eng');

    fireEvent.click(screen.getByRole('button', { name: /deploy workflow/i }));

    await waitFor(() => {
      expect(onDeployWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'wf-42' })
      );
    });
    expect(screen.getByText(/I've deployed the workflow "Lead Qualification Flow"/)).toBeInTheDocument();
  });

  it('falls back to the approval message when the check throws and the agent cannot deploy directly', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    fetchSpy.mockRejectedValueOnce(new Error('governance down'));
    render(<AgentWorkflowGenerator />);
    await generateWorkflow();

    fireEvent.click(screen.getByRole('button', { name: /deploy workflow/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/This workflow requires approval. I've submitted it for review by a team lead\./)
      ).toBeInTheDocument();
    });
  });

  // ------------------------------------------------------------------
  // Reasoning feedback
  // ------------------------------------------------------------------
  it('sends reasoning feedback and toasts', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(governanceAgents));
    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    render(<AgentWorkflowGenerator />);
    await selectSalesAgent();
    typePrompt('build it');
    clickGenerate();

    await waitFor(() => {
      expect(screen.getByText('Agent Reasoning Process')).toBeInTheDocument();
    });

    // ReasoningChain starts collapsed; expand it to expose the feedback buttons
    fireEvent.click(screen.getByText('Reasoning Process (5 steps)'));

    // first reasoning step: thumbs up (ReasoningChain records feedback itself
    // when no onFeedback prop is wired)
    const thumbsUp = document.querySelector('.lucide-thumbs-up')!.closest('button')!;
    fireEvent.click(thumbsUp);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/reasoning/feedback',
        expect.objectContaining({ method: 'POST' })
      );
    });
    const feedbackBody = JSON.parse(
      fetchSpy.mock.calls.find(
        ([url]: any) => url === '/api/reasoning/feedback'
      )![1].body
    );
    expect(feedbackBody).toMatchObject({
      step_index: 0,
      feedback_type: 'thumbs_up',
      step_content: { content: 'Routing: sales outreach is common' },
    });
    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Feedback Recorded' })
      );
    });
  });

  // ------------------------------------------------------------------
  // Voice toggle
  // ------------------------------------------------------------------
  it('toggles the agent voice and stops speech when muting', async () => {
    // Voice ships muted (opt-in): the toggle first enables it.
    const { rerender } = render(<AgentWorkflowGenerator />);
    await selectSalesAgent();

    expect(screen.getByTitle('Enable Agent Voice')).toBeInTheDocument();
    expect(screen.getByText('Voice Off')).toBeInTheDocument();

    fireEvent.click(screen.getByTitle('Enable Agent Voice'));
    expect(screen.getByTitle('Mute Agent Voice')).toBeInTheDocument();
    expect(screen.getByText('Voice On')).toBeInTheDocument();
    expect(ttsApi().stop).not.toHaveBeenCalled();

    // with speech active, muting stops the current utterance; re-render so
    // the click handler closure picks up the fresh isSpeaking value
    ttsApi().isSpeaking = true;
    rerender(<AgentWorkflowGenerator />);
    fireEvent.click(screen.getByTitle('Mute Agent Voice'));
    expect(ttsApi().stop).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Voice Off')).toBeInTheDocument();
  });

  it('does not speak when auto-read is disabled', async () => {
    // Default state: voice off — nothing is spoken even after a run.
    render(<AgentWorkflowGenerator />);
    await selectSalesAgent();
    expect(screen.getByTitle('Enable Agent Voice')).toBeInTheDocument();

    fetchSpy.mockResolvedValueOnce(jsonResponse(generatedWorkflow));
    typePrompt('quiet build');
    clickGenerate();

    await waitFor(() => {
      expect(screen.getByText('Lead Qualification Flow')).toBeInTheDocument();
    });
    expect(ttsApi().speak).not.toHaveBeenCalled();
  });
});

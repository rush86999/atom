/**
 * Stock workflow launch receipts.
 *
 * The stock `htn_invoice_followup` workflow returns a small receipt alongside
 * the execution id:
 *
 *   { execution_id, state, next_action, run_id? }
 *
 * Anything outside that shape (or an unrecognized state/next_action pairing)
 * must be presented as unconfirmed rather than guessed at.
 */

export const HTN_INVOICE_FOLLOWUP_WORKFLOW_ID = 'htn_invoice_followup';

export type WorkflowLaunchReceiptKind =
    | 'awaiting_review'
    | 'attached'
    | 'terminal'
    | 'unconfirmed';

export type WorkflowLaunchOutcome =
    | 'completed'
    | 'failed'
    | 'cancelled'
    | 'partial';

export interface WorkflowLaunchReceipt {
    kind: WorkflowLaunchReceiptKind;
    confirmed: boolean;
    executionId: string | null;
    state: string | null;
    nextAction: string | null;
    runId: string | null;
    outcome: WorkflowLaunchOutcome | null;
    /** Present only for an attached receipt with a usable run id. */
    assignmentHref: string | null;
    /** Stock receipts are terminal/actionable; none of them need generic polling. */
    shouldPoll: boolean;
    title: string;
    description: string;
}

const asNonEmptyString = (value: unknown): string | null =>
    typeof value === 'string' && value.trim().length > 0
        ? value.trim()
        : null;

const TERMINAL_STATES: Record<
    string,
    { outcome: WorkflowLaunchOutcome; title: string }
> = {
    completed: { outcome: 'completed', title: 'Workflow Completed' },
    success: { outcome: 'completed', title: 'Workflow Completed' },
    succeeded: { outcome: 'completed', title: 'Workflow Completed' },
    failed: { outcome: 'failed', title: 'Workflow Failed' },
    error: { outcome: 'failed', title: 'Workflow Failed' },
    cancelled: { outcome: 'cancelled', title: 'Workflow Cancelled' },
    canceled: { outcome: 'cancelled', title: 'Workflow Cancelled' },
    terminated: { outcome: 'cancelled', title: 'Workflow Terminated' },
    timed_out: { outcome: 'failed', title: 'Workflow Timed Out' },
    partial: { outcome: 'partial', title: 'Workflow Partially Completed' },
};

const isTerminalState = (state: string): state is keyof typeof TERMINAL_STATES =>
    Object.prototype.hasOwnProperty.call(TERMINAL_STATES, state);

export const isHtnInvoiceFollowupWorkflow = (...ids: unknown[]): boolean =>
    ids.some(
        (id) =>
            typeof id === 'string'
            && id.trim().toLowerCase() === HTN_INVOICE_FOLLOWUP_WORKFLOW_ID
    );

const unconfirmedReceipt = (
    executionId: string | null,
    state: string | null
): WorkflowLaunchReceipt => ({
    kind: 'unconfirmed',
    confirmed: false,
    executionId,
    state,
    nextAction: null,
    runId: null,
    outcome: null,
    assignmentHref: null,
    shouldPoll: false,
    title: 'Unconfirmed',
    description: executionId
        ? `Execution ${executionId} was recorded, but the launch receipt could not be confirmed.`
        : 'The launch response could not be confirmed.',
});

export const parseWorkflowLaunchReceipt = (
    data: unknown
): WorkflowLaunchReceipt => {
    if (data === null || typeof data !== 'object' || Array.isArray(data)) {
        return unconfirmedReceipt(null, null);
    }

    const payload = data as Record<string, unknown>;
    const executionId = asNonEmptyString(payload.execution_id);
    const stateValue = asNonEmptyString(payload.state);
    const nextActionValue = asNonEmptyString(payload.next_action);
    const runId = asNonEmptyString(payload.run_id);

    // The receipt contract requires all three fields; run_id is optional
    // except when the state is attached.
    if (!executionId || !stateValue || !nextActionValue) {
        return unconfirmedReceipt(executionId, stateValue);
    }

    const state = stateValue.trim().toLowerCase();
    const nextAction = nextActionValue.trim().toLowerCase();

    if (state === 'paused' && nextAction === 'review') {
        return {
            kind: 'awaiting_review',
            confirmed: true,
            executionId,
            state,
            nextAction,
            runId,
            outcome: null,
            assignmentHref: null,
            shouldPoll: false,
            title: 'Awaiting review',
            description: `Execution ${executionId} is paused and awaiting review.`,
        };
    }

    // An attached receipt must carry the wait action and a usable run ID;
    // otherwise there is nothing concrete to attach the launch to.
    if (state === 'attached' && nextAction === 'wait' && runId) {
        return {
            kind: 'attached',
            confirmed: true,
            executionId,
            state,
            nextAction,
            runId,
            outcome: null,
            assignmentHref: `/assignments?run=${encodeURIComponent(runId)}`,
            shouldPoll: false,
            title: 'Assignment attached',
            description: `Execution ${executionId} is attached to run ${runId}.`,
        };
    }

    // Terminal receipts must explicitly report "none" as their next action.
    if (isTerminalState(state) && nextAction === 'none') {
        const terminal = TERMINAL_STATES[state];
        return {
            kind: 'terminal',
            confirmed: true,
            executionId,
            state,
            nextAction,
            runId,
            outcome: terminal.outcome,
            assignmentHref: null,
            shouldPoll: false,
            title: terminal.title,
            description: `Execution ${executionId} — status: ${state}`,
        };
    }

    return unconfirmedReceipt(executionId, state);
};

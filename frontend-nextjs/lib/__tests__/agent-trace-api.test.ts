/**
 * agent-trace-api — the reasoning/feedback submission contract.
 *
 * The canvas thumbs/note loop and the AgentWorkspace step feedback both go
 * through submitStepFeedback. The POST opts out of the shared axios retry
 * interceptor: retrying timeouts up to 4× held the UI ~47s behind a stalled
 * backend before surfacing an error, and a late 200 arriving after the
 * client had aborted recorded feedback the UI had already reported as
 * failed. First-attempt outcome only — retry is the user's decision.
 */
const postMock = jest.fn();
jest.mock("@/lib/api-client", () => ({
    apiClient: { post: (...args: unknown[]) => postMock(...args) },
}));

import { submitStepFeedback } from "../agent-trace-api";

describe("submitStepFeedback", () => {
    it("posts the feedback payload to /api/reasoning/feedback", async () => {
        postMock.mockResolvedValue({ data: { id: "fb-1" } });

        await submitStepFeedback({
            agentId: "agent-1",
            runId: "canvas",
            stepIndex: -1,
            stepContent: { input_summary: "hi", canvas_id: "c-1" },
            feedbackType: "thumbs_down",
            comment: "make it shorter",
        });

        const [url, body] = postMock.mock.calls[0];
        expect(url).toBe("/api/reasoning/feedback");
        expect(body).toMatchObject({
            agent_id: "agent-1",
            run_id: "canvas",
            step_index: -1,
            feedback_type: "thumbs_down",
            comment: "make it shorter",
        });
    });

    it("opts out of the silent retry interceptor", async () => {
        postMock.mockResolvedValue({ data: {} });

        await submitStepFeedback({
            agentId: "agent-1",
            runId: "canvas",
            stepIndex: -1,
            stepContent: {},
            feedbackType: "thumbs_up",
        });

        const config = postMock.mock.calls[0][2];
        expect(config).toEqual({ retry: false });
    });
});

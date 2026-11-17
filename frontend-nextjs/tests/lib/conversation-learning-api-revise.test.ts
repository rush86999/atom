/**
 * Wire contract for the correction helper.
 *
 * The correction must address the same candidate and source thread the
 * reviewer was looking at, and must carry the revision CAS the endpoint
 * requires. A silent body change here would revive the "new candidate for a
 * correction" behavior or lose source identity.
 */
import { apiClient } from "@/lib/api-client";
import {
  getLearningCandidateHistory,
  reviseLearningCandidate,
} from "@/lib/conversation-learning-api";

jest.mock("@/lib/api-client", () => ({
  apiClient: { post: jest.fn(), get: jest.fn() },
}));

const post = apiClient.post as jest.Mock;
const get = apiClient.get as jest.Mock;

describe("reviseLearningCandidate", () => {
  test("posts the correction to the same candidate with source and revision guard", async () => {
    post.mockResolvedValue({
      data: { candidate: {}, review: {}, review_ready: false, blocking: [] },
    });

    await reviseLearningCandidate(
      "thread/1",
      "candidate/1",
      {
        expected_revision: 4,
        expected_status: "promoted",
        proposed_lesson: "Use the corrected workbook.",
        applies_to: ["pricing"],
        reason: "Superseded workbook.",
      },
      "native_chat",
    );

    expect(post).toHaveBeenCalledWith(
      "/api/conversation-learning/candidates/candidate%2F1/revise",
      {
        thread_id: "thread/1",
        source_kind: "native_chat",
        expected_revision: 4,
        expected_status: "promoted",
        proposed_lesson: "Use the corrected workbook.",
        applies_to: ["pricing"],
        reason: "Superseded workbook.",
      },
    );
  });

  test("omits the optional reason when the caller did not supply one", async () => {
    post.mockResolvedValue({
      data: { candidate: {}, review: {}, review_ready: false, blocking: [] },
    });

    await reviseLearningCandidate(
      "thread/1",
      "candidate/1",
      { expected_revision: 2, proposed_lesson: "Correction." },
      "email",
    );

    const body = post.mock.calls[0][1];
    expect(body).toEqual({
      thread_id: "thread/1",
      source_kind: "email",
      expected_revision: 2,
      proposed_lesson: "Correction.",
    });
    expect(body).not.toHaveProperty("reason");
  });
});

describe("getLearningCandidateHistory", () => {
  test("reads the stored history for the exact candidate, thread and page", async () => {
    get.mockResolvedValue({
      data: {
        thread_id: "thread/1",
        candidate_id: "candidate/1",
        events: [],
        coverage: {},
        signatures: { present: false },
        read_only: true,
      },
    });

    await getLearningCandidateHistory(
      "thread/1",
      "candidate/1",
      { limit: 10, offset: 20 },
      "native_chat",
    );

    expect(get).toHaveBeenCalledWith(
      "/api/conversation-learning/candidates/candidate%2F1/history",
      {
        params: {
          thread_id: "thread/1",
          source_kind: "native_chat",
          limit: 10,
          offset: 20,
        },
      },
    );
  });

  test("sends no page parameters for the first page", async () => {
    get.mockResolvedValue({ data: { events: [] } });

    await getLearningCandidateHistory("thread/1", "candidate/1");

    expect(get.mock.calls[0][1]).toEqual({
      params: { thread_id: "thread/1", source_kind: "email" },
    });
  });
});

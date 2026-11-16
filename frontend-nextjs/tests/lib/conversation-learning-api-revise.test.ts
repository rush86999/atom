/**
 * Wire contract for the correction helper.
 *
 * The correction must address the same candidate and source thread the
 * reviewer was looking at, and must carry the revision CAS the endpoint
 * requires. A silent body change here would revive the "new candidate for a
 * correction" behavior or lose source identity.
 */
import { apiClient } from "@/lib/api-client";
import { reviseLearningCandidate } from "@/lib/conversation-learning-api";

jest.mock("@/lib/api-client", () => ({
  apiClient: { post: jest.fn() },
}));

const post = apiClient.post as jest.Mock;

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
      },
    );
  });
});

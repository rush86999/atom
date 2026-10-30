import {
  FALLBACK_PROFILE,
  isRouteEnabled,
  routeCapability,
} from "../product-profile";

describe("core product profile learning surface", () => {
  it("enables the conversation-learning page in the core fallback", () => {
    expect(routeCapability("/learning", FALLBACK_PROFILE.routes)).toBe(
      "learning"
    );
    expect(isRouteEnabled("/learning", FALLBACK_PROFILE)).toBe(true);
    expect(FALLBACK_PROFILE.capabilities.learning.enabled).toBe(true);
  });
});

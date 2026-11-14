import {
  TOTP_CODE_LENGTH,
  isTwoFactorChallenge,
  loginErrorMessage,
  normalizeTotpCode,
} from "../loginChallenge";

describe("loginChallenge", () => {
  describe("isTwoFactorChallenge", () => {
    test("recognises the backend's password-accepted prompt", () => {
      expect(
        isTwoFactorChallenge("Two-factor authentication required")
      ).toBe(true);
      expect(
        isTwoFactorChallenge("  two-factor authentication required.  ")
      ).toBe(true);
    });

    test("uses a structured native flag when one is available", () => {
      expect(isTwoFactorChallenge({ twoFactorRequired: true })).toBe(true);
      expect(isTwoFactorChallenge({ two_factor_required: true })).toBe(true);
      expect(
        isTwoFactorChallenge({ two_factor_required: false })
      ).toBe(false);
    });

    test("treats challenge-scoped error codes as a second-factor signal", () => {
      expect(isTwoFactorChallenge({ code: "TWO_FACTOR_REQUIRED" })).toBe(true);
      expect(isTwoFactorChallenge({ error_code: "invalid_2fa_code" })).toBe(
        true
      );
    });

    test("does not misclassify terminal non-challenge errors", () => {
      expect(
        isTwoFactorChallenge("Two-factor authentication is not configured")
      ).toBe(false);
      expect(isTwoFactorChallenge("Invalid email or password")).toBe(false);
      expect(isTwoFactorChallenge("Failed to connect to server")).toBe(false);
      expect(isTwoFactorChallenge(undefined)).toBe(false);
    });
  });

  describe("loginErrorMessage", () => {
    test("normalises Tauri string rejections", () => {
      expect(loginErrorMessage("Invalid email or password")).toBe(
        "Invalid email or password"
      );
      expect(loginErrorMessage("  ")).toBe("Sign-in failed");
      expect(loginErrorMessage("", "fallback")).toBe("fallback");
    });

    test("normalises Error instances and HTTP error shapes", () => {
      expect(loginErrorMessage(new Error("Network unavailable"))).toBe(
        "Network unavailable"
      );
      expect(loginErrorMessage({ detail: "Too many login attempts" })).toBe(
        "Too many login attempts"
      );
      expect(
        loginErrorMessage({ error: { message: "Unable to verify" } })
      ).toBe("Unable to verify");
    });
  });

  describe("normalizeTotpCode", () => {
    test("keeps only digits and caps the supported length", () => {
      expect(normalizeTotpCode("12 34-56")).toBe("123456");
      expect(normalizeTotpCode("12345678")).toBe("123456");
      expect(normalizeTotpCode("abc")).toBe("");
      expect(normalizeTotpCode("123456").length).toBe(TOTP_CODE_LENGTH);
    });
  });
});

import { useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import {
  TOTP_CODE_LENGTH,
  isTwoFactorChallenge,
  loginErrorMessage,
  normalizeTotpCode,
} from "../loginChallenge";

interface LoginScreenProps {
  /**
   * ``totpCode`` is only supplied on the retry after the server reports that a
   * second factor is required. Password-only accounts keep the two-argument
   * call they had before.
   */
  onLogin: (
    email: string,
    password: string,
    totpCode?: string
  ) => Promise<void>;
}

type LoginStep = "credentials" | "two_factor";

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: "12px",
  marginBottom: "4px",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  background: "#2a2a2a",
  border: "1px solid #444",
  borderRadius: "6px",
  color: "#fff",
  fontSize: "13px",
  boxSizing: "border-box",
};

const secondaryButtonStyle: CSSProperties = {
  width: "100%",
  marginTop: "8px",
  padding: "6px",
  background: "transparent",
  border: "none",
  color: "#9e9e9e",
  fontSize: "12px",
  cursor: "pointer",
};

export default function LoginScreen({ onLogin }: LoginScreenProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [step, setStep] = useState<LoginStep>("credentials");
  const [code, setCode] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const codeInputRef = useRef<HTMLInputElement>(null);

  const normalizedCode = normalizeTotpCode(code);

  useEffect(() => {
    if (step === "two_factor") {
      codeInputRef.current?.focus();
    }
  }, [step]);

  const handleCredentialsSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (isLoading) {
      return;
    }
    setError(null);
    setIsLoading(true);

    try {
      await onLogin(email, password);
    } catch (err: unknown) {
      if (isTwoFactorChallenge(err)) {
        setStep("two_factor");
        setCode("");
      } else {
        setError(loginErrorMessage(err));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleCodeSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (isLoading || normalizedCode.length !== TOTP_CODE_LENGTH) {
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await onLogin(email, password, normalizedCode);
    } catch (err: unknown) {
      // The password was already accepted. Keep the challenge open for a fresh
      // code: a rejected, replayed or expired code must not send the user back
      // to the password form.
      setError(
        loginErrorMessage(err, "Code verification failed. Try again.")
      );
      setCode("");
      codeInputRef.current?.focus();
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    setStep("credentials");
    setCode("");
    setError(null);
  };

  const errorBlock = error ? (
    <div className="error" role="alert" data-testid="login-error">
      {error}
    </div>
  ) : null;

  return (
    <div className="menubar-container">
      <div className="header">
        <h1>Atom Menu Bar</h1>
      </div>

      {step === "two_factor" ? (
        <form onSubmit={handleCodeSubmit}>
          <p
            data-testid="two-factor-prompt"
            style={{
              fontSize: "12px",
              lineHeight: 1.5,
              color: "#bbb",
              marginBottom: "12px",
            }}
          >
            Two-factor authentication is enabled for{" "}
            <strong style={{ color: "#fff" }}>{email}</strong>. Enter the{" "}
            {TOTP_CODE_LENGTH}-digit code from your authenticator app.
          </p>

          <div style={{ marginBottom: "12px" }}>
            <label htmlFor="totp-code" style={labelStyle}>
              Authentication code
            </label>
            <input
              id="totp-code"
              ref={codeInputRef}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]*"
              maxLength={TOTP_CODE_LENGTH}
              value={code}
              onChange={(event) =>
                setCode(normalizeTotpCode(event.target.value))
              }
              disabled={isLoading}
              placeholder="123456"
              required
              style={{ ...inputStyle, letterSpacing: "0.3em" }}
            />
          </div>

          {errorBlock}

          <button
            type="submit"
            disabled={
              isLoading || normalizedCode.length !== TOTP_CODE_LENGTH
            }
            className="button"
            style={{ width: "100%", marginTop: "12px" }}
          >
            {isLoading ? "Verifying..." : "Verify Code"}
          </button>

          <button
            type="button"
            onClick={handleBack}
            disabled={isLoading}
            style={secondaryButtonStyle}
          >
            Back to sign in
          </button>
        </form>
      ) : (
        <form onSubmit={handleCredentialsSubmit}>
          <div style={{ marginBottom: "12px" }}>
            <label htmlFor="login-email" style={labelStyle}>
              Email
            </label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={isLoading}
              placeholder="you@example.com"
              autoComplete="username"
              required
              style={inputStyle}
            />
          </div>

          <div style={{ marginBottom: "12px" }}>
            <label htmlFor="login-password" style={labelStyle}>
              Password
            </label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={isLoading}
              placeholder="••••••••"
              autoComplete="current-password"
              required
              style={inputStyle}
            />
          </div>

          {errorBlock}

          <button
            type="submit"
            disabled={isLoading}
            className="button"
            style={{ width: "100%", marginTop: "12px" }}
          >
            {isLoading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      )}

      <div
        style={{
          marginTop: "16px",
          fontSize: "11px",
          color: "#888",
          textAlign: "center",
        }}
      >
        Atom AI-Powered Automation Platform
      </div>
    </div>
  );
}

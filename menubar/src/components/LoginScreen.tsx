import { useState } from "react";

interface LoginScreenProps {
  onLogin: (email: string, password: string) => Promise<void>;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await onLogin(email, password);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="menubar-container">
      <div className="header">
        <h1>Atom Menu Bar</h1>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "12px" }}>
          <label style={{ display: "block", fontSize: "12px", marginBottom: "4px" }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isLoading}
            placeholder="you@example.com"
            required
            style={{
              width: "100%",
              padding: "8px 12px",
              background: "#2a2a2a",
              border: "1px solid #444",
              borderRadius: "6px",
              color: "#fff",
              fontSize: "13px",
              boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ marginBottom: "12px" }}>
          <label style={{ display: "block", fontSize: "12px", marginBottom: "4px" }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isLoading}
            placeholder="••••••••"
            required
            style={{
              width: "100%",
              padding: "8px 12px",
              background: "#2a2a2a",
              border: "1px solid #444",
              borderRadius: "6px",
              color: "#fff",
              fontSize: "13px",
              boxSizing: "border-box",
            }}
          />
        </div>

        {error && <div className="error">{error}</div>}

        <button
          type="submit"
          disabled={isLoading}
          className="button"
          style={{ width: "100%", marginTop: "12px" }}
        >
          {isLoading ? "Signing in..." : "Sign In"}
        </button>
      </form>

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

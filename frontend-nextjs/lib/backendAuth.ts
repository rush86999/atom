const API_BASE = typeof window !== "undefined"
  ? (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "")
  : (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export type BackendLoginResponse = {
  access_token: string;
  token_type: string;
  two_factor_required?: boolean;
  detail?: string;
};

export async function loginWithBackend(
  email: string,
  password: string,
  totpCode?: string
): Promise<BackendLoginResponse> {
  // Network failures (offline, DNS, connection refused) reject the fetch
  // with a raw TypeError ("Failed to fetch"). Surfacing that verbatim to
  // users is unhelpful — map it to a friendly message instead. The login
  // form renders this error in data-testid="login-error-message".
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        username: email,
        password,
        ...(totpCode ? { totp_code: totpCode } : {}),
      }),
    });
  } catch {
    throw new Error(
      "Unable to connect to the server. Please check your internet connection and try again."
    );
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Invalid email or password");
  }

  if (data.two_factor_required) {
    return data;
  }

  if (!data.access_token) {
    throw new Error("Login response did not include an access token");
  }

  return data;
}

export function persistBackendToken(token: string, email?: string) {
  if (typeof window === "undefined") return;

  localStorage.removeItem("atom_explicit_logout");
  localStorage.setItem("auth_token", token);
  localStorage.setItem("token", token);
  // Sidebar/profile identity fallback for API-first sessions (NextAuth's
  // session stays empty when sign-in bypassed the NextAuth route).
  if (email) localStorage.setItem("user_email", email);
  document.cookie = `auth_token=${token}; path=/; max-age=86400; SameSite=Lax`;
  document.cookie = `next-auth.session-token=${token}; path=/; max-age=86400; SameSite=Lax`;
}

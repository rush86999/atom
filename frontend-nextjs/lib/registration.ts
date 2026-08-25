// Shared registration client — the single source of truth for both register
// funnels (`/auth/signup` and `/login`'s register mode). Keeps error rendering
// and the post-signup auto-login identical everywhere.

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export type RegisterInput = {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
};

export type RegisterResponse = {
  access_token: string;
  token_type: string;
};

// FastAPI 422 validation errors come back as detail: [{loc, msg, type}, ...].
// Rendering that array with String() shows "[object Object]" — map each entry
// to a readable, field-specific sentence instead.
function formatValidationError(items: any[]): string {
  const messages = items
    .filter((item) => item && typeof item === "object")
    .map((item) => {
      const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
      switch (field) {
        case "email":
          return "Please enter a valid email address";
        case "password":
          return item.msg?.includes("72 bytes")
            ? "Password must be at most 72 bytes when UTF-8 encoded"
            : "Password must be 8–128 characters";
        case "first_name":
          return "First name is required (1–100 characters)";
        case "last_name":
          return "Last name is required (1–100 characters)";
        default:
          return typeof item.msg === "string" ? item.msg : "Invalid input";
      }
    });
  return messages.length ? messages.join(". ") : "Please check the form and try again";
}

export function extractApiErrorMessage(
  data: any,
  status?: number,
  response?: Response
): string {
  // Rate-limited: surface the server's Retry-After as a concrete wait time.
  if (status === 429) {
    const retryAfter = Number(response?.headers?.get("Retry-After"));
    if (retryAfter && retryAfter > 0) {
      const minutes = Math.max(1, Math.ceil(retryAfter / 60));
      return `Too many attempts. Please try again in ${minutes} minute${minutes > 1 ? "s" : ""}.`;
    }
    return "Too many attempts. Please try again later.";
  }

  const detail = data?.detail;
  if (Array.isArray(detail)) {
    return formatValidationError(detail);
  }

  const message =
    (typeof detail === "object" && detail?.message) ||
    (typeof detail === "string" && detail) ||
    data?.message ||
    "";

  if (typeof message === "string" && message.length > 0) {
    const lower = message.toLowerCase();
    if (lower.includes("already registered") || lower.includes("already exists")) {
      return "An account with this email already exists. Try signing in instead.";
    }
    return message;
  }

  return "Failed to create account. Please try again.";
}

export async function registerWithBackend(
  input: RegisterInput
): Promise<RegisterResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        email: input.email.trim(),
        password: input.password,
        first_name: input.first_name.trim(),
        last_name: input.last_name.trim(),
      }),
    });
  } catch {
    throw new Error(
      "Unable to connect to the server. Please check your internet connection and try again."
    );
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(extractApiErrorMessage(data, response.status, response));
  }

  if (!data.access_token) {
    throw new Error("Registration response did not include an access token");
  }

  return data;
}

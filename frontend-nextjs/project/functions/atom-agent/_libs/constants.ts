// PostGraphile configuration
export const POSTGRAPHILE_GRAPH_URL =
  process.env.POSTGRAPHILE_GRAPH_URL || "http://localhost:3000/api/graphql";
export const POSTGRAPHILE_ADMIN_SECRET =
  process.env.POSTGRAPHILE_ADMIN_SECRET || "postgraphile_admin_secret";

// Google Calendar configuration
export const ATOM_GOOGLE_CALENDAR_CLIENT_ID =
  process.env.ATOM_GOOGLE_CALENDAR_CLIENT_ID || "";
export const ATOM_GOOGLE_CALENDAR_CLIENT_SECRET =
  process.env.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET || "";

// Zoom configuration
export const ZOOM_PASS_KEY = process.env.ZOOM_PASS_KEY || "zoom_pass_key";
export const ZOOM_IV_FOR_PASS =
  process.env.ZOOM_IV_FOR_PASS || "zoom_iv_for_pass";
export const ZOOM_SALT_FOR_PASS =
  process.env.ZOOM_SALT_FOR_PASS || "zoom_salt_for_pass";

// Scheduler configuration
export const SCHEDULER_API_URL =
  process.env.SCHEDULER_API_URL || "http://localhost:3001";

// Google OAuth configuration
export const GOOGLE_OAUTH_ATOMIC_WEB_REDIRECT_URL =
  process.env.GOOGLE_OAUTH_ATOMIC_WEB_REDIRECT_URL ||
  "http://localhost:3000/api/atom/auth/calendar/callback";

// Default timeouts
export const DEFAULT_API_TIMEOUT_MS = 15000;
export const DEFAULT_RETRY_ATTEMPTS = 3;

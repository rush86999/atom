// API backend helper constants
export const googleClientIdAtomicWeb =
  process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB || "";
export const googleClientSecretAtomicWeb =
  process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB || "";
export const googleOAuthAtomicWebRedirectUrl =
  process.env.GOOGLE_OAUTH_ATOMIC_WEB_REDIRECT_URL ||
  "http://localhost:3000/api/atom/auth/calendar/callback";
export const postgraphileAdminSecret =
  process.env.POSTGRAPHILE_ADMIN_SECRET || "postgraphile_admin_secret";
export const postgraphileGraphUrl =
  process.env.POSTGRAPHILE_GRAPH_URL || "http://localhost:3000/api/graphql";
export const zoomIVForPass = process.env.ZOOM_IV_FOR_PASS || "zoom_iv_for_pass";
export const zoomPassKey = process.env.ZOOM_PASS_KEY || "zoom_pass_key";
export const zoomSaltForPass =
  process.env.ZOOM_SALT_FOR_PASS || "zoom_salt_for_pass";

// Missing constants required by imports
export const SCHEDULER_API_URL =
  process.env.SCHEDULER_API_URL || "http://localhost:3001";

// Apollo GraphQL constants
export const postgraphileDbUrl =
  process.env.POSTGRAPHILE_DB_URL || "http://localhost:3000/api/graphql";
export const postgraphileWSUrl =
  process.env.POSTGRAPHILE_WS_URL || "ws://localhost:3000/api/graphql";
export const HASURA_GRAPHQL_URL =
  process.env.HASURA_GRAPHQL_URL || "http://localhost:8080/v1/graphql";
export const HASURA_ADMIN_SECRET =
  process.env.HASURA_ADMIN_SECRET || "hasura_admin_secret";
export const ATOM_GOOGLE_CALENDAR_CLIENT_ID =
  process.env.ATOM_GOOGLE_CALENDAR_CLIENT_ID || "";
export const ATOM_GOOGLE_CALENDAR_CLIENT_SECRET =
  process.env.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET || "";

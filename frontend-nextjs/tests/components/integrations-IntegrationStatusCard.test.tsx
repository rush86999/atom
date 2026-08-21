/**
 * IntegrationStatusCard (Round 80) — the shared shell used by the new
 * dropbox/telegram/gitlab/xero pages. Verifies:
 * - on mount it fetches the real status endpoint and renders a status chip,
 * - the Connect button redirects to the OAuth URL resolved from the backend
 *   JSON payload (`url` for xero/gitlab, `authorization_url` for dropbox).
 * Keep in its own file (top-level mock conflicts break the pages suite).
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import IntegrationStatusCard from "@/components/integrations/IntegrationStatusCard";

const realFetch = global.fetch;

beforeEach(() => {
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  global.fetch = realFetch;
});

test("fetches status endpoint on mount and shows connected state", async () => {
  global.fetch = jest.fn().mockResolvedValueOnce({
    ok: true,
    json: async () => ({ ok: true, status: "active" }),
  }) as any;
  render(
    <IntegrationStatusCard
      title="Xero"
      statusEndpoint="/api/xero/status"
      connectUrl="/api/xero/auth/url"
      connectUrlIsJson
    />
  );
  await waitFor(() => expect(screen.getByText("active")).toBeInTheDocument());
  expect(global.fetch).toHaveBeenCalledWith("/api/xero/status");
  // connected -> connect button hidden
  expect(screen.queryByRole("button", { name: /connect/i })).not.toBeInTheDocument();
});

test("shows disconnected state with a connect button when status is unknown", async () => {
  global.fetch = jest.fn().mockResolvedValueOnce({
    ok: true,
    json: async () => ({ ok: false, status: "not_configured" }),
  }) as any;
  render(
    <IntegrationStatusCard
      title="GitLab"
      statusEndpoint="/api/gitlab/status"
      connectUrl="/api/gitlab/auth/url"
      connectUrlIsJson
    />
  );
  await waitFor(() => expect(screen.getByRole("button", { name: /connect/i })).toBeInTheDocument());
});

test("resolves url from {url} JSON and redirects", async () => {
  const { resolveConnectUrl } = jest.requireActual<typeof import("@/components/integrations/IntegrationStatusCard")>(
    "@/components/integrations/IntegrationStatusCard"
  );
  const fetchMock = jest
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ url: "https://login.example/oauth" }) }) as any;
  global.fetch = fetchMock;
  render(
    <IntegrationStatusCard
      title="Xero"
      statusEndpoint="/api/xero/status"
      connectUrl="/api/xero/auth/url"
      connectUrlIsJson
    />
  );
  expect(resolveConnectUrl({ url: "https://login.example/oauth" })).toBe("https://login.example/oauth");
  const btn = await screen.findByRole("button", { name: /connect/i });
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ url: "https://login.example/oauth" }),
  });
  fireEvent.click(btn);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/xero/auth/url"));
});

test("resolves authorization_url for dropbox-shaped payloads", async () => {
  const { resolveConnectUrl } = jest.requireActual<typeof import("@/components/integrations/IntegrationStatusCard")>(
    "@/components/integrations/IntegrationStatusCard"
  );
  expect(resolveConnectUrl({ success: true, authorization_url: "https://dropbox.example/oauth" })).toBe(
    "https://dropbox.example/oauth"
  );
  expect(resolveConnectUrl({ success: true, url: "https://both.example/oauth", authorization_url: "https://dropbox.example/oauth" })).toBe(
    "https://both.example/oauth"
  );
  expect(resolveConnectUrl(null)).toBeNull();
  const fetchMock = jest
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ success: false, status: "disconnected" }) }) as any;
  global.fetch = fetchMock;
  render(
    <IntegrationStatusCard
      title="Dropbox"
      statusEndpoint="/api/dropbox/oauth/status"
      connectUrl="/api/dropbox/oauth/url"
      connectUrlIsJson
    />
  );
  const btn = await screen.findByRole("button", { name: /connect/i });
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ success: true, authorization_url: "https://dropbox.example/oauth" }),
  });
  fireEvent.click(btn);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/dropbox/oauth/url"));
});

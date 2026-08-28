/**
 * Round 80 — integration components must attach the stored JWT to same-origin
 * proxy calls. The Next handlers forward that Authorization header to the
 * backend (pages/api/integrations/*), whose data/write endpoints require it.
 *
 * Directly mocks global.fetch and asserts on the headers the component sent.
 */
import React from "react";
import { renderWithProviders, waitFor } from "../../tests/test-utils";

import SlackIntegration from "@/components/SlackIntegration";
import DiscordIntegration from "@/components/DiscordIntegration";

const realFetch = global.fetch;

function jsonResponse(body: any, status = 200) {
  return {
    ok: status < 400,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  jest.spyOn(console, "error").mockImplementation(() => {});
  window.localStorage.setItem("auth_token", "jwt-test-token");
});

afterEach(() => {
  global.fetch = realFetch;
  window.localStorage.clear();
});

test("SlackIntegration sends Bearer token on proxied data calls", async () => {
  const authSeen: string[] = [];
  const fetchMock = jest.fn(((url: any) => {
    const u = String(url);
    if (u.includes("/slack/workspace")) authSeen.push("workspace");
    if (u.includes("/slack/channels")) authSeen.push("channels");
    if (u.includes("/slack/users")) authSeen.push("users");
    if (u.includes("/slack/messages")) authSeen.push("messages");
    if (u.includes("/slack/health"))
      return Promise.resolve(jsonResponse({ status: "healthy" }));
    return Promise.resolve(jsonResponse({ success: true, data: {} }));
  }) as any);
  global.fetch = fetchMock as unknown as typeof global.fetch;

  renderWithProviders(<SlackIntegration />);

  await waitFor(() => expect(authSeen.length).toBeGreaterThan(0));
  // every proxied call the component made carried the stored JWT
  const callsWithHeaders = fetchMock.mock.calls.filter(
    ([, opts]: any[]) => opts && opts.headers && (opts.headers as any).Authorization
  );
  expect(callsWithHeaders.length).toBe(authSeen.length);
  expect((callsWithHeaders[0][1].headers as any).Authorization).toBe(
    "Bearer jwt-test-token"
  );
});

test("DiscordIntegration sends Bearer token on proxied data calls", async () => {
  const authSeen: string[] = [];
  const fetchMock = jest.fn(((url: any) => {
    const u = String(url);
    if (u.includes("/discord/profile")) authSeen.push("profile");
    if (u.includes("/discord/guilds")) authSeen.push("guilds");
    if (u.includes("/discord/health"))
      return Promise.resolve(jsonResponse({ success: true }));
    return Promise.resolve(jsonResponse({}));
  }) as any);
  global.fetch = fetchMock as unknown as typeof global.fetch;

  renderWithProviders(<DiscordIntegration />);

  await waitFor(() => expect(authSeen.length).toBeGreaterThan(0));
  const callsWithHeaders = fetchMock.mock.calls.filter(
    ([, opts]: any[]) => opts && opts.headers && (opts.headers as any).Authorization
  );
  expect(callsWithHeaders.length).toBe(authSeen.length);
  expect((callsWithHeaders[0][1].headers as any).Authorization).toBe(
    "Bearer jwt-test-token"
  );
});

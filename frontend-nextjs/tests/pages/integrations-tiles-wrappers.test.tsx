/**
 * Wrapper integration pages (were 0% coverage)
 *
 * These pages are thin delegations: they render exactly one child integration
 * component imported from @/components. Each child is mocked to a stub with a
 * testid, and the test asserts the page mounts the correct child.
 *
 * Covers: asana, azure, box, discord, freshdesk, github, google-workspace,
 * intercom, jira, linear, mailchimp, microsoft365, notion, outlook,
 * quickbooks, slack, tableau, teams, trello, zendesk, zoom.
 */

import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("@/components/AsanaIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="asana-integration" />,
}));
jest.mock("@/components/AzureIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="azure-integration" />,
}));
jest.mock("@/components/BoxIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="box-integration" />,
}));
jest.mock("@/components/DiscordIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="discord-integration" />,
}));
jest.mock("@/components/FreshdeskIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="freshdesk-integration" />,
}));
jest.mock("@/components/GitHubIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="github-integration" />,
}));
jest.mock("@/components/GoogleWorkspaceIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="google-workspace-integration" />,
}));
jest.mock("@/components/IntercomIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="intercom-integration" />,
}));
jest.mock("@/components/JiraIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="jira-integration" />,
}));
jest.mock("@/components/LinearIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="linear-integration" />,
}));
jest.mock("@/components/MailchimpIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="mailchimp-integration" />,
}));
jest.mock("@/components/Microsoft365Integration", () => ({
  __esModule: true,
  default: () => <div data-testid="microsoft365-integration" />,
}));
jest.mock("@/components/NotionIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="notion-integration" />,
}));
jest.mock("@/components/OutlookIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="outlook-integration" />,
}));
jest.mock("@/components/QuickBooksIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="quickbooks-integration" />,
}));
jest.mock("@/components/SlackIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="slack-integration" />,
}));
jest.mock("@/components/TableauIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="tableau-integration" />,
}));
jest.mock("@/components/TeamsIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="teams-integration" />,
}));
jest.mock("@/components/TrelloIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="trello-integration" />,
}));
jest.mock("@/components/ZendeskIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="zendesk-integration" />,
}));
jest.mock("@/components/ZoomIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="zoom-integration" />,
}));

import AsanaPage from "@/pages/integrations/asana";
import AzurePage from "@/pages/integrations/azure";
import BoxPage from "@/pages/integrations/box";
import DiscordPage from "@/pages/integrations/discord";
import FreshdeskPage from "@/pages/integrations/freshdesk";
import GitHubPage from "@/pages/integrations/github";
import GoogleWorkspacePage from "@/pages/integrations/google-workspace";
import IntercomPage from "@/pages/integrations/intercom";
import JiraPage from "@/pages/integrations/jira";
import LinearPage from "@/pages/integrations/linear";
import MailchimpPage from "@/pages/integrations/mailchimp";
import Microsoft365Page from "@/pages/integrations/microsoft365";
import NotionPage from "@/pages/integrations/notion";
import OutlookPage from "@/pages/integrations/outlook";
import QuickBooksPage from "@/pages/integrations/quickbooks";
import SlackPage from "@/pages/integrations/slack";
import TableauPage from "@/pages/integrations/tableau";
import TeamsPage from "@/pages/integrations/teams";
import TrelloPage from "@/pages/integrations/trello";
import ZendeskPage from "@/pages/integrations/zendesk";
import ZoomPage from "@/pages/integrations/zoom";

describe("integration wrapper pages", () => {
  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  // [page component, child testid]
  const wrappers: [string, React.FC, string][] = [
    ["asana", AsanaPage, "asana-integration"],
    ["azure", AzurePage, "azure-integration"],
    ["box", BoxPage, "box-integration"],
    ["discord", DiscordPage, "discord-integration"],
    ["freshdesk", FreshdeskPage, "freshdesk-integration"],
    ["github", GitHubPage, "github-integration"],
    ["google-workspace", GoogleWorkspacePage, "google-workspace-integration"],
    ["intercom", IntercomPage, "intercom-integration"],
    ["jira", JiraPage, "jira-integration"],
    ["linear", LinearPage, "linear-integration"],
    ["mailchimp", MailchimpPage, "mailchimp-integration"],
    ["microsoft365", Microsoft365Page, "microsoft365-integration"],
    ["notion", NotionPage, "notion-integration"],
    ["outlook", OutlookPage, "outlook-integration"],
    ["quickbooks", QuickBooksPage, "quickbooks-integration"],
    ["slack", SlackPage, "slack-integration"],
    ["tableau", TableauPage, "tableau-integration"],
    ["teams", TeamsPage, "teams-integration"],
    ["trello", TrelloPage, "trello-integration"],
    ["zendesk", ZendeskPage, "zendesk-integration"],
    ["zoom", ZoomPage, "zoom-integration"],
  ];

  test.each(wrappers)("%s renders its integration component", (_name, Page, testid) => {
    const { container, unmount } = render(<Page />);
    expect(screen.getByTestId(testid)).toBeInTheDocument();
    expect(container).toBeInTheDocument();
    unmount();
  });
});

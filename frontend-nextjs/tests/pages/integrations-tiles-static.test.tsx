/**
 * Static integration tile pages (were 0% coverage)
 *
 * Covers the self-contained "coming soon" pages under pages/integrations/:
 *  - airtable.tsx, nextjs.tsx (fully static)
 *  - the *_enhanced.tsx / xero.tsx config-driven tiles (Head + title +
 *    description + Connect button)
 *
 * These pages render no children and make no requests, so no mocks beyond
 * console.error silencing are required.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

import AirtablePage from "@/pages/integrations/airtable";
import NextjsPage from "@/pages/integrations/nextjs";
import AsanaEnhanced from "@/pages/integrations/asana_enhanced";
import BoxEnhanced from "@/pages/integrations/box_enhanced";
import GitlabEnhanced from "@/pages/integrations/gitlab_enhanced";
import GoogleEnhanced from "@/pages/integrations/google_enhanced";
import HubspotEnhanced from "@/pages/integrations/hubspot_enhanced";
import JiraEnhanced from "@/pages/integrations/jira_enhanced";
import LinearEnhanced from "@/pages/integrations/linear_enhanced";
import MicrosoftEnhanced from "@/pages/integrations/microsoft_enhanced";
import NotionEnhanced from "@/pages/integrations/notion_enhanced";
import SalesforceEnhanced from "@/pages/integrations/salesforce_enhanced";
import ShopifyEnhanced from "@/pages/integrations/shopify_enhanced";
import StripeEnhanced from "@/pages/integrations/stripe_enhanced";
import TrelloEnhanced from "@/pages/integrations/trello_enhanced";
import XeroPage from "@/pages/integrations/xero";
import XeroEnhanced from "@/pages/integrations/xero_enhanced";
import ZoomEnhanced from "@/pages/integrations/zoom_enhanced";

describe("static integration tile pages", () => {
  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  describe("airtable", () => {
    test("renders header, description and feature list", () => {
      render(<AirtablePage />);
      expect(screen.getByRole("heading", { name: "Airtable Integration" })).toBeInTheDocument();
      expect(screen.getByText("Connect and manage your Airtable bases")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Airtable Data Management" })).toBeInTheDocument();
      expect(screen.getByText("Airtable integration is coming soon. This page will allow you to:")).toBeInTheDocument();
      expect(screen.getByText("• Connect to your Airtable bases")).toBeInTheDocument();
      expect(screen.getByText("• View and manage tables and records")).toBeInTheDocument();
      expect(screen.getByText("• Sync data between Airtable and other services")).toBeInTheDocument();
      expect(screen.getByText("• Create automated workflows with Airtable data")).toBeInTheDocument();
    });
  });

  describe("nextjs", () => {
    test("renders header, description and feature list", () => {
      render(<NextjsPage />);
      expect(screen.getByRole("heading", { name: /Next\.js Integration/i })).toBeInTheDocument();
      expect(
        screen.getByText(/Next\.js and Vercel integration is coming soon/i)
      ).toBeInTheDocument();
      expect(screen.getByText("Deploy and manage Next.js applications")).toBeInTheDocument();
      expect(screen.getByText("Monitor Vercel deployments and performance")).toBeInTheDocument();
      expect(screen.getByText("Configure environment variables and domains")).toBeInTheDocument();
      expect(screen.getByText("View build logs and analytics")).toBeInTheDocument();
      expect(screen.getByText("Integrate with CI/CD pipelines")).toBeInTheDocument();
      expect(
        screen.getByText("Check back soon for updates on Next.js integration features.")
      ).toBeInTheDocument();
    });
  });

  // [tile name, page, heading, description, connect-button label]
  const enhancedTiles: [string, React.FC, RegExp, string, string][] = [
    ["asana_enhanced", AsanaEnhanced, /Asana Enhanced Integration/, "Enterprise integration for Asana services", "Connect Asana"],
    ["box_enhanced", BoxEnhanced, /Box Enhanced Integration/, "Enterprise integration for Box services", "Connect Box"],
    ["gitlab_enhanced", GitlabEnhanced, /GitLab Enhanced Integration/, "Enterprise integration for GitLab services", "Connect GitLab"],
    ["google_enhanced", GoogleEnhanced, /Google Enhanced Integration/, "Enterprise integration for Google services", "Connect Google"],
    ["hubspot_enhanced", HubspotEnhanced, /HubSpot Enhanced Integration/, "Enterprise integration for HubSpot services", "Connect HubSpot"],
    ["jira_enhanced", JiraEnhanced, /Jira Enhanced Integration/, "Enterprise integration for Jira services", "Connect Jira"],
    ["linear_enhanced", LinearEnhanced, /Linear Enhanced Integration/, "Enterprise integration for Linear services", "Connect Linear"],
    ["microsoft_enhanced", MicrosoftEnhanced, /Microsoft Enhanced Integration/, "Enterprise integration for Microsoft services", "Connect Microsoft"],
    ["notion_enhanced", NotionEnhanced, /Notion Enhanced Integration/, "Enterprise integration for Notion services", "Connect Notion"],
    ["salesforce_enhanced", SalesforceEnhanced, /Salesforce Enhanced Integration/, "Enterprise integration for Salesforce services", "Connect Salesforce"],
    ["shopify_enhanced", ShopifyEnhanced, /Shopify Enhanced Integration/, "Enterprise integration for Shopify services", "Connect Shopify"],
    ["stripe_enhanced", StripeEnhanced, /Stripe Enhanced Integration/, "Enterprise integration for Stripe services", "Connect Stripe"],
    ["trello_enhanced", TrelloEnhanced, /Trello Enhanced Integration/, "Enterprise integration for Trello services", "Connect Trello"],
    ["xero_enhanced", XeroEnhanced, /Xero Enhanced Integration/, "Enterprise integration for Xero services", "Connect Xero"],
    ["zoom_enhanced", ZoomEnhanced, /Zoom Enhanced Integration/, "Enterprise integration for Zoom services", "Connect Zoom"],
  ];

  describe.each(enhancedTiles)("tile %s", (_name, Page, heading, description, connectLabel) => {
    test("renders heading, description and connect button that accepts clicks", () => {
      const { unmount } = render(<Page />);
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
      expect(screen.getByText(description)).toBeInTheDocument();
      const button = screen.getByRole("button", { name: connectLabel });
      expect(button).toBeInTheDocument();
      fireEvent.click(button); // no-op handler, just exercises the element
      unmount();
    });
  });

  describe("xero", () => {
    test("renders live status card heading, accounting description and connect button", () => {
      render(<XeroPage />);
      expect(screen.getByRole("heading", { name: "Xero" })).toBeInTheDocument();
      expect(
        screen.getByText(/Invoices, contacts and bank accounts your agents can reconcile/)
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Connect Xero" })).toBeInTheDocument();
    });
  });
});

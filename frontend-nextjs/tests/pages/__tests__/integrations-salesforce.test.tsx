import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import SalesforceIntegration from "@/pages/integrations/salesforce";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const PROFILE = {
  id: "u-1",
  Name: "System Administrator",
  Title: "Salesforce Admin",
  Email: "admin@salesforce.com",
};

const LEADS = [
  {
    id: "lead-1",
    FirstName: "Ada",
    LastName: "Lovelace",
    Email: "ada@analytical.com",
    Phone: "555-0101",
    Company: "Analytical Engines",
    Status: "Open - Not Contacted",
    IsConverted: false,
    Owner: { Name: "Rushi" },
  },
  {
    id: "lead-2",
    FirstName: "Grace",
    LastName: "Hopper",
    Email: "grace@navy.mil",
    Phone: "555-0102",
    Company: "US Navy",
    Status: "Qualified",
    IsConverted: true,
    Owner: { Name: "Rushi" },
  },
];

const OPPORTUNITIES = [
  {
    id: "opp-1",
    Name: "Big Enterprise Deal",
    AccountName: "Acme Corp",
    Amount: 100000,
    StageName: "Prospecting",
    IsClosed: false,
    CloseDate: "2026-12-31",
  },
  {
    id: "opp-2",
    Name: "Expansion",
    AccountName: "Globex",
    Amount: 250000,
    StageName: "Closed Won",
    IsClosed: true,
    CloseDate: "2026-06-30",
  },
];

const ACCOUNTS = [
  { id: "acc-1", Name: "Acme Corp", Type: "Customer", Industry: "Technology", Phone: "555-1000", Website: "https://acme.example.com", Owner: { Name: "Rushi" } },
  { id: "acc-2", Name: "Globex", Type: "Partner", Industry: "Retail", Phone: "555-2000", Website: null, Owner: { Name: "Rushi" } },
];

const CONTACTS = [
  { id: "c-1", FirstName: "Alan", LastName: "Turing", Email: "alan@acme.example.com", AccountName: "Acme Corp", Owner: { Name: "Rushi" } },
];

const CASES = [
  { id: "cs-1", CaseNumber: "00001111", Subject: "Login issue", Status: "New", Priority: "High", AccountName: "Acme Corp", Owner: { Name: "Rushi" }, Comments: [] },
  { id: "cs-2", CaseNumber: "00002222", Subject: "Closed billing", Status: "Closed", Priority: "Low", ClosedDate: "2026-01-01", Owner: { Name: "Rushi" }, Comments: [] },
];

const USERS = [
  { id: "usr-1", Name: "Rushi Parikh", Email: "rushi@atom.ai", Title: "Engineer", IsActive: true },
  { id: "usr-2", Name: "Grace Hopper", Email: "grace@navy.mil", Title: "Rear Admiral", IsActive: false },
];

function okResponse(body: any) {
  return { ok: true, json: async () => body };
}

function errResponse(status: number) {
  return { ok: false, status, json: async () => ({}) };
}

describe("SalesforceIntegration", () => {
  const mockFetch = jest.fn();
  const mockToast = jest.fn();

  const setupConnectedMocks = () => {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url.includes("/salesforce/health")) return Promise.resolve(okResponse({ status: "healthy" }));
      if (url.includes("/salesforce/profile")) return Promise.resolve(okResponse({ data: { profile: PROFILE } }));
      if (url.includes("/salesforce/leads/create")) return Promise.resolve(okResponse({ data: { lead: {} } }));
      if (url.includes("/salesforce/leads")) return Promise.resolve(okResponse({ data: { leads: LEADS } }));
      if (url.includes("/salesforce/opportunities/create")) return Promise.resolve(okResponse({ data: { opportunity: {} } }));
      if (url.includes("/salesforce/opportunities")) return Promise.resolve(okResponse({ data: { opportunities: OPPORTUNITIES } }));
      if (url.includes("/salesforce/accounts/create")) return Promise.resolve(okResponse({ data: { account: {} } }));
      if (url.includes("/salesforce/accounts")) return Promise.resolve(okResponse({ data: { accounts: ACCOUNTS } }));
      if (url.includes("/salesforce/contacts")) return Promise.resolve(okResponse({ data: { contacts: CONTACTS } }));
      if (url.includes("/salesforce/cases")) return Promise.resolve(okResponse({ data: { cases: CASES } }));
      if (url.includes("/salesforce/users")) return Promise.resolve(okResponse({ data: { users: USERS } }));
      return Promise.resolve(errResponse(404));
    });
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    global.fetch = mockFetch;
  });

  it("shows the connect-required state when the health check fails", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(url.includes("/health") ? errResponse(500) : errResponse(404))
    );
    render(<SalesforceIntegration />);

    expect(await screen.findByRole("heading", { name: "Connect Salesforce" })).toBeInTheDocument();
    expect(screen.getByText("Disconnected")).toBeInTheDocument();

    // The OAuth button is wired (redirect is a no-op inside jsdom)
    const connectButton = screen.getByRole("button", {
      name: /connect salesforce organization/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
    expect(mockFetch).toHaveBeenCalledWith("/api/integrations/salesforce/health");
  });

  it("connects, loads all datasets once, and renders stats and records", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    // Regression: the health check must not loop (unstable effect deps used to
    // re-trigger every render, hammering the API forever).
    const healthCalls = mockFetch.mock.calls.filter((c) =>
      (c[0] as string).includes("/salesforce/health")
    );
    expect(healthCalls).toHaveLength(1);

    // Profile shown in header
    expect(screen.getByText("System Administrator")).toBeInTheDocument();

    // Stats overview
    expect(screen.getByText("Leads").nextSibling?.textContent).toBe("2");
    expect(screen.getByText("2 open")).toBeInTheDocument();
    expect(
      screen.getByText("$350,000.00 total")
    ).toBeInTheDocument();
    expect(screen.getByText("1 contacts")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // Open cases

    // Leads table renders rows
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("Grace Hopper")).toBeInTheDocument();
    expect(screen.getByText("Converted")).toBeInTheDocument();
    expect(screen.getByText("ada@analytical.com")).toBeInTheDocument();

    // Every loader issued exactly one request (no refetch loops)
    for (const endpoint of ["profile", "leads", "opportunities", "accounts", "contacts", "cases", "users"]) {
      const calls = mockFetch.mock.calls.filter((c) => {
        const u = c[0] as string;
        return u.includes(`/salesforce/${endpoint}`) && !u.includes("/create");
      });
      expect(calls).toHaveLength(1);
    }
  });

  it("filters the leads table by search query", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Search leads..."), {
      target: { value: "Grace" },
    });

    expect(screen.getByText("Grace Hopper")).toBeInTheDocument();
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
  });

  it("creates a lead through the modal and refreshes the list", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create lead/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Create Lead")).toBeInTheDocument();

    fireEvent.change(within(dialog).getByPlaceholderText("First name"), {
      target: { value: "Katherine" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Last name"), {
      target: { value: "Johnson" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Company name"), {
      target: { value: "NASA" },
    });

    fireEvent.click(within(dialog).getByRole("button", { name: "Create Lead" }));

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.some(
          (c) => (c[0] as string).includes("/salesforce/leads/create") && (c[1] as any)?.method === "POST"
        )
      ).toBe(true);
    });

    const createCall = mockFetch.mock.calls.find((c) =>
      (c[0] as string).includes("/salesforce/leads/create")
    );
    const body = JSON.parse((createCall as any[])[1].body);
    expect(body.FirstName).toBe("Katherine");
    expect(body.LastName).toBe("Johnson");
    expect(body.Company).toBe("NASA");

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Success", description: "Lead created successfully" })
    );

    // Modal closes and the list is reloaded
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("First name")).not.toBeInTheDocument();
    });
    const leadsCalls = mockFetch.mock.calls.filter((c) =>
      (c[0] as string).includes("/salesforce/leads") && !(c[0] as string).includes("/create")
    );
    expect(leadsCalls.length).toBeGreaterThanOrEqual(2);
  });

  it("keeps the Create Lead submit disabled until a last name is provided", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create lead/i }));
    const dialog = await screen.findByRole("dialog");
    const submit = within(dialog).getByRole("button", { name: "Create Lead" });
    expect(submit).toBeDisabled();

    fireEvent.change(within(dialog).getByPlaceholderText("Last name"), {
      target: { value: "Johnson" },
    });
    expect(submit).toBeEnabled();
  });

  it("creates an opportunity with a selected account", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create opportunity/i }));
    const dialog = await screen.findByRole("dialog");

    const accountSelect = within(dialog).getByLabelText(/Account \*/);
    expect(within(accountSelect).getByText("Acme Corp")).toBeInTheDocument();

    fireEvent.change(within(dialog).getByPlaceholderText("Opportunity name"), {
      target: { value: "Q4 Expansion" },
    });
    fireEvent.change(accountSelect, { target: { value: "acc-1" } });

    fireEvent.click(within(dialog).getByRole("button", { name: "Create Opportunity" }));

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.some(
          (c) =>
            (c[0] as string).includes("/salesforce/opportunities/create") &&
            (c[1] as any)?.method === "POST"
        )
      ).toBe(true);
    });

    const createCall = mockFetch.mock.calls.find((c) =>
      (c[0] as string).includes("/salesforce/opportunities/create")
    );
    const body = JSON.parse((createCall as any[])[1].body);
    expect(body.Name).toBe("Q4 Expansion");
    expect(body.AccountId).toBe("acc-1");
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ description: "Opportunity created successfully" })
    );
  });

  it("creates an account through its modal", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    const dialog = await screen.findByRole("dialog");

    fireEvent.change(within(dialog).getByPlaceholderText("Account name"), {
      target: { value: "Initech" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Phone number"), {
      target: { value: "555-9999" },
    });

    fireEvent.click(within(dialog).getByRole("button", { name: "Create Account" }));

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.some(
          (c) => (c[0] as string).includes("/salesforce/accounts/create") && (c[1] as any)?.method === "POST"
        )
      ).toBe(true);
    });

    const createCall = mockFetch.mock.calls.find((c) =>
      (c[0] as string).includes("/salesforce/accounts/create")
    );
    const body = JSON.parse((createCall as any[])[1].body);
    expect(body.Name).toBe("Initech");
    expect(body.Phone).toBe("555-9999");
  });

  it("shows accounts and their websites on the accounts tab", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: "Accounts" }));
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "https://acme.example.com" })).toHaveAttribute(
      "href",
      "https://acme.example.com"
    );
  });

  it("re-checks connection when Refresh Status is clicked", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
    const before = mockFetch.mock.calls.filter((c) =>
      (c[0] as string).includes("/salesforce/health")
    ).length;

    fireEvent.click(screen.getByRole("button", { name: /refresh status/i }));

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.filter((c) =>
          (c[0] as string).includes("/salesforce/health")
        ).length
      ).toBe(before + 1);
    });
  });
});

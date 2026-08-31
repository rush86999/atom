import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import SalesforceIntegration from "@/pages/integrations/salesforce";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockToast = jest.fn();

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});
const errResponse = (status: number) => ({
  ok: false,
  status,
  json: async () => ({}),
});

const navigationErrors: string[] = [];
const vc = (window as any)._virtualConsole;
if (vc && vc.on) {
  vc.on("jsdomError", (error: any) => {
    const message = String(error && (error.message || error));
    if (message.includes("Not implemented: navigation")) {
      navigationErrors.push(message);
    }
  });
}

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
  {
    id: "acc-1",
    Name: "Acme Corp",
    Type: "Customer",
    Industry: "Technology",
    Phone: "555-1000",
    Website: "https://acme.example.com",
    Owner: { Name: "Rushi" },
  },
  {
    id: "acc-2",
    Name: "Globex",
    Type: "Partner",
    Industry: "Retail",
    Phone: "555-2000",
    Website: null,
    Owner: { Name: "Rushi" },
  },
];

const CONTACTS = [
  {
    id: "c-1",
    FirstName: "Alan",
    LastName: "Turing",
    Email: "alan@acme.example.com",
    AccountName: "Acme Corp",
    Owner: { Name: "Rushi" },
  },
];

const CASES = [
  {
    id: "cs-1",
    CaseNumber: "00001111",
    Subject: "Login issue",
    Status: "New",
    Priority: "High",
    AccountName: "Acme Corp",
    Owner: { Name: "Rushi" },
    ClosedDate: null,
    Comments: [],
  },
  {
    id: "cs-2",
    CaseNumber: "00002222",
    Subject: "Closed billing",
    Status: "Closed",
    Priority: "Low",
    ClosedDate: "2026-01-01",
    Owner: { Name: "Rushi" },
    Comments: [],
  },
];

const USERS = [
  {
    id: "usr-1",
    Name: "Rushi Parikh",
    Email: "rushi@atom.ai",
    Title: "Engineer",
    IsActive: true,
  },
  {
    id: "usr-2",
    Name: "Grace Hopper",
    Email: "grace@navy.mil",
    Title: "Rear Admiral",
    IsActive: false,
  },
];

describe("SalesforceIntegration", () => {
  const mockFetch = jest.fn();

  const setupConnectedMocks = () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/salesforce/health"))
        return Promise.resolve(okResponse({ status: "healthy" }));
      if (url.includes("/salesforce/profile"))
        return Promise.resolve(okResponse({ data: { profile: PROFILE } }));
      if (url.includes("/salesforce/leads/create"))
        return Promise.resolve(okResponse({ data: { lead: {} } }));
      if (url.includes("/salesforce/leads"))
        return Promise.resolve(okResponse({ data: { leads: LEADS } }));
      if (url.includes("/salesforce/opportunities/create"))
        return Promise.resolve(okResponse({ data: { opportunity: {} } }));
      if (url.includes("/salesforce/opportunities"))
        return Promise.resolve(
          okResponse({ data: { opportunities: OPPORTUNITIES } }),
        );
      if (url.includes("/salesforce/accounts/create"))
        return Promise.resolve(okResponse({ data: { account: {} } }));
      if (url.includes("/salesforce/accounts"))
        return Promise.resolve(okResponse({ data: { accounts: ACCOUNTS } }));
      if (url.includes("/salesforce/contacts"))
        return Promise.resolve(okResponse({ data: { contacts: CONTACTS } }));
      if (url.includes("/salesforce/cases"))
        return Promise.resolve(okResponse({ data: { cases: CASES } }));
      if (url.includes("/salesforce/users"))
        return Promise.resolve(okResponse({ data: { users: USERS } }));
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
      url.includes("/health") ? Promise.resolve(errResponse(500)) : Promise.resolve(errResponse(404)),
    );
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /Connect Salesforce/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Connect Salesforce Organization/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Create Lead")).not.toBeInTheDocument();
  });

  it("starts the OAuth flow from the connect-required state", async () => {
    navigationErrors.length = 0;
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(500)));
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /Connect Salesforce/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: /Connect Salesforce Organization/i }),
    );
    expect(navigationErrors).toHaveLength(1);
  });

  it("connects, loads all datasets, renders the profile and overview stats", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("System Administrator")).toBeInTheDocument();
    });
    expect(screen.getByText("Salesforce Admin")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });
    expect(screen.getByText("Grace Hopper")).toBeInTheDocument();
    expect(screen.getByText("Analytical Engines")).toBeInTheDocument();
    expect(screen.getByText("Qualified")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/\$350,000\.00 total/)).toBeInTheDocument();
    });
    expect(screen.getByText("1 open")).toBeInTheDocument();
  });

  it("renders empty datasets without crashing", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/salesforce/health")
        ? Promise.resolve(okResponse({ status: "healthy" }))
        : Promise.resolve(okResponse({ data: {} })),
    );
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Leads").length).toBeGreaterThan(0);
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
    expect(screen.getByText(/\$0\.00 total/)).toBeInTheDocument();
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
  });

  it("filters the leads table by search query", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Search leads..."), {
      target: { value: "hopper" },
    });
    expect(screen.getByText("Grace Hopper")).toBeInTheDocument();
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Search leads..."), {
      target: { value: "zzz" },
    });
    expect(screen.queryByText("Grace Hopper")).not.toBeInTheDocument();
  });

  it("switches to the accounts tab and renders account rows", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Accounts/i }));
    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /https:\/\/acme\.example\.com/i }),
    ).toHaveAttribute("href", "https://acme.example.com");
    expect(screen.getByText("Customer")).toBeInTheDocument();
    expect(screen.getByText("Technology")).toBeInTheDocument();
  });

  it("creates a lead through the modal and refreshes the list", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByRole("button", {
      name: /Create Lead/i,
    });
    fireEvent.click(createButtons[0]);

    const dialog = await screen.findByRole("dialog");
    const submit = within(dialog).getByRole("button", {
      name: /Create Lead/i,
    });
    expect(submit).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText(/Last Name/i), {
      target: { value: "Newman" },
    });
    fireEvent.change(within(dialog).getByLabelText(/First Name/i), {
      target: { value: "Paul" },
    });
    expect(submit).not.toBeDisabled();

    fireEvent.click(submit);
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/salesforce/leads/create",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("Newman"),
        }),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Success" }),
      );
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the create-lead submit disabled without a last name", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getAllByRole("button", { name: /Create Lead/i })[0],
    );
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("button", { name: /Create Lead/i }),
    ).toBeDisabled();
  });

  it("creates an opportunity with a selected account", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: /Opportunities/i }),
    );
    expect(
      await screen.findByText("Big Enterprise Deal"),
    ).toBeInTheDocument();
    expect(screen.getByText("$100,000.00")).toBeInTheDocument();
    expect(screen.getByText("$250,000.00")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Create Opportunity/i }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("button", { name: /Create Opportunity/i }),
    ).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText(/Opportunity Name/i), {
      target: { value: "New Pipeline Deal" },
    });
    fireEvent.change(within(dialog).getByLabelText(/^Account/i), {
      target: { value: "acc-1" },
    });

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Opportunity/i }),
    );
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/salesforce/opportunities/create",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("New Pipeline Deal"),
        }),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Success" }),
      );
    });
  });

  it("creates an account through its modal", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Accounts/i }));
    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: /Create Account/i }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("button", { name: /Create Account/i }),
    ).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText(/Account Name/i), {
      target: { value: "Newco" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Account/i }),
    );
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/salesforce/accounts/create",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("Newco"),
        }),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Success" }),
      );
    });
  });

  it("shows an error toast when creating a lead fails", async () => {
    setupConnectedMocks();
    mockFetch.mockImplementation((url: string) =>
      url.includes("/salesforce/leads/create")
        ? Promise.reject(new Error("boom"))
        : Promise.resolve(okResponse({ data: {} })),
    );
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getAllByRole("button", { name: /Create Lead/i })[0],
    );
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Last Name/i), {
      target: { value: "Newman" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Lead/i }),
    );
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error" }),
      );
    });
  });

  it("re-checks connection when Refresh Status is clicked", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    const healthCalls = mockFetch.mock.calls.filter(([url]: [string]) =>
      String(url).includes("/salesforce/health"),
    ).length;
    fireEvent.click(
      screen.getByRole("button", { name: /Refresh Status/i }),
    );
    await waitFor(() => {
      const after = mockFetch.mock.calls.filter(([url]: [string]) =>
        String(url).includes("/salesforce/health"),
      ).length;
      expect(after).toBeGreaterThan(healthCalls);
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: full modal form fields, tab searches, and error paths
// ---------------------------------------------------------------------------
describe("SalesforceIntegration (extended coverage)", () => {
  const mockFetch = jest.fn();
  let errorSpy: jest.SpyInstance;

  const setupConnectedMocks = () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/salesforce/health"))
        return Promise.resolve(okResponse({ status: "healthy" }));
      if (url.includes("/salesforce/profile"))
        return Promise.resolve(okResponse({ data: { profile: PROFILE } }));
      if (url.includes("/salesforce/leads/create"))
        return Promise.resolve(okResponse({ data: { lead: {} } }));
      if (url.includes("/salesforce/leads"))
        return Promise.resolve(okResponse({ data: { leads: LEADS } }));
      if (url.includes("/salesforce/opportunities/create"))
        return Promise.resolve(okResponse({ data: { opportunity: {} } }));
      if (url.includes("/salesforce/opportunities"))
        return Promise.resolve(
          okResponse({ data: { opportunities: OPPORTUNITIES } }),
        );
      if (url.includes("/salesforce/accounts/create"))
        return Promise.resolve(okResponse({ data: { account: {} } }));
      if (url.includes("/salesforce/accounts"))
        return Promise.resolve(okResponse({ data: { accounts: ACCOUNTS } }));
      if (url.includes("/salesforce/contacts"))
        return Promise.resolve(okResponse({ data: { contacts: CONTACTS } }));
      if (url.includes("/salesforce/cases"))
        return Promise.resolve(okResponse({ data: { cases: CASES } }));
      if (url.includes("/salesforce/users"))
        return Promise.resolve(okResponse({ data: { users: USERS } }));
      return Promise.resolve(errResponse(404));
    });
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    global.fetch = mockFetch;
    errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const settle = async () => {
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });
  };

  const fill = (
    scope: HTMLElement,
    matcher: RegExp | string,
    value: string,
  ) => {
    fireEvent.change(within(scope).getByLabelText(matcher), {
      target: { value },
    });
  };

  it("fills every field of the create-lead modal and submits", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    fireEvent.click(
      screen.getAllByRole("button", { name: /Create Lead/i })[0],
    );
    const dialog = await screen.findByRole("dialog");

    fill(dialog, /First Name/i, "Paul");
    fill(dialog, /Last Name/i, "Newman");
    fill(dialog, /Company/i, "Newco");
    fill(dialog, /Title/i, "CTO");
    fill(dialog, /Email/i, "paul@newco.com");
    fill(dialog, /Phone/i, "555-9999");
    fireEvent.change(within(dialog).getByLabelText("Industry"), {
      target: { value: "Technology" },
    });
    fill(dialog, /Annual Revenue/i, "1000000");
    fireEvent.change(within(dialog).getByLabelText("Lead Source"), {
      target: { value: "Web" },
    });
    fireEvent.change(within(dialog).getByLabelText("Rating"), {
      target: { value: "Hot" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Street"), {
      target: { value: "1 Main St" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("City"), {
      target: { value: "Springfield" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("State"), {
      target: { value: "IL" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Postal Code"), {
      target: { value: "62701" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Country"), {
      target: { value: "USA" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Additional information..."), {
      target: { value: "A promising lead" },
    });

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Lead/i }),
    );
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/salesforce/leads/create",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("1 Main St"),
        }),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Success" }),
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("closes the create-lead modal via Cancel without creating", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    fireEvent.click(
      screen.getAllByRole("button", { name: /Create Lead/i })[0],
    );
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("fills every field of the create-opportunity modal and submits", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    fireEvent.click(screen.getByRole("button", { name: /Opportunities/i }));
    expect(
      await screen.findByText("Big Enterprise Deal"),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Create Opportunity/i }),
    );
    const dialog = await screen.findByRole("dialog");

    fill(dialog, /Opportunity Name/i, "New Deal");
    fireEvent.change(within(dialog).getByLabelText(/^Account/i), {
      target: { value: "acc-1" },
    });
    fill(dialog, /Amount/i, "50000");
    fill(dialog, /Close Date/i, "2026-12-31");
    fireEvent.change(within(dialog).getByLabelText("Stage"), {
      target: { value: "Negotiation/Review" },
    });
    fill(dialog, /Probability/i, "75");
    fireEvent.change(within(dialog).getByLabelText("Type"), {
      target: { value: "Existing Business" },
    });
    fireEvent.change(within(dialog).getByLabelText("Lead Source"), {
      target: { value: "Partner" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Opportunity description..."), {
      target: { value: "Desc" },
    });

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Opportunity/i }),
    );
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/salesforce/opportunities/create",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("Existing Business"),
        }),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Success" }),
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("shows an error toast when creating an opportunity fails", async () => {
    setupConnectedMocks();
    mockFetch.mockImplementation((url: string) =>
      url.includes("/salesforce/opportunities/create")
        ? Promise.reject(new Error("boom"))
        : url.includes("/salesforce/health")
          ? Promise.resolve(okResponse({ status: "healthy" }))
          : url.includes("/salesforce/accounts")
            ? Promise.resolve(okResponse({ data: { accounts: ACCOUNTS } }))
            : Promise.resolve(okResponse({ data: {} })),
    );
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Opportunities/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /Create Opportunity/i }),
    );
    const dialog = await screen.findByRole("dialog");
    fill(dialog, /Opportunity Name/i, "Failing");
    fireEvent.change(within(dialog).getByLabelText(/^Account/i), {
      target: { value: "acc-1" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Opportunity/i }),
    );
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error" }),
      );
    });
  });

  it("fills every field of the create-account modal and submits", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    fireEvent.click(screen.getByRole("button", { name: /Accounts/i }));
    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Create Account/i }),
    );
    const dialog = await screen.findByRole("dialog");

    fill(dialog, /Account Name/i, "Newco");
    fireEvent.change(within(dialog).getByLabelText("Type"), {
      target: { value: "Partner" },
    });
    fireEvent.change(within(dialog).getByLabelText("Industry"), {
      target: { value: "Retail" },
    });
    fill(dialog, /Phone/i, "555-3000");
    fill(dialog, /Website/i, "https://newco.example.com");
    fill(dialog, /Annual Revenue/i, "500000");
    fill(dialog, /Number of Employees/i, "42");
    fireEvent.change(within(dialog).getByPlaceholderText("Street"), {
      target: { value: "2 Oak Ave" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("City"), {
      target: { value: "Shelbyville" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("State"), {
      target: { value: "OH" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Postal Code"), {
      target: { value: "44101" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Country"), {
      target: { value: "USA" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("Account description..."), {
      target: { value: "Desc" },
    });

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Account/i }),
    );
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/salesforce/accounts/create",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("2 Oak Ave"),
        }),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Success" }),
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("shows an error toast when creating an account fails", async () => {
    setupConnectedMocks();
    mockFetch.mockImplementation((url: string) =>
      url.includes("/salesforce/accounts/create")
        ? Promise.reject(new Error("boom"))
        : url.includes("/salesforce/health")
          ? Promise.resolve(okResponse({ status: "healthy" }))
          : Promise.resolve(okResponse({ data: {} })),
    );
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Accounts/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /Create Account/i }),
    );
    const dialog = await screen.findByRole("dialog");
    fill(dialog, /Account Name/i, "Failco");
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Create Account/i }),
    );
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error" }),
      );
    });
  });

  it("filters the opportunities table by search query", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    fireEvent.click(screen.getByRole("button", { name: /Opportunities/i }));
    expect(
      await screen.findByText("Big Enterprise Deal"),
    ).toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText("Search opportunities..."),
      { target: { value: "globex" } },
    );
    expect(screen.getByText("Expansion")).toBeInTheDocument();
    expect(
      screen.queryByText("Big Enterprise Deal"),
    ).not.toBeInTheDocument();
  });

  it("filters the accounts table by search query", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    fireEvent.click(screen.getByRole("button", { name: /Accounts/i }));
    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Search accounts..."), {
      target: { value: "retail" },
    });
    expect(screen.getByText("Globex")).toBeInTheDocument();
    expect(screen.queryByText("Acme Corp")).not.toBeInTheDocument();
  });

  it("reloads leads when the status filter changes via the Radix select", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    const trigger = screen.getByRole("combobox");
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const option = await waitFor(() => {
      const found = Array.from(
        document.querySelectorAll('[role="option"]'),
      ).find((el) => el.textContent === "Qualified");
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    fireEvent.click(option);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/salesforce/leads",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"status":"Qualified"'),
        }),
      );
    });
  });

  it("logs errors and shows an error toast when loads fail", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/salesforce/health"))
        return Promise.resolve(okResponse({ status: "healthy" }));
      return Promise.reject(new Error("boom"));
    });
    render(<SalesforceIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        "Failed to load user profile:",
        expect.anything(),
      );
      expect(errorSpy).toHaveBeenCalledWith(
        "Failed to load leads:",
        expect.anything(),
      );
      expect(errorSpy).toHaveBeenCalledWith(
        "Failed to load opportunities:",
        expect.anything(),
      );
      expect(errorSpy).toHaveBeenCalledWith(
        "Failed to load accounts:",
        expect.anything(),
      );
      expect(errorSpy).toHaveBeenCalledWith(
        "Failed to load contacts:",
        expect.anything(),
      );
      expect(errorSpy).toHaveBeenCalledWith(
        "Failed to load cases:",
        expect.anything(),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Error",
          description: "Failed to load leads from Salesforce",
        }),
      );
    });
  });

  it("filters accounts by type via the Filter by type select", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    fireEvent.click(screen.getByRole("button", { name: /Accounts/i }));
    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();

    const typeTrigger = screen.getByRole("combobox");
    fireEvent.click(typeTrigger);
    const partnerOption = await screen.findByRole("option", {
      name: "Partner",
    });
    fireEvent.click(partnerOption);

    await waitFor(() => {
      expect(screen.queryByText("Acme Corp")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Globex")).toBeInTheDocument();

    fireEvent.click(typeTrigger);
    const allOption = await screen.findByRole("option", {
      name: "All Types",
    });
    fireEvent.click(allOption);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });
  });

  it("closes each create dialog via the Escape key", async () => {
    setupConnectedMocks();
    render(<SalesforceIntegration />);
    await settle();

    // Lead dialog
    fireEvent.click(
      screen.getAllByRole("button", { name: /Create Lead/i })[0],
    );
    const leadDialog = await screen.findByRole("dialog");
    fireEvent.keyDown(leadDialog, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // Opportunity dialog
    fireEvent.click(screen.getByRole("button", { name: /Opportunities/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /Create Opportunity/i }),
    );
    const oppDialog = await screen.findByRole("dialog");
    fireEvent.keyDown(oppDialog, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // Account dialog
    fireEvent.click(screen.getByRole("button", { name: /Accounts/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /Create Account/i }),
    );
    const accDialog = await screen.findByRole("dialog");
    fireEvent.keyDown(accDialog, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("shows the disconnected state when the health check rejects", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/salesforce/health")
        ? Promise.reject(new Error("network down"))
        : Promise.resolve(errResponse(404)),
    );
    render(<SalesforceIntegration />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: /Connect Salesforce/i }),
    ).toBeInTheDocument();
  });
});

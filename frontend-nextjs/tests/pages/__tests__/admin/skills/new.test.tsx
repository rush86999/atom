import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import NewSkillPage from "@/pages/admin/skills/new";
import { useSession } from "next-auth/react";

jest.mock("next-auth/react", () => ({
  useSession: jest.fn(),
  signIn: jest.fn(),
  getSession: jest.fn(),
}));

describe("NewSkillPage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useSession as jest.Mock).mockReturnValue({
      data: { backendToken: "backend-token-123" },
      status: "authenticated",
    });
    global.fetch = mockFetch;
  });

  describe("Component Import/Export", () => {
    it("should render the Skill Builder page", () => {
      render(<NewSkillPage />);
      expect(
        screen.getByRole("heading", { name: /skill builder/i })
      ).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("e.g., data-scraper")
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /create skill package/i })
      ).toBeInTheDocument();
    });
  });

  describe("Capabilities input", () => {
    it("should render capability badges as they are typed", () => {
      render(<NewSkillPage />);

      fireEvent.change(
        screen.getByPlaceholderText("scrape, interactions"),
        { target: { value: "scrape, interactions, " } }
      );

      expect(screen.getByText("scrape")).toBeInTheDocument();
      expect(screen.getByText("interactions")).toBeInTheDocument();
    });
  });

  describe("Form submission", () => {
    it("should POST skill payload with backend token and show success", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ success: true }),
      });

      render(<NewSkillPage />);

      fireEvent.change(screen.getByPlaceholderText("e.g., data-scraper"), {
        target: { value: "data-scraper" },
      });
      fireEvent.change(screen.getByPlaceholderText("What does this skill do?"), {
        target: { value: "Scrapes web pages" },
      });
      fireEvent.change(screen.getByPlaceholderText("Tell the agent how to use this skill..."), {
        target: { value: "Call it to scrape data" },
      });
      fireEvent.change(screen.getByPlaceholderText("scrape, interactions"), {
        target: { value: "scrape, interactions" },
      });
      fireEvent.change(screen.getByDisplayValue("script.py"), {
        target: { value: "main.py" },
      });

      fireEvent.click(
        screen.getByRole("button", { name: /create skill package/i })
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(1);
      });

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe("/api/admin/skills");
      expect(options.method).toBe("POST");
      expect(options.headers).toEqual({
        "Content-Type": "application/json",
        Authorization: "Bearer backend-token-123",
      });

      const payload = JSON.parse(options.body);
      expect(payload.name).toBe("data-scraper");
      expect(payload.description).toBe("Scrapes web pages");
      expect(payload.instructions).toBe("Call it to scrape data");
      expect(payload.capabilities).toEqual(["scrape", "interactions"]);
      expect(Object.keys(payload.scripts)).toEqual(["main.py"]);

      await waitFor(() => {
        expect(
          screen.getByText("Skill 'data-scraper' created successfully")
        ).toBeInTheDocument();
      });
    });

    it("should show backend error detail when creation fails", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: "Skill name already exists" }),
      });

      render(<NewSkillPage />);

      fireEvent.change(screen.getByPlaceholderText("e.g., data-scraper"), {
        target: { value: "dup-skill" },
      });
      fireEvent.change(screen.getByPlaceholderText("What does this skill do?"), {
        target: { value: "Description" },
      });
      fireEvent.change(screen.getByPlaceholderText("Tell the agent how to use this skill..."), {
        target: { value: "Usage instructions" },
      });

      fireEvent.click(
        screen.getByRole("button", { name: /create skill package/i })
      );

      await waitFor(() => {
        expect(screen.getByText("Skill name already exists")).toBeInTheDocument();
      });
      expect(
        screen.queryByText(/created successfully/)
      ).not.toBeInTheDocument();
    });

    it("should show thrown error message on network failure", async () => {
      mockFetch.mockRejectedValue(new Error("Failed to fetch"));

      render(<NewSkillPage />);

      fireEvent.change(screen.getByPlaceholderText("e.g., data-scraper"), {
        target: { value: "net-skill" },
      });
      fireEvent.change(screen.getByPlaceholderText("What does this skill do?"), {
        target: { value: "Description" },
      });
      fireEvent.change(screen.getByPlaceholderText("Tell the agent how to use this skill..."), {
        target: { value: "Usage instructions" },
      });

      fireEvent.click(
        screen.getByRole("button", { name: /create skill package/i })
      );

      await waitFor(() => {
        expect(screen.getByText("Failed to fetch")).toBeInTheDocument();
      });
    });
  });

  describe("Security scan", () => {
    it("should run a security scan and show safe results", async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url === "/api/protection/scan") {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ is_safe: true, findings: [] }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ success: true }),
        });
      });

      render(<NewSkillPage />);

      fireEvent.click(screen.getByRole("button", { name: /scan skill/i }));

      await waitFor(() => {
        const scanCall = mockFetch.mock.calls.find(
          ([url]: [string]) => url === "/api/protection/scan"
        );
        expect(scanCall).toBeTruthy();
      });

      await waitFor(() => {
        expect(screen.getByText("No Threats Detected")).toBeInTheDocument();
      });
    });
  });
});

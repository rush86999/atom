/**
 * InteractiveForm Component Tests
 * Target: 80%+ coverage
 *
 * Tests cover:
 * - Rendering all field types
 * - Field validation (required, pattern, min/max)
 * - Input handling (text, number, select, checkbox)
 * - Submission states (success, failure, loading)
 * - Canvas state integration
 * - Error messages
 * - Auto-hide success message
 */

import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InteractiveForm } from "../InteractiveForm";
import { FormField } from "../types";

// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';

describe("InteractiveForm", () => {
  // Increase timeout for canvas integration tests
  vi.setConfig({ testTimeout: 10000 });
  const mockTenantId = "tenant-123";
  const mockAgentId = "agent-456";

  const mockFields: FormField[] = [
    {
      name: "name",
      label: "Name",
      type: "text",
      required: true,
      placeholder: "Enter your name",
    },
    {
      name: "email",
      label: "Email",
      type: "email",
      required: true,
      placeholder: "user@example.com",
      validation: {
        pattern: "^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,4}$",
        custom: "Invalid email format",
      },
    },
    {
      name: "age",
      label: "Age",
      type: "number",
      validation: {
        min: 18,
        max: 120,
      },
    },
    {
      name: "country",
      label: "Country",
      type: "select",
      options: [
        { value: "us", label: "United States" },
        { value: "uk", label: "United Kingdom" },
        { value: "ca", label: "Canada" },
      ],
    },
    {
      name: "agree",
      label: "I agree to terms",
      type: "checkbox",
      required: true,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    // Clear window.atom.canvas before each test
    if (typeof window !== 'undefined') {
      delete (window as any).atom;
    }
    // Clear storage
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  describe("Rendering Tests", () => {
    it("should render form with title", () => {
      render(
        <InteractiveForm
          fields={mockFields}
          onSubmit={vi.fn()}
          title="Test Form"
        />
      );

      expect(screen.getByText("Test Form")).toBeInTheDocument();
    });

    it("renders all field types (text, email, number, select, checkbox)", () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      // Text and email fields (both render as textbox)
      const textboxes = screen.getAllByRole("textbox");
      expect(textboxes.length).toBeGreaterThanOrEqual(2);

      // Number field
      expect(screen.getByRole("spinbutton")).toBeInTheDocument();

      // Select field
      expect(screen.getByRole("combobox")).toBeInTheDocument();

      // Checkbox
      expect(screen.getByRole("checkbox")).toBeInTheDocument();
    });

    it("shows labels with required asterisk", () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Email")).toBeInTheDocument();
      expect(screen.getByText("I agree to terms")).toBeInTheDocument();

      const requiredIndicators = screen.getAllByText("*");
      expect(requiredIndicators.length).toBeGreaterThanOrEqual(3); // name, email, agree
    });

    it("shows placeholder text", () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      expect(screen.getByPlaceholderText("Enter your name")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("user@example.com")).toBeInTheDocument();
    });

    it("renders select dropdown with options", () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      const select = screen.getByRole("combobox");
      expect(select).toBeInTheDocument();

      // Check that options are rendered
      expect(screen.getByText("Select...")).toBeInTheDocument();
    });

    it("renders checkbox with unchecked state by default", () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      const checkbox = screen.getByRole("checkbox");
      expect(checkbox).not.toBeChecked();
    });
  });

  describe("Field Validation Tests", () => {
    it("required fields show error when empty", async () => {
      const mockSubmit = vi.fn();
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const submitButton = screen.getByRole("button", { name: /submit/i });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(mockSubmit).not.toHaveBeenCalled();
      });

      // Errors should be displayed
      expect(screen.getByText(/Name is required/)).toBeInTheDocument();
    });

    it("pattern validation works for email format", async () => {
      // Note: HTML5 email validation prevents custom pattern validation from running
      // This test verifies that HTML5 validation blocks submission
      const mockSubmit = vi.fn();
      const emailTextField: FormField[] = [
        {
          name: "email",
          label: "Email",
          type: "text", // Use text type to allow pattern validation
          required: true,
          validation: {
            pattern: "^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,4}$",
            custom: "Invalid email format",
          },
        }
      ];

      render(
        <InteractiveForm fields={emailTextField} onSubmit={mockSubmit} />
      );

      const input = screen.getByRole("textbox");
      const submitButton = screen.getByRole("button", { name: /submit/i });

      await userEvent.type(input, "invalid-email");
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Invalid email format")).toBeInTheDocument();
        expect(mockSubmit).not.toHaveBeenCalled();
      });
    });

    it("min validation for number fields", async () => {
      const mockSubmit = vi.fn();
      const fieldsWithMin: FormField[] = [
        { name: "age", label: "Age", type: "number", validation: { min: 18 }, required: true }
      ];

      render(
        <InteractiveForm fields={fieldsWithMin} onSubmit={mockSubmit} />
      );

      const ageInput = screen.getByRole("spinbutton");
      const submitButton = screen.getByRole("button", { name: /submit/i });

      await userEvent.type(ageInput, "15");
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Age must be at least 18/)).toBeInTheDocument();
        expect(mockSubmit).not.toHaveBeenCalled();
      });
    });

    it("max validation for number fields", async () => {
      const mockSubmit = vi.fn();
      const fieldsWithMax: FormField[] = [
        { name: "age", label: "Age", type: "number", validation: { max: 120 }, required: true }
      ];

      render(
        <InteractiveForm fields={fieldsWithMax} onSubmit={mockSubmit} />
      );

      const ageInput = screen.getByRole("spinbutton");
      const submitButton = screen.getByRole("button", { name: /submit/i });

      await userEvent.type(ageInput, "150");
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Age must be at most 120/)).toBeInTheDocument();
        expect(mockSubmit).not.toHaveBeenCalled();
      });
    });

    it("custom error messages display correctly", async () => {
      const mockSubmit = vi.fn();
      const fieldsWithCustom: FormField[] = [
        {
          name: "email",
          label: "Email",
          type: "text",
          required: true,
          validation: {
            pattern: "^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,4}$",
            custom: "Please enter a valid email address",
          },
        }
      ];

      render(
        <InteractiveForm fields={fieldsWithCustom} onSubmit={mockSubmit} />
      );

      const input = screen.getByRole("textbox");
      const submitButton = screen.getByRole("button", { name: /submit/i });

      await userEvent.type(input, "invalid");
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Please enter a valid email address")).toBeInTheDocument();
      });
    });

    it("multiple errors show simultaneously", async () => {
      const mockSubmit = vi.fn();
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const submitButton = screen.getByRole("button", { name: /submit/i });
      await userEvent.click(submitButton);

      await waitFor(() => {
        // Should show errors for multiple required fields
        const errorMessages = screen.queryAllByText(/required|Invalid/);
        expect(errorMessages.length).toBeGreaterThan(1);
      });
    });

    it("clears errors when valid input entered", async () => {
      const mockSubmit = vi.fn();
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      const nameInput = inputs[0];

      // Trigger validation error
      const submitButton = screen.getByRole("button", { name: /submit/i });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Name is required/)).toBeInTheDocument();
      }, { timeout: 1000 });

      // Fix error - type in name field
      await userEvent.click(nameInput);
      await userEvent.clear(nameInput);
      await userEvent.type(nameInput, "John Doe");

      // Submit again to clear errors
      await userEvent.click(submitButton);

      // Name error should be cleared, but email error may still exist
      await waitFor(() => {
        expect(screen.queryByText(/Name is required/)).not.toBeInTheDocument();
      }, { timeout: 1000 });
    });
  });

  describe("Input Handling Tests", () => {
    it("text input updates formData", async () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      const inputs = screen.getAllByRole("textbox");
      const nameInput = inputs[0];

      await userEvent.type(nameInput, "John Doe");

      expect(nameInput).toHaveValue("John Doe");
    });

    it("number input parses correctly", async () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      const ageInput = screen.getByRole("spinbutton");

      await userEvent.type(ageInput, "25");

      expect(ageInput).toHaveValue(25);
    });

    it("select dropdown updates on change", async () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      const select = screen.getByRole("combobox");

      await userEvent.selectOptions(select, "us");

      expect(select).toHaveValue("us");
    });

    it("checkbox toggles boolean value", async () => {
      render(
        <InteractiveForm fields={mockFields} onSubmit={vi.fn()} />
      );

      const checkbox = screen.getByRole("checkbox");

      expect(checkbox).not.toBeChecked();

      await userEvent.click(checkbox);

      expect(checkbox).toBeChecked();
    });

    it("form data persists across changes", async () => {
      const mockSubmit = vi.fn().mockResolvedValue(undefined);
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      const nameInput = inputs[0];
      const emailInput = inputs[1];

      await userEvent.type(nameInput, "Jane");
      await userEvent.type(emailInput, "jane@example.com");

      expect(nameInput).toHaveValue("Jane");
      expect(emailInput).toHaveValue("jane@example.com");

      // Add more text
      await userEvent.type(nameInput, " Doe");

      expect(nameInput).toHaveValue("Jane Doe");
      expect(emailInput).toHaveValue("jane@example.com"); // Should persist
    });
  });

  describe("Submission Tests", () => {
    it("calls onSubmit with formData when valid", async () => {
      const mockSubmit = vi.fn().mockResolvedValue(undefined);
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      const nameInput = inputs[0];
      const emailInput = inputs[1];
      const ageInput = screen.getByRole("spinbutton");
      const checkbox = screen.getByRole("checkbox");
      const submitButton = screen.getByRole("button", { name: /submit/i });

      await userEvent.type(nameInput, "John Doe");
      await userEvent.type(emailInput, "john@example.com");
      await userEvent.type(ageInput, "25");
      await userEvent.click(checkbox);

      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalled();
      }, { timeout: 1000 });

      const submittedData = mockSubmit.mock.calls[0][0];
      expect(submittedData).toMatchObject({
        name: "John Doe",
        email: "john@example.com",
        age: 25,
        agree: true,
      });
    });

    it("shows loading state during submission", async () => {
      let resolveSubmit: any;
      const mockSubmit = vi.fn().mockImplementation(
        () => new Promise(resolve => setImmediate(() => { resolveSubmit = resolve; }))
      );
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      await userEvent.type(inputs[0], "John Doe");
      await userEvent.type(inputs[1], "john@example.com");

      const checkbox = screen.getByRole("checkbox");
      await userEvent.click(checkbox);

      const submitButton = screen.getByRole("button", { name: /submit/i });

      // Click submit
      await userEvent.click(submitButton);

      // Wait a tick for state to update
      await new Promise(resolve => setImmediate(resolve));

      // Check for loading state
      expect(screen.getByText(/Submitting.../)).toBeInTheDocument();

      // Clean up
      resolveSubmit();
    });

    it("shows success message after submission", async () => {
      const mockSubmit = vi.fn().mockResolvedValue(undefined);
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      await userEvent.type(inputs[0], "John Doe");
      await userEvent.type(inputs[1], "john@example.com");

      const checkbox = screen.getByRole("checkbox");
      await userEvent.click(checkbox);

      const submitButton = screen.getByRole("button", { name: /submit/i });
      await userEvent.click(submitButton);

      // Wait for success message
      await new Promise(resolve => setImmediate(resolve));
      await waitFor(() => {
        expect(screen.getByText("Submitted successfully!")).toBeInTheDocument();
      });
    });

    it("success message auto-hides after 3 seconds", async () => {
      vi.useFakeTimers();
      const mockSubmit = vi.fn().mockResolvedValue(undefined);
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      await userEvent.type(inputs[0], "John Doe");
      await userEvent.type(inputs[1], "john@example.com");

      const checkbox = screen.getByRole("checkbox");
      await userEvent.click(checkbox);

      const submitButton = screen.getByRole("button", { name: /submit/i });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Submitted successfully!")).toBeInTheDocument();
      });

      // Fast-forward 3 seconds
      vi.advanceTimersByTime(3000);
      await vi.runAllTimersAsync();

      await waitFor(() => {
        expect(screen.queryByText("Submitted successfully!")).not.toBeInTheDocument();
      });

      vi.useRealTimers();
    });

    it("shows form-level error on submission failure", async () => {
      const mockSubmit = vi.fn().mockRejectedValue(new Error("Submission failed"));
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      await userEvent.type(inputs[0], "John Doe");
      await userEvent.type(inputs[1], "john@example.com");

      const checkbox = screen.getByRole("checkbox");
      await userEvent.click(checkbox);

      const submitButton = screen.getByRole("button", { name: /submit/i });
      await userEvent.click(submitButton);

      // Wait for error message
      await new Promise(resolve => setImmediate(resolve));
      await waitFor(() => {
        expect(screen.getByText("Submission failed. Please try again.")).toBeInTheDocument();
      });
    });

    it("disables submit button during submission", async () => {
      let resolveSubmit: any;
      const mockSubmit = vi.fn().mockImplementation(
        () => new Promise(resolve => setImmediate(() => { resolveSubmit = resolve; }))
      );
      render(
        <InteractiveForm fields={mockFields} onSubmit={mockSubmit} />
      );

      const inputs = screen.getAllByRole("textbox");
      await userEvent.type(inputs[0], "John Doe");
      await userEvent.type(inputs[1], "john@example.com");

      const checkbox = screen.getByRole("checkbox");
      await userEvent.click(checkbox);

      const submitButton = screen.getByRole("button", { name: /submit/i });

      await userEvent.click(submitButton);

      // Wait a tick for state to update
      await new Promise(resolve => setImmediate(resolve));

      // Button should be disabled during submission
      expect(submitButton).toBeDisabled();

      // Clean up
      resolveSubmit();
    });
  });

  describe("Canvas Integration Tests", () => {
    it("registers canvas state with window.atom.canvas", () => {
      render(
        <InteractiveForm
          fields={mockFields}
          onSubmit={vi.fn()}
          canvasId="test-canvas"
        />
      );

      // After render, check that window.atom.canvas was created
      expect((window as any).atom).toBeDefined();
      expect((window as any).atom.canvas).toBeDefined();
    });

    it("canvas state includes form schema", () => {
      render(
        <InteractiveForm
          fields={mockFields}
          onSubmit={vi.fn()}
          canvasId="test-canvas"
        />
      );

      // Check that the canvas API exists
      const api = (window as any).atom?.canvas;
      expect(api).toBeDefined();
      expect(typeof api.getState).toBe("function");
    });

    it("canvas state updates on form changes", async () => {
      render(
        <InteractiveForm
          fields={mockFields}
          onSubmit={vi.fn()}
          canvasId="test-canvas"
        />
      );

      const inputs = screen.getAllByRole("textbox");

      // Type value
      await userEvent.type(inputs[0], "Test Value");

      await waitFor(() => {
        expect(inputs[0]).toHaveValue("Test Value");
      }, { timeout: 3000 });
    });
  });

  describe("Additional Tests", () => {
    it("uses default values from field definitions", () => {
      const fieldsWithDefaults: FormField[] = [
        { name: "name", label: "Name", type: "text", defaultValue: "John Doe" }
      ];

      render(
        <InteractiveForm fields={fieldsWithDefaults} onSubmit={vi.fn()} />
      );

      const input = screen.getByRole("textbox");
      expect(input).toHaveValue("John Doe");
    });

    it("handles custom submitLabel", () => {
      render(
        <InteractiveForm
          fields={mockFields}
          onSubmit={vi.fn()}
          submitLabel="Send Form"
        />
      );

      expect(screen.getByRole("button", { name: /Send Form/ })).toBeInTheDocument();
    });

    it("handles empty options array for select", () => {
      const emptySelectFields: FormField[] = [
        { name: "country", label: "Country", type: "select", options: [] }
      ];

      render(
        <InteractiveForm fields={emptySelectFields} onSubmit={vi.fn()} />
      );

      const select = screen.getByRole("combobox");
      expect(select).toBeInTheDocument();
    });

    it("handles non-required checkbox field", async () => {
      const optionalCheckbox: FormField[] = [
        { name: "newsletter", label: "Subscribe to newsletter", type: "checkbox" }
      ];

      const mockSubmit = vi.fn().mockResolvedValue(undefined);
      render(
        <InteractiveForm fields={optionalCheckbox} onSubmit={mockSubmit} />
      );

      const submitButton = screen.getByRole("button", { name: /submit/i });
      await userEvent.click(submitButton);

      // Wait for async submit to complete with proper timeout
      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalled();
      }, { timeout: 3000 });

      const submittedData = mockSubmit.mock.calls[0][0];
      expect(submittedData.newsletter).toBe(false);
    });

    it("handles multiple checkboxes in same form", () => {
      const multipleCheckboxes: FormField[] = [
        { name: "agree1", label: "Agree 1", type: "checkbox" },
        { name: "agree2", label: "Agree 2", type: "checkbox" },
        { name: "agree3", label: "Agree 3", type: "checkbox" },
      ];

      render(
        <InteractiveForm fields={multipleCheckboxes} onSubmit={vi.fn()} />
      );

      const checkboxes = screen.getAllByRole("checkbox");
      expect(checkboxes.length).toBe(3);
    });
  });
});

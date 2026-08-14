/**
 * TemplatesPage tests (pages/automations/templates.tsx, was 0% coverage)
 *
 * Covers: rendering TemplateGallery and the use-template handler
 * (toast, sessionStorage persistence, router push to the builder).
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import TemplatesPage from "@/pages/automations/templates";

const mockPush = jest.fn();
const mockToast = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: (...args: any[]) => mockPush(...args),
    query: {},
  }),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: (...args: any[]) => mockToast(...args) }),
}));

let latestGalleryProps: any = null;
jest.mock("@/components/Automations/TemplateGallery", () => ({
  __esModule: true,
  default: (props: any) => {
    latestGalleryProps = props;
    return <div data-testid="template-gallery">Templates</div>;
  },
}));

describe("TemplatesPage", () => {
  let setItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    latestGalleryProps = null;
    setItemSpy = jest.spyOn(Storage.prototype, "setItem");
  });

  test("renders TemplateGallery", () => {
    render(<TemplatesPage />);
    expect(screen.getByTestId("template-gallery")).toBeInTheDocument();
  });

  test("use-template handler toasts, persists to session, and redirects", () => {
    render(<TemplatesPage />);

    const template = { id: "tpl-7", name: "Lead Router" };
    act(() => {
      latestGalleryProps.onUseTemplate(template);
    });

    expect(mockToast).toHaveBeenCalledWith({
      title: "Template Selected",
      description: 'Setting up "Lead Router"...',
    });
    expect(setItemSpy).toHaveBeenCalledWith(
      "selectedTemplate",
      JSON.stringify(template)
    );
    expect(mockPush).toHaveBeenCalledWith("/automations/builder?template=tpl-7");
  });
});

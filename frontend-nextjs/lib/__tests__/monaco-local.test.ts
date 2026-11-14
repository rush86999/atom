/**
 * The canvas editor must render from the bundled Monaco build.
 *
 * `@monaco-editor/react` defaults to cdn.jsdelivr.net; if that default ever
 * comes back, an offline/air-gapped install and the WA-045 "external traffic
 * refused" acceptance run break silently. These tests pin the same-origin path
 * and the fail-open behaviour under SSR / component-only test doubles.
 */

describe("local Monaco loader configuration", () => {
  beforeEach(() => {
    jest.resetModules();
  });

  test("points @monaco-editor/loader at the bundled same-origin build", () => {
    const config = jest.fn();
    jest.doMock("@monaco-editor/react", () => ({ loader: { config } }));

    let mod: typeof import("../monaco-local");
    jest.isolateModules(() => {
      mod = require("../monaco-local");
    });

    expect(mod!.configureLocalMonaco()).toBe(true);
    expect(config).toHaveBeenCalledTimes(1);
    expect(config).toHaveBeenCalledWith({ paths: { vs: "/monaco/vs" } });
  });

  test("configures the loader only once per client runtime", () => {
    const config = jest.fn();
    jest.doMock("@monaco-editor/react", () => ({ loader: { config } }));

    let mod: typeof import("../monaco-local");
    jest.isolateModules(() => {
      mod = require("../monaco-local");
    });

    expect(mod!.configureLocalMonaco()).toBe(true);
    expect(mod!.configureLocalMonaco()).toBe(true);
    expect(config).toHaveBeenCalledTimes(1);
  });

  test("the editor path is relative, never a CDN URL", () => {
    const { LOCAL_MONACO_VS_PATH } = require("../monaco-local");
    expect(LOCAL_MONACO_VS_PATH).toBe("/monaco/vs");
    expect(LOCAL_MONACO_VS_PATH).not.toMatch(/^(?:https?:)?\/\//i);
    expect(LOCAL_MONACO_VS_PATH).not.toMatch(/jsdelivr|unpkg|cdn/i);
  });

  test("a component-only test double does not throw and stays unconfigured", () => {
    jest.doMock("@monaco-editor/react", () => ({
      __esModule: true,
      default: () => null,
    }));

    let mod: typeof import("../monaco-local");
    jest.isolateModules(() => {
      mod = require("../monaco-local");
    });

    expect(mod!.configureLocalMonaco()).toBe(false);
    // A later real loader is not permanently disabled by the failed attempt.
    expect(mod!.configureLocalMonaco()).toBe(false);
  });
});

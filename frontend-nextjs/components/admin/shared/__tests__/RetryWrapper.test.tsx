/**
 * RetryWrapper / useRetry tests
 *
 * Covers:
 * - useRetry: success on first attempt
 * - useRetry: succeeds after transient failures (with backoff logging)
 * - useRetry: exhausts retries and throws the last error
 * - useRetry: custom options (maxRetries, delayMs, backoffMultiplier)
 * - RetryWrapper: passes the retry function to its children render prop
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import { useRetry, RetryWrapper } from "@/components/admin/shared/RetryWrapper";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: jest.fn(), dismiss: jest.fn(), toasts: [] }),
}));

describe("useRetry", () => {
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    consoleLogSpy = jest
      .spyOn(console, "log")
      .mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  const makeHook = () => {
    let retryFn: ReturnType<typeof useRetry>["retry"] | null = null;
    const Probe: React.FC = () => {
      const { retry } = useRetry();
      retryFn = retry;
      return null;
    };
    render(<Probe />);
    return () => retryFn!;
  };

  test("resolves immediately when the operation succeeds", async () => {
    const getRetry = makeHook();
    const fn = jest.fn().mockResolvedValue("ok");

    await expect(getRetry()(fn)).resolves.toBe("ok");
    expect(fn).toHaveBeenCalledTimes(1);
    expect(consoleLogSpy).not.toHaveBeenCalled();
  });

  test("retries transient failures and resolves once fn succeeds", async () => {
    const getRetry = makeHook();
    const fn = jest
      .fn()
      .mockRejectedValueOnce(new Error("fail 1"))
      .mockRejectedValueOnce(new Error("fail 2"))
      .mockResolvedValue("recovered");

    await expect(
      getRetry()(fn, { delayMs: 0 })
    ).resolves.toBe("recovered");
    expect(fn).toHaveBeenCalledTimes(3);
    // backoff log lines for the two failures
    expect(consoleLogSpy).toHaveBeenCalledWith(
      "[Retry] Attempt 1/4 failed, retrying in 0ms..."
    );
    expect(consoleLogSpy).toHaveBeenCalledWith(
      "[Retry] Attempt 2/4 failed, retrying in 0ms..."
    );
  });

  test("throws the last error after exhausting retries", async () => {
    const getRetry = makeHook();
    const fn = jest.fn().mockRejectedValue(new Error("permanent"));

    await expect(
      getRetry()(fn, { maxRetries: 2, delayMs: 0 })
    ).rejects.toThrow("permanent");
    expect(fn).toHaveBeenCalledTimes(3); // initial + 2 retries
  });

  test("honors custom delay and backoff multiplier", async () => {
    const getRetry = makeHook();
    const fn = jest
      .fn()
      .mockRejectedValueOnce(new Error("a"))
      .mockRejectedValueOnce(new Error("b"))
      .mockResolvedValue("done");

    await expect(
      getRetry()(fn, { maxRetries: 3, delayMs: 10, backoffMultiplier: 3 })
    ).resolves.toBe("done");

    // attempt 0 delay: 10 * 3^0 = 10, attempt 1 delay: 10 * 3^1 = 30
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining("retrying in 10ms...")
    );
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining("retrying in 30ms...")
    );
  });
});

describe("RetryWrapper", () => {
  test("passes the retry function to its children render prop", async () => {
    const rendered = await new Promise<string>((resolve) => {
      render(
        <RetryWrapper>
          {(retry) => {
            resolve(typeof retry);
            return <div data-testid="wrapper-content">wrapped</div>;
          }}
        </RetryWrapper>
      );
    });

    expect(rendered).toBe("function");
    expect(screen.getByTestId("wrapper-content")).toHaveTextContent("wrapped");
  });

  test("the retry function exposed via the render prop retries failures", async () => {
    let capturedRetry: any = null;
    render(
      <RetryWrapper>
        {(retry) => {
          capturedRetry = retry;
          return null;
        }}
      </RetryWrapper>
    );

    const fn = jest
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(42);

    await expect(capturedRetry(fn, { delayMs: 0 })).resolves.toBe(42);
    expect(fn).toHaveBeenCalledTimes(2);
  });
});

// keep `act` import used-type checks happy in environments that tree-shake
void act;

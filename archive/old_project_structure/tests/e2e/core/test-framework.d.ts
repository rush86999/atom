import { Browser, Page } from "@playwright/test";
import { TestConfig } from "./test-config";
export interface TestContext {
  browser: Browser;
  page: Page;
  config: TestConfig;
  authToken?: string;
  userId?: string;
}
export interface Persona {
  id: string;
  name: string;
  email: string;
  characteristics: string[];
  goals: string[];
  integrations: string[];
}
export declare class BaseE2ETest {
  protected context: TestContext;
  protected config: TestConfig;
  constructor(config: TestConfig);
  initializeTest(browser: Browser, testName: string): Promise<TestContext>;
  private setupBrowserDefaults;
  cleanupTest(): Promise<void>;
  login(persona: Persona): Promise<void>;
  waitForElement(
    selector: string,
    timeout?: number,
  ): Promise<import("playwright-core").ElementHandle<HTMLElement | SVGElement>>;
  takeScreenshot(name: string): Promise<void>;
}
export declare const test: import("@playwright/test").TestType<
  import("@playwright/test").PlaywrightTestArgs &
    import("@playwright/test").PlaywrightTestOptions & {
      testContext: TestContext;
      persona: Persona;
    },
  import("@playwright/test").PlaywrightWorkerArgs &
    import("@playwright/test").PlaywrightWorkerOptions
>;
//# sourceMappingURL=test-framework.d.ts.map

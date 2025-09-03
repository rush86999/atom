import { Page } from "@playwright/test";
export interface TestUser {
  id: string;
  name: string;
  email: string;
  persona: string;
}
export declare class TestHelpers {
  static loadTestUsers(): Promise<Record<string, TestUser>>;
  static waitForSelectorWithRetry(
    page: Page,
    selector: string,
    timeout?: number,
    retries?: number,
  ): Promise<true | undefined>;
  static generateScreenshot(page: Page, testName: string): Promise<string>;
  static mockOAuthFlows(page: Page): Promise<void>;
  static mockFinancialData(page: Page): Promise<void>;
  static mockCalendarData(page: Page): Promise<void>;
  static mockNotionData(page: Page): Promise<void>;
}
export declare class PageObject {}
export declare class AuthPage extends PageObject {}
export declare class BaseE2ETest {}
//# sourceMappingURL=test-utils.d.ts.map

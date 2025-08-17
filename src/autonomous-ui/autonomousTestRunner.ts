import { chromium, Browser, Page, BrowserContext } from 'playwright';
import { promises as fs } from 'fs';
import * as path from 'path';
import { EventEmitter } from 'events';

interface StepResult {
  stepId: string;
  success: boolean;
  duration: number;
  actualState: any;
  error?: string;
  screenshot?: string;
  selector?: string;
}

interface TestResult {
  workflowId: string;
  success: boolean;
  steps: StepResult[];
  duration: number;
  insights: string[];
  performanceMetrics: any;
  screenshots: string[];
  errors: string[];
}

interface TestStep {
  id: string;
  type: 'navigate' | 'click' | 'type' | 'select' | 'verify' | 'wait' | 'screenshot' | 'extract';
  selector: string;
  text?: string;
  expectedValue?: any;
  timeout?: number;
  screenshot?: boolean;
}

interface AutonomousTestConfig {
  headless: boolean;
  viewport: { width: number; height: number };
  timeout: number;
  retries: number;
  enableVideo: boolean;
  enableScreenshots: boolean;
}

export class AutonomousTestRunner extends EventEmitter {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private config: AutonomousTestConfig;

  constructor(config: Partial<AutonomousTestConfig> = {}) {
    super();
    this.config = {
      headless: false,
      viewport: { width: 1920, height: 1080 },
      timeout: 30000,
      retries: 2,
      enableVideo: true,
      enableScreenshots: true,
      ...config
    };
  }

  async initialize(): Promise<void> {
    this.browser = await chromium.launch({
      headless: this.config.headless,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    this.context = await this.browser.newContext({
      viewport: this.config.viewport,
      recordVideo: this.config.enableVideo ? { dir: 'videos/' } : undefined
    });
  }

  async shutdown(): Promise<void> {
    if (this.context) {
      await this.context.close();
      this.context = null;
    }
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
    }
  }

  async runAutonomousTest(
    workflowId: string,
    url: string,
    steps: TestStep[]
  ): Promise<TestResult> {
    const startTime = Date.now();
    const result: TestResult = {
      workflowId,
      success: true,
      steps: [],
      duration: 0,
      insights: [],
      performanceMetrics: {},
      screenshots: [],
      errors: []
    };

    const page = await this.context!.newPage();

    try {
      console.log(`[AutonomousTestRunner] Starting test: ${workflowId}`);

      await page.goto(url, { waitUntil: 'networkidle' });

      for (const step of steps) {
        const stepResult = await this.executeStep(step, page, result.screenshots);
        result.steps.push(stepResult);

        if (!stepResult.success) {
          result.success = false;
          result.errors.push(stepResult.error!);

          // Take additional screenshot on failure
          const failureScreenshot = await page.screenshot();
          const filename = `failure-${step.stepId}-${Date.now()}.png`;
          await fs.writeFile(path.join('screenshots', filename), failureScreenshot);
          result.screenshots.push(filename);

          break;
        }
      }

      // Collect final metrics
      result.performanceMetrics = await this.collectMetrics(page);

      // Generate insights
      result.insights = await this.generateInsights(page, result);

    } catch (error) {
      console.error(`[AutonomousTestRunner] Test failed: ${error}`);
      result.success = false;
      result.errors.push(error.message);
    } finally {
      result.duration = Date.now() - startTime;
      await page.close();

      this.emit('test-completed', result);
    }

    return result;
  }

  private async executeStep(step: TestStep, page: Page, screenshots: string[]): Promise<StepResult> {
    const startTime = Date.now();
    const result: StepResult = {
      stepId: step.id,
      success: false,
      duration: 0,
      actualState: null,
      selector: step.selector
    };

    try {
      switch (step.type) {
        case 'navigate':
          await page.goto(step.text!, { waitUntil: 'networkidle', timeout: step.timeout || 10000 });
          break;

        case 'click':
          await page.click(step.selector, { timeout: step.timeout || 10000 });
          break;

        case 'type

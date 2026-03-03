/**
 * WebDriverIO Configuration for Tauri Desktop E2E Testing
 *
 * This configuration supports testing the Atom desktop app using WebDriverIO.
 * Note: tauri-driver (official WebDriver support for Tauri) is not currently
 * available via npm or cargo. This configuration uses Chrome DevTools Protocol
 * to connect to the Tauri dev server.
 *
 * For production E2E testing, consider:
 * - Using Tauri's built-in integration tests (see src-tauri/tests/)
 * - Building a custom WebDriver adapter using Tauri's IPC
 * - Waiting for official tauri-driver support
 *
 * @see frontend-nextjs/wdio/README.md for feasibility assessment
 */

export const config = {
  /**
   * Runner configuration
   */
  runner: 'local',

  /**
   * TypeScript compilation options
   */
  autoCompileOpts: {
    autoCompile: true,
    tsNodeOpts: {
      transpileOnly: true,
      project: './tsconfig.json'
    }
  },

  /**
   * Test file patterns
   */
  specs: ['./specs/**/*.e2e.ts'],
  exclude: [],

  /**
   * Capabilities for Chrome DevTools Protocol
   *
   * Connects to Tauri dev server running on localhost:1430
   * Tauri apps in dev mode expose a CDP-compatible interface
   */
  capabilities: [{
    browserName: 'chrome',
    'wdio:chromedriverOptions': {
      // Use system chromedriver or the one installed via npm
      binary: require('chromedriver').path
    },
    'wdio:devtoolsOptions': {
      // Connect to Tauri app via Chrome DevTools Protocol
      // Tauri dev server typically runs on port 1430
      // Note: This requires the Tauri app to be running in dev mode
    },
    // Maximize window to see full desktop UI
    'goog:chromeOptions': {
      args: [
        '--disable-gpu',
        '--disable-dev-shm-usage',
        '--no-sandbox'
      ]
    }
  }],

  /**
   * Test framework
   */
  framework: 'mocha',

  /**
   * Reporters
   */
  reporters: ['spec'],

  /**
   * Mocha options
   */
  mochaOpts: {
    timeout: 60000, // 60 second timeout for E2E tests
    ui: 'bdd'
  },

  /**
   * Before all tests: Start Tauri dev server
   *
   * Note: This is a placeholder. In production, you would:
   * 1. Build the Tauri app
   * 2. Start it in a background process
   * 3. Wait for it to be ready
   */
  before: async () => {
    const { spawn } = require('child_process');
    console.log('🚀 Starting Tauri app for E2E testing...');

    // Placeholder: In production, uncomment to start Tauri app
    // const tauriProcess = spawn('npm', ['run', 'tauri:dev'], {
    //   cwd: process.cwd(),
    //   detached: true,
    //   stdio: 'ignore'
    // });
    // tauriProcess.unref();

    // Wait for Tauri app to start
    await new Promise(resolve => setTimeout(resolve, 10000));
  },

  /**
   * After all tests: Cleanup
   *
   * Note: In production, you would:
   * 1. Stop the Tauri app
   * 2. Clean up any temporary files
   * 3. Close browser sessions
   */
  after: async () => {
    console.log('✅ Cleaning up after E2E tests...');

    // Placeholder: In production, uncomment to stop Tauri app
    // const { exec } = require('child_process');
    // exec('pkill -f "tauri dev"');
  },

  /**
   * Before each test: Navigate to base URL
   */
  beforeTest: async () => {
    // Tauri dev server runs on localhost:1430 by default
    await browser.url('http://localhost:1430');
  }
} as any;

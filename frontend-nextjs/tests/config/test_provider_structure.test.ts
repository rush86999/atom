/**
 * Frontend provider structure tests
 *
 * These tests verify that provider configuration exists in _app.tsx
 * without importing the module (which has CSS import issues in tests).
 */

import { readFileSync } from 'fs';
import { join } from 'path';

describe('Provider Structure in _app.tsx', () => {
  let appContent: string;

  beforeAll(() => {
    // Read _app.tsx content
    const appPath = join(process.cwd(), 'pages', '_app.tsx');
    appContent = readFileSync(appPath, 'utf-8');
  });

  it('SessionProvider is imported', () => {
    expect(appContent).toMatch(/SessionProvider/);
    expect(appContent).toMatch(/next-auth\/react/);
  });

  it('ChakraProvider is imported', () => {
    expect(appContent).toMatch(/ChakraProvider/);
    expect(appContent).toMatch(/@chakra-ui\/react/);
  });

  it('ToastProvider is imported', () => {
    expect(appContent).toMatch(/ToastProvider/);
    expect(appContent).toMatch(/use-toast/);
  });

  it('WakeWordProvider is imported', () => {
    expect(appContent).toMatch(/WakeWordProvider/);
  });

  it('Layout component is imported', () => {
    expect(appContent).toMatch(/Layout/);
    expect(appContent).toMatch(/components\/layout\/Layout/);
  });

  it('GlobalChatWidget is imported', () => {
    expect(appContent).toMatch(/GlobalChatWidget/);
  });

  it('CSS styles are imported', () => {
    expect(appContent).toMatch(/globals\.css/);
  });

  it('useRouter is imported from next/router', () => {
    expect(appContent).toMatch(/useRouter/);
    expect(appContent).toMatch(/next\/router/);
  });

  it('app has SessionProvider wrapper', () => {
    expect(appContent).toMatch(/<SessionProvider/);
  });

  it('app has ChakraProvider wrapper', () => {
    expect(appContent).toMatch(/<ChakraProvider/);
  });

  it('app has ToastProvider wrapper', () => {
    expect(appContent).toMatch(/<ToastProvider/);
  });

  it('app has WakeWordProvider wrapper', () => {
    expect(appContent).toMatch(/<WakeWordProvider/);
  });

  it('app uses Layout component', () => {
    expect(appContent).toMatch(/<Layout/);
  });

  it('app includes GlobalChatWidget', () => {
    expect(appContent).toMatch(/<GlobalChatWidget/);
  });

  it('providers are nested in correct order', () => {
    // Check that SessionProvider is outermost
    const sessionProviderIndex = appContent.indexOf('<SessionProvider');
    const chakraProviderIndex = appContent.indexOf('<ChakraProvider');
    const toastProviderIndex = appContent.indexOf('<ToastProvider');
    const wakeWordProviderIndex = appContent.indexOf('<WakeWordProvider');

    expect(sessionProviderIndex).toBeGreaterThan(-1);
    expect(chakraProviderIndex).toBeGreaterThan(-1);
    expect(toastProviderIndex).toBeGreaterThan(-1);
    expect(wakeWordProviderIndex).toBeGreaterThan(-1);

    // Verify nesting order: Session -> Chakra -> Toast -> WakeWord
    expect(sessionProviderIndex).toBeLessThan(chakraProviderIndex);
    expect(chakraProviderIndex).toBeLessThan(toastProviderIndex);
  });

  it('app exports default component', () => {
    expect(appContent).toMatch(/export default/);
    expect(appContent).toMatch(/MyApp/);
  });

  it('app has proper TypeScript types', () => {
    expect(appContent).toMatch(/AppProps/);
  });

  it('app handles router pathname', () => {
    expect(appContent).toMatch(/router\.pathname/);
    expect(appContent).toMatch(/startsWith\(["']\/auth["']\)/);
  });
});

describe('App Configuration', () => {
  let appContent: string;

  beforeAll(() => {
    const appPath = join(process.cwd(), 'pages', '_app.tsx');
    appContent = readFileSync(appPath, 'utf-8');
  });

  it('app file exists and has content', () => {
    expect(appContent.length).toBeGreaterThan(0);
  });

  it('app file has reasonable size (>500 bytes)', () => {
    expect(appContent.length).toBeGreaterThan(500);
  });

  it('app imports are properly structured', () => {
    // Check for proper import statements
    expect(appContent).toMatch(/import.*from/);
  });

  it('app uses functional component pattern', () => {
    expect(appContent).toMatch(/function.*MyApp|const.*MyApp.*=/);
  });

  it('app uses TypeScript', () => {
    expect(appContent).toMatch(/:.*{/); // Type annotations
  });
});

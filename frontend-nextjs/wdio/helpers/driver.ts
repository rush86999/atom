/**
 * Tauri WebDriver Helper for Cross-Platform Test Abstraction
 *
 * Provides a unified interface for E2E testing across platforms (web, desktop, mobile).
 * This helper abstracts WebDriverIO commands and provides Tauri-specific utilities.
 *
 * Design Principles:
 * - Resilient selectors: Use data-testid attributes instead of CSS classes
 * - Platform-agnostic: Same test code works across web, desktop, and mobile
 * - Explicit waits: No implicit waits to reduce flakiness
 * - Clear error messages: Fail fast with actionable error messages
 *
 * @see frontend-nextjs/wdio/README.md for usage examples
 */

import { browser, $, $$ } from '@wdio/globals';

export class TauriDriver {
  /**
   * Base URL for Tauri app (dev mode)
   */
  private readonly baseUrl = 'http://localhost:1430';

  /**
   * Default timeout for element visibility (ms)
   */
  private readonly defaultTimeout = 5000;

  /**
   * Navigate to a route within the Tauri app.
   *
   * @param route - Route path (e.g., '/agent/test-agent', '/settings')
   */
  async navigate(route: string): Promise<void> {
    const url = `${this.baseUrl}${route}`;
    await browser.url(url);
    console.log(`📍 Navigated to: ${url}`);
  }

  /**
   * Navigate to base URL.
   */
  async navigateToHome(): Promise<void> {
    await browser.url(this.baseUrl);
  }

  /**
   * Find element by test ID (resilient selector).
   *
   * @param testId - data-testid attribute value
   * @returns WebDriverIO element
   */
  async findByTestId(testId: string) {
    return $(`[data-testid="${testId}"]`);
  }

  /**
   * Find multiple elements by test ID.
   *
   * @param testId - data-testid attribute value
   * @returns Array of WebDriverIO elements
   */
  async findAllByTestId(testId: string) {
    return $$(`[data-testid="${testId}"]`);
  }

  /**
   * Wait for element to be visible.
   *
   * @param testId - data-testid attribute value
   * @param timeout - Timeout in milliseconds (default: 5000)
   */
  async waitForVisible(testId: string, timeout = this.defaultTimeout): Promise<void> {
    const element = await this.findByTestId(testId);
    await element.waitForDisplayed({ timeout });
    console.log(`✅ Element visible: ${testId}`);
  }

  /**
   * Wait for element to be present in DOM (not necessarily visible).
   *
   * @param testId - data-testid attribute value
   * @param timeout - Timeout in milliseconds (default: 5000)
   */
  async waitForPresent(testId: string, timeout = this.defaultTimeout): Promise<void> {
    const element = await this.findByTestId(testId);
    await element.waitForExist({ timeout });
    console.log(`✅ Element present: ${testId}`);
  }

  /**
   * Wait for element to be hidden (not displayed).
   *
   * @param testId - data-testid attribute value
   * @param timeout - Timeout in milliseconds (default: 5000)
   */
  async waitForHidden(testId: string, timeout = this.defaultTimeout): Promise<void> {
    const element = await this.findByTestId(testId);
    await element.waitForDisplayed({ reverse: true, timeout });
    console.log(`✅ Element hidden: ${testId}`);
  }

  /**
   * Check if element is visible.
   *
   * @param testId - data-testid attribute value
   * @returns True if element is visible
   */
  async isVisible(testId: string): Promise<boolean> {
    const element = await this.findByTestId(testId);
    return await element.isDisplayed();
  }

  /**
   * Check if element exists in DOM.
   *
   * @param testId - data-testid attribute value
   * @returns True if element exists
   */
  async isPresent(testId: string): Promise<boolean> {
    const element = await this.findByTestId(testId);
    return await element.isExisting();
  }

  /**
   * Get element text content.
   *
   * @param testId - data-testid attribute value
   * @returns Text content
   */
  async getText(testId: string): Promise<string> {
    const element = await this.findByTestId(testId);
    const text = await element.getText();
    return text;
  }

  /**
   * Click element.
   *
   * @param testId - data-testid attribute value
   */
  async click(testId: string): Promise<void> {
    const element = await this.findByTestId(testId);
    await element.click();
    console.log(`🖱️ Clicked: ${testId}`);
  }

  /**
   * Type text into input field.
   *
   * @param testId - data-testid attribute value
   * @param text - Text to type
   */
  async type(testId: string, text: string): Promise<void> {
    const element = await this.findByTestId(testId);
    await element.setValue(text);
    console.log(`⌨️ Typed into ${testId}: ${text}`);
  }

  /**
   * Clear input field and type text.
   *
   * @param testId - data-testid attribute value
   * @param text - Text to type
   */
  async clearAndType(testId: string, text: string): Promise<void> {
    const element = await this.findByTestId(testId);
    await element.clearValue();
    await element.setValue(text);
    console.log(`⌨️ Cleared and typed into ${testId}: ${text}`);
  }

  /**
   * Send message to agent chat input.
   *
   * @param message - Message to send
   */
  async sendAgentMessage(message: string): Promise<void> {
    await this.waitForVisible('agent-chat-input');
    await this.clearAndType('agent-chat-input', message);
    await this.click('send-message-button');
    console.log(`💬 Sent agent message: ${message}`);
  }

  /**
   * Get current page URL.
   *
   * @returns Current URL
   */
  async getUrl(): Promise<string> {
    return await browser.getUrl();
  }

  /**
   * Get page title.
   *
   * @returns Page title
   */
  async getTitle(): Promise<string> {
    return await browser.getTitle();
  }

  /**
   * Execute JavaScript in browser context.
   *
   * @param script - JavaScript code to execute
   * @param args - Arguments to pass to script
   * @returns Script result
   */
  async executeScript(script: string | Function, ...args: any[]): Promise<any> {
    return await browser.execute(script, ...args);
  }

  /**
   * Take screenshot.
   *
   * @param filename - Screenshot filename (without extension)
   */
  async screenshot(filename: string): Promise<void> {
    await browser.saveScreenshot(`./screenshots/${filename}.png`);
    console.log(`📸 Screenshot saved: ${filename}.png`);
  }

  /**
   * Wait for navigation to complete.
   *
   * @param timeout - Timeout in milliseconds (default: 10000)
   */
  async waitForNavigation(timeout = 10000): Promise<void> {
    await browser.waitUntil(
      async () => {
        const state = await this.executeScript('return document.readyState');
        return state === 'complete';
      },
      { timeout }
    );
    console.log(`✅ Navigation complete`);
  }

  /**
   * Refresh the page.
   */
  async refresh(): Promise<void> {
    await browser.refresh();
    console.log(`🔄 Page refreshed`);
  }

  /**
   * Go back in browser history.
   */
  async back(): Promise<void> {
    await browser.back();
    console.log(`⬅️ Navigated back`);
  }

  /**
   * Go forward in browser history.
   */
  async forward(): Promise<void> {
    await browser.forward();
    console.log(`➡️ Navigated forward`);
  }

  /**
   * Get all cookies.
   *
   * @returns Array of cookies
   */
  async getCookies(): Promise<Cookie[]> {
    return await browser.getCookies();
  }

  /**
   * Set cookie.
   *
   * @param cookie - Cookie object
   */
  async setCookie(cookie: Cookie): Promise<void> {
    await browser.setCookies(cookie);
  }

  /**
   * Clear all cookies.
   */
  async clearCookies(): Promise<void> {
    await browser.deleteCookies();
    console.log(`🍪 Cookies cleared`);
  }

  /**
   * Get local storage item.
   *
   * @param key - Storage key
   * @returns Storage value
   */
  async getLocalStorage(key: string): Promise<string | null> {
    return await this.executeScript(`return localStorage.getItem('${key}');`);
  }

  /**
   * Set local storage item.
   *
   * @param key - Storage key
   * @param value - Storage value
   */
  async setLocalStorage(key: string, value: string): Promise<void> {
    await this.executeScript(`return localStorage.setItem('${key}', '${value}');`);
  }

  /**
   * Clear local storage.
   */
  async clearLocalStorage(): Promise<void> {
    await this.executeScript('return localStorage.clear();');
    console.log(`💾 Local storage cleared`);
  }

  /**
   * Get session storage item.
   *
   * @param key - Storage key
   * @returns Storage value
   */
  async getSessionStorage(key: string): Promise<string | null> {
    return await this.executeScript(`return sessionStorage.getItem('${key}');`);
  }

  /**
   * Set session storage item.
   *
   * @param key - Storage key
   * @param value - Storage value
   */
  async setSessionStorage(key: string, value: string): Promise<void> {
    await this.executeScript(`return sessionStorage.setItem('${key}', '${value}');`);
  }

  /**
   * Clear session storage.
   */
  async clearSessionStorage(): Promise<void> {
    await this.executeScript('return sessionStorage.clear();');
    console.log(`💾 Session storage cleared`);
  }

  /**
   * Switch to iframe by test ID.
   *
   * @param testId - data-testid attribute value
   */
  async switchToIframe(testId: string): Promise<void> {
    const iframe = await this.findByTestId(testId);
    await browser.switchToFrame(iframe);
    console.log(`🔗 Switched to iframe: ${testId}`);
  }

  /**
   * Switch back to main frame from iframe.
   */
  async switchToMainFrame(): Promise<void> {
    await browser.switchToFrame(null);
    console.log(`🔗 Switched to main frame`);
  }

  /**
   * Accept alert dialog.
   */
  async acceptAlert(): Promise<void> {
    await browser.acceptAlert();
    console.log(`✅ Alert accepted`);
  }

  /**
   * Dismiss alert dialog.
   */
  async dismissAlert(): Promise<void> {
    await browser.dismissAlert();
    console.log(`❌ Alert dismissed`);
  }

  /**
   * Get alert text.
   *
   * @returns Alert text
   */
  async getAlertText(): Promise<string> {
    return await browser.getAlertText();
  }

  /**
   * Resize browser window.
   *
   * @param width - Window width
   * @param height - Window height
   */
  async resizeWindow(width: number, height: number): Promise<void> {
    await browser.setWindowSize(width, height);
    console.log(`📏 Window resized to ${width}x${height}`);
  }

  /**
   * Maximize browser window.
   */
  async maximizeWindow(): Promise<void> {
    await browser.maximizeWindow();
    console.log(`📏 Window maximized`);
  }
}

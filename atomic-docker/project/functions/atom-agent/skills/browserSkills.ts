const { chromium } = require('playwright');

class BrowserSkill {
  constructor() {
    this.browser = null;
    this.page = null;
  }

  async start() {
    this.browser = await chromium.launch();
    this.page = await this.browser.newPage();
  }

  async stop() {
    await this.browser.close();
  }

  async goto(url) {
    await this.page.goto(url);
  }

  async click(selector) {
    await this.page.click(selector);
  }

  async type(selector, text) {
    await this.page.type(selector, text);
  }

  async extract(selector, attribute) {
    const element = await this.page.$(selector);
    if (attribute) {
      return await element.getAttribute(attribute);
    }
    return await element.textContent();
  }

  async screenshot(path) {
    await this.page.screenshot({ path });
  }
}

export async function handleBrowser(entities: any): Promise<string> {
  let textResponse: string;
  try {
    const browserSkill = new BrowserSkill();
    await browserSkill.start();
    const { action, url, selector, text, path } = entities;
    switch (action) {
      case 'goto':
        await browserSkill.goto(url);
        textResponse = `Navigated to ${url}`;
        break;
      case 'click':
        await browserSkill.click(selector);
        textResponse = `Clicked on ${selector}`;
        break;
      case 'type':
        await browserSkill.type(selector, text);
        textResponse = `Typed "${text}" into ${selector}`;
        break;
      case 'extract':
        const extractedText = await browserSkill.extract(selector);
        textResponse = `Extracted text: ${extractedText}`;
        break;
      case 'screenshot':
        await browserSkill.screenshot(path);
        textResponse = `Took a screenshot and saved it to ${path}`;
        break;
      default:
        textResponse = "Sorry, I don't know how to do that with the browser.";
    }
    await browserSkill.stop();
  } catch (error) {
    console.error(`Error in NLU Intent "Browser":`, error.message, error.stack);
    textResponse = 'Sorry, an error occurred while controlling the browser.';
  }
  return textResponse;
}

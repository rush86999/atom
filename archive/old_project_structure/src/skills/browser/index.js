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

module.exports = BrowserSkill;

import { Agent } from 'browser-use';
import { Tool } from "langchain/tools";

class OpenBrowser extends Tool {
    name = "open-browser";
    description = "Opens a browser to a specified URL.";

    async _call(url: string): Promise<string> {
        const agent = new Agent();
        await agent.init();
        await agent.goTo(url);
        return "Browser opened.";
    }
}

class Click extends Tool {
    name = "click";
    description = "Clicks on an element specified by a selector.";

    async _call(selector: string): Promise<string> {
        const agent = new Agent();
        await agent.init();
        await agent.click(selector);
        return "Element clicked.";
    }
}

class Type extends Tool {
    name = "type";
    description = "Types text into an element specified by a selector.";

    async _call(input: { selector: string, text: string }): Promise<string> {
        const agent = new Agent();
        await agent.init();
        await agent.type(input.selector, input.text);
        return "Text typed.";
    }
}

class Extract extends Tool {
    name = "extract";
    description = "Extracts text or an attribute from an element specified by a selector.";

    async _call(input: { selector: string, attribute?: string }): Promise<string> {
        const agent = new Agent();
        await agent.init();
        const page = await agent.getPage();
        const element = await page.waitForSelector(input.selector);
        if (input.attribute) {
            return await element.getAttribute(input.attribute) || "";
        } else {
            return await element.textContent() || "";
        }
    }
}

class Screenshot extends Tool {
    name = "screenshot";
    description = "Takes a screenshot of the current page.";

    async _call(path: string): Promise<string> {
        const agent = new Agent();
        await agent.init();
        const page = await agent.getPage();
        await page.screenshot({ path });
        return "Screenshot taken.";
    }
}

export const browserSkills = [
    new OpenBrowser(),
    new Click(),
    new Type(),
    new Extract(),
    new Screenshot(),
];

"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.runShopifyBusinessManager = runShopifyBusinessManager;
const shopifySkills_1 = require("../skills/shopifySkills");
const slackSkills_1 = require("atomic-docker/project/functions/atom-agent/skills/slackSkills");
async function runShopifyBusinessManager(userId, slackChannelId) {
    console.log(`[ShopifyBusinessManager] Starting Shopify business manager for user ${userId}.`);
    const result = {
        success: false,
        message: '',
        errors: [],
    };
    // 1. Get top selling products
    const topSellingProductsResponse = await (0, shopifySkills_1.getTopSellingProducts)(userId);
    if (!topSellingProductsResponse.ok || !topSellingProductsResponse.data) {
        const errorMsg = `Failed to get top selling products: ${topSellingProductsResponse.error?.message}`;
        console.error(`[ShopifyBusinessManager] ${errorMsg}`);
        result.message = errorMsg;
        result.errors.push(errorMsg);
        return result;
    }
    // 2. Format the message
    const products = topSellingProductsResponse.data.products;
    let message = 'Top selling products:\n';
    if (products.length === 0) {
        message = 'No top selling products found.';
    }
    else {
        products.forEach(product => {
            message += `- ${product.title}: ${product.count} sold\n`;
        });
    }
    // 3. Send Slack message
    await (0, slackSkills_1.sendSlackMessage)(userId, slackChannelId, message);
    result.success = true;
    result.message = `Successfully ran Shopify business manager.`;
    console.log(`[ShopifyBusinessManager] ${result.message}`);
    return result;
}
//# sourceMappingURL=shopifyBusinessManager.js.map
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.postTweet = postTweet;
const socialMediaSkills_1 = require("../skills/socialMediaSkills");
async function postTweet(userId, text) {
    console.log(`[SocialMediaOrchestrator] Posting tweet for user ${userId}.`);
    const result = await (0, socialMediaSkills_1.postToTwitter)(userId, text);
    if (result.ok) {
        console.log(`[SocialMediaOrchestrator] Successfully posted tweet for user ${userId}.`);
    }
    else {
        console.error(`[SocialMediaOrchestrator] Failed to post tweet for user ${userId}. Error: ${result.error.message}`);
    }
    return result;
}
//# sourceMappingURL=socialMediaOrchestrator.js.map
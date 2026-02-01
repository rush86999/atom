"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.postToTwitter = postToTwitter;
const twitter_api_sdk_1 = require("twitter-api-sdk");
const authService_1 = require("../services/authService");
async function postToTwitter(userId, text) {
    const credentials = await (0, authService_1.getTwitterCredentials)(userId);
    if (!credentials) {
        return {
            ok: false,
            error: {
                code: "UNAUTHORIZED",
                message: "Twitter credentials not found for this user.",
            },
        };
    }
    try {
        const client = new twitter_api_sdk_1.Client(credentials.bearerToken);
        await client.tweets.createTweet({ text });
        return { ok: true, data: { success: true } };
    }
    catch (error) {
        return {
            ok: false,
            error: {
                code: "TWITTER_API_ERROR",
                message: error.message,
            },
        };
    }
}
//# sourceMappingURL=socialMediaSkills.js.map
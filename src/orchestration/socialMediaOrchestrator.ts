import { postToTwitter, postToLinkedIn } from '../skills/socialMediaSkills';
import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
import { ContentCreationAgent } from '../skills/contentCreationSkill';
import { getLLMService } from '../services/llmService';

export async function postToTwitter(userId: string, text: string): Promise<SkillResponse<{ success: boolean }>> {
    console.log(`[SocialMediaOrchestrator] Posting tweet for user ${userId}.`);
    const result = await postToTwitter(userId, text);
    if (result.ok) {
        console.log(`[SocialMediaOrchestrator] Successfully posted tweet for user ${userId}.`);
    } else {
        console.error(`[SocialMediaOrchestrator] Failed to post tweet for user ${userId}. Error: ${result.error.message}`);
    }
    return result;
}

export async function generateSocialMediaPost(userId: string, topic: string): Promise<SkillResponse<{ content: string }>> {
    console.log(`[SocialMediaOrchestrator] Generating post for user ${userId} on topic: ${topic}.`);
    try {
        const llmService = getLLMService();
        const contentCreationAgent = new ContentCreationAgent(llmService);

        const contentResponse = await contentCreationAgent.analyze({
            userInput: `Generate a short social media post about ${topic}`,
            userId,
        });

        if (contentResponse.generatedContent) {
            return { ok: true, data: { content: contentResponse.generatedContent } };
        } else {
            return {
                ok: false,
                error: {
                    code: "CONTENT_GENERATION_FAILED",
                    message: "Failed to generate content for social media post.",
                },
            };
        }
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: "CONTENT_GENERATION_ERROR",
                message: error.message,
            },
        };
    }
}

export async function postToLinkedIn(userId: string, text: string): Promise<SkillResponse<{ success: boolean }>> {
    console.log(`[SocialMediaOrchestrator] Posting to LinkedIn for user ${userId}.`);
    const result = await postToLinkedIn(userId, text);
    if (result.ok) {
        console.log(`[SocialMediaOrchestrator] Successfully posted to LinkedIn for user ${userId}.`);
    } else {
        console.error(`[SocialMediaOrchestrator] Failed to post to LinkedIn for user ${userId}. Error: ${result.error.message}`);
    }
    return result;
}

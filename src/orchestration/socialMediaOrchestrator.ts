import { postToTwitter } from '../skills/socialMediaSkills';
import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';

export async function postTweet(userId: string, text: string): Promise<SkillResponse<{ success: boolean }>> {
    console.log(`[SocialMediaOrchestrator] Posting tweet for user ${userId}.`);
    const result = await postToTwitter(userId, text);
    if (result.ok) {
        console.log(`[SocialMediaOrchestrator] Successfully posted tweet for user ${userId}.`);
    } else {
        console.error(`[SocialMediaOrchestrator] Failed to post tweet for user ${userId}. Error: ${result.error.message}`);
    }
    return result;
}

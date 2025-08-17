import schedule from 'node-schedule';
import { postToTwitter, postToLinkedIn } from '../orchestration/socialMediaOrchestrator';
import { getPendingScheduledPosts, updateScheduledPostStatus } from './db'; // Assuming db service exists

interface ScheduledPost {
    id: number;
    user_id: string;
    platform: string;
    content: string;
    scheduled_at: Date;
}

export class SchedulerService {
    private static instance: SchedulerService;

    private constructor() {
        this.initialize();
    }

    public static getInstance(): SchedulerService {
        if (!SchedulerService.instance) {
            SchedulerService.instance = new SchedulerService();
        }
        return SchedulerService.instance;
    }

    private async initialize() {
        // Run every minute to check for new scheduled posts
        schedule.scheduleJob('* * * * *', async () => {
            console.log('Checking for scheduled posts...');
            const posts = await getPendingScheduledPosts();
            posts.forEach(post => this.schedulePost(post));
        });
    }

    private schedulePost(post: ScheduledPost) {
        schedule.scheduleJob(post.scheduled_at, async () => {
            console.log(`Executing scheduled post ${post.id}...`);
            let result;
            if (post.platform === 'twitter') {
                result = await postToTwitter(post.user_id, post.content);
            } else if (post.platform === 'linkedin') {
                result = await postToLinkedIn(post.user_id, post.content);
            }

            if (result && result.ok) {
                await updateScheduledPostStatus(post.id, 'sent');
                console.log(`Scheduled post ${post.id} sent successfully.`);
            } else {
                await updateScheduledPostStatus(post.id, 'failed');
                console.error(`Failed to send scheduled post ${post.id}.`);
            }
        });
    }
}

// To start the service
SchedulerService.getInstance();

import { SkillResponse, Tweet } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function getTwitterTimeline(userId: string): Promise<SkillResponse<{
    tweets: Tweet[];
}>>;
export declare function postTweet(userId: string, status: string): Promise<SkillResponse<Tweet>>;
export declare function searchTweets(userId: string, query: string): Promise<SkillResponse<{
    tweets: Tweet[];
}>>;
export declare function retweet(userId: string, tweetId: string): Promise<SkillResponse<Tweet>>;
export declare function likeTweet(userId: string, tweetId: string): Promise<SkillResponse<Tweet>>;
export declare function getTweet(userId: string, tweetId: string): Promise<SkillResponse<Tweet>>;

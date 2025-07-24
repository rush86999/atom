import { NotionTask } from '../../types';
import { createNotionPage } from './notionAndResearchSkills';
import { searchWeb } from './webResearchSkills';
import { analyzeSentiment } from '../../desktop/tauri/src/lib/sentiment';

async function getCompetitorNews(competitor: string): Promise<string> {
    const searchResults = await searchWeb(`news about ${competitor}`);
    // In a real app, we would process these search results to extract relevant information.
    // For now, we'll just return the first result.
    return searchResults[0]?.url || '';
}

async function analyzeCompetitorWebsite(competitor: string): Promise<string> {
    const searchResults = await searchWeb(`official website of ${competitor}`);
    // In a real app, we would scrape the website to extract relevant information.
    // For now, we'll just return the URL of the website.
    return searchResults[0]?.url || '';
}

export async function runCompetitorAnalysis(userId: string, competitors: string[], notionDatabaseId: string): Promise<void> {
    for (const competitor of competitors) {
        const news = await getCompetitorNews(competitor);
        const website = await analyzeCompetitorWebsite(competitor);

        const summary = `
            Competitor: ${competitor}
            Latest News: ${news}
            Website: ${website}
        `;

        await createNotionPage(userId, {
            parent: { database_id: notionDatabaseId },
            properties: {
                title: {
                    title: [
                        {
                            text: {
                                content: `Competitor Analysis: ${competitor}`,
                            },
                        },
                    ],
                },
            },
            children: [
                {
                    object: 'block',
                    type: 'paragraph',
                    paragraph: {
                        rich_text: [
                            {
                                type: 'text',
                                text: {
                                    content: summary,
                                },
                            },
                        ],
                    },
                },
            ],
        });
    }
}

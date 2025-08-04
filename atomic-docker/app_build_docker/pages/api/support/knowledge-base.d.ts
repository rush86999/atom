import type { NextApiRequest, NextApiResponse } from 'next';
export interface Article {
    id: string;
    title: string;
    content: string;
    category: 'HR' | 'IT' | 'Engineering';
    lastUpdated: string;
}
/**
 * API handler for searching the knowledge base.
 * It filters articles based on a query parameter and simulates a network delay.
 *
 * @param {NextApiRequest} req - The incoming API request. Expects a 'q' query parameter.
 * @param {NextApiResponse<Article[] | { message: string }>} res - The outgoing API response.
 */
export default function handler(req: NextApiRequest, res: NextApiResponse<Article[] | {
    message: string;
}>): void;

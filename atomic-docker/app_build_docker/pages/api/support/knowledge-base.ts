import type { NextApiRequest, NextApiResponse } from 'next';

// Define the structure for a knowledge base article
export interface Article {
  id: string;
  title: string;
  content: string;
  category: 'HR' | 'IT' | 'Engineering';
  lastUpdated: string;
}

// Mock data representing a company's internal knowledge base (like Confluence or Notion)
const allArticles: Article[] = [
  {
    id: 'kb-1',
    title: 'How to Set Up Your VPN',
    content:
      'To set up your VPN, please download the GlobalProtect client from the IT portal and follow the on-screen instructions. Contact IT support for any issues.',
    category: 'IT',
    lastUpdated: '2024-06-15',
  },
  {
    id: 'kb-2',
    title: 'Submitting Expense Reports',
    content:
      'All expense reports must be submitted through the "Expenses" app on your employee dashboard. Please ensure all receipts are attached.',
    category: 'HR',
    lastUpdated: '2024-07-01',
  },
  {
    id: 'kb-3',
    title: 'Requesting Time Off',
    content:
      'Paid time off (PTO) can be requested via the Workday portal under the "Absence" section. Requests should be submitted at least two weeks in advance.',
    category: 'HR',
    lastUpdated: '2024-05-20',
  },
  {
    id: 'kb-4',
    title: 'Git Branching Strategy',
    content:
      'Our standard Git branching strategy is GitFlow. Please create feature branches from `develop` and submit pull requests for review.',
    category: 'Engineering',
    lastUpdated: '2024-07-25',
  },
  {
    id: 'kb-5',
    title: 'Accessing Staging Environments',
    content:
      'To access the staging environment, you must be connected to the VPN. The credentials can be found in the secure password vault.',
    category: 'Engineering',
    lastUpdated: '2024-07-18',
  },
  {
    id: 'kb-6',
    title: 'Resetting Your Corporate Password',
    content:
      'If you have forgotten your password, you can reset it by visiting the login page and clicking "Forgot Password". A reset link will be sent to your recovery email.',
    category: 'IT',
    lastUpdated: '2024-07-28',
  },
];

/**
 * API handler for searching the knowledge base.
 * It filters articles based on a query parameter and simulates a network delay.
 *
 * @param {NextApiRequest} req - The incoming API request. Expects a 'q' query parameter.
 * @param {NextApiResponse<Article[] | { message: string }>} res - The outgoing API response.
 */
export default function handler(
  req: NextApiRequest,
  res: NextApiResponse<Article[] | { message: string }>
) {
  // Extract the search query from the request.
  const { q: searchQuery } = req.query;

  // Simulate a network delay of 1 second.
  setTimeout(() => {
    // If there's no search query, return all articles.
    if (!searchQuery || typeof searchQuery !== 'string') {
      res.status(200).json(allArticles);
      return;
    }

    // Filter articles based on the search query (case-insensitive).
    const lowercasedQuery = searchQuery.toLowerCase();
    const results = allArticles.filter(
      (article) =>
        article.title.toLowerCase().includes(lowercasedQuery) ||
        article.content.toLowerCase().includes(lowercasedQuery)
    );

    res.status(200).json(results);
  }, 1000); // 1-second delay
}

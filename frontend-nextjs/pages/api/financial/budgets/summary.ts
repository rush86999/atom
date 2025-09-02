import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const userId = req.query.userId as string;
    const { period = 'current', month, categories } = req.query;

    if (!userId) {
      return res.status(400).json({ error: 'User ID required' });
    }

    // Mock budget data for demonstration
    const mockBudgetSummary = {
      totalBudget: 2500,
      spent: 1837.5,
      remaining: 662.5,
      categories: [
        {
          category: 'Dining',
          budgeted: 500,
          spent: 485.75,
          remaining: 14.25,
          utilization: 97.15,
        },
        {
          category: 'Groceries',
          budgeted: 400,
          spent: 312.8,
          remaining: 87.2,
          utilization: 78.2,
        },
        {
          category: 'Transportation',
          budgeted: 300,
          spent: 198.45,
          remaining: 101.55,
          utilization: 66.15,
        },
        {
          category: 'Entertainment',
          budgeted: 200,
          spent: 235.3,
          remaining: -35.3,
          utilization: 117.65,
        },
        {
          category: 'Shopping',
          budgeted: 350,
          spent: 178.2,
          remaining: 171.8,
          utilization: 50.91,
        },
        {
          category: 'Utilities',
          budgeted: 250,
          spent: 187.0,
          remaining: 63.0,
          utilization: 74.8,
        },
        {
          category: 'Other',
          budgeted: 500,
          spent: 240.0,
          remaining: 260.0,
          utilization: 48.0,
        },
      ],
    };

    res.status(200).json({ data: mockBudgetSummary });
  } catch (error) {
    console.error('Budget summary error:', error);
    res.status(500).json({ error: 'Failed to retrieve budget summary' });
  }
}

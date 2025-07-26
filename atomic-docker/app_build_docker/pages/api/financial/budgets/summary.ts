import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
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
      spent: 1837.50,
      remaining: 662.50,
      categories: [
        {
          category: 'Dining',
          budgeted: 500,
          spent: 485.75,
          remaining: 14.25,
          utilization: 97.15
        },
        {
          category: 'Groceries',
          budgeted: 400,
          spent: 312.80,
          remaining: 87.20,
          utilization: 78.20
        },
        {
          category: 'Transportation',
          budgeted: 300,
          spent: 198.45,
          remaining: 101.55,
          utilization: 66.15
        },
        {
          category: 'Entertainment',
          budgeted: 200,
          spent: 235.30,
          remaining: -35.30,
          utilization: 117.65
        },
        {
          category: 'Shopping',
          budgeted: 350,
          spent: 178.20,
          remaining: 171.80,
          utilization: 50.91
        },
        {
          category: 'Utilities',
          budgeted: 250,
          spent: 187.00,
          remaining: 63.00,
          utilization: 74.80
        },
        {
          category: 'Other',
          budgeted: 500,
          spent: 240.00,
          remaining: 260.00,
          utilization: 48.00
        }
      ]
    };

    res.status(200).json({ data: mockBudgetSummary });
  } catch (error) {
    console.error('Budget summary error:', error);
    res.status(500).json({ error: 'Failed to retrieve budget summary' });
  }
}

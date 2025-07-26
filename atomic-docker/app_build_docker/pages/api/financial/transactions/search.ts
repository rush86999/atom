import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { userId, query, category, amountRange, dateRange, limit = 50 } = req.body;

    if (!userId) {
      return res.status(400).json({ error: 'User ID required' });
    }

    // Mock transaction data for demonstration
    const mockTransactions = [
      {
        id: 'txn_1',
        name: 'Grocery Store',
        amount: -127.45,
        date: '2024-06-10',
        category: 'Groceries',
        merchant: 'Whole Foods Market',
        description: 'Weekly groceries - organic produce, coffee, snacks'
      },
      {
        id: 'txn_2',
        name: 'Amazon Purchase',
        amount: -89.99,
        date: '2024-06-08',
        category: 'Shopping',
        merchant: 'Amazon',
        description: 'Books and household items'
      },
      {
        id: 'txn_3',
        name: 'Coffee Shop',
        amount: -6.75,
        date: '2024-06-07',
        category: 'Dining',
        merchant: 'Starbucks',
        description: 'Coffee and breakfast'
      },
      {
        id: 'txn_4',
        name: 'Gas Station',
        amount: -45.30,
        date: '2024-06-06',
        category: 'Transportation',
        merchant: 'Shell',
        description: 'Premium gasoline'
      },
      {
        id: 'txn_5',
        name: 'Netflix Subscription',
        amount: -15.99,
        date: '2024-06-05',
        category: 'Entertainment',
        merchant: 'Netflix',
        description: 'Monthly streaming service'
      },
      {
        id: 'txn_6',
        name: 'Salary Deposit',
        amount: 3850.00,
        date: '2024-06-01',
        category: 'Income',
        merchant: 'Employer Inc.',
        description: 'Monthly salary'
      },
      {
        id: 'txn_7',
        name: 'Restaurants',
        amount: -67.50,
        date: '2024-06-09',
        category: 'Dining',
        merchant: 'Local Restaurant',
        description: 'Dinner with friends'
      },
      {
        id: 'txn_8',
        name: 'Electric Bill',
        amount: -85.20,
        date: '2024-06-05',
        category: 'Utilities',
        merchant: 'Electric Company',
        description: 'Monthly electricity bill'
      }
    ];

    // Filter by query if provided
    let filteredTransactions = mockTransactions;

    if (query) {
      const searchQuery = query.toLowerCase();
      filteredTransactions = filteredTransactions.filter(t =>
        t.name.toLowerCase().includes(searchQuery) ||
        t.description.toLowerCase().includes(searchQuery) ||
        t.category.toLowerCase().includes(searchQuery)
      );
    }

    // Filter by category if provided
    if (category) {
      filteredTransactions = filteredTransactions.filter(t =>
        t.category.toLowerCase() === category.toLowerCase()
      );
    }

    // Filter by date range if provided
    if (dateRange && dateRange.start && dateRange.end) {
      const startDate = new Date(dateRange.start);
      const endDate = new Date(dateRange.end);

      filteredTransactions = filteredTransactions.filter(t => {
        const transactionDate = new Date(t.date);
        return transactionDate >= startDate && transactionDate <= endDate;
      });
    }

    // Filter by amount range if provided
    if (amountRange) {
      filteredTransactions = filteredTransactions.filter(t => {
        const absAmount = Math.abs(t.amount);
        if (amountRange.min !== undefined && absAmount < amountRange.min) return false;
        if (amountRange.max !== undefined && absAmount > amountRange.max) return false;
        return true;
      });
    }

    // Limit results
    const limitedTransactions = filteredTransactions.slice(0, limit);

    // Calculate summary statistics
    const totalSpent = limitedTransactions
      .filter(t => t.amount < 0)
      .reduce((sum, t) => sum + Math.abs(t.amount), 0);

    const totalIncome = limitedTransactions
      .filter(t => t.amount > 0)
      .reduce((sum, t) => sum + t.amount, 0);

    const spendingByCategory = limitedTransactions
      .filter(t => t.amount < 0)
      .reduce((acc, t) => {
        acc[t.category] = (acc[t.category] || 0) + Math.abs(t.amount);
        return acc;
      }, {} as Record<string, number>);

    res.status(200).json({
      transactions: limitedTransactions,
      summary: {
        totalTransactions: limitedTransactions.length,
        totalSpent,
        totalIncome,
        netFlow: totalIncome - totalSpent,
        categories: Object.entries(spendingByCategory).map(([category, amount]) => ({
          category,
          amount,
          transactionCount: limitedTransactions.filter(t => t.category === category).length
        }))
      }
    });
  } catch (error) {
    console.error('Transactions search error:', error);
    res.status(500).json({ error: 'Failed to search transactions' });
  }
}

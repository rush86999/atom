
import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'GET') {
    return handleGetGoals(req, res);
  } else if (req.method === 'POST') {
    return handleCreateGoal(req, res);
  } else if (req.method === 'PUT') {
    return handleUpdateGoal(req, res);
  } else {
    return res.status(405).json({ error: 'Method not allowed' });
  }
}

async function handleGetGoals(req: NextApiRequest, res: NextApiResponse) {
  try {
    const userId = req.query.userId as string;
    const goalType = req.query.goalType as string;

    if (!userId) {
      return res.status(400).json({ error: 'User ID required' });
    }

    // Mock financial goals data
    const mockGoals = [
      {
        id: 'goal_001',
        name: 'Emergency Fund',
        description: '3-6 months of living expenses',
        targetAmount: 10000,
        current: 6500,
        progress: 65,
        goalType: 'emergency',
        targetDate: '2024-12-31',
        status: 'active',
        priority: 1,
        monthlyContribution: 500,
        daysLeft: 184,
        tips: ['Consider setting up automatic transfers', 'Use a high-yield savings account']
      },
      {
        id: 'goal_002',
        name: 'Vacation to Hawaii',
        description: 'Dream vacation with family',
        targetAmount: 6000,
        current: 1200,
        progress: 20,
        goalType: 'vacation',
        targetDate: '2025-06-15',
        status: 'active',
        priority: 2,
        monthlyContribution: 200,
        daysLeft: 380,
        tips: ['Set aside tax refund', 'Use cashback credit towards flights']
      },
      {
        id: 'goal_003',
        name: 'New Car Down Payment',
        description: '20% down payment on new vehicle',
        targetAmount: 8000,
        current: 3500,
        progress: 43.75,
        goalType: 'purchase',
        targetDate: '2025-03-01',
        status: 'active',
        priority: 3,
        monthlyContribution: 300,
        daysLeft: 250,
        tips: ['Review car financing options', 'Consider Certified Pre-Owned vehicles']
      },
      {
        id: 'goal_004',
        name: 'Home Down Payment',
        description: '20% down payment on starter home',
        targetAmount: 50000,
        current: 8500,
        progress: 17,
        goalType: 'purchase',
        targetDate: '2026-12-31',
        status: 'active',
        priority: 4,
        monthlyContribution: 600,
        daysLeft: 925,
        tips: ['Explore first-time homebuyer programs', 'Consider FHA loans for lower down payment']
      }
    ];

    // Filter by goal type if provided
    let filteredGoals = mockGoals;
    if (goalType) {
      filteredGoals = mockGoals.filter(goal => goal.goalType === goalType);
    }

    res.status(200).json({
      goals: filteredGoals,
      summary: {
        totalGoals: filteredGoals.length,
        totalTarget: filteredGoals.reduce((sum, goal) => sum + goal.targetAmount, 0),
        totalSaved: filteredGoals.reduce((sum, goal) => sum + goal.current, 0),
        totalProgress: (filteredGoals.reduce((sum, goal) => sum + goal.current, 0) /
                      filteredGoals.reduce((sum, goal) => sum + goal.targetAmount, 0)) * 100
      }
    });
  } catch (error) {
    console.error('Goals fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch financial goals' });
  }
}

async function handleCreateGoal(req: NextApiRequest, res: NextApiResponse) {
  try {
    const { userId, name, targetAmount, goalType, currentAmount = 0, targetDate, description, priority = 3 } = req.body;

    if (!userId || !name || !targetAmount || !goalType) {
      return res.status(400).json({ error: 'Missing required fields: userId, name, targetAmount, goalType' });
    }

    // In a real implementation, this would insert into database
    const newGoal = {
      id: `goal_${Date.now()}`,
      name,
      description: description || '',
      targetAmount,
      current: currentAmount,
      progress: (currentAmount / targetAmount) * 100,
      goalType,
      targetDate,
      status: 'active',
      priority,
      createdAt: new Date().toISOString()
    };

    res.status(201).json({ data: newGoal });
  } catch (error) {
    console.error('Goal creation error:', error);
    res.status(500).json({ error: 'Failed to create financial goal' });
  }
}

async function handleUpdateGoal(req: NextApiRequest, res: NextApiResponse) {
  try {
    const { goalId, userId, currentAmount, targetAmount, name, targetDate } = req.body;

    if (!goalId || !userId) {
      return res.status(400).json({ error: 'Goal ID and User ID required' });
    }

    // Mock update response
    const updatedGoal = {
      id: goalId,
      name,
      targetAmount,
      current: currentAmount,
      progress: (currentAmount / targetAmount) * 100,
      targetDate
    };

    res.status(200).json({ data: updatedGoal });
  } catch (error) {
    console.error('Goal update error:', error);
    res.status(500).json({ error: 'Failed to update financial goal' });
  }
}

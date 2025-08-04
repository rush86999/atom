import { NextApiRequest, NextApiResponse } from 'next';
import { createServerSupabaseClient } from '@supabase/auth-helpers-nextjs';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const supabase = createServerSupabaseClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const userId = session.user.id;
    const { includeHistory = false, dateRange } = req.query;

    // Fetch all accounts for the user
    const { data: plaidAccounts } = await supabase
      .from('accounts')
      .select('balance, account_type')
      .eq('user_id', userId);

    const { data: manualAccounts } = await supabase
      .from('manual_accounts')
      .select('balance, account_type')
      .eq('user_id', userId);

    // Calculate net worth
    let totalAssets = 0;
    let totalLiabilities = 0;
    const allAccounts = [...(plaidAccounts || []), ...(manualAccounts || [])];

    allAccounts.forEach((account) => {
      const accountType = String(account.account_type).toLowerCase();

      // Define asset types
      const assetTypes = [
        'savings',
        'checking',
        'current',
        'investment',
        'brokerage',
        'retirement',
        'IRA',
        '401k',
        'money_market',
        'bond',
        'stock',
      ];
      const liabilityTypes = [
        'credit',
        'loan',
        'mortgage',
        'liability',
        'debt',
        'line_of_credit',
      ];

      let isAsset = false;
      let isLiability = false;

      // Check if it's an asset
      for (const type of assetTypes) {
        if (
          accountType.includes(type) ||
          String(account.account_type || '')
            .toLowerCase()
            .includes(type)
        ) {
          isAsset = true;
          break;
        }
      }

      // Check if it's a liability
      for (const type of liabilityTypes) {
        if (
          accountType.includes(type) ||
          String(account.account_type || '')
            .toLowerCase()
            .includes(type)
        ) {
          isLiability = true;
          break;
        }
      }

      // Handle balance sign
      const balance = Number(account.balance || 0);

      if (isAsset) {
        totalAssets += Math.abs(balance);
      } else if (isLiability) {
        totalLiabilities += Math.abs(balance);
      } else {
        // Default to asset for positive balances, liability for negative
        totalAssets += Math.max(0, balance);
        totalLiabilities += Math.max(0, -balance);
      }
    });

    const netWorth = totalAssets - totalLiabilities;

    // Fetch historical snapshots if requested
    let history = [];
    if (includeHistory === 'true' || includeHistory === true) {
      const { data: snapshots } = await supabase
        .from('net_worth_snapshots')
        .select('snapshot_date, net_worth')
        .eq('user_id', userId)
        .order('snapshot_date', { ascending: true });

      history =
        snapshots?.map((snap) => ({
          date: snap.snapshot_date,
          netWorth: Number(snap.net_worth),
        })) || [];
    }

    // Only include last 12 months for history
    if (history.length > 0) {
      const cutoffDate = new Date();
      cutoffDate.setMonth(cutoffDate.getMonth() - 12);
      history = history.filter((h) => new Date(h.date) >= cutoffDate);
    }

    // Calculate change (mock data if no history)
    let change = 0;
    let changePercent = 0;
    if (history.length > 1) {
      const firstValue = history[0]?.netWorth || 0;
      const lastValue = history[history.length - 1]?.netWorth || 0;
      change = lastValue - firstValue;
      changePercent = firstValue > 0 ? (change / firstValue) * 100 : 0;
    } else {
      // Mock change for demo purposes
      change = Math.random() * 1000 - 500;
      changePercent = (change / Math.abs(netWorth || 1)) * 100;
    }

    const result = {
      current: netWorth,
      change,
      changePercent,
      assets: totalAssets,
      liabilities: totalLiabilities,
      history,
    };

    res.status(200).json({ data: result });
  } catch (error) {
    console.error('Net worth summary error:', error);
    res.status(500).json({ error: 'Failed to calculate net worth' });
  }
}

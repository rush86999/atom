import { callHasura } from '../_utils/hasura';
import { sendEmail } from '../_utils/email'; // Assuming an email utility exists

const GET_USERS_QUERY = `
  query GetUsers {
    users {
      id
      email
    }
  }
`;

const GET_BUDGETS_QUERY = `
  query GetBudgets($userId: String!) {
    budgets(where: {user_id: {_eq: $userId}, is_active: {_eq: true}}) {
      id
      name
      category
      amount
      start_date
      end_date
    }
  }
`;

const GET_TRANSACTIONS_QUERY = `
  query GetTransactions($userId: String!, $startDate: date!, $endDate: date!) {
    transactions(where: {account: {user_id: {_eq: $userId}}, date: {_gte: $startDate, _lte: $endDate}}) {
      amount
      category
    }
  }
`;

async function checkBudgets() {
  console.log('Running budget check...');

  try {
    // 1. Get all users
    const usersResponse = await callHasura({ query: GET_USERS_QUERY });
    if (usersResponse.errors) {
      throw new Error(usersResponse.errors[0].message);
    }
    const users = usersResponse.data.users;

    for (const user of users) {
      // 2. Get budgets for the user
      const budgetsResponse = await callHasura({
        query: GET_BUDGETS_QUERY,
        variables: { userId: user.id },
      });
      if (budgetsResponse.errors) {
        console.error(`Error getting budgets for user ${user.id}:`, budgetsResponse.errors[0].message);
        continue;
      }
      const budgets = budgetsResponse.data.budgets;

      for (const budget of budgets) {
        // 3. Get transactions for the budget period
        const transactionsResponse = await callHasura({
          query: GET_TRANSACTIONS_QUERY,
          variables: {
            userId: user.id,
            startDate: budget.start_date,
            endDate: budget.end_date || new Date().toISOString().split('T')[0],
          },
        });
        if (transactionsResponse.errors) {
          console.error(`Error getting transactions for user ${user.id}:`, transactionsResponse.errors[0].message);
          continue;
        }
        const transactions = transactionsResponse.data.transactions;

        // 4. Calculate spending for the budget category
        const spending = transactions
          .filter(t => t.category === budget.category)
          .reduce((sum, t) => sum + t.amount, 0);

        // 5. Check if budget is close to being exceeded
        const spendingPercentage = (spending / budget.amount) * 100;
        if (spendingPercentage >= 90 && spendingPercentage < 100) {
          // Send "approaching limit" alert
          await sendEmail({
            message: {
              to: user.email,
              subject: `Budget Alert: Approaching limit for ${budget.name}`,
              text: `You have spent ${spending.toFixed(2)} of your ${budget.amount.toFixed(2)} budget for ${budget.name} (${spendingPercentage.toFixed(0)}%).`,
            }
          });
        } else if (spendingPercentage >= 100) {
          // Send "exceeded limit" alert
          await sendEmail({
            message: {
              to: user.email,
              subject: `Budget Alert: Exceeded limit for ${budget.name}`,
              text: `You have exceeded your ${budget.amount.toFixed(2)} budget for ${budget.name}. You have spent ${spending.toFixed(2)} (${spendingPercentage.toFixed(0)}%).`,
            }
          });
        }
      }
    }
  } catch (error) {
    console.error('Error checking budgets:', error);
  }

  console.log('Budget check complete.');
}

// This function will be called by the scheduler
export function runBudgetAlerts() {
  // For now, just call the function directly.
  // In a real implementation, this would be registered with a scheduler (e.g., cron).
  checkBudgets();
}

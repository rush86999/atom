import React, { useEffect, useState } from 'react';
import withSideBarWithHeader from '../../layouts/SideBarWithHeader';
import { usePlaidLink } from 'react-plaid-link';
import { Button } from '@mui/material';
import { useUser } from '../../lib/user-context';

const PlaidLink = ({ user, setAccounts, setTransactions }) => {
  const [linkToken, setLinkToken] = useState(null);

  useEffect(() => {
    const createLinkToken = async () => {
      const response = await fetch('/api/financial/plaid/create_link_token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: user.id }),
      });
      const { data } = await response.json();
      setLinkToken(data.link_token);
    };
    createLinkToken();
  }, [user]);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: async (public_token, metadata) => {
      await fetch('/api/financial/plaid/exchange_public_token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ public_token, user_id: user.id }),
      });
      // After successful link, fetch accounts and transactions
      const accountsResponse = await fetch(`/api/financial/accounts?user_id=${user.id}`);
      const accountsData = await accountsResponse.json();
      setAccounts(accountsData.data);

      const transactionsResponse = await fetch(`/api/financial/transactions?user_id=${user.id}&start_date=2023-01-01&end_date=2023-12-31`);
      const transactionsData = await transactionsResponse.json();
      setTransactions(transactionsData.data);
    },
  });

  return (
    <Button variant="contained" onClick={() => open()} disabled={!ready}>
      Connect a bank account
    </Button>
  );
};


const Finance = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);

  if (!hasRole('finance')) {
    return <div>You do not have permission to view this page.</div>;
  }

  return (
    <div>
      <h1>Finance</h1>
      <PlaidLink user={user} setAccounts={setAccounts} setTransactions={setTransactions} />

      <h2>Accounts</h2>
      <ul>
        {accounts.map((account) => (
          <li key={account.account_id}>
            {account.name} - {account.balances.current}
          </li>
        ))}
      </ul>

      <h2>Transactions</h2>
      <ul>
        {transactions.map((transaction) => (
          <li key={transaction.transaction_id}>
            {transaction.name} - {transaction.amount}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default withSideBarWithHeader(Finance);

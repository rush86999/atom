import React, { useEffect, useState } from 'react';
import withSideBarWithHeader from '../../layouts/SideBarWithHeader';
import { useUser } from '../../lib/user-context';
import { useUserRole } from '../../contexts/userRole/userRoleContext';
import { Button, TextField } from '@mui/material';

const ManualAccount = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [manualAccounts, setManualAccounts] = useState([]);
  const [accountName, setAccountName] = useState('');
  const [accountBalance, setAccountBalance] = useState('');
  const [transactionDescription, setTransactionDescription] = useState('');
  const [transactionAmount, setTransactionAmount] = useState('');
  const [selectedAccountId, setSelectedAccountId] = useState('');

  useEffect(() => {
    const getManualAccounts = async () => {
      const response = await fetch(`/api/financial/manual_accounts?user_id=${user.id}`);
      const { data } = await response.json();
      setManualAccounts(data);
    };
    if (user && hasRole('finance')) {
      getManualAccounts();
    }
  }, [user, hasRole]);

  const handleCreateManualAccount = async () => {
    await fetch('/api/financial/manual_accounts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: user.id,
        name: accountName,
        balance: accountBalance,
      }),
    });
    // Refresh the list of manual accounts
    const response = await fetch(`/api/financial/manual_accounts?user_id=${user.id}`);
    const { data } = await response.json();
    setManualAccounts(data);
  };

  const handleCreateManualTransaction = async () => {
    await fetch('/api/financial/manual_transactions', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: user.id,
            account_id: selectedAccountId,
            description: transactionDescription,
            amount: transactionAmount,
        }),
    });
    // You might want to refresh the transactions for the selected account here
  };


  if (!hasRole('finance')) {
    return <div>You do not have permission to view this page.</div>;
  }

  return (
    <div>
      <h1>Manual Accounts</h1>
      <div>
        <TextField
          label="Account Name"
          value={accountName}
          onChange={(e) => setAccountName(e.target.value)}
        />
        <TextField
          label="Account Balance"
          value={accountBalance}
          onChange={(e) => setAccountBalance(e.target.value)}
        />
        <Button variant="contained" onClick={handleCreateManualAccount}>
          Create Manual Account
        </Button>
      </div>
      <ul>
        {manualAccounts.map((account) => (
          <li key={account.id}>
            {account.name}: ${account.balance}
            <Button onClick={() => setSelectedAccountId(account.id)}>Add Transaction</Button>
          </li>
        ))}
      </ul>
        {selectedAccountId && (
            <div>
                <h2>Add Transaction</h2>
                <TextField
                    label="Description"
                    value={transactionDescription}
                    onChange={(e) => setTransactionDescription(e.target.value)}
                />
                <TextField
                    label="Amount"
                    value={transactionAmount}
                    onChange={(e) => setTransactionAmount(e.target.value)}
                />
                <Button variant="contained" onClick={handleCreateManualTransaction}>
                    Add Transaction
                </Button>
            </div>
        )}
    </div>
  );
};

export default withSideBarWithHeader(ManualAccount);

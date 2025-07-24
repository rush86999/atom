import React, { createContext, useContext, useState } from 'react';

const FinanceContext = createContext(null);

export const FinanceProvider = ({ children }) => {
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);

  const value = {
    accounts,
    setAccounts,
    transactions,
    setTransactions,
  };

  return (
    <FinanceContext.Provider value={value}>{children}</FinanceContext.Provider>
  );
};

export const useFinance = () => {
  return useContext(FinanceContext);
};

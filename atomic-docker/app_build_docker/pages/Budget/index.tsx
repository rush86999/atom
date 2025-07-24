import React, { useEffect, useState } from 'react';
import withSideBarWithHeader from '../../layouts/SideBarWithHeader';
import { useUser } from '../../lib/user-context';
import { useUserRole } from '../../contexts/userRole/userRoleContext';

const Budget = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [budgets, setBudgets] = useState([]);

  useEffect(() => {
    const getBudgets = async () => {
      const response = await fetch(`/api/financial/budgets?user_id=${user.id}`);
      const { data } = await response.json();
      setBudgets(data);
    };
    if (user && hasRole('finance')) {
      getBudgets();
    }
  }, [user, hasRole]);

  if (!hasRole('finance')) {
    return <div>You do not have permission to view this page.</div>;
  }

  return (
    <div>
      <h1>Budget</h1>
      <ul>
        {budgets.map((budget) => (
          <li key={budget.category}>
            {budget.category}: ${budget.amount}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default withSideBarWithHeader(Budget);

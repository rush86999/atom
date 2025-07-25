import React, { useEffect, useState } from 'react';
import withSideBarWithHeader from '../../layouts/SideBarWithHeader';
import { useUser } from '../../lib/user-context';
import { useUserRole } from '../../contexts/userRole/userRoleContext';

const Reporting = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [spendingReport, setSpendingReport] = useState({});

  useEffect(() => {
    const getSpendingReport = async () => {
      const response = await fetch(`/api/financial/reports/spending?user_id=${user.id}`);
      const { data } = await response.json();
      setSpendingReport(data);
    };
    if (user && hasRole('finance')) {
      getSpendingReport();
    }
  }, [user, hasRole]);

  if (!hasRole('finance')) {
    return <div>You do not have permission to view this page.</div>;
  }

  return (
    <div>
      <h1>Reporting</h1>
      <h2>Spending by Category</h2>
      <ul>
        {Object.entries(spendingReport).map(([category, amount]) => (
          <li key={category}>
            {category}: ${amount}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default withSideBarWithHeader(Reporting);

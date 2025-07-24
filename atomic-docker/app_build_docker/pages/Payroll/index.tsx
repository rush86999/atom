import React, { useEffect, useState } from 'react';
import withSideBarWithHeader from '../../layouts/SideBarWithHeader';
import { useUser } from '../../lib/user-context';
import { useUserRole } from '../../contexts/userRole/userRoleContext';

const Payroll = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [payrolls, setPayrolls] = useState([]);

  useEffect(() => {
    const getPayrolls = async () => {
      const response = await fetch(`/api/financial/payrolls?user_id=${user.id}`);
      const { data } = await response.json();
      setPayrolls(data);
    };
    if (user && hasRole('finance')) {
      getPayrolls();
    }
  }, [user, hasRole]);

  if (!hasRole('finance')) {
    return <div>You do not have permission to view this page.</div>;
  }

  return (
    <div>
      <h1>Payroll</h1>
      <ul>
        {payrolls.map((payroll) => (
          <li key={payroll.id}>
            Payroll #{payroll.id}: ${payroll.amount}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default withSideBarWithHeader(Payroll);

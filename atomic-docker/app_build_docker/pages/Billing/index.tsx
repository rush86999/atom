import React, { useEffect, useState } from 'react';
import withSideBarWithHeader from '../../layouts/SideBarWithHeader';
import { useUser } from '../../lib/user-context';
import { useUserRole } from '../../contexts/userRole/userRoleContext';

const Billing = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [bills, setBills] = useState([]);

  useEffect(() => {
    const getBills = async () => {
      const response = await fetch(`/api/financial/bills?user_id=${user.id}`);
      const { data } = await response.json();
      setBills(data);
    };
    if (user && hasRole('finance')) {
      getBills();
    }
  }, [user, hasRole]);

  if (!hasRole('finance')) {
    return <div>You do not have permission to view this page.</div>;
  }

  return (
    <div>
      <h1>Billing</h1>
      <ul>
        {bills.map((bill) => (
          <li key={bill.id}>
            Bill #{bill.id}: ${bill.amount}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default withSideBarWithHeader(Billing);

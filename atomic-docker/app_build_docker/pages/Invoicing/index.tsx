import React, { useEffect, useState } from 'react';
import withSideBarWithHeader from '../../layouts/SideBarWithHeader';
import { useUser } from '../../lib/user-context';
import { useUserRole } from '../../contexts/userRole/userRoleContext';

const Invoicing = () => {
  const { user } = useUser();
  const { hasRole } = useUserRole();
  const [invoices, setInvoices] = useState([]);

  useEffect(() => {
    const getInvoices = async () => {
      const response = await fetch(`/api/financial/invoices?user_id=${user.id}`);
      const { data } = await response.json();
      setInvoices(data);
    };
    if (user && hasRole('finance')) {
      getInvoices();
    }
  }, [user, hasRole]);

  if (!hasRole('finance')) {
    return <div>You do not have permission to view this page.</div>;
  }

  return (
    <div>
      <h1>Invoicing</h1>
      <ul>
        {invoices.map((invoice) => (
          <li key={invoice.id}>
            Invoice #{invoice.id}: ${invoice.amount}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default withSideBarWithHeader(Invoicing);

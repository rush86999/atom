import React from 'react';
import { useUserRole } from '../../contexts/userRole/userRoleContext';

/**
 * Settings page component for managing user roles.
 * It allows users to activate or deactivate roles, which in turn
 * controls access to different features within the application.
 */
const SettingsPage = () => {
  // Access the role management context.
  // This hook will fail if the component is not rendered within a UserRoleProvider.
  // We will ensure the provider is added in `_app.tsx`.
  const { availableRoles, hasRole, toggleRole } = useUserRole();

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>Settings</h1>
      <h2>Manage Your Roles & Agent Skills</h2>
      <p>Select the roles you want to activate. These determine which features and tools are available to you.</p>

      <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {availableRoles.map((role) => (
          <div key={role}>
            <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={hasRole(role)}
                onChange={() => toggleRole(role)}
                style={{ marginRight: '10px', height: '18px', width: '18px' }}
              />
              <span style={{ textTransform: 'capitalize' }}>
                {role.replace('_', ' ')}
              </span>
            </label>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SettingsPage;

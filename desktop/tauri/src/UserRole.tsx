import React from 'react';

// Define the type for a role. This can be expanded with more roles as needed.
export type Role = 'sales' | 'support' | 'developer' | 'project_manager' | 'data_analyst';

// Define the props for the UserRole component
interface UserRoleProps {
  activeRoles: Role[];
  availableRoles: Role[];
  onToggleRole: (role: Role) => void;
}

/**
 * A component for managing user roles and agent skills in the desktop app.
 * It displays a list of available roles and allows the user to toggle them.
 *
 * @param {UserRoleProps} props - The component props.
 * @param {Role[]} props.activeRoles - The currently active roles.
 * @param {Role[]} props.availableRoles - All possible roles.
 * @param {(role: Role) => void} props.onToggleRole - Callback function to toggle a role.
 */
const UserRole: React.FC<UserRoleProps> = ({ activeRoles, availableRoles, onToggleRole }) => {
  return (
    <div className="user-role-container" style={{ padding: '20px', fontFamily: 'Arial, sans-serif', border: '1px solid #ccc', borderRadius: '8px', marginTop: '20px' }}>
      <h2>Manage Your Roles & Agent Skills</h2>
      <p>Select the roles you want to activate to enable specific features.</p>
      <div style={{ marginTop: '15px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {availableRoles.map((role) => (
          <div key={role}>
            <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', textTransform: 'capitalize' }}>
              <input
                type="checkbox"
                checked={activeRoles.includes(role)}
                onChange={() => onToggleRole(role)}
                style={{ marginRight: '10px', height: '18px', width: '18px' }}
              />
              {role.replace('_', ' ')}
            </label>
          </div>
        ))}
      </div>
    </div>
  );
};

export default UserRole;

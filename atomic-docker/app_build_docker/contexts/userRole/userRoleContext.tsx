import React, { createContext, useContext, useState, ReactNode, useCallback } from 'react';

// Define the type for a role. This can be expanded with more roles as needed.
export type Role = 'sales' | 'support' | 'developer' | 'project_manager' | 'researcher' | 'social_media_manager' | 'content_creator' | 'shopper';

// Define the interface for the context's value
interface UserRoleContextType {
  activeRoles: Role[];
  availableRoles: Role[];
  hasRole: (role: Role) => boolean;
  toggleRole: (role: Role) => void;
}

// Create the context. The default value is `undefined` and will be provided by the `UserRoleProvider`.
const UserRoleContext = createContext<UserRoleContextType | undefined>(undefined);

/**
 * Custom hook to access the UserRoleContext.
 * This makes it easier to consume the context in components and provides a single point of failure
 * if the context is used outside of its provider.
 */
export const useUserRole = () => {
  const context = useContext(UserRoleContext);
  if (!context) {
    throw new Error('useUserRole must be used within a UserRoleProvider');
  }
  return context;
};

// A mock list of all roles available in the application.
const MOCK_AVAILABLE_ROLES: Role[] = ['sales', 'support', 'developer', 'project_manager', 'researcher', 'social_media_manager', 'content_creator', 'shopper'];

/**
 * Provider component that wraps parts of the application to provide user role management.
 * It holds the state for active roles and provides functions to interact with that state.
 * @param {object} props - The component props.
 * @param {ReactNode} props.children - The child components to be rendered within the provider.
 */
export const UserRoleProvider = ({ children }: { children: ReactNode }) => {
  const [activeRoles, setActiveRoles] = useState<Role[]>([]);

  // Memoize the `hasRole` function for performance, preventing unnecessary re-renders of consumer components.
  const hasRole = useCallback(
    (role: Role) => activeRoles.includes(role),
    [activeRoles]
  );

  // Function to add or remove a role from the active roles list.
  const toggleRole = (role: Role) => {
    setActiveRoles((prevRoles) => {
      if (prevRoles.includes(role)) {
        // If role is already active, deactivate it.
        return prevRoles.filter((r) => r !== role);
      } else {
        // Otherwise, activate it.
        return [...prevRoles, role];
      }
    });
  };

  // The value to be provided to consuming components.
  const value = {
    activeRoles,
    availableRoles: MOCK_AVAILABLE_ROLES,
    hasRole,
    toggleRole,
  };

  return (
    <UserRoleContext.Provider value={value}>
      {children}
    </UserRoleContext.Provider>
  );
};

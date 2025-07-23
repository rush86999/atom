import React from "react";
import { Role } from "../UserRole";

/**
 * Props for the FeatureViewGuard component.
 */
interface FeatureViewGuardProps {
  /** The currently active roles for the user. */
  activeRoles: Role[];
  /** The role required to access the guarded content. */
  requiredRole: Role;
  /** A user-friendly name for the feature or role being guarded. */
  roleName: string;
  /** A callback function to navigate the user to the settings view. */
  onNavigateToSettings: () => void;
  /** The content to render if the user has the necessary role. */
  children: React.ReactElement | null;
}

/**
 * A component that protects a view based on the user's active roles.
 * If the user has the required role, it renders the children. Otherwise, it
 * displays an "Access Denied" message with an option to go to settings.
 *
 * @param {FeatureViewGuardProps} props - The component's props.
 * @returns {React.ReactElement} The protected content or an access denied message.
 */
const FeatureViewGuard = ({
  activeRoles,
  requiredRole,
  roleName,
  onNavigateToSettings,
  children,
}: FeatureViewGuardProps): React.ReactElement | null => {
  // Check if the user has the required role.
  const hasAccess = activeRoles.includes(requiredRole);

  if (hasAccess) {
    return children;
  }

  // If the user does not have access, render the access denied message.
  return (
    <div
      className="access-denied"
      style={{ padding: "20px", textAlign: "center" }}
    >
      <h2>Access Denied</h2>
      <p>You need to activate the '{roleName}' role to view this page.</p>
      <button onClick={onNavigateToSettings}>Go to Settings</button>
    </div>
  );
};

export default FeatureViewGuard;

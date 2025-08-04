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
declare const FeatureViewGuard: ({ activeRoles, requiredRole, roleName, onNavigateToSettings, children, }: FeatureViewGuardProps) => React.ReactElement | null;
export default FeatureViewGuard;

import React, { ReactNode } from 'react';
import { Role } from '../../contexts/userRole/userRoleContext';
/**
 * Props for the FeaturePageGuard component.
 */
interface FeaturePageGuardProps {
    /** The specific role required to access the content. */
    role: Role;
    /** A user-friendly name for the role to be displayed in messages (e.g., "Sales Agent Skill"). */
    roleName: string;
    /** The content to be rendered if the user has the required role. */
    children: ReactNode;
}
/**
 * A component that acts as a gatekeeper for feature pages.
 * It checks if the user has the required role. If they do, it renders the child components.
 * If not, it displays a standardized "Access Denied" message with a link to the settings page.
 *
 * @param {FeaturePageGuardProps} props - The component's props.
 * @returns {React.ReactElement} The protected content or an access denied message.
 */
declare const FeaturePageGuard: React.FC<FeaturePageGuardProps>;
export default FeaturePageGuard;

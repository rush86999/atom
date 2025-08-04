import React from "react";
export type Role = "sales" | "support" | "developer" | "project_manager" | "financial_analyst" | "researcher" | "social_media_manager" | "content_creator" | "shopper";
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
declare const UserRole: React.FC<UserRoleProps>;
export default UserRole;

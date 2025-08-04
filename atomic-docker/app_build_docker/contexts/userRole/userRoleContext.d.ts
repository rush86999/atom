import { ReactNode } from 'react';
export type Role = 'sales' | 'support' | 'developer' | 'project_manager' | 'researcher' | 'social_media_manager' | 'content_creator' | 'shopper';
interface UserRoleContextType {
    activeRoles: Role[];
    availableRoles: Role[];
    hasRole: (role: Role) => boolean;
    toggleRole: (role: Role) => void;
}
/**
 * Custom hook to access the UserRoleContext.
 * This makes it easier to consume the context in components and provides a single point of failure
 * if the context is used outside of its provider.
 */
export declare const useUserRole: () => UserRoleContextType;
/**
 * Provider component that wraps parts of the application to provide user role management.
 * It holds the state for active roles and provides functions to interact with that state.
 * @param {object} props - The component props.
 * @param {ReactNode} props.children - The child components to be rendered within the provider.
 */
export declare const UserRoleProvider: ({ children }: {
    children: ReactNode;
}) => JSX.Element;
export {};

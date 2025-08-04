"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.UserRoleProvider = exports.useUserRole = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
// Create the context. The default value is `undefined` and will be provided by the `UserRoleProvider`.
const UserRoleContext = (0, react_1.createContext)(undefined);
/**
 * Custom hook to access the UserRoleContext.
 * This makes it easier to consume the context in components and provides a single point of failure
 * if the context is used outside of its provider.
 */
const useUserRole = () => {
    const context = (0, react_1.useContext)(UserRoleContext);
    if (!context) {
        throw new Error('useUserRole must be used within a UserRoleProvider');
    }
    return context;
};
exports.useUserRole = useUserRole;
// A mock list of all roles available in the application.
const MOCK_AVAILABLE_ROLES = ['sales', 'support', 'developer', 'project_manager', 'researcher', 'social_media_manager', 'content_creator', 'shopper'];
/**
 * Provider component that wraps parts of the application to provide user role management.
 * It holds the state for active roles and provides functions to interact with that state.
 * @param {object} props - The component props.
 * @param {ReactNode} props.children - The child components to be rendered within the provider.
 */
const UserRoleProvider = ({ children }) => {
    const [activeRoles, setActiveRoles] = (0, react_1.useState)([]);
    // Memoize the `hasRole` function for performance, preventing unnecessary re-renders of consumer components.
    const hasRole = (0, react_1.useCallback)((role) => activeRoles.includes(role), [activeRoles]);
    // Function to add or remove a role from the active roles list.
    const toggleRole = (role) => {
        setActiveRoles((prevRoles) => {
            if (prevRoles.includes(role)) {
                // If role is already active, deactivate it.
                return prevRoles.filter((r) => r !== role);
            }
            else {
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
    return ((0, jsx_runtime_1.jsx)(UserRoleContext.Provider, { value: value, children: children }));
};
exports.UserRoleProvider = UserRoleProvider;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlclJvbGVDb250ZXh0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXNlclJvbGVDb250ZXh0LnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7O0FBQUEsaUNBQTJGO0FBYTNGLHVHQUF1RztBQUN2RyxNQUFNLGVBQWUsR0FBRyxJQUFBLHFCQUFhLEVBQWtDLFNBQVMsQ0FBQyxDQUFDO0FBRWxGOzs7O0dBSUc7QUFDSSxNQUFNLFdBQVcsR0FBRyxHQUFHLEVBQUU7SUFDOUIsTUFBTSxPQUFPLEdBQUcsSUFBQSxrQkFBVSxFQUFDLGVBQWUsQ0FBQyxDQUFDO0lBQzVDLElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUNiLE1BQU0sSUFBSSxLQUFLLENBQUMsb0RBQW9ELENBQUMsQ0FBQztJQUN4RSxDQUFDO0lBQ0QsT0FBTyxPQUFPLENBQUM7QUFDakIsQ0FBQyxDQUFDO0FBTlcsUUFBQSxXQUFXLGVBTXRCO0FBRUYseURBQXlEO0FBQ3pELE1BQU0sb0JBQW9CLEdBQVcsQ0FBQyxPQUFPLEVBQUUsU0FBUyxFQUFFLFdBQVcsRUFBRSxpQkFBaUIsRUFBRSxZQUFZLEVBQUUsc0JBQXNCLEVBQUUsaUJBQWlCLEVBQUUsU0FBUyxDQUFDLENBQUM7QUFFOUo7Ozs7O0dBS0c7QUFDSSxNQUFNLGdCQUFnQixHQUFHLENBQUMsRUFBRSxRQUFRLEVBQTJCLEVBQUUsRUFBRTtJQUN4RSxNQUFNLENBQUMsV0FBVyxFQUFFLGNBQWMsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBUyxFQUFFLENBQUMsQ0FBQztJQUUzRCw0R0FBNEc7SUFDNUcsTUFBTSxPQUFPLEdBQUcsSUFBQSxtQkFBVyxFQUN6QixDQUFDLElBQVUsRUFBRSxFQUFFLENBQUMsV0FBVyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsRUFDMUMsQ0FBQyxXQUFXLENBQUMsQ0FDZCxDQUFDO0lBRUYsK0RBQStEO0lBQy9ELE1BQU0sVUFBVSxHQUFHLENBQUMsSUFBVSxFQUFFLEVBQUU7UUFDaEMsY0FBYyxDQUFDLENBQUMsU0FBUyxFQUFFLEVBQUU7WUFDM0IsSUFBSSxTQUFTLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxFQUFFLENBQUM7Z0JBQzdCLDRDQUE0QztnQkFDNUMsT0FBTyxTQUFTLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssSUFBSSxDQUFDLENBQUM7WUFDN0MsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLDBCQUEwQjtnQkFDMUIsT0FBTyxDQUFDLEdBQUcsU0FBUyxFQUFFLElBQUksQ0FBQyxDQUFDO1lBQzlCLENBQUM7UUFDSCxDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQztJQUVGLG9EQUFvRDtJQUNwRCxNQUFNLEtBQUssR0FBRztRQUNaLFdBQVc7UUFDWCxjQUFjLEVBQUUsb0JBQW9CO1FBQ3BDLE9BQU87UUFDUCxVQUFVO0tBQ1gsQ0FBQztJQUVGLE9BQU8sQ0FDTCx1QkFBQyxlQUFlLENBQUMsUUFBUSxJQUFDLEtBQUssRUFBRSxLQUFLLFlBQ25DLFFBQVEsR0FDZ0IsQ0FDNUIsQ0FBQztBQUNKLENBQUMsQ0FBQztBQW5DVyxRQUFBLGdCQUFnQixvQkFtQzNCIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IGNyZWF0ZUNvbnRleHQsIHVzZUNvbnRleHQsIHVzZVN0YXRlLCBSZWFjdE5vZGUsIHVzZUNhbGxiYWNrIH0gZnJvbSAncmVhY3QnO1xuXG4vLyBEZWZpbmUgdGhlIHR5cGUgZm9yIGEgcm9sZS4gVGhpcyBjYW4gYmUgZXhwYW5kZWQgd2l0aCBtb3JlIHJvbGVzIGFzIG5lZWRlZC5cbmV4cG9ydCB0eXBlIFJvbGUgPSAnc2FsZXMnIHwgJ3N1cHBvcnQnIHwgJ2RldmVsb3BlcicgfCAncHJvamVjdF9tYW5hZ2VyJyB8ICdyZXNlYXJjaGVyJyB8ICdzb2NpYWxfbWVkaWFfbWFuYWdlcicgfCAnY29udGVudF9jcmVhdG9yJyB8ICdzaG9wcGVyJztcblxuLy8gRGVmaW5lIHRoZSBpbnRlcmZhY2UgZm9yIHRoZSBjb250ZXh0J3MgdmFsdWVcbmludGVyZmFjZSBVc2VyUm9sZUNvbnRleHRUeXBlIHtcbiAgYWN0aXZlUm9sZXM6IFJvbGVbXTtcbiAgYXZhaWxhYmxlUm9sZXM6IFJvbGVbXTtcbiAgaGFzUm9sZTogKHJvbGU6IFJvbGUpID0+IGJvb2xlYW47XG4gIHRvZ2dsZVJvbGU6IChyb2xlOiBSb2xlKSA9PiB2b2lkO1xufVxuXG4vLyBDcmVhdGUgdGhlIGNvbnRleHQuIFRoZSBkZWZhdWx0IHZhbHVlIGlzIGB1bmRlZmluZWRgIGFuZCB3aWxsIGJlIHByb3ZpZGVkIGJ5IHRoZSBgVXNlclJvbGVQcm92aWRlcmAuXG5jb25zdCBVc2VyUm9sZUNvbnRleHQgPSBjcmVhdGVDb250ZXh0PFVzZXJSb2xlQ29udGV4dFR5cGUgfCB1bmRlZmluZWQ+KHVuZGVmaW5lZCk7XG5cbi8qKlxuICogQ3VzdG9tIGhvb2sgdG8gYWNjZXNzIHRoZSBVc2VyUm9sZUNvbnRleHQuXG4gKiBUaGlzIG1ha2VzIGl0IGVhc2llciB0byBjb25zdW1lIHRoZSBjb250ZXh0IGluIGNvbXBvbmVudHMgYW5kIHByb3ZpZGVzIGEgc2luZ2xlIHBvaW50IG9mIGZhaWx1cmVcbiAqIGlmIHRoZSBjb250ZXh0IGlzIHVzZWQgb3V0c2lkZSBvZiBpdHMgcHJvdmlkZXIuXG4gKi9cbmV4cG9ydCBjb25zdCB1c2VVc2VyUm9sZSA9ICgpID0+IHtcbiAgY29uc3QgY29udGV4dCA9IHVzZUNvbnRleHQoVXNlclJvbGVDb250ZXh0KTtcbiAgaWYgKCFjb250ZXh0KSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKCd1c2VVc2VyUm9sZSBtdXN0IGJlIHVzZWQgd2l0aGluIGEgVXNlclJvbGVQcm92aWRlcicpO1xuICB9XG4gIHJldHVybiBjb250ZXh0O1xufTtcblxuLy8gQSBtb2NrIGxpc3Qgb2YgYWxsIHJvbGVzIGF2YWlsYWJsZSBpbiB0aGUgYXBwbGljYXRpb24uXG5jb25zdCBNT0NLX0FWQUlMQUJMRV9ST0xFUzogUm9sZVtdID0gWydzYWxlcycsICdzdXBwb3J0JywgJ2RldmVsb3BlcicsICdwcm9qZWN0X21hbmFnZXInLCAncmVzZWFyY2hlcicsICdzb2NpYWxfbWVkaWFfbWFuYWdlcicsICdjb250ZW50X2NyZWF0b3InLCAnc2hvcHBlciddO1xuXG4vKipcbiAqIFByb3ZpZGVyIGNvbXBvbmVudCB0aGF0IHdyYXBzIHBhcnRzIG9mIHRoZSBhcHBsaWNhdGlvbiB0byBwcm92aWRlIHVzZXIgcm9sZSBtYW5hZ2VtZW50LlxuICogSXQgaG9sZHMgdGhlIHN0YXRlIGZvciBhY3RpdmUgcm9sZXMgYW5kIHByb3ZpZGVzIGZ1bmN0aW9ucyB0byBpbnRlcmFjdCB3aXRoIHRoYXQgc3RhdGUuXG4gKiBAcGFyYW0ge29iamVjdH0gcHJvcHMgLSBUaGUgY29tcG9uZW50IHByb3BzLlxuICogQHBhcmFtIHtSZWFjdE5vZGV9IHByb3BzLmNoaWxkcmVuIC0gVGhlIGNoaWxkIGNvbXBvbmVudHMgdG8gYmUgcmVuZGVyZWQgd2l0aGluIHRoZSBwcm92aWRlci5cbiAqL1xuZXhwb3J0IGNvbnN0IFVzZXJSb2xlUHJvdmlkZXIgPSAoeyBjaGlsZHJlbiB9OiB7IGNoaWxkcmVuOiBSZWFjdE5vZGUgfSkgPT4ge1xuICBjb25zdCBbYWN0aXZlUm9sZXMsIHNldEFjdGl2ZVJvbGVzXSA9IHVzZVN0YXRlPFJvbGVbXT4oW10pO1xuXG4gIC8vIE1lbW9pemUgdGhlIGBoYXNSb2xlYCBmdW5jdGlvbiBmb3IgcGVyZm9ybWFuY2UsIHByZXZlbnRpbmcgdW5uZWNlc3NhcnkgcmUtcmVuZGVycyBvZiBjb25zdW1lciBjb21wb25lbnRzLlxuICBjb25zdCBoYXNSb2xlID0gdXNlQ2FsbGJhY2soXG4gICAgKHJvbGU6IFJvbGUpID0+IGFjdGl2ZVJvbGVzLmluY2x1ZGVzKHJvbGUpLFxuICAgIFthY3RpdmVSb2xlc11cbiAgKTtcblxuICAvLyBGdW5jdGlvbiB0byBhZGQgb3IgcmVtb3ZlIGEgcm9sZSBmcm9tIHRoZSBhY3RpdmUgcm9sZXMgbGlzdC5cbiAgY29uc3QgdG9nZ2xlUm9sZSA9IChyb2xlOiBSb2xlKSA9PiB7XG4gICAgc2V0QWN0aXZlUm9sZXMoKHByZXZSb2xlcykgPT4ge1xuICAgICAgaWYgKHByZXZSb2xlcy5pbmNsdWRlcyhyb2xlKSkge1xuICAgICAgICAvLyBJZiByb2xlIGlzIGFscmVhZHkgYWN0aXZlLCBkZWFjdGl2YXRlIGl0LlxuICAgICAgICByZXR1cm4gcHJldlJvbGVzLmZpbHRlcigocikgPT4gciAhPT0gcm9sZSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICAvLyBPdGhlcndpc2UsIGFjdGl2YXRlIGl0LlxuICAgICAgICByZXR1cm4gWy4uLnByZXZSb2xlcywgcm9sZV07XG4gICAgICB9XG4gICAgfSk7XG4gIH07XG5cbiAgLy8gVGhlIHZhbHVlIHRvIGJlIHByb3ZpZGVkIHRvIGNvbnN1bWluZyBjb21wb25lbnRzLlxuICBjb25zdCB2YWx1ZSA9IHtcbiAgICBhY3RpdmVSb2xlcyxcbiAgICBhdmFpbGFibGVSb2xlczogTU9DS19BVkFJTEFCTEVfUk9MRVMsXG4gICAgaGFzUm9sZSxcbiAgICB0b2dnbGVSb2xlLFxuICB9O1xuXG4gIHJldHVybiAoXG4gICAgPFVzZXJSb2xlQ29udGV4dC5Qcm92aWRlciB2YWx1ZT17dmFsdWV9PlxuICAgICAge2NoaWxkcmVufVxuICAgIDwvVXNlclJvbGVDb250ZXh0LlByb3ZpZGVyPlxuICApO1xufTtcbiJdfQ==
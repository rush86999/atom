"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Chat_1 = __importDefault(require("./Chat"));
const Sales_1 = __importDefault(require("./Sales"));
const Projects_1 = __importDefault(require("./Projects"));
const Support_1 = __importDefault(require("./Support"));
const UserRole_1 = __importDefault(require("./UserRole"));
const Research_1 = __importDefault(require("./Research"));
const Social_1 = __importDefault(require("./Social"));
const Content_1 = __importDefault(require("./Content"));
const Shopping_1 = __importDefault(require("./Shopping"));
const Dashboard_1 = __importDefault(require("./Dashboard"));
const FeatureViewGuard_1 = __importDefault(require("./components/FeatureViewGuard"));
const ProjectHealth_1 = __importDefault(require("./ProjectHealth"));
const CompetitorAnalysis_1 = __importDefault(require("./CompetitorAnalysis"));
const LearningAssistant_1 = __importDefault(require("./LearningAssistant"));
const Finance_1 = __importDefault(require("./Finance"));
const Integrations_1 = __importDefault(require("./components/Integrations"));
require("./App.css");
// Define the roles available in the desktop application.
const AVAILABLE_ROLES = [
    "sales",
    "support",
    "developer",
    "project_manager",
    "financial_analyst",
    "researcher",
    "social_media_manager",
    "content_creator",
    "shopper",
];
/**
 * The main application component for the desktop app.
 * It handles navigation between different views (Chat, Sales, Settings)
 * and manages role-based access to features.
 */
function App() {
    // State to manage the currently displayed view. Defaults to 'chat'.
    const [activeView, setActiveView] = (0, react_1.useState)("chat");
    // State to track which roles the user has activated.
    const [activeRoles, setActiveRoles] = (0, react_1.useState)([]);
    /**
     * Toggles a role's active status.
     * If the role is already active, it's removed. Otherwise, it's added.
     * @param {Role} role - The role to toggle.
     */
    const handleToggleRole = (role) => {
        setActiveRoles((prevRoles) => prevRoles.includes(role)
            ? prevRoles.filter((r) => r !== role)
            : [...prevRoles, role]);
    };
    const renderContent = () => {
        switch (activeView) {
            case "chat":
                return (0, jsx_runtime_1.jsx)(Chat_1.default, {});
            case "sales":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "sales", roleName: "Sales", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Sales_1.default, {}) }));
            case "projects":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "project_manager", roleName: "Project Manager", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Projects_1.default, {}) }));
            case "support":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "support", roleName: "Support", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Support_1.default, {}) }));
            case "settings":
                return ((0, jsx_runtime_1.jsx)(UserRole_1.default, { activeRoles: activeRoles, availableRoles: AVAILABLE_ROLES, onToggleRole: handleToggleRole }));
            case "integrations":
                return (0, jsx_runtime_1.jsx)(Integrations_1.default, {});
            case "project-health":
                return (0, jsx_runtime_1.jsx)(ProjectHealth_1.default, {});
            case "competitor-analysis":
                return (0, jsx_runtime_1.jsx)(CompetitorAnalysis_1.default, {});
            case "learning-assistant":
                return (0, jsx_runtime_1.jsx)(LearningAssistant_1.default, {});
            case "finance":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "financial_analyst", roleName: "Financial Analyst", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Finance_1.default, {}) }));
            case "research":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "researcher", roleName: "Researcher", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Research_1.default, {}) }));
            case "social":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "social_media_manager", roleName: "Social Media Manager", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Social_1.default, {}) }));
            case "content":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "content_creator", roleName: "Content Creator", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Content_1.default, {}) }));
            case "shopping":
                return ((0, jsx_runtime_1.jsx)(FeatureViewGuard_1.default, { activeRoles: activeRoles, requiredRole: "shopper", roleName: "Shopper", onNavigateToSettings: () => setActiveView("settings"), children: (0, jsx_runtime_1.jsx)(Shopping_1.default, {}) }));
            default:
                return (0, jsx_runtime_1.jsx)(Chat_1.default, {});
        }
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "App", children: [(0, jsx_runtime_1.jsx)(Dashboard_1.default, { setActiveView: setActiveView }), (0, jsx_runtime_1.jsx)("div", { className: "content", children: renderContent() })] }));
}
exports.default = App;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQXBwLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiQXBwLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSxpQ0FBd0M7QUFDeEMsa0RBQTBCO0FBQzFCLG9EQUE0QjtBQUM1QiwwREFBa0M7QUFDbEMsd0RBQWdDO0FBQ2hDLDBEQUE0QztBQUM1QywwREFBa0M7QUFDbEMsc0RBQThCO0FBQzlCLHdEQUFnQztBQUNoQywwREFBa0M7QUFFbEMsNERBQW9DO0FBQ3BDLHFGQUE2RDtBQUM3RCxvRUFBNEM7QUFDNUMsOEVBQXNEO0FBQ3RELDRFQUFvRDtBQUNwRCx3REFBZ0M7QUFDaEMsNkVBQXFEO0FBQ3JELHFCQUFtQjtBQUVuQix5REFBeUQ7QUFDekQsTUFBTSxlQUFlLEdBQVc7SUFDOUIsT0FBTztJQUNQLFNBQVM7SUFDVCxXQUFXO0lBQ1gsaUJBQWlCO0lBQ2pCLG1CQUFtQjtJQUNuQixZQUFZO0lBQ1osc0JBQXNCO0lBQ3RCLGlCQUFpQjtJQUNqQixTQUFTO0NBQ1YsQ0FBQztBQUVGOzs7O0dBSUc7QUFDSCxTQUFTLEdBQUc7SUFDVixvRUFBb0U7SUFDcEUsTUFBTSxDQUFDLFVBQVUsRUFBRSxhQUFhLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBRTFDLE1BQU0sQ0FBQyxDQUFDO0lBQ1YscURBQXFEO0lBQ3JELE1BQU0sQ0FBQyxXQUFXLEVBQUUsY0FBYyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFTLEVBQUUsQ0FBQyxDQUFDO0lBRTNEOzs7O09BSUc7SUFDSCxNQUFNLGdCQUFnQixHQUFHLENBQUMsSUFBVSxFQUFFLEVBQUU7UUFDdEMsY0FBYyxDQUFDLENBQUMsU0FBUyxFQUFFLEVBQUUsQ0FDM0IsU0FBUyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7WUFDdEIsQ0FBQyxDQUFDLFNBQVMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxJQUFJLENBQUM7WUFDckMsQ0FBQyxDQUFDLENB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QUMxQixvQkFBb0IsRUFBRSxHQUFHLEVBQUUsQ0FBQyxhQUFhLENBQUMsVUFBVSxDQUFDLFlBRXJELHVCQUFDLGlCQUFPLEtBQUcsR0FDTSxDQUNwQixDQUFDO1lBQ0osS0FBSyxVQUFVO2dCQUNiLE9BQU8sQ0FDTCx1QkFBQywwQkFBZ0IsSUFDZixXQUFXLEVBQUUsV0FBVyxFQUN4QixZQUFZLEVBQUMsU0FBUyxFQUN0QixRQUFRLEVBQUMsU0FBUyxFQUNsQixvQkFBb0IsRUFBRSxHQUFHLEVBQUUsQ0FBQyxhQUFhLENBQUMsVUFBVSxDQUFDLFlBRXJELHVCQUFDLGtCQUFRLEtBQUcsR0FDSyxDQUNwQixDQUFDO1lBQ0o7Z0JBQ0UsT0FBTyx1QkFBQyxjQUFJLEtBQUcsQ0FBQztRQUNwQixDQUFDO0lBQ0gsQ0FBQyxDQUFDO0lBRUYsT0FBTyxDQUNMLGlDQUFLLFNBQVMsRUFBQyxLQUFLLGFBQ2xCLHVCQUFDLG1CQUFTLElBQUMsYUFBYSxFQUFFLGFBQWEsR0FBSSxFQUMzQyxnQ0FBSyxTQUFTLEVBQUMsU0FBUyxZQUNyQixhQUFhLEVBQUUsR0FDWixJQUNGLENBQ1AsQ0FBQztBQUNKLENBQUM7QUFFRCxrQkFBZSxHQUFHLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHsgdXNlU3RhdGUgfSBmcm9tIFwicmVhY3RcIjtcbmltcG9ydCBDaGF0IGZyb20gXCIuL0NoYXRcIjtcbmltcG9ydCBTYWxlcyBmcm9tIFwiLi9TYWxlc1wiO1xuaW1wb3J0IFByb2plY3RzIGZyb20gXCIuL1Byb2plY3RzXCI7XG5pbXBvcnQgU3VwcG9ydCBmcm9tIFwiLi9TdXBwb3J0XCI7XG5pbXBvcnQgVXNlclJvbGUsIHsgUm9sZSB9IGZyb20gXCIuL1VzZXJSb2xlXCI7XG5pbXBvcnQgUmVzZWFyY2ggZnJvbSBcIi4vUmVzZWFyY2hcIjtcbmltcG9ydCBTb2NpYWwgZnJvbSBcIi4vU29jaWFsXCI7XG5pbXBvcnQgQ29udGVudCBmcm9tIFwiLi9Db250ZW50XCI7XG5pbXBvcnQgU2hvcHBpbmcgZnJvbSBcIi4vU2hvcHBpbmdcIjtcbmltcG9ydCBTbWFydFNlYXJjaCBmcm9tIFwiLi9TbWFydFNlYXJjaFwiO1xuaW1wb3J0IERhc2hib2FyZCBmcm9tIFwiLi9EYXNoYm9hcmRcIjtcbmltcG9ydCBGZWF0dXJlVmlld0d1YXJkIGZyb20gXCIuL2NvbXBvbmVudHMvRmVhdHVyZVZpZXdHdWFyZFwiO1xuaW1wb3J0IFByb2plY3RIZWFsdGggZnJvbSAnLi9Qcm9qZWN0SGVhbHRoJztcbmltcG9ydCBDb21wZXRpdG9yQW5hbHlzaXMgZnJvbSAnLi9Db21wZXRpdG9yQW5hbHlzaXMnO1xuaW1wb3J0IExlYXJuaW5nQXNzaXN0YW50IGZyb20gJy4vTGVhcm5pbmdBc3Npc3RhbnQnO1xuaW1wb3J0IEZpbmFuY2UgZnJvbSAnLi9GaW5hbmNlJztcbmltcG9ydCBJbnRlZ3JhdGlvbnMgZnJvbSBcIi4vY29tcG9uZW50cy9JbnRlZ3JhdGlvbnNcIjtcbmltcG9ydCBcIi4vQXBwLmNzc1wiO1xuXG4vLyBEZWZpbmUgdGhlIHJvbGVzIGF2YWlsYWJsZSBpbiB0aGUgZGVza3RvcCBhcHBsaWNhdGlvbi5cbmNvbnN0IEFWQUlMQUJMRV9ST0xFUzogUm9sZVtdID0gW1xuICBcInNhbGVzXCIsXG4gIFwic3VwcG9ydFwiLFxuICBcImRldmVsb3BlclwiLFxuICBcInByb2plY3RfbWFuYWdlclwiLFxuICBcImZpbmFuY2lhbF9hbmFseXN0XCIsXG4gIFwicmVzZWFyY2hlclwiLFxuICBcInNvY2lhbF9tZWRpYV9tYW5hZ2VyXCIsXG4gIFwiY29udGVudF9jcmVhdG9yXCIsXG4gIFwic2hvcHBlclwiLFxuXTtcblxuLyoqXG4gKiBUaGUgbWFpbiBhcHBsaWNhdGlvbiBjb21wb25lbnQgZm9yIHRoZSBkZXNrdG9wIGFwcC5cbiAqIEl0IGhhbmRsZXMgbmF2aWdhdGlvbiBiZXR3ZWVuIGRpZmZlcmVudCB2aWV3cyAoQ2hhdCwgU2FsZXMsIFNldHRpbmdzKVxuICogYW5kIG1hbmFnZXMgcm9sZS1iYXNlZCBhY2Nlc3MgdG8gZmVhdHVyZXMuXG4gKi9cbmZ1bmN0aW9uIEFwcCgpIHtcbiAgLy8gU3RhdGUgdG8gbWFuYWdlIHRoZSBjdXJyZW50bHkgZGlzcGxheWVkIHZpZXcuIERlZmF1bHRzIHRvICdjaGF0Jy5cbiAgY29uc3QgW2FjdGl2ZVZpZXcsIHNldEFjdGl2ZVZpZXddID0gdXNlU3RhdGU8XG4gICAgXCJjaGF0XCIgfCBcInNhbGVzXCIgfCBcInByb2plY3RzXCIgfCBcInN1cHBvcnRcIiB8IFwic2V0dGluZ3NcIiB8IFwicHJvamVjdC1oZWFsdGhcIiB8IFwiY29tcGV0aXRvci1hbmFseXNpc1wiIHwgXCJsZWFybmluZy1hc3Npc3RhbnRcIiB8IFwiZmluYW5jZVwiIHwgXCJyZXNlYXJjaFwiIHwgXCJzb2NpYWxcIiB8IFwiY29udGVudFwiIHwgXCJzaG9wcGluZ1wiIHwgXCJpbnRlZ3JhdGlvbnNcIlxuICA+KFwiY2hhdFwiKTtcbiAgLy8gU3RhdGUgdG8gdHJhY2sgd2hpY2ggcm9sZXMgdGhlIHVzZXIgaGFzIGFjdGl2YXRlZC5cbiAgY29uc3QgW2FjdGl2ZVJvbGVzLCBzZXRBY3RpdmVSb2xlc10gPSB1c2VTdGF0ZTxSb2xlW10+KFtdKTtcblxuICAvKipcbiAgICogVG9nZ2xlcyBhIHJvbGUncyBhY3RpdmUgc3RhdHVzLlxuICAgKiBJZiB0aGUgcm9sZSBpcyBhbHJlYWR5IGFjdGl2ZSwgaXQncyByZW1vdmVkLiBPdGhlcndpc2UsIGl0J3MgYWRkZWQuXG4gICAqIEBwYXJhbSB7Um9sZX0gcm9sZSAtIFRoZSByb2xlIHRvIHRvZ2dsZS5cbiAgICovXG4gIGNvbnN0IGhhbmRsZVRvZ2dsZVJvbGUgPSAocm9sZTogUm9sZSkgPT4ge1xuICAgIHNldEFjdGl2ZVJvbGVzKChwcmV2Um9sZXMpID0+XG4gICAgICBwcmV2Um9sZXMuaW5jbHVkZXMocm9sZSlcbiAgICAgICAgPyBwcmV2Um9sZXMuZmlsdGVyKChyKSA9PiByICE9PSByb2xlKVxuICAgICAgICA6IFsuLi5wcmV2Um9sZXMsIHJvbGVdLFxuICAgICk7XG4gIH07XG5cbiAgY29uc3QgcmVuZGVyQ29udGVudCA9ICgpID0+IHtcbiAgICBzd2l0Y2ggKGFjdGl2ZVZpZXcpIHtcbiAgICAgIGNhc2UgXCJjaGF0XCI6XG4gICAgICAgIHJldHVybiA8Q2hhdCAvPjtcbiAgICAgIGNhc2UgXCJzYWxlc1wiOlxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxGZWF0dXJlVmlld0d1YXJkXG4gICAgICAgICAgICBhY3RpdmVSb2xlcz17YWN0aXZlUm9sZXN9XG4gICAgICAgICAgICByZXF1aXJlZFJvbGU9XCJzYWxlc1wiXG4gICAgICAgICAgICByb2xlTmFtZT1cIlNhbGVzXCJcbiAgICAgICAgICAgIG9uTmF2aWdhdGVUb1NldHRpbmdzPXsoKSA9PiBzZXRBY3RpdmVWaWV3KFwic2V0dGluZ3NcIil9XG4gICAgICAgICAgPlxuICAgICAgICAgICAgPFNhbGVzIC8+XG4gICAgICAgICAgPC9GZWF0dXJlVmlld0d1YXJkPlxuICAgICAgICApO1xuICAgICAgY2FzZSBcInByb2plY3RzXCI6XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgPEZlYXR1cmVWaWV3R3VhcmRcbiAgICAgICAgICAgIGFjdGl2ZVJvbGVzPXthY3RpdmVSb2xlc31cbiAgICAgICAgICAgIHJlcXVpcmVkUm9sZT1cInByb2plY3RfbWFuYWdlclwiXG4gICAgICAgICAgICByb2xlTmFtZT1cIlByb2plY3QgTWFuYWdlclwiXG4gICAgICAgICAgICBvbk5hdmlnYXRlVG9TZXR0aW5ncz17KCkgPT4gc2V0QWN0aXZlVmlldyhcInNldHRpbmdzXCIpfVxuICAgICAgICAgID5cbiAgICAgICAgICAgIDxQcm9qZWN0cyAvPlxuICAgICAgICAgIDwvRmVhdHVyZVZpZXdHdWFyZD5cbiAgICAgICAgKTtcbiAgICAgIGNhc2UgXCJzdXBwb3J0XCI6XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgPEZlYXR1cmVWaWV3R3VhcmRcbiAgICAgICAgICAgIGFjdGl2ZVJvbGVzPXthY3RpdmVSb2xlc31cbiAgICAgICAgICAgIHJlcXVpcmVkUm9sZT1cInN1cHBvcnRcIlxuICAgICAgICAgICAgcm9sZU5hbWU9XCJTdXBwb3J0XCJcbiAgICAgICAgICAgIG9uTmF2aWdhdGVUb1NldHRpbmdzPXsoKSA9PiBzZXRBY3RpdmVWaWV3KFwic2V0dGluZ3NcIil9XG4gICAgICAgICAgPlxuICAgICAgICAgICAgPFN1cHBvcnQgLz5cbiAgICAgICAgICA8L0ZlYXR1cmVWaWV3R3VhcmQ+XG4gICAgICAgICk7XG4gICAgICBjYXNlIFwic2V0dGluZ3NcIjpcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8VXNlclJvbGVcbiAgICAgICAgICAgIGFjdGl2ZVJvbGVzPXthY3RpdmVSb2xlc31cbiAgICAgICAgICAgIGF2YWlsYWJsZVJvbGVzPXtBVkFJTEFCTEVfUk9MRVN9XG4gICAgICAgICAgICBvblRvZ2dsZVJvbGU9e2hhbmRsZVRvZ2dsZVJvbGV9XG4gICAgICAgICAgLz5cbiAgICAgICAgKTtcbiAgICAgIGNhc2UgXCJpbnRlZ3JhdGlvbnNcIjpcbiAgICAgICAgcmV0dXJuIDxJbnRlZ3JhdGlvbnMgLz47XG4gICAgICBjYXNlIFwicHJvamVjdC1oZWFsdGhcIjpcbiAgICAgICAgcmV0dXJuIDxQcm9qZWN0SGVhbHRoIC8+O1xuICAgICAgY2FzZSBcImNvbXBldGl0b3ItYW5hbHlzaXNcIjpcbiAgICAgICAgcmV0dXJuIDxDb21wZXRpdG9yQW5hbHlzaXMgLz47XG4gICAgICBjYXNlIFwibGVhcm5pbmctYXNzaXN0YW50XCI6XG4gICAgICAgIHJldHVybiA8TGVhcm5pbmdBc3Npc3RhbnQgLz47XG4gICAgICBjYXNlIFwiZmluYW5jZVwiOlxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxGZWF0dXJlVmlld0d1YXJkXG4gICAgICAgICAgICBhY3RpdmVSb2xlcz17YWN0aXZlUm9sZXN9XG4gICAgICAgICAgICByZXF1aXJlZFJvbGU9XCJmaW5hbmNpYWxfYW5hbHlzdFwiXG4gICAgICAgICAgICByb2xlTmFtZT1cIkZpbmFuY2lhbCBBbmFseXN0XCJcbiAgICAgICAgICAgIG9uTmF2aWdhdGVUb1NldHRpbmdzPXsoKSA9PiBzZXRBY3RpdmVWaWV3KFwic2V0dGluZ3NcIil9XG4gICAgICAgICAgPlxuICAgICAgICAgICAgPEZpbmFuY2UgLz5cbiAgICAgICAgICA8L0ZlYXR1cmVWaWV3R3VhcmQ+XG4gICAgICAgICk7XG4gICAgICBjYXNlIFwicmVzZWFyY2hcIjpcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8RmVhdHVyZVZpZXdHdWFyZFxuICAgICAgICAgICAgYWN0aXZlUm9sZXM9e2FjdGl2ZVJvbGVzfVxuICAgICAgICAgICAgcmVxdWlyZWRSb2xlPVwicmVzZWFyY2hlclwiXG4gICAgICAgICAgICByb2xlTmFtZT1cIlJlc2VhcmNoZXJcIlxuICAgICAgICAgICAgb25OYXZpZ2F0ZVRvU2V0dGluZ3M9eygpID0+IHNldEFjdGl2ZVZpZXcoXCJzZXR0aW5nc1wiKX1cbiAgICAgICAgICA+XG4gICAgICAgICAgICA8UmVzZWFyY2ggLz5cbiAgICAgICAgICA8L0ZlYXR1cmVWaWV3R3VhcmQ+XG4gICAgICAgICk7XG4gICAgICBjYXNlIFwic29jaWFsXCI6XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgPEZlYXR1cmVWaWV3R3VhcmRcbiAgICAgICAgICAgIGFjdGl2ZVJvbGVzPXthY3RpdmVSb2xlc31cbiAgICAgICAgICAgIHJlcXVpcmVkUm9sZT1cInNvY2lhbF9tZWRpYV9tYW5hZ2VyXCJcbiAgICAgICAgICAgIHJvbGVOYW1lPVwiU29jaWFsIE1lZGlhIE1hbmFnZXJcIlxuICAgICAgICAgICAgb25OYXZpZ2F0ZVRvU2V0dGluZ3M9eygpID0+IHNldEFjdGl2ZVZpZXcoXCJzZXR0aW5nc1wiKX1cbiAgICAgICAgICA+XG4gICAgICAgICAgICA8U29jaWFsIC8+XG4gICAgICAgICAgPC9GZWF0dXJlVmlld0d1YXJkPlxuICAgICAgICApO1xuICAgICAgY2FzZSBcImNvbnRlbnRcIjpcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8RmVhdHVyZVZpZXdHdWFyZFxuICAgICAgICAgICAgYWN0aXZlUm9sZXM9e2FjdGl2ZVJvbGVzfVxuICAgICAgICAgICAgcmVxdWlyZWRSb2xlPVwiY29udGVudF9jcmVhdG9yXCJcbiAgICAgICAgICAgIHJvbGVOYW1lPVwiQ29udGVudCBDcmVhdG9yXCJcbiAgICAgICAgICAgIG9uTmF2aWdhdGVUb1NldHRpbmdzPXsoKSA9PiBzZXRBY3RpdmVWaWV3KFwic2V0dGluZ3NcIil9XG4gICAgICAgICAgPlxuICAgICAgICAgICAgPENvbnRlbnQgLz5cbiAgICAgICAgICA8L0ZlYXR1cmVWaWV3R3VhcmQ+XG4gICAgICAgICk7XG4gICAgICBjYXNlIFwic2hvcHBpbmdcIjpcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8RmVhdHVyZVZpZXdHdWFyZFxuICAgICAgICAgICAgYWN0aXZlUm9sZXM9e2FjdGl2ZVJvbGVzfVxuICAgICAgICAgICAgcmVxdWlyZWRSb2xlPVwic2hvcHBlclwiXG4gICAgICAgICAgICByb2xlTmFtZT1cIlNob3BwZXJcIlxuICAgICAgICAgICAgb25OYXZpZ2F0ZVRvU2V0dGluZ3M9eygpID0+IHNldEFjdGl2ZVZpZXcoXCJzZXR0aW5nc1wiKX1cbiAgICAgICAgICA+XG4gICAgICAgICAgICA8U2hvcHBpbmcgLz5cbiAgICAgICAgICA8L0ZlYXR1cmVWaWV3R3VhcmQ+XG4gICAgICAgICk7XG4gICAgICBkZWZhdWx0OlxuICAgICAgICByZXR1cm4gPENoYXQgLz47XG4gICAgfVxuICB9O1xuXG4gIHJldHVybiAoXG4gICAgPGRpdiBjbGFzc05hbWU9XCJBcHBcIj5cbiAgICAgIDxEYXNoYm9hcmQgc2V0QWN0aXZlVmlldz17c2V0QWN0aXZlVmlld30gLz5cbiAgICAgIDxkaXYgY2xhc3NOYW1lPVwiY29udGVudFwiPlxuICAgICAgICB7cmVuZGVyQ29udGVudCgpfVxuICAgICAgPC9kaXY+XG4gICAgPC9kaXY+XG4gICk7XG59XG5cbmV4cG9ydCBkZWZhdWx0IEFwcDtcbiJdfQ==
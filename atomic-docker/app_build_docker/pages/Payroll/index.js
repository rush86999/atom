"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const SideBarWithHeader_1 = __importDefault(require("../../layouts/SideBarWithHeader"));
const user_context_1 = require("../../lib/user-context");
const userRoleContext_1 = require("../../contexts/userRole/userRoleContext");
const Payroll = () => {
    const { user } = (0, user_context_1.useUser)();
    const { hasRole } = (0, userRoleContext_1.useUserRole)();
    const [payrolls, setPayrolls] = (0, react_1.useState)([]);
    (0, react_1.useEffect)(() => {
        const getPayrolls = async () => {
            const response = await fetch(`/api/financial/payrolls?user_id=${user.id}`);
            const { data } = await response.json();
            setPayrolls(data);
        };
        if (user && hasRole('finance')) {
            getPayrolls();
        }
    }, [user, hasRole]);
    if (!hasRole('finance')) {
        return (0, jsx_runtime_1.jsx)("div", { children: "You do not have permission to view this page." });
    }
    return ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h1", { children: "Payroll" }), (0, jsx_runtime_1.jsx)("ul", { children: payrolls.map((payroll) => ((0, jsx_runtime_1.jsxs)("li", { children: ["Payroll #", payroll.id, ": $", payroll.amount] }, payroll.id))) })] }));
};
exports.default = (0, SideBarWithHeader_1.default)(Payroll);
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsaUNBQW1EO0FBQ25ELHdGQUFvRTtBQUNwRSx5REFBaUQ7QUFDakQsNkVBQXNFO0FBRXRFLE1BQU0sT0FBTyxHQUFHLEdBQUcsRUFBRTtJQUNuQixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsSUFBQSxzQkFBTyxHQUFFLENBQUM7SUFDM0IsTUFBTSxFQUFFLE9BQU8sRUFBRSxHQUFHLElBQUEsNkJBQVcsR0FBRSxDQUFDO0lBQ2xDLE1BQU0sQ0FBQyxRQUFRLEVBQUUsV0FBVyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBRTdDLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixNQUFNLFdBQVcsR0FBRyxLQUFLLElBQUksRUFBRTtZQUM3QixNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxtQ0FBbUMsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDM0UsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ3ZDLFdBQVcsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUNwQixDQUFDLENBQUM7UUFDRixJQUFJLElBQUksSUFBSSxPQUFPLENBQUMsU0FBUyxDQUFDLEVBQUUsQ0FBQztZQUMvQixXQUFXLEVBQUUsQ0FBQztRQUNoQixDQUFDO0lBQ0gsQ0FBQyxFQUFFLENBQUMsSUFBSSxFQUFFLE9BQU8sQ0FBQyxDQUFDLENBQUM7SUFFcEIsSUFBSSxDQUFDLE9BQU8sQ0FBQyxTQUFTLENBQUMsRUFBRSxDQUFDO1FBQ3hCLE9BQU8sNEZBQXdELENBQUM7SUFDbEUsQ0FBQztJQUVELE9BQU8sQ0FDTCw0Q0FDRSxxREFBZ0IsRUFDaEIseUNBQ0csUUFBUSxDQUFDLEdBQUcsQ0FBQyxDQUFDLE9BQU8sRUFBRSxFQUFFLENBQUMsQ0FDekIsd0RBQ1ksT0FBTyxDQUFDLEVBQUUsU0FBSyxPQUFPLENBQUMsTUFBTSxLQURoQyxPQUFPLENBQUMsRUFBRSxDQUVkLENBQ04sQ0FBQyxHQUNDLElBQ0QsQ0FDUCxDQUFDO0FBQ0osQ0FBQyxDQUFDO0FBRUYsa0JBQWUsSUFBQSwyQkFBcUIsRUFBQyxPQUFPLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwgeyB1c2VFZmZlY3QsIHVzZVN0YXRlIH0gZnJvbSAncmVhY3QnO1xuaW1wb3J0IHdpdGhTaWRlQmFyV2l0aEhlYWRlciBmcm9tICcuLi8uLi9sYXlvdXRzL1NpZGVCYXJXaXRoSGVhZGVyJztcbmltcG9ydCB7IHVzZVVzZXIgfSBmcm9tICcuLi8uLi9saWIvdXNlci1jb250ZXh0JztcbmltcG9ydCB7IHVzZVVzZXJSb2xlIH0gZnJvbSAnLi4vLi4vY29udGV4dHMvdXNlclJvbGUvdXNlclJvbGVDb250ZXh0JztcblxuY29uc3QgUGF5cm9sbCA9ICgpID0+IHtcbiAgY29uc3QgeyB1c2VyIH0gPSB1c2VVc2VyKCk7XG4gIGNvbnN0IHsgaGFzUm9sZSB9ID0gdXNlVXNlclJvbGUoKTtcbiAgY29uc3QgW3BheXJvbGxzLCBzZXRQYXlyb2xsc10gPSB1c2VTdGF0ZShbXSk7XG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICBjb25zdCBnZXRQYXlyb2xscyA9IGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYC9hcGkvZmluYW5jaWFsL3BheXJvbGxzP3VzZXJfaWQ9JHt1c2VyLmlkfWApO1xuICAgICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICBzZXRQYXlyb2xscyhkYXRhKTtcbiAgICB9O1xuICAgIGlmICh1c2VyICYmIGhhc1JvbGUoJ2ZpbmFuY2UnKSkge1xuICAgICAgZ2V0UGF5cm9sbHMoKTtcbiAgICB9XG4gIH0sIFt1c2VyLCBoYXNSb2xlXSk7XG5cbiAgaWYgKCFoYXNSb2xlKCdmaW5hbmNlJykpIHtcbiAgICByZXR1cm4gPGRpdj5Zb3UgZG8gbm90IGhhdmUgcGVybWlzc2lvbiB0byB2aWV3IHRoaXMgcGFnZS48L2Rpdj47XG4gIH1cblxuICByZXR1cm4gKFxuICAgIDxkaXY+XG4gICAgICA8aDE+UGF5cm9sbDwvaDE+XG4gICAgICA8dWw+XG4gICAgICAgIHtwYXlyb2xscy5tYXAoKHBheXJvbGwpID0+IChcbiAgICAgICAgICA8bGkga2V5PXtwYXlyb2xsLmlkfT5cbiAgICAgICAgICAgIFBheXJvbGwgI3twYXlyb2xsLmlkfTogJHtwYXlyb2xsLmFtb3VudH1cbiAgICAgICAgICA8L2xpPlxuICAgICAgICApKX1cbiAgICAgIDwvdWw+XG4gICAgPC9kaXY+XG4gICk7XG59O1xuXG5leHBvcnQgZGVmYXVsdCB3aXRoU2lkZUJhcldpdGhIZWFkZXIoUGF5cm9sbCk7XG4iXX0=
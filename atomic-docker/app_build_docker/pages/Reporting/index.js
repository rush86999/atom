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
const Reporting = () => {
    const { user } = (0, user_context_1.useUser)();
    const { hasRole } = (0, userRoleContext_1.useUserRole)();
    const [spendingReport, setSpendingReport] = (0, react_1.useState)({});
    (0, react_1.useEffect)(() => {
        const getSpendingReport = async () => {
            const response = await fetch(`/api/financial/reports/spending?user_id=${user.id}`);
            const { data } = await response.json();
            setSpendingReport(data);
        };
        if (user && hasRole('finance')) {
            getSpendingReport();
        }
    }, [user, hasRole]);
    if (!hasRole('finance')) {
        return (0, jsx_runtime_1.jsx)("div", { children: "You do not have permission to view this page." });
    }
    return ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h1", { children: "Reporting" }), (0, jsx_runtime_1.jsx)("h2", { children: "Spending by Category" }), (0, jsx_runtime_1.jsx)("ul", { children: Object.entries(spendingReport).map(([category, amount]) => ((0, jsx_runtime_1.jsxs)("li", { children: [category, ": $", amount] }, category))) })] }));
};
exports.default = (0, SideBarWithHeader_1.default)(Reporting);
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsaUNBQW1EO0FBQ25ELHdGQUFvRTtBQUNwRSx5REFBaUQ7QUFDakQsNkVBQXNFO0FBRXRFLE1BQU0sU0FBUyxHQUFHLEdBQUcsRUFBRTtJQUNyQixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsSUFBQSxzQkFBTyxHQUFFLENBQUM7SUFDM0IsTUFBTSxFQUFFLE9BQU8sRUFBRSxHQUFHLElBQUEsNkJBQVcsR0FBRSxDQUFDO0lBQ2xDLE1BQU0sQ0FBQyxjQUFjLEVBQUUsaUJBQWlCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFFekQsSUFBQSxpQkFBUyxFQUFDLEdBQUcsRUFBRTtRQUNiLE1BQU0saUJBQWlCLEdBQUcsS0FBSyxJQUFJLEVBQUU7WUFDbkMsTUFBTSxRQUFRLEdBQUcsTUFBTSxLQUFLLENBQUMsMkNBQTJDLElBQUksQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1lBQ25GLE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxNQUFNLFFBQVEsQ0FBQyxJQUFJLEVBQUUsQ0FBQztZQUN2QyxpQkFBaUIsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUMxQixDQUFDLENBQUM7UUFDRixJQUFJLElBQUksSUFBSSxPQUFPLENBQUMsU0FBUyxDQUFDLEVBQUUsQ0FBQztZQUMvQixpQkFBaUIsRUFBRSxDQUFDO1FBQ3RCLENBQUM7SUFDSCxDQUFDLEVBQUUsQ0FBQyxJQUFJLEVBQUUsT0FBTyxDQUFDLENBQUMsQ0FBQztJQUVwQixJQUFJLENBQUMsT0FBTyxDQUFDLFNBQVMsQ0FBQyxFQUFFLENBQUM7UUFDeEIsT0FBTyw0RkFBd0QsQ0FBQztJQUNsRSxDQUFDO0lBRUQsT0FBTyxDQUNMLDRDQUNFLHVEQUFrQixFQUNsQixrRUFBNkIsRUFDN0IseUNBQ0csTUFBTSxDQUFDLE9BQU8sQ0FBQyxjQUFjLENBQUMsQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FDMUQsMkNBQ0csUUFBUSxTQUFLLE1BQU0sS0FEYixRQUFRLENBRVosQ0FDTixDQUFDLEdBQ0MsSUFDRCxDQUNQLENBQUM7QUFDSixDQUFDLENBQUM7QUFFRixrQkFBZSxJQUFBLDJCQUFxQixFQUFDLFNBQVMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCc7XG5pbXBvcnQgd2l0aFNpZGVCYXJXaXRoSGVhZGVyIGZyb20gJy4uLy4uL2xheW91dHMvU2lkZUJhcldpdGhIZWFkZXInO1xuaW1wb3J0IHsgdXNlVXNlciB9IGZyb20gJy4uLy4uL2xpYi91c2VyLWNvbnRleHQnO1xuaW1wb3J0IHsgdXNlVXNlclJvbGUgfSBmcm9tICcuLi8uLi9jb250ZXh0cy91c2VyUm9sZS91c2VyUm9sZUNvbnRleHQnO1xuXG5jb25zdCBSZXBvcnRpbmcgPSAoKSA9PiB7XG4gIGNvbnN0IHsgdXNlciB9ID0gdXNlVXNlcigpO1xuICBjb25zdCB7IGhhc1JvbGUgfSA9IHVzZVVzZXJSb2xlKCk7XG4gIGNvbnN0IFtzcGVuZGluZ1JlcG9ydCwgc2V0U3BlbmRpbmdSZXBvcnRdID0gdXNlU3RhdGUoe30pO1xuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgY29uc3QgZ2V0U3BlbmRpbmdSZXBvcnQgPSBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKGAvYXBpL2ZpbmFuY2lhbC9yZXBvcnRzL3NwZW5kaW5nP3VzZXJfaWQ9JHt1c2VyLmlkfWApO1xuICAgICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICBzZXRTcGVuZGluZ1JlcG9ydChkYXRhKTtcbiAgICB9O1xuICAgIGlmICh1c2VyICYmIGhhc1JvbGUoJ2ZpbmFuY2UnKSkge1xuICAgICAgZ2V0U3BlbmRpbmdSZXBvcnQoKTtcbiAgICB9XG4gIH0sIFt1c2VyLCBoYXNSb2xlXSk7XG5cbiAgaWYgKCFoYXNSb2xlKCdmaW5hbmNlJykpIHtcbiAgICByZXR1cm4gPGRpdj5Zb3UgZG8gbm90IGhhdmUgcGVybWlzc2lvbiB0byB2aWV3IHRoaXMgcGFnZS48L2Rpdj47XG4gIH1cblxuICByZXR1cm4gKFxuICAgIDxkaXY+XG4gICAgICA8aDE+UmVwb3J0aW5nPC9oMT5cbiAgICAgIDxoMj5TcGVuZGluZyBieSBDYXRlZ29yeTwvaDI+XG4gICAgICA8dWw+XG4gICAgICAgIHtPYmplY3QuZW50cmllcyhzcGVuZGluZ1JlcG9ydCkubWFwKChbY2F0ZWdvcnksIGFtb3VudF0pID0+IChcbiAgICAgICAgICA8bGkga2V5PXtjYXRlZ29yeX0+XG4gICAgICAgICAgICB7Y2F0ZWdvcnl9OiAke2Ftb3VudH1cbiAgICAgICAgICA8L2xpPlxuICAgICAgICApKX1cbiAgICAgIDwvdWw+XG4gICAgPC9kaXY+XG4gICk7XG59O1xuXG5leHBvcnQgZGVmYXVsdCB3aXRoU2lkZUJhcldpdGhIZWFkZXIoUmVwb3J0aW5nKTtcbiJdfQ==
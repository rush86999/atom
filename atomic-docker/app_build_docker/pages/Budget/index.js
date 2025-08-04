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
const Budget = () => {
    const { user } = (0, user_context_1.useUser)();
    const { hasRole } = (0, userRoleContext_1.useUserRole)();
    const [budgets, setBudgets] = (0, react_1.useState)([]);
    (0, react_1.useEffect)(() => {
        const getBudgets = async () => {
            const response = await fetch(`/api/financial/budgets?user_id=${user.id}`);
            const { data } = await response.json();
            setBudgets(data);
        };
        if (user && hasRole('finance')) {
            getBudgets();
        }
    }, [user, hasRole]);
    if (!hasRole('finance')) {
        return (0, jsx_runtime_1.jsx)("div", { children: "You do not have permission to view this page." });
    }
    return ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h1", { children: "Budget" }), (0, jsx_runtime_1.jsx)("ul", { children: budgets.map((budget) => ((0, jsx_runtime_1.jsxs)("li", { children: [budget.category, ": $", budget.amount] }, budget.category))) })] }));
};
exports.default = (0, SideBarWithHeader_1.default)(Budget);
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsaUNBQW1EO0FBQ25ELHdGQUFvRTtBQUNwRSx5REFBaUQ7QUFDakQsNkVBQXNFO0FBRXRFLE1BQU0sTUFBTSxHQUFHLEdBQUcsRUFBRTtJQUNsQixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsSUFBQSxzQkFBTyxHQUFFLENBQUM7SUFDM0IsTUFBTSxFQUFFLE9BQU8sRUFBRSxHQUFHLElBQUEsNkJBQVcsR0FBRSxDQUFDO0lBQ2xDLE1BQU0sQ0FBQyxPQUFPLEVBQUUsVUFBVSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBRTNDLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixNQUFNLFVBQVUsR0FBRyxLQUFLLElBQUksRUFBRTtZQUM1QixNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxrQ0FBa0MsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDMUUsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ3ZDLFVBQVUsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUNuQixDQUFDLENBQUM7UUFDRixJQUFJLElBQUksSUFBSSxPQUFPLENBQUMsU0FBUyxDQUFDLEVBQUUsQ0FBQztZQUMvQixVQUFVLEVBQUUsQ0FBQztRQUNmLENBQUM7SUFDSCxDQUFDLEVBQUUsQ0FBQyxJQUFJLEVBQUUsT0FBTyxDQUFDLENBQUMsQ0FBQztJQUVwQixJQUFJLENBQUMsT0FBTyxDQUFDLFNBQVMsQ0FBQyxFQUFFLENBQUM7UUFDeEIsT0FBTyw0RkFBd0QsQ0FBQztJQUNsRSxDQUFDO0lBRUQsT0FBTyxDQUNMLDRDQUNFLG9EQUFlLEVBQ2YseUNBQ0csT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLENBQUMsQ0FDdkIsMkNBQ0csTUFBTSxDQUFDLFFBQVEsU0FBSyxNQUFNLENBQUMsTUFBTSxLQUQzQixNQUFNLENBQUMsUUFBUSxDQUVuQixDQUNOLENBQUMsR0FDQyxJQUNELENBQ1AsQ0FBQztBQUNKLENBQUMsQ0FBQztBQUVGLGtCQUFlLElBQUEsMkJBQXFCLEVBQUMsTUFBTSxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHsgdXNlRWZmZWN0LCB1c2VTdGF0ZSB9IGZyb20gJ3JlYWN0JztcbmltcG9ydCB3aXRoU2lkZUJhcldpdGhIZWFkZXIgZnJvbSAnLi4vLi4vbGF5b3V0cy9TaWRlQmFyV2l0aEhlYWRlcic7XG5pbXBvcnQgeyB1c2VVc2VyIH0gZnJvbSAnLi4vLi4vbGliL3VzZXItY29udGV4dCc7XG5pbXBvcnQgeyB1c2VVc2VyUm9sZSB9IGZyb20gJy4uLy4uL2NvbnRleHRzL3VzZXJSb2xlL3VzZXJSb2xlQ29udGV4dCc7XG5cbmNvbnN0IEJ1ZGdldCA9ICgpID0+IHtcbiAgY29uc3QgeyB1c2VyIH0gPSB1c2VVc2VyKCk7XG4gIGNvbnN0IHsgaGFzUm9sZSB9ID0gdXNlVXNlclJvbGUoKTtcbiAgY29uc3QgW2J1ZGdldHMsIHNldEJ1ZGdldHNdID0gdXNlU3RhdGUoW10pO1xuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgY29uc3QgZ2V0QnVkZ2V0cyA9IGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goYC9hcGkvZmluYW5jaWFsL2J1ZGdldHM/dXNlcl9pZD0ke3VzZXIuaWR9YCk7XG4gICAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgIHNldEJ1ZGdldHMoZGF0YSk7XG4gICAgfTtcbiAgICBpZiAodXNlciAmJiBoYXNSb2xlKCdmaW5hbmNlJykpIHtcbiAgICAgIGdldEJ1ZGdldHMoKTtcbiAgICB9XG4gIH0sIFt1c2VyLCBoYXNSb2xlXSk7XG5cbiAgaWYgKCFoYXNSb2xlKCdmaW5hbmNlJykpIHtcbiAgICByZXR1cm4gPGRpdj5Zb3UgZG8gbm90IGhhdmUgcGVybWlzc2lvbiB0byB2aWV3IHRoaXMgcGFnZS48L2Rpdj47XG4gIH1cblxuICByZXR1cm4gKFxuICAgIDxkaXY+XG4gICAgICA8aDE+QnVkZ2V0PC9oMT5cbiAgICAgIDx1bD5cbiAgICAgICAge2J1ZGdldHMubWFwKChidWRnZXQpID0+IChcbiAgICAgICAgICA8bGkga2V5PXtidWRnZXQuY2F0ZWdvcnl9PlxuICAgICAgICAgICAge2J1ZGdldC5jYXRlZ29yeX06ICR7YnVkZ2V0LmFtb3VudH1cbiAgICAgICAgICA8L2xpPlxuICAgICAgICApKX1cbiAgICAgIDwvdWw+XG4gICAgPC9kaXY+XG4gICk7XG59O1xuXG5leHBvcnQgZGVmYXVsdCB3aXRoU2lkZUJhcldpdGhIZWFkZXIoQnVkZ2V0KTtcbiJdfQ==
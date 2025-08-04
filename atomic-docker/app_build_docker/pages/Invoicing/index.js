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
const Invoicing = () => {
    const { user } = (0, user_context_1.useUser)();
    const { hasRole } = (0, userRoleContext_1.useUserRole)();
    const [invoices, setInvoices] = (0, react_1.useState)([]);
    (0, react_1.useEffect)(() => {
        const getInvoices = async () => {
            const response = await fetch(`/api/financial/invoices?user_id=${user.id}`);
            const { data } = await response.json();
            setInvoices(data);
        };
        if (user && hasRole('finance')) {
            getInvoices();
        }
    }, [user, hasRole]);
    if (!hasRole('finance')) {
        return (0, jsx_runtime_1.jsx)("div", { children: "You do not have permission to view this page." });
    }
    return ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h1", { children: "Invoicing" }), (0, jsx_runtime_1.jsx)("ul", { children: invoices.map((invoice) => ((0, jsx_runtime_1.jsxs)("li", { children: ["Invoice #", invoice.id, ": $", invoice.amount] }, invoice.id))) })] }));
};
exports.default = (0, SideBarWithHeader_1.default)(Invoicing);
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsaUNBQW1EO0FBQ25ELHdGQUFvRTtBQUNwRSx5REFBaUQ7QUFDakQsNkVBQXNFO0FBRXRFLE1BQU0sU0FBUyxHQUFHLEdBQUcsRUFBRTtJQUNyQixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsSUFBQSxzQkFBTyxHQUFFLENBQUM7SUFDM0IsTUFBTSxFQUFFLE9BQU8sRUFBRSxHQUFHLElBQUEsNkJBQVcsR0FBRSxDQUFDO0lBQ2xDLE1BQU0sQ0FBQyxRQUFRLEVBQUUsV0FBVyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBRTdDLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixNQUFNLFdBQVcsR0FBRyxLQUFLLElBQUksRUFBRTtZQUM3QixNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxtQ0FBbUMsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDM0UsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ3ZDLFdBQVcsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUNwQixDQUFDLENBQUM7UUFDRixJQUFJLElBQUksSUFBSSxPQUFPLENBQUMsU0FBUyxDQUFDLEVBQUUsQ0FBQztZQUMvQixXQUFXLEVBQUUsQ0FBQztRQUNoQixDQUFDO0lBQ0gsQ0FBQyxFQUFFLENBQUMsSUFBSSxFQUFFLE9BQU8sQ0FBQyxDQUFDLENBQUM7SUFFcEIsSUFBSSxDQUFDLE9BQU8sQ0FBQyxTQUFTLENBQUMsRUFBRSxDQUFDO1FBQ3hCLE9BQU8sNEZBQXdELENBQUM7SUFDbEUsQ0FBQztJQUVELE9BQU8sQ0FDTCw0Q0FDRSx1REFBa0IsRUFDbEIseUNBQ0csUUFBUSxDQUFDLEdBQUcsQ0FBQyxDQUFDLE9BQU8sRUFBRSxFQUFFLENBQUMsQ0FDekIsd0RBQ1ksT0FBTyxDQUFDLEVBQUUsU0FBSyxPQUFPLENBQUMsTUFBTSxLQURoQyxPQUFPLENBQUMsRUFBRSxDQUVkLENBQ04sQ0FBQyxHQUNDLElBQ0QsQ0FDUCxDQUFDO0FBQ0osQ0FBQyxDQUFDO0FBRUYsa0JBQWUsSUFBQSwyQkFBcUIsRUFBQyxTQUFTLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwgeyB1c2VFZmZlY3QsIHVzZVN0YXRlIH0gZnJvbSAncmVhY3QnO1xuaW1wb3J0IHdpdGhTaWRlQmFyV2l0aEhlYWRlciBmcm9tICcuLi8uLi9sYXlvdXRzL1NpZGVCYXJXaXRoSGVhZGVyJztcbmltcG9ydCB7IHVzZVVzZXIgfSBmcm9tICcuLi8uLi9saWIvdXNlci1jb250ZXh0JztcbmltcG9ydCB7IHVzZVVzZXJSb2xlIH0gZnJvbSAnLi4vLi4vY29udGV4dHMvdXNlclJvbGUvdXNlclJvbGVDb250ZXh0JztcblxuY29uc3QgSW52b2ljaW5nID0gKCkgPT4ge1xuICBjb25zdCB7IHVzZXIgfSA9IHVzZVVzZXIoKTtcbiAgY29uc3QgeyBoYXNSb2xlIH0gPSB1c2VVc2VyUm9sZSgpO1xuICBjb25zdCBbaW52b2ljZXMsIHNldEludm9pY2VzXSA9IHVzZVN0YXRlKFtdKTtcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGNvbnN0IGdldEludm9pY2VzID0gYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgL2FwaS9maW5hbmNpYWwvaW52b2ljZXM/dXNlcl9pZD0ke3VzZXIuaWR9YCk7XG4gICAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgIHNldEludm9pY2VzKGRhdGEpO1xuICAgIH07XG4gICAgaWYgKHVzZXIgJiYgaGFzUm9sZSgnZmluYW5jZScpKSB7XG4gICAgICBnZXRJbnZvaWNlcygpO1xuICAgIH1cbiAgfSwgW3VzZXIsIGhhc1JvbGVdKTtcblxuICBpZiAoIWhhc1JvbGUoJ2ZpbmFuY2UnKSkge1xuICAgIHJldHVybiA8ZGl2PllvdSBkbyBub3QgaGF2ZSBwZXJtaXNzaW9uIHRvIHZpZXcgdGhpcyBwYWdlLjwvZGl2PjtcbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPGRpdj5cbiAgICAgIDxoMT5JbnZvaWNpbmc8L2gxPlxuICAgICAgPHVsPlxuICAgICAgICB7aW52b2ljZXMubWFwKChpbnZvaWNlKSA9PiAoXG4gICAgICAgICAgPGxpIGtleT17aW52b2ljZS5pZH0+XG4gICAgICAgICAgICBJbnZvaWNlICN7aW52b2ljZS5pZH06ICR7aW52b2ljZS5hbW91bnR9XG4gICAgICAgICAgPC9saT5cbiAgICAgICAgKSl9XG4gICAgICA8L3VsPlxuICAgIDwvZGl2PlxuICApO1xufTtcblxuZXhwb3J0IGRlZmF1bHQgd2l0aFNpZGVCYXJXaXRoSGVhZGVyKEludm9pY2luZyk7XG4iXX0=
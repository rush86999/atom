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
const Billing = () => {
    const { user } = (0, user_context_1.useUser)();
    const { hasRole } = (0, userRoleContext_1.useUserRole)();
    const [bills, setBills] = (0, react_1.useState)([]);
    (0, react_1.useEffect)(() => {
        const getBills = async () => {
            const response = await fetch(`/api/financial/bills?user_id=${user.id}`);
            const { data } = await response.json();
            setBills(data);
        };
        if (user && hasRole('finance')) {
            getBills();
        }
    }, [user, hasRole]);
    if (!hasRole('finance')) {
        return (0, jsx_runtime_1.jsx)("div", { children: "You do not have permission to view this page." });
    }
    return ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h1", { children: "Billing" }), (0, jsx_runtime_1.jsx)("ul", { children: bills.map((bill) => ((0, jsx_runtime_1.jsxs)("li", { children: ["Bill #", bill.id, ": $", bill.amount] }, bill.id))) })] }));
};
exports.default = (0, SideBarWithHeader_1.default)(Billing);
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsaUNBQW1EO0FBQ25ELHdGQUFvRTtBQUNwRSx5REFBaUQ7QUFDakQsNkVBQXNFO0FBRXRFLE1BQU0sT0FBTyxHQUFHLEdBQUcsRUFBRTtJQUNuQixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsSUFBQSxzQkFBTyxHQUFFLENBQUM7SUFDM0IsTUFBTSxFQUFFLE9BQU8sRUFBRSxHQUFHLElBQUEsNkJBQVcsR0FBRSxDQUFDO0lBQ2xDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsUUFBUSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBRXZDLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixNQUFNLFFBQVEsR0FBRyxLQUFLLElBQUksRUFBRTtZQUMxQixNQUFNLFFBQVEsR0FBRyxNQUFNLEtBQUssQ0FBQyxnQ0FBZ0MsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDeEUsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ3ZDLFFBQVEsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUNqQixDQUFDLENBQUM7UUFDRixJQUFJLElBQUksSUFBSSxPQUFPLENBQUMsU0FBUyxDQUFDLEVBQUUsQ0FBQztZQUMvQixRQUFRLEVBQUUsQ0FBQztRQUNiLENBQUM7SUFDSCxDQUFDLEVBQUUsQ0FBQyxJQUFJLEVBQUUsT0FBTyxDQUFDLENBQUMsQ0FBQztJQUVwQixJQUFJLENBQUMsT0FBTyxDQUFDLFNBQVMsQ0FBQyxFQUFFLENBQUM7UUFDeEIsT0FBTyw0RkFBd0QsQ0FBQztJQUNsRSxDQUFDO0lBRUQsT0FBTyxDQUNMLDRDQUNFLHFEQUFnQixFQUNoQix5Q0FDRyxLQUFLLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FBQyxDQUNuQixxREFDUyxJQUFJLENBQUMsRUFBRSxTQUFLLElBQUksQ0FBQyxNQUFNLEtBRHZCLElBQUksQ0FBQyxFQUFFLENBRVgsQ0FDTixDQUFDLEdBQ0MsSUFDRCxDQUNQLENBQUM7QUFDSixDQUFDLENBQUM7QUFFRixrQkFBZSxJQUFBLDJCQUFxQixFQUFDLE9BQU8sQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCc7XG5pbXBvcnQgd2l0aFNpZGVCYXJXaXRoSGVhZGVyIGZyb20gJy4uLy4uL2xheW91dHMvU2lkZUJhcldpdGhIZWFkZXInO1xuaW1wb3J0IHsgdXNlVXNlciB9IGZyb20gJy4uLy4uL2xpYi91c2VyLWNvbnRleHQnO1xuaW1wb3J0IHsgdXNlVXNlclJvbGUgfSBmcm9tICcuLi8uLi9jb250ZXh0cy91c2VyUm9sZS91c2VyUm9sZUNvbnRleHQnO1xuXG5jb25zdCBCaWxsaW5nID0gKCkgPT4ge1xuICBjb25zdCB7IHVzZXIgfSA9IHVzZVVzZXIoKTtcbiAgY29uc3QgeyBoYXNSb2xlIH0gPSB1c2VVc2VyUm9sZSgpO1xuICBjb25zdCBbYmlsbHMsIHNldEJpbGxzXSA9IHVzZVN0YXRlKFtdKTtcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGNvbnN0IGdldEJpbGxzID0gYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgL2FwaS9maW5hbmNpYWwvYmlsbHM/dXNlcl9pZD0ke3VzZXIuaWR9YCk7XG4gICAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgIHNldEJpbGxzKGRhdGEpO1xuICAgIH07XG4gICAgaWYgKHVzZXIgJiYgaGFzUm9sZSgnZmluYW5jZScpKSB7XG4gICAgICBnZXRCaWxscygpO1xuICAgIH1cbiAgfSwgW3VzZXIsIGhhc1JvbGVdKTtcblxuICBpZiAoIWhhc1JvbGUoJ2ZpbmFuY2UnKSkge1xuICAgIHJldHVybiA8ZGl2PllvdSBkbyBub3QgaGF2ZSBwZXJtaXNzaW9uIHRvIHZpZXcgdGhpcyBwYWdlLjwvZGl2PjtcbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPGRpdj5cbiAgICAgIDxoMT5CaWxsaW5nPC9oMT5cbiAgICAgIDx1bD5cbiAgICAgICAge2JpbGxzLm1hcCgoYmlsbCkgPT4gKFxuICAgICAgICAgIDxsaSBrZXk9e2JpbGwuaWR9PlxuICAgICAgICAgICAgQmlsbCAje2JpbGwuaWR9OiAke2JpbGwuYW1vdW50fVxuICAgICAgICAgIDwvbGk+XG4gICAgICAgICkpfVxuICAgICAgPC91bD5cbiAgICA8L2Rpdj5cbiAgKTtcbn07XG5cbmV4cG9ydCBkZWZhdWx0IHdpdGhTaWRlQmFyV2l0aEhlYWRlcihCaWxsaW5nKTtcbiJdfQ==
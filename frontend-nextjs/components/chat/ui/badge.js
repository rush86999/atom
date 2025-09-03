"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.badgeVariants = void 0;
exports.Badge = Badge;
const jsx_runtime_1 = require("react/jsx-runtime");
const class_variance_authority_1 = require("class-variance-authority");
const utils_1 = require("@lib/Chat/utils");
const badgeVariants = (0, class_variance_authority_1.cva)('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold font-sans transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2', // Added font-sans, updated focus ring
{
    variants: {
        variant: {
            default: 'border-transparent bg-sky-100 text-sky-700 dark:bg-sky-800 dark:text-sky-200',
            secondary: 'border-transparent bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200',
            destructive: 'border-transparent bg-red-100 text-red-700 dark:bg-red-800 dark:text-red-200',
            outline: 'text-gray-600 border-gray-300 dark:text-gray-300 dark:border-gray-600'
        }
    },
    defaultVariants: {
        variant: 'default'
    }
});
exports.badgeVariants = badgeVariants;
function Badge({ className, variant, ...props }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)(badgeVariants({ variant }), className), ...props }));
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYmFkZ2UuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJiYWRnZS50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBbUNTLHNCQUFLOztBQWxDZCx1RUFBaUU7QUFFakUsMkNBQW9DO0FBRXBDLE1BQU0sYUFBYSxHQUFHLElBQUEsOEJBQUcsRUFDdkIscUxBQXFMLEVBQUUsc0NBQXNDO0FBQzdOO0lBQ0UsUUFBUSxFQUFFO1FBQ1IsT0FBTyxFQUFFO1lBQ1AsT0FBTyxFQUNMLDhFQUE4RTtZQUNoRixTQUFTLEVBQ1Asa0ZBQWtGO1lBQ3BGLFdBQVcsRUFDVCw4RUFBOEU7WUFDaEYsT0FBTyxFQUFFLHVFQUF1RTtTQUNqRjtLQUNGO0lBQ0QsZUFBZSxFQUFFO1FBQ2YsT0FBTyxFQUFFLFNBQVM7S0FDbkI7Q0FDRixDQUNGLENBQUE7QUFZZSxzQ0FBYTtBQU43QixTQUFTLEtBQUssQ0FBQyxFQUFFLFNBQVMsRUFBRSxPQUFPLEVBQUUsR0FBRyxLQUFLLEVBQWM7SUFDekQsT0FBTyxDQUNMLGdDQUFLLFNBQVMsRUFBRSxJQUFBLFVBQUUsRUFBQyxhQUFhLENBQUMsRUFBRSxPQUFPLEVBQUUsQ0FBQyxFQUFFLFNBQVMsQ0FBQyxLQUFNLEtBQUssR0FBSSxDQUN6RSxDQUFBO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCAqIGFzIFJlYWN0IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgY3ZhLCB0eXBlIFZhcmlhbnRQcm9wcyB9IGZyb20gJ2NsYXNzLXZhcmlhbmNlLWF1dGhvcml0eSdcblxuaW1wb3J0IHsgY24gfSBmcm9tICdAbGliL0NoYXQvdXRpbHMnXG5cbmNvbnN0IGJhZGdlVmFyaWFudHMgPSBjdmEoXG4gICdpbmxpbmUtZmxleCBpdGVtcy1jZW50ZXIgcm91bmRlZC1mdWxsIGJvcmRlciBweC0yLjUgcHktMC41IHRleHQteHMgZm9udC1zZW1pYm9sZCBmb250LXNhbnMgdHJhbnNpdGlvbi1jb2xvcnMgZm9jdXM6b3V0bGluZS1ub25lIGZvY3VzOnJpbmctMiBmb2N1czpyaW5nLXNreS01MDAgZm9jdXM6cmluZy1vZmZzZXQtMicsIC8vIEFkZGVkIGZvbnQtc2FucywgdXBkYXRlZCBmb2N1cyByaW5nXG4gIHtcbiAgICB2YXJpYW50czoge1xuICAgICAgdmFyaWFudDoge1xuICAgICAgICBkZWZhdWx0OlxuICAgICAgICAgICdib3JkZXItdHJhbnNwYXJlbnQgYmctc2t5LTEwMCB0ZXh0LXNreS03MDAgZGFyazpiZy1za3ktODAwIGRhcms6dGV4dC1za3ktMjAwJyxcbiAgICAgICAgc2Vjb25kYXJ5OlxuICAgICAgICAgICdib3JkZXItdHJhbnNwYXJlbnQgYmctZ3JheS0xMDAgdGV4dC1ncmF5LTcwMCBkYXJrOmJnLWdyYXktNzAwIGRhcms6dGV4dC1ncmF5LTIwMCcsXG4gICAgICAgIGRlc3RydWN0aXZlOlxuICAgICAgICAgICdib3JkZXItdHJhbnNwYXJlbnQgYmctcmVkLTEwMCB0ZXh0LXJlZC03MDAgZGFyazpiZy1yZWQtODAwIGRhcms6dGV4dC1yZWQtMjAwJyxcbiAgICAgICAgb3V0bGluZTogJ3RleHQtZ3JheS02MDAgYm9yZGVyLWdyYXktMzAwIGRhcms6dGV4dC1ncmF5LTMwMCBkYXJrOmJvcmRlci1ncmF5LTYwMCdcbiAgICAgIH1cbiAgICB9LFxuICAgIGRlZmF1bHRWYXJpYW50czoge1xuICAgICAgdmFyaWFudDogJ2RlZmF1bHQnXG4gICAgfVxuICB9XG4pXG5cbmV4cG9ydCBpbnRlcmZhY2UgQmFkZ2VQcm9wc1xuICBleHRlbmRzIFJlYWN0LkhUTUxBdHRyaWJ1dGVzPEhUTUxEaXZFbGVtZW50PixcbiAgICBWYXJpYW50UHJvcHM8dHlwZW9mIGJhZGdlVmFyaWFudHM+IHt9XG5cbmZ1bmN0aW9uIEJhZGdlKHsgY2xhc3NOYW1lLCB2YXJpYW50LCAuLi5wcm9wcyB9OiBCYWRnZVByb3BzKSB7XG4gIHJldHVybiAoXG4gICAgPGRpdiBjbGFzc05hbWU9e2NuKGJhZGdlVmFyaWFudHMoeyB2YXJpYW50IH0pLCBjbGFzc05hbWUpfSB7Li4ucHJvcHN9IC8+XG4gIClcbn1cblxuZXhwb3J0IHsgQmFkZ2UsIGJhZGdlVmFyaWFudHMgfSJdfQ==
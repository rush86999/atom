"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.buttonVariants = exports.Button = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const React = __importStar(require("react"));
const react_slot_1 = require("@radix-ui/react-slot");
const class_variance_authority_1 = require("class-variance-authority");
const utils_1 = require("@lib/Chat/utils");
const buttonVariants = (0, class_variance_authority_1.cva)('inline-flex items-center justify-center rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 font-sans', // Added rounded-lg, focus-visible:ring-sky-500 and font-sans (system font stack will be inherited)
{
    variants: {
        variant: {
            default: 'bg-sky-600 text-white hover:bg-sky-700 dark:bg-sky-500 dark:hover:bg-sky-600', // Removed shadow-md
            destructive: 'bg-red-500 text-white hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700',
            outline: 'border border-sky-600 text-sky-600 hover:bg-sky-100 dark:border-sky-500 dark:text-sky-500 dark:hover:bg-sky-900',
            secondary: 'bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600',
            ghost: 'hover:bg-gray-100 dark:hover:bg-gray-700 shadow-none', // Removed shadow-none as it's base now
            link: 'text-sky-600 underline-offset-4 hover:underline dark:text-sky-400 shadow-none' // Removed shadow-none
        },
        size: {
            default: 'h-9 px-4 py-2', // Adjusted height for better proportions
            sm: 'h-8 rounded-md px-3',
            lg: 'h-11 rounded-lg px-8', // Adjusted rounding
            icon: 'h-9 w-9 p-0' // Adjusted height/width for icon buttons
        }
    },
    defaultVariants: {
        variant: 'default',
        size: 'default'
    }
});
exports.buttonVariants = buttonVariants;
const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? react_slot_1.Slot : 'button';
    return ((0, jsx_runtime_1.jsx)(Comp, { className: (0, utils_1.cn)(buttonVariants({ variant, size, className }), 'font-medium'), ref: ref, ...props }));
});
exports.Button = Button;
Button.displayName = 'Button';
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYnV0dG9uLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYnV0dG9uLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0FBQUEsNkNBQThCO0FBQzlCLHFEQUEyQztBQUMzQyx1RUFBaUU7QUFFakUsMkNBQW9DO0FBRXBDLE1BQU0sY0FBYyxHQUFHLElBQUEsOEJBQUcsRUFDeEIsNFBBQTRQLEVBQUUsbUdBQW1HO0FBQ2pXO0lBQ0UsUUFBUSxFQUFFO1FBQ1IsT0FBTyxFQUFFO1lBQ1AsT0FBTyxFQUNMLDhFQUE4RSxFQUFFLG9CQUFvQjtZQUN0RyxXQUFXLEVBQ1QsOEVBQThFO1lBQ2hGLE9BQU8sRUFDTCxpSEFBaUg7WUFDbkgsU0FBUyxFQUNQLHdHQUF3RztZQUMxRyxLQUFLLEVBQUUsc0RBQXNELEVBQUUsdUNBQXVDO1lBQ3RHLElBQUksRUFBRSwrRUFBK0UsQ0FBQyxzQkFBc0I7U0FDN0c7UUFDRCxJQUFJLEVBQUU7WUFDSixPQUFPLEVBQUUsZUFBZSxFQUFFLHlDQUF5QztZQUNuRSxFQUFFLEVBQUUscUJBQXFCO1lBQ3pCLEVBQUUsRUFBRSxzQkFBc0IsRUFBRSxvQkFBb0I7WUFDaEQsSUFBSSxFQUFFLGFBQWEsQ0FBQyx5Q0FBeUM7U0FDOUQ7S0FDRjtJQUNELGVBQWUsRUFBRTtRQUNmLE9BQU8sRUFBRSxTQUFTO1FBQ2xCLElBQUksRUFBRSxTQUFTO0tBQ2hCO0NBQ0YsQ0FDRixDQUFBO0FBc0JnQix3Q0FBYztBQWQvQixNQUFNLE1BQU0sR0FBRyxLQUFLLENBQUMsVUFBVSxDQUM3QixDQUFDLEVBQUUsU0FBUyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsT0FBTyxHQUFHLEtBQUssRUFBRSxHQUFHLEtBQUssRUFBRSxFQUFFLEdBQUcsRUFBRSxFQUFFO0lBQy9ELE1BQU0sSUFBSSxHQUFHLE9BQU8sQ0FBQyxDQUFDLENBQUMsaUJBQUksQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFBO0lBQ3RDLE9BQU8sQ0FDTCx1QkFBQyxJQUFJLElBQ0gsU0FBUyxFQUFFLElBQUEsVUFBRSxFQUFDLGNBQWMsQ0FBQyxFQUFFLE9BQU8sRUFBRSxJQUFJLEVBQUUsU0FBUyxFQUFFLENBQUMsRUFBRSxhQUFhLENBQUMsRUFDMUUsR0FBRyxFQUFFLEdBQUcsS0FDSixLQUFLLEdBQ1QsQ0FDSCxDQUFBO0FBQ0gsQ0FBQyxDQUNGLENBQUE7QUFHUSx3QkFBTTtBQUZmLE1BQU0sQ0FBQyxXQUFXLEdBQUcsUUFBUSxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0ICogYXMgUmVhY3QgZnJvbSAncmVhY3QnXG5pbXBvcnQgeyBTbG90IH0gZnJvbSAnQHJhZGl4LXVpL3JlYWN0LXNsb3QnXG5pbXBvcnQgeyBjdmEsIHR5cGUgVmFyaWFudFByb3BzIH0gZnJvbSAnY2xhc3MtdmFyaWFuY2UtYXV0aG9yaXR5J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJ0BsaWIvQ2hhdC91dGlscydcblxuY29uc3QgYnV0dG9uVmFyaWFudHMgPSBjdmEoXG4gICdpbmxpbmUtZmxleCBpdGVtcy1jZW50ZXIganVzdGlmeS1jZW50ZXIgcm91bmRlZC1sZyB0ZXh0LXNtIGZvbnQtbWVkaXVtIHRyYW5zaXRpb24tY29sb3JzIGZvY3VzLXZpc2libGU6b3V0bGluZS1ub25lIGZvY3VzLXZpc2libGU6cmluZy0yIGZvY3VzLXZpc2libGU6cmluZy1za3ktNTAwIGZvY3VzLXZpc2libGU6cmluZy1vZmZzZXQtMiBkaXNhYmxlZDpwb2ludGVyLWV2ZW50cy1ub25lIGRpc2FibGVkOm9wYWNpdHktNTAgZm9udC1zYW5zJywgLy8gQWRkZWQgcm91bmRlZC1sZywgZm9jdXMtdmlzaWJsZTpyaW5nLXNreS01MDAgYW5kIGZvbnQtc2FucyAoc3lzdGVtIGZvbnQgc3RhY2sgd2lsbCBiZSBpbmhlcml0ZWQpXG4gIHtcbiAgICB2YXJpYW50czoge1xuICAgICAgdmFyaWFudDoge1xuICAgICAgICBkZWZhdWx0OlxuICAgICAgICAgICdiZy1za3ktNjAwIHRleHQtd2hpdGUgaG92ZXI6Ymctc2t5LTcwMCBkYXJrOmJnLXNreS01MDAgZGFyazpob3ZlcjpiZy1za3ktNjAwJywgLy8gUmVtb3ZlZCBzaGFkb3ctbWRcbiAgICAgICAgZGVzdHJ1Y3RpdmU6XG4gICAgICAgICAgJ2JnLXJlZC01MDAgdGV4dC13aGl0ZSBob3ZlcjpiZy1yZWQtNjAwIGRhcms6YmctcmVkLTYwMCBkYXJrOmhvdmVyOmJnLXJlZC03MDAnLFxuICAgICAgICBvdXRsaW5lOlxuICAgICAgICAgICdib3JkZXIgYm9yZGVyLXNreS02MDAgdGV4dC1za3ktNjAwIGhvdmVyOmJnLXNreS0xMDAgZGFyazpib3JkZXItc2t5LTUwMCBkYXJrOnRleHQtc2t5LTUwMCBkYXJrOmhvdmVyOmJnLXNreS05MDAnLFxuICAgICAgICBzZWNvbmRhcnk6XG4gICAgICAgICAgJ2JnLWdyYXktMjAwIHRleHQtZ3JheS04MDAgaG92ZXI6YmctZ3JheS0zMDAgZGFyazpiZy1ncmF5LTcwMCBkYXJrOnRleHQtZ3JheS0xMDAgZGFyazpob3ZlcjpiZy1ncmF5LTYwMCcsXG4gICAgICAgIGdob3N0OiAnaG92ZXI6YmctZ3JheS0xMDAgZGFyazpob3ZlcjpiZy1ncmF5LTcwMCBzaGFkb3ctbm9uZScsIC8vIFJlbW92ZWQgc2hhZG93LW5vbmUgYXMgaXQncyBiYXNlIG5vd1xuICAgICAgICBsaW5rOiAndGV4dC1za3ktNjAwIHVuZGVybGluZS1vZmZzZXQtNCBob3Zlcjp1bmRlcmxpbmUgZGFyazp0ZXh0LXNreS00MDAgc2hhZG93LW5vbmUnIC8vIFJlbW92ZWQgc2hhZG93LW5vbmVcbiAgICAgIH0sXG4gICAgICBzaXplOiB7XG4gICAgICAgIGRlZmF1bHQ6ICdoLTkgcHgtNCBweS0yJywgLy8gQWRqdXN0ZWQgaGVpZ2h0IGZvciBiZXR0ZXIgcHJvcG9ydGlvbnNcbiAgICAgICAgc206ICdoLTggcm91bmRlZC1tZCBweC0zJyxcbiAgICAgICAgbGc6ICdoLTExIHJvdW5kZWQtbGcgcHgtOCcsIC8vIEFkanVzdGVkIHJvdW5kaW5nXG4gICAgICAgIGljb246ICdoLTkgdy05IHAtMCcgLy8gQWRqdXN0ZWQgaGVpZ2h0L3dpZHRoIGZvciBpY29uIGJ1dHRvbnNcbiAgICAgIH1cbiAgICB9LFxuICAgIGRlZmF1bHRWYXJpYW50czoge1xuICAgICAgdmFyaWFudDogJ2RlZmF1bHQnLFxuICAgICAgc2l6ZTogJ2RlZmF1bHQnXG4gICAgfVxuICB9XG4pXG5cbmV4cG9ydCBpbnRlcmZhY2UgQnV0dG9uUHJvcHNcbiAgZXh0ZW5kcyBSZWFjdC5CdXR0b25IVE1MQXR0cmlidXRlczxIVE1MQnV0dG9uRWxlbWVudD4sXG4gICAgVmFyaWFudFByb3BzPHR5cGVvZiBidXR0b25WYXJpYW50cz4ge1xuICBhc0NoaWxkPzogYm9vbGVhblxufVxuXG5jb25zdCBCdXR0b24gPSBSZWFjdC5mb3J3YXJkUmVmPEhUTUxCdXR0b25FbGVtZW50LCBCdXR0b25Qcm9wcz4oXG4gICh7IGNsYXNzTmFtZSwgdmFyaWFudCwgc2l6ZSwgYXNDaGlsZCA9IGZhbHNlLCAuLi5wcm9wcyB9LCByZWYpID0+IHtcbiAgICBjb25zdCBDb21wID0gYXNDaGlsZCA/IFNsb3QgOiAnYnV0dG9uJ1xuICAgIHJldHVybiAoXG4gICAgICA8Q29tcFxuICAgICAgICBjbGFzc05hbWU9e2NuKGJ1dHRvblZhcmlhbnRzKHsgdmFyaWFudCwgc2l6ZSwgY2xhc3NOYW1lIH0pLCAnZm9udC1tZWRpdW0nKX0gLy8gRW5zdXJlIGZvbnQtbWVkaXVtIGlzIGFwcGxpZWRcbiAgICAgICAgcmVmPXtyZWZ9XG4gICAgICAgIHsuLi5wcm9wc31cbiAgICAgIC8+XG4gICAgKVxuICB9XG4pXG5CdXR0b24uZGlzcGxheU5hbWUgPSAnQnV0dG9uJ1xuXG5leHBvcnQgeyBCdXR0b24sIGJ1dHRvblZhcmlhbnRzIH0iXX0=
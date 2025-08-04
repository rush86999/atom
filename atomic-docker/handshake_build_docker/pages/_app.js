"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
require("../styles/globals.css");
const react_1 = require("@chakra-ui/react");
const theme_1 = __importDefault(require("../lib/theme"));
require("react-datepicker/dist/react-datepicker.css");
require("../styles/time-preferences.scss");
const react_2 = require("@vercel/analytics/react");
function MyApp({ Component, pageProps }) {
    return ((0, jsx_runtime_1.jsx)(react_1.ChakraProvider, { theme: theme_1.default, children: (0, jsx_runtime_1.jsxs)("div", { className: "h-full w-full", children: [(0, jsx_runtime_1.jsx)(Component, { ...pageProps }), (0, jsx_runtime_1.jsx)(react_2.Analytics, {})] }) }));
}
exports.default = MyApp;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiX2FwcC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIl9hcHAudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUFBLGlDQUE4QjtBQUU5Qiw0Q0FBaUQ7QUFDakQseURBQWdDO0FBQ2hDLHNEQUFvRDtBQUNwRCwyQ0FBd0M7QUFDeEMsbURBQW1EO0FBRW5ELFNBQVMsS0FBSyxDQUFDLEVBQUUsU0FBUyxFQUFFLFNBQVMsRUFBWTtJQUMvQyxPQUFPLENBQ0gsdUJBQUMsc0JBQWMsSUFBQyxLQUFLLEVBQUUsZUFBSyxZQUMxQixpQ0FBSyxTQUFTLEVBQUMsZUFBZSxhQUM1Qix1QkFBQyxTQUFTLE9BQUssU0FBUyxHQUFJLEVBQzVCLHVCQUFDLGlCQUFTLEtBQUcsSUFDVCxHQUNTLENBQ2xCLENBQUE7QUFDTCxDQUFDO0FBRUQsa0JBQWUsS0FBSyxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0ICcuLi9zdHlsZXMvZ2xvYmFscy5jc3MnXG5pbXBvcnQgdHlwZSB7IEFwcFByb3BzIH0gZnJvbSAnbmV4dC9hcHAnXG5pbXBvcnQgeyBDaGFrcmFQcm92aWRlciB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5pbXBvcnQgdGhlbWUgZnJvbSAnLi4vbGliL3RoZW1lJ1xuaW1wb3J0IFwicmVhY3QtZGF0ZXBpY2tlci9kaXN0L3JlYWN0LWRhdGVwaWNrZXIuY3NzXCI7XG5pbXBvcnQgJy4uL3N0eWxlcy90aW1lLXByZWZlcmVuY2VzLnNjc3MnXG5pbXBvcnQgeyBBbmFseXRpY3MgfSBmcm9tICdAdmVyY2VsL2FuYWx5dGljcy9yZWFjdCdcblxuZnVuY3Rpb24gTXlBcHAoeyBDb21wb25lbnQsIHBhZ2VQcm9wcyB9OiBBcHBQcm9wcykge1xuICByZXR1cm4gKFxuICAgICAgPENoYWtyYVByb3ZpZGVyIHRoZW1lPXt0aGVtZX0+XG4gICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiaC1mdWxsIHctZnVsbFwiPlxuICAgICAgICAgIDxDb21wb25lbnQgey4uLnBhZ2VQcm9wc30gLz5cbiAgICAgICAgICA8QW5hbHl0aWNzIC8+XG4gICAgICAgIDwvZGl2PlxuICAgICAgPC9DaGFrcmFQcm92aWRlcj5cbiAgICApXG59XG5cbmV4cG9ydCBkZWZhdWx0IE15QXBwXG4iXX0=
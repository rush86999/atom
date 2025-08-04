"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
require("../styles/globals.css");
const react_1 = require("@chakra-ui/react");
const react_2 = require("@chakra-ui/react");
// 
const config = {
    useSystemColorMode: true,
    initialColorMode: 'dark',
};
const theme = (0, react_2.extendTheme)({
    config,
    colors: {
        zoom: "#0E72ED"
    },
});
// #0E72ED
function MyApp({ Component, pageProps }) {
    return ((0, jsx_runtime_1.jsx)(react_1.ChakraProvider, { theme: theme, children: (0, jsx_runtime_1.jsx)("div", { className: "h-screen w-full", children: (0, jsx_runtime_1.jsx)(Component, { ...pageProps }) }) }));
}
exports.default = MyApp;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiX2FwcC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIl9hcHAudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLGlDQUE4QjtBQUU5Qiw0Q0FBaUQ7QUFDakQsNENBQWdFO0FBR2hFLEdBQUc7QUFFSCxNQUFNLE1BQU0sR0FBZ0I7SUFDMUIsa0JBQWtCLEVBQUUsSUFBSTtJQUN4QixnQkFBZ0IsRUFBRSxNQUFNO0NBQ3pCLENBQUE7QUFFRCxNQUFNLEtBQUssR0FBRyxJQUFBLG1CQUFXLEVBQUM7SUFDeEIsTUFBTTtJQUNOLE1BQU0sRUFBRTtRQUNOLElBQUksRUFBRSxTQUFTO0tBQ2hCO0NBQ0YsQ0FBQyxDQUFBO0FBRUYsVUFBVTtBQUNWLFNBQVMsS0FBSyxDQUFDLEVBQUUsU0FBUyxFQUFFLFNBQVMsRUFBWTtJQUMvQyxPQUFPLENBQ0wsdUJBQUMsc0JBQWMsSUFBQyxLQUFLLEVBQUUsS0FBSyxZQUMxQixnQ0FBSyxTQUFTLEVBQUMsaUJBQWlCLFlBQzlCLHVCQUFDLFNBQVMsT0FBSyxTQUFTLEdBQUksR0FDeEIsR0FDUyxDQUNsQixDQUFBO0FBQ0gsQ0FBQztBQUVELGtCQUFlLEtBQUssQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCAnLi4vc3R5bGVzL2dsb2JhbHMuY3NzJ1xuaW1wb3J0IHR5cGUgeyBBcHBQcm9wcyB9IGZyb20gJ25leHQvYXBwJ1xuaW1wb3J0IHsgQ2hha3JhUHJvdmlkZXIgfSBmcm9tICdAY2hha3JhLXVpL3JlYWN0J1xuaW1wb3J0IHsgZXh0ZW5kVGhlbWUsIHR5cGUgVGhlbWVDb25maWcgfSBmcm9tIFwiQGNoYWtyYS11aS9yZWFjdFwiXG5cblxuLy8gXG5cbmNvbnN0IGNvbmZpZzogVGhlbWVDb25maWcgPSB7XG4gIHVzZVN5c3RlbUNvbG9yTW9kZTogdHJ1ZSxcbiAgaW5pdGlhbENvbG9yTW9kZTogJ2RhcmsnLFxufVxuXG5jb25zdCB0aGVtZSA9IGV4dGVuZFRoZW1lKHsgXG4gIGNvbmZpZywgXG4gIGNvbG9yczoge1xuICAgIHpvb206IFwiIzBFNzJFRFwiXG4gIH0sIFxufSlcblxuLy8gIzBFNzJFRFxuZnVuY3Rpb24gTXlBcHAoeyBDb21wb25lbnQsIHBhZ2VQcm9wcyB9OiBBcHBQcm9wcykge1xuICByZXR1cm4gKFxuICAgIDxDaGFrcmFQcm92aWRlciB0aGVtZT17dGhlbWV9PlxuICAgICAgPGRpdiBjbGFzc05hbWU9XCJoLXNjcmVlbiB3LWZ1bGxcIj5cbiAgICAgICAgPENvbXBvbmVudCB7Li4ucGFnZVByb3BzfSAvPlxuICAgICAgPC9kaXY+XG4gICAgPC9DaGFrcmFQcm92aWRlcj5cbiAgKVxufVxuXG5leHBvcnQgZGVmYXVsdCBNeUFwcFxuIl19
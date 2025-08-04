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
exports.Textarea = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const React = __importStar(require("react"));
const utils_1 = require("@lib/Chat/utils");
const Textarea = React.forwardRef(({ className, ...props }, ref) => {
    return ((0, jsx_runtime_1.jsx)("textarea", { className: (0, utils_1.cn)('flex min-h-[60px] w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-base font-sans text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-0 focus-visible:border-sky-500 dark:focus-visible:border-sky-500 disabled:cursor-not-allowed disabled:opacity-50 shadow-sm', // Adjusted styles for modern look, readability, and dark mode
        // Note: min-h-[60px] is often overridden by ChatInput.tsx specific styles if used there. Default min-h can be adjusted.
        className), ref: ref, ...props }));
});
exports.Textarea = Textarea;
Textarea.displayName = 'Textarea';
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGV4dGFyZWEuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ0ZXh0YXJlYS50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQUFBLDZDQUE4QjtBQUU5QiwyQ0FBb0M7QUFLcEMsTUFBTSxRQUFRLEdBQUcsS0FBSyxDQUFDLFVBQVUsQ0FDL0IsQ0FBQyxFQUFFLFNBQVMsRUFBRSxHQUFHLEtBQUssRUFBRSxFQUFFLEdBQUcsRUFBRSxFQUFFO0lBQy9CLE9BQU8sQ0FDTCxxQ0FDRSxTQUFTLEVBQUUsSUFBQSxVQUFFLEVBQ1gsbWNBQW1jLEVBQUUsOERBQThEO1FBQ25nQix3SEFBd0g7UUFDeEgsU0FBUyxDQUNWLEVBQ0QsR0FBRyxFQUFFLEdBQUcsS0FDSixLQUFLLEdBQ1QsQ0FDSCxDQUFBO0FBQ0gsQ0FBQyxDQUNGLENBQUE7QUFHUSw0QkFBUTtBQUZqQixRQUFRLENBQUMsV0FBVyxHQUFHLFVBQVUsQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCAqIGFzIFJlYWN0IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiB9IGZyb20gJ0BsaWIvQ2hhdC91dGlscydcblxuZXhwb3J0IGludGVyZmFjZSBUZXh0YXJlYVByb3BzXG4gIGV4dGVuZHMgUmVhY3QuVGV4dGFyZWFIVE1MQXR0cmlidXRlczxIVE1MVGV4dEFyZWFFbGVtZW50PiB7fVxuXG5jb25zdCBUZXh0YXJlYSA9IFJlYWN0LmZvcndhcmRSZWY8SFRNTFRleHRBcmVhRWxlbWVudCwgVGV4dGFyZWFQcm9wcz4oXG4gICh7IGNsYXNzTmFtZSwgLi4ucHJvcHMgfSwgcmVmKSA9PiB7XG4gICAgcmV0dXJuIChcbiAgICAgIDx0ZXh0YXJlYVxuICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICdmbGV4IG1pbi1oLVs2MHB4XSB3LWZ1bGwgcm91bmRlZC1sZyBib3JkZXIgYm9yZGVyLWdyYXktMzAwIGRhcms6Ym9yZGVyLWdyYXktNjAwIGJnLXdoaXRlIGRhcms6YmctZ3JheS04MDAgcHgtMyBweS0yIHRleHQtYmFzZSBmb250LXNhbnMgdGV4dC1ncmF5LTkwMCBkYXJrOnRleHQtZ3JheS0xMDAgcGxhY2Vob2xkZXI6dGV4dC1ncmF5LTQwMCBkYXJrOnBsYWNlaG9sZGVyOnRleHQtZ3JheS01MDAgZm9jdXMtdmlzaWJsZTpvdXRsaW5lLW5vbmUgZm9jdXMtdmlzaWJsZTpyaW5nLTIgZm9jdXMtdmlzaWJsZTpyaW5nLXNreS01MDAgZm9jdXMtdmlzaWJsZTpyaW5nLW9mZnNldC0wIGZvY3VzLXZpc2libGU6Ym9yZGVyLXNreS01MDAgZGFyazpmb2N1cy12aXNpYmxlOmJvcmRlci1za3ktNTAwIGRpc2FibGVkOmN1cnNvci1ub3QtYWxsb3dlZCBkaXNhYmxlZDpvcGFjaXR5LTUwIHNoYWRvdy1zbScsIC8vIEFkanVzdGVkIHN0eWxlcyBmb3IgbW9kZXJuIGxvb2ssIHJlYWRhYmlsaXR5LCBhbmQgZGFyayBtb2RlXG4gICAgICAgICAgLy8gTm90ZTogbWluLWgtWzYwcHhdIGlzIG9mdGVuIG92ZXJyaWRkZW4gYnkgQ2hhdElucHV0LnRzeCBzcGVjaWZpYyBzdHlsZXMgaWYgdXNlZCB0aGVyZS4gRGVmYXVsdCBtaW4taCBjYW4gYmUgYWRqdXN0ZWQuXG4gICAgICAgICAgY2xhc3NOYW1lXG4gICAgICAgICl9XG4gICAgICAgIHJlZj17cmVmfVxuICAgICAgICB7Li4ucHJvcHN9XG4gICAgICAvPlxuICAgIClcbiAgfVxuKVxuVGV4dGFyZWEuZGlzcGxheU5hbWUgPSAnVGV4dGFyZWEnXG5cbmV4cG9ydCB7IFRleHRhcmVhIH0iXX0=
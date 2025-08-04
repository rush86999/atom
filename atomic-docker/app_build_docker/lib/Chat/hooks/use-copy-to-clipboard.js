'use client';
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
exports.useCopyToClipboard = useCopyToClipboard;
const React = __importStar(require("react"));
function useCopyToClipboard({ timeout = 20000 }) {
    const [isCopied, setIsCopied] = React.useState(false);
    const copyToClipboard = (value) => {
        if (typeof window === 'undefined' || !navigator.clipboard?.writeText) {
            return;
        }
        if (!value) {
            return;
        }
        navigator.clipboard.writeText(value).then(() => {
            setIsCopied(true);
            setTimeout(() => {
                setIsCopied(false);
            }, timeout);
        });
    };
    return { isCopied, copyToClipboard };
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlLWNvcHktdG8tY2xpcGJvYXJkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXNlLWNvcHktdG8tY2xpcGJvYXJkLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxZQUFZLENBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQVFaLGdEQXdCQztBQTlCRCw2Q0FBOEI7QUFNOUIsU0FBZ0Isa0JBQWtCLENBQUMsRUFDakMsT0FBTyxHQUFHLEtBQUssRUFDUztJQUN4QixNQUFNLENBQUMsUUFBUSxFQUFFLFdBQVcsQ0FBQyxHQUFHLEtBQUssQ0FBQyxRQUFRLENBQVUsS0FBSyxDQUFDLENBQUE7SUFFOUQsTUFBTSxlQUFlLEdBQUcsQ0FBQyxLQUFhLEVBQUUsRUFBRTtRQUN4QyxJQUFJLE9BQU8sTUFBTSxLQUFLLFdBQVcsSUFBSSxDQUFDLFNBQVMsQ0FBQyxTQUFTLEVBQUUsU0FBUyxFQUFFLENBQUM7WUFDckUsT0FBTTtRQUNSLENBQUM7UUFFRCxJQUFJLENBQUMsS0FBSyxFQUFFLENBQUM7WUFDWCxPQUFNO1FBQ1IsQ0FBQztRQUVELFNBQVMsQ0FBQyxTQUFTLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLElBQUksQ0FBQyxHQUFHLEVBQUU7WUFDN0MsV0FBVyxDQUFDLElBQUksQ0FBQyxDQUFBO1lBRWpCLFVBQVUsQ0FBQyxHQUFHLEVBQUU7Z0JBQ2QsV0FBVyxDQUFDLEtBQUssQ0FBQyxDQUFBO1lBQ3BCLENBQUMsRUFBRSxPQUFPLENBQUMsQ0FBQTtRQUNiLENBQUMsQ0FBQyxDQUFBO0lBQ0osQ0FBQyxDQUFBO0lBRUQsT0FBTyxFQUFFLFFBQVEsRUFBRSxlQUFlLEVBQUUsQ0FBQTtBQUN0QyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCAqIGFzIFJlYWN0IGZyb20gJ3JlYWN0J1xuXG5leHBvcnQgaW50ZXJmYWNlIHVzZUNvcHlUb0NsaXBib2FyZFByb3BzIHtcbiAgdGltZW91dD86IG51bWJlclxufVxuXG5leHBvcnQgZnVuY3Rpb24gdXNlQ29weVRvQ2xpcGJvYXJkKHtcbiAgdGltZW91dCA9IDIwMDAwXG59OiB1c2VDb3B5VG9DbGlwYm9hcmRQcm9wcykge1xuICBjb25zdCBbaXNDb3BpZWQsIHNldElzQ29waWVkXSA9IFJlYWN0LnVzZVN0YXRlPEJvb2xlYW4+KGZhbHNlKVxuXG4gIGNvbnN0IGNvcHlUb0NsaXBib2FyZCA9ICh2YWx1ZTogc3RyaW5nKSA9PiB7XG4gICAgaWYgKHR5cGVvZiB3aW5kb3cgPT09ICd1bmRlZmluZWQnIHx8ICFuYXZpZ2F0b3IuY2xpcGJvYXJkPy53cml0ZVRleHQpIHtcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGlmICghdmFsdWUpIHtcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIG5hdmlnYXRvci5jbGlwYm9hcmQud3JpdGVUZXh0KHZhbHVlKS50aGVuKCgpID0+IHtcbiAgICAgIHNldElzQ29waWVkKHRydWUpXG5cbiAgICAgIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgICBzZXRJc0NvcGllZChmYWxzZSlcbiAgICAgIH0sIHRpbWVvdXQpXG4gICAgfSlcbiAgfVxuXG4gIHJldHVybiB7IGlzQ29waWVkLCBjb3B5VG9DbGlwYm9hcmQgfVxufSJdfQ==